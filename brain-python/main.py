from fastapi import FastAPI, UploadFile, File, Form
import ollama
import whisper
import os
import PyPDF2
import io
import torch # Necessário para detectar sua RTX 4060

app = FastAPI()

# --- CONFIGURAÇÃO DE HARDWARE ---
# Detecta se você tem GPU (RTX 4060) ou se vai rodar no processador (PC Fraco)
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Sistema iniciado usando: {device.upper()}")

# Carregamento do Whisper Otimizado
# 'medium' é perfeito para sua 4060. Para PC fraco, use 'tiny' ou 'base'.
model_whisper = whisper.load_model("medium", device=device)

# --- DEFINIÇÃO DE MODELOS (Centralizado para facilitar o README) ---
# Altere aqui e mudará no bot todo:
MODELO_TEXTO = "llama3.1:8b" # Recomendado para RTX 4060
# MODELO_TEXTO = "gpt-oss:20b"   # Se quiser testar o limite (será lento)
# MODELO_TEXTO = "llama3.2:3b"   # Para PC Fraco / Sem Placa

MODELO_VISAO = "minicpm-v"     # RTX 4060 (Lê textos e detalhes)
# MODELO_VISAO = "moondream"     # PC Fraco

SYSTEM_PROMPT = (
    "Você é um assistente inteligente e versátil. "
    "REGRA PRINCIPAL: Identifique o idioma do usuário e responda no MESMO idioma. "
    "Se o usuário falar em Português, responda em Português. Se falar em Inglês, responda em Inglês. "
    "Nunca misture idiomas na mesma frase (nada de portunhol). "
    "Seja direto, prestativo e mantenha o tom profissional."
)

@app.post("/chat")
async def chat(data: dict):
    try:
        # Injetamos o System Prompt no início da conversa
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        messages.extend(data.get("messages", []))
        
        response = ollama.chat(model=MODELO_TEXTO, messages=messages)
        return {"reply": response['message']['content']}
    except Exception as e:
        return {"reply": f"ERRO DE TEXTO: {str(e)}"}

@app.post("/vision")
async def vision(prompt: str = Form("Descreva esta imagem"), file: UploadFile = File(...)):
    try:
        img_bytes = await file.read()
        # O MiniCPM-V também obedece ao prompt de sistema
        response = ollama.chat(model=MODELO_VISAO, messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt, 'images': [img_bytes]}
        ])
        return {"reply": response['message']['content']}
    except Exception as e:
        return {"reply": f"ERRO DE IMAGEM: {str(e)}"}

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        content = await file.read()
        with open("temp_audio.ogg", "wb") as f:
            f.write(content)
            
        # fp16=True só funciona em GPU (RTX). Se for CPU, usamos False.
        use_fp16 = True if device == "cuda" else False
        result = model_whisper.transcribe("temp_audio.ogg", fp16=use_fp16)
        
        # Aqui a IA processa o texto do áudio seguindo a regra do idioma
        ai_res = ollama.chat(model=MODELO_TEXTO, messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f"O usuário enviou um áudio com este conteúdo: {result['text']}. Responda adequadamente."}
        ])
        return {"reply": ai_res['message']['content']}
    except Exception as e:
        return {"reply": f"ERRO DE ÁUDIO: {str(e)}"}

@app.post("/pdf")
async def read_pdf(file: UploadFile = File(...)):
    try:
        content = await file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted: text += extracted
        
        # Aumentado o texto para não estourar o contexto do Llama 3.1
        ai_res = ollama.chat(model=MODELO_TEXTO, messages=[
            {'role': 'system', 'content': f"{SYSTEM_PROMPT} Resuma o PDF enviado pelo usuário."},
            {'role': 'user', 'content': text[:8000]} 
        ])
        return {"reply": ai_res['message']['content']}
    except Exception as e:
        return {"reply": f"ERRO DE PDF: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
