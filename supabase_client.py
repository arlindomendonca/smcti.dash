"""
supabase_client.py — Integração com o Supabase
REST API do Supabase via requests (sem SDK extra).
Upserts são idempotentes: chave única uuid/id — seguro rodar N vezes.
"""
import requests
import streamlit as st


# ── Conexão ──────────────────────────────────────────────────────────────────

def _sb_url() -> str:
    return st.secrets["supabase"]["url"].rstrip("/")


def _sb_key() -> str:
    return st.secrets["supabase"]["service_key"]


def _headers(extra_prefer: str = "") -> dict:
    """
    Headers obrigatórios para a REST API do Supabase.
    O Prefer para upsert deve ser exatamente:
      'resolution=merge-duplicates'   (sem 'return=minimal' junto)
    """
    prefer = "resolution=merge-duplicates"
    if extra_prefer:
        prefer = extra_prefer
    return {
        "apikey":        _sb_key(),
        "Authorization": f"Bearer {_sb_key()}",
        "Content-Type":  "application/json",
        "Prefer":        prefer,
    }


def _read_headers() -> dict:
    return {
        "apikey":        _sb_key(),
        "Authorization": f"Bearer {_sb_key()}",
        "Content-Type":  "application/json",
    }


def testar_conexao() -> tuple[bool, str]:
    """
    Testa se a service_key consegue ler a tabela atendimento.
    Retorna (ok, mensagem).
    """
    try:
        url = f"{_sb_url()}/rest/v1/atendimento"
        r = requests.get(
            url,
            headers=_read_headers(),
            params={"select": "id", "limit": "1"},
            timeout=10,
        )
        if r.status_code == 401:
            return False, (
                "Erro 401 — chave inválida ou sem permissão. "
                "Verifique se está usando a **service_role key** "
                "(Project Settings → API → service_role), não a anon key."
            )
        if r.status_code == 404:
            return False, "Erro 404 — URL do Supabase incorreta ou tabela não existe."
        r.raise_for_status()
        return True, "Conexão OK"
    except requests.exceptions.ConnectionError:
        return False, "Erro de conexão — verifique a URL do Supabase nos secrets."
    except Exception as e:
        return False, str(e)


def _upsert(table: str, payload: list[dict], on_conflict: str) -> None:
    """
    Upsert em lote.
    on_conflict: nome da coluna que é chave única (ex: 'uuid' ou 'id').
    """
    if not payload:
        return
    url = f"{_sb_url()}/rest/v1/{table}"
    r = requests.post(
        url,
        json=payload,
        headers=_headers(),
        params={"on_conflict": on_conflict},
        timeout=30,
    )
    if not r.ok:
        raise Exception(f"Supabase [{table}] {r.status_code}: {r.text[:300]}")


# ── IDs já importados ─────────────────────────────────────────────────────────

def get_ids_importados() -> set[int]:
    """Retorna todos os IDs de atendimentos já gravados no Supabase."""
    todos: set[int] = set()
    limit = 1000
    offset = 0

    while True:
        url = f"{_sb_url()}/rest/v1/atendimento"
        r = requests.get(
            url,
            headers=_read_headers(),
            params={"select": "id", "limit": str(limit), "offset": str(offset)},
            timeout=15,
        )
        if not r.ok:
            break
        rows = r.json()
        if not rows:
            break
        todos.update(row["id"] for row in rows)
        if len(rows) < limit:
            break
        offset += limit

    return todos


# ── Upserts individuais ───────────────────────────────────────────────────────

def upsert_departamento(sector: dict) -> None:
    if not sector or not sector.get("uuid"):
        return
    _upsert("departamento", [{
        "uuid":    sector["uuid"],
        "name":    sector.get("name", ""),
        "acronym": sector.get("acronym"),
    }], "uuid")


def upsert_atendente(agent: dict) -> None:
    if not agent or not agent.get("uuid"):
        return
    _upsert("atendente", [{
        "uuid":           agent["uuid"],
        "name":           agent.get("name", ""),
        "email":          agent.get("email"),
        "api_created_at": agent.get("created_at"),
    }], "uuid")


def upsert_atendimento(chat: dict) -> None:
    _upsert("atendimento", [{
        "id":                chat["id"],
        "recipient":         chat.get("recipient", ""),
        "started_at":        chat.get("started_at"),
        "finished_at":       chat.get("finished_at"),
        "rating":            chat.get("rating"),
        "atendente_uuid":    (chat.get("agent") or {}).get("uuid"),
        "departamento_uuid": (chat.get("sector") or {}).get("uuid"),
    }], "id")


def upsert_mensagens(atendimento_id: int, mensagens: list[dict]) -> None:
    payload = [{
        "uuid":                     m["uuid"],
        "atendimento_id":           atendimento_id,
        "channel":                  m.get("channel"),
        "recipient":                m.get("recipient"),
        "body":                     m.get("body"),
        "attachment":               m.get("attachment"),
        "sent_at":                  m.get("sent_at"),
        "read_at":                  m.get("read_at"),
        "send_status":              m.get("send_status"),
        "send_status_confirmation": m.get("send_status_confirmation"),
    } for m in mensagens if m.get("uuid")]
    _upsert("mensagem", payload, "uuid")


# ── Leitura para o dashboard ──────────────────────────────────────────────────

def _get_all(table_or_view: str, params: dict | None = None) -> list[dict]:
    """Leitura paginada (lotes de 1000) de tabela ou view."""
    params = dict(params or {})
    todos: list[dict] = []
    limit = 1000
    offset = 0

    while True:
        p = {**params, "limit": str(limit), "offset": str(offset)}
        r = requests.get(
            f"{_sb_url()}/rest/v1/{table_or_view}",
            headers=_read_headers(),
            params=p,
            timeout=30,
        )
        if not r.ok:
            raise Exception(f"Supabase GET {table_or_view} {r.status_code}: {r.text[:200]}")
        rows = r.json()
        if not rows:
            break
        todos.extend(rows)
        if len(rows) < limit:
            break
        offset += limit

    return todos


def get_atendimentos_enriquecidos(
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> list[dict]:
    """
    Lê a view vw_atendimento_enriquecido.
    Datas em formato 'YYYY-MM-DD' (filtro no campo started_at).
    """
    # PostgREST: para filtros de comparação, a chave é o nome da coluna
    # e o valor começa com o operador: 'gte.2026-01-01'
    base_params: dict = {
        "select": "*",
        "order":  "started_at.desc",
    }
    if data_inicio:
        base_params["started_at"] = f"gte.{data_inicio}"
    if data_fim:
        # Como não pode haver duas chaves 'started_at' em um dict,
        # usamos 'and' para combinar filtros na mesma coluna
        if data_inicio:
            base_params.pop("started_at")
            base_params["and"] = f"(started_at.gte.{data_inicio},started_at.lte.{data_fim}T23:59:59)"
        else:
            base_params["started_at"] = f"lte.{data_fim}T23:59:59"

    url = f"{_sb_url()}/rest/v1/vw_atendimento_enriquecido"

    todos: list[dict] = []
    limit = 1000
    offset = 0
    while True:
        params = {**base_params, "limit": str(limit), "offset": str(offset)}
        r = requests.get(url, headers=_read_headers(), params=params, timeout=30)
        if not r.ok:
            raise Exception(
                f"Supabase view {r.status_code}: {r.text[:400]} | URL={r.url}"
            )
        rows = r.json()
        if not rows:
            break
        todos.extend(rows)
        if len(rows) < limit:
            break
        offset += limit
    return todos
