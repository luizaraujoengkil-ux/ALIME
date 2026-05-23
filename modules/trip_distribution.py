"""Tela 4 — Distribuição de viagens (Para onde vou?).

Implementa o modelo gravitacional normalizado por origem:

    T_ij = P_i · ( A_j · f(c_ij) ) / Σ_j ( A_j · f(c_ij) )

onde:
    - T_ij  : viagens estimadas da origem i ao destino j
    - P_i   : produção balanceada da origem i
    - A_j   : atração balanceada do destino j
    - c_ij  : custo generalizado entre i e j
    - f(c)  : função de atrito (potência 1/c^β ou exponencial exp(-β·c))

Por construção, Σ_j T_ij = P_i (linha respeita a produção). As colunas
podem divergir de A_j; o erro é calculado e exibido.

Esta é uma versão exploratória, sem ajuste duplo (Furness).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from . import ui_theme, validation, map_utils


# ============================================================
# Núcleo matemático
# ============================================================
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Distância em quilômetros entre dois pontos lat/lon (fórmula de Haversine)."""
    R = 6371.0
    p1 = np.radians(lat1); p2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi/2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl/2) ** 2
    return float(2 * R * np.arcsin(np.sqrt(a)))


def distance_matrix(zones_df: pd.DataFrame) -> np.ndarray:
    """Matriz de distâncias (km) entre centroides."""
    lat = pd.to_numeric(zones_df["centroid_lat"], errors="coerce").to_numpy()
    lon = pd.to_numeric(zones_df["centroid_lon"], errors="coerce").to_numpy()
    n = len(lat)
    D = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            if i == j:
                D[i, j] = 0.0
            else:
                D[i, j] = haversine_km(lat[i], lon[i], lat[j], lon[j])
    return D


def impedance_from_distance(
    D: np.ndarray,
    speed_kmh: float = 35.0,
    extra_delay_min: np.ndarray | None = None,
    mode: str = "tempo",  # "distancia" | "tempo" | "custo_generalizado"
    min_distance_km: float = 0.3,
) -> np.ndarray:
    """Constrói a matriz de impedância c_ij.

    - "distancia": c_ij = max(d_ij, dmin)
    - "tempo":     c_ij = (d_ij / v) · 60  + atraso_extra
    - "custo_generalizado": tempo + atraso_extra (pesos α=1 nesta versão)
    """
    Dsafe = validation.safe_min_distance(D, min_distance_km)
    if mode == "distancia":
        return Dsafe
    t_mov = (Dsafe / max(speed_kmh, 1e-6)) * 60.0
    extra = extra_delay_min if extra_delay_min is not None else np.zeros_like(t_mov)
    return t_mov + extra


def friction(c: np.ndarray, beta: float, kind: str = "potencia") -> np.ndarray:
    """Função de atrito f(c)."""
    if kind == "potencia":
        return 1.0 / np.power(np.maximum(c, 1e-6), beta)
    if kind == "exponencial":
        return np.exp(-beta * c)
    raise ValueError(f"friction kind desconhecido: {kind}")


def gravity_distribution(
    productions: np.ndarray,
    attractions: np.ndarray,
    impedance_matrix: np.ndarray,
    beta: float = 2.0,
    friction_type: str = "potencia",
) -> np.ndarray:
    """Modelo gravitacional normalizado por origem.

    Matemática:
        f_ij = f(c_ij)
        T_ij = P_i · (A_j · f_ij) / Σ_j (A_j · f_ij)

    Garante que Σ_j T_ij = P_i.
    """
    P = np.asarray(productions, dtype=float)
    A = np.asarray(attractions, dtype=float)
    F = friction(impedance_matrix, beta, friction_type)
    n = len(P)
    np.fill_diagonal(F, 0.0)  # ignora viagens intra-zonais por padrão

    AF = A[np.newaxis, :] * F            # (n,n) — atração ponderada
    row_sums = AF.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums <= 0, 1.0, row_sums)  # evita /0
    T = P[:, np.newaxis] * (AF / row_sums)
    return T


def od_summary(T: np.ndarray, A_target: np.ndarray | None = None) -> dict:
    """Resumo da matriz O-D (totais e erro de coluna vs A alvo)."""
    sumT = float(T.sum())
    row_sum = T.sum(axis=1)
    col_sum = T.sum(axis=0)
    col_err = None
    if A_target is not None and A_target.sum() > 0:
        col_err = float(np.mean(np.abs(col_sum - A_target)) / max(A_target.sum(), 1e-9))
    return {
        "sum_total": sumT,
        "row_sum": row_sum,
        "col_sum": col_sum,
        "col_err": col_err,
    }


