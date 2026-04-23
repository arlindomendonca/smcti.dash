"""
api_client.py — Wrapper para a API gove.digital
"""
import requests
import streamlit as st
from datetime import date
from typing import Optional


def _headers() -> dict:
    token = st.secrets["api"]["token"]
    return {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
    }


def _base() -> str:
    return st.secrets["api"]["base_url"]


def _fmt_date(d: Optional[date]) -> Optional[str]:
    if d is None:
        return None
    return d.strftime("%d/%m/%Y")


def _build_params(
    page: int = 1,
    id: Optional[str] = None,
    recipient: Optional[str] = None,
    agent_uuid: Optional[str] = None,
    started_at_initial: Optional[date] = None,
    started_at_final: Optional[date] = None,
    finished_at_initial: Optional[date] = None,
    finished_at_final: Optional[date] = None,
    order_by: str = "created_at",
    order_direction: str = "desc",
) -> dict:
    params: dict = {
        "page": page,
        "order_by": order_by,
        "order_direction": order_direction,
    }
    if id:
        params["id"] = id
    if recipient:
        params["recipient"] = recipient
    if agent_uuid:
        params["agent_uuid"] = agent_uuid
    if started_at_initial:
        params["started_at_initial"] = _fmt_date(started_at_initial)
    if started_at_final:
        params["started_at_final"] = _fmt_date(started_at_final)
    if finished_at_initial:
        params["finished_at_initial"] = _fmt_date(finished_at_initial)
    if finished_at_final:
        params["finished_at_final"] = _fmt_date(finished_at_final)
    return params


def get_atendimentos(
    page: int = 1,
    id: Optional[str] = None,
    recipient: Optional[str] = None,
    agent_uuid: Optional[str] = None,
    started_at_initial: Optional[date] = None,
    started_at_final: Optional[date] = None,
    finished_at_initial: Optional[date] = None,
    finished_at_final: Optional[date] = None,
    order_by: str = "created_at",
    order_direction: str = "desc",
) -> dict:
    """Consulta /v2/chats — uma página."""
    params = _build_params(
        page=page, id=id, recipient=recipient, agent_uuid=agent_uuid,
        started_at_initial=started_at_initial, started_at_final=started_at_final,
        finished_at_initial=finished_at_initial, finished_at_final=finished_at_final,
        order_by=order_by, order_direction=order_direction,
    )
    resp = requests.get(f"{_base()}/chats", headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_todas_paginas(
    id: Optional[str] = None,
    recipient: Optional[str] = None,
    agent_uuid: Optional[str] = None,
    started_at_initial: Optional[date] = None,
    started_at_final: Optional[date] = None,
    finished_at_initial: Optional[date] = None,
    finished_at_final: Optional[date] = None,
    order_by: str = "created_at",
    order_direction: str = "desc",
    ids_ja_importados: Optional[set] = None,
) -> list[dict]:
    """
    Percorre todas as páginas e retorna apenas os atendimentos
    ainda NÃO presentes no Supabase.
    """
    ids_ja_importados = ids_ja_importados or set()
    todos: list[dict] = []
    page = 1

    while True:
        params = _build_params(
            page=page, id=id, recipient=recipient, agent_uuid=agent_uuid,
            started_at_initial=started_at_initial, started_at_final=started_at_final,
            finished_at_initial=finished_at_initial, finished_at_final=finished_at_final,
            order_by=order_by, order_direction=order_direction,
        )
        resp = requests.get(f"{_base()}/chats", headers=_headers(), params=params, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        items = payload.get("data", [])
        if not items:
            break

        novos = [item for item in items if item.get("id") not in ids_ja_importados]
        todos.extend(novos)

        next_link = payload.get("links", {}).get("next")
        if not next_link:
            break
        page += 1

    return todos


def get_mensagens(atendimento_id: int) -> dict:
    """Consulta /v2/chats/{id}/messages com paginação interna."""
    todas: list[dict] = []
    page = 1

    while True:
        resp = requests.get(
            f"{_base()}/chats/{atendimento_id}/messages",
            headers=_headers(),
            params={"page": page},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("data", [])
        todas.extend(items)

        next_link = payload.get("links", {}).get("next")
        if not next_link:
            break
        page += 1

    return {"data": todas}
