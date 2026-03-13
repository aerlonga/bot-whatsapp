const { Telegraf } = require('telegraf');
const { message } = require('telegraf/filters');
const axios = require('axios');
const FormData = require('form-data');
const { Queue, Worker } = require('bullmq');
const IORedis = require('ioredis');

const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;
if (!TELEGRAM_TOKEN) {
    console.error('FATAL: Variável TELEGRAM_TOKEN não definida!');
    process.exit(1);
}

// const PYTHON_API = process.env.PYTHON_API_URL || 'http://localhost:8000';
const PYTHON_API = process.env.PYTHON_API_URL || 'http://172.19.0.1:11434';
const API_TIMEOUT = 300000;

const REDIS_HOST = process.env.REDIS_HOST || 'localhost';
const REDIS_PORT = parseInt(process.env.REDIS_PORT || '6379', 10);

const connection = new IORedis({
    host: REDIS_HOST,
    port: REDIS_PORT,
    maxRetriesPerRequest: null
});

const chatQueue = new Queue('bot-ai', { connection });

const introducedUsers = new Set();
const ERROR_MSG = '*Ops!* Tive um probleminha para processar isso agora. Pode tentar mandar de novo em alguns segundos?';

const bot = new Telegraf(TELEGRAM_TOKEN);

async function downloadTelegramFile(fileId) {
    const fileLink = await bot.telegram.getFileLink(fileId);
    const response = await axios.get(fileLink.href, { responseType: 'arraybuffer' });
    return Buffer.from(response.data);
}

bot.on(message('text'), async (ctx) => {
    const msg = ctx.message;
    if (msg.chat.type !== 'private') return;

    try {
        const chatId = String(msg.chat.id);
        const pushname = msg.from.first_name || msg.from.username || 'Usuário';

        const jobData = {
            messageId: String(msg.message_id),
            chatId,
            body: msg.text,
            type: 'text',
            hasMedia: false,
            pushname,
            mediaData: null,
            mimetype: null
        };

        await chatQueue.add('process', jobData, {
            removeOnComplete: 100,
            removeOnFail: 50
        });

        console.log(`[TEXTO] Mensagem de ${pushname} (${chatId}) na fila.`);
    } catch (err) {
        console.error('Erro ao enfileirar texto:', err.message);
    }
});

bot.on(message('photo'), async (ctx) => {
    const msg = ctx.message;
    if (msg.chat.type !== 'private') return;

    try {
        const chatId = String(msg.chat.id);
        const pushname = msg.from.first_name || msg.from.username || 'Usuário';

        const photo = msg.photo[msg.photo.length - 1];
        const buffer = await downloadTelegramFile(photo.file_id);
        const mediaData = buffer.toString('base64');

        const jobData = {
            messageId: String(msg.message_id),
            chatId,
            body: msg.caption || 'Descreva esta imagem em detalhes',
            type: 'image',
            hasMedia: true,
            pushname,
            mediaData,
            mimetype: 'image/jpeg'
        };

        await chatQueue.add('process', jobData, {
            removeOnComplete: 100,
            removeOnFail: 50
        });

        console.log(`[FOTO] Imagem de ${pushname} (${chatId}) na fila.`);
    } catch (err) {
        console.error('Erro ao enfileirar foto:', err.message);
    }
});

bot.on([message('voice'), message('audio')], async (ctx) => {
    const msg = ctx.message;
    if (msg.chat.type !== 'private') return;

    try {
        const chatId = String(msg.chat.id);
        const pushname = msg.from.first_name || msg.from.username || 'Usuário';

        const audioObj = msg.voice || msg.audio;
        const buffer = await downloadTelegramFile(audioObj.file_id);
        const mediaData = buffer.toString('base64');
        const mimetype = audioObj.mime_type || 'audio/ogg';

        const jobData = {
            messageId: String(msg.message_id),
            chatId,
            body: null,
            type: 'audio',
            hasMedia: true,
            pushname,
            mediaData,
            mimetype
        };

        await chatQueue.add('process', jobData, {
            removeOnComplete: 100,
            removeOnFail: 50
        });

        console.log(`[ÁUDIO] Áudio de ${pushname} (${chatId}) na fila.`);
    } catch (err) {
        console.error('Erro ao enfileirar áudio:', err.message);
    }
});

bot.on(message('document'), async (ctx) => {
    const msg = ctx.message;
    if (msg.chat.type !== 'private') return;

    const doc = msg.document;

    if (doc.mime_type !== 'application/pdf') {
        await ctx.reply('Apenas documentos PDF são suportados no momento.');
        return;
    }

    try {
        const chatId = String(msg.chat.id);
        const pushname = msg.from.first_name || msg.from.username || 'Usuário';

        const buffer = await downloadTelegramFile(doc.file_id);
        const mediaData = buffer.toString('base64');

        const jobData = {
            messageId: String(msg.message_id),
            chatId,
            body: msg.caption || null,
            type: 'document',
            hasMedia: true,
            pushname,
            mediaData,
            mimetype: 'application/pdf'
        };

        await chatQueue.add('process', jobData, {
            removeOnComplete: 100,
            removeOnFail: 50
        });

        console.log(`[PDF] Documento de ${pushname} (${chatId}) na fila.`);
    } catch (err) {
        console.error('Erro ao enfileirar documento:', err.message);
    }
});

