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
import itertools
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
    """P'_i = P_i · (1 + g_i)^n   ;   A'_j = A_j · (1 + h_j)^n.

    Aplica crescimento sobre os valores BALANCEADOS (que são os inputs
    canônicos do modelo). Também atualiza as colunas `production`/
    `attraction` para manter a view editável sincronizada.
    """
    df = zones_df.copy()
    pb = pd.to_numeric(df.get("production_balanced", df["production"]), errors="coerce").fillna(0)
    ab = pd.to_numeric(df.get("attraction_balanced", df["attraction"]), errors="coerce").fillna(0)
    df["production_balanced"] = pb * (1 + g_prod) ** years
    df["attraction_balanced"] = ab * (1 + g_attr) ** years
    # Sincroniza view editável
    df["production"] = df["production_balanced"]
    df["attraction"] = df["attraction_balanced"]
    return df


def run_future_scenario(name: str, g_prod: float, g_attr: float, years: int,
                        description: str = "") -> dict:
    """Executa um cenário futuro reaproveitando os mesmos parâmetros de impedância
    e repartição modal."""
    from . import zones as zones_mod
    zones_df = st.session_state["zones"]
    df_future = apply_growth(zones_df, g_prod, g_attr, years)
    # Rebalanceia atrações para igualar produções (mais comum em planejamento)
    P_in, A_in = zones_mod.get_balanced_vectors(df_future)
    res = balancing.balance_vectors(
        P_in.to_numpy(),
        A_in.to_numpy(),
        method="ajustar_atracoes",
    )
    df_future["production_balanced"] = res["P"]
    df_future["attraction_balanced"] = res["A"]
    df_future["production"] = res["P"]
    df_future["attraction"] = res["A"]

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
    from . import zones as zones_mod
    zones_df = st.session_state["zones"]
    p = st.session_state["params"]
    P_s, A_s = zones_mod.get_balanced_vectors(zones_df)
    P = P_s.to_numpy()
    A = A_s.to_numpy()
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
    from . import zones as zones_mod
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

    P_s, A_s = zones_mod.get_balanced_vectors(zones_df)
    P = P_s.to_numpy()
    A = A_s.to_numpy()
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
def interference_delay_min_day(it: dict, total_trips: float,
                               edges_df=None) -> float:
    """Atraso diário (viagens·min) atribuível a UMA interferência.

    Mesma base de network_assignment.compute_indicators:
        atraso = bloqueios/dia · (bloqueio + fila) · viagens_afetadas
    onde viagens_afetadas vem do FLUXO da aresta mais próxima (se houver rede
    com geometria) ou, na falta, de `fração_afetada · total`.
    """
    blocks = float(it.get("blocks_per_day", 0) or 0)
    tblock = float(it.get("average_blockage_min", 0) or 0)
    tqueue = float(it.get("queue_dissipation_min", 0) or 0)
    affected = na.interference_affected_trips(it, edges_df, total_trips)
    return blocks * (tblock + tqueue) * affected


def _render_base_summary(base: dict, ind: dict) -> None:
    """Painel de impacto do Cenário 0: viagens, atraso diário/anual, custo
    social anual e a interferência mais crítica."""
    from . import social_cost as sc_mod
    p = base.get("params") or st.session_state.get("params", {}) or {}
    its = list(base.get("interferences") or [])
    total_trips = float(ind.get("total_trips", 0) or 0)
    daily_delay = float(ind.get("delay_total_min", 0) or 0)
    days = float(p.get("operating_days", 252) or 252)
    annual_delay = daily_delay * days
    cost = sc_mod.social_cost(ind, p)
    edges_df = pd.DataFrame(base.get("edges") or [])

    ranked = sorted(its, key=lambda it: interference_delay_min_day(it, total_trips, edges_df),
                    reverse=True)
    worst = ranked[0] if ranked else None

    st.markdown("#### 📋 Resumo do Cenário 0 — Situação Atual")
    r1 = st.columns(3)
    with r1[0]: ui_theme.card("Viagens totais estimadas", f"{total_trips:,.0f}")
    with r1[1]: ui_theme.card("Interferências ativas", f"{len(its)}")
    with r1[2]: ui_theme.card("Atraso diário estimado", f"{daily_delay:,.0f} viagens·min")
    r2 = st.columns(3)
    with r2[0]: ui_theme.card("Atraso anual estimado", f"{annual_delay:,.0f} viagens·min")
    with r2[1]: ui_theme.card("Custo social anual", f"R$ {cost['annual_cost_brl']:,.0f}")
    with r2[2]:
        ui_theme.card("Interferência mais crítica",
                      worst.get("name", "—") if worst else "—")

    if worst:
        wd = interference_delay_min_day(worst, total_trips, edges_df)
        share = wd / daily_delay * 100 if daily_delay > 0 else 0.0
        st.caption(
            f"🚨 **{worst.get('name')}** é a mais crítica: responde por "
            f"~{wd:,.0f} viagens·min/dia ({share:.0f}% do atraso total). "
            "Priorizar a intervenção aqui (ex.: viaduto) tende ao maior impacto "
            "positivo na cidade e na redução do custo social.")


