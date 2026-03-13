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
# SYSTEM PROMPT
# ============================================
SYSTEM_PROMPT = (
    "Você é o assistente pessoal do Aerlon. "
    "REGRA DE OURO: Você possui ferramentas financeiras, mas elas SÓ podem ser usadas se o usuário usar os comandos '@gasto' ou '@orçamento'. "
    "Não mencione ferramentas financeiras, gastos ou orçamentos em mensagens de saudação ou conversas gerais, a menos que o usuário utilize os comandos. "
    "Se o usuário pedir para guardar uma informação, apenas confirme que guardou. "
    "Responda sempre no mesmo idioma que o usuário. Seja direto e profissional."
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
        
        # PROMPT DE SISTEMA MELHORADO
        improved_system_prompt = (
            f"{SYSTEM_PROMPT}\n"
            "INSTRUÇÕES DE FERRAMENTAS:\n"
            "1. Quando o usuário usar '@gasto', extraia Local, Valor, Categoria e Data. Se a data não for clara, use 'hoje'.\n"
            "2. Após chamar 'registrar_gasto', você receberá uma mensagem de confirmação. REPASSE essa mensagem exatamente para o usuário.\n"
            "3. Se o usuário confirmar (Sim) ou cancelar (Não), use a ferramenta 'confirmar_acao'.\n"
            "4. NUNCA responda com JSON bruto. Sempre fale de forma natural e amigável."
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
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] == 'registrar_gasto'])
        elif trimmed_msg.startswith("@orçamento") or trimmed_msg.startswith("@orcamento"):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] == 'consultar_orcamentos'])
        
        # Se houver pendência ou o usuário parecer estar confirmando/negando, libera confirmar_acao
        if pending_action or any(x in trimmed_msg for x in ["sim", "não", "nao", "confirmo", "cancela"]):
            available_tools.extend([t for t in TOOLS_DEFINITION if t['function']['name'] == 'confirmar_acao'])
            
        if not available_tools:
            available_tools = None

        response = await ollama_service.chat(messages=messages, tools=available_tools)
        
        ai_message = response.get('message', {})
        
        # Se Llama chamou alguma tool
        if ai_message.get('tool_calls'):
            messages.append(ai_message)  # Add assistant's tool call message
            
            for tool_call in ai_message.get('tool_calls', []):
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']
                
                # Executa a tool
                tool_result = await run_tool(tool_name, tool_args, user_id=user_id)
                
                messages.append({
                    'role': 'tool',
                    'content': json.dumps(tool_result),
                })
                
            # Segunda chamada para Ollama formatar a resposta
            response = await ollama_service.chat(messages=messages)
            ai_message = response.get('message', {})
            
        final_reply = ai_message.get('content', '')
        
        # Se o modelo falhou em dar um conteúdo mas a tool retornou algo amigável para confirmação, usa o result da tool
        if not final_reply and ai_message.get('tool_calls'):
             # Tenta achar o 'result' na última mensagem de tool
             for msg in reversed(messages):
                 if msg.get('role') == 'tool':
                     try:
                         res_data = json.loads(msg['content'])
                         if res_data.get('success') and res_data.get('result'):
                             final_reply = res_data['result']
                             break
                     except:
                         continue
        
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
