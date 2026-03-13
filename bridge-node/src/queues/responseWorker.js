const { Worker } = require('bullmq');
const axios = require('axios');
const { connection } = require('../queue');

const responseWorker = new Worker('bot-ai-response', async job => {
  const { chat_id, text } = job.data;
  const token = process.env.TELEGRAM_TOKEN;

  if (!token) {
    console.error('TELEGRAM_TOKEN não configurado no worker');
    return;
  }

  const url = `https://api.telegram.org/bot${token}/sendMessage`;

  try {
    await axios.post(url, {
      chat_id,
      text
    });
    console.log(`[Worker] Resposta enviada para ${chat_id}: ${text.substring(0, 50)}...`);
  } catch (error) {
    console.error(`[Worker] Erro ao enviar resposta para ${chat_id}:`, error.response?.data || error.message);
    throw error;
  }
}, { connection });

console.log('Worker de resposta BullMQ (bot-ai-response) iniciado');

module.exports = responseWorker;
