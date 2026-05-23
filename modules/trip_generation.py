"""Tela 3 — Geração de viagens (Vou ou não vou?).

Lê vetores de produção (P) e atração (A) por zona, com detecção
automática de colunas e opções de balanceamento.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import ui_theme, validation, balancing


def _load_uploaded(up) -> pd.DataFrame | None:
    if up is None:
        return None
    name = up.name.lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(up)
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(up)
    except Exception as e:
        ui_theme.warn(f"Erro ao ler arquivo: {e}")
    return None


def render() -> None:
    ui_theme.section_title(3, "Geração — Vou ou não vou?")
    st.markdown(
        "<p style='color:#B8C0CC'>"
        "Cada zona produz (P) e atrai (A) viagens. Aqui você carrega ou edita "
        "esses vetores e, se necessário, balanceia para que ΣP = ΣA."
        "</p>", unsafe_allow_html=True,
    )

    zones_df = st.session_state.get("zones")
    if zones_df is None or zones_df.empty:
        ui_theme.warn("Cadastre as zonas primeiro (aba 2. Zonas).")
        return

    tab_table, tab_import = st.tabs(["Tabela", "Importar arquivo"])

    with tab_import:
        up = st.file_uploader("CSV ou Excel com colunas (zona, produção, atração, …)",
                              type=["csv", "xlsx", "xls"])
        if up is not None:
            raw = _load_uploaded(up)
            if raw is not None:
                st.dataframe(raw.head(10), use_container_width=True)
                det = validation.detect_columns(raw, ["zone_id", "production", "attraction", "population"])
                st.markdown("**Mapeamento detectado:**")
                cc = st.columns(4)
                with cc[0]:
                    sel_id = st.selectbox("zone_id", ["—"] + list(raw.columns),
                                          index=(list(raw.columns).index(det["zone_id"]) + 1)
                                          if det["zone_id"] else 0, key="map_id")
                with cc[1]:
                    sel_p = st.selectbox("production", ["—"] + list(raw.columns),
                                         index=(list(raw.columns).index(det["production"]) + 1)
                                         if det["production"] else 0, key="map_p")
                with cc[2]:
                    sel_a = st.selectbox("attraction", ["—"] + list(raw.columns),
                                         index=(list(raw.columns).index(det["attraction"]) + 1)
                                         if det["attraction"] else 0, key="map_a")
                with cc[3]:
                    sel_pop = st.selectbox("population", ["—"] + list(raw.columns),
                                           index=(list(raw.columns).index(det["population"]) + 1)
                                           if det["population"] else 0, key="map_pop")
                if st.button("Aplicar à tabela de zonas"):
                    if sel_id == "—":
                        ui_theme.warn("Selecione ao menos a coluna zone_id.")
                    else:
                        df2 = zones_df.set_index("zone_id").copy()
                        raw_idx = raw.set_index(sel_id)
                        if sel_p != "—":
                            df2["production"] = validation.numeric_clean(raw_idx[sel_p])
                        if sel_a != "—":
                            df2["attraction"] = validation.numeric_clean(raw_idx[sel_a])
                        if sel_pop != "—":
                            df2["population"] = validation.numeric_clean(raw_idx[sel_pop])
                        st.session_state["zones"] = df2.reset_index()
                        ui_theme.ok("Vetores aplicados.")

    with tab_table:
        edit = st.data_editor(
            zones_df[["zone_id", "zone_name", "population", "production", "attraction"]],
            num_rows="fixed",
            use_container_width=True,
            key="gen_editor",
        )
        if st.button("💾 Salvar vetores"):
            for col in ("population", "production", "attraction"):
                zones_df[col] = validation.numeric_clean(edit[col])
            st.session_state["zones"] = zones_df
            ui_theme.ok("Vetores salvos.")

    # ---- Resumo + Balanceamento ----
    P = validation.numeric_clean(zones_df["production"]).to_numpy()
    A = validation.numeric_clean(zones_df["attraction"]).to_numpy()
    sumP, sumA = float(P.sum()), float(A.sum())
    diff = sumP - sumA
    rel = abs(diff) / max(sumP, sumA, 1e-9)

    st.markdown("### Resumo")
    c1, c2, c3, c4 = st.columns(4)
    with c1: ui_theme.card("Σ Produção", f"{sumP:,.0f}")
    with c2: ui_theme.card("Σ Atração", f"{sumA:,.0f}")
    with c3: ui_theme.card("Diferença", f"{diff:+,.0f}")
    with c4:
        status = "Balanceado" if rel < 0.01 else ("Quase balanceado" if rel < 0.05 else "Desbalanceado")
        ui_theme.card("Status", status)

    if rel >= 0.01:
        ui_theme.warn("As produções e atrações não estão balanceadas. Escolha um método abaixo.")

    st.markdown("### Balanceamento")
    method = st.radio(
        "Método",
        [
            "ajustar_atracoes",
            "ajustar_producoes",
            "normalizar_para_total",
            "manter_sem_balancear",
        ],
        format_func=lambda x: {
            "ajustar_atracoes":      "1. Ajustar atrações para igualar produções",
            "ajustar_producoes":     "2. Ajustar produções para igualar atrações",
            "normalizar_para_total": "3. Normalizar ambos para um total alvo",
            "manter_sem_balancear":  "4. Manter sem balancear (com aviso)",
        }[x],
        horizontal=False,
    )
    target = None
    if method == "normalizar_para_total":
        target = st.number_input("Total alvo (T)", value=float(max(sumP, sumA, 1.0)), step=100.0)

    if st.button("⚙ Aplicar balanceamento"):
        res = balancing.balance_vectors(P, A, method=method, target_total=target)
        zones_df = st.session_state["zones"].copy()
        zones_df["production"] = res["P"]
        zones_df["attraction"] = res["A"]
        st.session_state["zones"] = zones_df
        ui_theme.ok(
            f"Método aplicado: **{res['method']}** | fator: **{res['factor']:.4f}** | "
            f"ΣP={res['sumP_final']:.1f} / ΣA={res['sumA_final']:.1f} | "
            f"erro relativo final: **{res['rel_error']*100:.3f}%**"
        )

    # Gráfico P × A
    st.markdown("### Comparação P × A por zona")
    fig = go.Figure()
    fig.add_bar(name="Produção", x=zones_df["zone_id"], y=validation.numeric_clean(zones_df["production"]),
                marker_color=ui_theme.PALETTE["yellow"])
    fig.add_bar(name="Atração",  x=zones_df["zone_id"], y=validation.numeric_clean(zones_df["attraction"]),
                marker_color=ui_theme.PALETTE["orange"])
    fig.update_layout(
        barmode="group", template="plotly_dark",
        paper_bgcolor=ui_theme.PALETTE["bg_main"],
        plot_bgcolor=ui_theme.PALETTE["bg_second"],
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)
