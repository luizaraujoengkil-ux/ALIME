"""Tela 1 — Município e Estudo.

Coleta dados básicos do estudo (nome, município, UF, população, ano,
horizonte, tipo de problema e modo de uso).
"""
from __future__ import annotations

import streamlit as st

from . import ui_theme
from . import validation


PROBLEM_TYPES = [
    "ferrovia",
    "rodovia",
    "rio/canal",
    "avenida arterial",
    "alagamento",
    "ponte/viaduto",
    "expansão urbana",
    "ligação intermunicipal",
    "outro",
]


def render() -> None:
    ui_theme.section_title(1, "Município e Estudo")
    st.markdown(
        "<p style='color:#B8C0CC'>Defina os dados básicos do estudo. Esses parâmetros "
        "alimentam todas as etapas seguintes (zonas, geração, distribuição etc.).</p>",
        unsafe_allow_html=True,
    )

    study = st.session_state["study"]

    c1, c2 = st.columns(2)
    with c1:
        study["name"] = st.text_input("Nome do estudo", study.get("name", "Novo estudo"))
        study["municipality"] = st.text_input("Município", study.get("municipality", ""))
        study["uf"] = st.text_input("UF (2 letras)", study.get("uf", "")).upper()[:2]
        study["population"] = st.number_input(
            "População estimada",
            min_value=0, max_value=2_000_000,
            value=int(study.get("population") or 0),
            step=500,
        )
    with c2:
        study["base_year"] = st.number_input(
            "Ano-base", min_value=2000, max_value=2100,
            value=int(study.get("base_year") or 2025), step=1,
        )
        study["horizon"] = st.number_input(
            "Horizonte do estudo", min_value=int(study["base_year"]), max_value=2100,
            value=int(study.get("horizon") or 2035), step=1,
        )
        study["problem_type"] = st.selectbox(
            "Tipo principal de problema",
            PROBLEM_TYPES,
            index=PROBLEM_TYPES.index(study.get("problem_type", "outro"))
            if study.get("problem_type") in PROBLEM_TYPES else len(PROBLEM_TYPES) - 1,
        )
        study["mode"] = st.radio(
            "Modo de uso",
            ["Básico", "Avançado"],
            index=0 if study.get("mode", "Básico") == "Básico" else 1,
            horizontal=True,
            help=("Básico = linguagem simples, passo a passo. "
                  "Avançado = parâmetros técnicos visíveis."),
        )

    # Aviso de população
    warn = validation.warn_population(study["population"])
    if warn:
        ui_theme.warn(warn)
    else:
        if study["population"] > 0:
            ui_theme.ok(f"População dentro do escopo do ALIME ({int(study['population'])} hab).")

    st.session_state["study"] = study

    st.markdown("---")
    cc = st.columns(3)
    with cc[0]:
        if st.button("➡ Ir para Zonas", use_container_width=True):
            st.session_state["page"] = "2. Zonas"
    with cc[1]:
        if st.button("📚 Estudo demonstrativo", use_container_width=True):
            from . import data_update
            data_update.load_demo()
            ui_theme.ok("Estudo demo carregado.")
    with cc[2]:
        if st.button("🏠 Voltar ao início", use_container_width=True):
            st.session_state["page"] = "Início"
