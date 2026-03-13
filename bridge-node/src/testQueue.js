const { botAiQueue } = require('./queue');

async function test() {
  console.log('--- Teste de Fila BullMQ ---');
  console.log('1. Enfileirando mensagem de teste...');

  const job = await botAiQueue.add('test-incoming-msg', {
    chat_id: '12345678',
    text: 'Olá IA, isso é um teste de fila.'
  });

  console.log(`2. Job adicionado com sucesso! ID: ${job.id}`);
  console.log('3. Verifique no Redis usando: redis-cli LLEN bulk:bot-ai:wait');
}

test().then(() => {
  setTimeout(() => process.exit(0), 1000);
}).catch(err => {
  console.error('Erro no teste:', err);
  process.exit(1);
});
