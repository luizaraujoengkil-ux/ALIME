"""Tela 3 — Geração de viagens (Vou ou não vou?).

Lê vetores de produção (P) e atração (A) por zona, com detecção
automática de colunas e balanceamento robusto.

REGRA DE OURO do balanceamento:

    O fator é SEMPRE calculado a partir dos vetores ORIGINAIS,
    nunca a partir de valores já balanceados. As colunas-sombra
    `production_original` e `attraction_original` da DataFrame
    de zonas guardam essa referência fixa.

Isso garante que clicar "Aplicar balanceamento" 1, 2 ou N vezes
produz sempre o mesmo resultado (idempotente).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import ui_theme, validation, balancing, zones as zones_mod


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


def _render_balancing_summary(res: dict) -> None:
    """Cards + tabela comparativa após um balanceamento bem-sucedido."""
    method_label = {
        "ajustar_atracoes":      "Ajustar atrações para igualar produções",
        "ajustar_producoes":     "Ajustar produções para igualar atrações",
        "normalizar_para_total": "Normalizar ambos para total alvo",
        "manter_sem_balancear":  "Mantido sem balancear",
    }.get(res["method"], res["method"])

    ui_theme.ok(
        f"Vetores balanceados e salvos para a etapa de Distribuição.<br/>"
        f"Método aplicado: <b>{method_label}</b> | "
        f"fator: <b>{res['factor']:.6f}</b> | "
        f"ΣP original=<b>{res['sumP_original']:.1f}</b> | "
        f"ΣA original=<b>{res['sumA_original']:.1f}</b> | "
        f"ΣP final=<b>{res['sumP_final']:.1f}</b> | "
        f"ΣA final=<b>{res['sumA_final']:.1f}</b> | "
        f"erro relativo final=<b>{res['rel_error']*100:.3f}%</b>"
    )

    # 8 cards do balanceamento
    st.markdown("#### Indicadores do balanceamento")
    r1 = st.columns(4)
    with r1[0]: ui_theme.card("ΣP original",  f"{res['sumP_original']:,.1f}")
    with r1[1]: ui_theme.card("ΣA original",  f"{res['sumA_original']:,.1f}")
    with r1[2]:
        diff = res["sumP_original"] - res["sumA_original"]
        ui_theme.card("Diferença original", f"{diff:+,.1f}")
    with r1[3]:
        ui_theme.card("Fator aplicado", f"{res['factor']:.6f}")

    r2 = st.columns(4)
    with r2[0]: ui_theme.card("ΣP final",     f"{res['sumP_final']:,.1f}")
    with r2[1]: ui_theme.card("ΣA final",     f"{res['sumA_final']:,.1f}")
    with r2[2]: ui_theme.card("Erro relativo", f"{res['rel_error']*100:.3f}%")
    with r2[3]:
        status = "Balanceado" if res["rel_error"] < 0.001 else "Não balanceado"
        ui_theme.card("Status", status)


def _render_compare_table(zones_df: pd.DataFrame, res: dict) -> None:
    """Tabela lado a lado: original vs balanceado."""
    df = pd.DataFrame({
        "zone_id":              zones_df["zone_id"].astype(str).values,
        "zone_name":            zones_df["zone_name"].fillna("").astype(str).values,
        "production_original":  pd.to_numeric(zones_df["production_original"], errors="coerce").fillna(0).round(2).values,
        "attraction_original":  pd.to_numeric(zones_df["attraction_original"], errors="coerce").fillna(0).round(2).values,
        "production_balanced":  np.round(res["P"], 2),
        "attraction_balanced":  np.round(res["A"], 2),
    })
    df["balance_method"] = res["method"]
    df["factor_applied"] = round(res["factor"], 6)

    st.markdown("#### Comparação original × balanceado")
    st.dataframe(df, use_container_width=True)


def render() -> None:
    ui_theme.section_title(3, "Geração — Vou ou não vou?")
    st.markdown(
        "<p style='color:#B8C0CC'>"
        "Cada zona produz (P) e atrai (A) viagens. Aqui você carrega ou edita "
        "esses vetores e, se necessário, balanceia para que ΣP = ΣA. "
        "<b>Importante:</b> o balanceamento sempre usa os valores "
        "<i>originais</i> como referência, então clicar várias vezes é seguro."
        "</p>", unsafe_allow_html=True,
    )

    zones_df = st.session_state.get("zones")
    if zones_df is None or zones_df.empty:
        ui_theme.warn("Cadastre as zonas primeiro (aba 2. Zonas).")
        return

    # Garante que originais existam
    if "production_original" not in zones_df.columns or "attraction_original" not in zones_df.columns:
        zones_df = zones_mod._coerce(zones_df)
        st.session_state["zones"] = zones_df

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
                        # Esses são os novos ORIGINAIS — refresca a baseline
                        df2 = df2.reset_index()
                        df2 = zones_mod.reset_originals(zones_mod._coerce(df2))
                        st.session_state["zones"] = df2
                        st.session_state["balancing"] = None
                        ui_theme.ok("Vetores aplicados e marcados como originais. "
                                     "Clique em **Aplicar balanceamento** abaixo.")

    with tab_table:
        edit = st.data_editor(
            zones_df[["zone_id", "zone_name", "population", "production", "attraction"]],
            num_rows="fixed",
            use_container_width=True,
            key="gen_editor",
        )
        if st.button("💾 Salvar vetores"):
            zdf = zones_df.copy()
            for col in ("population", "production", "attraction"):
                zdf[col] = validation.numeric_clean(edit[col])
            # Salvar manualmente = nova baseline
            zdf = zones_mod.reset_originals(zones_mod._coerce(zdf))
            st.session_state["zones"] = zdf
            st.session_state["balancing"] = None
            zones_df = zdf
            ui_theme.ok("Vetores salvos com sucesso. Valores marcados como originais para o balanceamento.")

    # =====================================================
    # Resumo dos vetores ORIGINAIS (referência fixa)
    # =====================================================
    P_orig = pd.to_numeric(zones_df["production_original"], errors="coerce").fillna(0).to_numpy()
    A_orig = pd.to_numeric(zones_df["attraction_original"], errors="coerce").fillna(0).to_numpy()
    sumP_orig = float(P_orig.sum())
    sumA_orig = float(A_orig.sum())
    diff = sumP_orig - sumA_orig
    rel = abs(diff) / max(sumP_orig, sumA_orig, 1e-9)

    st.markdown("### Resumo dos vetores originais")
    c1, c2, c3, c4 = st.columns(4)
    with c1: ui_theme.card("Σ Produção (original)", f"{sumP_orig:,.1f}")
    with c2: ui_theme.card("Σ Atração (original)",  f"{sumA_orig:,.1f}")
    with c3: ui_theme.card("Diferença",             f"{diff:+,.1f}")
    with c4:
        status = "Balanceado" if rel < 0.01 else ("Quase balanceado" if rel < 0.05 else "Desbalanceado")
        ui_theme.card("Status original", status)

    if rel >= 0.01:
        ui_theme.warn("As produções e atrações ORIGINAIS não estão balanceadas. "
                       "Escolha um método abaixo.")

    # =====================================================
    # Balanceamento
    # =====================================================
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
    )
    target = None
    if method == "normalizar_para_total":
        target = st.number_input("Total alvo (T)",
                                  value=float(max(sumP_orig, sumA_orig, 1.0)),
                                  step=100.0)

    if st.button("⚙ Aplicar balanceamento"):
        # SEMPRE usa originais — nunca os valores atuais que podem já estar
        # balanceados de uma execução anterior.
        res = balancing.balance_vectors(P_orig, A_orig,
                                         method=method, target_total=target)

        zdf = zones_df.copy()
        zdf["production"] = res["P"]
        zdf["attraction"] = res["A"]
        # production_original e attraction_original ficam INTACTOS

        st.session_state["zones"] = zdf
        st.session_state["balancing"] = {
            "method":         res["method"],
            "factor":         res["factor"],
            "sumP_original":  res["sumP_original"],
            "sumA_original":  res["sumA_original"],
            "sumP_final":     res["sumP_final"],
            "sumA_final":     res["sumA_final"],
            "diff_original":  res["diff_original"],
            "rel_error":      res["rel_error"],
            "applied":        True,
        }

        # Validação automática usando o módulo validation
        chk = validation.validate_balancing(
            P_orig, A_orig, res["P"], res["A"], res["method"]
        )
        if not chk["ok"]:
            ui_theme.warn(
                "Validação detectou inconsistências:<br/>" +
                "<br/>".join(f"• {m}" for m in chk["messages"])
            )

        _render_balancing_summary(res)
        _render_compare_table(zdf, res)

    else:
        # Se um balanceamento anterior estiver guardado, mostra o resumo
        # mesmo sem clicar de novo.
        prev = st.session_state.get("balancing")
        if prev and prev.get("applied"):
            P_cur = pd.to_numeric(zones_df["production"], errors="coerce").fillna(0).to_numpy()
            A_cur = pd.to_numeric(zones_df["attraction"], errors="coerce").fillna(0).to_numpy()
            res_view = {
                "method":        prev["method"],
                "factor":        prev["factor"],
                "sumP_original": prev["sumP_original"],
                "sumA_original": prev["sumA_original"],
                "sumP_final":    prev["sumP_final"],
                "sumA_final":    prev["sumA_final"],
                "diff_original": prev.get("diff_original",
                                          prev["sumP_original"] - prev["sumA_original"]),
                "rel_error":     prev["rel_error"],
                "P": P_cur, "A": A_cur,
            }
            st.markdown("---")
            st.markdown("#### Último balanceamento aplicado")
            _render_balancing_summary(res_view)
            _render_compare_table(zones_df, res_view)

    # =====================================================
    # Gráfico P × A por zona (sempre com os valores atuais)
    # =====================================================
    st.markdown("### Comparação P × A por zona (valores atuais)")
    fig = go.Figure()
    fig.add_bar(name="Produção",
                x=zones_df["zone_id"],
                y=validation.numeric_clean(zones_df["production"]),
                marker_color=ui_theme.PALETTE["yellow"])
    fig.add_bar(name="Atração",
                x=zones_df["zone_id"],
                y=validation.numeric_clean(zones_df["attraction"]),
                marker_color=ui_theme.PALETTE["orange"])
    fig.update_layout(
        barmode="group", template="plotly_dark",
        paper_bgcolor=ui_theme.PALETTE["bg_main"],
        plot_bgcolor=ui_theme.PALETTE["bg_second"],
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)
