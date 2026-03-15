import io
import json
import PyPDF2
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import PROFILE, DEVICE, MODELO_TEXTO, MODELO_VISAO, WHISPER_MODEL
from app.prompts.system_prompt import SYSTEM_PROMPT
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

# SYSTEM_PROMPT importado de app.prompts.system_prompt

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
        
        # Prompt final com regras de comportamento para tools
        improved_system_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "REGRAS DE FERRAMENTAS:\n"
            "1. NUNCA chame ferramentas automaticamente. Ferramentas SÓ ativam com os comandos: '!gasto', '!orçamento', '!economia', '!pesquisa'.\n"
            "2. Se o usuário perguntar sobre gastos sem usar '!gasto', responda em texto que ele pode usar o comando.\n"
            "3. Repasse EXATAMENTE as confirmações retornadas pelas ferramentas.\n"
            "4. 'Sim'/'Não' do usuário é APENAS para confirmar ações pendentes.\n"
            "5. Responda de forma direta, curta e amigável."
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
        if trimmed_msg.startswith("!gasto"):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] in ['registrar_gasto', 'consultar_gastos']])
        elif trimmed_msg.startswith("!orçamento") or trimmed_msg.startswith("!orcamento"):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] in ['consultar_orcamentos', 'consultar_gastos']])
        elif trimmed_msg.startswith("!economia"):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] in ['registrar_economia', 'consultar_economias']])
        elif trimmed_msg.startswith("!pesquisa"):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] == 'pesquisar_web'])
        
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
                
                # Usamos a role 'tool' que é o esperado pelo Ollama após um tool_call.
                # Isso evita que o modelo se perca ou retorne vazio.
                tool_output = tool_result.get('result', str(tool_result))
                messages.append({
                    'role': 'tool',
                    'content': tool_output
                })
                
            # Instrução final de síntese para garantir que o modelo fale com o usuário
            messages.append({
                'role': 'system',
                'content': "SÍNTESE: Utilize os dados da ferramenta acima para responder ao usuário de forma direta. Se for um valor (Selic, Dólar, etc), informe o número exato encontrado."
            })
            
            # Segunda chamada ao Ollama para processar os resultados
            response = await ollama_service.chat(messages=messages)
            ai_message = response.get('message', {})
            final_reply = ai_message.get('content', '')

            # FALLBACK: Se o modelo retornar vazio (bug comum em 8B), tentamos uma última vez sem ferramentas
            if not final_reply.strip():
                print("[Chat] Segundo pass retornou vazio. Tentando fallback simples.")
                messages.append({
                    'role': 'user',
                    'content': "Por favor, apenas resume os dados acima para mim."
                })
                response = await ollama_service.chat(messages=messages)
                final_reply = response.get('message', {}).get('content', 'Não consegui processar a informação da pesquisa. Tente perguntar de outra forma.')
        elif _is_raw_tool_call(raw_content):
            # O modelo tentou chamar uma tool mas retornou como texto JSON (bug do Ollama)
            # Ignora o "fantasma" e pede ao modelo para responder em linguagem natural
            print(f"[Chat] Detectado tool call como texto JSON bruto. Descartando e pedindo resposta natural.")
            messages.append({'role': 'assistant', 'content': raw_content})
            messages.append({
                'role': 'user',
                'content': (
                    "[INSTRUÇÃO DO SISTEMA]: Você tentou chamar uma ferramenta sem o gatilho correto ('!gasto', '!orçamento', '!economia' ou '!pesquisa'). "
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
    print(f"Iniciando servidor FastAPI em http://0.0.0.0:8000 (Perfil: {PROFILE})")
    uvicorn.run(app, host="0.0.0.0", port=8000)
