# Bot Telegram + IA Local — Roteiro

## Stack

| Telegram Bot API | Node.js Bridge | Redis BullMQ | Python Brain | Ollama GPU | Spring Boot |
|:---:|:---:|:---:|:---:|:---:|:---:|
| Entrada de mensagens | Ponte Telegram↔Fila | Fila assíncrona | Processamento IA | Modelos locais | Financeiro |

---

## Fase 1 — Infraestrutura & Bancos de Dados

### 1.1 — Criar o PostgreSQL + pgvector no Docker

Configura o banco relacional com suporte a vetores. Execute antes de qualquer outro serviço.

```
Crie a estrutura inicial do banco de dados para o projeto bot-telegram.

Contexto do projeto:
- Arquitetura de microserviços com Docker Compose
- Node.js (bridge Telegram), Python (brain IA), Spring Boot (financeiro)
- Usa pgvector para memória vetorial das conversas

Tarefas:
1. Crie a pasta postgres/init/ na raiz do projeto
2. Crie o arquivo postgres/init/01-init.sql com:
   - CREATE EXTENSION IF NOT EXISTS vector
   - Tabela "contatos" (id, telefone_telegram, nome, criado_em)
   - Tabela "memoria_vetorial" (id, contato_id FK, conteudo TEXT,
     embedding vector(384), criado_em, expira_em com DEFAULT NOW()+30 days)
   - Índice ivfflat na coluna embedding para busca por similaridade
   - Tabela "mensagens_processadas" (id VARCHAR PK = message_id do Telegram,
     contato_id FK, tipo VARCHAR, status VARCHAR, processado_em)
   - Tabela "gastos" (id, contato_id FK, estabelecimento, valor NUMERIC,
     categoria, data_gasto, mensagem_id FK, enviado_spring BOOLEAN, criado_em)
   - Tabela "orcamentos" (id, servico, valor_min, valor_max, descricao, ativo, criado_em)
3. Adicione o serviço "postgres" no docker-compose.yml existente:
   - image: pgvector/pgvector:pg16
   - variáveis vindas do .env (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
   - volume postgres_data para persistência
   - mount em /docker-entrypoint-initdb.d apontando para postgres/init/
   - na mesma rede "bot-network" já existente
4. Adicione as variáveis no .env:
   POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, DATABASE_URL

Não altere os serviços redis, brain-python e bridge-node já existentes.
Apenas acrescente o postgres e o volume/rede necessários.
```

---

### 1.2 — Configurar o Redis já existente como fila BullMQ

O Redis já está no docker-compose. Este passo configura as filas e testa a conexão.

```
Configure e documente a arquitetura de filas BullMQ no projeto bot-telegram.

O docker-compose.yml já tem o serviço Redis (bot-redis) na porta 6379.

Tarefas:
1. No bridge-node, instale as dependências se ainda não estiverem:
   npm install bullmq ioredis
2. Crie o arquivo bridge-node/src/queue.js com:
   - Conexão Redis usando REDIS_HOST e REDIS_PORT do .env
   - Exportar uma instância de Queue chamada "bot-ai"
   - Exportar uma instância de Worker para processar respostas
   - Configuração de retry: 3 tentativas, backoff exponencial 2s
3. Crie o arquivo bridge-node/src/queues/responseWorker.js que:
   - Escuta a fila "bot-ai-response"
   - Recebe { chat_id, text } e envia a resposta via Telegram Bot API
4. Adicione as variáveis no .env:
   REDIS_HOST=redis, REDIS_PORT=6379
   (Use o nome do serviço Docker "redis", não "localhost")
5. Crie um script bridge-node/src/testQueue.js que:
   - Enfileira uma mensagem de teste
   - Confirma que o Redis recebeu com redis-cli LLEN

Não crie o processador Python neste passo — apenas o lado Node.js.
```

---

### 1.3 — Atualizar o docker-compose.yml completo

Consolida todos os serviços numa única rede: postgres, redis, brain-python, bridge-node e spring-boot.

