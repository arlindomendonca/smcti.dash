"""
pages/2_📊_Dashboard.py — Análise de Performance dos Atendimentos
Lê dados da view vw_atendimento_enriquecido no Supabase.
"""
import streamlit as st
import pandas as pd
import altair as alt
from datetime import date, timedelta
from supabase_client import get_atendimentos_enriquecidos

# ── Configuração ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Dashboard · Atendimentos", page_icon="📊", layout="wide")

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #F8F9FB;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 16px 18px;
}
[data-testid="stMetricLabel"] { color: #6B7280 !important; font-size: 12px !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: .04em; }
[data-testid="stMetricValue"] { color: #111827 !important; font-size: 26px !important; font-weight: 600 !important; }
div[data-testid="stExpander"] { border: 1px solid #E5E7EB !important; border-radius: 10px !important; }
.section-title { font-size: 15px; font-weight: 600; color: #111827; margin: 8px 0 14px; padding-bottom: 6px; border-bottom: 1px solid #E5E7EB; }
.kpi-help { font-size: 11px; color: #9CA3AF; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)


# ── Cores padronizadas por tipo de atendimento ───────────────────────────────
CORES_TIPO = {
    "Atendimento real":   "#10B981",
    "Autenticação 2FA":   "#8B5CF6",
    "Abandonado":         "#F59E0B",
    "Em aberto":          "#3B82F6",
    "Sem classificação":  "#6B7280",
}


# ── Cache da consulta ────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner="Carregando dados do Supabase…")
def carregar_dados(data_inicio: str | None, data_fim: str | None) -> pd.DataFrame:
    raw = get_atendimentos_enriquecidos(data_inicio=data_inicio, data_fim=data_fim)
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    for col in ["started_at", "finished_at", "primeira_msg_at", "ultima_msg_at", "data_inicio"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    if "data_inicio" in df.columns:
        df["data_inicio"] = df["data_inicio"].dt.tz_convert("America/Sao_Paulo").dt.date
    for col in ["duracao_minutos", "total_mensagens", "msgs_para_cidadao", "msgs_do_cidadao", "rating"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── Cabeçalho ────────────────────────────────────────────────────────────────
st.title("📊 Dashboard de Atendimentos")
st.caption("Análise de performance, prazos e qualidade · Rio Verde GO")
st.divider()


# ── Filtros ──────────────────────────────────────────────────────────────────
with st.expander("🎛️ Filtros", expanded=True):
    f1, f2, f3 = st.columns([2, 2, 2])
    with f1:
        periodo = st.selectbox(
            "Período",
            ["Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias", "Este mês", "Personalizado"],
            index=1,
        )
    today = date.today()
    if periodo == "Últimos 7 dias":
        dt_ini, dt_fim = today - timedelta(days=7), today
    elif periodo == "Últimos 30 dias":
        dt_ini, dt_fim = today - timedelta(days=30), today
    elif periodo == "Últimos 90 dias":
        dt_ini, dt_fim = today - timedelta(days=90), today
    elif periodo == "Este mês":
        dt_ini, dt_fim = today.replace(day=1), today
    else:
        with f2:
            dt_ini = st.date_input("De", value=today - timedelta(days=30), format="DD/MM/YYYY")
        with f3:
            dt_fim = st.date_input("Até", value=today, format="DD/MM/YYYY")

    if periodo != "Personalizado":
        f2.metric("De",  dt_ini.strftime("%d/%m/%Y"))
        f3.metric("Até", dt_fim.strftime("%d/%m/%Y"))


# ── Carrega dados ────────────────────────────────────────────────────────────
try:
    df = carregar_dados(str(dt_ini), str(dt_fim))
except Exception as e:
    st.error("❌ Falha ao carregar dados do Supabase")
    st.code(str(e), language="text")
    st.info(
        "Verifique se:\n"
        "1. A view `vw_atendimento_enriquecido` foi criada no Supabase\n"
        "2. As credenciais (url e service_key) estão corretas nos secrets\n"
        "3. A view está acessível (sem RLS bloqueando leitura)"
    )
    st.stop()

if df.empty:
    st.warning("Nenhum atendimento encontrado no período selecionado.")
    st.stop()


# Filtros secundários dependentes dos dados
with st.expander("🔍 Filtros avançados", expanded=False):
    a1, a2, a3 = st.columns(3)
    with a1:
        tipos_disp = sorted(df["tipo_atendimento"].dropna().unique().tolist())
        f_tipos = st.multiselect("Tipo de atendimento", tipos_disp, default=tipos_disp)
    with a2:
        deps_disp = sorted(df["departamento_nome"].dropna().unique().tolist())
        f_deps = st.multiselect("Departamentos", deps_disp, default=deps_disp)
    with a3:
        atts_disp = sorted(df["atendente_nome"].dropna().unique().tolist())
        f_atts = st.multiselect("Atendentes", atts_disp, default=atts_disp)


df_f = df[
    df["tipo_atendimento"].isin(f_tipos)
    & (df["departamento_nome"].isin(f_deps) | df["departamento_nome"].isna())
    & (df["atendente_nome"].isin(f_atts) | df["atendente_nome"].isna())
].copy()

if df_f.empty:
    st.warning("Nenhum dado encontrado com os filtros aplicados.")
    st.stop()


# ── KPIs principais ──────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Visão geral</div>', unsafe_allow_html=True)

total           = len(df_f)
reais           = len(df_f[df_f["tipo_atendimento"] == "Atendimento real"])
abandonados     = len(df_f[df_f["tipo_atendimento"] == "Abandonado"])
em_aberto       = len(df_f[df_f["tipo_atendimento"] == "Em aberto"])
pct_reais       = (reais / total * 100) if total else 0
pct_abandono    = (abandonados / total * 100) if total else 0
dur_media       = df_f[df_f["tipo_atendimento"] == "Atendimento real"]["duracao_minutos"].mean()
dur_mediana     = df_f[df_f["tipo_atendimento"] == "Atendimento real"]["duracao_minutos"].median()
avaliacao_media = df_f["rating"].mean()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total",          f"{total:,}".replace(",", "."))
k2.metric("Efetivos",       f"{reais:,}".replace(",", "."), f"{pct_reais:.1f}%")
k3.metric("Taxa de abandono", f"{pct_abandono:.1f}%", f"{abandonados} atend.", delta_color="inverse")
k4.metric("Em aberto",      em_aberto)
k5.metric("Duração média",  f"{dur_media:.1f} min" if pd.notna(dur_media) else "—")
k6.metric("Avaliação média",f"{avaliacao_media:.2f} ★" if pd.notna(avaliacao_media) else "—")

st.divider()


# ── Composição dos atendimentos ──────────────────────────────────────────────
st.markdown('<div class="section-title">Composição dos atendimentos</div>', unsafe_allow_html=True)

c1, c2 = st.columns([1, 1.3])

with c1:
    composicao = (
        df_f.groupby("tipo_atendimento").size().reset_index(name="quantidade")
        .sort_values("quantidade", ascending=False)
    )
    composicao["pct"] = (composicao["quantidade"] / composicao["quantidade"].sum() * 100).round(1)

    chart = alt.Chart(composicao).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("quantidade:Q", title="Quantidade"),
        y=alt.Y("tipo_atendimento:N", sort="-x", title=None),
        color=alt.Color(
            "tipo_atendimento:N",
            scale=alt.Scale(domain=list(CORES_TIPO.keys()), range=list(CORES_TIPO.values())),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("tipo_atendimento:N", title="Tipo"),
            alt.Tooltip("quantidade:Q", title="Qtd"),
            alt.Tooltip("pct:Q", title="%", format=".1f"),
        ],
    ).properties(height=220)
    st.altair_chart(chart, use_container_width=True)

with c2:
    # Evolução diária
    evolucao = (
        df_f.groupby(["data_inicio", "tipo_atendimento"]).size().reset_index(name="quantidade")
    )
    chart_evol = alt.Chart(evolucao).mark_area(opacity=0.85).encode(
        x=alt.X("data_inicio:T", title="Data"),
        y=alt.Y("quantidade:Q", stack="zero", title="Atendimentos"),
        color=alt.Color(
            "tipo_atendimento:N",
            scale=alt.Scale(domain=list(CORES_TIPO.keys()), range=list(CORES_TIPO.values())),
            legend=alt.Legend(orient="bottom", title=None),
        ),
        tooltip=[
            alt.Tooltip("data_inicio:T", title="Data", format="%d/%m"),
            alt.Tooltip("tipo_atendimento:N", title="Tipo"),
            alt.Tooltip("quantidade:Q", title="Qtd"),
        ],
    ).properties(height=220)
    st.altair_chart(chart_evol, use_container_width=True)

st.divider()


# ── Performance por departamento ─────────────────────────────────────────────
st.markdown('<div class="section-title">Performance por departamento</div>', unsafe_allow_html=True)

df_reais = df_f[df_f["tipo_atendimento"] == "Atendimento real"].copy()

if df_reais.empty:
    st.info("Sem atendimentos efetivos no período para análise por departamento.")
else:
    dep_stats = (
        df_reais.groupby("departamento_nome", dropna=True)
        .agg(
            total=("id", "count"),
            duracao_media=("duracao_minutos", "mean"),
            duracao_mediana=("duracao_minutos", "median"),
            avaliacao=("rating", "mean"),
            msgs_trocadas=("total_mensagens", "mean"),
        )
        .round(2)
        .reset_index()
        .sort_values("total", ascending=False)
    )

    d1, d2 = st.columns([1.3, 1])

    with d1:
        top_n = min(10, len(dep_stats))
        top = dep_stats.head(top_n)
        chart_dep = alt.Chart(top).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, color="#3B82F6").encode(
            y=alt.Y("departamento_nome:N", sort="-x", title=None),
            x=alt.X("total:Q", title="Atendimentos efetivos"),
            tooltip=[
                alt.Tooltip("departamento_nome:N", title="Departamento"),
                alt.Tooltip("total:Q", title="Total"),
                alt.Tooltip("duracao_media:Q", title="Duração média (min)", format=".1f"),
                alt.Tooltip("avaliacao:Q", title="Avaliação", format=".2f"),
            ],
        ).properties(height=280)
        st.altair_chart(chart_dep, use_container_width=True)

    with d2:
        st.markdown("**Ranking de eficiência**")
        tabela = dep_stats.head(top_n).copy()
        tabela["duracao_media"] = tabela["duracao_media"].apply(lambda v: f"{v:.1f} min" if pd.notna(v) else "—")
        tabela["avaliacao"]     = tabela["avaliacao"].apply(lambda v: f"{v:.2f}★" if pd.notna(v) else "—")
        tabela = tabela.rename(columns={
            "departamento_nome": "Departamento",
            "total": "Qtd",
            "duracao_media": "Duração",
            "avaliacao": "Nota",
        })[["Departamento", "Qtd", "Duração", "Nota"]]
        st.dataframe(tabela, hide_index=True, use_container_width=True, height=280)

st.divider()


# ── Performance por atendente ────────────────────────────────────────────────
with st.expander("👤 Performance individual dos atendentes", expanded=True):
    if df_reais.empty:
        st.info("Sem dados de atendentes no período.")
    else:
        att_stats = (
            df_reais.groupby("atendente_nome", dropna=True)
            .agg(
                total=("id", "count"),
                duracao_media=("duracao_minutos", "mean"),
                duracao_mediana=("duracao_minutos", "median"),
                avaliacao_media=("rating", "mean"),
                avaliacoes=("rating", "count"),
                msgs_enviadas=("msgs_para_cidadao", "sum"),
            )
            .round(2)
            .reset_index()
            .sort_values("total", ascending=False)
        )

        # Scatter: volume x duração (bolha = avaliação)
        scatter_df = att_stats.dropna(subset=["duracao_media"]).copy()
        if not scatter_df.empty:
            scatter_df["avaliacao_display"] = scatter_df["avaliacao_media"].fillna(0)
            chart_scatter = alt.Chart(scatter_df).mark_circle(opacity=0.75).encode(
                x=alt.X("total:Q", title="Volume de atendimentos"),
                y=alt.Y("duracao_media:Q", title="Duração média (min)"),
                size=alt.Size("avaliacao_display:Q", legend=alt.Legend(title="Avaliação"), scale=alt.Scale(range=[80, 600])),
                color=alt.Color("avaliacao_display:Q", scale=alt.Scale(scheme="tealblues"), legend=None),
                tooltip=[
                    alt.Tooltip("atendente_nome:N", title="Atendente"),
                    alt.Tooltip("total:Q", title="Total"),
                    alt.Tooltip("duracao_media:Q", title="Duração média", format=".1f"),
                    alt.Tooltip("avaliacao_media:Q", title="Avaliação", format=".2f"),
                    alt.Tooltip("avaliacoes:Q", title="Qtd avaliações"),
                ],
            ).properties(height=340)
            st.altair_chart(chart_scatter, use_container_width=True)
            st.caption("Cada bolha = um atendente. Tamanho/cor = média de avaliação. Ideal: canto inferior-direito (alto volume + baixa duração).")

        # Tabela detalhada
        detalhe = att_stats.copy()
        detalhe["duracao_media"]   = detalhe["duracao_media"].apply(lambda v: f"{v:.1f} min" if pd.notna(v) else "—")
        detalhe["duracao_mediana"] = detalhe["duracao_mediana"].apply(lambda v: f"{v:.1f} min" if pd.notna(v) else "—")
        detalhe["avaliacao_media"] = detalhe["avaliacao_media"].apply(lambda v: f"{v:.2f}★" if pd.notna(v) else "—")
        detalhe = detalhe.rename(columns={
            "atendente_nome": "Atendente",
            "total": "Atendimentos",
            "duracao_media": "Duração média",
            "duracao_mediana": "Duração mediana",
            "avaliacao_media": "Avaliação",
            "avaliacoes": "Qtd avaliações",
            "msgs_enviadas": "Msgs enviadas",
        })
        st.dataframe(detalhe, hide_index=True, use_container_width=True)


# ── Análise de prazos ────────────────────────────────────────────────────────
with st.expander("⏱️ Análise de prazos e duração", expanded=True):
    if df_reais.empty:
        st.info("Sem atendimentos efetivos para análise de duração.")
    else:
        p1, p2 = st.columns(2)

        with p1:
            st.markdown("**Distribuição por faixa de duração**")
            ordem_faixas = ["Menos de 2 min", "2 a 10 min", "10 a 30 min", "30 a 60 min", "Mais de 1 hora"]
            faixa = df_reais.groupby("faixa_duracao").size().reset_index(name="quantidade")
            chart_faixa = alt.Chart(faixa).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#6366F1").encode(
                x=alt.X("faixa_duracao:N", sort=ordem_faixas, title=None),
                y=alt.Y("quantidade:Q", title="Atendimentos"),
                tooltip=[
                    alt.Tooltip("faixa_duracao:N", title="Faixa"),
                    alt.Tooltip("quantidade:Q", title="Qtd"),
                ],
            ).properties(height=240)
            st.altair_chart(chart_faixa, use_container_width=True)

        with p2:
            st.markdown("**Métricas de duração (em minutos)**")
            duracao_stats = df_reais["duracao_minutos"].describe()
            mp = st.columns(2)
            mp[0].metric("Mediana",  f"{duracao_stats['50%']:.1f} min")
            mp[1].metric("Média",    f"{duracao_stats['mean']:.1f} min")
            mp2 = st.columns(2)
            mp2[0].metric("P90",     f"{df_reais['duracao_minutos'].quantile(0.9):.1f} min")
            mp2[1].metric("Máximo",  f"{duracao_stats['max']:.1f} min")

            longos = len(df_reais[df_reais["duracao_minutos"] > 60])
            st.caption(f"📌 **{longos}** atendimentos excederam 1 hora de duração.")


# ── Análise temporal: horários e dias ────────────────────────────────────────
with st.expander("📅 Volume por dia e horário", expanded=True):
    t1, t2 = st.columns(2)

    with t1:
        st.markdown("**Distribuição por turno**")
        turno_stats = df_f.groupby("turno").size().reset_index(name="quantidade")
        ordem_turnos = ["Manhã", "Tarde", "Noite", "Madrugada"]
        chart_turno = alt.Chart(turno_stats).mark_arc(innerRadius=55, outerRadius=100).encode(
            theta="quantidade:Q",
            color=alt.Color("turno:N", sort=ordem_turnos, scale=alt.Scale(scheme="category10"), legend=alt.Legend(orient="right", title=None)),
            tooltip=[
                alt.Tooltip("turno:N", title="Turno"),
                alt.Tooltip("quantidade:Q", title="Qtd"),
            ],
        ).properties(height=240)
        st.altair_chart(chart_turno, use_container_width=True)

    with t2:
        st.markdown("**Volume por hora do dia**")
        hora_stats = df_f.groupby("hora_inicio").size().reset_index(name="quantidade")
        chart_hora = alt.Chart(hora_stats).mark_bar(color="#14B8A6", cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("hora_inicio:O", title="Hora"),
            y=alt.Y("quantidade:Q", title="Atendimentos"),
            tooltip=[
                alt.Tooltip("hora_inicio:O", title="Hora"),
                alt.Tooltip("quantidade:Q", title="Qtd"),
            ],
        ).properties(height=240)
        st.altair_chart(chart_hora, use_container_width=True)

    # Heatmap dia x hora
    st.markdown("**Mapa de calor: dia da semana × hora do dia**")
    dow_map = {0: "Dom", 1: "Seg", 2: "Ter", 3: "Qua", 4: "Qui", 5: "Sex", 6: "Sáb"}
    df_f["dia_semana_lbl"] = df_f["dia_semana_num"].map(dow_map)
    heat = df_f.groupby(["dia_semana_lbl", "hora_inicio"]).size().reset_index(name="quantidade")
    ordem_dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    chart_heat = alt.Chart(heat).mark_rect().encode(
        x=alt.X("hora_inicio:O", title="Hora"),
        y=alt.Y("dia_semana_lbl:N", sort=ordem_dias, title=None),
        color=alt.Color("quantidade:Q", scale=alt.Scale(scheme="blues"), title="Atendimentos"),
        tooltip=[
            alt.Tooltip("dia_semana_lbl:N", title="Dia"),
            alt.Tooltip("hora_inicio:O", title="Hora"),
            alt.Tooltip("quantidade:Q", title="Qtd"),
        ],
    ).properties(height=220)
    st.altair_chart(chart_heat, use_container_width=True)
    st.caption("Use este mapa para identificar janelas de pico e dimensionar turnos.")


# ── Qualidade ────────────────────────────────────────────────────────────────
with st.expander("⭐ Análise de qualidade (avaliações)", expanded=False):
    df_aval = df_f[df_f["rating"].notna()].copy()
    if df_aval.empty:
        st.info("Nenhum atendimento avaliado no período.")
    else:
        q1, q2, q3 = st.columns(3)
        q1.metric("Atendimentos avaliados", len(df_aval))
        q2.metric("Taxa de avaliação", f"{len(df_aval) / len(df_f) * 100:.1f}%")
        q3.metric("Nota média", f"{df_aval['rating'].mean():.2f} ★")

        dist_rating = df_aval.groupby("rating").size().reset_index(name="quantidade")
        chart_rating = alt.Chart(dist_rating).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("rating:O", title="Nota"),
            y=alt.Y("quantidade:Q", title="Atendimentos"),
            color=alt.Color("rating:O", scale=alt.Scale(scheme="redyellowgreen"), legend=None),
            tooltip=[
                alt.Tooltip("rating:O", title="Nota"),
                alt.Tooltip("quantidade:Q", title="Qtd"),
            ],
        ).properties(height=220)
        st.altair_chart(chart_rating, use_container_width=True)


# ── Rodapé com insights ──────────────────────────────────────────────────────
st.divider()
st.markdown('<div class="section-title">💡 Insights automáticos</div>', unsafe_allow_html=True)

insights: list[str] = []

if pct_abandono > 15:
    insights.append(f"⚠️ **Taxa de abandono alta** ({pct_abandono:.1f}%). Considere revisar o fluxo inicial do bot.")

if not df_reais.empty and pd.notna(dur_media) and dur_media > 30:
    insights.append(f"⏱️ **Duração média elevada** ({dur_media:.1f} min). Avalie treinamento ou roteiros de atendimento.")

if not df_reais.empty:
    heat_local = df_f.groupby(["dia_semana_num", "hora_inicio"]).size().reset_index(name="q")
    if not heat_local.empty:
        pico = heat_local.sort_values("q", ascending=False).iloc[0]
        dow_map2 = {0: "domingo", 1: "segunda", 2: "terça", 3: "quarta", 4: "quinta", 5: "sexta", 6: "sábado"}
        insights.append(
            f"📈 **Pico de demanda**: {dow_map2.get(int(pico['dia_semana_num']), '?')} às {int(pico['hora_inicio'])}h "
            f"com {int(pico['q'])} atendimentos. Priorize alocação nesse horário."
        )

if not df_reais.empty:
    dep_concentracao = df_reais["departamento_nome"].value_counts(normalize=True)
    if not dep_concentracao.empty and dep_concentracao.iloc[0] > 0.4:
        insights.append(
            f"🏢 **{dep_concentracao.index[0]}** concentra **{dep_concentracao.iloc[0]*100:.0f}%** "
            "dos atendimentos efetivos. Avalie reforço de equipe nesse departamento."
        )

if em_aberto > 0:
    insights.append(f"🔔 **{em_aberto}** atendimentos ainda em aberto — verifique se há pendências.")

if insights:
    for i in insights:
        st.markdown(f"- {i}")
else:
    st.success("Tudo dentro dos parâmetros esperados. 👍")
