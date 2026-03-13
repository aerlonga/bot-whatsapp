import logging

logger = logging.getLogger(__name__)

async def marcar_reuniao(**kwargs):
    """
    Agenda uma reunião ou compromisso. (Stub).
    """
    titulo = kwargs.get("titulo")
    data = kwargs.get("data")
    hora = kwargs.get("hora")
    duracao_minutos = kwargs.get("duracao_minutos", 60)
    
    logger.info(f"Recebido pedido para marcar reunião: {titulo} às {data} {hora} ({duracao_minutos} min)")
    
    return {
        "success": True,
        "result": f"A reunião '{titulo}' em {data} às {hora} foi anotada. (Integração com Google Calendar pendente)",
        "data": {
            "titulo": titulo,
            "data": data,
            "hora": hora,
            "duracao": duracao_minutos
        }
    }