```
Atualize o docker-compose.yml do projeto para incluir todos os serviços.

Serviços atuais no arquivo: redis, brain-python, bridge-node.

Tarefas:
1. Adicione o serviço "postgres" (pgvector/pgvector:pg16) conforme feito na etapa 1.1
2. Adicione o serviço "spring-financeiro" com:
   - build: ./spring-financeiro (se existir) OU image: openjdk:17-jdk-slim
   - porta 8080:8080
   - variáveis: SPRING_DATASOURCE_URL, SPRING_DATASOURCE_USERNAME,
     SPRING_DATASOURCE_PASSWORD (apontando para o serviço "postgres")
   - depends_on: postgres
   - restart: unless-stopped
3. Garanta que TODOS os serviços estão na mesma rede:
   networks: [bot-network]
4. Defina a rede no final do arquivo:
   networks: { bot-network: { driver: bridge } }
5. Defina o volume no final:
   volumes: { postgres_data: {} }
6. Atualize o .env com TODAS as variáveis necessárias com valores padrão seguros:
   - AI_PROFILE, TELEGRAM_TOKEN
   - REDIS_HOST=redis, REDIS_PORT=6379
   - POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
   - DATABASE_URL=postgresql://user:pass@postgres:5432/dbname
   - PYTHON_API_URL=http://brain-python:8000
   - SPRING_API_URL=http://spring-financeiro:8080
   - SPRING_API_KEY (para autenticar o bot no Spring)

Mantenha o bloco "deploy.resources" da GPU no brain-python.
Mostre o arquivo docker-compose.yml completo ao final.
```

---

## Fase 2 — IA Local — Ollama + Modelos + Memória

> **Antes de começar:** o Ollama deve rodar no host Ubuntu (fora do Docker).
>
> ```bash
> export OLLAMA_HOST=0.0.0.0
> ollama serve &
>
> ollama pull llama3.1:8b   # texto + tool calling
> ollama pull minicpm-v     # visão / OCR
> # Whisper é instalado via pip no brain-python
> ```

### 2.1 — Configurar o Ollama e baixar modelos

```
Configure o serviço brain-python para se comunicar com o Ollama do host.

O Ollama roda no host Ubuntu (fora do Docker) com OLLAMA_HOST=0.0.0.0.
O docker-compose já tem: OLLAMA_HOST=http://host.docker.internal:11434

Tarefas:
1. No arquivo brain-python/app/services/ollama_service.py, crie/atualize:
   - Função async chat(model, messages, tools=None) que chama POST /api/chat
   - Função async vision(image_bytes, prompt) que usa o modelo minicpm-v
   - Tratamento de erro se Ollama não responder (retornar mensagem amigável)
   - Log do modelo usado e tempo de resposta
2. Crie brain-python/app/services/whisper_service.py:
   - Carrega o modelo whisper usando a variável AI_PROFILE
   - MED/HIGH: modelo "medium", LOW: modelo "base"
   - Função async transcribe(audio_bytes) -> str
   - Salva o áudio temporariamente, transcreve, deleta o temp
3. Crie brain-python/app/config.py com as configurações de perfil:
   - AI_PROFILE=MED: { text_model: llama3.1:8b, vision_model: minicpm-v, whisper: medium }
   - AI_PROFILE=LOW: { text_model: llama3.2:3b, vision_model: moondream, whisper: base }
   - AI_PROFILE=HIGH: { text_model: gpt-oss:20b, vision_model: minicpm-v, whisper: medium }
4. Adicione endpoint GET /health no main.py que verifica:
   - Conexão com Ollama (GET /api/tags)
   - GPU disponível (nvidia-smi)
   - Retorna JSON com status de cada componente
```

---

### 2.2 — System Prompt e comportamento da secretária

Define a personalidade, regras e contexto que o bot carrega em toda conversa.

```
Crie o sistema de prompts e contexto para a secretária IA no brain-python.

Tarefas:
1. Crie brain-python/app/prompts/system_prompt.py com a constante SYSTEM_PROMPT:
   - Definir que é uma secretária virtual profissional
   - Regras: responder em português BR, ser objetiva, confirmar ações antes de executar
   - Lista de categorias de gastos disponíveis:
     Alimentação, Transporte, Saúde, Moradia, Lazer, Educação, Outros
   - Instrução para usar as tools disponíveis quando necessário
   - Instrução: NUNCA inventar valores de orçamento — sempre consultar a tool
   - Instrução: ao registrar gasto, sempre confirmar: "Anotei R$ X em [categoria]. Correto?"
2. Crie brain-python/app/prompts/tools_definition.py com a lista de tools:
   - registrar_gasto(estabelecimento, valor, categoria, data)
   - consultar_orcamentos(servico)
   - marcar_reuniao(titulo, data, hora, duracao_minutos)
   - enviar_email(destinatario, assunto, corpo)
   Cada tool deve ter: name, description, parameters com tipos e required
3. Crie brain-python/app/services/context_service.py:
   - Função get_context(telegram_user_id) que busca as últimas N memórias
     do pgvector filtrando por contato e expira_em > NOW()
   - Função save_context(telegram_user_id, mensagem_resumida, embedding)
   - Usa psycopg2 ou asyncpg com DATABASE_URL do .env
   - Embedding gerado com sentence-transformers (modelo paraphrase-multilingual)
```

