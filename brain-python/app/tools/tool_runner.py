import logging
from app.tools.financeiro_tool import registrar_gasto
from app.tools.orcamento_tool import consultar_orcamentos
from app.tools.calendar_tool import marcar_reuniao
from app.tools.email_tool import enviar_email

logger = logging.getLogger(__name__)

async def run_tool(name: str, args: dict) -> dict:
    """
    Roteador de ferramentas. Recebe o nome da ferramenta enviada pelo Ollama,
    chama a função correta do python com os argumentos, e retorna resultado formatado.
    """
    logger.info(f"[ToolRunner] Executando tool: {name} com argumentos: {args}")
    
    try:
        if name == "registrar_gasto":
            return await registrar_gasto(**args)
            
        elif name == "consultar_orcamentos":
            return await consultar_orcamentos(**args)
            
        elif name == "marcar_reuniao":
            return await marcar_reuniao(**args)
            
        elif name == "enviar_email":
            return await enviar_email(**args)
            
        else:
            return {
                "success": False,
                "result": f"A ferramenta '{name}' não existe ou não está implementada.",
                "data": None
            }
            
    except TypeError as e:
        logger.error(f"[ToolRunner] Erro de tipos na ferramenta {name}: {e}")
        return {
            "success": False,
            "result": f"Faltam parâmetros obrigatórios para a ferramenta {name}.",
            "data": None
        }
    except Exception as e:
        logger.error(f"[ToolRunner] Erro ao executar {name}: {e}")
        return {
            "success": False,
            "result": f"Ocorreu um erro interno ao executar {name}: {str(e)}",
            "data": None
        }
