const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const FormData = require('form-data');

// Configuração da API Python
const PYTHON_API = "http://localhost:8000";
const API_TIMEOUT = 60000; // 60 segundos (segurança para áudios longos)

const introducedUsers = new Set();
const ERROR_MSG = "🤖 *Ops!* Tive um probleminha para processar isso agora. Pode tentar mandar de novo em alguns segundos?";

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { 
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
        headless: true 
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));
client.on('ready', () => console.log('🚀 Ponte Multimodal Ativa e Conectada!'));

client.on('message', async msg => {
    // Ignorar mensagens em grupos
    if (msg.from.includes('@g.us')) return;

    try {
        const contact = await msg.getContact();
        // Ignorar contas de WhatsApp Business (para evitar loop bot com bot)
        if (contact.isBusiness) return;

        const userId = msg.from;
        let aiReply = "";

        // Instância do Axios com timeout estendido para o processamento de IA
        const api = axios.create({ baseURL: PYTHON_API, timeout: API_TIMEOUT });

        if (msg.hasMedia) {
            console.log(`[Mídia] Processando ${msg.type} de ${contact.pushname}...`);
            const media = await msg.downloadMedia();
            if (!media) throw new Error("Mídia vazia");

            const buffer = Buffer.from(media.data, 'base64');
            const form = new FormData();

            if (msg.type === 'image') {
                form.append('file', buffer, { filename: 'image.jpg', contentType: 'image/jpeg' });
                form.append('prompt', msg.body || "Descreva esta imagem em detalhes");
                const res = await api.post('/vision', form, { headers: form.getHeaders() });
                aiReply = res.data.reply;
            } 
            else if (msg.type === 'audio' || msg.type === 'ptt') {
                // ptt = Push To Talk (Áudio gravado na hora)
                form.append('file', buffer, { filename: 'audio.ogg', contentType: 'audio/ogg' });
                const res = await api.post('/transcribe', form, { headers: form.getHeaders() });
                aiReply = res.data.reply;
            }
            else if (media.mimetype === 'application/pdf') {
                form.append('file', buffer, { filename: 'doc.pdf', contentType: 'application/pdf' });
                const res = await api.post('/pdf', form, { headers: form.getHeaders() });
                aiReply = res.data.reply;
            } else {
                // Ignorar outros tipos de arquivos/mídias não suportados
                return;
            }
        } 
        else {
            // Processamento de Texto Normal
            const res = await api.post('/chat', {
                messages: [{ role: 'user', content: msg.body }]
            });
            aiReply = res.data.reply;
        }

        if (!aiReply) throw new Error("Sem resposta da IA (Backend retornou vazio)");

        // Formatação da Mensagem Final com Introdução para novos usuários
        let finalMessage = aiReply;
        if (!introducedUsers.has(userId)) {
            finalMessage = `👋 *Olá, ${contact.pushname}!*\n\nSou o assistente inteligente do Aerlon. Vou processar sua mensagem agora:\n\n${aiReply}`;
            introducedUsers.add(userId);
        }

        await msg.reply(finalMessage);
        
    } catch (err) {
        console.error("❌ Erro:", err.message);
        await msg.reply(ERROR_MSG);
    }
});

client.initialize();