"""
app.py — Plataforma de Atendimentos · Rio Verde GO
Página principal: listagem com filtros + painel de mensagens
"""
import streamlit as st
from datetime import date, datetime
from api_client import get_atendimentos, get_mensagens

# ── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Atendimentos",
    page_icon="💬",
    layout="wide",
)

# ── CSS customizado ─────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Tabela de atendimentos */
.atend-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.atend-table th {
    background: #F3F4F6;
    color: #6B7280;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .05em;
    padding: 8px 12px;
    border-bottom: 1px solid #E5E7EB;
    text-align: left;
}
.atend-table td {
    padding: 9px 12px;
    border-bottom: 1px solid #F3F4F6;
    color: #111827;
    vertical-align: middle;
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.atend-table tr:hover td { background: #F9FAFB; }

/* Mensagens */
.chat-wrap { display: flex; flex-direction: column; gap: 10px; padding: 4px 0; }
.msg-row-in  { display: flex; justify-content: flex-start; }
.msg-row-out { display: flex; justify-content: flex-end; }
.bubble {
    max-width: 75%;
    padding: 8px 12px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.55;
    word-break: break-word;
}
.bubble-in  { background: #F3F4F6; color: #111827; }
.bubble-out { background: #DBEAFE; color: #1E3A5F; }
.msg-meta { font-size: 11px; color: #9CA3AF; margin-top: 3px; }
.badge-rating {
    display: inline-block;
    background: #D1FAE5;
    color: #065F46;
    border-radius: 99px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
}
.badge-none {
    display: inline-block;
    background: #F3F4F6;
    color: #9CA3AF;
    border-radius: 99px;
    padding: 2px 8px;
    font-size: 12px;
}
div[data-testid="stExpander"] { border: 1px solid #E5E7EB !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────────────
def fmt_dt(s: str | None) -> str:
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return s


def rating_html(r) -> str:
    if r is None:
        return '<span class="badge-none">—</span>'
    stars = "★" * int(r) + "☆" * (5 - int(r))
    return f'<span class="badge-rating">{stars}</span>'


def render_mensagens(atendimento_id: int, recipient: str):
    """Busca e renderiza as mensagens de um atendimento."""
    with st.spinner("Carregando mensagens…"):
        try:
            data = get_mensagens(atendimento_id)
            msgs = list(reversed(data.get("data", [])))
        except Exception as e:
            st.error(f"Erro ao carregar mensagens: {e}")
            return

    if not msgs:
        st.info("Nenhuma mensagem registrada.")
        return

    rows_html = ""
    for m in msgs:
        body = (m.get("body") or "").replace("\n", "<br>")
        sent = fmt_dt(m.get("sent_at"))
        status = " · ".join(filter(None, [m.get("send_status"), m.get("send_status_confirmation")]))
        meta = f"{sent}{' · ' + status if status else ''}"

        is_out = m.get("recipient") == recipient
        row_class = "msg-row-out" if is_out else "msg-row-in"
        bubble_class = "bubble bubble-out" if is_out else "bubble bubble-in"

        rows_html += f"""
        <div class="{row_class}">
          <div>
            <div class="{bubble_class}">{body}</div>
            <div class="msg-meta" style="text-align:{'right' if is_out else 'left'}">{meta}</div>
          </div>
        </div>"""

    st.markdown(f'<div class="chat-wrap">{rows_html}</div>', unsafe_allow_html=True)


# ── Session state ───────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = 1
if "selected_id" not in st.session_state:
    st.session_state.selected_id = None
if "selected_recipient" not in st.session_state:
    st.session_state.selected_recipient = None
if "selected_label" not in st.session_state:
    st.session_state.selected_label = ""


# ── Cabeçalho ───────────────────────────────────────────────────────────────
st.title("💬 Atendimentos")
st.caption("Plataforma de Gestão · Rio Verde GO")
st.divider()


# ── Filtros ─────────────────────────────────────────────────────────────────
with st.expander("🔍 Filtros", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        f_id        = st.text_input("ID do atendimento", placeholder="Ex: 8274730")
        f_recipient = st.text_input("Destinatário", placeholder="5564993202784")
        f_agent     = st.text_input("UUID do atendente", placeholder="00000000-0000-…")
    with c2:
        f_start_ini = st.date_input("Início — de",   value=None, format="DD/MM/YYYY")
        f_start_fin = st.date_input("Início — até",  value=None, format="DD/MM/YYYY")
    with c3:
        f_end_ini   = st.date_input("Fim — de",      value=None, format="DD/MM/YYYY")
        f_end_fin   = st.date_input("Fim — até",     value=None, format="DD/MM/YYYY")

    fc1, fc2, _, _, _, fbtn = st.columns([2, 2, 1, 1, 1, 1])
    with fc1:
        f_order = st.selectbox("Ordenar por", ["created_at"], label_visibility="collapsed")
    with fc2:
        f_dir = st.selectbox("Direção", ["desc", "asc"],
                             format_func=lambda x: "Decrescente" if x == "desc" else "Crescente",
                             label_visibility="collapsed")
    with fbtn:
        if st.button("🔄 Limpar", use_container_width=True):
            st.session_state.page = 1
            st.rerun()


# ── Busca ───────────────────────────────────────────────────────────────────
try:
    result = get_atendimentos(
        page=st.session_state.page,
        id=f_id or None,
        recipient=f_recipient or None,
        agent_uuid=f_agent or None,
        started_at_initial=f_start_ini if isinstance(f_start_ini, date) else None,
        started_at_final=f_start_fin   if isinstance(f_start_fin, date) else None,
        finished_at_initial=f_end_ini  if isinstance(f_end_ini, date) else None,
        finished_at_final=f_end_fin    if isinstance(f_end_fin, date) else None,
        order_by=f_order,
        order_direction=f_dir,
    )
    data  = result.get("data", [])
    meta  = result.get("meta", {})
    links = result.get("links", {})
except Exception as e:
    st.error(f"Erro ao consultar a API: {e}")
    st.stop()


# ── Métricas resumidas ───────────────────────────────────────────────────────
total   = meta.get("total", len(data))
from_n  = meta.get("from", 1)
to_n    = meta.get("to", len(data))
per_pg  = meta.get("per_page", 25)
total_pages = max(1, -(-total // per_pg)) if total else 1  # ceil division

m1, m2, m3 = st.columns(3)
m1.metric("Total de atendimentos", f"{total:,}".replace(",", "."))
m2.metric("Página atual", f"{st.session_state.page} / {total_pages}")
m3.metric("Exibindo", f"{from_n}–{to_n}")

st.divider()

# ── Layout: lista + painel de mensagens ─────────────────────────────────────
col_list, col_panel = st.columns([3, 2], gap="large")

with col_list:
    st.subheader("Lista de atendimentos")

    if not data:
        st.info("Nenhum atendimento encontrado para os filtros selecionados.")
    else:
        # Cabeçalho da tabela
        h = st.columns([1, 2, 2.5, 2, 2, 1.5, 1])
        for col, label in zip(h, ["ID", "Destinatário", "Atendente", "Início", "Fim", "Avaliação", ""]):
            col.markdown(f"**{label}**")
        st.divider()

        for row in data:
            atend_id  = row.get("id")
            recipient = row.get("recipient", "—")
            agent     = (row.get("agent") or {}).get("name", "—")
            sector    = (row.get("sector") or {}).get("name", "—")
            started   = fmt_dt(row.get("started_at"))
            finished  = fmt_dt(row.get("finished_at"))
            rating    = row.get("rating")
            rating_str = ("★" * int(rating) + "☆" * (5 - int(rating))) if rating else "—"

            c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 2, 2.5, 2, 2, 1.5, 1])
            c1.write(atend_id)
            c2.write(recipient)
            c3.write(agent[:28] + "…" if len(agent) > 28 else agent)
            c4.write(started)
            c5.write(finished)
            c6.write(rating_str)
            if c7.button("Ver", key=f"btn_{atend_id}"):
                st.session_state.selected_id        = atend_id
                st.session_state.selected_recipient = recipient
                st.session_state.selected_label     = f"#{atend_id} · {agent} · {sector}"
                st.rerun()

    # ── Paginação ────────────────────────────────────────────────────────────
    st.divider()
    pg1, pg2, pg3 = st.columns([1, 3, 1])

    with pg1:
        if st.button("◀ Anterior", disabled=st.session_state.page <= 1, use_container_width=True):
            st.session_state.page -= 1
            st.rerun()

    with pg2:
        new_page = st.number_input(
            "Ir para página",
            min_value=1,
            max_value=total_pages,
            value=st.session_state.page,
            step=1,
            label_visibility="collapsed",
        )
        if new_page != st.session_state.page:
            st.session_state.page = int(new_page)
            st.rerun()

    with pg3:
        if st.button("Próxima ▶", disabled=st.session_state.page >= total_pages, use_container_width=True):
            st.session_state.page += 1
            st.rerun()


# ── Painel de mensagens ──────────────────────────────────────────────────────
with col_panel:
    if st.session_state.selected_id:
        st.subheader("Mensagens")
        st.caption(st.session_state.selected_label)

        if st.button("✕ Fechar", key="close_panel"):
            st.session_state.selected_id = None
            st.session_state.selected_recipient = None
            st.session_state.selected_label = ""
            st.rerun()

        st.divider()
        render_mensagens(
            st.session_state.selected_id,
            st.session_state.selected_recipient or "",
        )
    else:
        st.info("Selecione um atendimento na lista para visualizar as mensagens.")
