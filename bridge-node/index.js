const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const FormData = require('form-data');

// Set para guardar quem já recebeu a apresentação (limpa se o bot reiniciar)
const introducedUsers = new Set();
const ERROR_MSG = "Como sou um robo, posso errar, desculpe, não entendi. tente novamente. esperando com que o usuario envie novamente";

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { 
        args: ['--no-sandbox', '--disable-setuid-sandbox'] 
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));

client.on('ready', () => console.log('🚀 Ponte Multimodal Ativa!'));

client.on('message', async msg => {
    // 1. Bloqueia mensagens de GRUPOS
    if (msg.from.includes('@g.us')) return;

    try {
        const contact = await msg.getContact();

        // 2. Bloqueia mensagens de CONTAS COMERCIAIS
        if (contact.isBusiness) {
            console.log(`🚫 Ignorando conta comercial: ${contact.number}`);
            return;
        }

        const userId = msg.from;
        console.log(`📩 Mensagem de: ${contact.pushname || contact.number}`);

        let aiReply = "";

        // Lógica de Processamento de Mídia
        if (msg.hasMedia) {
            console.log(`[Mídia] Detectou mídia do tipo: ${msg.type}`);
            console.log(`[Mídia] Baixando a mídia do WhatsApp... (isso pode demorar se for muito grande)`);
            const media = await msg.downloadMedia();
            
            if (!media) {
                throw new Error("Falha ao baixar a mídia do WhatsApp (veio vazia).");
            }
            console.log(`[Mídia] Mídia baixada com sucesso! Tamanho aprox: ${(media.data.length / 1024 / 1024).toFixed(2)} MB`);
            
            const form = new FormData();
            
            // Converte o base64 do WhatsApp para Buffer para enviar ao Python
            console.log(`[Mídia] Convertendo base64 para Buffer...`);
            const buffer = Buffer.from(media.data, 'base64');

            if (msg.type === 'image') {
                console.log(`[Mídia-Imagem] Montando requisição para enviar para o Python /vision...`);
                form.append('file', buffer, { filename: 'image.jpg' });
                form.append('prompt', msg.body || "Descreva esta imagem");
                console.log(`[Mídia-Imagem] Enviando o POST para http://localhost:8000/vision`);
                const res = await axios.post('http://localhost:8000/vision', form);
                console.log(`[Mídia-Imagem] Resposta do Python recebida com sucesso!`);
                aiReply = res.data.reply;
            } 
            else if (msg.type === 'audio' || msg.type === 'ptt') {
                console.log(`[Mídia-Áudio] Montando requisição para enviar para o Python /transcribe...`);
                form.append('file', buffer, { filename: 'audio.ogg' });
                console.log(`[Mídia-Áudio] Enviando o POST para http://localhost:8000/transcribe...`);
                const res = await axios.post('http://localhost:8000/transcribe', form);
                console.log(`[Mídia-Áudio] Resposta do Python recebida com sucesso!`);
                aiReply = res.data.reply;
            }
            else if (media.mimetype === 'application/pdf') {
                console.log(`[Mídia-PDF] Montando requisição para enviar para o Python /pdf...`);
                form.append('file', buffer, { filename: 'doc.pdf' });
                console.log(`[Mídia-PDF] Enviando o POST para http://localhost:8000/pdf...`);
                const res = await axios.post('http://localhost:8000/pdf', form);
                console.log(`[Mídia-PDF] Resposta do Python recebida com sucesso!`);
                aiReply = res.data.reply;
            } else {
                console.log(`[Mídia-Desconhecida] Tipo de mídia não suportado: ${media.mimetype}`);
                throw new Error("Mídia não suportada.");
            }
        } 
        else {
            // Processamento de Texto Normal
            const res = await axios.post('http://localhost:8000/chat', {
                messages: [{ role: 'user', content: msg.body }]
            });
            aiReply = res.data.reply;
        }

        // Se o Python retornar erro ou estiver vazio
        if (!aiReply || aiReply === "fail") throw new Error("AI Fail");

        let finalMessage = "";

        // Lógica de Apresentação (Apenas na primeira mensagem)
        if (!introducedUsers.has(userId)) {
            finalMessage = "🤖\n" +
                           "E aí! Sou o assistente de IA. Só passando pra avisar que agora este chat é automatizado, beleza? Segue a resposta:\n\n" + 
                           aiReply;
            
            introducedUsers.add(userId); // Marca que o usuário já conhece o bot
        } else {
            finalMessage = aiReply;
        }

        // Responde o usuário
        await msg.reply(finalMessage);
        
    } catch (err) {
        console.error("❌ Erro na ponte ou no cérebro:", err.message);
        await msg.reply(ERROR_MSG);
    }
});

client.initialize();