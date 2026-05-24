"""Atualização de dados e metadata. Também carrega o estudo demonstrativo."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from . import ui_theme


DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo"
METADATA_PATH = Path(__file__).resolve().parent.parent / "data" / "metadata.json"


def write_metadata(extra: dict | None = None) -> None:
    """Grava o arquivo metadata.json com a configuração atual + carimbos."""
    meta = {
        "base": "ALIME-demo-v1",
        "fonte": "Dados de demonstração genéricos",
        "ano": st.session_state["study"].get("base_year"),
        "ultima_atualizacao": datetime.now().isoformat(timespec="seconds"),
        "responsavel": st.session_state.get("user", "—"),
        "status": "ok",
        "observacoes": "Gerado pelo ALIME (aba Atualização de Dados).",
    }
    if extra:
        meta.update(extra)
    METADATA_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_demo() -> None:
    """Carrega o estudo demonstrativo genérico.

    Aplica _coerce + reset_all_layers para garantir que o demo
    venha já com as 4 colunas (production_original, attraction_original,
    production_balanced, attraction_balanced) inicializadas.
    """
    from . import zones as zones_mod
    zones_path = DEMO_DIR / "zones_demo.csv"
    if not zones_path.exists():
        _generate_demo_files()
    df = pd.read_csv(zones_path)
    df = zones_mod.reset_all_layers(zones_mod._coerce(df))
    st.session_state["zones"] = df
    # Invalida estados de etapas posteriores ao recarregar o demo
    for k in ("balancing_applied", "vectors_saved", "od_matrix_generated",
              "base_scenario_done", "modal_applied", "assignment_done",
              "scenario_future_done", "scenario_interdiction_done",
              "scenario_improvement_done"):
        from .ui_theme import clear_status
        clear_status(k)
    st.session_state["balancing"] = None
    st.session_state["od_matrix"] = None
    st.session_state["base_scenario"] = None
    st.session_state["scenarios"] = []
    st.session_state["network"] = None
    st.session_state["assignment"] = None
    st.session_state["study"] = {
        "name": "Estudo demonstrativo",
        "municipality": "Cidade Demonstrativa",
        "uf": "MG",
        "population": 18500,
        "base_year": 2025,
        "horizon": 2035,
        "problem_type": "ferrovia",
        "mode": "Básico",
    }
    st.session_state["interferences"] = [{
        "interference_id": "demo01",
        "name": "Passagem em nível central",
        "type": "passagem em nível ferroviária",
        "geometry_type": "point",
        "affected_modes": ["veiculo_leve", "veiculo_pesado"],
        "affected_zones": ["Z01", "Z02"],
        "affected_edges": [],
        "blocks_per_day": 14, "average_blockage_min": 3.5,
        "queue_dissipation_min": 4.0,
        "capacity_reduction_percent": 0.0,
        "risk_level": "alto",
        "periodicity": "recorrente",
        "lat": -21.870, "lon": -43.330,
        "train_speed_kmh": 30.0, "train_length_km": 1.2,
        "operational_factor": 1.0, "trains_per_day": 14,
        "computed_block_min": 2.4, "computed_total_interference_min": 6.4,
        "affected_share": 0.20,
        "notes": "Interferência ferroviária demonstrativa.",
    }]
    st.session_state["page"] = "2. Zonas"


def _generate_demo_files() -> None:
    """Gera CSV demo mínimo (8 zonas) caso ainda não exista."""
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    # Coordenadas plausíveis (perto de Matias Barbosa/MG só como ilustração)
    demo = pd.DataFrame([
        ["Z01", "Centro",       "centro/núcleo urbano",  4500, 1100,  900, -21.860, -43.330],
        ["Z02", "Bairro Norte", "residencial",            3200,  900,  300, -21.850, -43.335],
        ["Z03", "Bairro Sul",   "residencial",            2800,  800,  280, -21.875, -43.328],
        ["Z04", "Industrial",   "industrial/logístico",    600,  150,  900, -21.868, -43.310],
        ["Z05", "Comercial",    "comercial/serviços",     1100,  300,  650, -21.862, -43.320],
        ["Z06", "Periferia L",  "residencial",            1900,  600,  180, -21.880, -43.345],
        ["Z07", "Rural",        "rural/periurbano",       1500,  400,  120, -21.840, -43.305],
        ["Z08", "Externo",      "externo",                 900,  300,  450, -21.890, -43.360],
    ], columns=[
        "zone_id", "zone_name", "zone_type",
        "population", "production", "attraction",
        "centroid_lat", "centroid_lon",
    ])
    for c in ["jobs", "schools", "commerce", "industry",
              "generation_weight", "attraction_weight", "notes"]:
        demo[c] = ""
    demo = demo[[
        "zone_id", "zone_name", "zone_type",
        "population", "jobs", "schools", "commerce", "industry",
        "production", "attraction",
        "generation_weight", "attraction_weight",
        "centroid_lat", "centroid_lon",
        "notes",
    ]]
    demo.to_csv(DEMO_DIR / "zones_demo.csv", index=False)


def render() -> None:
    ui_theme.section_title("🔄", "Atualização de Dados")
    st.markdown(
        "<p style='color:#B8C0CC'>Controle versionamento da base, carregue o estudo "
        "demonstrativo e ajuste parâmetros globais (valor do tempo, ocupação etc.).</p>",
        unsafe_allow_html=True,
    )

    cc = st.columns(3)
    with cc[0]:
        if st.button("📂 Carregar estudo demonstrativo", use_container_width=True):
            load_demo()
            ui_theme.ok("Estudo demonstrativo carregado.")
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
