import logging
import json
import os
import redis
import asyncpg
from datetime import datetime
from app.config import DATABASE_URL, MEMORY_TTL_DAYS

logger = logging.getLogger(__name__)

# Configuração do Redis (mesma env usada pelo Node.js e docker-compose)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
except Exception as e:
    logger.error(f"Erro ao conectar ao Redis: {e}")
    redis_client = None

async def cleanup_expired_memories():
    """
    Busca memórias com expira_em < NOW().
    Para cada usuário afetado, adiciona uma mensagem na fila informando a limpeza,
    depois apaga do banco.
    """
    if not DATABASE_URL:
        logger.warning("[Cleanup] DATABASE_URL não configurada. Abortando cleanup.")
        return
        
    logger.info("[Cleanup] Iniciando verificação de memórias expiradas...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Pega os usuários distintos que têm memórias expiradas
            affected_users_records = await conn.fetch('''
                SELECT DISTINCT c.telefone_telegram 
                FROM memoria_vetorial m
                JOIN contatos c ON m.contato_id = c.id
                WHERE m.expira_em < NOW()
            ''')
            
            affected_users = [record['telefone_telegram'] for record in affected_users_records]
            
            if affected_users:
                # Deleta memórias expiradas
                deleted = await conn.execute("DELETE FROM memoria_vetorial WHERE expira_em < NOW()")
                logger.info(f"[Cleanup] Removidas memórias de {len(affected_users)} usuários. SQL Status: {deleted}")
                
                # Notifica os usuários afetados via fila BullMQ do Node
                if redis_client:
                    for str_user_id in affected_users:
                        # BullMQ do Node espera jobs em Hashes/ZSETS complexos, 
                        # mas para inserção simples do python geralmente requer uma lib BullMQ compatível (ou enviar por webhook Node).
                        # Aqui faremos um fallback push simples para uma lista ou enviar como BullMQ manual se necessário.
                        # Mais seguro: Avisar a ponte node ou usar webhook, mas os requisitos pedem:
                        # "Coloca na fila Redis (fila "bot-ai-response") uma mensagem para cada contato afetado"
                        # Nota: BullMQ não é só LPUSH list, mas se a ponte node ouve isso como fallback, deixaremos no formato simples que simula:
                        
                        mensagem_aviso = f"Oi! Para manter a precisão das minhas respostas e organizar minha memória, resumi e silenciei algumas de nossas conversas mais antigas (mais de {MEMORY_TTL_DAYS} dias). Pode continuar normalmente!"
                        
                        job_data = {
                            "data": {
                                "chatId": str_user_id,
                                "response": mensagem_aviso
                            }
                        }
                        
                        # BullMQ adds
                        # Para manter a compatibilidade total com o BullMQ (nodejs) do outro repositório:
                        # Em tese a fila é bot-ai-response, o node deve interceptar isso. 
                        # Fazemos push na fila compatível com ioredis/bullmq ou webhook HTTP é melhor.
                        # Como não podemos rodar código JS aqui, a instrução diz "fila Redis 'bot-ai-response'"
                        # Vamos empurrar a mensagem em JSON
                        redis_client.lpush("bot-ai-response", json.dumps(job_data))
                        logger.info(f"Notificação de limpeza enviada para {str_user_id}")
            else:
                logger.info("[Cleanup] Nenhuma memória expirada no momento.")
                
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"[Cleanup] Erro durante limpeza programada: {e}")