def enumerate_interventions(base: dict, params: dict,
                            costs: dict | None = None,
                            horizon_years: int = 10) -> dict:
    """Gera TODOS os cenários de intervenção possíveis sobre as interferências.

    Cada cenário = um subconjunto de interferências "melhoradas" (ex.: viaduto),
    cuja contribuição de atraso passa a zero. Como o atraso é aditivo por
    interferência, enumeramos as 2^n combinações (uma a uma, pares, trios…,
    todas) de forma exata e instantânea. Para n grande (2^n > 4096) cai para
    singles + pares + todas.

    Se `costs` (custo de obra por nome de interferência) for informado, calcula
    também:
        custo_obra  = Σ custos das interferências melhoradas
        payback     = custo_obra / benefício_anual          (anos)
        IBC         = (benefício_anual · horizonte) / custo_obra
    """
    from . import social_cost as sc_mod
    its = list(base.get("interferences") or [])
    ind = base.get("assignment", {})
    total_trips = float(ind.get("total_trips", 0) or 0)
    n = len(its)
    names = [it.get("name", f"INT{i+1}") for i, it in enumerate(its)]
    edges_df = pd.DataFrame(base.get("edges") or [])
    delays = [interference_delay_min_day(it, total_trips, edges_df) for it in its]
    base_daily = float(ind.get("delay_total_min", sum(delays)) or sum(delays))
    days = float(params.get("operating_days", 252) or 252)
    base_annual_cost = sc_mod.social_cost({"delay_total_min": base_daily}, params)["annual_cost_brl"]
    costs = costs or {}
    horizon_years = max(int(horizon_years or 10), 1)

    if n <= 12:
        subsets = []
        for r in range(0, n + 1):
            subsets.extend(itertools.combinations(range(n), r))
        exhaustive = True
    else:  # fallback: nenhuma + singles + pares + todas
        subsets = [()] + [(i,) for i in range(n)]
        subsets += list(itertools.combinations(range(n), 2))
        subsets.append(tuple(range(n)))
        exhaustive = False

    rows = []
    for combo in subsets:
        removed = set(combo)
        residual_daily = sum(d for i, d in enumerate(delays) if i not in removed)
        annual_cost = sc_mod.social_cost({"delay_total_min": residual_daily}, params)["annual_cost_brl"]
        benefit = base_annual_cost - annual_cost
        obra = sum(float(costs.get(names[i], 0.0) or 0.0) for i in combo)
        payback = (obra / benefit) if (benefit > 0 and obra > 0) else None
        ibc = ((benefit * horizon_years) / obra) if obra > 0 else None
        rows.append({
            "n_intervencoes": len(combo),
            "cruzamentos_melhorados": ", ".join(names[i] for i in combo) or "(nenhuma — base)",
            "atraso_diario": residual_daily,
            "atraso_anual": residual_daily * days,
            "custo_anual": annual_cost,
            "beneficio_anual": benefit,
            "beneficio_por_intervencao": (benefit / len(combo)) if combo else 0.0,
            "custo_obra": obra,
            "payback_anos": payback,
            "ibc": ibc,
        })
    rows.sort(key=lambda r: r["beneficio_anual"], reverse=True)
    has_costs = any(float(c or 0) > 0 for c in costs.values())
    return {"rows": rows, "exhaustive": exhaustive, "n": n,
            "base_annual_cost": base_annual_cost,
            "horizon_years": horizon_years, "has_costs": has_costs}