---

### 2.3 — Tool Calling (executor de ferramentas)

Quando o Llama decide usar uma tool, este módulo executa a ação real no mundo.

```
Implemente o executor de tool calls no brain-python.

Fluxo: Llama retorna JSON com tool_call → Python executa a ação real →
resultado volta para o Llama formatar a resposta final.

Tarefas:
1. Crie brain-python/app/tools/tool_runner.py com função async run_tool(tool_name, args):
   - Switch/match nos nomes das tools definidas em tools_definition.py
   - Cada case chama o serviço correspondente
   - Retorna dict { success: bool, result: str, data: dict }
2. Crie brain-python/app/tools/financeiro_tool.py:
   - Função async registrar_gasto(estabelecimento, valor, categoria, data)
   - Faz POST para SPRING_API_URL/api/gastos com header X-API-Key
   - Em caso de erro do Spring, salva localmente na tabela "gastos" com enviado_spring=False
   - Retorna confirmação com o id gerado
3. Crie brain-python/app/tools/orcamento_tool.py:
   - Função async consultar_orcamentos(servico)
   - Faz GET para SPRING_API_URL/api/orcamentos?servico=X
   - Formata resultado como texto legível para o Llama incluir na resposta
4. Crie brain-python/app/tools/calendar_tool.py (stub por agora):
   - Função async marcar_reuniao(titulo, data, hora, duracao_minutos)
   - Por enquanto, apenas loga e retorna "Reunião anotada (integração Google Calendar pendente)"
5. Crie brain-python/app/tools/email_tool.py (stub por agora):
   - Função async enviar_email(destinatario, assunto, corpo)
   - Por enquanto, apenas loga e retorna "Email registrado (integração SMTP pendente)"

Use variáveis SPRING_API_URL e SPRING_API_KEY do .env.
```

---

### 2.4 — Memória vetorial + limpeza TTL

O bot lembra de conversas antigas, mas limpa automaticamente após 30 dias.

```
Implemente o sistema de memória com TTL no projeto.

Tarefas:
1. Atualize brain-python/app/services/context_service.py:
   - Função build_context_for_llama(telegram_user_id) que:
     a) Busca últimas 10 memórias válidas (expira_em > NOW()) do pgvector
     b) Retorna lista de messages no formato {role: "system", content: resumo}
     c) Cada memória vira uma linha de contexto para o Llama
2. Crie o script brain-python/app/tasks/cleanup_memory.py:
   - Roda como cron (use APScheduler ou schedule)
   - A cada 6 horas, busca memórias com expira_em < NOW()
   - Para cada contato afetado, guarda o telegram_user_id
   - Deleta as memórias expiradas
   - Coloca na fila Redis (fila "bot-ai-response") uma mensagem para
     cada contato afetado: "Oi! Para manter a precisão das minhas respostas,
     arquivei nossas conversas de mais de 30 dias. Pode continuar normalmente!"
3. Inicie o scheduler junto com o FastAPI no brain-python/app/main.py:
   - Use o evento startup do FastAPI para iniciar o APScheduler
   - Adicione APScheduler ao requirements.txt
4. Adicione no .env:
   MEMORY_TTL_DAYS=30 (padrão, configurável)
```

---

## Fase 3 — Bridge Telegram (Node.js)

### 3.1 — Configurar o bot Telegram (node-telegram-bot-api)

Substitui o bot-web.js. Recebe mensagens do Telegram e joga na fila BullMQ.

