import os
import whisper
from app.config import WHISPER_MODEL, DEVICE

# Carregamento do Whisper otimizado para o perfil atual
print(f"[{DEVICE.upper()}] Carregando modelo Whisper '{WHISPER_MODEL}'...")
try:
    model_whisper = whisper.load_model(WHISPER_MODEL, device=DEVICE)
    print(f"Whisper '{WHISPER_MODEL}' carregado com sucesso no {DEVICE.upper()}!")
except Exception as e:
    print(f"Falha gravíssima ao carregar modelo Whisper: {e}")
    model_whisper = None

async def transcribe(audio_bytes: bytes) -> str:
    """
    Transcreve bytes de um áudio (ex: ogg) enviando para o modelo Whisper carregado na RAM/VRAM.
    """
    if not model_whisper:
        raise RuntimeError("O modelo Whisper não foi inicializado corretamente.")
        
    temp_path = "/tmp/temp_audio_transcribe.ogg"
    
    try:
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)
            
        use_fp16 = (DEVICE == "cuda")
        
        result = model_whisper.transcribe(temp_path, fp16=use_fp16)
        return result["text"]
    except Exception as e:
        raise RuntimeError(f"Erro na transcrição de áudio: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
