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
        # Salva para confirmação posterior
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
