# bot-bot

Um bot de bot multimodal com arquitetura de **microserviços** usando Docker Compose, filas Redis (BullMQ) e IA local (Ollama + Whisper). Processa **texto, áudio, imagens e PDFs** com suporte automático a GPU.

## 📐 Arquitetura

```
┌─────────────────┐    ┌──────────┐    ┌──────────────────┐    ┌──────────────┐
│  bot Web   │───▶│  Bridge  │───▶│   Redis (Fila)   │───▶│    Brain     │
│  (Usuário)      │◀───│  Node.js │◀───│   BullMQ Queue   │◀───│   Python     │
└─────────────────┘    └──────────┘    └──────────────────┘    └──────┬───────┘
                                                                      │
                                                               ┌──────▼───────┐
                                                               │   Ollama     │
                                                               │  (Host GPU)  │
                                                               └──────────────┘
```

- **Bridge Node**: Recebe mensagens do bot e coloca na fila (Producer). Um Worker consome a fila e envia respostas.
- **Redis**: Fila persistente. Se desligar o PC, as mensagens que estavam na fila serão processadas quando ligar de novo.
- **Brain Python**: API FastAPI que processa texto (Ollama), imagens (MiniCPM-V/Moondream), áudio (Whisper) e PDFs.
- **Ollama**: Roda no host (Ubuntu), fora do Docker, para máxima performance.

---

## 🛠️ Pré-requisitos

### 1. Docker e Docker Compose
```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Reinicie o terminal após esse comando

# Docker Compose já vem incluído no Docker moderno (docker compose)
```

### 2. Ollama (roda no host, fora do Docker)
```bash
sudo apt update && sudo apt install -y curl zstd
curl -fsSL https://ollama.com/install.sh | sh
```

### 3. NVIDIA Container Toolkit (apenas se tiver GPU)
> **⚠️ Sem isso, o Docker NÃO consegue acessar sua RTX/GTX.**

Verifique se já está instalado:
```bash
nvidia-container-cli --version
```

Se não estiver, instale:
```bash
# Configura o repositório
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Instala
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configura o Docker para usar o runtime NVIDIA
sudo nvidia-ctk runtime configure --runtime=docker

# Reinicia o Docker para aplicar as mudanças (crucial para o erro "could not select device driver")
sudo systemctl restart docker
# OU, se estiver usando WSL e o de cima falhar:
# sudo service docker restart
```

---

## 🧠 Passo 1: Baixar os Modelos de IA (Ollama)

O Ollama roda **no seu Ubuntu** (não dentro do Docker). Baixe os modelos antes de subir os containers:

```bash
# ===== MODELOS DE TEXTO (escolha um) =====

# OPÇÃO 1 — RTX 4060 / 8GB VRAM (Recomendado):
ollama pull llama3.1:8b

# OPÇÃO 2 — GPU 12GB+ VRAM (Mais pesado, mais inteligente):
ollama pull gpt-oss:20b

# OPÇÃO 3 — PC Fraco / Sem GPU:
ollama pull llama3.2:3b

# ===== MODELOS DE VISÃO (escolha um) =====

# OPÇÃO 1 — RTX 4060 (Lê textos em imagens, gráficos):
ollama pull minicpm-v

# OPÇÃO 2 — PC Fraco (Rápido, descrições básicas):
ollama pull moondream
```

---

## ⚙️ Passo 2: Configurar o Perfil de Hardware

Edite o arquivo `.env` na raiz do projeto:

```env
# Opções: LOW (sem GPU), MED (RTX 4060), HIGH (GPU 12GB+)
AI_PROFILE=MED
```

| Perfil | Texto | Visão | Whisper | Requisitos |
|--------|-------|-------|---------|------------|
| `LOW` | llama3.2:3b | moondream | base | Apenas CPU |
| `LOW2` | llama3.2:3b | minicpm-v | medium | Apenas CPU OU RTX 4060 (8GB VRAM)|
| `MED` | llama3.1:8b | minicpm-v | medium | RTX 4060 (8GB VRAM) |
| `HIGH` | gpt-oss:20b | minicpm-v | medium | GPU 12GB+ VRAM |

> **💡 Fallback automático:** Se a GPU não for detectada, o sistema força o perfil `LOW` automaticamente, independente do que estiver no `.env`.

---

## 🚀 Passo 3: Rodar!

### Configurar o Ollama para aceitar conexões do Docker
O Docker roda em uma rede interna. Para o container Python alcançar o Ollama no host:

```bash
# Opção 1: Modo manual com alta performance (Mantém modelo na VRAM por 24h)
OLLAMA_KEEP_ALIVE=24h OLLAMA_HOST=0.0.0.0 ollama serve

# Opção 2: Reiniciar o serviço (se instalado via instalador padrão)
sudo systemctl restart ollama

# Para parar o serviço totalmente
sudo systemctl stop ollama
```

### Subir os containers
```bash
# Na raiz do projeto:
docker-compose up --build
```

Isso vai:
1. Baixar e iniciar o **Redis**
2. Construir e iniciar o **Brain Python** (com GPU)
3. Construir e iniciar o **Bridge Node** (com Chromium)

### Escaneie o QR Code
Quando o Bridge Node estiver pronto, um QR Code aparecerá no terminal. Escaneie com bot > Aparelhos Conectados > Conectar um Aparelho.

---

## 🖥️ Rodando SEM GPU

Se a máquina não tiver placa NVIDIA:

1. Mude `AI_PROFILE=LOW` no `.env`
2. **Remova** o bloco `deploy.resources` do `docker-compose.yml`:
   ```yaml
   # Comente ou remova estas linhas do serviço brain-python:
   # deploy:
   #   resources:
   #     reservations:
   #       devices:
   #         - driver: nvidia
   #           count: 1
   #           capabilities: [gpu]
   ```
3. Rode normalmente: `docker-compose up --build`

> O bot vai funcionar, mas o Whisper usará CPU (~15-20s por áudio em vez de ~1-2s com GPU).

---

## ⚠️ Erros Comuns

### 1. Erro de permissão (Permission Denied) no Build
Se o Docker reclamar de permissão na pasta `.wwebjs_auth` ao buildar o `bridge-node`, rode:

```bash
sudo chown -R $USER:$USER ./bridge-node/.wwebjs_auth
```
Isso devolve a posse da pasta da sessão do bot (que o Docker criou como root) para o seu usuário.

---

## 📊 Monitoramento

### Ver logs dos containers
```bash
# Todos os serviços
docker-compose logs -f

# Apenas um serviço
docker-compose logs -f brain-python
docker-compose logs -f bridge-node
```

### Health check do Brain
```bash
curl http://localhost:8000/health
```

### Monitorar filas no Redis
```bash
docker exec -it bot-redis redis-cli
# Dentro do CLI:
LLEN bull:bot-ai:wait    # Mensagens aguardando
LLEN bull:bot-ai:active  # Mensagem sendo processada
```

---

## 🎉 Pronto!

Mande uma mensagem de **texto**, **áudio**, **imagem** ou **PDF** para o número conectado. O bot enfileira, processa com IA e responde automaticamente!