def _render_intervention_study(base: dict) -> None:
    """Botão + tabela do estudo de TODOS os cenários de intervenção."""
    its = list(base.get("interferences") or [])
    st.markdown("#### 🎲 Estudo de intervenções — todos os cenários possíveis")
    if not its:
        ui_theme.info("Cadastre interferências (etapa 7) para estudar intervenções.")
        return
    st.caption(
        "Avalia a melhoria de cada interferência **sozinha, em pares, em trios e "
        "todas juntas** (enumeração completa de 2ⁿ combinações). Cada 'melhoria' "
        "equivale a eliminar o atraso daquele cruzamento (ex.: construir viaduto). "
        "O ranking mostra qual obra — ou combinação — traz o maior benefício."
    )
    # ----- Custo de obra por interferência (opcional → custo-benefício) -----
    st.markdown("##### Custo de obra por interferência (opcional)")
    last = st.session_state.get("last_obra_cost")
    if last:
        st.caption(f"💡 Última estimativa (aba **Custo de obra**): {last['type']} — "
                   f"**R$ {last['cost_brl']:,.0f}** ({last['area_m2']:,.0f} m²). "
                   "Digite-a na interferência desejada abaixo.")
    saved = st.session_state.get("obra_costs", {}) or {}
    cost_df = pd.DataFrame({
        "interferência": [it.get("name") for it in its],
        "custo_obra_R$": [float(saved.get(it.get("name"), 0.0)) for it in its],
    })
    edited = st.data_editor(
        cost_df, key="obra_cost_editor", use_container_width=True, hide_index=True,
        disabled=["interferência"],
        column_config={"custo_obra_R$": st.column_config.NumberColumn(
            "custo da obra (R$)", min_value=0.0, step=100000.0, format="%.0f")},
    )
    costs = {r["interferência"]: float(r["custo_obra_R$"] or 0.0)
             for _, r in edited.iterrows()}
    st.session_state["obra_costs"] = costs

    sd = st.session_state.get("study", {}) or {}
    horizon_years = max(int(sd.get("horizon", 0) or 0) - int(sd.get("base_year", 0) or 0), 1)

    if st.button("🎲 Gerar todos os cenários de intervenção", key="gen_interv_study"):
        p = base.get("params") or st.session_state.get("params", {}) or {}
        st.session_state["intervention_study"] = enumerate_interventions(
            base, p, costs, horizon_years)

    study = st.session_state.get("intervention_study")
    if study:
        display_intervention_ranking(study, key_prefix="step8")


def display_intervention_ranking(study: dict, key_prefix: str = "r") -> None:
    """Exibe destaques + tabela do estudo de intervenções (reusável em
    Cenários e Comparação). `key_prefix` evita colisão de chaves de widget."""
    rows = study["rows"]
    n = study["n"]
    has_costs = study.get("has_costs", False)
    st.success(
        f"{len(rows)} cenários avaliados "
        f"({'enumeração completa 2^' + str(n) if study['exhaustive'] else 'amostra: singles+pares+todas'})"
        + (f" · horizonte {study.get('horizon_years')} anos" if has_costs else "") + ".")

    opts = ["Benefício anual"] + (["Payback (menor)", "IBC (maior)"] if has_costs else [])
    sort_opt = st.radio("Ordenar por", opts, horizontal=True, key=f"{key_prefix}_interv_sort")
    if sort_opt == "Payback (menor)":
        rows = sorted(rows, key=lambda r: (r["payback_anos"] is None,
                                           r["payback_anos"] if r["payback_anos"] is not None else 1e18))
    elif sort_opt == "IBC (maior)":
        rows = sorted(rows, key=lambda r: (r["ibc"] is None, -(r["ibc"] or 0)))
    else:
        rows = sorted(rows, key=lambda r: r["beneficio_anual"], reverse=True)

    singles = [r for r in rows if r["n_intervencoes"] == 1]
    best_single = max(singles, key=lambda r: r["beneficio_anual"]) if singles else None
    full = max(rows, key=lambda r: r["n_intervencoes"])
    cA, cB, cC = st.columns(3)
    with cA:
        if best_single:
            ui_theme.card("🥇 Melhor obra única", f"{best_single['cruzamentos_melhorados']}")
            st.caption(f"Benefício R$ {best_single['beneficio_anual']:,.0f}/ano")
    with cB:
        if has_costs:
            pbs = [r for r in rows if r["payback_anos"] is not None]
            best_pb = min(pbs, key=lambda r: r["payback_anos"]) if pbs else None
            if best_pb:
                ui_theme.card("⏱️ Menor payback", f"{best_pb['payback_anos']:.1f} anos")
                st.caption(f"{best_pb['cruzamentos_melhorados']}")
        else:
            eff = max((r for r in rows if r["n_intervencoes"] > 0),
                      key=lambda r: r["beneficio_por_intervencao"], default=None)
            if eff:
                ui_theme.card("💡 Melhor benefício/obra",
                              f"R$ {eff['beneficio_por_intervencao']:,.0f}")
                st.caption(f"{eff['cruzamentos_melhorados']}")
    with cC:
        ui_theme.card("🏆 Resolver todas", f"R$ {full['beneficio_anual']:,.0f}/ano")
        st.caption(f"{full['n_intervencoes']} obras → atraso ~0")

    base_cols = ["n_intervencoes", "cruzamentos_melhorados", "atraso_anual",
                 "custo_anual", "beneficio_anual"]
    extra = (["custo_obra", "payback_anos", "ibc"] if has_costs
             else ["beneficio_por_intervencao"])
    ren = {
        "n_intervencoes": "nº obras",
        "cruzamentos_melhorados": "cruzamentos melhorados",
        "atraso_anual": "atraso anual (viagens·min)",
        "custo_anual": "custo social anual (R$)",
        "beneficio_anual": "benefício anual (R$)",
        "beneficio_por_intervencao": "benefício/obra (R$)",
        "custo_obra": "custo de obra (R$)",
        "payback_anos": "payback (anos)",
        "ibc": "IBC",
    }
    dfv = pd.DataFrame(rows)[base_cols + extra].rename(columns=ren)

    def _money(v): return "—" if pd.isna(v) else f"R$ {v:,.0f}"
    def _num(v): return "—" if pd.isna(v) else f"{v:,.0f}"
    def _pb(v): return "—" if pd.isna(v) else f"{v:.1f}"
    def _ibc(v): return "—" if pd.isna(v) else f"{v:.2f}"
    fmt = {
        "atraso anual (viagens·min)": _num,
        "custo social anual (R$)": _money,
        "benefício anual (R$)": _money,
    }
    if has_costs:
        fmt.update({"custo de obra (R$)": _money, "payback (anos)": _pb, "IBC": _ibc})
    else:
        fmt["benefício/obra (R$)"] = _money

    st.markdown(f"##### Ranking — ordenado por {sort_opt}")
    st.dataframe(dfv.style.format(fmt), use_container_width=True, height=420)
    if has_costs:
        st.caption("**Payback** = custo da obra ÷ benefício anual (anos até se pagar). "
                   "**IBC** = benefício no horizonte ÷ custo da obra (>1 = vale a pena). "
                   "'—' = sem custo informado ou sem benefício.")
    else:
        st.caption("Informe o **custo de obra** (etapa 8) para ranquear por "
                   "**payback** e **IBC** (custo-benefício).")