```
Configure o bridge-node para usar o Telegram Bot API no lugar do bot.

Contexto: o projeto estava usando bot-web.js.
Motivo da migração: Telegram tem API oficial, sem risco de banimento.

Tarefas:
1. No bridge-node, substitua/instale as dependências:
   npm uninstall bot-web.js (se instalado)
   npm install node-telegram-bot-api bullmq ioredis
2. Crie bridge-node/src/telegram/bot.js:
   - Inicializa TelegramBot com TELEGRAM_TOKEN do .env no modo polling
   - Handler bot.on("message") que:
     a) Extrai: message_id, chat_id, user.id, user.first_name, text, date
     b) Identifica o tipo: texto, áudio (voice/audio), foto (photo), documento
     c) Para áudio: chama bot.getFileLink() e faz download para Buffer
     d) Para foto: pega a maior resolução (último item do array photo[])
     e) Monta payload e enfileira na fila "bot-ai" do BullMQ
     f) Log de cada mensagem recebida com tipo e user_id
3. Estrutura do payload na fila:
   { message_id, chat_id, user_id, user_name, type,
     text (se texto), audio_buffer (base64), image_buffer (base64),
     timestamp }
4. Crie bridge-node/src/telegram/sender.js:
   - Função sendMessage(chat_id, text) para responder
   - Função sendTyping(chat_id) para mostrar "digitando..."
   - Chama sendTyping antes de qualquer resposta
5. Atualize bridge-node/src/index.js para iniciar o bot e o responseWorker

TELEGRAM_TOKEN vem do .env. Obter em @BotFather no Telegram.
```

---

### 3.2 — Scan de inicialização (mensagens offline)

Quando o PC liga, o bot processa as mensagens que chegaram enquanto estava desligado.

```
Implemente o processamento de mensagens perdidas quando o bot reinicia.

Contexto: o Telegram entrega mensagens não processadas automaticamente
via getUpdates com offset. O objetivo é garantir que nenhuma mensagem
seja perdida ou processada duas vezes.

Tarefas:
1. Crie bridge-node/src/telegram/updatePoller.js:
   - Na inicialização, faz GET para api.telegram.org/getUpdates?offset=-1
     para verificar o último update_id processado
   - Compara com o último update_id salvo no Redis (chave "last_update_id")
   - Se houver updates pendentes, processa todos em ordem crescente de update_id
   - Salva o novo last_update_id no Redis após processar cada mensagem
2. Crie bridge-node/src/telegram/deduplication.js:
   - Função isAlreadyProcessed(message_id, user_id) que:
     a) Consulta o PostgreSQL: SELECT 1 FROM mensagens_processadas WHERE id = $1
     b) Usa a lib "postgres" (postgres.js): npm install postgres
     c) Retorna boolean
   - Função markAsProcessed(message_id, user_id, tipo)
3. No bot.js (handler de mensagens), adicione a verificação:
   if (await isAlreadyProcessed(message_id, user_id)) return;
   await markAsProcessed(message_id, user_id, tipo);
   // só então enfileira
4. No bridge-node/src/index.js, no evento de startup:
   - Chame o updatePoller antes de iniciar o polling normal
   - Log: "Verificando mensagens pendentes..."
5. Variáveis necessárias no .env: DATABASE_URL (para o bridge-node conectar ao postgres)

Use a lib "postgres" (postgres.js) para queries simples — mais leve que pg para o Node.
```

---

### 3.3 — Filtros de grupo e comandos

Configura em quais grupos o bot age e quais comandos especiais ele responde.

```
Implemente filtros de grupos e comandos Telegram no bridge-node.

Tarefas:
1. Crie bridge-node/src/telegram/filters.js com:
   - ALLOWED_GROUPS: lista de chat_ids permitidos (do .env: ALLOWED_GROUP_IDS)
     Formato .env: ALLOWED_GROUP_IDS=-1001234567890,-1009876543210
   - Função isAllowed(chat_id): retorna true se chat_id está na lista
     OU se a mensagem é de chat privado (chat_id > 0)
   - Em grupos: só processa se o bot for @mencionado OU se for um comando
   - Em chat privado: processa sempre
2. No bridge-node/src/telegram/commands.js, crie handlers para:
   /start  → "Olá [nome]! Sou sua secretária IA. Pode mandar texto, áudio ou foto."
   /limpar → Deleta memória do usuário no pgvector (via chamada ao brain-python)
   /status → Chama GET brain-python:8000/health e formata o resultado
   /ajuda  → Lista os comandos disponíveis
3. No handler principal do bot.js, adicione no início:
   if (!isAllowed(chat_id)) return; // ignora grupos não autorizados
   if (text?.startsWith("/")) { handleCommand(msg); return; }
4. Adicione ao .env:
   ALLOWED_GROUP_IDS=   (vazio = só chat privado)
   BOT_USERNAME=@seu_bot  (para detectar menções em grupos)
```

