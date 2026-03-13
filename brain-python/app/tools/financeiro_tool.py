import httpx
import logging
import asyncpg
from datetime import datetime

from app.config import SPRING_API_URL, SPRING_API_KEY, DATABASE_URL

logger = logging.getLogger(__name__)

async def registrar_gasto(**kwargs):
    """
    Registra um gasto na API em Spring Boot.
    Se a API estiver fora, salva no PostgreSQL local (tabela gastos) com enviado_spring=False.
    """
    estabelecimento = kwargs.get('estabelecimento', 'Desconhecido')
    # Pode vir como float (15.5) ou string ("15.5") do modelo
    raw_valor = kwargs.get('valor', 0)
    try:
        valor = float(raw_valor)
    except:
        valor = 0.0
        
    categoria = kwargs.get('categoria', 'Outros')
    data_gasto = kwargs.get('data', datetime.now().strftime("%Y-%m-%d"))
    
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
        # Spring falhou ou timeout -> Salvar Localmente no banco principal Postgres
        logger.warning(f"Erro ao contatar API de Finanças: {e}. Salvando em Fallback Local no PostgreSQL.")
        
        try:
            # Tenta inserir na tabela gastos local que criamos no init.sql
            if DATABASE_URL:
                conn = await asyncpg.connect(DATABASE_URL)
                try:
                    # Converte string de data para objeto date esperado pelo banco, mas asyncpg aceita string pra DATE tbm
                    await conn.execute(
                        '''
                        INSERT INTO gastos (estabelecimento, valor, categoria, data_gasto, enviado_spring)
                        VALUES ($1, $2, $3, $4::date, FALSE)
                        ''',
                        estabelecimento,
                        valor,
                        categoria,
                        data_gasto
                    )
                finally:
                    await conn.close()
                
                return {
                    "success": True,
                    "result": f"O sistema principal está fora do ar, mas anotei temporariamente seu gasto de R$ {valor:.2f} na categoria {categoria}.",
                    "data": {"estabelecimento": estabelecimento, "valor": valor, "local": True}
                }
            else:
                raise Exception("DATABASE_URL não configurada.")
                
        except Exception as db_err:
            logger.error(f"Erro no banco de fallback (PostgreSQL): {db_err}")
            return {
                "success": False,
                "result": "Houve uma falha crítica ao anotar o seu gasto. O serviço está temporariamente indisponível.",
                "data": None
            }
