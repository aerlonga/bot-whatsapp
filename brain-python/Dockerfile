FROM python:3.10-slim

# FFmpeg é necessário para o Whisper processar áudio
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# PyTorch com suporte a CUDA 12.1 (para placas nvidia)
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
