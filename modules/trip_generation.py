"""Tela 3 — Geração de viagens (Vou ou não vou?).

Lê vetores de produção (P) e atração (A) por zona, com detecção
automática de colunas e balanceamento robusto.

=========================================================================
ESTRUTURA DE COLUNAS USADA NESTA ETAPA
=========================================================================

| Coluna                | Papel                                          |
|-----------------------|------------------------------------------------|
| production            | view editável (mesma coisa que *_original)     |
| attraction            | view editável (mesma coisa que *_original)     |
| production_original   | snapshot fixo do input do usuário              |
| attraction_original   | snapshot fixo do input do usuário              |
| production_balanced   | output do motor de balanceamento (idempotente) |
| attraction_balanced   | output do motor de balanceamento (idempotente) |
| balance_method        | método aplicado (string)                       |
| factor_applied        | fator multiplicativo aplicado                  |

REGRA DE OURO: o motor matemático SEMPRE usa `*_original` como entrada
e SEMPRE escreve em `*_balanced` como saída. Nunca toca em `*_original`.
Isso garante idempotência (clicar Aplicar 100x = clicar 1x).
=========================================================================
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
        ui_theme.error_message(f"Erro ao ler arquivo: {e}")
    return None


def _method_label(method: str) -> str:
    return {
        "ajustar_atracoes":      "Ajustar atrações para igualar produções",
        "ajustar_producoes":     "Ajustar produções para igualar atrações",
        "normalizar_para_total": "Normalizar ambos para total alvo",
        "manter_sem_balancear":  "Mantido sem balancear",
    }.get(method, method)


def _render_balancing_cards(b: dict) -> None:
    """Cards de indicadores do balanceamento. `b` vem do session_state."""
    st.markdown("#### Indicadores do balanceamento")

    r1 = st.columns(4)
    with r1[0]: ui_theme.card("Método aplicado", _method_label(b["method"]))
    with r1[1]: ui_theme.card("Fator aplicado", f"{b['factor']:.6f}")
    with r1[2]: ui_theme.card("Σ P final", f"{b['sumP_final']:,.1f}")
    with r1[3]: ui_theme.card("Σ A final", f"{b['sumA_final']:,.1f}")

    r2 = st.columns(4)
    with r2[0]: ui_theme.card("Erro relativo final", f"{b['rel_error']*100:.3f}%")
    with r2[1]:
        status = "Balanceado" if b["rel_error"] < 0.001 else "Não balanceado"
        ui_theme.card("Status final", status)
    with r2[2]: ui_theme.card("ΔΣ original", f"{b['diff_original']:+,.1f}")
    with r2[3]:
        if b["sumA_original"] > 0:
            check = (b["sumA_final"] / b["sumA_original"]) if b["method"] == "ajustar_atracoes" else b["factor"]
        else:
            check = float("nan")
        ui_theme.card("Verificação fator", f"{check:.6f}")


def _render_compare_table(zones_df: pd.DataFrame, b: dict | None) -> None:
    """Tabela lado a lado com as 4 colunas + metadados do balanceamento."""
    df = pd.DataFrame({
        "zone_id":              zones_df["zone_id"].astype(str).values,
        "zone_name":            zones_df["zone_name"].fillna("").astype(str).values,
        "population":           pd.to_numeric(zones_df.get("population"), errors="coerce").fillna(0).astype(int).values,
        "production_original":  pd.to_numeric(zones_df["production_original"], errors="coerce").fillna(0).round(2).values,
        "attraction_original":  pd.to_numeric(zones_df["attraction_original"], errors="coerce").fillna(0).round(2).values,
        "production_balanced":  pd.to_numeric(zones_df["production_balanced"], errors="coerce").fillna(0).round(2).values,
        "attraction_balanced":  pd.to_numeric(zones_df["attraction_balanced"], errors="coerce").fillna(0).round(2).values,
    })
    if b:
        df["balance_method"] = b["method"]
        df["factor_applied"] = round(b["factor"], 6)
    else:
        df["balance_method"] = "—"
        df["factor_applied"] = pd.NA

    st.markdown("#### Tabela de zonas — original × balanceado")
    st.dataframe(df, use_container_width=True)


def render() -> None:
    ui_theme.section_title(3, "Geração — Vou ou não vou?")
    ui_theme.info(
        "O balanceamento sempre usa os valores <b>originais</b> como referência. "
        "Portanto, clicar várias vezes em <b>Aplicar balanceamento</b> é seguro — "
        "o resultado é sempre o mesmo. Os valores <i>originais</i> nunca são "
        "sobrescritos: a saída do motor matemático fica em colunas separadas "
        "(<code>production_balanced</code> / <code>attraction_balanced</code>)."
    )

    zones_df = st.session_state.get("zones")
    if zones_df is None or zones_df.empty:
        ui_theme.warning_message("Cadastre as zonas primeiro (aba 2. Zonas).")
        return

    # Migração automática para o novo esquema, se necessário
    if any(c not in zones_df.columns for c in (
        "production_original", "attraction_original",
        "production_balanced", "attraction_balanced",
        "balance_method", "factor_applied",
    )):
        zones_df = zones_mod._coerce(zones_df)
        st.session_state["zones"] = zones_df

    tab_table, tab_import = st.tabs(["Tabela", "Importar arquivo"])

    # =====================================================
    # Aba IMPORTAR
    # =====================================================
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
                        ui_theme.error_message("Selecione ao menos a coluna zone_id.")
                    else:
                        df2 = zones_df.set_index("zone_id").copy()
                        raw_idx = raw.set_index(sel_id)
                        if sel_p != "—":
                            df2["production"] = validation.numeric_clean(raw_idx[sel_p])
                        if sel_a != "—":
                            df2["attraction"] = validation.numeric_clean(raw_idx[sel_a])
                        if sel_pop != "—":
                            df2["population"] = validation.numeric_clean(raw_idx[sel_pop])
                        df2 = df2.reset_index()
                        df2 = zones_mod.reset_all_layers(zones_mod._coerce(df2))
                        st.session_state["zones"] = df2
                        st.session_state["balancing"] = None
                        ui_theme.clear_status("balancing_applied")
                        ui_theme.clear_status("od_matrix_generated")
                        ui_theme.remember_status(
                            "vectors_saved", "success",
                            "Vetores importados e marcados como originais. "
                            "Clique em <b>Aplicar balanceamento</b> abaixo."
                        )

    # =====================================================
    # Aba TABELA (edição manual)
    # =====================================================
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
            zdf = zones_mod.reset_all_layers(zones_mod._coerce(zdf))
            st.session_state["zones"] = zdf
            st.session_state["balancing"] = None
            zones_df = zdf
            ui_theme.clear_status("balancing_applied")
            ui_theme.clear_status("od_matrix_generated")
            ui_theme.remember_status(
                "vectors_saved", "success",
                "Vetores de produção e atração salvos com sucesso."
            )

        ui_theme.show_status("vectors_saved")

    # =====================================================
    # Resumo dos vetores ORIGINAIS (sempre fixos, nunca mudam)
    # =====================================================
    P_orig = pd.to_numeric(zones_df["production_original"], errors="coerce").fillna(0).to_numpy()
    A_orig = pd.to_numeric(zones_df["attraction_original"], errors="coerce").fillna(0).to_numpy()
    sumP_orig = float(P_orig.sum())
    sumA_orig = float(A_orig.sum())
    diff = sumP_orig - sumA_orig
    rel_orig = abs(diff) / max(sumP_orig, sumA_orig, 1e-9)

    st.markdown("### Resumo dos vetores originais")
    c1, c2, c3, c4 = st.columns(4)
    with c1: ui_theme.card("Σ Produção original", f"{sumP_orig:,.1f}")
    with c2: ui_theme.card("Σ Atração original",  f"{sumA_orig:,.1f}")
    with c3: ui_theme.card("Diferença original",  f"{diff:+,.1f}")
    with c4:
        status_orig = ("Balanceado" if rel_orig < 0.01
                       else "Quase balanceado" if rel_orig < 0.05
                       else "Desbalanceado")
        ui_theme.card("Status original", status_orig)

    if rel_orig >= 0.01:
        ui_theme.warning_message("As produções e atrações <b>originais</b> não estão "
                                  "balanceadas. Escolha um método abaixo.")

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
        # SEMPRE usa originais — proteção contra acumular fator
        res = balancing.balance_vectors(P_orig, A_orig,
                                         method=method, target_total=target)

        # Escreve APENAS nas colunas _balanced. *_original ficam intactas.
        zdf = zones_df.copy()
        zdf["production_balanced"] = res["P"]
        zdf["attraction_balanced"] = res["A"]
        zdf["balance_method"] = res["method"]
        zdf["factor_applied"] = round(res["factor"], 10)
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

        # Validação automática
        chk = validation.validate_balancing(
            P_orig, A_orig, res["P"], res["A"], res["method"]
        )
        if chk["ok"]:
            ui_theme.remember_status(
                "balancing_applied", "success",
                "Vetores balanceados e salvos para a etapa de Distribuição."
            )
        else:
            ui_theme.remember_status(
                "balancing_applied", "warning",
                "Balanceamento aplicado mas com inconsistências:<br/>"
                + "<br/>".join(f"• {m}" for m in chk["messages"])
            )
        # Invalida etapas posteriores
        ui_theme.clear_status("od_matrix_generated")

    # Cards e tabela: usar o balanceamento persistido se existir
    b = st.session_state.get("balancing")
    if b and b.get("applied"):
        ui_theme.show_status("balancing_applied")
        _render_balancing_cards(b)
        _render_compare_table(zones_df, b)
    else:
        # Pré-balanceamento: mostra tabela com *_balanced == *_original
        _render_compare_table(zones_df, None)

    # =====================================================
    # Gráfico P × A por zona
    # =====================================================
    st.markdown("### Comparação P × A por zona")
    show_balanced = st.checkbox(
        "Mostrar valores balanceados (em vez dos originais)",
        value=bool(b and b.get("applied")),
    )

    if show_balanced:
        y_p = pd.to_numeric(zones_df["production_balanced"], errors="coerce").fillna(0)
        y_a = pd.to_numeric(zones_df["attraction_balanced"], errors="coerce").fillna(0)
        suffix = " (balanceados)"
    else:
        y_p = pd.to_numeric(zones_df["production_original"], errors="coerce").fillna(0)
        y_a = pd.to_numeric(zones_df["attraction_original"], errors="coerce").fillna(0)
        suffix = " (originais)"

    fig = go.Figure()
    fig.add_bar(name=f"Produção{suffix}",
                x=zones_df["zone_id"], y=y_p,
                marker_color=ui_theme.PALETTE["yellow"])
    fig.add_bar(name=f"Atração{suffix}",
                x=zones_df["zone_id"], y=y_a,
                marker_color=ui_theme.PALETTE["orange"])
    fig.update_layout(
        barmode="group", template="plotly_dark",
        paper_bgcolor=ui_theme.PALETTE["bg_main"],
        plot_bgcolor=ui_theme.PALETTE["bg_second"],
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)
