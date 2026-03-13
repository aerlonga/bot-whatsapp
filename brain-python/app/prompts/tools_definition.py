TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "registrar_gasto",
            "description": "Registra um gasto financeiro (local, valor, categoria, data).",
            "parameters": {
                "type": "object",
                "properties": {
                    "estabelecimento": {
                        "type": "string",
                        "description": "Local/loja."
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor numérico."
                    },
                    "categoria": {
                        "type": "string",
                        "description": "Alimentação, Transporte, Lazer, etc.",
                        "enum": ["Alimentação", "Transporte", "Saúde", "Moradia", "Lazer", "Educação", "Outros"]
                    },
                    "data": {
                        "type": "string",
                        "description": "Data mencionada (ex: 'hoje', 'ontem', '13/03/2026' ou '2026-03-13')."
                    }
                },
                "required": ["estabelecimento", "valor", "categoria"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirmar_acao",
            "description": "Confirma ou cancela uma ação pendente (como o registro de um gasto) quando o usuário responde 'Sim' ou 'Não' após ser solicitado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmado": {
                        "type": "boolean",
                        "description": "True se o usuário confirmou (Sim), False se cancelou (Não)."
                    }
                },
                "required": ["confirmado"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_orcamentos",
            "description": "REGRA EXTREMAMENTE IMPORTANTE: Você SÓ DEVE usar esta ferramenta SE e SOMENTE SE o usuário digitar EXATAMENTE a palavra '@orçamento' no início da mensagem. Verifica os orçamentos, saldos ou gastos acumulados em um serviço para saber se o usuário ainda pode gastar com ele.",
            "parameters": {
                "type": "object",
                "properties": {
                    "servico": {
                        "type": "string",
                        "description": "Nome da categoria, serviço ou área que deseja consultar (ex: Alimentação, Transporte, Total). Se vazio, retorna uma visão geral."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "marcar_reuniao",
            "description": "Agenda uma reunião ou compromisso no calendário do usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {
                        "type": "string",
                        "description": "Título ou assunto da reunião."
                    },
                    "data": {
                        "type": "string",
                        "description": "Data do compromisso no formato YYYY-MM-DD."
                    },
                    "hora": {
                        "type": "string",
                        "description": "Hora do compromisso no formato HH:MM."
                    },
                    "duracao_minutos": {
                        "type": "integer",
                        "description": "Duração em minutos da reunião. Padrão 60.",
                        "default": 60
                    }
                },
                "required": ["titulo", "data", "hora"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enviar_email",
            "description": "Envia um email para um destinatário com um assunto e corpo de texto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destinatario": {
                        "type": "string",
                        "description": "Endereço de email de destino."
                    },
                    "assunto": {
                        "type": "string",
                        "description": "O tema central, título ou assunto principal do email."
                    },
                    "corpo": {
                        "type": "string",
                        "description": "O conteúdo completo que será enviado no corpo da mensagem de e-mail."
                    }
                },
                "required": ["destinatario", "assunto", "corpo"]
            }
        }
    }
]