---

## Fase 4 — Cérebro Python — Processamento IA

### 4.1 — Worker Python: consumir a fila

O brain-python consome a fila do Redis, detecta o tipo de mensagem e roteia para o modelo certo.

```
Crie o worker principal do brain-python que consome mensagens do BullMQ.

Contexto: o bridge-node enfileira payloads na fila "bot-ai" do Redis.
O brain-python precisa consumir esses jobs e processá-los.

Tarefas:
1. Instale no brain-python: pip install aioredis
   No Python, a forma mais simples de consumir a fila BullMQ é via:
   BLPOP bull:bot-ai:wait 0  (bloqueante, pega o próximo job)
2. Crie brain-python/app/workers/message_worker.py:
   - Loop infinito async com aioredis BLPOP na fila "bull:bot-ai:wait"
   - Deserializa o JSON do job
   - Roteia por tipo:
     "text"  → chama process_text(payload)
     "audio" → chama process_audio(payload)
     "image" → chama process_image(payload)
   - Após processar, enfileira resposta em "bull:bot-ai-response:wait"
     com { chat_id, text: resposta_final }
   - Loga erros sem travar o loop (try/except com log)
3. Crie brain-python/app/processors/text_processor.py:
   - Busca contexto do usuário (context_service.get_context)
   - Monta messages: [system_prompt] + [contexto] + [mensagem atual]
   - Chama ollama_service.chat com as tools definidas
   - Se a resposta contiver tool_call: executa tool_runner.run_tool
   - Faz segunda chamada ao Ollama com o resultado da tool para formatar resposta
   - Salva resumo da conversa no pgvector via context_service.save_context
   - Retorna texto final da resposta
4. Inicie o worker junto com o FastAPI usando asyncio.create_task no startup
```

---

### 4.2 — Pipeline OCR: foto de conta → JSON

Lê uma foto de nota fiscal ou cupom e transforma em dados estruturados para o Spring Boot.

```
Implemente o pipeline de OCR para contas e notas fiscais no brain-python.

Fluxo: imagem (base64) → MiniCPM-V extrai texto → Llama 8B estrutura em JSON
       → registrar_gasto tool → Spring Boot.

Tarefas:
1. Crie brain-python/app/processors/image_processor.py:
   - Recebe payload com image_buffer (base64) e chat_id
   - Decodifica base64 para bytes
   - Chama ollama_service.vision(image_bytes, prompt_ocr)
   - prompt_ocr: "Extraia do cupom/nota fiscal: estabelecimento, valor total,
     data. Responda apenas com os dados encontrados, sem explicação."
   - Passa o texto extraído para o Llama 8B com prompt de estruturação
2. Crie brain-python/app/prompts/ocr_prompt.py com OCR_STRUCTURE_PROMPT:
   "Dado este texto extraído de um cupom fiscal, retorne APENAS um JSON válido
    sem markdown com os campos: estabelecimento (string), valor (number, use .
    como decimal), data (YYYY-MM-DD), categoria (uma de: Alimentação,
    Transporte, Saúde, Moradia, Lazer, Educação, Outros). Se um campo não
    for encontrado, use null. Texto: {texto_ocr}"
3. No image_processor.py, após receber o JSON do Llama:
   - Parse seguro: json.loads com fallback para None
   - Se valor for None: retorna "Não consegui identificar o valor.
     Pode me dizer quanto foi?"
   - Se JSON válido: chama tool registrar_gasto com os dados
   - Retorna mensagem de confirmação: "Anotei R$ X,XX em [categoria]
     ([estabelecimento]). Correto?"
4. Trate imagens que não são notas fiscais:
   - Se o MiniCPM-V não encontrar valores monetários no texto,
     chama o Llama para descrever a imagem normalmente
```

---

### 4.3 — Processador de áudio (Whisper)

Transcreve mensagens de voz e processa como texto normal.

