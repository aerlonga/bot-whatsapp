TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "registrar_gasto",
            "description": "Registra uma despesa ou gasto no sistema financeiro. Use esta ferramenta quando o usuário mencionar que gastou, comprou ou pagou algo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "estabelecimento": {
                        "type": "string",
                        "description": "Nome do local, loja ou entidade onde o gasto foi feito (ex: Mercado, Uber, Farmácia). Se não mencionado, crie um nome genérico aplicável."
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor monetário do gasto (ex: 50.00). Use sempre formato numérico (float)."
                    },
                    "categoria": {
                        "type": "string",
                        "description": "Categoria do gasto obrigatória de acodo com o prompt (Alimentação, Transporte, Saúde, Moradia, Lazer, Educação, Outros).",
                        "enum": ["Alimentação", "Transporte", "Saúde", "Moradia", "Lazer", "Educação", "Outros"]
                    },
                    "data": {
                        "type": "string",
                        "description": "Data aproximada ou exata mencionada, no formato YYYY-MM-DD. O padrão é a data de hoje, calcule se ele falar 'ontem' em relação a hoje."
                    }
                },
                "required": ["estabelecimento", "valor", "categoria"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_orcamentos",
            "description": "Verifica os orçamentos, saldos ou gastos acumulados em um serviço para saber se o usuário ainda pode gastar com ele.",
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
