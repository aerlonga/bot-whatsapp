import logging
import asyncio
import httpx
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import RatelimitException, DuckDuckGoSearchException

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Mapa de palavras-chave → moeda na AwesomeAPI
# Permite resposta direta sem depender do DDG
# ──────────────────────────────────────────────
CURRENCY_KEYWORDS = {
    "dólar": "USD-BRL",
    "dolar": "USD-BRL",
    "usd": "USD-BRL",
    "euro": "EUR-BRL",
    "eur": "EUR-BRL",
    "libra": "GBP-BRL",
    "gbp": "GBP-BRL",
    "bitcoin": "BTC-BRL",
    "btc": "BTC-BRL",
    "ethereum": "ETH-BRL",
    "eth": "ETH-BRL",
}

async def _fetch_currency(pair: str) -> str | None:
    """
    Busca cotação em tempo real via economia.awesomeapi.com.br.
    Retorna string formatada ou None se falhar.
    """
    try:
        url = f"https://economia.awesomeapi.com.br/json/last/{pair}"
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
            key = pair.replace("-", "")
            coin = data.get(key, {})
            if not coin:
                return None
            name = coin.get("name", pair)
            bid = coin.get("bid", "?")
            ask = coin.get("ask", "?")
            high = coin.get("high", "?")
            low = coin.get("low", "?")
            pct = coin.get("pctChange", "?")
            create_date = coin.get("create_date", "")
            return (
                f"📊 **Cotação {name}** ({create_date})\n"
                f"• Compra: R$ {float(bid):.2f}\n"
                f"• Venda:  R$ {float(ask):.2f}\n"
                f"• Máx:   R$ {float(high):.2f}\n"
                f"• Mín:   R$ {float(low):.2f}\n"
                f"• Variação: {pct}%\n"
                f"Fonte: economia.awesomeapi.com.br"
            )
    except Exception as e:
        logger.warning(f"[WebSearch] AwesomeAPI falhou para {pair}: {e}")
        return None


def _ddgs_search_sync(query: str, max_results: int = 5) -> list:
    """
    Executa a busca DuckDuckGo de forma síncrona com retry interno.
    Separado para rodar em thread via asyncio.to_thread.
    """
    last_exc = None
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                return list(ddgs.text(query, region="br-br", max_results=max_results))
        except RatelimitException as e:
            last_exc = e
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(f"[WebSearch] Rate limit DDG (tentativa {attempt+1}). Aguardando {wait}s...")
            import time
            time.sleep(wait)
        except DuckDuckGoSearchException as e:
            last_exc = e
            logger.warning(f"[WebSearch] Erro DDG (tentativa {attempt+1}): {e}")
            import time
            time.sleep(1)
        except Exception as e:
            last_exc = e
            logger.error(f"[WebSearch] Erro inesperado DDG: {e}")
            break
    logger.error(f"[WebSearch] DDG falhou após retries: {last_exc}")
    return []


async def pesquisar_web(query: str = "", **kwargs) -> dict:
    """
    Pesquisa na internet usando DuckDuckGo com:
    - Fallback rápido para AwesomeAPI em cotações de moeda
    - Retry automático com backoff em rate-limit
    """
    if not query:
        query = kwargs.get("query", "")

    if not query:
        return {
            "success": False,
            "result": "Nenhum termo de pesquisa fornecido. Use: !pesquisa [seu termo]"
        }

    query_lower = query.lower()

    # ── FAST PATH: Cotações de moeda via API dedicada ──────────────────────
    for keyword, pair in CURRENCY_KEYWORDS.items():
        if keyword in query_lower:
            logger.info(f"[WebSearch] Fast-path cotação detectada: {keyword} → {pair}")
            result = await _fetch_currency(pair)
            if result:
                return {"success": True, "result": result, "data": {"source": "awesomeapi", "pair": pair}}
            # Se a API falhou, cai para DDG normalmente
            logger.warning(f"[WebSearch] AwesomeAPI falhou, tentando DDG para '{query}'")
            break

    # ── BUSCA DDG com retry ────────────────────────────────────────────────
    try:
        current_query = f"{query} hoje março 2026"
        # Roda em thread para não bloquear o event loop
        results = await asyncio.to_thread(_ddgs_search_sync, current_query, 5)

        if not results:
            return {
                "success": False,
                "result": (
                    f"Não encontrei resultados para '{query}' no momento. "
                    "O DuckDuckGo pode estar temporariamente indisponível. Tente novamente em alguns segundos."
                )
            }

        # Formato estruturado tipo "Observation" para o LLM extrair dados
        output = f"OBSERVAÇÃO DA BUSCA WEB (Termo: {query}):\n"
        for i, r in enumerate(results, 1):
            output += f"--- RESULTADO {i} ---\n"
            output += f"Título: {r.get('title')}\n"
            output += f"Conteúdo: {r.get('body')}\n"
            output += f"Fonte: {r.get('href')}\n"

        return {
            "success": True,
            "result": output.strip(),
            "data": {"query": query, "num_results": len(results), "source": "duckduckgo"}
        }

    except Exception as e:
        logger.error(f"[WebSearch] Erro geral na pesquisa: {e}")
        return {
            "success": False,
            "result": "Não consegui realizar a pesquisa no momento. Tente novamente mais tarde."
        }
