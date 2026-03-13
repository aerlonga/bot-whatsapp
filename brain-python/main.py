import os
import io
import PyPDF2
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
    "Você é um assistente inteligente e versátil. "
    "REGRA PRINCIPAL: Identifique o idioma do usuário e responda no MESMO idioma. "
    "Se o usuário falar em Português, responda em Português. Se falar em Inglês, responda em Inglês. "
    "Se o usuário pedir explicitamente para mudar de idioma, obedeça. "
    "Nunca misture idiomas na mesma frase (nada de portunhol). "
    "Seja direto, prestativo e mantenha o tom profissional."
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
        
        # Build context
        context_messages = await context_service.build_context_for_llama(user_id)
        
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        messages.extend(context_messages)
        messages.extend(data.get("messages", []))
        
        response = await ollama_service.chat(messages=messages, tools=TOOLS_DEFINITION)
        
        ai_message = response.get('message', {})
        
        # Se Llama chamou alguma tool
        if ai_message.get('tool_calls'):
            messages.append(ai_message)  # Add assistant's tool call message
            
            for tool_call in ai_message.get('tool_calls', []):
                tool_name = tool_call['function']['name']
                tool_args = tool_call['function']['arguments']
                
                # Executa a tool
                tool_result = await run_tool(tool_name, tool_args)
                
                messages.append({
                    'role': 'tool',
                    'content': str(tool_result),
                })
                
            # Segunda chamada para Ollama formatar a resposta
            response = await ollama_service.chat(messages=messages)
            ai_message = response.get('message', {})
            
        final_reply = ai_message.get('content', '')
        
        # Save memory
        user_msg = data.get("messages", [])[-1].get("content", "")
        if user_msg and final_reply:
            resumo = f"User: {user_msg}\nBot: {final_reply}"
            await context_service.save_context(str(user_id), resumo)
            
        return {"reply": final_reply}
    except Exception as e:
        import traceback
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
                text += extracted
        
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
