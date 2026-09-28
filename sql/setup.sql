-- ═══════════════════════════════════════════════════════════════════════════
-- SN-2026 · GRUPO 01 · NASA NeoWs (Near Earth Object Web Service)
-- Projeto Supabase: NeoWs-DB
--
-- Cria a tabela principal (asteroides), a tabela de log (execucoes),
-- a constraint UNIQUE para upsert sem duplicatas, RLS e GRANTs.
-- Execute no SQL Editor do Supabase — seguro para reexecutar (idempotente).
-- ═══════════════════════════════════════════════════════════════════════════


-- ── 1. Tabela principal: asteroides ──────────────────────────────────────────
-- Cada linha é UMA aproximação de UM asteroide à Terra numa data.
-- O mesmo asteroide pode aparecer em datas diferentes — por isso a chave
-- natural combina o identificador do objeto com a data da aproximação.

CREATE TABLE IF NOT EXISTS asteroides (
    id                      bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Identificação do objeto
    neo_reference_id        text        NOT NULL,
    nome                    text        NOT NULL,
    designacao              text,
    nasa_jpl_url            text,

    -- Características físicas
    magnitude_absoluta      float8,
    diametro_min_m          float8,
    diametro_max_m          float8,
    diametro_medio_m        float8,
    potencialmente_perigoso boolean     NOT NULL DEFAULT false,
    objeto_sentry           boolean     NOT NULL DEFAULT false,

    -- Dados da aproximação
    data_aproximacao        date        NOT NULL,
    data_aproximacao_full   timestamptz,
    velocidade_kms          float8,
    velocidade_kmh          float8,
    distancia_km            float8,
    distancia_lunar         float8,   -- em distâncias lunares (1 LD ≈ 384.400 km)
    distancia_au            float8,
    corpo_orbitado          text,

    criado_em               timestamptz NOT NULL DEFAULT now()
);

-- Chave natural do registro: um asteroide só tem uma aproximação por data.
-- É o que permite o upsert idempotente do pipeline, sem gerar duplicatas.
ALTER TABLE asteroides DROP CONSTRAINT IF EXISTS asteroides_unique;
ALTER TABLE asteroides ADD CONSTRAINT asteroides_unique
    UNIQUE (neo_reference_id, data_aproximacao);

-- Índices para as consultas do painel
CREATE INDEX IF NOT EXISTS idx_ast_data      ON asteroides (data_aproximacao DESC);
CREATE INDEX IF NOT EXISTS idx_ast_perigoso  ON asteroides (potencialmente_perigoso);
CREATE INDEX IF NOT EXISTS idx_ast_distancia ON asteroides (distancia_lunar ASC);
CREATE INDEX IF NOT EXISTS idx_ast_nome      ON asteroides (nome);


-- ── 2. Tabela de log: execucoes ──────────────────────────────────────────────
-- Registra cada rodada do pipeline. O painel lê daqui a "última atualização".

CREATE TABLE IF NOT EXISTS execucoes (
    id                    bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    iniciado_em           timestamptz NOT NULL DEFAULT now(),
    concluido_em          timestamptz,

    periodo_inicio        date,
    periodo_fim           date,

    registros_processados integer     NOT NULL DEFAULT 0,
    lotes                 integer     NOT NULL DEFAULT 0,
    erros                 integer     NOT NULL DEFAULT 0,

    -- concluido | erro_parcial | erro_critico | sem_dados
    status                text        NOT NULL DEFAULT 'em_andamento',
    observacao            text
);

CREATE INDEX IF NOT EXISTS idx_exec_concluido ON execucoes (concluido_em DESC);


-- ── 3. RLS — Row Level Security ──────────────────────────────────────────────
-- Sobre as chaves do Supabase:
--   publishable key (anon): pode ficar no index.html. Não concede privilégio
--     administrativo — a segurança vem da combinação RLS + policies + GRANTs.
--   secret key (service_role): acesso total. Fica SOMENTE nos GitHub Secrets.
--     Nunca no index.html, em commits, prints ou mensagens.

ALTER TABLE asteroides ENABLE ROW LEVEL SECURITY;
ALTER TABLE execucoes  ENABLE ROW LEVEL SECURITY;

-- Políticas: leitura pública, escrita restrita ao service_role
DROP POLICY IF EXISTS "leitura publica asteroides" ON asteroides;
CREATE POLICY "leitura publica asteroides"
    ON asteroides FOR SELECT USING (true);

DROP POLICY IF EXISTS "leitura publica execucoes" ON execucoes;
CREATE POLICY "leitura publica execucoes"
    ON execucoes FOR SELECT USING (true);

-- Sem políticas de INSERT/UPDATE/DELETE: apenas o service_role escreve,
-- porque ele ignora RLS por definição.


-- ── 4. GRANTs explícitos ─────────────────────────────────────────────────────
-- O RLS filtra linhas; o GRANT define o que cada role pode fazer na tabela.
-- Sem GRANT explícito, projetos novos do Supabase podem negar o acesso mesmo
-- com a policy correta.

GRANT SELECT ON TABLE asteroides TO anon;
GRANT SELECT ON TABLE execucoes  TO anon;

GRANT SELECT ON TABLE asteroides TO authenticated;
GRANT SELECT ON TABLE execucoes  TO authenticated;

GRANT ALL ON TABLE asteroides TO service_role;
GRANT ALL ON TABLE execucoes  TO service_role;

-- Necessário para INSERT em colunas GENERATED ALWAYS AS IDENTITY
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;


-- ── 5. View auxiliar: aproximações mais próximas ─────────────────────────────
-- Usada pelo painel para destacar os objetos que mais se aproximaram.

CREATE OR REPLACE VIEW asteroides_proximos AS
SELECT
    neo_reference_id,
    nome,
    data_aproximacao,
    diametro_medio_m,
    velocidade_kms,
    distancia_km,
    distancia_lunar,
    potencialmente_perigoso
FROM asteroides
ORDER BY distancia_lunar ASC;

GRANT SELECT ON TABLE asteroides_proximos TO anon;
GRANT SELECT ON TABLE asteroides_proximos TO authenticated;


-- ── 6. Verificação final ─────────────────────────────────────────────────────
SELECT tablename AS tabela,
       rowsecurity AS rls_ativo
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('asteroides', 'execucoes')
ORDER BY tablename;
-- Esperado: as duas tabelas com rls_ativo = true

SELECT conname AS constraint_name, contype AS tipo
FROM pg_constraint
WHERE conrelid = 'asteroides'::regclass
  AND conname = 'asteroides_unique';
-- Esperado: asteroides_unique | u  (u = UNIQUE)
