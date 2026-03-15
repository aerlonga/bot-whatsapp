import httpx
import logging
from app.config import SPRING_API_URL, SPRING_API_KEY

logger = logging.getLogger(__name__)

async def consultar_orcamentos(**kwargs):
    """
    Consulta orçamentos na API do Spring Boot.
    """
    servico = kwargs.get("servico", "")
    
    headers = {
        "X-API-Key": SPRING_API_KEY
    }
    
    url = f"{SPRING_API_URL}/api/orcamentos"
    if servico:
        url += f"?servico={servico}"
        
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if servico:
                texto = f"A categoria '{servico}' possui orcamento mensal de R${data.get('orcamento', 0):.2f}. Foram gastos R${data.get('gasto',0):.2f}, restando R${data.get('saldo',0):.2f}."
            else:
                texto = f"No geral, o orçamento deste mês é de R${data.get('orcamento', 0):.2f}. Já foram gastos R${data.get('gasto',0):.2f}, restando R${data.get('saldo',0):.2f}."
            
            return {
                "success": True,
                "result": texto,
                "data": data
            }
    except Exception as e:
        logger.error(f"Erro ao consultar orçamentos no Spring: {e}")
        return {
            "success": False,
            "result": "Não consegui acessar as informações do seu orçamentos no momento (Serviço Fora do Ar).",
            "data": None
        }
