"""
supabase_client.py — Integração com o Supabase
REST API do Supabase via requests (sem SDK extra).
Upserts são idempotentes: chave única uuid/id — seguro rodar N vezes.
"""
import requests
import streamlit as st


# ── Conexão ──────────────────────────────────────────────────────────────────

def _sb_url() -> str:
    return st.secrets["SUPABASE_URL"].rstrip("/")


def _sb_key() -> str:
    return st.secrets["SUPABASE_SERVICE_KEY"]


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
                "Verifique a SUPABASE_ANON_KEY nos secrets e se o RLS "
                "está desabilitado nas tabelas (ou se há policies de leitura/escrita)."
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
    """
    Retorna todos os IDs de atendimentos já gravados no Supabase.

    O PostgREST tem limite padrão de 1000 linhas por resposta,
    então usamos paginação por Range header (header HTTP padrão
    do PostgREST) para trazer todos os registros, mesmo que a
    tabela tenha dezenas de milhares.
    """
    todos: set[int] = set()
    chunk_size = 1000
    offset = 0

    while True:
        headers = _read_headers().copy()
        # Range header força o PostgREST a aceitar ranges além do default
        headers["Range-Unit"] = "items"
        headers["Range"] = f"{offset}-{offset + chunk_size - 1}"

        url = f"{_sb_url()}/rest/v1/atendimento"
        r = requests.get(
            url,
            headers=headers,
            params={"select": "id", "order": "id.asc"},
            timeout=30,
        )
        if not r.ok:
            break
        rows = r.json()
        if not rows:
            break
        todos.update(row["id"] for row in rows)
        # Se veio menos que o chunk, acabou
        if len(rows) < chunk_size:
            break
        offset += chunk_size

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
