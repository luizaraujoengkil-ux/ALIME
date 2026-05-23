"""Tela 2 — Zonas e Microzonas.

Define unidades de análise. Permite criar, editar, importar (CSV/Excel/GeoJSON/KML/KMZ)
e remover zonas. Renderiza centroides no mapa.
"""
from __future__ import annotations

import io
import json

import pandas as pd
import streamlit as st

from . import ui_theme, map_utils


ZONE_TYPES = [
    "residencial",
    "comercial/serviços",
    "industrial/logístico",
    "centro/núcleo urbano",
    "misto",
    "rural/periurbano",
    "externo",
    "equipamento público",
    "outro",
]


ZONE_COLUMNS = [
    "zone_id", "zone_name", "zone_type",
    "population", "jobs", "schools", "commerce", "industry",
    "production", "attraction",
    "generation_weight", "attraction_weight",
    "centroid_lat", "centroid_lon",
    "notes",
]


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=ZONE_COLUMNS)


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    """Garante todas as colunas esperadas e tipos numéricos básicos."""
    df = df.copy()
    for c in ZONE_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[ZONE_COLUMNS]
    num_cols = ["population", "jobs", "schools", "commerce", "industry",
                "production", "attraction", "generation_weight", "attraction_weight",
                "centroid_lat", "centroid_lon"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _read_uploaded(uploaded) -> pd.DataFrame:
    """Leitura tolerante: CSV, Excel, GeoJSON, KML/KMZ."""
    name = uploaded.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded)
    if name.endswith(".geojson") or name.endswith(".json"):
        gj = json.loads(uploaded.read().decode("utf-8"))
        feats = gj.get("features", [])
        rows = []
        for f in feats:
            props = f.get("properties", {}) or {}
            geom = f.get("geometry") or {}
            lat = lon = None
            if geom.get("type") == "Point":
                coords = geom.get("coordinates") or [None, None]
                lon, lat = coords[0], coords[1]
            rows.append({**props, "centroid_lat": lat, "centroid_lon": lon})
        return pd.DataFrame(rows)
    if name.endswith((".kml", ".kmz")):
        # Tenta via geopandas (que cobre KML/KMZ se Fiona/pyogrio estiver disponível)
        try:
            import geopandas as gpd  # noqa: F401
            tmp = io.BytesIO(uploaded.read())
            gdf = gpd.read_file(tmp)
            gdf["centroid_lat"] = gdf.geometry.centroid.y
            gdf["centroid_lon"] = gdf.geometry.centroid.x
            return pd.DataFrame(gdf.drop(columns=["geometry"]))
        except Exception as e:
            raise RuntimeError(f"Não foi possível ler KML/KMZ: {e}")
    raise RuntimeError(f"Formato não suportado: {name}")