# ============================================================
# UI
# ============================================================
def render() -> None:
    ui_theme.section_title(4, "Distribuição — Para onde vou?")
    st.markdown(
        "<p style='color:#B8C0CC'>"
        "Gera a matriz origem-destino (O-D). Você pode importar uma matriz pronta "
        "ou calcular pelo modelo gravitacional. A normalização por origem garante "
        "que Σ<sub>j</sub> T<sub>ij</sub> = P<sub>i</sub>."
        "</p>", unsafe_allow_html=True,
    )

    zones_df = st.session_state.get("zones")
    if zones_df is None or zones_df.empty:
        ui_theme.warn("Cadastre as zonas primeiro.")
        return

    P = validation.numeric_clean(zones_df["production"]).to_numpy()
    A = validation.numeric_clean(zones_df["attraction"]).to_numpy()
    zone_ids = zones_df["zone_id"].astype(str).tolist()
    n = len(P)

    tab_grav, tab_import = st.tabs(["Modelo gravitacional", "Importar matriz O-D"])

    with tab_import:
        up = st.file_uploader(
            "CSV com matriz O-D (1ª coluna = zone_id, demais = zone_ids)",
            type=["csv", "xlsx"],
        )
        if up is not None:
            try:
                if up.name.lower().endswith(".csv"):
                    raw = pd.read_csv(up, index_col=0)
                else:
                    raw = pd.read_excel(up, index_col=0)
                if list(raw.columns) != list(raw.index):
                    ui_theme.warn("Índices e colunas devem coincidir (mesma ordem de zone_id).")
                else:
                    st.session_state["od_matrix"] = raw.to_numpy(dtype=float)
                    st.session_state["od_zone_ids"] = [str(x) for x in raw.index]
                    ui_theme.ok("Matriz O-D importada.")
            except Exception as e:
                ui_theme.warn(f"Erro ao ler matriz: {e}")

    with tab_grav:
        params = st.session_state["params"]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            beta = st.number_input("β (atrito)", value=float(params["beta"]),
                                   min_value=0.1, max_value=10.0, step=0.1)
        with c2:
            friction_type = st.selectbox("Função de atrito",
                                         ["potencia", "exponencial"],
                                         index=0 if params["friction"] == "potencia" else 1)
        with c3:
            imp_mode = st.selectbox("Impedância",
                                    ["tempo", "distancia", "custo_generalizado"])
        with c4:
            dmin = st.number_input("Distância mín. (km)",
                                   value=float(params["min_distance_km"]),
                                   min_value=0.05, max_value=5.0, step=0.05)
        speed = st.number_input(
            "Velocidade média (km/h) [usada para 'tempo' e 'custo_generalizado']",
            value=float(params["default_speed_kmh"]),
            min_value=5.0, max_value=120.0, step=1.0,
        )
        if st.button("🧮 Calcular matriz O-D"):
            params.update({"beta": beta, "friction": friction_type,
                           "min_distance_km": dmin, "default_speed_kmh": speed})
            st.session_state["params"] = params
            D = distance_matrix(zones_df)
            C = impedance_from_distance(D, speed_kmh=speed,
                                        mode=imp_mode, min_distance_km=dmin)
            T = gravity_distribution(P, A, C, beta=beta, friction_type=friction_type)
            st.session_state["od_matrix"] = T
            st.session_state["od_zone_ids"] = zone_ids
            st.session_state["impedance"] = C
            ui_theme.ok(f"Matriz O-D calculada para {n} zonas (modelo gravitacional).")

    # --- Saídas ---
    T = st.session_state.get("od_matrix")
    if T is None:
        ui_theme.info("Configure o modelo e clique em **Calcular matriz O-D**.")
        return

    summary = od_summary(T, A_target=A)
    c1, c2, c3, c4 = st.columns(4)
    with c1: ui_theme.card("Σ viagens", f"{summary['sum_total']:,.0f}")
    with c2: ui_theme.card("Σ por origem (Σ=ΣP)", f"{summary['row_sum'].sum():,.0f}")
    with c3: ui_theme.card("Σ por destino", f"{summary['col_sum'].sum():,.0f}")
    with c4:
        e = summary["col_err"]
        ui_theme.card("Erro col vs A", f"{(e*100):.2f}%" if e is not None else "—")

    # Heatmap
    st.markdown("### Heatmap da matriz O-D")
    df_T = pd.DataFrame(T, index=zone_ids, columns=zone_ids)
    fig = px.imshow(df_T, color_continuous_scale="YlOrRd", aspect="auto")
    fig.update_layout(template="plotly_dark",
                      paper_bgcolor=ui_theme.PALETTE["bg_main"],
                      plot_bgcolor=ui_theme.PALETTE["bg_second"],
                      height=480)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver matriz numérica"):
        st.dataframe(df_T.round(2), use_container_width=True)

    # Linhas de desejo
    st.markdown("### Linhas de desejo (top 30)")
    m = map_utils.base_map(zones_df)
    m = map_utils.add_zones(m, zones_df)
    m = map_utils.add_desire_lines(m, zones_df, T, zone_ids, top_n=30)
    map_utils.show(m, height=500)

    ui_theme.disclaimer_box()
