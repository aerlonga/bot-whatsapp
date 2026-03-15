import io
import json
import PyPDF2
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import PROFILE, DEVICE, MODELO_TEXTO, MODELO_VISAO, WHISPER_MODEL
from app.services import ollama_service, whisper_service
from app.tasks.cleanup_memory import cleanup_expired_memories

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executa ao iniciar
    scheduler = AsyncIOScheduler()
    # Executa a limpeza a cada 6 horas
    scheduler.add_job(cleanup_expired_memories, 'interval', hours=6)
    scheduler.start()
    print("Scheduler de limpeza de memória iniciado (a cada 6 horas).")
    
    yield
    
    # Executa ao desligar
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

# ============================================
# SYSTEM PROMPT (Escolha a versão de acordo com o modelo)
# ============================================

# --- VERSÃO MODELO 3B (Bot Focado / Baixo contexto) ---
# SYSTEM_PROMPT = (
#     "Você é a Inteligência Financeira do Aerlon. "
#     "Sua função é EXCLUSIVA para gestão de gastos e orçamentos. "
#     "Se o usuário falar sobre qualquer outro tema, informe educadamente que você é um bot especializado em finanças. "
#     "Sempre apresente os comandos disponíveis: Digite !help para ajuda, "
#     "@gasto para registrar despesas ou ver o histórico, e @orçamento para consultas de saldo e planejamento."
# )

# --- VERSÃO MODELO 8B (Assistente Versátil / Recomendado) ---
SYSTEM_PROMPT = (
    "Você é o assistente pessoal do Aerlon, especializado em finanças. "
    "Você pode manter conversas curtas sobre outros temas, mas sua prioridade e trabalho principal é cuidar das finanças. "
    "Sempre informe ao usuário que você foca em finanças e apresente os comandos: "
    "Digite !help para ver todos os comandos, '@gasto' para registrar ou ver seu histórico e '@orçamento' para planejar seus saldos."
)

# ============================================
# ENDPOINTS
# ============================================

