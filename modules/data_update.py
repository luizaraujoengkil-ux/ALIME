"""Atualização de dados, metadata e carregamento opcional de exemplo genérico.

Por padrão, o ALIME inicia VAZIO. O exemplo genérico (6 zonas com
nomes "Zona A"...) é estritamente OPCIONAL e existe apenas para
validação rápida do motor matemático. Os atributos são fictícios; as
coordenadas ficam ancoradas sobre Brasília apenas para que o mapa
mostre uma cidade real ao fundo. Não é um estudo real de Brasília.
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

# Nome do arquivo do exemplo genérico
EXAMPLE_FILENAME = "zonas_exemplo_generico.csv"


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


def load_example() -> None:
    """Carrega um EXEMPLO GENÉRICO de estudo, apenas para validação.

    Atributos fictícios (nomes "Zona A"..); coordenadas ancoradas sobre
    Brasília só para o mapa exibir uma cidade real. Não é estudo de Brasília.
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
    st.session_state["interferences"] = []

    # Estudo genérico — atributos fictícios, ancorado em Brasília só para o mapa
    st.session_state["study"] = {
        "name": "Exemplo genérico",
        "area_name": "Área de Estudo (exemplo)",
        "entry_type": "ponto",
        "center_lat": -15.793,
        "center_lon": -47.882,
        "collection_radius_km": 5.0,
        "analysis_radius_km": 3.0,
        "municipality": "",      # campo livre, mantido por compat
        "uf": "",
        "country": "",
        "population": 12000,
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
    """Garante que o CSV de exemplo genérico exista.

    Os atributos (população, produção, atração) são fictícios; as coordenadas
    ficam ancoradas sobre Brasília APENAS para que o mapa mostre uma cidade
    real ao fundo. Não é um estudo real de Brasília.
    """
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    example = pd.DataFrame([
        ["ZA", "Zona A", "centro/núcleo urbano",  3000, 900, 1200, -15.783, -47.882],
        ["ZB", "Zona B", "residencial",           2500, 800,  300, -15.773, -47.882],
        ["ZC", "Zona C", "residencial",           2200, 700,  250, -15.793, -47.872],
        ["ZD", "Zona D", "industrial/logístico",   800, 250,  800, -15.793, -47.892],
        ["ZE", "Zona E", "comercial/serviços",    1500, 500,  650, -15.803, -47.882],
        ["ZF", "Zona F", "externo",               2000, 600,  400, -15.813, -47.877],
    ], columns=[
        "zone_id", "zone_name", "zone_type",
        "population", "production", "attraction",
        "centroid_lat", "centroid_lon",
    ])
    for c in ["jobs", "schools", "commerce", "industry",
              "generation_weight", "attraction_weight", "notes"]:
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
        if st.button("🧪 Carregar exemplo genérico (validação)",
                      use_container_width=True,
                      help="Carrega 6 zonas sintéticas para validar o motor. "
                           "Os dados NÃO representam nenhuma cidade real."):
            load_example()
            ui_theme.ok("Exemplo genérico carregado. Use apenas para validação do motor.")
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
