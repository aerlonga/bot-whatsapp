import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

async def pesquisar_web(query: str = "", **kwargs) -> dict:
    """
    Pesquisa na internet usando DuckDuckGo.
    Retorna os top 3 resultados formatados.
    """
    if not query:
        query = kwargs.get("query", "")
    
    if not query:
        return {
            "success": False,
            "result": "Nenhum termo de pesquisa fornecido. Use: @pesquisa [seu termo]"
        }
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="br-pt", max_results=3))
        
        if not results:
            return {
                "success": True,
                "result": f"Não encontrei resultados para '{query}'. Tente reformular a busca."
            }
        
        texto = f"🔍 *Resultados para:* _{query}_\n\n"
        for i, r in enumerate(results, 1):
            titulo = r.get("title", "Sem título")
            snippet = r.get("body", "")
            link = r.get("href", "")
            texto += f"*{i}. {titulo}*\n"
            texto += f"{snippet}\n"
            if link:
                texto += f"🔗 {link}\n"
            texto += "\n"
        
        return {
            "success": True,
            "result": texto.strip(),
            "data": {"query": query, "num_results": len(results)}
        }
        
    except Exception as e:
        logger.error(f"Erro na pesquisa web: {e}")
        return {
            "success": False,
            "result": "Não consegui realizar a pesquisa no momento. Tente novamente mais tarde."
        }
