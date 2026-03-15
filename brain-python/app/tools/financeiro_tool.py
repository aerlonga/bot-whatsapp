import httpx
import logging
import asyncpg
import re
from datetime import datetime

from app.config import SPRING_API_URL, SPRING_API_KEY, DATABASE_URL
from app.services.context_service import _get_or_create_contato, save_pending_action

logger = logging.getLogger(__name__)

def _parse_brazilian_date(date_str: str) -> str:
    """
    Converte data de dd/mm/aaaa ou dd/mm/aa para YYYY-MM-DD.
    Se já estiver no formato ISO ou for inválida, lida adequadamente.
    """
    if not date_str or "disponível" in date_str.lower():
        return datetime.now().strftime("%Y-%m-%d")
        
    # Tenta DD/MM/YYYY
    match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', date_str)
    if match:
        d, m, y = match.groups()
        if len(y) == 2:
            y = "20" + y
        try:
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        except:
            pass
            
    # Tenta extrair YYYY-MM-DD
    match_iso = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match_iso:
        return match_iso.group(0)
        
    return datetime.now().strftime("%Y-%m-%d")

async def registrar_gasto(user_id=None, confirmed=False, **kwargs):
    """
    Registra um gasto na API em Spring Boot.
    Se confirmed for False, salva como pendente e retorna mensagem de confirmação.
    """
    estabelecimento = kwargs.get('estabelecimento', 'Desconhecido')
    raw_valor = kwargs.get('valor', 0)
    try:
        valor = float(raw_valor)
    except:
        valor = 0.0
        
    categoria = kwargs.get('categoria', 'Outros')
    
    # Tratamento de data
    raw_data = kwargs.get('data', '')
    data_gasto = _parse_brazilian_date(raw_data)
    
    if not confirmed:
        # Salva as info pra confirmação
        pending_args = {
            "estabelecimento": estabelecimento,
            "valor": valor,
            "categoria": categoria,
            "data": data_gasto
        }
        await save_pending_action(user_id, "registrar_gasto", pending_args)
        
        # Formata data para exibição ao usuário
        try:
            date_obj = datetime.strptime(data_gasto, "%Y-%m-%d")
            data_formatada = date_obj.strftime("%d/%m/%Y")
        except:
            data_formatada = data_gasto
            
        return {
            "success": True,
            "needs_confirmation": True,
            "result": f"Confirma o gasto de *R$ {valor:.2f}* em *{estabelecimento}* (Categoria: {categoria}) no dia *{data_formatada}*? (Responda Sim ou Não)",
            "data": pending_args
        }

    payload = {
        "estabelecimento": estabelecimento,
        "valor": valor,
        "categoria": categoria,
        "data": data_gasto
    }
    
    headers = {
        "X-API-Key": SPRING_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        # Tenta enviar para a API do Spring
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{SPRING_API_URL}/api/gastos", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            return {
                "success": True,
                "result": f"Gasto de R$ {valor:.2f} registrado com sucesso em {categoria} no sistema.",
                "data": data
            }
    except Exception as e:
        # Fallback Local
        logger.warning(f"Erro ao contatar API de Finanças: {e}. Salvando em Fallback Local no PostgreSQL.")
        
        try:
            if DATABASE_URL:
                conn = await asyncpg.connect(DATABASE_URL)
                try:
                    contato_id = None
                    if user_id:
                        contato_id = await _get_or_create_contato(conn, user_id)
                        
                    data_gasto_date = datetime.strptime(data_gasto, "%Y-%m-%d").date()
                        
                    await conn.execute(
                        '''
                        INSERT INTO gastos (contato_id, estabelecimento, valor, categoria, data_gasto, enviado_spring)
                        VALUES ($1, $2, $3, $4, $5, FALSE)
                        ''',
                        contato_id, estabelecimento, valor, categoria, data_gasto_date
                    )
                finally:
                    await conn.close()
                
                return {
                    "success": True,
                    "result": f"O sistema principal está fora do ar, mas anotei seu gasto de R$ {valor:.2f} na categoria {categoria}.",
                    "data": {"estabelecimento": estabelecimento, "valor": valor, "local": True}
                }
            else:
                raise Exception("DATABASE_URL não configurada.")
        except Exception as db_err:
            logger.error(f"Erro no banco de fallback: {db_err}")
            return {"success": False, "result": "Falha crítica ao salvar o gasto."}

