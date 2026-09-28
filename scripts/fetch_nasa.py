"""
fetch_nasa.py — Pipeline NASA NeoWs → Supabase
SN-2026 · Grupo 01 · Near Earth Object Web Service

Consulta o endpoint /feed da API NeoWs, normaliza cada aproximação de
asteroide à Terra e envia os registros ao Supabase em lotes, com upsert.

Fluxo:
  1. Monta a janela de datas (a API aceita no máximo 7 dias por requisição)
  2. Consulta api.nasa.gov/neo/rest/v1/feed
  3. Achata a resposta (near_earth_objects vem agrupado por data)
  4. Deduplica pela chave natural antes do envio — evita o erro PostgreSQL
     21000 "ON CONFLICT DO UPDATE command cannot affect row a second time"
  5. Faz upsert em lotes na tabela asteroides
  6. Registra a execução na tabela execucoes
  7. Encerra com sys.exit(1) se algum lote falhar, para o Actions marcar erro

Variáveis de ambiente (GitHub Secrets):
  SUPABASE_URL          → URL do projeto (https://XXXX.supabase.co)
  SUPABASE_SERVICE_KEY  → service_role key (acesso total, só no servidor)
  NASA_API_KEY          → chave gratuita obtida em api.nasa.gov

Variáveis de ambiente (GitHub Variables, opcionais):
  DIAS_JANELA           → tamanho da janela em dias (padrão 7, máximo 7)
  DATA_INICIO           → data inicial YYYY-MM-DD (padrão: hoje)
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from supabase import create_client

# ── Credenciais ───────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
NASA_API_KEY = os.environ.get("NASA_API_KEY", "").strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERRO CRITICO] SUPABASE_URL e SUPABASE_SERVICE_KEY sao obrigatorios.")
    print("               Configure-os como GitHub Secrets no repositorio.")
    sys.exit(1)

if not NASA_API_KEY:
    print("[ERRO CRITICO] NASA_API_KEY e obrigatoria para o endpoint NeoWs.")
    print("               Obtenha a chave gratuita em https://api.nasa.gov/")
    sys.exit(1)

db = create_client(SUPABASE_URL, SUPABASE_KEY)
print(f"Supabase conectado: {SUPABASE_URL}")

# ── Configuracoes ─────────────────────────────────────────────────────────────

API_URL = "https://api.nasa.gov/neo/rest/v1/feed"
LOTE = 500                      # registros por requisicao ao Supabase
DIST_LUNAR_KM = 384_400.0       # 1 LD — distancia media Terra-Lua

BRT = timezone(timedelta(hours=-3))
hoje = datetime.now(BRT).date()

# A API NeoWs aceita no maximo 7 dias entre start_date e end_date
dias = int(os.environ.get("DIAS_JANELA", "7"))
dias = max(1, min(dias, 7))

if os.environ.get("DATA_INICIO", "").strip():
    data_inicio = datetime.strptime(os.environ["DATA_INICIO"].strip(), "%Y-%m-%d").date()
else:
    data_inicio = hoje

data_fim = data_inicio + timedelta(days=dias - 1)

print(f"Janela consultada: {data_inicio} a {data_fim} ({dias} dia(s))")


# ── Funcoes auxiliares ────────────────────────────────────────────────────────

def num(valor):
    """Converte string/None para float, devolvendo None quando nao der."""
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def parse_epoch(ms):
    """Converte epoch em milissegundos para ISO 8601 com timezone UTC."""
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def buscar_feed() -> dict:
    """Consulta o endpoint /feed da NeoWs para a janela configurada."""
    params = {
        "start_date": data_inicio.isoformat(),
        "end_date": data_fim.isoformat(),
        "api_key": NASA_API_KEY,
    }
    # A chave nao aparece no log — mostramos a URL sem o api_key
    print(f"\nGET {API_URL}?start_date={params['start_date']}"
          f"&end_date={params['end_date']}&api_key=***")
    try:
        r = requests.get(API_URL, params=params, timeout=60)
        if r.status_code == 429:
            print("  [ERRO] Limite de requisicoes da NASA atingido (HTTP 429).")
            print("         Aguarde a renovacao horaria ou verifique a chave.")
            return {}
        r.raise_for_status()
        dados = r.json()
        total = dados.get("element_count", 0)
        print(f"  element_count informado pela API: {total}")
        return dados
    except Exception as e:
        print(f"  [ERRO] Falha ao consultar a NeoWs: {e}")
        return {}


def normalizar(neo: dict, aprox: dict, data_ref: str) -> dict:
    """Achata um asteroide + uma aproximacao numa linha da tabela."""
    diam = (neo.get("estimated_diameter") or {}).get("meters") or {}
    d_min = num(diam.get("estimated_diameter_min"))
    d_max = num(diam.get("estimated_diameter_max"))
    d_med = round((d_min + d_max) / 2, 3) if d_min is not None and d_max is not None else None

    vel = aprox.get("relative_velocity") or {}
    dist = aprox.get("miss_distance") or {}
    dist_km = num(dist.get("kilometers"))

    return {
        "neo_reference_id":        (neo.get("neo_reference_id") or neo.get("id") or "").strip(),
        "nome":                    (neo.get("name") or "").strip(),
        "designacao":              (neo.get("designation") or "").strip() or None,
        "nasa_jpl_url":            neo.get("nasa_jpl_url"),

        "magnitude_absoluta":      num(neo.get("absolute_magnitude_h")),
        "diametro_min_m":          d_min,
        "diametro_max_m":          d_max,
        "diametro_medio_m":        d_med,
        "potencialmente_perigoso": bool(neo.get("is_potentially_hazardous_asteroid")),
        "objeto_sentry":           bool(neo.get("is_sentry_object")),

        "data_aproximacao":        data_ref,
        "data_aproximacao_full":   parse_epoch(aprox.get("epoch_date_close_approach")),
        "velocidade_kms":          num(vel.get("kilometers_per_second")),
        "velocidade_kmh":          num(vel.get("kilometers_per_hour")),
        "distancia_km":            dist_km,
        "distancia_lunar":         num(dist.get("lunar")),
        "distancia_au":            num(dist.get("astronomical")),
        "corpo_orbitado":          (aprox.get("orbiting_body") or "").strip() or None,
    }


def deduplicar(lista: list) -> list:
    """
    Remove duplicatas internas antes do upsert.

    O PostgreSQL nao permite que um unico comando ON CONFLICT DO UPDATE
    afete a mesma linha duas vezes (erro 21000). Se o mesmo par
    (neo_reference_id, data_aproximacao) aparecer mais de uma vez no lote,
    o envio falha inteiro — por isso limpamos antes.
    """
    vistos = set()
    resultado = []
    for r in lista:
        chave = (r.get("neo_reference_id"), r.get("data_aproximacao"))
        if chave not in vistos:
            vistos.add(chave)
            resultado.append(r)
    return resultado


def registrar_execucao(processados: int, lotes: int, erros: int,
                       status: str, obs: str = "") -> None:
    """Grava o log da rodada na tabela execucoes."""
    try:
        db.table("execucoes").insert({
            "concluido_em":          datetime.now(timezone.utc).isoformat(),
            "periodo_inicio":        data_inicio.isoformat(),
            "periodo_fim":           data_fim.isoformat(),
            "registros_processados": processados,
            "lotes":                 lotes,
            "erros":                 erros,
            "status":                status,
            "observacao":            obs or None,
        }).execute()
        print(f"\n  Log de execucao salvo — status: {status}")
    except Exception as e:
        print(f"  [AVISO] Nao foi possivel salvar o log de execucao: {e}")


# ── Execucao principal ────────────────────────────────────────────────────────

feed = buscar_feed()

if not feed:
    print("\n[ERRO] A API NeoWs nao retornou dados para a janela solicitada.")
    registrar_execucao(0, 0, 1, "erro_critico",
                       "Falha na consulta a API NeoWs.")
    sys.exit(1)

# near_earth_objects vem como um dicionario agrupado por data:
#   { "2026-11-13": [ {...}, {...} ], "2026-11-14": [ ... ] }
por_data = feed.get("near_earth_objects") or {}

registros = []
for data_ref, lista_neos in por_data.items():
    for neo in lista_neos:
        aproximacoes = neo.get("close_approach_data") or []
        # No modo feed, a API ja filtra as aproximacoes da data consultada.
        # Mantemos so as que batem com a data do agrupamento, por seguranca.
        for aprox in aproximacoes:
            if aprox.get("close_approach_date") != data_ref:
                continue
            linha = normalizar(neo, aprox, data_ref)
            if not linha["neo_reference_id"] or not linha["nome"]:
                continue
            registros.append(linha)

print(f"\nRegistros achatados a partir do feed: {len(registros)}")

if not registros:
    print("[AVISO] Nenhuma aproximacao encontrada na janela consultada.")
    registrar_execucao(0, 0, 0, "sem_dados",
                       f"Janela {data_inicio} a {data_fim} sem aproximacoes.")
    sys.exit(0)

# Deduplicacao antes do upsert
antes = len(registros)
registros = deduplicar(registros)
removidos = antes - len(registros)
if removidos:
    print(f"  Deduplicacao: {removidos} registro(s) duplicado(s) removido(s)")
print(f"  Chave natural do upsert: (neo_reference_id, data_aproximacao)")

# Envio em lotes ao Supabase
total_processados = 0
total_lotes = 0
total_erros = 0
qtd_lotes = (len(registros) + LOTE - 1) // LOTE

for i in range(0, len(registros), LOTE):
    lote = registros[i:i + LOTE]
    n = i // LOTE + 1
    try:
        db.table("asteroides").upsert(
            lote,
            on_conflict="neo_reference_id,data_aproximacao",
        ).execute()
        total_processados += len(lote)
        total_lotes += 1
        print(f"  Lote {n}/{qtd_lotes}: {len(lote)} registros enviados")
    except Exception as e:
        total_erros += 1
        print(f"  [ERRO] Lote {n}/{qtd_lotes} falhou: {e}")

# Status final
if total_erros == 0:
    status_final = "concluido"
elif total_processados > 0:
    status_final = "erro_parcial"
else:
    status_final = "erro_critico"

perigosos = sum(1 for r in registros if r["potencialmente_perigoso"])
obs = (f"Janela: {data_inicio} a {data_fim} | "
       f"Processados: {total_processados} | Lotes: {total_lotes} | "
       f"Erros: {total_erros} | Potencialmente perigosos: {perigosos}")

registrar_execucao(total_processados, total_lotes, total_erros,
                   status_final, obs)

print(f"\nConcluido — {total_processados} registros enviados em {total_lotes} lote(s).")
print(f"Asteroides potencialmente perigosos na janela: {perigosos}")

# Falha parcial derruba o workflow, para o erro ficar visivel no Actions
if total_erros > 0:
    print(f"\n[ATENCAO] {total_erros} lote(s) com erro — workflow encerrado com falha.")
    sys.exit(1)
