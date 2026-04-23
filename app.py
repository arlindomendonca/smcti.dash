"""
app.py — Plataforma de Atendimentos · Rio Verde GO
Listagem com filtros, paginação, painel de mensagens e importação para Supabase.
"""
import streamlit as st
from datetime import date, datetime
from api_client import get_atendimentos, get_mensagens, get_todas_paginas
from supabase_client import (
    get_ids_importados,
    upsert_departamento,
    upsert_atendente,
    upsert_atendimento,
    upsert_mensagens,
    testar_conexao,
)

# ── Página ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Atendimentos · Integração", page_icon="💬", layout="wide")

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.chat-wrap { display:flex; flex-direction:column; gap:10px; padding:4px 0; }
.msg-row-in  { display:flex; justify-content:flex-start; }
.msg-row-out { display:flex; justify-content:flex-end; }
.bubble { max-width:75%; padding:8px 12px; border-radius:12px; font-size:13px;
          line-height:1.55; word-break:break-word; }
.bubble-in  { background:#F3F4F6; color:#111827; }
.bubble-out { background:#DBEAFE; color:#1E3A5F; }
.msg-meta { font-size:11px; color:#9CA3AF; margin-top:3px; }
.badge-imp { display:inline-block; background:#D1FAE5; color:#065F46;
             border-radius:99px; padding:2px 8px; font-size:11px; font-weight:500; }
.badge-new { display:inline-block; background:#EFF6FF; color:#1D4ED8;
             border-radius:99px; padding:2px 8px; font-size:11px; font-weight:500; }
div[data-testid="stExpander"] { border:1px solid #E5E7EB !important; border-radius:8px !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────
def fmt_dt(s):
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return s


def render_mensagens(atendimento_id: int, recipient: str):
    with st.spinner("Carregando mensagens…"):
        try:
            payload = get_mensagens(atendimento_id)
            msgs = list(reversed(payload.get("data", [])))
        except Exception as e:
            st.error(f"Erro: {e}")
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
        row_class   = "msg-row-out" if is_out else "msg-row-in"
        bubble_class = "bubble bubble-out" if is_out else "bubble bubble-in"
        align = "right" if is_out else "left"
        rows_html += f"""
        <div class="{row_class}">
          <div>
            <div class="{bubble_class}">{body}</div>
            <div class="msg-meta" style="text-align:{align}">{meta}</div>
          </div>
        </div>"""

    st.markdown(f'<div class="chat-wrap">{rows_html}</div>', unsafe_allow_html=True)


# ── Importação completa ───────────────────────────────────────────────────────
def executar_importacao(filtros: dict, ids_importados: set) -> tuple[int, list[str]]:
    """
    Busca todas as páginas da API com os filtros ativos,
    importa apenas atendimentos novos (não presentes em ids_importados).
    Retorna (total_importado, lista_de_erros).
    """
    erros: list[str] = []
    total = 0

    with st.spinner("Buscando atendimentos na API…"):
        try:
            chats = get_todas_paginas(**filtros, ids_ja_importados=ids_importados)
        except Exception as e:
            return 0, [f"Erro ao buscar API: {e}"]

    if not chats:
        return 0, []

    progress = st.progress(0, text="Importando…")
    n = len(chats)

    for i, chat in enumerate(chats):
        atend_id = chat.get("id")
        try:
            # 1. Departamento (upsert por uuid — idempotente)
            upsert_departamento(chat.get("sector") or {})
            # 2. Atendente (upsert por uuid — idempotente)
            upsert_atendente(chat.get("agent") or {})
            # 3. Atendimento
            upsert_atendimento(chat)
            # 4. Mensagens
            msgs_payload = get_mensagens(atend_id)
            upsert_mensagens(atend_id, msgs_payload.get("data", []))
            total += 1
        except Exception as e:
            erros.append(f"Atendimento #{atend_id}: {e}")

        progress.progress((i + 1) / n, text=f"Importando {i+1}/{n}…")

    progress.empty()
    return total, erros


# ── Session state ────────────────────────────────────────────────────────────
defaults = {
    "page": 1,
    "selected_id": None,
    "selected_recipient": None,
    "selected_label": "",
    "ids_importados": None,   # carregado na primeira renderização
    "importacao_msg": None,   # mensagem de resultado da última importação
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Carrega IDs já importados do Supabase (uma vez por sessão)
if st.session_state.ids_importados is None:
    try:
        st.session_state.ids_importados = get_ids_importados()
    except Exception:
        st.session_state.ids_importados = set()

ids_importados: set = st.session_state.ids_importados


# ── Cabeçalho ────────────────────────────────────────────────────────────────
st.title("💬 Atendimentos")
st.caption("Plataforma de Gestão · Rio Verde GO")
st.divider()


# ── Filtros ──────────────────────────────────────────────────────────────────
with st.expander("🔍 Filtros", expanded=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        f_id        = st.text_input("ID do atendimento", placeholder="Ex: 8274730")
        f_recipient = st.text_input("Destinatário", placeholder="5564993202784")
        f_agent     = st.text_input("UUID do atendente", placeholder="00000000-0000-…")
    with c2:
        f_start_ini = st.date_input("Início — de",  value=None, format="DD/MM/YYYY")
        f_start_fin = st.date_input("Início — até", value=None, format="DD/MM/YYYY")
    with c3:
        f_end_ini = st.date_input("Fim — de",  value=None, format="DD/MM/YYYY")
        f_end_fin = st.date_input("Fim — até", value=None, format="DD/MM/YYYY")

    fc1, fc2, _, fbtn_clear, fbtn_int = st.columns([2, 2, 2, 1, 1.4])
    with fc1:
        f_order = st.selectbox("Ordenar por", ["created_at"], label_visibility="collapsed")
    with fc2:
        f_dir = st.selectbox(
            "Direção", ["desc", "asc"],
            format_func=lambda x: "Decrescente" if x == "desc" else "Crescente",
            label_visibility="collapsed",
        )
    with fbtn_clear:
        if st.button("🔄 Limpar filtros", use_container_width=True):
            st.session_state.page = 1
            st.rerun()
    with fbtn_int:
        integrar_clicked = st.button("⬆️ Integrar", use_container_width=True, type="primary")


# Monta dict de filtros reaproveitável
filtros_ativos = dict(
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


# ── Importação ────────────────────────────────────────────────────────────────
if integrar_clicked:
    # Testa conexão antes de iniciar
    ok, msg_conn = testar_conexao()
    if not ok:
        st.error(f"❌ Falha na conexão com o Supabase: {msg_conn}")
        st.stop()

    total_imp, erros = executar_importacao(filtros_ativos, ids_importados)

    if total_imp == 0 and not erros:
        st.session_state.importacao_msg = ("info", "Nenhum atendimento novo encontrado para importar.")
    elif erros:
        msg = f"Importados: {total_imp}. Erros: {len(erros)}.\n" + "\n".join(erros[:10])
        st.session_state.importacao_msg = ("warning", msg)
    else:
        st.session_state.importacao_msg = ("success", f"✅ {total_imp} atendimento(s) importado(s) com sucesso!")

    # Atualiza cache de IDs importados
    try:
        st.session_state.ids_importados = get_ids_importados()
        ids_importados = st.session_state.ids_importados
    except Exception:
        pass

    st.rerun()

# Exibe resultado da última importação
if st.session_state.importacao_msg:
    kind, msg = st.session_state.importacao_msg
    getattr(st, kind)(msg)
    st.session_state.importacao_msg = None


# ── Busca da página atual ─────────────────────────────────────────────────────
try:
    result = get_atendimentos(page=st.session_state.page, **filtros_ativos)
    data_api = result.get("data", [])
    meta     = result.get("meta", {})
except Exception as e:
    st.error(f"Erro ao consultar a API: {e}")
    st.stop()

# Filtra da lista os já importados
data = [row for row in data_api if row.get("id") not in ids_importados]

total_api  = meta.get("total", len(data_api))
from_n     = meta.get("from", 1)
to_n       = meta.get("to", len(data_api))
per_pg     = meta.get("per_page", 25)
total_pages = max(1, -(-total_api // per_pg)) if total_api else 1


# ── Métricas ──────────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total na API (filtro atual)", f"{total_api:,}".replace(",", "."))
m2.metric("Já importados (sessão)", f"{len(ids_importados):,}".replace(",", "."))
m3.metric("Pendentes nesta página", len(data))
m4.metric("Página", f"{st.session_state.page} / {total_pages}")

st.divider()


# ── Layout: lista + mensagens ─────────────────────────────────────────────────
col_list, col_panel = st.columns([3, 2], gap="large")

with col_list:
    st.subheader("Atendimentos pendentes de importação")

    if not data:
        if data_api:
            st.success("✅ Todos os atendimentos desta página já foram importados.")
        else:
            st.info("Nenhum atendimento encontrado para os filtros selecionados.")
    else:
        h = st.columns([1, 2, 2.5, 2, 2, 1])
        for col, label in zip(h, ["ID", "Destinatário", "Atendente", "Início", "Fim", ""]):
            col.markdown(f"**{label}**")
        st.divider()

        for row in data:
            atend_id  = row.get("id")
            recipient = row.get("recipient", "—")
            agent     = (row.get("agent") or {}).get("name", "—")
            sector    = (row.get("sector") or {}).get("name", "—")
            started   = fmt_dt(row.get("started_at"))
            finished  = fmt_dt(row.get("finished_at"))

            c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 2.5, 2, 2, 1])
            c1.write(atend_id)
            c2.write(recipient)
            c3.write(agent[:26] + "…" if len(agent) > 26 else agent)
            c4.write(started)
            c5.write(finished)
            if c6.button("Ver", key=f"btn_{atend_id}"):
                st.session_state.selected_id        = atend_id
                st.session_state.selected_recipient = recipient
                st.session_state.selected_label     = f"#{atend_id} · {agent} · {sector}"
                st.rerun()

    # Paginação
    st.divider()
    pg1, pg2, pg3 = st.columns([1, 3, 1])
    with pg1:
        if st.button("◀ Anterior", disabled=st.session_state.page <= 1, use_container_width=True):
            st.session_state.page -= 1
            st.rerun()
    with pg2:
        new_page = st.number_input(
            "Página", min_value=1, max_value=total_pages,
            value=st.session_state.page, step=1, label_visibility="collapsed",
        )
        if int(new_page) != st.session_state.page:
            st.session_state.page = int(new_page)
            st.rerun()
    with pg3:
        if st.button("Próxima ▶", disabled=st.session_state.page >= total_pages, use_container_width=True):
            st.session_state.page += 1
            st.rerun()


# ── Painel de mensagens ───────────────────────────────────────────────────────
with col_panel:
    if st.session_state.selected_id:
        st.subheader("Mensagens")
        st.caption(st.session_state.selected_label)
        if st.button("✕ Fechar"):
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