def render() -> None:
    ui_theme.section_title(2, "Zonas e Microzonas")
    st.markdown(
        "<p style='color:#B8C0CC'>"
        "Zonas são partes da cidade usadas para estimar de onde as viagens saem e para onde elas vão. "
        "Você pode criá-las manualmente, importar arquivos ou usar um estudo demo."
        "</p>", unsafe_allow_html=True,
    )

    if st.session_state.get("zones") is None:
        st.session_state["zones"] = _empty_df()

    df = _coerce(st.session_state["zones"])

    tab_edit, tab_import, tab_map, tab_add = st.tabs(
        ["Tabela editável", "Importar arquivo", "Mapa", "Adicionar zona"]
    )

    with tab_edit:
        st.caption("Edite diretamente. Use o botão (+) ao final para nova linha.")
        edited = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "zone_type": st.column_config.SelectboxColumn(
                    "zone_type", options=ZONE_TYPES, required=False,
                ),
                "centroid_lat": st.column_config.NumberColumn("centroid_lat", format="%.6f"),
                "centroid_lon": st.column_config.NumberColumn("centroid_lon", format="%.6f"),
            },
            key="zones_editor",
        )
        if st.button("💾 Salvar alterações"):
            st.session_state["zones"] = _coerce(edited)
            ui_theme.ok(f"{len(edited)} zonas salvas.")

    with tab_import:
        up = st.file_uploader(
            "Arquivo de zonas (CSV, Excel, GeoJSON, KML, KMZ)",
            type=["csv", "xlsx", "xls", "geojson", "json", "kml", "kmz"],
        )
        if up is not None:
            try:
                raw = _read_uploaded(up)
                st.write("Pré-visualização (10 primeiras linhas):")
                st.dataframe(raw.head(10), use_container_width=True)
                # Heurística simples: já tenta mapear colunas conhecidas
                rename = {}
                for c in raw.columns:
                    lc = c.lower().strip()
                    if lc in ("zona", "id", "id_zona", "zone", "zone_id", "codigo"):
                        rename[c] = "zone_id"
                    elif lc in ("nome", "name", "zone_name"):
                        rename[c] = "zone_name"
                    elif lc in ("tipo", "type", "zone_type"):
                        rename[c] = "zone_type"
                    elif lc in ("populacao", "população", "population", "pop"):
                        rename[c] = "population"
                    elif lc in ("producao", "produção", "production"):
                        rename[c] = "production"
                    elif lc in ("atracao", "atração", "attraction"):
                        rename[c] = "attraction"
                    elif lc in ("lat", "latitude", "centroid_lat", "y"):
                        rename[c] = "centroid_lat"
                    elif lc in ("lon", "lng", "longitude", "centroid_lon", "x"):
                        rename[c] = "centroid_lon"
                raw = raw.rename(columns=rename)
                if st.button("✅ Importar"):
                    st.session_state["zones"] = _coerce(raw)
                    ui_theme.ok(f"{len(raw)} zonas importadas.")
            except Exception as e:
                ui_theme.warn(f"Erro ao ler arquivo: {e}")

    with tab_map:
        m = map_utils.base_map(df)
        m = map_utils.add_zones(m, df)
        map_utils.show(m, height=520)

    with tab_add:
        with st.form("add_zone"):
            c1, c2, c3 = st.columns(3)
            with c1:
                zid = st.text_input("zone_id*", "")
                zname = st.text_input("zone_name", "")
                ztype = st.selectbox("zone_type", ZONE_TYPES)
            with c2:
                pop = st.number_input("population", min_value=0, value=0, step=10)
                prod = st.number_input("production", min_value=0.0, value=0.0, step=10.0)
                attr = st.number_input("attraction", min_value=0.0, value=0.0, step=10.0)
            with c3:
                lat = st.number_input("centroid_lat", value=0.0, format="%.6f")
                lon = st.number_input("centroid_lon", value=0.0, format="%.6f")
                notes = st.text_input("notes", "")
            ok = st.form_submit_button("Adicionar")
            if ok:
                if not zid:
                    ui_theme.warn("zone_id é obrigatório.")
                else:
                    new_row = {
                        "zone_id": zid, "zone_name": zname, "zone_type": ztype,
                        "population": pop, "production": prod, "attraction": attr,
                        "centroid_lat": lat, "centroid_lon": lon, "notes": notes,
                    }
                    df_new = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state["zones"] = _coerce(df_new)
                    ui_theme.ok(f"Zona {zid} adicionada.")

    st.markdown("---")
    n = len(st.session_state["zones"])
    cc = st.columns(3)
    with cc[0]:
        ui_theme.card("Zonas cadastradas", str(n))
    with cc[1]:
        try:
            sp = float(pd.to_numeric(st.session_state["zones"]["production"], errors="coerce").fillna(0).sum())
        except Exception:
            sp = 0.0
        ui_theme.card("Σ Produção", f"{sp:,.0f}")
    with cc[2]:
        try:
            sa = float(pd.to_numeric(st.session_state["zones"]["attraction"], errors="coerce").fillna(0).sum())
        except Exception:
            sa = 0.0
        ui_theme.card("Σ Atração", f"{sa:,.0f}")
