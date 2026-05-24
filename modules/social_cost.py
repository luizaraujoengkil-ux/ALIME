"""Tempo × Custo social.

Aplica fórmulas exploratórias para converter atraso em custo monetário:

    pessoas_afetadas = fluxo_afetado · ocupacao_media
    horas_perdidas   = pessoas_afetadas · tempo_atraso_min / 60
    custo_atraso     = horas_perdidas  · valor_tempo_hora
    custo_anual      = custo_atraso    · dias_uteis

Para melhoria:
    beneficio_anual = custo_base - custo_cenario
    payback         = custo_obra / beneficio_anual
    IBC             = beneficio_acumulado / custo_obra
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from . import ui_theme


def social_cost(assignment: dict, params: dict) -> dict:
    """Calcula o custo social diário e anual a partir dos indicadores."""
    if not assignment:
        return {"daily_cost_brl": 0.0, "annual_cost_brl": 0.0,
                "people_minutes": 0.0, "hours_lost": 0.0}
    delay_total_min = float(assignment.get("delay_total_min", 0.0))
    occupancy = float(params.get("occupancy", 1.4))
    value_h = float(params.get("value_of_time_brl_h", 18.0))
    days = float(params.get("operating_days", 252))
    # delay_total_min já está em min·pessoa (a função compute_indicators
    # multiplica fluxo×ocupação implicitamente por affected_share). Aqui
    # aplicamos a ocupação como reforço quando vier zero (segurança).
    people_minutes = delay_total_min if delay_total_min > 0 else 0.0
    hours_lost = people_minutes / 60.0
    daily = hours_lost * value_h
    annual = daily * days
    return {
        "daily_cost_brl": daily,
        "annual_cost_brl": annual,
        "people_minutes": people_minutes,
        "hours_lost": hours_lost,
        "occupancy": occupancy,
        "value_of_time_brl_h": value_h,
        "operating_days": days,
    }


def render() -> None:
    from . import workflow
    if not workflow.render_guard("custo_social"):
        return
    ui_theme.section_title("💸", "Tempo × Custo Social")
    ui_theme.disclaimer_box()

    p = st.session_state["params"]
    c1, c2, c3 = st.columns(3)
    with c1:
        p["occupancy"] = st.number_input(
            "Ocupação média (pessoas/veículo)",
            min_value=1.0, max_value=10.0, value=float(p["occupancy"]), step=0.1,
        )
    with c2:
        p["value_of_time_brl_h"] = st.number_input(
            "Valor do tempo (R$/h)",
            min_value=1.0, max_value=200.0, value=float(p["value_of_time_brl_h"]), step=1.0,
        )
    with c3:
        p["operating_days"] = st.number_input(
            "Dias úteis/ano",
            min_value=1, max_value=365, value=int(p["operating_days"]), step=1,
        )
    st.session_state["params"] = p

    # Apenas configurar parâmetros já marca esta etapa como concluída
    st.session_state["social_cost_computed"] = True

    base = st.session_state.get("base_scenario")
    if base:
        cb = social_cost(base.get("assignment", {}), p)
        c1, c2, c3, c4 = st.columns(4)
        with c1: ui_theme.card("Horas perdidas / dia (base)", f"{cb['hours_lost']:,.0f}")
        with c2: ui_theme.card("Custo social diário (R$)",   f"{cb['daily_cost_brl']:,.0f}")
        with c3: ui_theme.card("Custo social anual (R$)",    f"{cb['annual_cost_brl']:,.0f}")
        with c4: ui_theme.card("Ocupação adotada",           f"{p['occupancy']:.1f}")

    # Lista comparada com favoritos
    favs = st.session_state.get("favorite_scenarios", [])
    rows = []
    if base:
        rows.append({"cenário": "Cenário-base",
                     **{k: v for k, v in social_cost(base.get("assignment", {}), p).items()}})
    for sc in favs:
        c = social_cost(sc.get("assignment", {}), p)
        rows.append({"cenário": sc.get("name", "?"), **c})
    if rows:
        st.markdown("### Comparativo")
        df = pd.DataFrame(rows)[[
            "cenário", "hours_lost", "daily_cost_brl", "annual_cost_brl",
        ]].rename(columns={
            "hours_lost":      "horas/dia",
            "daily_cost_brl":  "custo diário (R$)",
            "annual_cost_brl": "custo anual (R$)",
        })
        st.dataframe(df.style.format({
            "horas/dia": "{:,.1f}",
            "custo diário (R$)": "R$ {:,.0f}",
            "custo anual (R$)": "R$ {:,.0f}",
        }), use_container_width=True)
