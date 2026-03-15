import logging
import asyncpg
from datetime import datetime

from app.config import DATABASE_URL
from app.services.context_service import _get_or_create_contato, save_pending_action

logger = logging.getLogger(__name__)

async def registrar_economia(user_id=None, confirmed=False, **kwargs) -> dict:
    """
    Registra uma economia/poupança do usuário.
    Se confirmed=False, salva como pendente e pede confirmação.
    """
    raw_valor = kwargs.get("valor", 0)
    try:
        valor = float(raw_valor)
    except (ValueError, TypeError):
        valor = 0.0
    
    if valor <= 0:
        return {
            "success": False,
            "result": "O valor da economia precisa ser maior que zero."
        }
    
    descricao = kwargs.get("descricao", "Economia geral")
    
    if not confirmed:
        pending_args = {
            "valor": valor,
            "descricao": descricao
        }
        await save_pending_action(user_id, "registrar_economia", pending_args)
        
        return {
            "success": True,
            "needs_confirmation": True,
            "result": f"Confirma o registro de *R$ {valor:.2f}* guardado ({descricao})? (Responda Sim ou Não)",
            "data": pending_args
        }
    
    if not DATABASE_URL:
        return {"success": False, "result": "Configuração de banco de dados ausente."}
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            contato_id = await _get_or_create_contato(conn, user_id)
            
            await conn.execute(
                '''
                INSERT INTO economias (contato_id, valor, descricao, data_registro)
                VALUES ($1, $2, $3, CURRENT_DATE)
                ''',
                contato_id, valor, descricao
            )
            
            return {
                "success": True,
                "result": f"💰 Economia de *R$ {valor:.2f}* registrada com sucesso! ({descricao})",
                "data": {"valor": valor, "descricao": descricao}
            }
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao registrar economia: {e}")
        return {"success": False, "result": "Erro ao salvar a economia no banco de dados."}

async def consultar_economias(user_id=None, periodo="mes", **kwargs) -> dict:
    """
    Consulta o total de economias do usuário em um período.
    """
    if not DATABASE_URL:
        return {"success": False, "result": "Configuração de banco de dados ausente."}
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            contato_id = await _get_or_create_contato(conn, user_id)
            
            date_filter = "AND data_registro >= DATE_TRUNC('month', CURRENT_DATE)"
            periodo_nome = "deste mês"
            
            if periodo == "hoje":
                date_filter = "AND data_registro = CURRENT_DATE"
                periodo_nome = "de hoje"
            elif periodo == "semana":
                date_filter = "AND data_registro >= CURRENT_DATE - INTERVAL '7 days'"
                periodo_nome = "dos últimos 7 dias"
            elif periodo == "total":
                date_filter = ""
                periodo_nome = "de todo o histórico"
            
            # Agregação
            row = await conn.fetchrow(
                f'''
                SELECT 
                    COUNT(*) as total_registros,
                    COALESCE(SUM(valor), 0) as soma_total
                FROM economias
                WHERE contato_id = $1 {date_filter}
                ''',
                contato_id
            )
            
            # Detalhes (últimos 5)
            details = await conn.fetch(
                f'''
                SELECT valor, descricao, data_registro
                FROM economias
                WHERE contato_id = $1 {date_filter}
                ORDER BY data_registro DESC, criado_em DESC
                LIMIT 5
                ''',
                contato_id
            )
            
            soma = float(row['soma_total'])
            qtd = row['total_registros']
            
            if qtd == 0:
                return {
                    "success": True,
                    "result": f"Você não possui economias registradas {periodo_nome}."
                }
            
            resumo = f"💰 *Resumo de Economias ({periodo_nome})*\n"
            resumo += f"- Total Guardado: *R$ {soma:.2f}*\n"
            resumo += f"- Quantidade: {qtd} registros\n\n"
            
            if details:
                resumo += "*Últimos registros:*\n"
                for d in details:
                    data_str = d['data_registro'].strftime("%d/%m")
                    desc = d['descricao'] or "Economia geral"
                    resumo += f"• {data_str}: R$ {float(d['valor']):.2f} ({desc})\n"
            
            if qtd > 5:
                resumo += f"\n_... e outros {qtd - 5} registros._"
            
            return {
                "success": True,
                "result": resumo,
                "data": {"total": soma, "qtd": qtd}
            }
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao consultar economias: {e}")
        return {"success": False, "result": "Erro ao consultar suas economias."}
