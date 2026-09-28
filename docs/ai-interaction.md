
# Histórico de Interação com IA

> Registro dos prompts utilizados no desenvolvimento do projeto, incluindo os
> que não funcionaram de primeira. Documento obrigatório da avaliação.

---

## Informações gerais

| **Campo** | **Valor** |
|---|---|
| **Grupo** | 01 |
| **Integrantes** | João Vitor Cosmo, Maria Laura Schossler |
| **API NASA escolhida** | NeoWs — Near Earth Object Web Service |
| **IA utilizada** | Claude (Anthropic) |
| **Data de início** | 28-09-2026 |
| **Data de conclusão** | 28-09-2026 |

---

## Interação 1 — Leitura do enunciado e planejamento do projeto

**Data:** 28-09-2026
**Objetivo:** Entender os requisitos da atividade e definir a estrutura completa
do projeto antes de escrever qualquer código.

**Prompt enviado à IA:**

```
[Anexados: Atividade_Avaliativa_3_Trim.docx, ai-interaction_md.docx,
print da planilha de reserva]

oi novo trabalho

leia e se prepare
```

**Resumo da resposta:**
A IA leu os dois documentos, identificou que o Grupo 01 ficou com a API NeoWs e
levantou as particularidades do endpoint `/feed` antes de propor código: janela
máxima de 7 dias por requisição, resposta agrupada por data em vez de lista
plana, e exigência de chave. Em seguida gerou a estrutura completa do
repositório — `sql/setup.sql`, `scripts/fetch_nasa.py`,
`.github/workflows/update-data.yml`, `index.html` e `README.md`.

**O que funcionou:**
A identificação das particularidades da API antes de escrever o script evitou
retrabalho. A definição da chave natural `(neo_reference_id, data_aproximacao)`
partiu da observação de que o mesmo asteroide aparece em datas diferentes.

**O que precisou ajuste:**
*(preencher conforme o grupo revisar os arquivos — por exemplo nomes de colunas,
frequência do cron ou campos adicionais no painel)*

---
**Avaliação geral do uso da IA:** *(até 10 linhas)*
Só teve essa interação com o claude.