@app.post("/chat")
async def chat_endpoint(data: dict):
    try:
        from app.prompts.tools_definition import TOOLS_DEFINITION
        from app.tools.tool_runner import run_tool
        from app.services import context_service
        
        user_id = data.get("user_id", "default_user")
        pushname = data.get("pushname")
        
        # Atualiza nome do usuário se fornecido
        if pushname:
            await context_service.update_user_name(str(user_id), pushname)
        
        # Build context
        context_messages = await context_service.build_context_for_llama(user_id)
        
        # PROMPT DE SISTEMA MELHORADO PARA MODELOS PEQUENOS (LLAMA 3B)
        improved_system_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "REGRAS CRÍTICAS DE COMPORTAMENTO (SIGA SEMPRE):\n"
            "1. NUNCA chame uma ferramenta (tool/função) automaticamente. Ferramentas SÓ podem ser ativadas quando o usuário digitar EXPLICITAMENTE os comandos '@gasto' ou '@orçamento' no início da mensagem.\n"
            "2. Se o usuário perguntar sobre gastos de forma genérica (ex: 'você consegue ver meus gastos?', 'quanto gastei?'), responda apenas em texto explicando que ele pode usar '@gasto' para isso. NÃO execute nenhuma ferramenta.\n"
            "3. Se você chamar 'registrar_gasto', repasse EXATAMENTE a pergunta de confirmação que a ferramenta retornar.\n"
            "4. O usuário responderá 'Sim' ou 'Não' APENAS em resposta a uma confirmação de registro de gasto.\n"
            "5. NÃO peça 'Sim' ou 'Não' em conversas sobre outros temas (saudação, dúvidas, ajuda).\n"
            "6. Evite repetir 'Olá' no meio de uma conversa em andamento.\n"
            "7. Responda de forma direta, curta e amigável."
        )
        
        messages = [{'role': 'system', 'content': improved_system_prompt}]
        messages.extend(context_messages)
        
        user_msg_list = data.get("messages", [])
        messages.extend(user_msg_list)
        
        # Filtra as ferramentas baseada no gatilho ou estado pendente
        user_msg_content = user_msg_list[-1].get("content", "") if user_msg_list else ""
        trimmed_msg = user_msg_content.strip().lower()
        
        # Sempre verifica se há algo pendente para dar a ferramenta de confirmação
        pending_action = await context_service.get_pending_action(user_id)
        
        available_tools = []
        if trimmed_msg.startswith("@gasto"):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] in ['registrar_gasto', 'consultar_gastos']])
        elif trimmed_msg.startswith("@orçamento") or trimmed_msg.startswith("@orcamento"):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] in ['consultar_orcamentos', 'consultar_gastos']])
        
        # Se houver pendência ou o usuário parecer estar confirmando/negando, libera confirmar_acao
        if pending_action or any(x in trimmed_msg for x in ["sim", "não", "nao", "confirmo", "cancela"]):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] == 'confirmar_acao'])
            
        if not available_tools:
            available_tools = None

        response = await ollama_service.chat(messages=messages, tools=available_tools)
        
        ai_message = response.get('message', {})
        raw_content = ai_message.get('content', '')
        
        # Detecta se o modelo retornou um tool call como texto JSON bruto
        # (acontece quando o Ollama "pensa" mas não executa via tool_calls)
        def _is_raw_tool_call(text: str) -> bool:
            stripped = text.strip() if text else ""
            if not stripped.startswith("{"):
                return False
            try:
                parsed = json.loads(stripped)
                return "name" in parsed and ("parameters" in parsed or "arguments" in parsed)
            except (json.JSONDecodeError, ValueError):
                return False
        
        # Se Llama chamou alguma tool via mecanismo oficial
        if ai_message.get('tool_calls'):
            messages.append(ai_message)  # Add assistant's tool call message
            
            tool_replies = []
            for tool_call in ai_message.get('tool_calls', []):
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']
                
                # Executa a tool
                tool_result = await run_tool(tool_name, tool_args, user_id=user_id)
                
                if isinstance(tool_result, dict) and tool_result.get('result'):
                    tool_replies.append(tool_result['result'])
                
                messages.append({
                    'role': 'tool',
                    'content': json.dumps(tool_result),
                })
                
            # Usa as mensagens formatadas das próprias tools, se disponíveis
            if tool_replies:
                final_reply = "\n".join(tool_replies)
            else:
                # Segunda chamada para Ollama formatar a resposta apenas como fallback
                response = await ollama_service.chat(messages=messages)
                ai_message = response.get('message', {})
                final_reply = ai_message.get('content', '')
        elif _is_raw_tool_call(raw_content):
            # O modelo tentou chamar uma tool mas retornou como texto JSON (bug do Ollama)
            # Ignora o "fantasma" e pede ao modelo para responder em linguagem natural
            logger.warning(f"[Chat] Detectado tool call como texto JSON bruto. Descartando e pedindo resposta natural.")
            messages.append({'role': 'assistant', 'content': raw_content})
            messages.append({
                'role': 'user',
                'content': (
                    "[INSTRUÇÃO DO SISTEMA]: Você tentou chamar uma ferramenta sem o gatilho correto ('@gasto' ou '@orçamento'). "
                    "Por favor, responda a última mensagem do usuário SOMENTE em texto, sem chamar nenhuma ferramenta."
                )
            })
            response = await ollama_service.chat(messages=messages)
            ai_message = response.get('message', {})
            final_reply = ai_message.get('content', '')
        else:
            final_reply = raw_content
        
        # Save memory
        user_msg = user_msg_content
        if user_msg and final_reply:
            resumo = f"User: {user_msg}\nBot: {final_reply}"
            await context_service.save_context(str(user_id), resumo)
            
        return {"reply": final_reply}
    except Exception as e:
        traceback.print_exc()
        return {"reply": f"ERRO DE TEXTO: {str(e)}"}

@app.post("/vision")
async def vision_endpoint(prompt: str = Form("Descreva esta imagem"), file: UploadFile = File(...)):
    try:
        img_bytes = await file.read()
        response = await ollama_service.vision(prompt, img_bytes)
        return {"reply": response.get('message', {}).get('content', '')}
    except Exception as e:
        return {"reply": f"ERRO DE IMAGEM: {str(e)}"}

@app.post("/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = await whisper_service.transcribe(content)
        
        ai_res = await ollama_service.chat(messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f"O usuário enviou um áudio com este conteúdo: {text}. Responda adequadamente."}
        ])
        return {"reply": ai_res.get('message', {}).get('content', '')}
    except Exception as e:
        return {"reply": f"ERRO DE ÁUDIO: {str(e)}"}

@app.post("/pdf")
async def read_pdf_endpoint(file: UploadFile = File(...)):
    try:
        content = await file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                text = text + str(extracted)
        
        ai_res = await ollama_service.chat(messages=[
            {'role': 'system', 'content': f"{SYSTEM_PROMPT} Resuma o PDF enviado pelo usuário."},
            {'role': 'user', 'content': text[:8000]}
        ])
        return {"reply": ai_res.get('message', {}).get('content', '')}
    except Exception as e:
        return {"reply": f"ERRO DE PDF: {str(e)}"}

# ============================================
# HEALTH CHECK
# ============================================
@app.get("/health")
async def health():
    ollama_ok, ollama_msg = await ollama_service.check_connection()
    return {
        "status": "ok" if ollama_ok else "degraded",
        "ollama_status": ollama_msg,
        "profile": PROFILE,
        "device": DEVICE,
        "modelo_texto": MODELO_TEXTO,
        "modelo_visao": MODELO_VISAO,
        "whisper_model": WHISPER_MODEL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