```
Implemente o processador de áudio com Whisper no brain-python.

Tarefas:
1. Crie brain-python/app/processors/audio_processor.py:
   - Recebe payload com audio_buffer (base64)
   - Decodifica base64 para bytes
   - Salva temporariamente em /tmp/audio_{uuid}.ogg
   - Chama whisper_service.transcribe(caminho_arquivo)
   - Deleta o arquivo temp após transcrição
   - Se transcrição vazia/falha: retorna "Não consegui entender o áudio.
     Pode digitar sua mensagem?"
   - Se transcrição OK: passa o texto para o text_processor.process_text
   - Antes de retornar a resposta, prefixe com: "[🎤 Transcrição: {texto}]\n\n"
     para o usuário confirmar que foi entendido corretamente
2. Atualize brain-python/requirements.txt com:
   openai-whisper
   ffmpeg-python
3. No Dockerfile do brain-python, certifique-se que o ffmpeg está instalado:
   RUN apt-get update && apt-get install -y ffmpeg
4. O modelo Whisper deve ser carregado UMA vez no startup (não a cada requisição):
   - Em brain-python/app/main.py, no evento startup:
     app.state.whisper_model = whisper.load_model(config.WHISPER_MODEL)
   - O whisper_service.py deve usar app.state.whisper_model
```

---

## Fase 5 — Integração com Spring Boot

### 5.1 — Endpoints REST no Spring Boot

O Spring Boot gerencia os dados financeiros. O bot apenas chama sua API via HTTP.

```
Crie os endpoints REST no Spring Boot para integração com o bot Telegram.

Contexto: o Spring Boot já existe com JPA/Hibernate.
Idioma: Java 17+, Spring Boot 3.x, banco PostgreSQL compartilhado.

Tarefas:
1. Crie a entidade Gasto.java com os campos:
   id, estabelecimento, valor (BigDecimal), categoria, dataGasto (LocalDate),
   mensagemTelegramId, criadoEm (LocalDateTime)
2. Crie GastoRepository.java (JpaRepository<Gasto, Long>)
3. Crie GastoService.java com:
   - Método registrar(GastoDTO dto) que valida e salva
   - Validações: valor > 0, categoria na lista permitida, dataGasto não futura
4. Crie GastoController.java com:
   - POST /api/gastos → recebe GastoDTO, retorna GastoDTO com id gerado
   - GET /api/gastos?mes=YYYY-MM → lista gastos do mês agrupados por categoria
   - GET /api/gastos/resumo → total do mês atual por categoria
5. Crie OrcamentoController.java com:
   - GET /api/orcamentos?servico={servico} → busca orçamentos por nome
   - POST /api/orcamentos → cria novo orçamento (para popular manualmente)
6. Crie GastoDTO.java com: estabelecimento, valor, categoria, dataGasto,
   mensagemTelegramId

Os endpoints devem retornar JSON com status HTTP correto:
201 Created, 200 OK, 400 Bad Request, 500 Internal Server Error.
```

---

### 5.2 — Segurança: Spring Security + API Key

Protege os endpoints para que apenas o bot autenticado possa registrar gastos.

```
Configure a autenticação por API Key no Spring Boot.

Tarefas:
1. Adicione Spring Security ao pom.xml:
   spring-boot-starter-security
2. Crie ApiKeyAuthFilter.java (extends OncePerRequestFilter):
   - Lê o header "X-API-Key" de cada requisição
   - Compara com a variável de ambiente BOT_API_KEY
   - Se válido: seta SecurityContextHolder com autenticação
   - Se inválido: retorna 401 Unauthorized com JSON { "error": "Unauthorized" }
3. Crie SecurityConfig.java:
   - Desabilita CSRF (API REST)
   - Aplica ApiKeyAuthFilter antes do UsernamePasswordAuthenticationFilter
   - Libera: GET /actuator/health (sem auth)
   - Protege: tudo em /api/** (requer API Key)
4. No application.properties (ou application.yml):
   bot.api.key=${BOT_API_KEY}
5. Adicione BOT_API_KEY ao .env do projeto (gere um UUID: uuidgen)
6. Adicione ao docker-compose.yml no serviço spring-financeiro:
   environment:
     BOT_API_KEY: ${BOT_API_KEY}

Teste com curl:
curl -H "X-API-Key: sua-chave" http://localhost:8080/api/gastos
```

---

### 5.3 — Conectar Python → Spring Boot

O brain-python chama o Spring Boot para registrar gastos e consultar orçamentos.

