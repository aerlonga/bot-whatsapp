const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const FormData = require('form-data');
const { Queue, Worker } = require('bullmq');
const IORedis = require('ioredis');

// ============================================
// CONFIGURAÇÃO
// ============================================
const PYTHON_API = process.env.PYTHON_API_URL || "http://localhost:8000";
const API_TIMEOUT = 120000; // 120s (margem para modelos pesados)

const REDIS_HOST = process.env.REDIS_HOST || "localhost";
const REDIS_PORT = parseInt(process.env.REDIS_PORT || "6379", 10);

const connection = new IORedis({
    host: REDIS_HOST,
    port: REDIS_PORT,
    maxRetriesPerRequest: null // Exigido pelo BullMQ
});

const chatQueue = new Queue('whatsapp-ai', { connection });

const introducedUsers = new Set();
const ERROR_MSG = "*Ops!* Tive um probleminha para processar isso agora. Pode tentar mandar de novo em alguns segundos?";

// ============================================
// CLIENTE WHATSAPP
// ============================================
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',    // Evita crash por memória no Docker
            '--disable-gpu',               // Chromium não precisa de GPU
            '--no-first-run',
            '--no-zygote',
            '--single-process'             // Mais estável dentro de containers
        ],
        headless: true
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));
client.on('ready', () => {
    console.log('Ponte Multimodal Ativa e Conectada!');
    console.log(`API Python: ${PYTHON_API}`);
    console.log(`Redis: ${REDIS_HOST}:${REDIS_PORT}`);
});

// ============================================
// PRODUCER: Recebe mensagem → Joga na fila
// ============================================
client.on('message', async msg => {
    // Ignorar mensagens em grupos, newsletters e transmissões
    if (msg.from.includes('@g.us') || msg.from.includes('@newsletter') || msg.from.includes('@broadcast')) return;

    try {
        const contact = await msg.getContact();
        // Ignorar contas de WhatsApp Business (evita loop bot-com-bot)
        if (contact.isBusiness) return;

        // Prepara os dados do job
        const jobData = {
            messageId: msg.id._serialized, // ID para permitir reações depois
            chatId: msg.from,
            body: msg.body,
            type: msg.type,
            hasMedia: msg.hasMedia,
            pushname: contact.pushname || "Usuário",
            mediaData: null,
            mimetype: null
        };

        // Se tem mídia, converte para base64 antes de por na fila
        // (Redis trabalha com strings, não com Buffers brutos)
        if (msg.hasMedia) {
            const media = await msg.downloadMedia();
            if (media) {
                jobData.mediaData = media.data; // Já vem em base64 do whatsapp-web.js
                jobData.mimetype = media.mimetype;
            }
        }

        // Adiciona na fila e libera o WhatsApp imediatamente
        await chatQueue.add('process', jobData, {
            removeOnComplete: 100, // Mantém últimos 100 jobs completos
            removeOnFail: 50       // Mantém últimos 50 jobs com erro
        });

        console.log(`Mensagem de ${contact.pushname || msg.from} na fila.`);

    } catch (err) {
        console.error("Erro ao enfileirar:", err.message);
    }
});

// ============================================
// WORKER: Consome a fila, um por vez (GPU focus)
// ============================================
const worker = new Worker('whatsapp-ai', async job => {
    const { messageId, chatId, body, type, hasMedia, mediaData, mimetype, pushname } = job.data;

    console.log(`Processando job ${job.id} de ${pushname}...`);

    try {
        const api = axios.create({ baseURL: PYTHON_API, timeout: API_TIMEOUT });
        let aiReply = "";

        // Busca a mensagem original e o chat
        const [msg, chat] = await Promise.all([
            client.getMessageById(messageId).catch(() => null),
            client.getChatById(chatId)
        ]);

        // Feedback visual instantâneo: Reações
        if (msg && msg.react) {
            try {
                if (type === 'image') await msg.react('🔍');
                else if (mimetype === 'application/pdf') await msg.react('📄');
                else if (type === 'audio' || type === 'ptt') await msg.react('🎧');
            } catch (reactErr) {
                console.warn("Não foi possível reagir à mensagem:", reactErr.message);
            }
        }

        // Status de "Digitando..." ou "Gravando..."
        if (type === 'audio' || type === 'ptt') {
            await chat.sendStateRecording();
        } else {
            await chat.sendStateTyping();
        }

        if (hasMedia && mediaData) {
            // Reconstrói o Buffer a partir do base64
            const buffer = Buffer.from(mediaData, 'base64');
            const form = new FormData();

            if (type === 'image') {
                form.append('file', buffer, { filename: 'image.jpg', contentType: 'image/jpeg' });
                form.append('prompt', body || "Descreva esta imagem em detalhes");
                const res = await api.post('/vision', form, { headers: form.getHeaders() });
                aiReply = res.data.reply;
            }
            else if (type === 'audio' || type === 'ptt') {
                // ptt = Push To Talk (áudio gravado na hora)
                form.append('file', buffer, { filename: 'audio.ogg', contentType: 'audio/ogg' });
                const res = await api.post('/transcribe', form, { headers: form.getHeaders() });
                aiReply = res.data.reply;
            }
            else if (mimetype === 'application/pdf') {
                form.append('file', buffer, { filename: 'doc.pdf', contentType: 'application/pdf' });
                const res = await api.post('/pdf', form, { headers: form.getHeaders() });
                aiReply = res.data.reply;
            }
            else {
                // Tipo de mídia não suportado — ignora silenciosamente
                console.log(`Mídia ${type} (${mimetype}) não suportada. Ignorando.`);
                return;
            }
        }
        else {
            // Processamento de Texto Normal
            const res = await api.post('/chat', {
                messages: [{ role: 'user', content: body }]
            });
            aiReply = res.data.reply;
        }

        if (!aiReply) throw new Error("Sem resposta da IA (Backend retornou vazio)");

        // Formatação da Mensagem Final com Introdução para novos usuários
        let finalMessage = aiReply;
        if (!introducedUsers.has(chatId)) {
            finalMessage = `*Olá, ${pushname}!*\n\nSou o assistente inteligente do Aerlon. Vou processar sua mensagem agora:\n\n${aiReply}`;
            introducedUsers.add(chatId);
        }

        await client.sendMessage(chatId, finalMessage);
        console.log(`Resposta enviada para ${pushname}.`);

    } catch (err) {
        console.error(`Erro no job ${job.id}:`, err.message);
        try {
            await client.sendMessage(chatId, ERROR_MSG);
        } catch (sendErr) {
            console.error("Falha ao enviar mensagem de erro:", sendErr.message);
        }
    }
}, {
    connection,
    concurrency: 1 // Uma tarefa por vez = GPU focada em 100% do poder
});

worker.on('completed', job => {
    console.log(`Job ${job.id} concluído.`);
});

worker.on('failed', (job, err) => {
    console.error(`Job ${job?.id} falhou:`, err.message);
});

console.log('Inicializando ponte WhatsApp com filas BullMQ...');
client.initialize();