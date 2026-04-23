"""
api_client.py — Wrapper para a API gove.digital
"""
import requests
import streamlit as st
from datetime import date
from typing import Optional


def _headers() -> dict:
    token = st.secrets["GOVE_TOKEN"]
    return {
        "accept": "application/json",
        "authorization": f"Bearer {token}",
    }


def _base() -> str:
    return st.secrets["GOVE_BASE_URL"]


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


def iter_atendimentos_lotes(
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
    tamanho_lote: int = 1000,
):
    """
    Iterador que retorna atendimentos NOVOS (não importados) em lotes.
    Cada `yield` entrega até `tamanho_lote` atendimentos prontos para importar.

    A API retorna 25 por página, então o iterador agrupa internamente
    várias páginas até formar um lote. Isso evita carregar todas as
    20.000+ ocorrências de um dia na memória de uma só vez.

    Yields:
        tuple[list[dict], int]: (lote_de_atendimentos, total_paginas_consultadas)
    """
    ids_ja_importados = {int(x) for x in (ids_ja_importados or set()) if x is not None}
    buffer: list[dict] = []
    page = 1
    paginas_consultadas = 0

    while True:
        params = _build_params(
            page=page, id=id, recipient=recipient, agent_uuid=agent_uuid,
            started_at_initial=started_at_initial, started_at_final=started_at_final,
            finished_at_initial=finished_at_initial, finished_at_final=finished_at_final,
            order_by=order_by, order_direction=order_direction,
        )
        resp = requests.get(f"{_base()}/chats", headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        paginas_consultadas += 1

        items = payload.get("data", [])
        if not items:
            break

        # Filtra apenas novos (normaliza ID para int)
        novos = [
            item for item in items
            if int(item.get("id")) not in ids_ja_importados
        ]
        buffer.extend(novos)

        # Se atingiu o tamanho do lote, emite
        while len(buffer) >= tamanho_lote:
            yield buffer[:tamanho_lote], paginas_consultadas
            buffer = buffer[tamanho_lote:]

        next_link = payload.get("links", {}).get("next")
        if not next_link:
            break
        page += 1

    # Emite o resto
    if buffer:
        yield buffer, paginas_consultadas


def get_meta_filtro(
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
    """
    Retorna apenas o bloco 'meta' da primeira página — útil para
    saber o total de registros antes de começar a importação.
    """
    params = _build_params(
        page=1, id=id, recipient=recipient, agent_uuid=agent_uuid,
        started_at_initial=started_at_initial, started_at_final=started_at_final,
        finished_at_initial=finished_at_initial, finished_at_final=finished_at_final,
        order_by=order_by, order_direction=order_direction,
    )
    resp = requests.get(f"{_base()}/chats", headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("meta", {})


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