```
Finalize a integração Python → Spring Boot no brain-python.

Tarefas:
1. Atualize brain-python/app/tools/financeiro_tool.py:
   - Use httpx (async) em vez de requests
   - Header obrigatório: { "X-API-Key": SPRING_API_KEY, "Content-Type": "application/json" }
   - Timeout de 10 segundos
   - Em caso de erro HTTP (4xx/5xx):
     * Log do erro com status code e body
     * Salva na tabela local "gastos" com enviado_spring=False
     * Retorna mensagem: "Anotei localmente. Sincronizarei com o sistema assim que possível."
2. Crie brain-python/app/tasks/sync_pending_gastos.py:
   - Roda a cada 30 minutos via APScheduler
   - Busca gastos com enviado_spring=False no PostgreSQL
   - Tenta reenviar cada um para o Spring Boot
   - Se sucesso: atualiza enviado_spring=True
   - Log de quantos foram sincronizados
3. Adicione httpx ao requirements.txt
4. Adicione ao .env:
   SPRING_API_URL=http://spring-financeiro:8080
   SPRING_API_KEY=mesmo-valor-do-BOT_API_KEY
5. Crie brain-python/app/tools/tests/test_financeiro_tool.py com:
   - Teste que mocka o Spring Boot com httpx Mock
   - Verifica que o gasto é salvo localmente se Spring falhar
```

---

## Fase 6 — Testes, Segurança & Ajustes Finais

### 6.1 — Teste do fluxo ponta a ponta

Valida o fluxo completo: mensagem no Telegram → Redis → Python → Spring → resposta.

```
Crie um script de teste ponta a ponta para validar o fluxo completo do bot.

Tarefas:
1. Crie scripts/test_e2e.sh que:
   a) Sobe todos os containers: docker-compose up -d
   b) Aguarda health checks de cada serviço (curl com retry)
   c) Simula um payload de texto na fila Redis diretamente:
      docker exec bot-redis redis-cli LPUSH bull:bot-ai:wait \
      '{"message_id":"test-001","chat_id":"123","type":"text",
      "text":"qual o meu gasto de alimentação este mês?","user_id":"123"}'
   d) Aguarda 10s e verifica se apareceu resposta na fila de resposta
   e) Testa o endpoint do Spring Boot:
      curl -X POST http://localhost:8080/api/gastos \
        -H "X-API-Key: $SPRING_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"estabelecimento":"Teste","valor":10.50,"categoria":"Alimentação"}'
   f) Verifica health de todos os serviços
   g) Imprime relatório: PASSOU / FALHOU para cada etapa
2. Crie scripts/test_ocr.py que:
   - Lê uma imagem de teste (crie uma imagem simples com texto de nota fiscal)
   - Chama diretamente o endpoint POST http://localhost:8000/process/image
   - Valida que retornou JSON com valor e categoria
3. Documente no README.md a seção "Testando o sistema" com os comandos
```

---

### 6.2 — Segurança: variáveis de ambiente e secrets

Garante que nenhuma chave sensível fica exposta no código ou no repositório.

```
Audite e corrija a gestão de segredos em todo o projeto.

Tarefas:
1. Crie/atualize o arquivo .env.example na raiz com TODAS as variáveis
   necessárias, com valores de exemplo (nunca valores reais):
   TELEGRAM_TOKEN=your-token-from-botfather
   POSTGRES_USER=botuser
   POSTGRES_PASSWORD=change-me-strong-password
   POSTGRES_DB=botbot
   DATABASE_URL=postgresql://botuser:change-me@postgres:5432/botbot
   REDIS_HOST=redis
   REDIS_PORT=6379
   AI_PROFILE=MED
   SPRING_API_URL=http://spring-financeiro:8080
   SPRING_API_KEY=generate-with-uuidgen
   BOT_API_KEY=same-as-spring-api-key
   ALLOWED_GROUP_IDS=
   BOT_USERNAME=@yourbotname
   MEMORY_TTL_DAYS=30
2. Verifique o .gitignore e certifique que contém:
   .env
   *.env
   !.env.example
   bridge-node/.wwebjs_auth/
   **/__pycache__/
   *.pyc
3. Faça grep -r "password\|secret\|token\|api_key" --include="*.py"
   --include="*.js" --include="*.ts" em todo o projeto.
   Reporte qualquer hardcode encontrado e corrija usando os.environ ou process.env
4. Adicione validação de variáveis obrigatórias:
   - brain-python/app/config.py: raise ValueError se TELEGRAM_TOKEN vazio
   - bridge-node/src/index.js: process.exit(1) com mensagem clara se token ausente
```

---

### 6.3 — Script de limpeza TTL + notificação

Remove memórias expiradas e avisa o usuário antes da limpeza.

