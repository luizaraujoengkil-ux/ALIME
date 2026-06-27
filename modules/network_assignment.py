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


def nearest_edge_flow(lat, lon, edges_df: pd.DataFrame,
                      max_dist_m: float = 250.0) -> float | None:
    """Fluxo (viagens) da aresta mais próxima de um ponto, ou None.

    Mede a distância do ponto ao ponto médio de cada aresta; se a mais próxima
    estiver além de `max_dist_m`, devolve None (ponto não está sobre a rede).
    """
    if edges_df is None or len(edges_df) == 0:
        return None
    need = {"from_lat", "from_lon", "to_lat", "to_lon", "flow"}
    if not need.issubset(set(edges_df.columns)):
        return None
    try:
        lat = float(lat); lon = float(lon)
    except (TypeError, ValueError):
        return None
    if lat == 0.0 and lon == 0.0:
        return None
    best_flow, best_d = None, float("inf")
    for r in edges_df.itertuples(index=False):
        try:
            mlat = (float(r.from_lat) + float(r.to_lat)) / 2.0
            mlon = (float(r.from_lon) + float(r.to_lon)) / 2.0
        except Exception:
            continue
        d = td.haversine_km(lat, lon, mlat, mlon) * 1000.0
        if d < best_d:
            best_d, best_flow = d, float(getattr(r, "flow", 0.0) or 0.0)
    return best_flow if best_d <= max_dist_m else None


def interference_affected_trips(it: dict, edges_df: pd.DataFrame,
                                total_trips: float) -> float:
    """Viagens afetadas por uma interferência.

    Usa o FLUXO da aresta mais próxima (viagens que realmente cruzam o ponto)
    quando há rede com geometria; senão cai para `fração_afetada · total`.
    """
    flow = nearest_edge_flow(it.get("lat"), it.get("lon"), edges_df)
    if flow is not None:
        return flow
    return total_trips * float(it.get("affected_share", 0.10) or 0.10)


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

    # Atraso por interferências — pelo fluxo do trecho (aresta mais próxima);
    # cai para fração agregada quando não há geometria de rede.
    delay_total_min = 0.0
    if interferences:
        for it in interferences:
            blocks = float(it.get("blocks_per_day", 0) or 0)
            tblock = float(it.get("average_blockage_min", 0) or 0)
            tqueue = float(it.get("queue_dissipation_min", 0) or 0)
            affected = interference_affected_trips(it, edges_df, total_trips)
            delay_total_min += blocks * (tblock + tqueue) * affected
    return {
        "total_trips": total_trips,
        "veh_km": veh_km,
        "veh_min": veh_min,
        "avg_dist_km": avg_dist,
        "avg_time_min": avg_time,
        "delay_total_min": delay_total_min,
    }


# ============================================================
# Rede real OSM (OpenStreetMap via OSMnx)
# ============================================================
@st.cache_resource(show_spinner="Baixando malha viária do OpenStreetMap…")
def build_osm_graph(center_lat: float, center_lon: float, radius_m: int,
                    network_type: str = "drive") -> Any:
    """Baixa a malha viária real do OSM em torno de um ponto (cacheado).

    Retorna o grafo dirigido (MultiDiGraph) do osmnx, ou None se OSMnx não
    estiver disponível ou a coleta falhar (sem internet, área vazia, etc.).
    """
    if not OSMNX_OK:
        return None
    try:
        return ox.graph_from_point(
            (float(center_lat), float(center_lon)),
            dist=int(radius_m), network_type=network_type, simplify=True,
        )
    except Exception:
        return None


def zone_nodes(G: Any, zones_df: pd.DataFrame) -> dict[str, int]:
    """Mapeia cada zona ao nó OSM mais próximo. Devolve {zone_id: node_id}.

    Zonas externas (fora do raio) caem no nó de fronteira mais próximo —
    funcionam, na prática, como pontos de cordão da malha.
    """
    mapping: dict[str, int] = {}
    if G is None:
        return mapping
    lats = pd.to_numeric(zones_df["centroid_lat"], errors="coerce")
    lons = pd.to_numeric(zones_df["centroid_lon"], errors="coerce")
    ids = zones_df["zone_id"].astype(str).tolist()
    for zid, la, lo in zip(ids, lats, lons):
        if pd.isna(la) or pd.isna(lo):
            continue
        try:
            mapping[zid] = int(ox.distance.nearest_nodes(G, X=float(lo), Y=float(la)))
        except Exception:
            continue
    return mapping


