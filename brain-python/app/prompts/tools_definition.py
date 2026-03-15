TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "registrar_gasto",
            "description": "Registra um gastos financeiro (local, valor, categoria, data).",
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
            "description": "Confirma ou cancela uma ação pendente (como o registro de um gastos ou economia) quando o usuário responde 'Sim' ou 'Não'.",
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
            "description": "Consulta orçamentos, saldos ou gastos acumulados por categoria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "servico": {
                        "type": "string",
                        "description": "Nome da categoria (ex: Alimentação, Transporte, Total). Se vazio, retorna visão geral."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_gastos",
            "description": "Consulta o resumo de gastos do usuário em um período determinado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string",
                        "description": "Período da consulta.",
                        "enum": ["hoje", "ontem", "semana", "mes", "total", "especifico"]
                    },
                    "data": {
                        "type": "string",
                        "description": "Data específica (ex: '09/03/2026'). Apenas se período for 'especifico'."
                    },
                    "categoria": {
                        "type": "string",
                        "description": "Filtrar por categoria (opcional)."
                    }
                },
                "required": ["periodo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_economia",
            "description": "Registra um valor (dinheiro) que o usuário guardou ou economizou.",
            "parameters": {
                "type": "object",
                "properties": {
                    "valor": {
                        "type": "number",
                        "description": "Valor guardado em reais."
                    },
                    "descricao": {
                        "type": "string",
                        "description": "Descrição ou motivo (ex: 'salário', 'poupança', 'mesada')."
                    }
                },
                "required": ["valor"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_economias",
            "description": "Consulta o total de economias ou dinheiro guardado pelo usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string",
                        "description": "Período da consulta.",
                        "enum": ["hoje", "semana", "mes", "total"]
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pesquisar_web",
            "description": "Pesquisa informações financeiras e econômicas atualizadas na internet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca (ex: 'taxa selic atual', 'valor dólar hoje')."
                    }
                },
                "required": ["query"]
            }
        }
    }
]
