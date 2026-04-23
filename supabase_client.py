"""
supabase_client.py — Integração com o Supabase
Usa a REST API do Supabase diretamente via requests (sem SDK extra).
Todas as operações de escrita são upsert por UUID — seguro rodar N vezes.
"""
import requests
import streamlit as st
from typing import Any


# ── Conexão ─────────────────────────────────────────────────────────────────

def _sb_url() -> str:
    return st.secrets["supabase"]["url"].rstrip("/")


def _sb_headers(prefer: str = "") -> dict:
    h = {
        "apikey": st.secrets["supabase"]["service_key"],
        "Authorization": f"Bearer {st.secrets['supabase']['service_key']}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _post(table: str, payload: list[dict], on_conflict: str) -> requests.Response:
    """Upsert em lote numa tabela do Supabase."""
    url = f"{_sb_url()}/rest/v1/{table}"
    return requests.post(
        url,
        json=payload,
        headers=_sb_headers(f"resolution=merge-duplicates,return=minimal"),
        params={"on_conflict": on_conflict},
        timeout=30,
    )


# ── IDs já importados ────────────────────────────────────────────────────────

def get_ids_importados() -> set[int]:
    """Retorna o conjunto de IDs de atendimentos já gravados no Supabase."""
    url = f"{_sb_url()}/rest/v1/atendimento"
    resp = requests.get(
        url,
        headers=_sb_headers(),
        params={"select": "id"},
        timeout=15,
    )
    if not resp.ok:
        return set()
    return {row["id"] for row in resp.json()}


# ── Importação ───────────────────────────────────────────────────────────────

def upsert_departamento(sector: dict) -> None:
    if not sector or not sector.get("uuid"):
        return
    payload = [{
        "uuid":    sector["uuid"],
        "name":    sector.get("name", ""),
        "acronym": sector.get("acronym"),
    }]
    r = _post("departamento", payload, "uuid")
    r.raise_for_status()


def upsert_atendente(agent: dict) -> None:
    if not agent or not agent.get("uuid"):
        return
    payload = [{
        "uuid":           agent["uuid"],
        "name":           agent.get("name", ""),
        "email":          agent.get("email"),
        "api_created_at": agent.get("created_at"),
    }]
    r = _post("atendente", payload, "uuid")
    r.raise_for_status()


def upsert_atendimento(chat: dict) -> None:
    payload = [{
        "id":                 chat["id"],
        "recipient":          chat.get("recipient", ""),
        "started_at":         chat.get("started_at"),
        "finished_at":        chat.get("finished_at"),
        "rating":             chat.get("rating"),
        "atendente_uuid":     (chat.get("agent") or {}).get("uuid"),
        "departamento_uuid":  (chat.get("sector") or {}).get("uuid"),
    }]
    r = _post("atendimento", payload, "id")
    r.raise_for_status()


def upsert_mensagens(atendimento_id: int, mensagens: list[dict]) -> None:
    if not mensagens:
        return
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
    if payload:
        r = _post("mensagem", payload, "uuid")
        r.raise_for_status()