def osm_distance_matrix(G: Any, znode: dict[str, int],
                        zone_ids: list[str]) -> np.ndarray:
    """Matriz n×n de distâncias (km) pela rede real, via Dijkstra (peso 'length')."""
    n = len(zone_ids)
    D = np.full((n, n), np.nan)
    if G is None:
        return D
    for i in range(n):
        ni = znode.get(str(zone_ids[i]))
        if ni is None:
            continue
        try:
            lengths = nx.single_source_dijkstra_path_length(G, ni, weight="length")
        except Exception:
            continue
        for j in range(n):
            nj = znode.get(str(zone_ids[j]))
            if nj is not None and nj in lengths:
                D[i, j] = lengths[nj] / 1000.0
    return D


def mixed_distance_matrix(G: Any, znode: dict[str, int], zones_df: pd.DataFrame,
                          zone_ids: list[str], center_lat: float, center_lon: float,
                          radius_m: float) -> tuple[np.ndarray, list[bool]]:
    """Distância entre zonas combinando rede real e linha reta.

    - Ambas as zonas DENTRO do raio  → distância pela rede (Dijkstra/extensão).
    - Alguma zona FORA do raio        → distância em linha reta (haversine),
      pois a malha baixada não cobre aquele ponto.

    Retorna (D_km, inside), onde inside[i] indica se a zona i está no raio.
    """
    n = len(zone_ids)
    lats = pd.to_numeric(zones_df["centroid_lat"], errors="coerce").to_numpy()
    lons = pd.to_numeric(zones_df["centroid_lon"], errors="coerce").to_numpy()
    radius_km = radius_m / 1000.0
    inside = []
    for i in range(n):
        if np.isnan(lats[i]) or np.isnan(lons[i]):
            inside.append(False)
        else:
            d_center = td.haversine_km(center_lat, center_lon, lats[i], lons[i])
            inside.append(bool(d_center <= radius_km))

    netD = osm_distance_matrix(G, znode, zone_ids)
    D = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(n):
            if i == j:
                D[i, j] = 0.0
                continue
            if inside[i] and inside[j] and not np.isnan(netD[i, j]):
                D[i, j] = netD[i, j]                       # rede real (Dijkstra)
            elif not (np.isnan(lats[i]) or np.isnan(lons[i])
                      or np.isnan(lats[j]) or np.isnan(lons[j])):
                D[i, j] = td.haversine_km(lats[i], lons[i], lats[j], lons[j])  # reta
    return D, inside


def assign_on_osm(G: Any, T: np.ndarray, znode: dict[str, int],
                  zone_ids: list[str], speed_kmh: float = 35.0) -> pd.DataFrame:
    """Aloca a matriz O-D nas arestas reais do OSM (all-or-nothing por Dijkstra).

    Retorna edges_df só com as arestas usadas (flow>0): from/to, comprimento,
    tempo livre, coordenadas dos nós e fluxo — pronto para render e indicadores.
    """
    if G is None:
        return pd.DataFrame()
    edge_flow: dict[tuple[int, int], float] = {}
    n = len(zone_ids)
    for i in range(n):
        ni = znode.get(str(zone_ids[i]))
        if ni is None:
            continue
        for j in range(n):
            if i == j:
                continue
            tij = float(T[i, j])
            if tij <= 0:
                continue
            nj = znode.get(str(zone_ids[j]))
            if nj is None:
                continue
            try:
                path = nx.shortest_path(G, ni, nj, weight="length")
            except Exception:
                continue
            for a, b in zip(path[:-1], path[1:]):
                edge_flow[(a, b)] = edge_flow.get((a, b), 0.0) + tij

    rows = []
    for (a, b), f in edge_flow.items():
        data = G.get_edge_data(a, b)
        if not data:
            continue
        length_m = min(d.get("length", 0.0) for d in data.values())
        length_km = length_m / 1000.0
        rows.append({
            "from": a, "to": b,
            "length_km": length_km,
            "free_time_min": (length_km / max(speed_kmh, 1e-6)) * 60.0,
            "from_lat": G.nodes[a]["y"], "from_lon": G.nodes[a]["x"],
            "to_lat":   G.nodes[b]["y"], "to_lon":   G.nodes[b]["x"],
            "flow": f,
        })
    return pd.DataFrame(rows)


