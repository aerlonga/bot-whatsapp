import logging
from app.tools.financeiro_tool import registrar_gasto, consultar_gastos
from app.tools.orcamento_tool import consultar_orcamentos
from app.tools.economia_tool import registrar_economia, consultar_economias
from app.tools.web_search_tool import pesquisar_web

from app.services.context_service import get_pending_action, clear_pending_action

logger = logging.getLogger(__name__)

async def run_tool(name: str, args: dict, user_id: str | None = None) -> dict:
    """
    Roteador de ferramentas. Recebe o nome da ferramenta enviada pelo Ollama,
    chama a função correta do python com os argumentos, e retorna resultado formatado.
    """
    logger.info(f"[ToolRunner] Executando tool: {name} com argumentos: {args}")
    
    try:
        if name == "registrar_gasto":
            return await registrar_gasto(user_id=user_id, **args)
            
        elif name == "confirmar_acao":
            confirmado = args.get("confirmado", False)
            if not confirmado:
                await clear_pending_action(user_id)
                return {"success": True, "result": "Ação cancelada pelo usuário."}
            
            pending = await get_pending_action(user_id)
            if not pending:
                return {"success": False, "result": "Não encontrei nenhuma ação pendente para confirmar."}
            
            if pending["tool"] == "registrar_gasto":
                res = await registrar_gasto(user_id=user_id, confirmed=True, **pending["args"])
                await clear_pending_action(user_id)
                return res
            elif pending["tool"] == "registrar_economia":
                res = await registrar_economia(user_id=user_id, confirmed=True, **pending["args"])
                await clear_pending_action(user_id)
                return res
            
            return {"success": False, "result": "A ferramenta pendente não é suportada para confirmação direta."}
            
        elif name == "consultar_orcamentos":
            return await consultar_orcamentos(**args)
            
        elif name == "consultar_gastos":
            return await consultar_gastos(user_id=user_id, **args)
        
        elif name == "registrar_economia":
            return await registrar_economia(user_id=user_id, **args)
        
        elif name == "consultar_economias":
            return await consultar_economias(user_id=user_id, **args)
        
        elif name == "pesquisar_web":
            return await pesquisar_web(**args)
            
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
