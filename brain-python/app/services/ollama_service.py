import time
import urllib.parse
import httpx
import ollama
from app.config import OLLAMA_HOST, MODELO_TEXTO, MODELO_VISAO

# Verifica se OLLAMA_HOST é uma URL completa ou apenas host:port
import urllib.parse
parsed_host = urllib.parse.urlparse(OLLAMA_HOST)
if not parsed_host.scheme:
    OLLAMA_HOST_URL = f"http://{OLLAMA_HOST}"
else:
    OLLAMA_HOST_URL = OLLAMA_HOST

ollama_client = ollama.Client(host=OLLAMA_HOST_URL)

async def check_connection():
    """
    Verifica a conexão com o Ollama fazendo request em /api/tags
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{OLLAMA_HOST_URL}/api/tags")
            response.raise_for_status()
            return True, "Conectado"
    except Exception as e:
        return False, str(e)

async def chat(messages, model=None, tools=None):
    """
    Chama o modelo de texto do Ollama. Suporta envio de tools (tool calling).
    """
    selected_model = model or MODELO_TEXTO
    start_time = time.time()
    
    try:
        if tools:
            response = ollama_client.chat(
                model=selected_model,
                messages=messages,
                tools=tools
            )
        else:
            response = ollama_client.chat(
                model=selected_model,
                messages=messages
            )
            
        elapsed_time = time.time() - start_time
        print(f"[Ollama Chat] Model: {selected_model} | Time: {elapsed_time:.2f}s")
        
        return response
    except Exception as e:
        print(f"[Ollama Erro] Falha ao comunicar com Ollama para texto: {e}")
        return {
            "message": {
                "role": "assistant",
                "content": "Desculpe, estou tendo dificuldades para processar sua mensagem no momento (Ollama Offline)."
            }
        }

async def vision(prompt: str, image_bytes: bytes):
    """
    Chama o modelo de visão do Ollama.
    """
    start_time = time.time()
    try:
        response = ollama_client.chat(
            model=MODELO_VISAO,
            messages=[
                {'role': 'user', 'content': prompt, 'images': [image_bytes]}
            ]
        )
        elapsed_time = time.time() - start_time
        print(f"[Ollama Vision] Model: {MODELO_VISAO} | Time: {elapsed_time:.2f}s")
        return response
    except Exception as e:
        print(f"[Ollama Erro] Falha ao comunicar com Ollama para visão: {e}")
        return {
            "message": {
                "role": "assistant",
                "content": "Desculpe, estou tendo dificuldades para processar essa imagem no momento (Ollama Offline)."
            }
        }
