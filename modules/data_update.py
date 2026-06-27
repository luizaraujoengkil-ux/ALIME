"""Atualização de dados, metadata e carregamento do estudo de demonstração.

Por padrão, o ALIME inicia VAZIO. O estudo de demonstração é OPCIONAL e
serve para validar o fluxo completo com dados reais de referência:
**Matias Barbosa/MG** (5 zonas internas ZT01..ZT05 + 4 zonas externas
ZTE01..ZTE04, vetores de produção/atração derivados de Censo 2022 e do
estudo de caso). As coordenadas internas são aproximadas (ajustáveis).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from . import ui_theme


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "examples"
METADATA_PATH = Path(__file__).resolve().parent.parent / "data" / "metadata.json"

# Nome do arquivo do estudo de demonstração
EXAMPLE_FILENAME = "zonas_matias_barbosa.csv"


def write_metadata(extra: dict | None = None) -> None:
    """Grava o arquivo metadata.json com a configuração atual + carimbos."""
    study = st.session_state.get("study") or {}
    meta = {
        "study_name": study.get("name", "—"),
        "ano": study.get("base_year"),
        "ultima_atualizacao": datetime.now().isoformat(timespec="seconds"),
        "responsavel": st.session_state.get("user", "—"),
        "status": "ok",
        "observacoes": "Gerado pelo ALIME (aba Atualização de Dados).",
    }
    if extra:
        meta.update(extra)
    METADATA_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _demo_interferences() -> list[dict]:
    """Interferências ferroviárias do estudo Matias Barbosa (linha MRS).

    4 cruzamentos rodovia–ferrovia (coordenadas Google Earth). Parâmetros
    operacionais com valores-padrão editáveis na etapa 7.
    """
    import uuid
    from .interferences import compute_rail
    pts = [
        ("Passagem de nível 01",           -21.872428, -43.321183),
        ("Passagem de nível 02",           -21.867511, -43.318361),
        ("Interseção rodovia-ferrovia 01", -21.864783, -43.316367),
        ("Interseção rodovia-ferrovia 02", -21.855644, -43.308803),
    ]
    speed, length, factor, queue, trains = 30.0, 1.2, 1.3, 4.0, 20
    rail = compute_rail(length, speed, factor, queue)
    out = []
    for name, lat, lon in pts:
        out.append({
            "interference_id": uuid.uuid4().hex[:8],
            "name": name,
            "type": "passagem em nível ferroviária",
            "geometry_type": "point",
            "affected_modes": ["veiculo_leve", "veiculo_pesado", "transporte_coletivo"],
            "affected_zones": [],
            "affected_edges": [],
            "blocks_per_day": trains,
            "average_blockage_min": round(rail["block_min"], 2),
            "queue_dissipation_min": queue,
            "capacity_reduction_percent": 0.0,
            "risk_level": "alto",
            "periodicity": "recorrente",
            "lat": lat, "lon": lon,
            "train_speed_kmh": speed,
            "train_length_km": length,
            "operational_factor": factor,
            "trains_per_day": trains,
            "computed_block_min": round(rail["block_min"], 2),
            "computed_total_interference_min": round(rail["total_min"], 2),
            "affected_share": 0.15,
            "notes": "Cruzamento rodovia–ferrovia (linha MRS). Coord. Google Earth.",
        })
    return out


def load_example() -> None:
    """Carrega o estudo de DEMONSTRAÇÃO (Matias Barbosa/MG).

    9 zonas (5 internas + 4 externas) com vetores de produção/atração de
    referência. Coordenadas internas aproximadas — ajustáveis na etapa Zonas.
    """
    from . import zones as zones_mod
    zones_path = EXAMPLES_DIR / EXAMPLE_FILENAME
    if not zones_path.exists():
        _ensure_example_files()
    df = pd.read_csv(zones_path)
    df = zones_mod.reset_all_layers(zones_mod._coerce(df))
    st.session_state["zones"] = df

    # Invalida estados de etapas posteriores
    for k in ("balancing_applied", "vectors_saved", "od_matrix_generated",
              "base_scenario_done", "modal_applied", "assignment_done",
              "scenario_future_done", "scenario_interdiction_done",
              "scenario_improvement_done"):
        from .ui_theme import clear_status
        clear_status(k)
    st.session_state["balancing"] = None
    st.session_state["od_matrix"] = None
    st.session_state["impedance"] = None
    st.session_state["base_scenario"] = None
    st.session_state["scenarios"] = []
    st.session_state["network"] = None
    st.session_state["assignment"] = None
    st.session_state["interferences"] = _demo_interferences()

    # Estudo de demonstração — Matias Barbosa/MG (dados reais de referência)
    st.session_state["study"] = {
        "name": "Demonstração — Matias Barbosa/MG",
        "area_name": "Matias Barbosa",
        "entry_type": "municipio",
        "center_lat": -21.8650,
        "center_lon": -43.3160,
        "collection_radius_km": 5.0,
        "analysis_radius_km": 3.0,
        "municipality": "Matias Barbosa",
        "uf": "MG",
        "country": "BR",
        "population": 14121,     # residentes internos (Censo 2022)
        "base_year": 2026,
        "horizon": 2036,
        "problem_type": "outro",
        "mode": "Básico",
    }
    st.session_state["page"] = "2. Zonas"


# Alias retrocompatível — alguns lugares ainda chamam load_demo()
def load_demo() -> None:
    """Compat: chama load_example()."""
    load_example()


def _ensure_example_files() -> None:
    """Fallback: garante que o CSV de demonstração (Matias Barbosa/MG) exista.

    5 zonas internas (ZT) + 4 externas (ZTE). Atração = empregos + matrículas.
    Coordenadas internas aproximadas; externas nos centros reais das cidades.
    """
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    example = pd.DataFrame([
        # id, nome, tipo, pop, jobs, schools, prod, attr, lat, lon, notes
        ["ZT01", "Centro e Rodoviária", "centro/núcleo urbano", 3850, 1600, 1300, 1615, 2900, -21.873922, -43.321128, "interna; coord Google Earth (Rodoviária)"],
        ["ZT02", "Monte Alegre", "residencial", 3120, 250, 450, 1310, 700, -21.877879, -43.311365, "interna; coord OSM (Park Monte Alegre)"],
        ["ZT03", "N. Sra. da Penha e MG-874", "residencial", 2650, 250, 350, 1107, 600, -21.860000, -43.313000, "interna; aproximada no eixo LMG-874"],
        ["ZT04", "Cedofeita e Expansão", "industrial/logístico", 2100, 850, 200, 881, 1050, -21.840890, -43.313800, "interna; coord OSM (bairro Cedofeitas)"],
        ["ZT05", "Área Rural e Distrito", "rural/periurbano", 2401, 150, 150, 1038, 300, -21.854067, -43.325233, "interna; coord Google Earth (Área Rural/Distrito)"],
        ["ZTE01", "Juiz de Fora/MG", "externo", 0, 2100, 950, 3050, 3050, -21.7610, -43.3501, "externa; absorção via BR-040 Norte e MG-874"],
        ["ZTE02", "Simão Pereira/MG", "externo", 0, 85, 10, 95, 95, -21.9644, -43.3127, "externa; absorção via BR-040 Sul"],
        ["ZTE03", "Três Rios/RJ", "externo", 0, 45, 5, 50, 50, -22.1202, -43.1072, "externa; absorção via BR-040 Sul"],
        ["ZTE04", "Rio de Janeiro/RJ", "externo", 0, 30, 0, 30, 30, -22.9110, -43.2094, "externa; absorção via BR-040 Sul"],
    ], columns=[
        "zone_id", "zone_name", "zone_type",
        "population", "jobs", "schools",
        "production", "attraction",
        "centroid_lat", "centroid_lon", "notes",
    ])
    for c in ["commerce", "industry", "generation_weight", "attraction_weight"]:
        example[c] = ""
    example = example[[
        "zone_id", "zone_name", "zone_type",
        "population", "jobs", "schools", "commerce", "industry",
        "production", "attraction",
        "generation_weight", "attraction_weight",
        "centroid_lat", "centroid_lon",
        "notes",
    ]]
    example.to_csv(EXAMPLES_DIR / EXAMPLE_FILENAME, index=False)


def render() -> None:
    from . import workflow
    if not workflow.render_guard("atualizacao"):
        return
    ui_theme.section_title("🔄", "Atualização de Dados")
    st.markdown(
        "<p style='color:#B8C0CC'>Controle versionamento da base, carregue um "
        "exemplo genérico (apenas para validação) e ajuste parâmetros globais.</p>",
        unsafe_allow_html=True,
    )

    # Checklist consolidado da consistência do estudo
    workflow.render_consistency_check()
    st.markdown("---")

    cc = st.columns(3)
    with cc[0]:
        if st.button("🧪 Carregar estudo de demonstração",
                      use_container_width=True,
                      help="Carrega o estudo Matias Barbosa/MG (9 zonas, dados "
                           "reais de referência) para validar o fluxo completo."):
            load_example()
            ui_theme.ok("Estudo de demonstração (Matias Barbosa/MG) carregado.")
    with cc[1]:
        if st.button("💾 Gravar metadata.json", use_container_width=True):
            write_metadata()
            ui_theme.ok(f"metadata.json gravado em {METADATA_PATH}")
    with cc[2]:
        if st.button("🧹 Resetar sessão", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k not in ("page",):
                    del st.session_state[k]
            ui_theme.ok("Estado resetado.")

    st.markdown("### Parâmetros globais")
    p = st.session_state["params"]
    c1, c2, c3 = st.columns(3)
    with c1:
        p["beta"] = st.number_input("β (atrito)", value=float(p["beta"]), step=0.1)
        p["friction"] = st.selectbox("Função de atrito",
                                     ["potencia", "exponencial"],
                                     index=0 if p["friction"] == "potencia" else 1)
    with c2:
        p["min_distance_km"] = st.number_input("Distância mín. (km)",
                                                value=float(p["min_distance_km"]),
                                                step=0.05)
        p["default_speed_kmh"] = st.number_input("Velocidade média (km/h)",
                                                  value=float(p["default_speed_kmh"]),
                                                  step=1.0)
    with c3:
        p["occupancy"] = st.number_input("Ocupação média",
                                          value=float(p["occupancy"]), step=0.1)
        p["value_of_time_brl_h"] = st.number_input("Valor do tempo (R$/h)",
                                                    value=float(p["value_of_time_brl_h"]),
                                                    step=1.0)
        p["operating_days"] = st.number_input("Dias úteis/ano",
                                                value=int(p["operating_days"]), step=1)
    st.session_state["params"] = p

    if METADATA_PATH.exists():
        st.markdown("### Metadata atual")
        st.code(METADATA_PATH.read_text(encoding="utf-8"), language="json")
