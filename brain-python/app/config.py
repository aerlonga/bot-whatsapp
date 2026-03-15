import os
import torch
from dotenv import load_dotenv

load_dotenv()

PROFILE = os.getenv("AI_PROFILE", "MED").upper()

# Verifica se a GPU está disponível
HAS_GPU = torch.cuda.is_available()
DEVICE = "cuda" if HAS_GPU else "cpu"

# FALLBACK INTELIGENTE: Se não tem GPU, força perfil LOW
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
elif PROFILE == "MED":
    MODELO_TEXTO = "llama3.1:8b"
    MODELO_VISAO = "minicpm-v"
    WHISPER_MODEL = "base"
elif PROFILE == "HIGH":
    MODELO_TEXTO = "gpt-oss:20b"
    MODELO_VISAO = "minicpm-v"
    WHISPER_MODEL = "medium"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")

DATABASE_URL = os.getenv("DATABASE_URL")
SPRING_API_URL = os.getenv("SPRING_API_URL", "http://spring-financeiro:8080")
SPRING_API_KEY = os.getenv("SPRING_API_KEY", "super-secret-key-123")

MEMORY_TTL_DAYS = int(os.getenv("MEMORY_TTL_DAYS", "30"))
