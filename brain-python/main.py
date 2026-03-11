from fastapi import FastAPI, UploadFile, File, Form
import ollama
import whisper
import os
import PyPDF2
import io
import traceback

app = FastAPI()

# Carrega o Whisper (usaremos o modelo 'base' para o seu i7-10700 não sofrer)
model_whisper = whisper.load_model("base")

@app.post("/chat")
async def chat(data: dict):
    try:
        response = ollama.chat(model='llama3.2:3b', messages=data.get("messages", []))
        return {"reply": response['message']['content']}
    except Exception as e:
        return {"reply": f"⚠️ ERRO DE TEXTO PYTHON: {str(e)}"}

@app.post("/vision")
async def vision(prompt: str = Form("Descreva esta imagem"), file: UploadFile = File(...)):
    try:
        img_bytes = await file.read()
        response = ollama.chat(model='moondream', messages=[{
        # response = ollama.chat(model='llama3.2-vision', messages=[{
            'role': 'user', 'content': prompt, 'images': [img_bytes]
        }])
        return {"reply": response['message']['content']}
    except Exception as e:
        return {"reply": f"🤖 ERRO DE IMAGEM NO PYTHON:\n{str(e)}"}

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        content = await file.read()
        with open("temp_audio.ogg", "wb") as f:
            f.write(content)
            
        # fp16=False adicionado para o warning no CPU sumir
        result = model_whisper.transcribe("temp_audio.ogg", fp16=False)
        
        # Após transcrever, pedimos para o Llama 3b dar uma resposta inteligente
        ai_res = ollama.chat(model='llama3.2:3b', messages=[
            {'role': 'system', 'content': 'O usuário enviou um áudio que diz o seguinte:'},
            {'role': 'user', 'content': result["text"]}
        ])
        return {"reply": ai_res['message']['content']}
    except Exception as e:
        import traceback
        erro = traceback.format_exc()
        print(erro) # Imprime no terminal local do Python para vermos melhor
        return {"reply": f"🎧 ERRO DE ÁUDIO NO PYTHON:\n{str(e)}"}

@app.post("/pdf")
async def read_pdf(file: UploadFile = File(...)):
    try:
        content = await file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        ai_res = ollama.chat(model='llama3.2:3b', messages=[
            {'role': 'system', 'content': 'Você acabou de ler este PDF. Resuma-o brevemente:'},
            {'role': 'user', 'content': text[:4000]} 
        ])
        return {"reply": ai_res['message']['content']}
    except Exception as e:
        return {"reply": f"📄 ERRO DE PDF NO PYTHON:\n{str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