const worker = new Worker('bot-ai', async (job) => {
    const { messageId, chatId, body, type, hasMedia, mediaData, mimetype, pushname } = job.data;

    console.log(`Processando job ${job.id} de ${pushname} (${chatId})...`);

    const telegramChatId = parseInt(chatId, 10);

    try {
        const api = axios.create({ baseURL: PYTHON_API, timeout: API_TIMEOUT });
        let aiReply = '';

        const action = type === 'audio' ? 'record_voice' : (type === 'image' ? 'upload_photo' : 'typing');
        await bot.telegram.sendChatAction(telegramChatId, action);
        const typingInterval = setInterval(() => {
            bot.telegram.sendChatAction(telegramChatId, action).catch(() => { });
        }, 5000);

        try {
            if (hasMedia && mediaData) {
                const buffer = Buffer.from(mediaData, 'base64');
                const form = new FormData();

                if (type === 'image') {
                    form.append('file', buffer, { filename: 'image.jpg', contentType: 'image/jpeg' });
                    form.append('prompt', body || 'Descreva esta imagem em detalhes');
                    const res = await api.post('/vision', form, { headers: form.getHeaders() });
                    aiReply = res.data.reply;
                } else if (type === 'audio') {
                    form.append('file', buffer, { filename: 'audio.ogg', contentType: mimetype || 'audio/ogg' });
                    const res = await api.post('/transcribe', form, { headers: form.getHeaders() });
                    aiReply = res.data.reply;
                } else if (mimetype === 'application/pdf') {
                    form.append('file', buffer, { filename: 'doc.pdf', contentType: 'application/pdf' });
                    const res = await api.post('/pdf', form, { headers: form.getHeaders() });
                    aiReply = res.data.reply;
                }
            } else {
                const res = await api.post('/chat', {
                    messages: [{ role: 'user', content: body }],
                    user_id: chatId,
                    pushname: pushname
                });
                aiReply = res.data.reply;
            }
        } finally {
            clearInterval(typingInterval);
        }

        if (body && body.trim().toLowerCase() === '!help') {
            aiReply = `*Lista de Comandos:* ✨\n\n` +
                `📌 *@gasto*
                    Informe o [local], [valor],  [categoria] e [data] do gasto\n` +
                `_Ex: @gasto Mercado 50 Alimentação no dia 01/01/2024_\n\n` +
                `📊 *@orçamento* [categoria]\n` +
                `_Ex: @orçamento Lazer ou apenas @orçamento_\n\n` +
                `💡 *Dica:* Utilize os comandos no início da mensagem!`;
        }

        if (!aiReply) throw new Error('Sem resposta da IA (Backend retornou vazio)');

        let finalMessage = aiReply;
        if (!introducedUsers.has(chatId)) {
            // finalMessage = `*Olá, ${pushname}!* 👋\n\nSou o assistente inteligente do Aerlon. Enquanto ele não responde, posso te ajudar com algo? (Digite *!help* para ver meus comandos)\n\n${aiReply}`;
            finalMessage = `*Olá, ${pushname}!* 👋\n\nSou a assistente inteligente do Aerlon. Enquanto ele não responde, posso te ajudar com algo? (Digite *!help* para ver meus comandos)`;
            introducedUsers.add(chatId);
        }

        const sendSafe = async (chatId, text) => {
            try {
                await bot.telegram.sendMessage(chatId, text, { parse_mode: 'Markdown' });
            } catch (err) {
                if (err.description && err.description.includes('can\'t parse entities')) {
                    console.warn('Falha no parser Markdown, enviando como texto simples...');
                    await bot.telegram.sendMessage(chatId, text);
                } else {
                    throw err;
                }
            }
        };

        const MAX_LENGTH = 4000;
        if (finalMessage.length > MAX_LENGTH) {
            const lines = finalMessage.split('\n');
            let currentChunk = '';

            for (const line of lines) {
                if ((currentChunk + line).length > MAX_LENGTH) {
                    await sendSafe(telegramChatId, currentChunk);
                    currentChunk = line + '\n';
                } else {
                    currentChunk += line + '\n';
                }
            }
            if (currentChunk) await sendSafe(telegramChatId, currentChunk);
        } else {
            await sendSafe(telegramChatId, finalMessage);
        }

        console.log(`Resposta enviada para ${pushname}.`);

    } catch (err) {
        console.error(`Erro no job ${job.id}:`, err.message);
        try {
            await bot.telegram.sendMessage(telegramChatId, ERROR_MSG, { parse_mode: 'Markdown' });
        } catch (sendErr) {
            console.error('Falha ao enviar mensagem de erro:', sendErr.message);
        }
    }
}, {
    connection,
    concurrency: 1
});

worker.on('completed', (job) => {
    console.log(`Job ${job.id} concluído.`);
});

worker.on('failed', (job, err) => {
    console.error(`Job ${job?.id} falhou:`, err.message);
});


bot.launch().then(() => {
    console.log('Ponte Telegram com filas BullMQ ativa!');
    console.log(`API Python: ${PYTHON_API}`);
    console.log(`Redis: ${REDIS_HOST}:${REDIS_PORT}`);
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));