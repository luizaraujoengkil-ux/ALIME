"""Tela 7 — Interferências e barreiras urbanas.

Permite cadastrar pontos/trechos de interferência (ferrovia, alagamento,
ponte estreita, semáforo, gargalo etc.) com seus parâmetros operacionais.

Para ferrovia há campos específicos e fórmulas:

    tempo_ocupacao_min       = (train_length_km / train_speed_kmh) · 60
    tempo_bloqueio_min       = tempo_ocupacao_min · operational_factor
    tempo_total_interferencia_min = tempo_bloqueio_min + queue_dissipation_min
"""
from __future__ import annotations

import uuid

import pandas as pd
import streamlit as st

from . import ui_theme, map_utils


INTERFERENCE_TYPES = [
    "passagem em nível ferroviária",
    "travessia rodoviária crítica",
    "ponte estreita",
    "viaduto crítico",
    "rua alagada",
    "semáforo",
    "gargalo",
    "trecho de baixa capacidade",
    "obra",
    "acidente",
    "bloqueio temporário",
    "outro",
]

PERIODICITIES = ["permanente", "recorrente", "temporária", "por período"]

FIELDS = [
    "interference_id", "name", "type", "geometry_type",
    "affected_modes", "affected_zones", "affected_edges",
    "blocks_per_day", "average_blockage_min", "queue_dissipation_min",
    "capacity_reduction_percent", "risk_level",
    "periodicity", "lat", "lon",
    # Campos ferroviários
    "train_speed_kmh", "train_length_km", "operational_factor", "trains_per_day",
    "computed_block_min", "computed_total_interference_min",
    "affected_share",
    "notes",
]


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def compute_rail(train_length_km: float, train_speed_kmh: float,
                 operational_factor: float, queue_dissipation_min: float) -> dict:
    """Aplica as fórmulas ferroviárias.

    tempo_ocupacao_min = (L / v) · 60
    tempo_bloqueio     = tempo_ocupacao_min · operational_factor
    tempo_total        = tempo_bloqueio + queue_dissipation_min
    """
    if train_speed_kmh <= 0:
        return {"occupancy_min": 0.0, "block_min": 0.0, "total_min": queue_dissipation_min}
    occ = (train_length_km / train_speed_kmh) * 60.0
    block = occ * operational_factor
    total = block + queue_dissipation_min
    return {"occupancy_min": occ, "block_min": block, "total_min": total}


def _parse_coords(text: str) -> list[tuple[float, float]]:
    """Converte a string <coordinates> do KML em lista de (lat, lon)."""
    out = []
    for tok in (text or "").replace("\n", " ").replace("\t", " ").split():
        parts = tok.split(",")
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            out.append((lat, lon))
    return out


def parse_kml_kmz(uploaded) -> list[dict]:
    """Lê um KMZ/KML e devolve uma lista de placemarks {name, lat, lon, geometry_type}.

    Pontos viram 'point'; linhas/áreas viram 'line'/'area' usando o centroide
    (média das coordenadas) como ponto representativo.
    """
    import io
    import zipfile
    import xml.etree.ElementTree as ET

    name = uploaded.name.lower()
    data = uploaded.read()
    if name.endswith(".kmz"):
        zf = zipfile.ZipFile(io.BytesIO(data))
        kmls = [n for n in zf.namelist() if n.lower().endswith(".kml")]
        if not kmls:
            return []
        data = zf.read(kmls[0])
    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="ignore")
    root = ET.fromstring(data)

    placemarks = []
    for pm in root.iter():
        if not pm.tag.endswith("Placemark"):
            continue
        nm, coords, has_line, has_poly = None, None, False, False
        for child in pm.iter():
            tag = child.tag.split("}")[-1]
            if tag == "name" and nm is None:
                nm = (child.text or "").strip()
            elif tag == "LineString":
                has_line = True
            elif tag == "Polygon":
                has_poly = True
            elif tag == "coordinates" and coords is None:
                coords = child.text
        pts = _parse_coords(coords) if coords else []
        if not pts:
            continue
        if len(pts) == 1:
            lat, lon, gtype = pts[0][0], pts[0][1], "point"
        else:
            lat = sum(p[0] for p in pts) / len(pts)
            lon = sum(p[1] for p in pts) / len(pts)
            gtype = "area" if has_poly else ("line" if has_line else "point")
        placemarks.append({"name": nm or "Interferência",
                           "lat": round(lat, 6), "lon": round(lon, 6),
                           "geometry_type": gtype})
    return placemarks


