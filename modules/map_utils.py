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


# Temas de basemap (rótulo amigável -> (tiles, attribution)).
# Para tiles nativos do folium, attribution = None. Para URLs externas
# (ex.: satélite Esri) a attribution é obrigatória.
TILE_THEMES = {
    "Claro": ("CartoDB positron", None),
    "Escuro": ("CartoDB dark_matter", None),
    "OpenStreetMap": ("OpenStreetMap", None),
    "Satélite": (
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "Esri, Maxar, Earthstar Geographics, GIS User Community",
    ),
}

# Distância (em graus) de (0,0) abaixo da qual consideramos que as
# coordenadas são offsets de exemplo, e não coordenadas reais. ~1° ≈ 111 km.
NULL_ISLAND_TOL = 1.0


def _center_from_zones(zones_df: pd.DataFrame) -> tuple[float, float]:
    if zones_df is None or zones_df.empty:
        return -15.78, -47.93  # Brasília como fallback
    df = zones_df
    # Centraliza nas zonas INTERNAS — as externas/cordão (ex.: Rio de Janeiro)
    # podem ficar a dezenas de km e puxariam o mapa para longe da área de estudo.
    if "zone_type" in df.columns:
        internal = df[df["zone_type"].astype(str).str.strip().str.lower() != "externo"]
        if not internal.empty:
            df = internal
    lats = pd.to_numeric(df.get("centroid_lat"), errors="coerce").dropna()
    lons = pd.to_numeric(df.get("centroid_lon"), errors="coerce").dropna()
    if lats.empty or lons.empty:
        return -15.78, -47.93
    return float(lats.mean()), float(lons.mean())


def coords_status(zones_df: pd.DataFrame | None) -> tuple[str, int]:
    """Classifica as coordenadas das zonas.

    Retorna (status, n_validos):
        "empty"        — sem coordenadas válidas.
        "null_island"  — há coords válidas, mas todas a menos de
                          NULL_ISLAND_TOL graus de (0,0). Quase sempre são
                          offsets de exemplo (caem no Oceano Atlântico), e o
                          basemap fica "vazio" porque não há ruas ali.
        "ok"           — coordenadas reais.
    """
    if zones_df is None or zones_df.empty:
        return ("empty", 0)
    lats = pd.to_numeric(zones_df.get("centroid_lat"), errors="coerce").dropna()
    lons = pd.to_numeric(zones_df.get("centroid_lon"), errors="coerce").dropna()
    n = int(min(len(lats), len(lons)))
    if n == 0:
        return ("empty", 0)
    near_null = bool((lats.abs() < NULL_ISLAND_TOL).all()
                     and (lons.abs() < NULL_ISLAND_TOL).all())
    return ("null_island" if near_null else "ok", n)


def theme_selector(key: str, default: str = "OpenStreetMap") -> tuple[str, str | None]:
    """Renderiza o seletor de estilo do mapa.

    Devolve (tiles, attribution) prontos para passar a `base_map`.
    """
    import streamlit as st
    options = list(TILE_THEMES.keys())
    if default not in options:
        default = options[0]
    label = st.radio(
        "Estilo do mapa",
        options,
        index=options.index(default),
        horizontal=True,
        key=key,
        help="Satélite e OpenStreetMap mostram a cidade ao fundo; "
             "Claro/Escuro são mapas estilizados.",
    )
    return TILE_THEMES[label]


def warn_if_null_island(zones_df: pd.DataFrame | None) -> bool:
    """Avisa quando os centroides estão perto de (0,0). Retorna True se avisou."""
    status, _ = coords_status(zones_df)
    if status == "null_island":
        import streamlit as st
        st.warning(
            "As coordenadas das zonas estão muito próximas de **(0, 0)** — que "
            "fica no meio do Oceano Atlântico. O mapa carrega normalmente, mas o "
            "fundo aparece vazio porque não há ruas nesse ponto. Edite "
            "`centroid_lat` e `centroid_lon` na aba **Tabela editável** com "
            "coordenadas reais da sua área (ex.: -15.79, -47.88)."
        )
        return True
    return False


def base_map(zones_df: pd.DataFrame | None = None, zoom: int = 13,
             tiles: str = "CartoDB dark_matter", attr: str | None = None) -> Any:
    """Cria um mapa folium centrado nas zonas.

    `tiles` aceita basemaps nativos do folium (ex.: "OpenStreetMap") ou uma
    URL de tiles externa (ex.: satélite Esri), caso em que `attr` é obrigatório.
    """
    if not FOLIUM_OK:
        return None
    lat, lon = _center_from_zones(zones_df) if zones_df is not None else (-15.78, -47.93)
    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom,
        tiles=tiles,
        attr=attr,
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
        zid = row.get("zone_id")
        zname = row.get("zone_name")
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="#F5B700",
            fill=True,
            fill_color="#F5B700",
            fill_opacity=0.9,
            tooltip=str(zname if pd.notna(zname) and str(zname).strip() else zid),
            popup=folium.Popup(
                f"<b>{zid} — {zname}</b><br>"
                f"Pop: {row.get('population','-')}<br>"
                f"P: {row.get('production','-')} | A: {row.get('attraction','-')}",
                max_width=250,
            ),
        ).add_to(m)
        # Rótulo fixo com o código da zona (ZT01, ZTE01...) ao lado da bolinha.
        if pd.notna(zid) and str(zid).strip():
            folium.map.Marker(
                [lat, lon],
                icon=folium.DivIcon(
                    icon_size=(0, 0),
                    icon_anchor=(0, 0),
                    html=(
                        '<div style="font-size:11px;font-weight:700;color:#2E9BFF;'
                        'background:rgba(15,23,38,0.82);padding:1px 5px;'
                        'border-radius:6px;border:1px solid #2E9BFF;'
                        'white-space:nowrap;transform:translate(8px,-8px);">'
                        f'{zid}</div>'
                    ),
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
