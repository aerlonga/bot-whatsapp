# bot-whatsapp

Um bot de WhatsApp multimodal usando `whatsapp-web.js` no frontend (Node.js) e uma API poderosa no backend (Python com FastAPI) que utiliza **Ollama (Llama 3 e Moondream)** e **Whisper** para processar texto, áudio, imagens e PDFs.

## 🛠️ Pré-requisitos do Sistema

Antes de começar, garanta que você tem as ferramentas abaixo instaladas no seu computador. Seguem os comandos para instalação do zero (focados em Ubuntu/Debian ou WSL):

### 1. Node.js e npm
```bash
# Instalando Node.js v20 (LTS) - Essencial para o whatsapp-web.js funcionar
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```
> Alternativa recomendada via [NVM](https://github.com/nvm-sh/nvm): 
> `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash`

### 2. Python (v3.9 ou superior) e venv
```bash
# Instalando Python 3, pip e suporte a ambientes virtuais (venv)
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

### 3. Ollama
Ollama é utilizado para rodar os modelos de IA (Llama 3 e Moondream) localmente na sua máquina.
```bash
# O instalador do Ollama precisa de algumas ferramentas base. Instale o zstd (extrator) e o curl:
sudo apt update && sudo apt install -y curl zstd

# Script de instalação oficial do Ollama para Linux:
curl -fsSL https://ollama.com/install.sh | sh
```

### 4. FFmpeg
Dependência de sistema necessária para a IA (Whisper) recuperar e processar os arquivos de áudio.
```bash
sudo apt update
sudo apt install -y ffmpeg
```

## 🧠 Passo 1: Configurando a IA Local (Ollama)

O bot utiliza IA rodando totalmente na sua própria máquina. Abra o terminal e baixe os modelos necessários antes de rodar os servidores:

```bash
# Para conversar e fazer resumos - ESCOLHA APENAS UMA OPÇÃO ABAIXO:

# OPÇÃO 1 (Recomendada para placas de vídeo com 8GB de VRAM como a RTX 4060):
# -> llama3.1:8b (aprox 4.7GB): Excelente raciocínio e velocidade. Cabe inteiro na VRAM da placa de vídeo sem engasgar e sem precisar puxar a RAM do PC.
ollama pull llama3.1:8b

# OPÇÃO 2 (Para testar o poder máximo / Raciocínio de ChatGPT):
# -> gpt-oss:20b (aprox 12GB+): Modelo da OpenAI. Exige VRAM e RAM juntas, vai responder mais devagar mas com qualidade insana.
ollama pull gpt-oss:20b

# OPÇÃO 3 (Para PCs mais fracos / sem placa de vídeo dedicada):
# -> llama3.2:3b (aprox 2.0GB): Modelo da Meta leve, focado em responder rápido usando muito pouca RAM/VRAM.
ollama pull llama3.2:3b

# Para ler imagens - ESCOLHA APENAS UMA OPÇÃO ABAIXO:

# OPÇÃO 1 (Recomendada para 8GB de VRAM / RTX 4060):
# -> minicpm-v (aprox 5.5GB): Um modelo de visão de 8 bilhões de parâmetros. Consegue ler textos em placas, gráficos complexos e detalhes que o Moondream não vê.
ollama pull minicpm-v

# OPÇÃO 2 (Para PCs mais fracos / Foco em velocidade máxima):
# -> moondream (aprox 1.8B): Um modelo minúsculo e focado apenas em enxergar imagens básicas. É rápido demais e mal consome memória.
ollama pull moondream
```

---

## 🐍 Passo 2: Configurando o Backend (Python - "Cérebro")

O backend é responsável por receber os arquivos e textos e processá-los com IA.

1. Abra um terminal e navegue até a pasta Python:
   ```bash
   cd brain-python
   ```

2. Crie um ambiente virtual (recomendado) e ative-o:
   ```bash
   python -m venv venv
   # No Linux/Mac:
   source venv/bin/activate
   # No Windows:
   venv\Scripts\activate
   ```

3. Instale as dependências:
   > **⚠️ ATENÇÃO - PARA QUEM TEM PLACA DE VÍDEO NVIDIA (RTX/GTX):**
   > Para o Whisper rodar em 1 segundo usando Placa de Vídeo, você precisa baixar a versão do PyTorch com suporte a CUDA antes das outras bibliotecas.
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```

   Após isso, instale o restante do backend:
   ```bash
   pip install fastapi "uvicorn[standard]" ollama openai-whisper pypdf2 python-multipart
   ```

4. Inicie o servidor da API:
   ```bash
   python main.py
   ```
   > O servidor ficará rodando na porta `8000`. Deixe este terminal aberto!

---

## 🚀 Passo 3: Configurando o Frontend (Node.js - "Ponte")

O frontend gerencia a conexão com o WhatsApp e repassa as mensagens para o backend.

1. Abra **outro** terminal e navegue até a pasta Node:
   ```bash
   cd bridge-node
   ```

2. Instale as dependências do projeto:
   ```bash
   npm install
   ```

3. Inicie o bot:
   ```bash
   node index.js
   ```

4. **Ler o QR Code:** Quando você rodar o comando acima, um QR Code enorme será gerado no terminal. Abra o WhatsApp no seu celular, vá em "Aparelhos Conectados" > "Conectar um Aparelho" e escaneie o código.

---

## 🎉 Tudo Pronto!

Se o bot se conectou com sucesso, você verá no terminal a mensagem dizendo que o cliente está pronto.
Agora basta mandar uma mensagem de texto, de áudio, imagem ou PDF para o número conectado e ele irá responder processando pela máquina!