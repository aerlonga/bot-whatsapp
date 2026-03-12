from fastapi import FastAPI, UploadFile, File, Form
import ollama
import whisper
import os
import PyPDF2
import io
import torch

app = FastAPI()

# ============================================
# DETECÇÃO DE PERFIL DE HARDWARE
# ============================================
# Lido da variável de ambiente AI_PROFILE (definida no .env / docker-compose)
PROFILE = os.getenv("AI_PROFILE", "MED").upper()

# Verifica se a GPU está disponível
HAS_GPU = torch.cuda.is_available()
device = "cuda" if HAS_GPU else "cpu"

# FALLBACK INTELIGENTE: Se não tem GPU, força perfil LOW
# para evitar que a máquina trave tentando rodar modelos pesados na CPU
if not HAS_GPU and PROFILE != "LOW":
    print(f"GPU não detectada! Perfil '{PROFILE}' ignorado → forçando perfil LOW.")
    PROFILE = "LOW"

# Seleção de modelos baseada no perfil
if PROFILE == "LOW":
    MODELO_TEXTO = "llama3.2:3b"
    MODELO_VISAO = "moondream"
    WHISPER_MODEL = "base"
elif PROFILE == "LOW2":
    MODELO_TEXTO = "llama3.2:3b"
    MODELO_VISAO = "minicpm-v"
    WHISPER_MODEL = "medium"
elif PROFILE == "HIGH":
    MODELO_TEXTO = "gpt-oss:20b"
    MODELO_VISAO = "minicpm-v"
    WHISPER_MODEL = "medium"
else:
    MODELO_TEXTO = "llama3.1:8b"
    MODELO_VISAO = "minicpm-v"
    WHISPER_MODEL = "medium"

print(f"Perfil: {PROFILE} | Device: {device.upper()}")
print(f"Texto: {MODELO_TEXTO} | Visão: {MODELO_VISAO} | Whisper: {WHISPER_MODEL}")

# ============================================
# CONFIGURAÇÃO DO OLLAMA (dentro do Docker)
# ============================================
# Quando roda no Docker, o Ollama está no host (Ubuntu), não no container.
# A variável OLLAMA_HOST é setada no docker-compose.yml via extra_hosts.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", None)
if OLLAMA_HOST:
    # Configura o cliente Ollama para apontar para o host
    ollama_client = ollama.Client(host=OLLAMA_HOST)
    print(f"Ollama conectado via: {OLLAMA_HOST}")
else:
    # Rodando localmente (sem Docker), usa localhost padrão
    ollama_client = ollama.Client()
    print("Ollama conectado via: localhost (padrão)")

# Carregamento do Whisper otimizado para o perfil
model_whisper = whisper.load_model(WHISPER_MODEL, device=device)
print(f"Whisper '{WHISPER_MODEL}' carregado no {device.upper()}!")

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
async def chat(data: dict):
    try:
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        messages.extend(data.get("messages", []))
        
        response = ollama_client.chat(model=MODELO_TEXTO, messages=messages)
        return {"reply": response['message']['content']}
    except Exception as e:
        return {"reply": f"ERRO DE TEXTO: {str(e)}"}

@app.post("/vision")
async def vision(prompt: str = Form("Descreva esta imagem"), file: UploadFile = File(...)):
    try:
        img_bytes = await file.read()
        response = ollama_client.chat(model=MODELO_VISAO, messages=[
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
        temp_path = "/tmp/temp_audio.ogg"
        with open(temp_path, "wb") as f:
            f.write(content)
            
        # fp16 só funciona com GPU (CUDA). Na CPU usamos fp32.
        use_fp16 = device == "cuda"
        result = model_whisper.transcribe(temp_path, fp16=use_fp16)
        
        # Remove o arquivo temporário
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # IA processa o texto transcrito seguindo a regra do idioma
        ai_res = ollama_client.chat(model=MODELO_TEXTO, messages=[
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
            if extracted:
                text += extracted
        
        ai_res = ollama_client.chat(model=MODELO_TEXTO, messages=[
            {'role': 'system', 'content': f"{SYSTEM_PROMPT} Resuma o PDF enviado pelo usuário."},
            {'role': 'user', 'content': text[:8000]}
        ])
        return {"reply": ai_res['message']['content']}
    except Exception as e:
        return {"reply": f"ERRO DE PDF: {str(e)}"}

# ============================================
# HEALTH CHECK
# ============================================
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "profile": PROFILE,
        "device": device,
        "modelo_texto": MODELO_TEXTO,
        "modelo_visao": MODELO_VISAO,
        "whisper_model": WHISPER_MODEL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