async def consultar_gastos(user_id=None, periodo="hoje", categoria=None, **kwargs):
    """
    Consulta gastos no banco de dados local com agregação para performance e privacidade.
    """
    if not DATABASE_URL:
        return {"success": False, "result": "Configuração de banco de dados ausente."}

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # 1. Isolamento: Pega o contato_id do usuário que está chamando
            contato_id = await _get_or_create_contato(conn, user_id)
            
            # 2. Define o filtro de data
            date_filter = "AND data_gasto = CURRENT_DATE"
            periodo_nome = "de hoje"
            
            if periodo == "ontem":
                date_filter = "AND data_gasto = CURRENT_DATE - INTERVAL '1 day'"
                periodo_nome = "de ontem"
            elif periodo == "semana":
                date_filter = "AND data_gasto >= CURRENT_DATE - INTERVAL '7 days'"
                periodo_nome = "dos últimos 7 dias"
            elif periodo == "mes":
                date_filter = "AND data_gasto >= DATE_TRUNC('month', CURRENT_DATE)"
                periodo_nome = "deste mês"
            elif periodo == "total":
                date_filter = ""
                periodo_nome = "de todo o histórico"
            elif periodo == "especifico":
                raw_data = kwargs.get('data', '')
                data_iso = _parse_brazilian_date(raw_data)
                date_filter = f"AND data_gasto = '{data_iso}'"
                periodo_nome = f"do dia {datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')}"

            # 3. Filtro de categoria
            cat_filter = ""
            params = [contato_id]
            if categoria:
                cat_filter = "AND categoria = $2"
                params.append(categoria)

            # 4. Agregação no Banco (Escalável!)
            query = f'''
                SELECT 
                    COUNT(*) as total_compras,
                    COALESCE(SUM(valor), 0) as soma_total
                FROM gastos
                WHERE contato_id = $1 {date_filter} {cat_filter}
            '''
            
            row = await conn.fetchrow(query, *params)
            
            # 5. Busca detalhes (Top 5 para não estourar contexto)
            details_query = f'''
                SELECT estabelecimento, valor, data_gasto, categoria
                FROM gastos
                WHERE contato_id = $1 {date_filter} {cat_filter}
                ORDER BY data_gasto DESC, criado_em DESC
                LIMIT 5
            '''
            details = await conn.fetch(details_query, *params)
            
            soma = float(row['soma_total'])
            qtd = row['total_compras']
            
            if qtd == 0:
                return {
                    "success": True, 
                    "result": f"Você não possui gastos registrados {periodo_nome}."
                }
                
            resumo = f"📊 *Resumo Financeiro ({periodo_nome})*\n"
            resumo += f"- Total Gasto: *R$ {soma:.2f}*\n"
            resumo += f"- Quantidade: {qtd} registros\n\n"
            
            if details:
                resumo += "*Últimos lançamentos:*\n"
                for d in details:
                    data_str = d['data_gasto'].strftime("%d/%m")
                    resumo += f"• {data_str}: {d['estabelecimento']} - R$ {float(d['valor']):.2f} ({d['categoria']})\n"
            
            if qtd > 5:
                resumo += f"\n_... e outros {qtd-5} lançamentos._"
                
            return {
                "success": True,
                "result": resumo,
                "data": {"total": soma, "qtd": qtd}
            }
            
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Erro ao consultar gastos: {e}")
        return {"success": False, "result": "Erro interno ao processar sua consulta financeira."}
