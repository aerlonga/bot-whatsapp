import logging

logger = logging.getLogger(__name__)

async def enviar_email(**kwargs):
    """
    Envia email. (Stub).
    """
    destinatario = kwargs.get("destinatario")
    assunto = kwargs.get("assunto")
    corpo = kwargs.get("corpo")
    
    logger.info(f"Recebido pedido para enviar email para {destinatario}: {assunto} - {corpo}")
    
    return {
        "success": True,
        "result": f"O email para {destinatario} com assunto '{assunto}' foi registrado internamente. (Integração SMTP pendente)",
        "data": {
            "destinatario": destinatario,
            "assunto": assunto,
            "corpo_length": len(corpo) if corpo else 0
        }
    }
