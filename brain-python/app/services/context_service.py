import json
import logging
from datetime import datetime, timedelta
import asyncpg
import asyncpg.types
from sentence_transformers import SentenceTransformer

from app.config import DATABASE_URL, MEMORY_TTL_DAYS

logger = logging.getLogger(__name__)

print("[Memória] Carregando modelo sentence-transformers para embeddings...")
embedding_model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
print("[Memória] Modelo de embeddings carregado.")

async def _get_conn():
    """
    Retorna uma conexão asyncpg com suporte a pgvector.
    Certifique-se de fechar a conexão no final (usar async with conn)
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    except Exception as e:
        logger.warning(f"Erro ao tentar criar extensão vector: {e}")
    return conn

async def _get_or_create_contato(conn, telegram_user_id: str, nome: str = None) -> int:
    """Insere o contato na tabela 'contatos' se não existir e retorna o ID interno."""
    if nome:
        row = await conn.fetchrow(
            '''
            INSERT INTO contatos (telefone_telegram, nome) 
            VALUES ($1, $2) 
            ON CONFLICT (telefone_telegram) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            ''',
            str(telegram_user_id), nome
        )
    else:
        row = await conn.fetchrow(
            '''
            INSERT INTO contatos (telefone_telegram) 
            VALUES ($1) 
            ON CONFLICT (telefone_telegram) DO UPDATE SET telefone_telegram = EXCLUDED.telefone_telegram
            RETURNING id
            ''',
            str(telegram_user_id)
        )
    return row['id']


async def save_context(telegram_user_id: str, mensagem_resumida: str):
    """
    Gera embedding da mensagem resumida e salva no pgvector com uma data de expiração.
    """
    if not DATABASE_URL:
        logger.warning("DATABASE_URL não configurada. Memória não será salva.")
        return False
        
    try:
        # Gera o embedding
        embedding = embedding_model.encode(mensagem_resumida).tolist()
        
        # Calcula a data de expiração baseada no TTL configurado
        expira_em = datetime.now() + timedelta(days=MEMORY_TTL_DAYS)
        
        # Insere no banco
        conn = await _get_conn()
        try:
            # 1. Garante que o contato existe e pega o ID da tabela contatos
            # Tenta pegar o nome se disponível no futuro ou passar None
            contato_id = await _get_or_create_contato(conn, telegram_user_id)
            
            # O array de embedding precisa ser inserido como string literal para o pgvector
            # Usamos json.dumps para formatar a lista Python num array literal [1.0, 2.0...] compatível com pgvector
            emb_str = json.dumps(embedding)
            
            await conn.execute(
                '''
                INSERT INTO memoria_vetorial (contato_id, conteudo, embedding, criado_em, expira_em)
                VALUES ($1, $2, $3::vector, $4, $5)
                ''',
                contato_id,
                mensagem_resumida,
                emb_str,
                datetime.now(),
                expira_em
            )
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao salvar contexto: {e}")
        return False

async def update_user_name(telegram_user_id: str, nome: str):
    """Atualiza apenas o nome do usuário na tabela contatos."""
    try:
        conn = await _get_conn()
        try:
            await _get_or_create_contato(conn, telegram_user_id, nome)
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao atualizar nome do usuário: {e}")
        return False

async def get_context(telegram_user_id: str, limit: int = 10):
    """
    Busca as memórias recentes e válidas do usuário no pgvector.
    Retorna uma lista de strings com os resumos das conversas.
    """
    if not DATABASE_URL:
        return []
        
    try:
        conn = await _get_conn()
        try:
            # 1. Garante que o contato existe para buscar o ID correto
            contato_id = await _get_or_create_contato(conn, telegram_user_id)
            
            # Busca ignorando os expirados, pela ordem de criação descendente
            rows = await conn.fetch(
                '''
                SELECT conteudo FROM memoria_vetorial 
                WHERE contato_id = $1 AND expira_em > NOW()
                ORDER BY criado_em DESC
                LIMIT $2
                ''',
                contato_id,
                limit
            )
            # Reverte para ficar em ordem cronológica (mais antigo primeiro)
            resumos = [row['conteudo'] for row in reversed(rows)]
            return resumos
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao ler contexto: {e}")
        return []

async def save_pending_action(telegram_user_id: str, tool_name: str, args: dict):
    """Salva uma ação pendente para confirmação do usuário."""
    try:
        conn = await _get_conn()
        try:
            contato_id = await _get_or_create_contato(conn, telegram_user_id)
            arg_json = json.dumps(args)
            
            # Limpa pendências antigas antes de salvar a nova
            await conn.execute("DELETE FROM pendencias WHERE contato_id = $1", contato_id)
            
            await conn.execute(
                '''
                INSERT INTO pendencias (contato_id, ferramenta, argumentos)
                VALUES ($1, $2, $3)
                ''',
                contato_id, tool_name, arg_json
            )
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao salvar ação pendente: {e}")
        return False

async def get_pending_action(telegram_user_id: str):
    """Recupera a última ação pendente do usuário."""
    try:
        conn = await _get_conn()
        try:
            contato_id = await _get_or_create_contato(conn, telegram_user_id)
            row = await conn.fetchrow(
                "SELECT ferramenta, argumentos FROM pendencias WHERE contato_id = $1 ORDER BY criado_em DESC LIMIT 1",
                contato_id
            )
            if row:
                return {
                    "tool": row['ferramenta'],
                    "args": json.loads(row['argumentos'])
                }
            return None
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao buscar ação pendente: {e}")
        return None

async def clear_pending_action(telegram_user_id: str):
    """Remove a ação pendente após confirmação ou cancelamento."""
    try:
        conn = await _get_conn()
        try:
            contato_id = await _get_or_create_contato(conn, telegram_user_id)
            await conn.execute("DELETE FROM pendencias WHERE contato_id = $1", contato_id)
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao limpar ação pendente: {e}")
        return False

async def build_context_for_llama(telegram_user_id: str, limit: int = 10):
    """
    Gera o array de messages no formato {role: "system", content: "..."} que o Llama espera.
    Adiciona a memória da última pra mais recente sem poluir a visão principal.
    """
    historico = await get_context(telegram_user_id, limit)
    
    messages = []
    if historico:
        # Pega as últimas memórias e adiciona uma instrução do sistema
        context_str = "Memória da(s) última(s) conversa(s) com este usuário (não o mencione a menos que necessário):\n"
        for i, h in enumerate(historico):
            context_str += f"- {h}\n"
            
        messages.append({
            "role": "system",
            "content": context_str
        })
        
    return messages
