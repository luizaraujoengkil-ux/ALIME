"""Helpers de mapa: criação de mapa folium, camadas de zonas, linhas de desejo, atribuição.

Todas as funções degradam graciosamente se folium/streamlit_folium não estiver disponível.
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except Exception:
    FOLIUM_OK = False


def _center_from_zones(zones_df: pd.DataFrame) -> tuple[float, float]:
    if zones_df is None or zones_df.empty:
        return -15.78, -47.93  # Brasília como fallback
    lats = pd.to_numeric(zones_df.get("centroid_lat"), errors="coerce").dropna()
    lons = pd.to_numeric(zones_df.get("centroid_lon"), errors="coerce").dropna()
    if lats.empty or lons.empty:
        return -15.78, -47.93
    return float(lats.mean()), float(lons.mean())


def base_map(zones_df: pd.DataFrame | None = None, zoom: int = 13) -> Any:
    """Cria um mapa folium em estilo escuro centrado nas zonas."""
    if not FOLIUM_OK:
        return None
    lat, lon = _center_from_zones(zones_df) if zones_df is not None else (-15.78, -47.93)
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom,
        tiles="CartoDB dark_matter",
        control_scale=True,
    )
    return m


def add_zones(m: Any, zones_df: pd.DataFrame) -> Any:
    """Adiciona marcadores (centroides) das zonas no mapa."""
    if not FOLIUM_OK or m is None or zones_df is None or zones_df.empty:
        return m
    for _, row in zones_df.iterrows():
        try:
            lat = float(row.get("centroid_lat"))
            lon = float(row.get("centroid_lon"))
        except Exception:
            continue
        if not (lat == lat and lon == lon):  # NaN
            continue
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="#F5B700",
            fill=True,
            fill_color="#F5B700",
            fill_opacity=0.85,
            popup=folium.Popup(
                f"<b>{row.get('zone_name', row.get('zone_id'))}</b><br>"
                f"Pop: {row.get('population','-')}<br>"
                f"P: {row.get('production','-')} | A: {row.get('attraction','-')}",
                max_width=250,
            ),
        ).add_to(m)
    return m


def add_desire_lines(m: Any, zones_df: pd.DataFrame, od: np.ndarray,
                     zone_ids: list, top_n: int = 30) -> Any:
    """Adiciona as N maiores linhas de desejo da matriz O-D."""
    if not FOLIUM_OK or m is None or od is None or zones_df is None or zones_df.empty:
        return m
    coord = {
        str(z["zone_id"]): (float(z["centroid_lat"]), float(z["centroid_lon"]))
        for _, z in zones_df.iterrows()
        if pd.notna(z.get("centroid_lat")) and pd.notna(z.get("centroid_lon"))
    }
    pairs = []
    n = od.shape[0]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            pairs.append((od[i, j], i, j))
    pairs.sort(reverse=True, key=lambda x: x[0])
    pairs = pairs[:top_n]
    if not pairs:
        return m
    vmax = pairs[0][0] or 1
    for val, i, j in pairs:
        oi = str(zone_ids[i])
        dj = str(zone_ids[j])
        if oi not in coord or dj not in coord:
            continue
        w = 1 + 6 * (val / vmax)
        folium.PolyLine(
            locations=[coord[oi], coord[dj]],
            color="#FF7A00",
            weight=w,
            opacity=0.7,
            tooltip=f"{oi} → {dj} : {val:.1f} viagens",
        ).add_to(m)
    return m


def add_link_loads(m: Any, edges_df: pd.DataFrame, flow_col: str = "flow") -> Any:
    """Renderiza arestas com cor/espessura proporcional ao fluxo.

    `edges_df` deve ter colunas: from_lat, from_lon, to_lat, to_lon, flow.
    """
    if not FOLIUM_OK or m is None or edges_df is None or edges_df.empty:
        return m
    vmax = float(edges_df[flow_col].max() or 1)
    for _, r in edges_df.iterrows():
        f = float(r.get(flow_col, 0))
        if f <= 0:
            continue
        ratio = f / vmax
        # vermelho intenso para mais carregado, amarelo para médio, azul para leve
        if ratio > 0.66:
            color = "#E53935"
        elif ratio > 0.33:
            color = "#F5B700"
        else:
            color = "#28A8FF"
        folium.PolyLine(
            locations=[(r["from_lat"], r["from_lon"]), (r["to_lat"], r["to_lon"])],
            color=color,
            weight=1 + 7 * ratio,
            opacity=0.85,
            tooltip=f"Fluxo: {f:.1f}",
        ).add_to(m)
    return m


def show(m: Any, height: int = 520):
    """Renderiza no Streamlit. Se folium ausente, mostra placeholder."""
    if FOLIUM_OK and m is not None:
        return st_folium(m, height=height, use_container_width=True)
    import streamlit as st
    st.info("Mapa indisponível (folium/streamlit-folium não instalado). Instale com `pip install folium streamlit-folium`.")
    return None