def render() -> None:
    from . import workflow
    if not workflow.render_guard("cenarios"):
        return
    ui_theme.section_title(8, "Cenários")
    ui_theme.disclaimer_box()

    tab_base, tab_fut, tab_int, tab_mel, tab_cost = st.tabs(
        ["Cenário-base", "Futuro", "Interdição", "Melhoria", "💰 Custo de obra"]
    )

    with tab_cost:
        from . import obra_cost
        obra_cost.render_estimator()

    # ---- Cenário-base ----
    with tab_base:
        st.markdown("Gera o **Cenário 0 — Situação Atual** com o que está cadastrado agora.")
        if st.button("✅ Gerar cenário-base"):
            if st.session_state.get("od_matrix") is None:
                ui_theme.error_message("Gere a matriz O-D antes (etapa 4).")
            else:
                st.session_state["base_scenario"] = snapshot_current()
                ui_theme.remember_status(
                    "base_scenario_done", "success",
                    "Cenário-base gerado com sucesso. Agora você pode criar "
                    "cenários futuros, de interdição ou de melhoria."
                )

        ui_theme.show_status("base_scenario_done")

        base = st.session_state.get("base_scenario")
        if base:
            ind = base.get("assignment", {})
            cc = st.columns(4)
            with cc[0]: ui_theme.card("Σ Viagens", f"{ind.get('total_trips',0):,.0f}")
            with cc[1]: ui_theme.card("Veh·km",   f"{ind.get('veh_km',0):,.0f}")
            with cc[2]: ui_theme.card("Tempo médio (min)", f"{ind.get('avg_time_min',0):.1f}")
            with cc[3]: ui_theme.card("Atraso (min·pessoa)", f"{ind.get('delay_total_min',0):,.0f}")

            _render_base_summary(base, ind)
            st.markdown("---")
            _render_intervention_study(base)

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
                ui_theme.remember_status(
                    "scenario_future_done", "success",
                    f"Cenário '{name}' gerado. "
                    f"Total armazenado nesta sessão: {len(st.session_state['scenarios'])}."
                )
            except Exception as e:
                ui_theme.error_message(f"Falha ao rodar cenário futuro: {e}")
        ui_theme.show_status("scenario_future_done")

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
                    ui_theme.remember_status(
                        "scenario_interdiction_done", "success",
                        f"Cenário de interdição '{name}' gerado com sucesso."
                    )
                except Exception as e:
                    ui_theme.error_message(f"Falha ao rodar cenário de interdição: {e}")
            ui_theme.show_status("scenario_interdiction_done")
        else:
            ui_theme.warning_message("Gere a rede em <b>6. Atribuição</b> primeiro.")

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
                ui_theme.remember_status(
                    "scenario_improvement_done", "success",
                    f"Cenário de melhoria '{name}' gerado com sucesso."
                )
            except Exception as e:
                ui_theme.error_message(f"Falha ao rodar cenário de melhoria: {e}")
        ui_theme.show_status("scenario_improvement_done")

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
