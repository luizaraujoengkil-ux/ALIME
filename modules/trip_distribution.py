"""Tela 4 — Distribuição de viagens (Para onde vou?).

Implementa o modelo gravitacional normalizado por origem:

    T_ij = P_i · ( A_j · f(c_ij) ) / Σ_j ( A_j · f(c_ij) )

onde:
    - T_ij  : viagens estimadas da origem i ao destino j
    - P_i   : produção balanceada (production_balanced) da origem i
    - A_j   : atração balanceada (attraction_balanced) do destino j
    - c_ij  : custo generalizado entre i e j (matriz de impedância)
    - f(c)  : função de atrito (potência 1/c^β ou exponencial exp(-β·c))

GUARDAS DEFENSIVOS desta etapa:
    1. Antes de qualquer cálculo, a matriz de impedância é VALIDADA
       (sem NaN, sem Inf, sem negativos, diagonal tratada).
    2. Antes da distribuição, ΣP e ΣA são checados (> 0).
    3. Por origem, o denominador gravitacional é checado.
    4. Se qualquer NaN aparecer em T, o cálculo é abortado com
       mensagem amigável em vez de propagar NaN para os cards.

Por construção, Σ_j T_ij = P_i (cada linha respeita a produção).
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
    """Matriz de distâncias (km) entre centroides.

    Levanta exceção descritiva se algum centroide estiver vazio/NaN.
    """
    lat = pd.to_numeric(zones_df["centroid_lat"], errors="coerce").to_numpy()
    lon = pd.to_numeric(zones_df["centroid_lon"], errors="coerce").to_numpy()
    bad = np.where(~np.isfinite(lat) | ~np.isfinite(lon))[0]
    if len(bad):
        ids = zones_df["zone_id"].astype(str).to_numpy()
        bad_ids = ", ".join(ids[bad].tolist())
        raise ValueError(
            f"Centroides ausentes nas zonas: {bad_ids}. "
            f"Preencha centroid_lat e centroid_lon na aba 2 — Zonas, "
            f"ou use uma matriz de impedância importada."
        )
    n = len(lat)
    D = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(n):
            if i == j:
                D[i, j] = 0.0
            else:
                D[i, j] = haversine_km(lat[i], lon[i], lat[j], lon[j])
    return D


def network_distance_matrix(nd: dict, zone_ids: list, zones_df: pd.DataFrame) -> np.ndarray:
    """Alinha a matriz de distância da rede real (etapa 6) à ordem atual das
    zonas. Lacunas (zonas não cobertas) são preenchidas com a distância em
    linha reta (haversine), garantindo uma matriz completa."""
    ids = [str(x) for x in zone_ids]
    M = pd.DataFrame(
        np.asarray(nd["matrix"], dtype=float),
        index=[str(x) for x in nd["zone_ids"]],
        columns=[str(x) for x in nd["zone_ids"]],
    ).reindex(index=ids, columns=ids)
    D = np.array(M.to_numpy(dtype=float), copy=True)
    if np.isnan(D).any():
        H = distance_matrix(zones_df)
        mask = np.isnan(D)
        D[mask] = H[mask]
    np.fill_diagonal(D, 0.0)
    return D


def impedance_from_distance(
    D: np.ndarray,
    speed_kmh: float = 35.0,
    extra_delay_min: np.ndarray | None = None,
    mode: str = "tempo",  # "distancia" | "tempo" | "custo_generalizado"
    min_distance_km: float = 0.3,
) -> np.ndarray:
    """Constrói a matriz de impedância c_ij a partir de distâncias."""
    Dsafe = validation.safe_min_distance(D, min_distance_km)
    if mode == "distancia":
        return Dsafe
    t_mov = (Dsafe / max(speed_kmh, 1e-6)) * 60.0
    extra = extra_delay_min if extra_delay_min is not None else np.zeros_like(t_mov)
    return t_mov + extra


# ============================================================
# Validação e preparo da matriz de impedância
# ============================================================
def validate_impedance_matrix(
    matrix: np.ndarray | None,
    zone_ids: list[str] | None = None,
) -> dict:
    """Valida a matriz de impedância. Retorna dict com ok/errors/warnings/stats."""
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict = {}

    if matrix is None:
        return {"ok": False,
                "errors": ["Matriz de impedância ausente."],
                "warnings": [], "stats": {}}

    M = np.asarray(matrix, dtype=float)
    if M.ndim != 2:
        return {"ok": False,
                "errors": [f"Matriz tem {M.ndim} dimensões (esperado 2D)."],
                "warnings": [], "stats": {}}
    if M.shape[0] != M.shape[1]:
        return {"ok": False,
                "errors": [f"Matriz não-quadrada: shape={M.shape}."],
                "warnings": [], "stats": {}}
    n = M.shape[0]
    if zone_ids is not None and n != len(zone_ids):
        errors.append(
            f"Matriz é {n}×{n} mas existem {len(zone_ids)} zonas cadastradas."
        )

    n_nan = int(np.isnan(M).sum())
    n_inf = int(np.isinf(M).sum())
    if n_nan > 0:
        errors.append(f"{n_nan} valores NaN na matriz.")
    if n_inf > 0:
        errors.append(f"{n_inf} valores infinitos na matriz.")

    if not (n_nan or n_inf):
        if np.any(M < 0):
            n_neg = int((M < 0).sum())
            errors.append(f"{n_neg} valores negativos na matriz.")

        diag = np.diag(M)
        n_zero_diag = int((diag == 0).sum())
        off = M.copy()
        np.fill_diagonal(off, np.nan)
        n_zero_off = int((off == 0).sum())
        if n_zero_diag:
            warnings.append(
                f"Diagonal contém {n_zero_diag} zeros — serão substituídos "
                f"por custo mínimo no cálculo do atrito."
            )
        if n_zero_off:
            warnings.append(
                f"{n_zero_off} zeros fora da diagonal — serão substituídos "
                f"por custo mínimo no cálculo do atrito."
            )

        stats = {
            "shape": M.shape,
            "min": float(np.min(M)),
            "max": float(np.max(M)),
            "mean": float(np.mean(M)),
            "diag_zeros": n_zero_diag,
            "offdiag_zeros": n_zero_off,
        }

    return {"ok": len(errors) == 0, "errors": errors,
            "warnings": warnings, "stats": stats}


def prepare_impedance_matrix(
    matrix: np.ndarray,
    min_cost: float = 1.0,
    ignore_intrazonal: bool = True,
) -> np.ndarray:
    """Substitui zeros e valores <= 0 pela constante `min_cost`.

    `ignore_intrazonal=True` força custo mínimo na diagonal (será zerada
    pelo motor gravitacional de qualquer forma, mas evita /0 em outros usos).
    """
    M = np.asarray(matrix, dtype=float).copy()
    if not np.all(np.isfinite(M)):
        raise ValueError(
            "Matriz de impedância contém NaN ou Inf — execute "
            "validate_impedance_matrix antes de chamar prepare."
        )
    # Substitui não-positivos por min_cost
    M = np.where(M <= 0, float(min_cost), M)
    if ignore_intrazonal:
        # Diagonal explícita com min_cost (será zerada na função de atrito)
        np.fill_diagonal(M, float(min_cost))
    return M


# ============================================================
# Funções de atrito e modelo gravitacional
# ============================================================
def friction(c: np.ndarray, beta: float, kind: str = "potencia",
             min_cost: float = 1.0) -> np.ndarray:
    """Função de atrito f(c) com piso de custo para evitar singularidades.

    - potência:    f(c) = 1 / max(c, min_cost)^β
    - exponencial: f(c) = exp(-β · max(c, min_cost))
    """
    c_safe = np.maximum(c, float(min_cost))
    if kind == "potencia":
        return 1.0 / np.power(c_safe, beta)
    if kind == "exponencial":
        return np.exp(-beta * c_safe)
    raise ValueError(f"friction kind desconhecido: {kind!r}")


def gravity_distribution(
    productions: np.ndarray,
    attractions: np.ndarray,
    impedance_matrix: np.ndarray,
    beta: float = 2.0,
    friction_type: str = "potencia",
    min_cost: float = 1.0,
) -> np.ndarray:
    """Modelo gravitacional normalizado por origem (defensivo).

    Garante:
        - ΣP > 0 e ΣA > 0 (caso contrário, ValueError)
        - matriz de impedância válida (sem NaN/Inf)
        - denominador positivo por origem
        - resultado sem NaN
    """
    P = np.asarray(productions, dtype=float)
    A = np.asarray(attractions, dtype=float)

    if P.size == 0 or A.size == 0:
        raise ValueError("Produções e atrações não podem ser vazias.")
    if P.size != A.size:
        raise ValueError(f"Tamanhos divergentes: |P|={P.size}, |A|={A.size}.")
    if P.sum() <= 0:
        raise ValueError(f"ΣP={P.sum()} — produções vazias ou zeradas.")
    if A.sum() <= 0:
        raise ValueError(f"ΣA={A.sum()} — atrações vazias ou zeradas.")

    M = prepare_impedance_matrix(impedance_matrix, min_cost=min_cost,
                                  ignore_intrazonal=True)
    if M.shape[0] != P.size:
        raise ValueError(
            f"Matriz de impedância {M.shape} não combina com {P.size} zonas."
        )

    F = friction(M, beta, friction_type, min_cost=min_cost)
    # Ignora viagens intra-zonais por padrão
    np.fill_diagonal(F, 0.0)

    AF = A[np.newaxis, :] * F                  # (n, n)
    row_sums = AF.sum(axis=1)                  # (n,)

    bad_origins: list[int] = []
    for i, r in enumerate(row_sums):
        if not np.isfinite(r) or r <= 0:
            bad_origins.append(i)
    if bad_origins:
        raise ValueError(
            f"Não foi possível calcular a distribuição para a(s) origem(ns) "
            f"{bad_origins}: denominador gravitacional inválido (Σ_j(A_j · f) = 0 ou NaN)."
        )

    T = P[:, np.newaxis] * (AF / row_sums[:, np.newaxis])

    if not np.all(np.isfinite(T)):
        raise ValueError(
            "Matriz O-D resultante contém NaN/Inf após o cálculo gravitacional. "
            "Verifique os vetores P/A e a matriz de impedância."
        )

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
# UI helpers
# ============================================================
def _impedance_status_block(M: np.ndarray | None, zone_ids: list[str]) -> None:
    """Mostra status visual da matriz de impedância atual."""
    chk = validate_impedance_matrix(M, zone_ids)
    if M is None:
        ui_theme.warning_message(
            "Nenhuma matriz de impedância carregada ainda. "
            "Escolha uma fonte abaixo."
        )
        return
    if chk["ok"]:
        s = chk["stats"]
        ui_theme.success_message(
            f"Matriz de impedância <b>válida</b>. "
            f"Shape: <b>{s['shape'][0]}×{s['shape'][1]}</b> · "
            f"min={s['min']:.2f} · média={s['mean']:.2f} · max={s['max']:.2f}"
        )
        if chk["warnings"]:
            for w in chk["warnings"]:
                ui_theme.warning_message(w)
    else:
        for e in chk["errors"]:
            ui_theme.error_message(e)


# ============================================================
# UI principal
# ============================================================
def render() -> None:
    from . import workflow
    if not workflow.render_guard("distribuicao"):
        return
    ui_theme.section_title(4, "Distribuição — Para onde vou?")
    st.markdown(
        "<p style='color:#B8C0CC'>"
        "Gera a matriz origem-destino (O-D). Etapa: (1) configure a matriz "
        "de impedância, (2) rode o modelo gravitacional, ou (3) importe uma "
        "matriz O-D pronta."
        "</p>", unsafe_allow_html=True,
    )

    zones_df = st.session_state.get("zones")
    if zones_df is None or zones_df.empty:
        ui_theme.warning_message("Cadastre as zonas primeiro (aba 2. Zonas).")
        return

    from . import zones as zones_mod
    P_series, A_series = zones_mod.get_balanced_vectors(zones_df)
    P = P_series.to_numpy()
    A = A_series.to_numpy()
    zone_ids = zones_df["zone_id"].astype(str).tolist()
    n = len(P)

    # Banner sobre a fonte dos vetores
    b = st.session_state.get("balancing")
    if b and b.get("applied"):
        ui_theme.info(
            f"Distribuição utilizando <b>vetores balanceados</b> da etapa 3. "
            f"Σ P usado = <b>{ui_theme.num_br(float(P.sum()), 1)}</b> · "
            f"Σ A usado = <b>{ui_theme.num_br(float(A.sum()), 1)}</b> · "
            f"fator aplicado = <b>{b['factor']:.6f}</b>."
        )
    else:
        ui_theme.warning_message(
            f"Distribuição utilizando vetores <b>originais</b> "
            f"(o balanceamento ainda não foi aplicado na etapa 3). "
            f"Σ P = <b>{ui_theme.num_br(float(P.sum()), 1)}</b> · "
            f"Σ A = <b>{ui_theme.num_br(float(A.sum()), 1)}</b>."
        )

    tab_imp, tab_grav, tab_import = st.tabs(
        ["1. Matriz de Impedância", "2. Modelo Gravitacional", "Importar matriz O-D"]
    )

    # =====================================================
    # ABA 1 — MATRIZ DE IMPEDÂNCIA
    # =====================================================
    with tab_imp:
        st.markdown(
            "<p style='color:#B8C0CC'>Escolha como construir a matriz de impedância. "
            "Ela é a entrada do modelo gravitacional.</p>",
            unsafe_allow_html=True,
        )

        current_M = st.session_state.get("impedance")
        _impedance_status_block(current_M, zone_ids)

        st.markdown("### Fontes")
        _nd = st.session_state.get("network_distance_km")
        use_network = st.checkbox(
            "🛣️ Usar distância pela rede real (OSM) em vez de linha reta",
            value=bool(_nd),
            help="Requer ter construído a malha OSM na etapa 6 (Atribuição). "
                 "Troca a distância haversine pela distância de viário (Dijkstra) "
                 "ao calcular a impedância. Zonas fora do raio usam linha reta.",
        )
        if use_network and _nd is None:
            ui_theme.info("Malha OSM ainda não construída — construa na etapa 6 "
                          "para habilitar a distância pela rede. Por ora, linha reta.")
        cc = st.columns(3)
        with cc[0]:
            use_centroids = st.button(
                "🛣️ Calcular pela rede (OSM)" if (use_network and _nd is not None)
                else "🌍 Calcular dos centroides",
                use_container_width=True)
        with cc[1]:
            up_imp = st.file_uploader("📥 Importar CSV/Excel",
                                       type=["csv", "xlsx"], key="imp_upload",
                                       label_visibility="visible")
        with cc[2]:
            edit_manual = st.button("✏ Editar manualmente",
                                     use_container_width=True)

        # --- Calcular dos centroides ---
        if use_centroids:
            try:
                params = st.session_state["params"]
                if use_network and _nd is not None:
                    D = network_distance_matrix(_nd, zone_ids, zones_df)
                    src = "rede OSM (Dijkstra)"
                else:
                    D = distance_matrix(zones_df)
                    src = "centroides (linha reta)"
                C = impedance_from_distance(
                    D, speed_kmh=params["default_speed_kmh"],
                    mode="tempo",
                    min_distance_km=params["min_distance_km"],
                )
                chk = validate_impedance_matrix(C, zone_ids)
                if chk["ok"]:
                    st.session_state["impedance"] = C
                    st.session_state["impedance_source"] = src
                    ui_theme.remember_status(
                        "impedance_loaded", "success",
                        f"Matriz de impedância calculada — fonte: **{src}**. "
                        f"Σ tempos (off-diagonal) = {float(np.tril(C, -1).sum() + np.triu(C, 1).sum()):.0f} min."
                    )
                else:
                    ui_theme.error_message("Falha na validação:<br/>" +
                                            "<br/>".join(f"• {e}" for e in chk["errors"]))
            except Exception as e:
                ui_theme.error_message(f"Falha ao calcular dos centroides: {e}")

        # --- Importar CSV/Excel ---
        if up_imp is not None:
            try:
                if up_imp.name.lower().endswith(".csv"):
                    raw = pd.read_csv(up_imp, index_col=0)
                else:
                    raw = pd.read_excel(up_imp, index_col=0)
                M_imp = raw.to_numpy(dtype=float)
                chk = validate_impedance_matrix(M_imp, zone_ids)
                if chk["ok"]:
                    st.session_state["impedance"] = M_imp
                    st.session_state["impedance_source"] = "import"
                    ui_theme.remember_status(
                        "impedance_loaded", "success",
                        f"Matriz importada com sucesso ({M_imp.shape[0]}×{M_imp.shape[1]})."
                    )
                else:
                    ui_theme.error_message("Falha na validação:<br/>" +
                                            "<br/>".join(f"• {e}" for e in chk["errors"]))
            except Exception as e:
                ui_theme.error_message(f"Erro ao ler arquivo: {e}")

        ui_theme.show_status("impedance_loaded")

        # --- Editor manual ---
        if edit_manual or st.session_state.get("_imp_edit_open", False):
            st.session_state["_imp_edit_open"] = True
            st.markdown("### Editor manual da matriz")
            base = current_M if current_M is not None else np.zeros((n, n))
            if base.shape[0] != n:
                base = np.zeros((n, n))
            df_edit = pd.DataFrame(base, index=zone_ids, columns=zone_ids)
            edited = st.data_editor(
                df_edit,
                use_container_width=True,
                num_rows="fixed",
                key="imp_editor",
            )
            if st.button("💾 Salvar matriz editada"):
                try:
                    M_new = edited.to_numpy(dtype=float)
                    chk = validate_impedance_matrix(M_new, zone_ids)
                    if chk["ok"]:
                        st.session_state["impedance"] = M_new
                        st.session_state["impedance_source"] = "manual"
                        ui_theme.remember_status(
                            "impedance_loaded", "success",
                            "Matriz editada manualmente salva."
                        )
                        st.session_state["_imp_edit_open"] = False
                    else:
                        ui_theme.error_message("Falha na validação:<br/>" +
                                                "<br/>".join(f"• {e}" for e in chk["errors"]))
                except Exception as e:
                    ui_theme.error_message(f"Erro ao salvar matriz: {e}")

        # --- Visualização da matriz atual ---
        cur = st.session_state.get("impedance")
        if cur is not None and isinstance(cur, np.ndarray) and cur.shape == (n, n):
            with st.expander("Ver matriz atual"):
                df_cur = pd.DataFrame(cur, index=zone_ids, columns=zone_ids)
                st.dataframe(df_cur.round(2), use_container_width=True)
                src = st.session_state.get("impedance_source", "?")
                st.caption(f"Fonte: **{src}**")

    # =====================================================
    # ABA 2 — MODELO GRAVITACIONAL
    # =====================================================
    with tab_grav:
        params = st.session_state["params"]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            beta_val = st.number_input("β (atrito)", value=float(params["beta"]),
                                        min_value=0.1, max_value=10.0, step=0.1)
        with c2:
            friction_type = st.selectbox("Função de atrito",
                                          ["potencia", "exponencial"],
                                          index=0 if params["friction"] == "potencia" else 1)
        with c3:
            min_cost = st.number_input("Custo mínimo (piso)",
                                        min_value=0.01, max_value=100.0,
                                        value=1.0, step=0.1,
                                        help="Substitui zeros e valores < piso "
                                             "antes do cálculo do atrito. "
                                             "Evita divisão por zero.")
        with c4:
            st.caption("Vetores em uso:")
            st.write(f"Σ P = **{ui_theme.num_br(float(P.sum()), 1)}**")
            st.write(f"Σ A = **{ui_theme.num_br(float(A.sum()), 1)}**")

        M_current = st.session_state.get("impedance")
        chk = validate_impedance_matrix(M_current, zone_ids)
        if not chk["ok"]:
            ui_theme.warning_message(
                "Não foi encontrada matriz de impedância válida. "
                "Importe uma matriz O-D de tempos/distâncias ou preencha "
                "os centroides das zonas (aba 1 acima)."
            )
        else:
            for w in chk["warnings"]:
                ui_theme.warning_message(w)

        if st.button("🧮 Calcular matriz O-D", disabled=(not chk["ok"])):
            params.update({"beta": beta_val, "friction": friction_type})
            st.session_state["params"] = params
            try:
                T = gravity_distribution(
                    P, A, M_current,
                    beta=beta_val, friction_type=friction_type,
                    min_cost=min_cost,
                )
                st.session_state["od_matrix"] = T
                st.session_state["od_zone_ids"] = zone_ids
                ui_theme.remember_status(
                    "od_matrix_generated", "success",
                    f"Matriz O-D gerada com sucesso usando os vetores balanceados "
                    f"({n} zonas, modelo gravitacional, β={beta_val}, "
                    f"atrito={friction_type}, custo mínimo={min_cost})."
                )
            except ValueError as e:
                # Bloqueia o estado anterior para não exibir matriz inválida
                st.session_state["od_matrix"] = None
                ui_theme.remember_status(
                    "od_matrix_generated", "error",
                    f"Erro no modelo gravitacional: {e}"
                )

        ui_theme.show_status("od_matrix_generated")

    # =====================================================
    # ABA 3 — IMPORTAR MATRIZ O-D
    # =====================================================
    with tab_import:
        up = st.file_uploader(
            "CSV com matriz O-D (1ª coluna = zone_id, demais = zone_ids)",
            type=["csv", "xlsx"], key="od_upload",
        )
        if up is not None:
            try:
                if up.name.lower().endswith(".csv"):
                    raw = pd.read_csv(up, index_col=0)
                else:
                    raw = pd.read_excel(up, index_col=0)
                if list(raw.columns) != list(raw.index):
                    ui_theme.error_message(
                        "Índices e colunas devem coincidir (mesma ordem de zone_id)."
                    )
                else:
                    T_in = raw.to_numpy(dtype=float)
                    if not np.all(np.isfinite(T_in)):
                        ui_theme.error_message(
                            "Matriz O-D importada contém valores NaN ou infinitos."
                        )
                    else:
                        st.session_state["od_matrix"] = T_in
                        st.session_state["od_zone_ids"] = [str(x) for x in raw.index]
                        ui_theme.remember_status(
                            "od_matrix_generated", "success",
                            "Matriz O-D importada com sucesso."
                        )
            except Exception as e:
                ui_theme.error_message(f"Erro ao ler matriz: {e}")

    # =====================================================
    # SAÍDAS (cards + heatmap + linhas de desejo)
    # =====================================================
    T = st.session_state.get("od_matrix")
    if T is None or not isinstance(T, np.ndarray) or not np.all(np.isfinite(T)):
        ui_theme.info("Configure a matriz de impedância (aba 1) e clique em "
                       "<b>Calcular matriz O-D</b> (aba 2).")
        return

    summary = od_summary(T, A_target=A)

    def _fmt(val: float, fmt: str = ",.0f") -> str:
        """Formata um valor numérico evitando 'nan' nos cards."""
        if val is None or (isinstance(val, float) and not np.isfinite(val)):
            return "—"
        return format(val, fmt)

    c1, c2, c3, c4 = st.columns(4)
    with c1: ui_theme.card("Σ viagens",      _fmt(summary["sum_total"]))
    with c2: ui_theme.card("Σ por origem",   _fmt(float(summary["row_sum"].sum())))
    with c3: ui_theme.card("Σ por destino",  _fmt(float(summary["col_sum"].sum())))
    with c4:
        e = summary["col_err"]
        if e is None or not np.isfinite(e):
            ui_theme.card("Erro col vs A", "—")
        else:
            ui_theme.card("Erro col vs A", f"{e*100:.2f}%")

    # Heatmap (com o número de viagens em cada célula)
    st.markdown("### Heatmap da matriz O-D (viagens)")
    df_T = pd.DataFrame(T, index=zone_ids, columns=zone_ids)
    fig = px.imshow(df_T, color_continuous_scale="Oranges", aspect="auto",
                    text_auto=".0f")
    fig.update_traces(textfont_size=11)
    fig.update_layout(template="plotly_dark",
                      paper_bgcolor=ui_theme.PALETTE["bg_main"],
                      plot_bgcolor=ui_theme.PALETTE["bg_second"],
                      height=520, coloraxis_colorbar_title="viagens")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Ver matriz numérica"):
        st.dataframe(df_T.round(2), use_container_width=True)

    # Linhas de desejo
    st.markdown("### Linhas de desejo (top 30)")
    _tiles, _attr = map_utils.theme_selector("dist_map_theme", default="OpenStreetMap")
    map_utils.warn_if_null_island(zones_df)
    m = map_utils.base_map(zones_df, tiles=_tiles, attr=_attr)
    m = map_utils.add_zones(m, zones_df)
    m = map_utils.add_desire_lines(m, zones_df, T, zone_ids, top_n=30)
    map_utils.show(m, height=500)

    ui_theme.disclaimer_box()
