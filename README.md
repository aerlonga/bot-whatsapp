# bot-whatsapp

Um bot de WhatsApp multimodal usando `whatsapp-web.js` no frontend (Node.js) e uma API poderosa no backend (Python com FastAPI) que utiliza **Ollama (Llama 3 e Moondream)** e **Whisper** para processar texto, áudio, imagens e PDFs.

## 🛠️ Pré-requisitos do Sistema

Antes de começar, garanta que você tem as seguintes ferramentas instaladas no seu computador:
- **Node.js** (v18 ou superior) e **npm**
- **Python** (v3.9 ou superior)
- **Ollama**: [Baixe e instale o Ollama](https://ollama.com/)
- **FFmpeg**: Necessário para o Whisper processar os áudios. (No Ubuntu: `sudo apt install ffmpeg`)

## 🧠 Passo 1: Configurando a IA Local (Ollama)

O bot utiliza IA rodando totalmente na sua própria máquina. Abra o terminal e baixe os modelos necessários antes de rodar os servidores:

```bash
# Para conversar e fazer resumos:
ollama pull llama3.2:3b

# Para ler imagens:
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