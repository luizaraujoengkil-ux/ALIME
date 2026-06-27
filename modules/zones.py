"""Tela 2 — Zonas e Microzonas.

Define unidades de análise. Permite criar, editar, importar (CSV/Excel/GeoJSON/KML/KMZ)
e remover zonas. Renderiza centroides no mapa.
"""
from __future__ import annotations

import io
import json

import pandas as pd
import streamlit as st

from . import ui_theme, map_utils, geocoding


@st.cache_data(show_spinner=False, ttl=86400)
def _cached_geocode(query: str, country: str):
    """Geocodificação com cache de 24h (evita repetir chamadas ao Nominatim)."""
    return geocoding.geocode(query, country_codes=country)


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


# Colunas gerenciadas pelo motor de balanceamento (não aparecem na
# tabela editável de zonas; são manipuladas em trip_generation.py).
MANAGED_COLUMNS = [
    "production_original",  # snapshot, NUNCA sobrescrito após balanceamento
    "attraction_original",  # snapshot, NUNCA sobrescrito após balanceamento
    "production_balanced",  # resultado do balanceamento (motor matemático)
    "attraction_balanced",  # resultado do balanceamento (motor matemático)
    "balance_method",       # método aplicado (string)
    "factor_applied",       # fator multiplicativo aplicado (float)
]


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    """Garante todas as colunas esperadas e tipos numéricos básicos.

    Também garante as 6 colunas gerenciadas (originais, balanceados,
    metadados do balanceamento). Faz migração automática de DataFrames
    antigos que só tinham `production`/`attraction`.
    """
    df = df.copy()
    for c in ZONE_COLUMNS:
        if c not in df.columns:
            df[c] = None
    for c in MANAGED_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[ZONE_COLUMNS + MANAGED_COLUMNS]

    num_cols = ["population", "jobs", "schools", "commerce", "industry",
                "production", "attraction",
                "production_original", "attraction_original",
                "production_balanced", "attraction_balanced",
                "factor_applied",
                "generation_weight", "attraction_weight",
                "centroid_lat", "centroid_lon"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Migração automática: se um original/balanced estiver vazio (NaN),
    # tomamos o valor corrente de production/attraction como baseline.
    # Isso cobre o caso de estudos antigos sem essas colunas.
    for shadow, base in [
        ("production_original", "production"),
        ("attraction_original", "attraction"),
        ("production_balanced", "production"),
        ("attraction_balanced", "attraction"),
    ]:
        mask = df[shadow].isna()
        df.loc[mask, shadow] = df.loc[mask, base]
    return df


def reset_all_layers(df: pd.DataFrame) -> pd.DataFrame:
    """Marca os valores ATUAIS de production/attraction como a nova baseline.

    Após esta operação:
        production_original = production
        attraction_original = attraction
        production_balanced = production   (ainda não balanceado)
        attraction_balanced = attraction   (ainda não balanceado)
        balance_method      = NaN
        factor_applied      = NaN

    Use sempre que o usuário salvar manualmente os vetores, importar
    um arquivo novo ou cadastrar uma nova zona — é a "nova baseline"
    sobre a qual o próximo balanceamento opera.
    """
    df = df.copy()
    P = pd.to_numeric(df["production"], errors="coerce")
    A = pd.to_numeric(df["attraction"], errors="coerce")
    df["production_original"] = P
    df["attraction_original"] = A
    df["production_balanced"] = P
    df["attraction_balanced"] = A
    df["balance_method"] = None
    df["factor_applied"] = None
    return df


# Mantido como alias por compatibilidade com versões anteriores
def reset_originals(df: pd.DataFrame) -> pd.DataFrame:
    return reset_all_layers(df)


def get_balanced_vectors(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Conveniência para módulos downstream (etapa 4+).

    Devolve (P, A) usando `production_balanced` e `attraction_balanced`.
    Se essas colunas estiverem ausentes (caso anômalo), faz fallback
    para `production` e `attraction`.
    """
    if "production_balanced" in df.columns and "attraction_balanced" in df.columns:
        P = pd.to_numeric(df["production_balanced"], errors="coerce").fillna(0)
        A = pd.to_numeric(df["attraction_balanced"], errors="coerce").fillna(0)
        return P, A
    return (pd.to_numeric(df["production"], errors="coerce").fillna(0),
            pd.to_numeric(df["attraction"], errors="coerce").fillna(0))


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
    from . import workflow
    if not workflow.render_guard("zonas"):
        return
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
        # Resultado de uma geocodificação anterior (sobrevive ao st.rerun()).
        _geo_report = st.session_state.pop("geo_report", None)
        if _geo_report is not None:
            ui_theme.ok(_geo_report.get("msg", "Geocodificação concluída."))
            if _geo_report.get("rows"):
                st.dataframe(pd.DataFrame(_geo_report["rows"]),
                             use_container_width=True)
        # Esconde as 6 colunas gerenciadas (originais/balanced/method/factor) — elas
        # são manipuladas exclusivamente pelo motor de balanceamento na etapa 3.
        editor_df = df.drop(columns=MANAGED_COLUMNS, errors="ignore")
        edited = st.data_editor(
            editor_df,
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
            # Salvar manualmente = nova baseline. Invalida balanceamento.
            df_new = reset_all_layers(_coerce(edited))
            st.session_state["zones"] = df_new
            st.session_state["balancing"] = None
            ui_theme.clear_status("balancing_applied")
            ui_theme.clear_status("vectors_saved")
            ui_theme.clear_status("od_matrix_generated")
            ui_theme.remember_status(
                "zones_saved", "success",
                f"{len(edited)} zonas salvas com sucesso. Você já pode avançar para Geração."
            )

        # --- Geocodificação por zona (preenche lat/lon pelo nome) ---
        st.markdown("**📍 Geocodificar zonas pelo nome (OpenStreetMap)**")
        study = st.session_state.get("study", {}) or {}
        city = (study.get("area_name") or "").strip()
        uf = (study.get("uf") or "").strip()
        ctx = ", ".join(p for p in [city, uf, "Brasil"] if p)
        st.caption(
            "Preenche `centroid_lat`/`centroid_lon` buscando o nome de cada zona "
            f"no contexto **{ctx}**. Nomeie as zonas com bairros/locais reais "
            "(ex.: 'Centro', 'Bairro Floresta') para melhores resultados. "
            "Defina o município na etapa **1. Área de Estudo**."
        )
        geo_overwrite = st.checkbox(
            "Sobrescrever coordenadas já preenchidas", value=False, key="geo_overwrite"
        )
        if st.button("🔎 Buscar coordenadas das zonas", key="geo_run"):
            cur = _coerce(st.session_state["zones"])
            if cur.empty:
                ui_theme.warn("Cadastre zonas antes de geocodificar.")
            else:
                report, found = [], 0
                prog = st.progress(0.0, text="Buscando coordenadas…")
                total = len(cur)
                for k, (idx, row) in enumerate(cur.iterrows()):
                    name = str(row.get("zone_name") or row.get("zone_id") or "").strip()
                    has = (pd.notna(row.get("centroid_lat"))
                           and pd.notna(row.get("centroid_lon")))
                    if not name:
                        status = "sem nome"
                    elif has and not geo_overwrite:
                        status = "mantida (já tinha)"
                    else:
                        res = _cached_geocode(geocoding.build_query(name, city, uf), "br")
                        if res:
                            cur.at[idx, "centroid_lat"] = round(res[0], 6)
                            cur.at[idx, "centroid_lon"] = round(res[1], 6)
                            found += 1
                            status = "✓ atualizada" if has else "✓ encontrada"
                        elif has:
                            # Busca não achou, mas a zona JÁ tinha coordenada: preserva.
                            status = "○ mantida (busca não achou)"
                        else:
                            status = "✗ sem coordenada"
                    # Sempre reporta a coordenada FINAL (nunca apaga a existente).
                    flat = cur.at[idx, "centroid_lat"]
                    flon = cur.at[idx, "centroid_lon"]
                    report.append({
                        "zona": name or row.get("zone_id"),
                        "status": status,
                        "lat": round(float(flat), 6) if pd.notna(flat) else None,
                        "lon": round(float(flon), 6) if pd.notna(flon) else None,
                    })
                    prog.progress((k + 1) / total, text=f"{k + 1}/{total}")
                prog.empty()
                # Atualiza SÓ as coordenadas — preserva vetores P/A e balanceamento.
                st.session_state["zones"] = cur
                st.session_state["geo_report"] = {
                    "rows": report,
                    "msg": (f"{found} zona(s) atualizada(s) por geocodificação. "
                            "As demais mantiveram as coordenadas que já tinham."
                            if found else
                            "Nenhuma coordenada nova encontrada — todas as zonas "
                            "mantiveram as coordenadas atuais."),
                }
                st.rerun()

    ui_theme.show_status("zones_saved")

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
                    st.session_state["zones"] = reset_all_layers(_coerce(raw))
                    st.session_state["balancing"] = None
                    ui_theme.clear_status("balancing_applied")
                    ui_theme.clear_status("od_matrix_generated")
                    ui_theme.remember_status(
                        "zones_saved", "success",
                        f"{len(raw)} zonas importadas. Valores marcados como originais."
                    )
            except Exception as e:
                ui_theme.warn(f"Erro ao ler arquivo: {e}")

    with tab_map:
        tiles, tile_attr = map_utils.theme_selector("zones_map_theme", default="OpenStreetMap")
        map_utils.warn_if_null_island(df)
        m = map_utils.base_map(df, tiles=tiles, attr=tile_attr)
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
                    glat, glon = lat, lon
                    geocoded = False
                    # Sem coordenadas + tem nome -> tenta geocodificar pelo nome.
                    if lat == 0.0 and lon == 0.0 and zname.strip():
                        _study = st.session_state.get("study", {}) or {}
                        _res = _cached_geocode(
                            geocoding.build_query(
                                zname, _study.get("area_name", ""), _study.get("uf", "")
                            ), "br",
                        )
                        if _res:
                            glat, glon = round(_res[0], 6), round(_res[1], 6)
                            geocoded = True
                    new_row = {
                        "zone_id": zid, "zone_name": zname, "zone_type": ztype,
                        "population": pop, "production": prod, "attraction": attr,
                        "centroid_lat": glat, "centroid_lon": glon, "notes": notes,
                    }
                    df_new = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state["zones"] = reset_all_layers(_coerce(df_new))
                    st.session_state["balancing"] = None
                    ui_theme.clear_status("balancing_applied")
                    msg = f"Zona {zid} adicionada com sucesso."
                    if geocoded:
                        msg += f" Coordenadas encontradas: {glat:.5f}, {glon:.5f}."
                    ui_theme.remember_status("zones_saved", "success", msg)

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
