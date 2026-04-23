"""
app.py — Plataforma de Atendimentos · Rio Verde GO
Listagem com filtros, paginação, painel de mensagens e importação para Supabase.
"""
import streamlit as st
from datetime import date, datetime
from api_client import get_atendimentos, get_mensagens, iter_atendimentos_lotes
from supabase_client import (
    get_ids_importados,
    upsert_departamento,
    upsert_atendente,
    upsert_atendimento,
    upsert_mensagens,
    testar_conexao,
)

# ── Página ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Atendimentos", page_icon="💬", layout="wide")

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


# ── Importação em lotes ──────────────────────────────────────────────────────
def executar_importacao(filtros: dict, ids_importados: set, tamanho_lote: int = 1000) -> tuple[int, list[str]]:
    """
    Importa atendimentos em lotes de `tamanho_lote` para não travar em
    volumes grandes (ex: dias com 20.000+ atendimentos).
    """
    erros: list[str] = []
    total_importado = 0

    # Normaliza IDs importados para int
    ids_importados_norm = {int(x) for x in ids_importados if x is not None}

    st.info(
        f"🔄 Iniciando importação em lotes de **{tamanho_lote}** · "
        f"Já existem **{len(ids_importados_norm):,}** atendimentos no Supabase"
        .replace(",", ".")
    )

    progress_lote = st.progress(0, text="Buscando primeiro lote…")
    status_text   = st.empty()
    debug_text    = st.empty()

    processados = 0
    lote_num = 0
    paginas_totais = 0

    try:
        for lote, paginas in iter_atendimentos_lotes(
            **filtros,
            ids_ja_importados=ids_importados_norm,
            tamanho_lote=tamanho_lote,
        ):
            lote_num += 1
            lote_tam = len(lote)
            paginas_totais = paginas

            debug_text.caption(
                f"🔬 Lote {lote_num}: {lote_tam} itens novos · "
                f"{paginas_totais} páginas consultadas na API até agora"
            )

            for i, chat in enumerate(lote):
                atend_id = chat.get("id")
                try:
                    upsert_departamento(chat.get("sector") or {})
                    upsert_atendente(chat.get("agent") or {})
                    upsert_atendimento(chat)
                    msgs_payload = get_mensagens(atend_id)
                    upsert_mensagens(atend_id, msgs_payload.get("data", []))
                    total_importado += 1
                except Exception as e:
                    erros.append(f"Atendimento #{atend_id}: {str(e)[:150]}")

                processados += 1
                progress_lote.progress(
                    (i + 1) / lote_tam,
                    text=f"Lote {lote_num} — item {i+1}/{lote_tam} · "
                         f"Total: {total_importado:,} importados · {len(erros)} erros"
                         .replace(",", ".")
                )

            status_text.info(
                f"✓ Lote {lote_num} concluído — {lote_tam} atendimentos processados. "
                f"Buscando próximo lote…"
            )
    except Exception as e:
        erros.append(f"Falha ao buscar lote: {e}")

    progress_lote.empty()
    status_text.empty()
    debug_text.empty()

    if total_importado == 0 and not erros:
        st.warning(
            f"⚠️ Nenhum atendimento foi emitido pelo iterador. "
            f"Páginas consultadas: {paginas_totais}. "
            f"Todos os IDs retornados pela API já estão no Supabase "
            f"(set de {len(ids_importados_norm):,} IDs).".replace(",", ".")
        )

    return total_importado, erros


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
col_titulo, col_reload = st.columns([5, 1])
with col_titulo:
    st.title("💬 Atendimentos")
    st.caption(f"Plataforma de Gestão · Rio Verde GO · "
               f"**{len(ids_importados):,}** atendimentos no Supabase".replace(",", "."))
