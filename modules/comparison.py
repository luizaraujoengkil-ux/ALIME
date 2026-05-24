"""Tela de Comparação Multicenário.

Compara o cenário-base com até 5 cenários da biblioteca.
Indicadores principais (tempo, atraso, custo social, B/C) e mapas
qualitativos de melhoria/piora.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import ui_theme, social_cost as sc_mod


COLOR_WORSE = ["#7A0F0D", "#E53935", "#FF7A00", "#F5B700", "#888888"]
COLOR_BETTER = ["#1F6F2C", "#3ECF5E", "#28A8FF", "#888888", "#E53935"]


def _row(sc: dict, base: dict, params: dict) -> dict:
    ind = sc.get("assignment", {}) or {}
    indb = base.get("assignment", {}) or {}
    cost_now = sc_mod.social_cost(ind, params)
    cost_base = sc_mod.social_cost(indb, params)
    benefit = cost_base["annual_cost_brl"] - cost_now["annual_cost_brl"]
    cost_obra = float(sc.get("cost_estimate") or 0.0)
    payback = (cost_obra / benefit) if benefit > 0 else float("inf")
    ibc = (benefit / cost_obra) if cost_obra > 0 else (float("inf") if benefit > 0 else 0.0)
    return {
        "id": sc.get("scenario_id"),
        "nome": sc.get("name"),
        "tipo": sc.get("type"),
        "horizonte": sc.get("horizon_year"),
        "tempo médio (min)":       round(ind.get("avg_time_min", 0), 2),
        "dist média (km)":          round(ind.get("avg_dist_km", 0), 3),
        "Σ viagens":                round(ind.get("total_trips", 0), 0),
        "veh·km":                   round(ind.get("veh_km", 0), 0),
        "atraso (min·pessoa)":      round(ind.get("delay_total_min", 0), 0),
        "custo social anual (R$)":  round(cost_now["annual_cost_brl"], 0),
        "benefício anual (R$)":     round(benefit, 0),
        "custo obra (R$)":          round(cost_obra, 0),
        "payback (anos)":           "∞" if payback == float("inf") else round(payback, 2),
        "B/C":                      "∞" if ibc == float("inf") else round(ibc, 3),
    }


def render() -> None:
    from . import workflow
    if not workflow.render_guard("comparacao"):
        return
    ui_theme.section_title("📊", "Comparação Multicenário")
    ui_theme.disclaimer_box()

    base = st.session_state.get("base_scenario")
    favs = st.session_state.get("favorite_scenarios", [])

    if base is None:
        ui_theme.warning_message("Gere o cenário-base antes (8. Cenários → Cenário-base).")
        return
    if not favs:
        ui_theme.info("Salve cenários na <b>Biblioteca</b> para compará-los aqui.")
        if st.button("✓ Confirmar: comparação não será realizada neste estudo",
                      use_container_width=True):
            workflow.mark_skipped(
                "comparacao",
                "Etapa marcada como concluída sem cenários para comparar."
            )
        ui_theme.show_status("skip_comparacao")
        return

    params = st.session_state["params"]
    rows = [_row(base, base, params)]
    for sc in favs:
        rows.append(_row(sc, base, params))
    df = pd.DataFrame(rows)

    st.markdown("### Tabela comparativa")
    st.dataframe(df, use_container_width=True)

    # Ranking
    st.markdown("### Rankings")
    cc = st.columns(4)
    with cc[0]:
        try:
            best_time = df.iloc[1:].nsmallest(1, "tempo médio (min)")
            ui_theme.card("Melhor por tempo", best_time.iloc[0]["nome"] if not best_time.empty else "—")
        except Exception:
            ui_theme.card("Melhor por tempo", "—")
    with cc[1]:
        try:
            best_ben = df.iloc[1:].nlargest(1, "benefício anual (R$)")
            ui_theme.card("Maior benefício", best_ben.iloc[0]["nome"] if not best_ben.empty else "—")
        except Exception:
            ui_theme.card("Maior benefício", "—")
    with cc[2]:
        try:
            df_bc = df.iloc[1:].copy()
            df_bc["B/C_num"] = pd.to_numeric(df_bc["B/C"], errors="coerce")
            best_bc = df_bc.dropna(subset=["B/C_num"]).nlargest(1, "B/C_num")
            ui_theme.card("Melhor B/C", best_bc.iloc[0]["nome"] if not best_bc.empty else "—")
        except Exception:
            ui_theme.card("Melhor B/C", "—")
    with cc[3]:
        try:
            worst = df.iloc[1:].nlargest(1, "atraso (min·pessoa)")
            ui_theme.card("Cenário mais crítico", worst.iloc[0]["nome"] if not worst.empty else "—")
        except Exception:
            ui_theme.card("Cenário mais crítico", "—")

    # Gráficos
    st.markdown("### Gráficos")
    g1, g2 = st.columns(2)
    with g1:
        fig = px.bar(df, x="nome", y="tempo médio (min)",
                     color="tipo", color_discrete_sequence=px.colors.qualitative.Vivid)
        fig.update_layout(template="plotly_dark",
                          paper_bgcolor=ui_theme.PALETTE["bg_main"],
                          plot_bgcolor=ui_theme.PALETTE["bg_second"],
                          height=380, title="Tempo médio por cenário")
        st.plotly_chart(fig, use_container_width=True)
    with g2:
        fig = px.bar(df, x="nome", y="custo social anual (R$)",
                     color="tipo", color_discrete_sequence=px.colors.qualitative.Vivid)
        fig.update_layout(template="plotly_dark",
                          paper_bgcolor=ui_theme.PALETTE["bg_main"],
                          plot_bgcolor=ui_theme.PALETTE["bg_second"],
                          height=380, title="Custo social anual por cenário")
        st.plotly_chart(fig, use_container_width=True)

    g3, g4 = st.columns(2)
    with g3:
        fig = px.bar(df, x="nome", y="benefício anual (R$)",
                     color="tipo", color_discrete_sequence=px.colors.qualitative.Vivid)
        fig.update_layout(template="plotly_dark",
                          paper_bgcolor=ui_theme.PALETTE["bg_main"],
                          plot_bgcolor=ui_theme.PALETTE["bg_second"],
                          height=380, title="Benefício anual estimado")
        st.plotly_chart(fig, use_container_width=True)
    with g4:
        df_bc = df.copy()
        df_bc["B/C_num"] = pd.to_numeric(df_bc["B/C"], errors="coerce").fillna(0)
        fig = px.bar(df_bc, x="nome", y="B/C_num",
                     color="tipo", color_discrete_sequence=px.colors.qualitative.Vivid)
        fig.update_layout(template="plotly_dark",
                          paper_bgcolor=ui_theme.PALETTE["bg_main"],
                          plot_bgcolor=ui_theme.PALETTE["bg_second"],
                          height=380, title="Índice benefício/custo (preliminar)")
        st.plotly_chart(fig, use_container_width=True)