# ============================================================
# UI
# ============================================================
def render() -> None:
    from . import workflow
    if not workflow.render_guard("atribuicao"):
        return
    ui_theme.section_title(6, "Atribuição — Por onde vou?")
    ui_theme.warn("Atribuição all-or-nothing (sem congestionamento) — exploratória, **não substitui** modelo de tráfego calibrado.")

    zones_df = st.session_state.get("zones")
    T = st.session_state.get("od_matrix")
    if zones_df is None or zones_df.empty or T is None:
        ui_theme.warning_message("Cadastre as zonas e gere a matriz O-D antes de alocar.")
        return
    T = np.asarray(T, dtype=float)
    zone_ids = zones_df["zone_id"].astype(str).tolist()

    st.markdown("#### Malha viária")
    cc = st.columns(3)
    with cc[0]:
        net_mode = st.radio(
            "Tipo de malha",
            ["Real (OpenStreetMap)", "Simplificada (k-vizinhos)"],
            index=0 if OSMNX_OK else 1,
            help="A malha REAL baixa as ruas do OSM e calcula caminhos mínimos "
                 "por Dijkstra (peso = extensão). A simplificada liga os "
                 "centroides aos k vizinhos mais próximos.",
        )
    use_osm = net_mode.startswith("Real")
    with cc[1]:
        speed = st.number_input("Velocidade média (km/h)",
                                value=float(st.session_state["params"]["default_speed_kmh"]),
                                min_value=5.0, max_value=120.0, step=1.0)
    k, radius_m = 3, 3000
    with cc[2]:
        if use_osm:
            radius_km = st.slider("Raio de download (km)", min_value=1.0, max_value=5.0,
                                  value=3.0, step=0.5,
                                  help="Área de atuação em torno do centro das zonas "
                                       "internas. Zonas FORA do raio têm a distância "
                                       "estimada por linha reta (haversine).")
            radius_m = int(radius_km * 1000)
        else:
            k = st.number_input("Vizinhos por nó (k)", min_value=1, max_value=10,
                                value=3, step=1)

    if use_osm and not OSMNX_OK:
        ui_theme.warning_message(
            "OSMnx indisponível neste ambiente — a malha real não pode ser baixada. "
            "Usando malha simplificada.")
        use_osm = False

    if st.button("🧮 Construir rede e alocar"):
        if use_osm:
            clat, clon = map_utils._center_from_zones(zones_df)
            G = build_osm_graph(clat, clon, int(radius_m))
            if G is None:
                ui_theme.warn(
                    "Não foi possível baixar a malha OSM (sem internet ou área "
                    "vazia). Tente outro raio ou use a malha simplificada.")
            else:
                znode = zone_nodes(G, zones_df)
                edges_df = assign_on_osm(G, T, znode, zone_ids, speed_kmh=speed)
                D, inside = mixed_distance_matrix(
                    G, znode, zones_df, zone_ids, clat, clon, int(radius_m))
                n_out = sum(1 for x in inside if not x)
                st.session_state["network"] = {
                    "graph": G, "edges": edges_df, "kind": "osm",
                    "znode": znode, "radius_m": int(radius_m),
                    "center": (clat, clon),
                    "n_nodes": G.number_of_nodes(), "n_edges": G.number_of_edges(),
                }
                st.session_state["network_distance_km"] = {
                    "matrix": D, "zone_ids": zone_ids, "inside": inside,
                    "radius_km": radius_m / 1000.0, "n_out": n_out}
                ind = compute_indicators(edges_df, T, st.session_state.get("interferences"))
                st.session_state["assignment"] = ind
                ui_theme.remember_status(
                    "assignment_done", "success",
                    f"Atribuição na malha real OSM concluída — {G.number_of_nodes()} "
                    f"nós e {G.number_of_edges()} arestas. Distâncias por Dijkstra "
                    f"disponíveis para o modelo gravitacional.")
        else:
            net = build_simplified_network(zones_df, k_neighbors=int(k), speed_kmh=speed)
            edges_df = all_or_nothing(net["graph"], T, zone_ids)
            net["edges"] = edges_df
            net["kind"] = "simplified"
            st.session_state["network"] = net
            st.session_state.pop("network_distance_km", None)
            ind = compute_indicators(edges_df, T, st.session_state.get("interferences"))
            st.session_state["assignment"] = ind
            ui_theme.remember_status(
                "assignment_done", "success",
                "Atribuição na rede simplificada concluída.")

    ui_theme.show_status("assignment_done")

    net = st.session_state.get("network")
    ind = st.session_state.get("assignment")
    if net is None or ind is None:
        ui_theme.info("Configure os parâmetros e clique em **Construir rede e alocar**.")
        return

    if net.get("kind") == "osm":
        ui_theme.info(
            f"Malha real OSM: **{net.get('n_nodes','?')} nós** e "
            f"**{net.get('n_edges','?')} arestas** "
            f"(área de atuação: raio {net.get('radius_m',0)/1000:.1f} km).")

    c1, c2, c3, c4 = st.columns(4)
    with c1: ui_theme.card("Viagens totais",   ui_theme.num_br(ind['total_trips']))
    with c2: ui_theme.card("Veh·km",           ui_theme.num_br(ind['veh_km']))
    with c3: ui_theme.card("Tempo médio (min)", ui_theme.num_br(ind['avg_time_min'], 1))
    with c4: ui_theme.card("Atraso total (min·pessoa)", ui_theme.num_br(ind['delay_total_min']))

    edges_df = net.get("edges")
    if edges_df is None or edges_df.empty:
        ui_theme.warn("Rede vazia. Verifique os centroides das zonas e a matriz O-D.")
        return

    st.markdown("### Mapa de carregamento")
    _tiles, _attr = map_utils.theme_selector("assign_map_theme", default="OpenStreetMap")
    show_net = False
    if net.get("kind") == "osm" and net.get("graph") is not None:
        show_net = st.checkbox("Mostrar a malha viária extraída (OSM)", value=True,
                               key="show_osm_net")
    map_utils.warn_if_null_island(zones_df)
    m = map_utils.base_map(zones_df, tiles=_tiles, attr=_attr)
    if show_net:
        m = map_utils.add_osm_network(m, net["graph"])
    # Círculo da área de atuação (raio considerado)
    if net.get("kind") == "osm" and net.get("center"):
        m = map_utils.add_radius_circle(m, net["center"][0], net["center"][1],
                                        net.get("radius_m", 0))
    m = map_utils.add_zones(m, zones_df)
    m = map_utils.add_link_loads(m, edges_df, flow_col="flow")
    map_utils.show(m, height=520)

    nd = st.session_state.get("network_distance_km")
    if nd is not None and net.get("kind") == "osm":
        st.markdown("### Distâncias entre zonas (km)")
        n_out = nd.get("n_out", 0)
        rkm = nd.get("radius_km", 0)
        if n_out:
            ui_theme.info(
                f"Dentro do raio ({rkm:.1f} km): **distância pela rede real** "
                f"(Dijkstra). Fora do raio ({n_out} zona(s), ex.: externas): "
                f"**distância em linha reta** (haversine), pois a malha não as cobre.")
        ids = nd["zone_ids"]
        inside = nd.get("inside", [True] * len(ids))
        labels = [f"{z}{'' if ins else ' ⟂'}" for z, ins in zip(ids, inside)]
        ddf = pd.DataFrame(nd["matrix"], index=labels, columns=labels).round(2)
        st.dataframe(ddf, use_container_width=True)
        st.caption("⟂ = zona fora do raio (distância estimada por linha reta). "
                   "Estas distâncias podem alimentar o modelo gravitacional (etapa 4).")

    st.markdown("### Trechos mais carregados")
    top = edges_df.sort_values("flow", ascending=False).head(20)
    st.dataframe(top[["from", "to", "length_km", "free_time_min", "flow"]]
                 .round({"length_km": 2, "free_time_min": 2, "flow": 1}),
                 use_container_width=True)