with col_reload:
    st.write("")
    st.write("")
    if st.button("🔁 Recarregar cache", use_container_width=True,
                 help="Recarrega a lista de IDs já importados do Supabase"):
        try:
            st.session_state.ids_importados = get_ids_importados()
            st.rerun()
        except Exception as e:
            st.error(f"Erro: {e}")

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

    fc1, fc2, fc_lote, fbtn_clear, fbtn_int = st.columns([2, 2, 1.3, 1, 1.4])
    with fc1:
        f_order = st.selectbox("Ordenar por", ["created_at"], label_visibility="collapsed")
    with fc2:
        f_dir = st.selectbox(
            "Direção", ["desc", "asc"],
            format_func=lambda x: "Decrescente" if x == "desc" else "Crescente",
            label_visibility="collapsed",
        )
    with fc_lote:
        tam_lote = st.selectbox(
            "Lote",
            [250, 500, 1000, 2000],
            index=2,
            format_func=lambda x: f"Lote {x}",
            label_visibility="collapsed",
            help="Tamanho do lote de importação. Valores menores = menos travamento em volumes altos.",
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


# ── 🔬 PAINEL DE DIAGNÓSTICO (sempre visível) ────────────────────────────────
from urllib.parse import urlencode
from api_client import _headers as _dbg_h, _base as _dbg_b, _build_params as _dbg_p
import requests as _req

diag = st.container(border=True)
with diag:
    st.markdown("### 🔬 Diagnóstico do sistema")

    # Normaliza cache
    _ids_norm_cache = {int(x) for x in ids_importados if x is not None}

    # ── Linha 1: status gerais ──
    c1, c2, c3, c4 = st.columns(4)

    try:
        ok_sb, msg_sb = testar_conexao()
    except Exception as e:
        ok_sb, msg_sb = False, str(e)

    c1.metric("Supabase", "✅ Conectado" if ok_sb else "❌ Erro", help=msg_sb)
    c2.metric(
        "IDs no cache",
        f"{len(_ids_norm_cache):,}".replace(",", "."),
        help="Atendimentos já importados em memória",
    )
    if _ids_norm_cache:
        c3.metric("Maior ID no cache", sorted(_ids_norm_cache, reverse=True)[0])
    else:
        c3.metric("Maior ID no cache", "—")
    c4.metric("Filtros preenchidos", sum(1 for v in filtros_ativos.values() if v and v not in ("created_at", "desc")))

    # ── Filtros sendo enviados ──
    st.markdown("**Filtros que serão enviados à API:**")
    filtros_nao_nulos = {k: str(v) for k, v in filtros_ativos.items() if v is not None}
    st.json(filtros_nao_nulos)

    # ── Teste real da API ──
    st.markdown("**Resposta da API (chamada real com os filtros acima, página 1):**")
    try:
        params_teste = _dbg_p(page=1, **filtros_ativos)
        url_teste = f"{_dbg_b()}/chats?{urlencode(params_teste)}"
        st.code(url_teste, language="text")

        with st.spinner("Consultando API…"):
            resp = _req.get(f"{_dbg_b()}/chats", headers=_dbg_h(), params=params_teste, timeout=30)

        ct1, ct2, ct3, ct4 = st.columns(4)
        ct1.metric("HTTP", resp.status_code)

        if resp.status_code == 200:
            payload_teste = resp.json()
            meta_teste  = payload_teste.get("meta", {})
            data_teste  = payload_teste.get("data", [])
            links_teste = payload_teste.get("links", {})

            ct2.metric("Itens retornados", len(data_teste))
            ct3.metric("per_page", meta_teste.get("per_page", "?"))
            ct4.metric("Tem next?", "Sim" if links_teste.get("next") else "Não")

            if data_teste:
                # Análise dos IDs
                ids_api = [item.get("id") for item in data_teste]
                tipos = set(type(x).__name__ for x in ids_api)
                ids_int = [int(x) for x in ids_api if x is not None]

                novos = [x for x in ids_int if x not in _ids_norm_cache]
                ja = [x for x in ids_int if x in _ids_norm_cache]

                st.caption(f"Tipos dos IDs: `{tipos}` · Conversão para int: OK")

                cn1, cn2 = st.columns(2)
                cn1.metric("🆕 Novos (não estão no cache)", len(novos))
                cn2.metric("♻️ Já importados (no cache)", len(ja))

                # Amostra dos 3 primeiros
                st.markdown("**Amostra dos 3 primeiros atendimentos retornados:**")
                for idx, item in enumerate(data_teste[:3]):
                    aid = int(item.get("id"))
                    start = item.get("started_at", "?")
                    agent = (item.get("agent") or {}).get("name", "—")
                    sector = (item.get("sector") or {}).get("name", "—")
                    in_cache = aid in _ids_norm_cache

                    status_emoji = "♻️" if in_cache else "🆕"
                    st.code(
                        f"{status_emoji}  ID {aid}  ·  {start}  ·  "
                        f"Atendente: {agent[:30]}  ·  Setor: {sector[:30]}  ·  "
                        f"{'EM CACHE' if in_cache else 'NOVO'}",
                        language="text",
                    )
            else:
                st.error("❌ A API retornou lista vazia. Verifique os filtros enviados.")
        else:
            st.error(f"API retornou HTTP {resp.status_code}")
            st.code(resp.text[:500], language="text")
    except Exception as e:
        st.error(f"Erro ao consultar API: {e}")


st.divider()


# ── Importação ────────────────────────────────────────────────────────────────
if integrar_clicked:
    # Testa conexão antes de iniciar
    ok, msg_conn = testar_conexao()
    if not ok:
        st.error(f"❌ Falha na conexão com o Supabase: {msg_conn}")
        st.stop()

    total_imp, erros = executar_importacao(filtros_ativos, ids_importados, tamanho_lote=tam_lote)

    if total_imp == 0 and not erros:
        st.info("Nenhum atendimento novo encontrado para importar. (Veja o diagnóstico acima para detalhes)")
    elif erros:
        st.warning(f"Importados: {total_imp}. Erros: {len(erros)}.")
        with st.expander(f"Ver {len(erros)} erros"):
            for e in erros[:50]:
                st.code(e)
    else:
        st.success(f"✅ {total_imp} atendimento(s) importado(s) com sucesso!")

    # Atualiza cache de IDs importados (sem rerun, pra manter diagnóstico visível)
    try:
        st.session_state.ids_importados = get_ids_importados()
        ids_importados = st.session_state.ids_importados
    except Exception:
        pass

    st.stop()  # Para aqui, não renderiza a lista (economiza chamada API)


# ── Busca da página atual ─────────────────────────────────────────────────────
try:
    result = get_atendimentos(page=st.session_state.page, **filtros_ativos)
    data_api = result.get("data", [])
    meta     = result.get("meta", {})
except Exception as e:
    st.error(f"Erro ao consultar a API: {e}")
    st.stop()

# Filtra da lista os já importados (normaliza ID para int)
_ids_norm = {int(x) for x in ids_importados if x is not None}
data = [row for row in data_api if int(row.get("id")) not in _ids_norm]

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
