"""Tela 6 — Atribuição na rede (Por onde vou?).

Aloca os fluxos da matriz O-D na rede viária pelo método all-or-nothing:

    x_a = Σ_ij T_ij · δ_a,ij

onde δ_a,ij = 1 se a aresta a pertence ao caminho mínimo entre i e j.

A rede pode vir de:
- OSMnx (se disponível e se houver conectividade);
- arquivo importado (GeoJSON simples com from/to/length);
- rede simplificada gerada automaticamente dos centroides das zonas
  (grafo k-vizinhos, fallback robusto que NÃO quebra se faltar OSMnx).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

try:
    import networkx as nx
    NX_OK = True
except Exception:
    NX_OK = False

try:
    import osmnx as ox
    OSMNX_OK = True
except Exception:
    OSMNX_OK = False

from . import ui_theme, map_utils, trip_distribution as td


# ============================================================
# Construção de rede
# ============================================================
def build_simplified_network(zones_df: pd.DataFrame, k_neighbors: int = 3,
                              speed_kmh: float = 35.0) -> dict:
    """Cria uma rede simplificada conectando cada centroide aos k vizinhos mais próximos.

    Cada aresta guarda comprimento (km), tempo livre (min), capacidade nominal e
    coordenadas (para renderização).
    """
    if not NX_OK:
        return {"graph": None, "edges": pd.DataFrame()}
    G = nx.Graph()
    lats = pd.to_numeric(zones_df["centroid_lat"], errors="coerce").to_numpy()
    lons = pd.to_numeric(zones_df["centroid_lon"], errors="coerce").to_numpy()
    ids = zones_df["zone_id"].astype(str).tolist()
    n = len(ids)
    for i in range(n):
        G.add_node(ids[i], lat=float(lats[i]), lon=float(lons[i]))

    # Lista de arestas candidatas: cada nó conecta aos k vizinhos mais próximos
    edges: list[tuple[str, str, float]] = []
    for i in range(n):
        dists = []
        for j in range(n):
            if i == j:
                continue
            d = td.haversine_km(lats[i], lons[i], lats[j], lons[j])
            dists.append((d, j))
        dists.sort()
        for d, j in dists[:k_neighbors]:
            a, b = sorted([ids[i], ids[j]])
            edges.append((a, b, d))

    seen = set()
    rows = []
    for a, b, d in edges:
        if (a, b) in seen:
            continue
        seen.add((a, b))
        tmin = (d / max(speed_kmh, 1e-6)) * 60.0
        G.add_edge(a, b, length_km=d, free_time_min=tmin,
                   speed_kmh=speed_kmh, capacity=1500.0, flow=0.0)
        rows.append({
            "from": a, "to": b, "length_km": d, "free_time_min": tmin,
            "from_lat": G.nodes[a]["lat"], "from_lon": G.nodes[a]["lon"],
            "to_lat":   G.nodes[b]["lat"], "to_lon":   G.nodes[b]["lon"],
            "flow": 0.0,
        })
    edges_df = pd.DataFrame(rows)
    return {"graph": G, "edges": edges_df}


# ============================================================
# All-or-nothing assignment
# ============================================================
def all_or_nothing(G: Any, T: np.ndarray, zone_ids: list[str],
                   weight: str = "free_time_min") -> pd.DataFrame:
    """Aloca toda a demanda no caminho mínimo de cada par O-D.

    x_a = Σ_ij T_ij · δ_a,ij

    Retorna DataFrame de arestas com a coluna `flow` atualizada.
    """
    if not NX_OK or G is None:
        return pd.DataFrame()
    edge_flow: dict[tuple[str, str], float] = {}
    n = len(zone_ids)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            tij = float(T[i, j])
            if tij <= 0:
                continue
            try:
                path = nx.shortest_path(G, zone_ids[i], zone_ids[j], weight=weight)
            except Exception:
                continue
            for a, b in zip(path[:-1], path[1:]):
                key = tuple(sorted([a, b]))
                edge_flow[key] = edge_flow.get(key, 0.0) + tij

    rows = []
    for (a, b), data in G.edges.items():
        key = tuple(sorted([a, b]))
        rows.append({
            "from": a, "to": b,
            "length_km": data.get("length_km", 0.0),
            "free_time_min": data.get("free_time_min", 0.0),
            "from_lat": G.nodes[a]["lat"], "from_lon": G.nodes[a]["lon"],
            "to_lat":   G.nodes[b]["lat"], "to_lon":   G.nodes[b]["lon"],
            "flow": float(edge_flow.get(key, 0.0)),
        })
    return pd.DataFrame(rows)


def compute_indicators(edges_df: pd.DataFrame, T: np.ndarray,
                       interferences: list[dict] | None = None) -> dict:
    """Indicadores de saída: distância média ponderada, tempo médio, atraso total."""
    if edges_df is None or edges_df.empty:
        return {}
    total_trips = float(T.sum())
    veh_km = float((edges_df["length_km"] * edges_df["flow"]).sum())
    veh_min = float((edges_df["free_time_min"] * edges_df["flow"]).sum())
    avg_dist = veh_km / max(total_trips, 1e-9)
    avg_time = veh_min / max(total_trips, 1e-9)

    # Atraso por interferências (aplicado de forma agregada)
    delay_total_min = 0.0
    if interferences:
        for it in interferences:
            blocks = float(it.get("blocks_per_day", 0) or 0)
            tblock = float(it.get("average_blockage_min", 0) or 0)
            tqueue = float(it.get("queue_dissipation_min", 0) or 0)
            affected_share = float(it.get("affected_share", 0.10) or 0.10)
            people = total_trips * affected_share
            delay_total_min += blocks * (tblock + tqueue) * people
    return {
        "total_trips": total_trips,
        "veh_km": veh_km,
        "veh_min": veh_min,
        "avg_dist_km": avg_dist,
        "avg_time_min": avg_time,
        "delay_total_min": delay_total_min,
    }


# ============================================================
# UI
# ============================================================
def render() -> None:
    ui_theme.section_title(6, "Atribuição — Por onde vou?")
    ui_theme.warn("Esta atribuição é simplificada (all-or-nothing) e **não substitui** modelo de tráfego calibrado.")

    zones_df = st.session_state.get("zones")
    T = st.session_state.get("od_matrix")
    if zones_df is None or zones_df.empty or T is None:
        ui_theme.warning_message("Cadastre as zonas e gere a matriz O-D antes de alocar.")
        return

    cc = st.columns(3)
    with cc[0]:
        k = st.number_input("Vizinhos por nó (k)", min_value=1, max_value=10, value=3, step=1)
    with cc[1]:
        speed = st.number_input("Velocidade média (km/h)",
                                value=float(st.session_state["params"]["default_speed_kmh"]),
                                min_value=5.0, max_value=120.0, step=1.0)
    with cc[2]:
        use_osmnx = st.checkbox("Tentar usar OSMnx", value=False,
                                disabled=not OSMNX_OK,
                                help="Requer OSMnx instalado e internet. "
                                     "Em V01, recomenda-se rede simplificada.")

    if st.button("🧮 Construir rede e alocar"):
        net = build_simplified_network(zones_df, k_neighbors=int(k), speed_kmh=speed)
        if use_osmnx and OSMNX_OK:
            ui_theme.info("OSMnx detectado — esta versão usa rede simplificada por estabilidade. "
                          "Integração OSM completa fica para futuras versões.")
        st.session_state["network"] = net
        zone_ids = zones_df["zone_id"].astype(str).tolist()
        edges_df = all_or_nothing(net["graph"], T, zone_ids)
        st.session_state["network"]["edges"] = edges_df
        ind = compute_indicators(edges_df, T, st.session_state.get("interferences"))
        st.session_state["assignment"] = ind
        ui_theme.remember_status(
            "assignment_done", "success",
            "Atribuição na rede concluída com sucesso. "
            "Você já pode cadastrar interferências e gerar o cenário-base."
        )

    ui_theme.show_status("assignment_done")

    net = st.session_state.get("network")
    ind = st.session_state.get("assignment")
    if net is None or ind is None:
        ui_theme.info("Configure os parâmetros e clique em **Construir rede e alocar**.")
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1: ui_theme.card("Viagens totais",   f"{ind['total_trips']:,.0f}")
    with c2: ui_theme.card("Veh·km",           f"{ind['veh_km']:,.0f}")
    with c3: ui_theme.card("Tempo médio (min)", f"{ind['avg_time_min']:,.1f}")
    with c4: ui_theme.card("Atraso total (min·pessoa)", f"{ind['delay_total_min']:,.0f}")

    edges_df = net.get("edges")
    if edges_df is None or edges_df.empty:
        ui_theme.warn("Rede vazia. Verifique os centroides das zonas.")
        return

    st.markdown("### Mapa de carregamento")
    m = map_utils.base_map(zones_df)
    m = map_utils.add_zones(m, zones_df)
    m = map_utils.add_link_loads(m, edges_df, flow_col="flow")
    map_utils.show(m, height=520)

    st.markdown("### Trechos mais carregados")
    top = edges_df.sort_values("flow", ascending=False).head(20)
    st.dataframe(top[["from", "to", "length_km", "free_time_min", "flow"]]
                 .round({"length_km": 2, "free_time_min": 2, "flow": 1}),
                 use_container_width=True)