def render() -> None:
    from . import workflow
    if not workflow.render_guard("interferencias"):
        return
    ui_theme.section_title(7, "Interferências e Barreiras")
    st.markdown(
        "<p style='color:#B8C0CC'>Cadastre pontos ou trechos de interferência. "
        "Para ferrovias, informe velocidade, comprimento e fator operacional — "
        "o sistema calcula tempo de bloqueio automaticamente.</p>",
        unsafe_allow_html=True,
    )

    if not st.session_state.get("interferences"):
        st.session_state["interferences"] = []

    tab_list, tab_add, tab_imp = st.tabs(
        ["Lista cadastrada", "Adicionar interferência", "Importar KMZ/KML"]
    )

    with tab_imp:
        st.markdown(
            "Importe pontos de interferência de um **KMZ/KML** (ex.: marcadores do "
            "Google Earth). Defina abaixo os parâmetros aplicados a todos — depois "
            "ajuste cada um na aba **Lista cadastrada**."
        )
        ci1, ci2, ci3 = st.columns(3)
        with ci1:
            imp_type = st.selectbox("Tipo (para todos)", INTERFERENCE_TYPES, key="imp_type")
            imp_risk = st.selectbox("Risco", ["baixo", "médio", "alto", "crítico"],
                                    index=2, key="imp_risk")
        with ci2:
            imp_blocks = st.number_input("Bloqueios/dia", 0, 1000, 8, 1, key="imp_blocks")
            imp_block = st.number_input("Bloqueio médio (min)", 0.0, 120.0, 7.0, 0.5, key="imp_block")
        with ci3:
            imp_queue = st.number_input("Dissipação da fila (min)", 0.0, 60.0, 3.0, 0.5, key="imp_queue")
            imp_share = st.number_input("Fração de viagens afetada", 0.0, 1.0, 0.15, 0.05,
                                        key="imp_share",
                                        help="Usada só se não houver malha OSM construída "
                                             "(senão o atraso vem do fluxo do trecho).")
        up_kml = st.file_uploader("Arquivo KMZ ou KML", type=["kmz", "kml"], key="interf_kml")
        if up_kml is not None:
            try:
                pms = parse_kml_kmz(up_kml)
            except Exception as e:
                ui_theme.warn(f"Não foi possível ler o arquivo: {e}")
                pms = []
            if not pms:
                ui_theme.info("Nenhum ponto/linha encontrado no arquivo.")
            else:
                st.caption(f"{len(pms)} feição(ões) encontrada(s):")
                st.dataframe(pd.DataFrame(pms), use_container_width=True)
                if st.button(f"➕ Importar {len(pms)} interferência(s)", key="imp_btn"):
                    for pm in pms:
                        st.session_state["interferences"].append({
                            "interference_id": _new_id(),
                            "name": pm["name"], "type": imp_type,
                            "geometry_type": pm.get("geometry_type", "point"),
                            "affected_modes": ["veiculo_leve", "veiculo_pesado",
                                               "transporte_coletivo"],
                            "affected_zones": [], "affected_edges": [],
                            "blocks_per_day": int(imp_blocks),
                            "average_blockage_min": float(imp_block),
                            "queue_dissipation_min": float(imp_queue),
                            "capacity_reduction_percent": 0.0,
                            "risk_level": imp_risk, "periodicity": "recorrente",
                            "lat": pm["lat"], "lon": pm["lon"],
                            "train_speed_kmh": 0.0, "train_length_km": 0.0,
                            "operational_factor": 1.0, "trains_per_day": int(imp_blocks),
                            "computed_block_min": float(imp_block),
                            "computed_total_interference_min": float(imp_block) + float(imp_queue),
                            "affected_share": float(imp_share),
                            "notes": f"Importado de {up_kml.name}.",
                        })
                    ui_theme.ok(f"{len(pms)} interferência(s) importada(s). "
                                "Veja na aba Lista cadastrada.")

    with tab_add:
        with st.form("add_interf"):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Nome*", "Travessia ferroviária central")
                itype = st.selectbox("Tipo", INTERFERENCE_TYPES)
                geomtype = st.selectbox("Geometria", ["point", "line", "area"])
                periodicity = st.selectbox("Periodicidade", PERIODICITIES)
                modes = st.multiselect(
                    "Modos afetados",
                    ["veiculo_leve", "veiculo_pesado", "transporte_coletivo",
                     "a_pe", "bicicleta", "outros"],
                    default=["veiculo_leve", "veiculo_pesado"],
                )
                zones = st.text_input("Zonas afetadas (zone_ids separados por vírgula)", "")
                edges = st.text_input("Arestas afetadas (from-to separadas por vírgula)", "")
            with c2:
                lat = st.number_input("Latitude", value=0.0, format="%.6f")
                lon = st.number_input("Longitude", value=0.0, format="%.6f")
                blocks = st.number_input("Bloqueios/dia", min_value=0, value=12, step=1)
                avg_block = st.number_input("Duração média do bloqueio (min)",
                                            min_value=0.0, value=3.0, step=0.5)
                queue = st.number_input("Tempo de dissipação da fila (min)",
                                        min_value=0.0, value=4.0, step=0.5)
                cap_red = st.number_input("Redução de capacidade (%)", 0.0, 100.0, 0.0, 5.0)
                risk = st.selectbox("Nível de risco", ["baixo", "médio", "alto", "crítico"])
                affected_share = st.number_input(
                    "Fração de viagens afetada (0–1)",
                    min_value=0.0, max_value=1.0, value=0.15, step=0.05,
                    help="Aproximação grosseira usada no cálculo agregado de atraso.",
                )

            st.markdown("##### Campos ferroviários (preencher se aplicável)")
            r1, r2, r3, r4 = st.columns(4)
            with r1:
                train_speed = st.number_input("Velocidade do trem (km/h)", 0.0, 200.0, 30.0, 5.0)
            with r2:
                train_length = st.number_input("Comprimento do trem (km)", 0.0, 5.0, 1.2, 0.1)
            with r3:
                op_fac = st.number_input("Fator operacional", 0.0, 5.0, 1.0, 0.1,
                                         help="Ajuste de fila e operação. 1.0 = idealizado.")
            with r4:
                trains_day = st.number_input("Trens/dia", 0, 200, 12, 1)

            notes = st.text_area("Observações", "")
            ok = st.form_submit_button("➕ Adicionar")
            if ok:
                if not name:
                    ui_theme.warn("Nome é obrigatório.")
                else:
                    rail = compute_rail(train_length, train_speed, op_fac, queue)
                    rec = {
                        "interference_id": _new_id(),
                        "name": name,
                        "type": itype,
                        "geometry_type": geomtype,
                        "affected_modes": modes,
                        "affected_zones": [s.strip() for s in zones.split(",") if s.strip()],
                        "affected_edges": [s.strip() for s in edges.split(",") if s.strip()],
                        "blocks_per_day": blocks,
                        "average_blockage_min": avg_block,
                        "queue_dissipation_min": queue,
                        "capacity_reduction_percent": cap_red,
                        "risk_level": risk,
                        "periodicity": periodicity,
                        "lat": lat, "lon": lon,
                        "train_speed_kmh": train_speed,
                        "train_length_km": train_length,
                        "operational_factor": op_fac,
                        "trains_per_day": trains_day,
                        "computed_block_min": rail["block_min"],
                        "computed_total_interference_min": rail["total_min"],
                        "affected_share": affected_share,
                        "notes": notes,
                    }
                    st.session_state["interferences"].append(rec)
                    ui_theme.ok(f"Interferência '{name}' adicionada.")

    with tab_list:
        items = st.session_state["interferences"]
        if not items:
            ui_theme.info("Nenhuma interferência cadastrada ainda.")
            if st.button("✓ Confirmar: não há interferências neste estudo",
                          use_container_width=True):
                from . import workflow
                workflow.mark_skipped(
                    "interferencias",
                    "Etapa marcada como concluída sem interferências cadastradas."
                )
            ui_theme.show_status("skip_interferencias")
        else:
            df = pd.DataFrame([{
                "id": it["interference_id"],
                "nome": it["name"], "tipo": it["type"],
                "bloqueios/dia": it["blocks_per_day"],
                "bloq (min)": round(it["average_blockage_min"], 1),
                "fila (min)": round(it["queue_dissipation_min"], 1),
                "trem-bloq (min)": round(it.get("computed_block_min", 0.0), 1),
                "total interf (min)": round(it.get("computed_total_interference_min", 0.0), 1),
                "modos": ", ".join(it.get("affected_modes", [])),
                "risco": it["risk_level"],
            } for it in items])
            st.dataframe(df, use_container_width=True)

            # Remoção
            ids = [it["interference_id"] for it in items]
            rem = st.selectbox("Remover", ["—"] + ids)
            if rem != "—" and st.button("🗑 Remover selecionada"):
                st.session_state["interferences"] = [
                    i for i in items if i["interference_id"] != rem
                ]
                ui_theme.ok("Interferência removida.")

            # Mapa
            st.markdown("### Mapa das interferências")
            zones_df = st.session_state.get("zones")
            _tiles, _attr = map_utils.theme_selector("interf_map_theme", default="OpenStreetMap")
            map_utils.warn_if_null_island(zones_df)
            m = map_utils.base_map(zones_df, tiles=_tiles, attr=_attr)
            m = map_utils.add_zones(m, zones_df) if zones_df is not None else m
            try:
                import folium
                for it in items:
                    lat, lon = it.get("lat"), it.get("lon")
                    if not lat or not lon:
                        continue
                    color = {"baixo": "#28A8FF", "médio": "#F5B700",
                             "alto": "#FF7A00", "crítico": "#E53935"}.get(it["risk_level"], "#F5B700")
                    folium.CircleMarker(
                        location=[lat, lon], radius=8, color=color,
                        fill=True, fill_color=color, fill_opacity=0.85,
                        popup=f"<b>{it['name']}</b><br>{it['type']}<br>"
                              f"Bloqueio: {it['average_blockage_min']} min × "
                              f"{it['blocks_per_day']}/dia",
                    ).add_to(m)
            except Exception:
                pass
            map_utils.show(m, height=420)