```
Finalize e teste o sistema de expiração de memória com notificação ao usuário.

Tarefas:
1. Revise brain-python/app/tasks/cleanup_memory.py (criado na fase 2.4):
   - 48h ANTES de expirar, enfileira notificação prévia:
     "Oi! Em 2 dias vou arquivar nossas conversas antigas (>30 dias).
     Se quiser salvar algo importante, me diga agora!"
   - No dia da expiração, deleta e enfileira confirmação:
     "Pronto! Arquivei as conversas antigas. Pode continuar normalmente!"
2. Crie o endpoint POST /admin/cleanup no brain-python (sem auth de API Key,
   apenas acessível internamente) para forçar limpeza manual em testes
3. Adicione ao docker-compose.yml um healthcheck para o brain-python:
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
     interval: 30s
     timeout: 10s
     retries: 3
4. Adicione ao README.md a seção "Gerenciamento de memória" explicando:
   - Como mudar o TTL via MEMORY_TTL_DAYS
   - Como o usuário é notificado
   - Como forçar limpeza manual
```

---

### 6.4 — Autostart e monitoramento

Deixa o bot subindo automaticamente junto com o Docker ao ligar o PC.

```
Configure o autostart do bot e adicione monitoramento básico.

Contexto: Ubuntu Linux com Docker instalado.

Tarefas:
1. Garanta que todos os serviços no docker-compose.yml têm:
   restart: unless-stopped
2. Habilite o Docker para iniciar com o sistema:
   sudo systemctl enable docker
3. Crie um serviço systemd para subir o bot automaticamente.
   Arquivo: /etc/systemd/system/bot-telegram.service
   Conteúdo:
     [Unit]
     Description=Bot Telegram IA
     After=docker.service
     Requires=docker.service

     [Service]
     WorkingDirectory=/caminho/para/o/projeto
     ExecStart=/usr/bin/docker compose up
     ExecStop=/usr/bin/docker compose down
     Restart=on-failure

     [Install]
     WantedBy=multi-user.target

   Depois: sudo systemctl enable bot-telegram
4. Crie scripts/monitor.sh que exibe:
   - Status de cada container (docker ps)
   - Uso de VRAM da GPU (nvidia-smi --query-gpu=memory.used --format=csv)
   - Tamanho da fila Redis (redis-cli LLEN bull:bot-ai:wait)
   - Últimas 20 linhas de log de cada serviço
   - Health check de cada serviço
5. Adicione alias úteis ao README.md:
   alias bot-logs="docker-compose logs -f"
   alias bot-status="bash scripts/monitor.sh"
   alias bot-restart="docker-compose restart"
```

---

## Ordem de execução recomendada

| Passo | Etapa | O que entrega | Depende de |
|:---:|:---:|---|:---:|
| 1 | 1.1 | PostgreSQL + pgvector rodando | — |
| 2 | 1.2 | Filas BullMQ configuradas no Node | — |
| 3 | 1.3 | docker-compose.yml completo | 1.1, 1.2 |
| 4 | 2.1 | Ollama respondendo do container Python | Ollama no host |
| 5 | 2.2 | System prompt + context service | 1.1, 2.1 |
| 6 | 2.3 | Tool runner funcionando | 2.2 |
| 7 | 2.4 | Memória com TTL + limpeza | 1.1, 2.2 |
| 8 | 3.1 | Bot Telegram recebendo mensagens | 1.2 |
| 9 | 3.2 | Deduplicação + scan de inicialização | 1.1, 3.1 |
| 10 | 3.3 | Filtros de grupo e comandos | 3.1 |
| 11 | 4.1 | Worker Python processando fila | 2.1, 2.2, 2.3 |
| 12 | 4.2 | OCR de notas fiscais funcionando | 2.1, 4.1 |
| 13 | 4.3 | Transcrição de áudio | 2.1, 4.1 |
| 14 | 5.1 | Endpoints Spring Boot criados | — |
| 15 | 5.2 | Spring Boot protegido com API Key | 5.1 |
| 16 | 5.3 | Python → Spring integrado com fallback | 5.1, 5.2 |
| 17 | 6.1 | Teste E2E passando | tudo |
| 18 | 6.2 | Zero segredos no código | tudo |
| 19 | 6.3 | TTL + notificação ao usuário | 2.4 |
| 20 | 6.4 | Autostart no boot do Ubuntu | tudo |

---