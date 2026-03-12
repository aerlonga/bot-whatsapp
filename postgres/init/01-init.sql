-- Habilita extensão pgvector para embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
-- Tabela: contatos
-- Armazena os usuários/contatos do Telegram
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contatos (
    id          SERIAL PRIMARY KEY,
    telefone_telegram TEXT NOT NULL UNIQUE,
    nome        TEXT,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- Tabela: memoria_vetorial
-- Armazena embeddings das conversas para busca semântica
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS memoria_vetorial (
    id          SERIAL PRIMARY KEY,
    contato_id  INTEGER NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
    conteudo    TEXT NOT NULL,
    embedding   vector(384) NOT NULL,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expira_em   TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days')
);

-- Índice IVFFlat para busca por similaridade de cosseno
CREATE INDEX IF NOT EXISTS idx_memoria_vetorial_embedding
    ON memoria_vetorial
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ------------------------------------------------------------
-- Tabela: mensagens_processadas
-- Garante idempotência no processamento de mensagens
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mensagens_processadas (
    id            VARCHAR PRIMARY KEY,   -- message_id vindo do Telegram
    contato_id    INTEGER REFERENCES contatos(id) ON DELETE SET NULL,
    tipo          VARCHAR(50),
    status        VARCHAR(50),
    processado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- Tabela: gastos
-- Registros financeiros extraídos das mensagens
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gastos (
    id             SERIAL PRIMARY KEY,
    contato_id     INTEGER REFERENCES contatos(id) ON DELETE SET NULL,
    estabelecimento TEXT,
    valor          NUMERIC(12, 2),
    categoria      TEXT,
    data_gasto     DATE,
    mensagem_id    VARCHAR REFERENCES mensagens_processadas(id) ON DELETE SET NULL,
    enviado_spring BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- Tabela: orcamentos
-- Tabela de referência com faixas de preço por serviço
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orcamentos (
    id          SERIAL PRIMARY KEY,
    servico     TEXT NOT NULL,
    valor_min   NUMERIC(12, 2),
    valor_max   NUMERIC(12, 2),
    descricao   TEXT,
    ativo       BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
