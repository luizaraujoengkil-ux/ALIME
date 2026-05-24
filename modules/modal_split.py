"""Tela 5 — Repartição modal (Como vou?).

Distribui T_ij por modos de transporte. No modo básico, uma participação
global s_m é aplicada a toda a matriz; no avançado, é possível variar
por zona ou por par O-D (esta versão implementa o modo básico).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from . import ui_theme, validation


MODES = [
    "veiculo_leve",
    "veiculo_pesado",
    "transporte_coletivo",
    "a_pe",
    "bicicleta",
    "outros",
]

MODE_LABEL = {
    "veiculo_leve":        "Veículo leve",
    "veiculo_pesado":      "Veículo pesado",
    "transporte_coletivo": "Transporte coletivo",
    "a_pe":                "A pé",
    "bicicleta":           "Bicicleta",
    "outros":              "Outros",
}


def split_matrix(T: np.ndarray, shares: dict[str, float]) -> dict[str, np.ndarray]:
    """Aplica T_ij^m = T_ij · s_m por modo. Os percentuais são normalizados se
    não somarem 1.
    """
    s, _ = validation.percentages_normalize(shares)
    return {m: T * s.get(m, 0.0) for m in s}


def render() -> None:
    ui_theme.section_title(5, "Repartição Modal — Como vou?")
    st.markdown(
        "<p style='color:#B8C0CC'>Defina como as viagens da matriz O-D se distribuem "
        "entre os modos. No modo básico, o percentual é global. No modo avançado, "
        "você pode personalizar por zona ou par O-D (em versões futuras).</p>",
        unsafe_allow_html=True,
    )

    T = st.session_state.get("od_matrix")
    if T is None:
        ui_theme.warning_message("Gere a matriz O-D primeiro (aba 4. Distribuição).")
        return

    shares = dict(st.session_state["modal_split"])
    cc = st.columns(3)
    for i, m in enumerate(MODES):
        with cc[i % 3]:
            shares[m] = st.number_input(
                MODE_LABEL[m],
                min_value=0.0, max_value=1.0,
                value=float(shares.get(m, 0.0)), step=0.01,
                format="%.2f",
            )

    total = sum(shares.values())
    if abs(total - 1.0) > 0.01:
        ui_theme.warn(f"A soma dos percentuais é {total*100:.1f}%. Será normalizada para 100%.")

    if st.button("⚙ Aplicar repartição"):
        norm, was = validation.percentages_normalize(shares)
        st.session_state["modal_split"] = norm
        mats = split_matrix(T, norm)
        st.session_state["modal_matrices"] = mats
        ui_theme.remember_status(
            "modal_applied", "success",
            "Repartição modal aplicada com sucesso. Matrizes por modo geradas."
        )

    ui_theme.show_status("modal_applied")

    norm = st.session_state["modal_split"]
    mats = st.session_state.get("modal_matrices") or split_matrix(T, norm)

    # Tabela
    rows = []
    for m, mat in mats.items():
        rows.append({"Modo": MODE_LABEL[m], "Participação": norm.get(m, 0.0), "Σ viagens": float(mat.sum())})
    df = pd.DataFrame(rows)
    st.dataframe(df.style.format({"Participação": "{:.1%}", "Σ viagens": "{:,.0f}"}),
                 use_container_width=True)

    # Gráficos
    c1, c2 = st.columns(2)
    with c1:
        fig = px.pie(df, names="Modo", values="Σ viagens", hole=0.45)
        fig.update_layout(template="plotly_dark",
                          paper_bgcolor=ui_theme.PALETTE["bg_main"],
                          height=400)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = px.bar(df, x="Modo", y="Σ viagens",
                      color="Modo", color_discrete_sequence=px.colors.qualitative.Vivid)
        fig2.update_layout(template="plotly_dark",
                           paper_bgcolor=ui_theme.PALETTE["bg_main"],
                           plot_bgcolor=ui_theme.PALETTE["bg_second"],
                           height=400, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
