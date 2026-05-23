"""Tela 8 — Cenários (base, futuro, interdição, melhoria).

Cada cenário guarda um snapshot dos resultados e parâmetros relevantes.
O cenário-base (Cenário 0) é gerado automaticamente após a atribuição.

Tipos suportados:
- "base":        situação atual
- "futuro":      projeta crescimento de P, A, tráfego pesado etc.
- "interdicao":  bloqueia arestas ou penaliza tempos
- "melhoria":    adiciona arestas, reduz interferências
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from . import (
    ui_theme,
    balancing,
    trip_distribution as td,
    modal_split as ms,
    network_assignment as na,
    interferences as itf,
)


SCENARIO_TYPES = ["base", "futuro", "interdicao", "melhoria"]


# ============================================================
# Snapshot / construção do cenário-base
# ============================================================
def snapshot_current(name: str = "Cenário 0 — Situação Atual",
                     scenario_type: str = "base",
                     description: str = "Situação atual",
                     horizon_year: int | None = None) -> dict:
    """Cria um dict de cenário a partir do estado atual da sessão."""
    zones_df = st.session_state.get("zones")
    T = st.session_state.get("od_matrix")
    return {
        "scenario_id": uuid.uuid4().hex[:8],
        "name": name,
        "type": scenario_type,
        "description": description,
        "horizon_year": horizon_year or st.session_state["study"].get("horizon"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cost_estimate": 0.0,
        "interventions": [],
        "assumptions": "",
        "status": "ok",
        # snapshots
        "zones": zones_df.to_dict(orient="records") if zones_df is not None else [],
        "od_matrix": None if T is None else T.tolist(),
        "od_zone_ids": list(st.session_state.get("od_zone_ids") or []),
        "modal_split": dict(st.session_state.get("modal_split") or {}),
        "interferences": copy.deepcopy(st.session_state.get("interferences") or []),
        "assignment": copy.deepcopy(st.session_state.get("assignment") or {}),
        "params": copy.deepcopy(st.session_state.get("params") or {}),
        "edges": (
            None if st.session_state.get("network") is None or
            st.session_state["network"].get("edges") is None
            else st.session_state["network"]["edges"].to_dict(orient="records")
        ),
    }


# ============================================================
# Cenário futuro
# ============================================================
def apply_growth(zones_df: pd.DataFrame, g_prod: float, g_attr: float, years: int
                 ) -> pd.DataFrame:
    """P'_i = P_i · (1 + g_i)^n   ;   A'_j = A_j · (1 + h_j)^n."""
    df = zones_df.copy()
    df["production"] = pd.to_numeric(df["production"], errors="coerce").fillna(0) * (1 + g_prod) ** years
    df["attraction"] = pd.to_numeric(df["attraction"], errors="coerce").fillna(0) * (1 + g_attr) ** years
    return df


def run_future_scenario(name: str, g_prod: float, g_attr: float, years: int,
                        description: str = "") -> dict:
    """Executa um cenário futuro reaproveitando os mesmos parâmetros de impedância
    e repartição modal."""
    zones_df = st.session_state["zones"]
    df_future = apply_growth(zones_df, g_prod, g_attr, years)
    # Rebalanceia atrações para igualar produções (mais comum em planejamento)
    res = balancing.balance_vectors(
        df_future["production"].to_numpy(),
        df_future["attraction"].to_numpy(),
        method="ajustar_atracoes",
    )
    df_future["production"], df_future["attraction"] = res["P"], res["A"]

    P, A = res["P"], res["A"]
    D = td.distance_matrix(df_future)
    p = st.session_state["params"]
    C = td.impedance_from_distance(D, speed_kmh=p["default_speed_kmh"],
                                   mode="tempo", min_distance_km=p["min_distance_km"])
    T = td.gravity_distribution(P, A, C, beta=p["beta"], friction_type=p["friction"])

    net = na.build_simplified_network(df_future, k_neighbors=3,
                                       speed_kmh=p["default_speed_kmh"])
    zone_ids = df_future["zone_id"].astype(str).tolist()
    edges = na.all_or_nothing(net["graph"], T, zone_ids)
    ind = na.compute_indicators(edges, T, st.session_state.get("interferences"))

    sc = {
        "scenario_id": uuid.uuid4().hex[:8],
        "name": name, "type": "futuro", "description": description,
        "horizon_year": st.session_state["study"].get("base_year", 0) + years,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cost_estimate": 0.0,
        "interventions": [{"kind": "crescimento",
                            "g_prod": g_prod, "g_attr": g_attr, "years": years}],
        "assumptions": f"Crescimento composto P={g_prod:.2%}, A={g_attr:.2%}, {years} anos",
        "status": "ok",
        "zones": df_future.to_dict(orient="records"),
        "od_matrix": T.tolist(),
        "od_zone_ids": zone_ids,
        "modal_split": dict(st.session_state["modal_split"]),
        "interferences": copy.deepcopy(st.session_state["interferences"]),
        "assignment": ind,
        "params": dict(p),
        "edges": edges.to_dict(orient="records"),
    }
    return sc


# ============================================================
# Cenário de interdição
# ============================================================
def run_interdiction_scenario(name: str, interdictions: list[dict],
                               description: str = "") -> dict:
    """Aplica interdições (totais ou parciais) sobre a rede do cenário-base.

    Cada item de `interdictions`:
        {"from": str, "to": str, "kind": "total"|"parcial",
         "factor": float (1.0 = sem mudança), "extra_delay_min": float}
    """
    zones_df = st.session_state["zones"]
    p = st.session_state["params"]
    P = pd.to_numeric(zones_df["production"], errors="coerce").fillna(0).to_numpy()
    A = pd.to_numeric(zones_df["attraction"], errors="coerce").fillna(0).to_numpy()
    D = td.distance_matrix(zones_df)
    C = td.impedance_from_distance(D, speed_kmh=p["default_speed_kmh"], mode="tempo",
                                   min_distance_km=p["min_distance_km"])
    T = td.gravity_distribution(P, A, C, beta=p["beta"], friction_type=p["friction"])

    net = na.build_simplified_network(zones_df, k_neighbors=3,
                                       speed_kmh=p["default_speed_kmh"])
    G = net["graph"]
    if G is not None:
        for it in interdictions:
            a, b = str(it.get("from")), str(it.get("to"))
            if not G.has_edge(a, b):
                continue
            if it.get("kind") == "total":
                G.remove_edge(a, b)
            else:
                factor = float(it.get("factor", 1.5))
                extra = float(it.get("extra_delay_min", 0.0))
                G[a][b]["free_time_min"] = G[a][b].get("free_time_min", 0.0) * factor + extra

    zone_ids = zones_df["zone_id"].astype(str).tolist()
    edges = na.all_or_nothing(G, T, zone_ids)
    ind = na.compute_indicators(edges, T, st.session_state.get("interferences"))

    return {
        "scenario_id": uuid.uuid4().hex[:8],
        "name": name, "type": "interdicao", "description": description,
        "horizon_year": st.session_state["study"].get("horizon"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cost_estimate": 0.0,
        "interventions": interdictions,
        "assumptions": "Interdições aplicadas",
        "status": "ok",
        "zones": zones_df.to_dict(orient="records"),
        "od_matrix": T.tolist(),
        "od_zone_ids": zone_ids,
        "modal_split": dict(st.session_state["modal_split"]),
        "interferences": copy.deepcopy(st.session_state["interferences"]),
        "assignment": ind,
        "params": dict(p),
        "edges": edges.to_dict(orient="records"),
    }


# ============================================================
# Cenário de melhoria
# ============================================================
def run_improvement_scenario(name: str, improvements: list[dict],
                              cost_estimate: float = 0.0,
                              description: str = "") -> dict:
    """Adiciona arestas novas e/ou reduz interferências, depois reatribui.

    improvements: lista de dicts; cada item pode ser:
        {"kind": "nova_aresta", "from": str, "to": str,
         "length_km": float, "speed_kmh": float}
        {"kind": "reduzir_interferencia", "interference_id": str,
         "block_reduction_pct": float}
    """
    zones_df = st.session_state["zones"]
    p = st.session_state["params"]

    # Reduzir/eliminar interferências antes de avaliar
    interferences = copy.deepcopy(st.session_state["interferences"])
    for imp in improvements:
        if imp.get("kind") == "reduzir_interferencia":
            iid = imp.get("interference_id")
            pct = float(imp.get("block_reduction_pct", 100.0)) / 100.0
            for it in interferences:
                if it["interference_id"] == iid:
                    it["blocks_per_day"] = it.get("blocks_per_day", 0) * (1 - pct)

    P = pd.to_numeric(zones_df["production"], errors="coerce").fillna(0).to_numpy()
    A = pd.to_numeric(zones_df["attraction"], errors="coerce").fillna(0).to_numpy()
    D = td.distance_matrix(zones_df)
    C = td.impedance_from_distance(D, speed_kmh=p["default_speed_kmh"], mode="tempo",
                                   min_distance_km=p["min_distance_km"])
    T = td.gravity_distribution(P, A, C, beta=p["beta"], friction_type=p["friction"])

    net = na.build_simplified_network(zones_df, k_neighbors=3,
                                       speed_kmh=p["default_speed_kmh"])
    G = net["graph"]
    for imp in improvements:
        if imp.get("kind") == "nova_aresta" and G is not None:
            a, b = str(imp["from"]), str(imp["to"])
            if a in G.nodes and b in G.nodes and not G.has_edge(a, b):
                length = float(imp.get("length_km") or
                               td.haversine_km(G.nodes[a]["lat"], G.nodes[a]["lon"],
                                               G.nodes[b]["lat"], G.nodes[b]["lon"]))
                v = float(imp.get("speed_kmh") or p["default_speed_kmh"])
                G.add_edge(a, b,
                           length_km=length,
                           free_time_min=(length / max(v, 1e-6)) * 60.0,
                           speed_kmh=v, capacity=1500.0, flow=0.0)

    zone_ids = zones_df["zone_id"].astype(str).tolist()
    edges = na.all_or_nothing(G, T, zone_ids)
    ind = na.compute_indicators(edges, T, interferences)

    return {
        "scenario_id": uuid.uuid4().hex[:8],
        "name": name, "type": "melhoria", "description": description,
        "horizon_year": st.session_state["study"].get("horizon"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "cost_estimate": float(cost_estimate),
        "interventions": improvements,
        "assumptions": "Melhorias aplicadas",
        "status": "ok",
        "zones": zones_df.to_dict(orient="records"),
        "od_matrix": T.tolist(),
        "od_zone_ids": zone_ids,
        "modal_split": dict(st.session_state["modal_split"]),
        "interferences": interferences,
        "assignment": ind,
        "params": dict(p),
        "edges": edges.to_dict(orient="records"),
    }


# ============================================================
# UI
# ============================================================
def render() -> None:
    ui_theme.section_title(8, "Cenários")
    ui_theme.disclaimer_box()

    tab_base, tab_fut, tab_int, tab_mel = st.tabs(
        ["Cenário-base", "Futuro", "Interdição", "Melhoria"]
    )

    # ---- Cenário-base ----
    with tab_base:
        st.markdown("Gera o **Cenário 0 — Situação Atual** com o que está cadastrado agora.")
        if st.button("✅ Gerar cenário-base"):
            if st.session_state.get("od_matrix") is None:
                ui_theme.warn("Gere a matriz O-D antes.")
            else:
                st.session_state["base_scenario"] = snapshot_current()
                ui_theme.ok("Cenário-base gerado com sucesso. "
                             "Agora você pode criar cenários futuros, "
                             "de interdição ou de melhoria.")

        base = st.session_state.get("base_scenario")
        if base:
            ind = base.get("assignment", {})
            cc = st.columns(4)
            with cc[0]: ui_theme.card("Σ Viagens", f"{ind.get('total_trips',0):,.0f}")
            with cc[1]: ui_theme.card("Veh·km",   f"{ind.get('veh_km',0):,.0f}")
            with cc[2]: ui_theme.card("Tempo médio (min)", f"{ind.get('avg_time_min',0):.1f}")
            with cc[3]: ui_theme.card("Atraso (min·pessoa)", f"{ind.get('delay_total_min',0):,.0f}")

    # ---- Futuro ----
    with tab_fut:
        st.markdown("**Projetar crescimento** (P e A) e recalcular tudo.")
        c1, c2, c3 = st.columns(3)
        with c1: g_prod = st.number_input("Taxa anual P (g_i)", value=0.02, step=0.005, format="%.4f")
        with c2: g_attr = st.number_input("Taxa anual A (h_j)", value=0.02, step=0.005, format="%.4f")
        with c3: years = st.number_input("Anos (n)", value=10, min_value=1, max_value=50, step=1)
        name = st.text_input("Nome do cenário futuro", "Cenário Futuro 2035")
        desc = st.text_area("Descrição", "")
        if st.button("▶ Rodar cenário futuro"):
            try:
                sc = run_future_scenario(name, g_prod, g_attr, int(years), desc)
                st.session_state.setdefault("scenarios", []).append(sc)
                ui_theme.ok(f"Cenário '{name}' gerado. Total armazenados: "
                             f"{len(st.session_state['scenarios'])}.")
            except Exception as e:
                ui_theme.warn(f"Falha: {e}")

    # ---- Interdição ----
    with tab_int:
        st.markdown("**Bloquear arestas** (total ou parcial). Use os pares from→to da rede.")
        # Sugestão: listar arestas existentes
        net = st.session_state.get("network") or {}
        edges_df = net.get("edges")
        if edges_df is not None and not edges_df.empty:
            opts = [f"{r['from']} -> {r['to']}" for _, r in edges_df.iterrows()]
            sel = st.multiselect("Arestas a interditar", opts[:200])
            kind = st.radio("Tipo de interdição",
                            ["total", "parcial"], horizontal=True)
            factor = st.number_input("Fator de penalidade (parcial)", value=2.0, min_value=1.0, step=0.1)
            extra = st.number_input("Atraso adicional (min) (parcial)", value=0.0, step=0.5)
            name = st.text_input("Nome do cenário", "Cenário Interdição A")
            desc = st.text_area("Descrição", "", key="int_desc")
            if st.button("▶ Rodar cenário de interdição"):
                inters = []
                for s in sel:
                    a, b = [x.strip() for x in s.split("->")]
                    inters.append({"from": a, "to": b, "kind": kind,
                                   "factor": factor, "extra_delay_min": extra})
                try:
                    sc = run_interdiction_scenario(name, inters, desc)
                    st.session_state.setdefault("scenarios", []).append(sc)
                    ui_theme.ok(f"Cenário '{name}' gerado.")
                except Exception as e:
                    ui_theme.warn(f"Falha: {e}")
        else:
            ui_theme.info("Gere a rede em **6. Atribuição** primeiro.")

    # ---- Melhoria ----
    with tab_mel:
        st.markdown("**Adicionar arestas** novas ou **reduzir interferências**.")
        zones_df = st.session_state.get("zones")
        if zones_df is None or zones_df.empty:
            ui_theme.warn("Cadastre as zonas primeiro.")
            return
        ids = zones_df["zone_id"].astype(str).tolist()
        c1, c2, c3, c4 = st.columns(4)
        with c1: a = st.selectbox("De (zone)", ids, key="mel_a")
        with c2: b = st.selectbox("Para (zone)", ids, key="mel_b")
        with c3: length = st.number_input("Comprimento (km, 0 = auto)", value=0.0, step=0.1)
        with c4: spd = st.number_input("Velocidade (km/h)", value=50.0, step=1.0)
        cost = st.number_input("Custo estimado da obra (R$)", value=0.0, step=10000.0)

        st.markdown("##### Redução de interferência existente")
        it_list = st.session_state.get("interferences") or []
        red_target = st.selectbox(
            "Interferência alvo",
            ["—"] + [f"{i['interference_id']} - {i['name']}" for i in it_list],
        )
        red_pct = st.slider("Redução (%)", 0, 100, 100)

        name = st.text_input("Nome do cenário", "Cenário Melhoria — nova ligação")
        desc = st.text_area("Descrição", "", key="mel_desc")
        if st.button("▶ Rodar cenário de melhoria"):
            imps = []
            if a != b:
                imps.append({"kind": "nova_aresta", "from": a, "to": b,
                             "length_km": length or None, "speed_kmh": spd})
            if red_target != "—":
                iid = red_target.split(" - ")[0]
                imps.append({"kind": "reduzir_interferencia",
                             "interference_id": iid,
                             "block_reduction_pct": red_pct})
            try:
                sc = run_improvement_scenario(name, imps, cost_estimate=cost, description=desc)
                st.session_state.setdefault("scenarios", []).append(sc)
                ui_theme.ok(f"Cenário '{name}' gerado.")
            except Exception as e:
                ui_theme.warn(f"Falha: {e}")

    st.markdown("---")
    scs = st.session_state.get("scenarios", [])
    st.markdown(f"#### Cenários gerados nesta sessão: **{len(scs)}**")
    if scs:
        df = pd.DataFrame([{
            "id": s["scenario_id"], "nome": s["name"], "tipo": s["type"],
            "horizonte": s.get("horizon_year"),
            "Σ viagens": float(s["assignment"].get("total_trips", 0)),
            "tempo médio (min)": round(float(s["assignment"].get("avg_time_min", 0)), 1),
            "veh·km": round(float(s["assignment"].get("veh_km", 0)), 0),
            "custo obra (R$)": s.get("cost_estimate", 0),
        } for s in scs])
        st.dataframe(df, use_container_width=True)
