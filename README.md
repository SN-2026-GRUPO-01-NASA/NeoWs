# NeoWs — Pipeline de aproximações de asteroides

Projeto da **Atividade Avaliativa do 3º Trimestre** de Serviços em Nuvem (SN-2026).
Coleta automatizada de dados da API **NeoWs** (Near Earth Object Web Service) da
NASA, armazenamento em PostgreSQL no Supabase e publicação de um painel web no
GitHub Pages.

| | |
|---|---|
| **Grupo** | 01 |
| **Integrantes** | João Vitor Cosmo · Maria Laura Schossler |
| **API** | NASA NeoWs — `api.nasa.gov/neo/rest/v1/feed` |
| **Organização** | [SN-2026-GRUPO-01-NASA](https://github.com/SN-2026-GRUPO-01-NASA) |
| **Repositório** | [NeoWs](https://github.com/SN-2026-GRUPO-01-NASA/NeoWs) |
| **Painel publicado** | https://sn-2026-grupo-01-nasa.github.io/NeoWs/ |
| **Projeto Supabase** | NeoWs-DB (South America — São Paulo) |

---

## Sobre a API

A **NeoWs** é um serviço REST mantido pelo time de Asteroides do NASA JPL que
expõe informações sobre objetos próximos à Terra (*Near Earth Objects*).

O endpoint usado neste projeto é o **`/feed`**, que retorna as aproximações
à Terra dentro de um intervalo de datas:

```
https://api.nasa.gov/neo/rest/v1/feed?start_date=2026-11-13&end_date=2026-11-19&api_key=SUA_CHAVE
```

Particularidades que moldaram o pipeline:

- **Janela máxima de 7 dias** por requisição. O script limita a janela a esse
  intervalo automaticamente.
- **A resposta vem agrupada por data**, não como uma lista plana:
  `near_earth_objects` é um objeto cujas chaves são datas, e cada uma contém
  um array de asteroides. O script achata essa estrutura.
- **Um asteroide pode ter várias aproximações.** No modo feed a API já filtra
  as aproximações da data consultada, mas o script confere a data de cada
  entrada de `close_approach_data` antes de gravar.
- **Exige chave** gratuita obtida em [api.nasa.gov](https://api.nasa.gov/).
  A `DEMO_KEY` existe, mas tem limite baixo de requisições por hora e não é
  usada aqui.

### Dados coletados

Para cada aproximação são gravados: identificação do objeto (`neo_reference_id`,
nome, designação, link do JPL), características físicas (magnitude absoluta,
diâmetro estimado mínimo e máximo, classificação de risco, flag Sentry) e os
dados da passagem (data, velocidade relativa, distância mínima em km, em
distâncias lunares e em unidades astronômicas, corpo orbitado).

---

## Arquitetura

```
        NASA NeoWs (api.nasa.gov)
                  │
                  │  GET /feed?start_date&end_date
                  ▼
     GitHub Actions  ·  update-data.yml
     cron diário 09h UTC + execução manual
                  │
                  │  scripts/fetch_nasa.py
                  │  achata → normaliza → deduplica → upsert em lotes
                  ▼
        Supabase  ·  NeoWs-DB (PostgreSQL)
        ├── asteroides   (dados da API, UNIQUE + RLS)
        └── execucoes    (log de cada rodada)
                  │
                  │  API REST automática + publishable key (anon)
                  ▼
        GitHub Pages  ·  index.html
        régua de proximidade + filtros + tabela
```

**Chave de deduplicação:** `(neo_reference_id, data_aproximacao)`

Um asteroide tem no máximo uma aproximação registrada por data. Essa é a chave
natural do registro e a constraint `UNIQUE` que permite o `upsert` idempotente —
rodar o pipeline duas vezes no mesmo período atualiza as linhas em vez de
duplicá-las.

---

## Estrutura do repositório

```
NeoWs/
├── index.html                      painel publicado no GitHub Pages
├── README.md
├── scripts/
│   └── fetch_nasa.py               coleta, deduplicação e upsert
├── sql/
│   └── setup.sql                   tabelas, constraint, RLS e GRANTs
├── .github/workflows/
│   └── update-data.yml             agendamento do pipeline
└── docs/
    ├── tutorial.pdf                guia de replicação do projeto
    ├── ai-interaction.md           histórico de prompts com a IA
    ├── reflexao.md                 análise crítica do uso de IA
    └── apresentacao.pdf            slides do seminário
```

---

## Divisão de responsabilidades

| Área | Responsável |
|---|---|
| Pipeline de coleta (`fetch_nasa.py`, workflow) | João Vitor Cosmo |
| Banco de dados (`setup.sql`, modelagem, RLS) | João Vitor Cosmo |
| Painel web (`index.html`, filtros, visualização) | Maria Laura Schossler |
| Documentação (README, tutorial, apresentação) | Maria Laura Schossler |

> Ajustem esta tabela conforme a divisão real do grupo antes da entrega.

**Uso de IA generativa:** o grupo utilizou a trilha de IA generativa descrita no
Guia de Ambiente de Desenvolvimento Integrado. O histórico completo de prompts
está em [`docs/ai-interaction.md`](docs/ai-interaction.md) e a análise crítica
em [`docs/reflexao.md`](docs/reflexao.md).

---

## Como configurar

### 1. Chave da NASA

Gere a chave gratuita em [api.nasa.gov](https://api.nasa.gov/) (*Generate API Key*).
Ela chega por e-mail em segundos.

### 2. Supabase

1. Crie a organização **SN-2026-GRUPO-01-NASA** e o projeto **NeoWs-DB**,
   região *South America (São Paulo)*.
2. No **SQL Editor**, execute todo o conteúdo de [`sql/setup.sql`](sql/setup.sql).
   O script é idempotente — pode ser reexecutado sem perder dados.
3. Confirme ao final que as duas tabelas aparecem com `rls_ativo = true`.
4. Em **Settings → Team**, convide `rafael.ferques@ifpr.edu.br` como *Developer*.
5. Em **Settings → API**, anote a *Project URL*, a *publishable key* (anon) e a
   *secret key* (service_role).

### 3. GitHub

Em **Settings → Secrets and variables → Actions**, crie três *Secrets*:

| Secret | Valor |
|---|---|
| `SUPABASE_URL` | a Project URL do Supabase |
| `SUPABASE_SERVICE_KEY` | a *secret key* (service_role) |
| `NASA_API_KEY` | a chave obtida em api.nasa.gov |

Em **Settings → Pages**, ative o site: *Deploy from a branch*, branch `main`,
pasta `/ (root)`.

### 4. Painel

Edite as duas constantes no início do bloco `<script>` do `index.html`:

```js
const SUPABASE_URL      = "https://SEU-PROJETO.supabase.co";
const SUPABASE_ANON_KEY = "sua_publishable_key";
```

> A **publishable key (anon)** pode ficar no `index.html`: ela não concede
> privilégio administrativo, e a segurança vem da combinação de RLS, policies
> e GRANTs — o role `anon` só tem `SELECT`.
>
> A **secret key (service_role)** nunca pode aparecer no `index.html`, em
> commits, prints ou mensagens. Se for exposta, regenere imediatamente no
> painel do Supabase.

### 5. Executar o pipeline

Aba **Actions** → *Pipeline NeoWs → Supabase* → **Run workflow**.

Os campos opcionais permitem escolher a data inicial e o tamanho da janela
(1 a 7 dias). Deixando em branco, o pipeline coleta os próximos 7 dias a
partir de hoje.

---

## Painel

O `index.html` consome a API REST do Supabase e apresenta:

- **Régua de proximidade** — cada aproximação plotada em escala logarítmica de
  distâncias lunares, com a órbita da Lua marcada em 1 LD. Triângulos são
  objetos potencialmente perigosos, círculos são os demais (a forma diferencia
  além da cor, para não depender só dela).
- **Filtros** — período (data inicial e final), busca por nome, recorte apenas
  de potencialmente perigosos e quatro critérios de ordenação.
- **Números do recorte** — total de aproximações, quantos são potencialmente
  perigosos, passagem mais próxima, maior velocidade e maior diâmetro.
- **Tabela** — uma linha por aproximação, com link para a ficha do objeto no
  NASA JPL.
- **Última coleta** — data, status e volume da execução mais recente, lidos da
  tabela `execucoes`.

Todo valor vindo do banco passa por `escapeHtml()` antes de ser inserido no HTML.

---

## Testando a API REST do Supabase

Cole no navegador, substituindo a URL e a chave:

```
https://SEU-PROJETO.supabase.co/rest/v1/asteroides?select=*&order=distancia_lunar.asc&limit=10&apikey=SUA_PUBLISHABLE_KEY
```

Deve retornar um array JSON com as aproximações mais próximas.
