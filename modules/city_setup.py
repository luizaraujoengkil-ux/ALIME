"""Tela 1 — Área de Estudo.

Etapa genérica para definir o recorte territorial de qualquer estudo:
município, bairro, ponto no mapa, arquivo geográfico, área desenhada
ou corredor.

Não pressupõe nenhuma cidade específica. O usuário define o que
quiser — uma cidade pequena, um bairro, um corredor rodoviário,
uma ponte, uma área de alagamento, etc.
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

ENTRY_TYPES = {
    "municipio":      "🏙 Por município / localidade",
    "ponto":          "📍 Por ponto no mapa (lat/lon + raio)",
    "arquivo":        "📁 Por arquivo geográfico (KML/KMZ/GeoJSON/Shapefile)",
    "area_desenhada": "✏ Por área desenhada (polígono)",
    "corredor":       "↔ Por corredor / eixo (linha + faixa)",
}


def _data_quality_level() -> tuple[str, str]:
    """Avalia o nível de qualidade dos dados do estudo atual.
    Retorna (level, descrição).

    Níveis:
        Dados mínimos       — área de estudo + ≥2 zonas + população
        Dados intermediários — adiciona matriz de impedância + interferências
        Dados calibrados     — adiciona pesquisa O-D real (não modelada hoje)
    """
    s = st.session_state
    zones = s.get("zones")
    n_zones = 0 if zones is None or zones.empty else len(zones)
    has_imp = s.get("impedance") is not None
    has_inter = bool(s.get("interferences"))
    has_od_obs = bool(s.get("od_observed"))  # placeholder p/ pesquisa O-D real

    if has_od_obs and has_imp and has_inter and n_zones >= 4:
        return ("Dados calibrados",
                "Com pesquisa O-D observada e contagens — comparações mais confiáveis.")
    if has_imp and n_zones >= 2:
        return ("Dados intermediários",
                "Vetores, impedância e/ou interferências definidos — modelo razoável.")
    if n_zones >= 2:
        return ("Dados mínimos",
                "Diagnóstico exploratório preliminar. Adicione impedância para refinar.")
    return ("Sem dados", "Cadastre zonas para começar.")


def render() -> None:
    from . import workflow
    if not workflow.render_guard("municipio"):
        return
    ui_theme.section_title(1, "Área de Estudo")
    st.markdown(
        "<p style='color:#B8C0CC'>Defina o recorte territorial do estudo. "
        "O ALIME é genérico: pode ser um município, bairro, ponto crítico, "
        "corredor, área de alagamento ou qualquer recorte definido por você.</p>",
        unsafe_allow_html=True,
    )

    study = st.session_state.setdefault("study", {})
    # Defaults p/ campos novos
    study.setdefault("entry_type", "municipio")
    study.setdefault("area_name", "")
    study.setdefault("center_lat", 0.0)
    study.setdefault("center_lon", 0.0)
    study.setdefault("collection_radius_km", 5.0)
    study.setdefault("analysis_radius_km", 3.0)
    study.setdefault("country", "")
    study.setdefault("corridor_buffer_km", 1.0)

    # ============================================================
    # BLOCO 1 — Como você deseja iniciar o estudo?
    # ============================================================
    st.markdown("### Como você deseja iniciar o estudo?")
    entry_key = st.radio(
        "Tipo de entrada",
        list(ENTRY_TYPES.keys()),
        format_func=lambda k: ENTRY_TYPES[k],
        index=list(ENTRY_TYPES.keys()).index(study.get("entry_type", "municipio")),
        horizontal=False,
    )
    study["entry_type"] = entry_key

    # Campos condicionais por tipo
    with st.container(border=True):
        if entry_key == "municipio":
            c1, c2, c3 = st.columns(3)
            with c1:
                study["area_name"] = st.text_input(
                    "Nome da área (cidade/bairro/distrito)",
                    study.get("area_name", ""),
                    placeholder="ex.: Cidade X / Bairro Y / Distrito Z",
                )
            with c2:
                study["uf"] = st.text_input(
                    "UF / Estado (opcional)",
                    study.get("uf", ""),
                    max_chars=2,
                ).upper()[:2]
            with c3:
                study["country"] = st.text_input(
                    "País (opcional)",
                    study.get("country", "") or "",
                    max_chars=3,
                ).upper()[:3]

        elif entry_key == "ponto":
            c1, c2, c3 = st.columns(3)
            with c1:
                study["center_lat"] = st.number_input(
                    "Latitude do ponto central",
                    value=float(study.get("center_lat") or 0.0),
                    format="%.6f", step=0.001,
                )
            with c2:
                study["center_lon"] = st.number_input(
                    "Longitude do ponto central",
                    value=float(study.get("center_lon") or 0.0),
                    format="%.6f", step=0.001,
                )
            with c3:
                study["area_name"] = st.text_input(
                    "Rótulo do ponto (opcional)",
                    study.get("area_name", ""),
                    placeholder="ex.: Cruzamento crítico, Acesso da fábrica…",
                )

        elif entry_key == "arquivo":
            study["area_name"] = st.text_input(
                "Rótulo do estudo",
                study.get("area_name", ""),
                placeholder="ex.: Bairro X (do meu KML)",
            )
            up = st.file_uploader(
                "Arquivo geográfico (KML, KMZ, GeoJSON, Shapefile zipado)",
                type=["kml", "kmz", "geojson", "json", "zip"],
                key="area_file_upload",
            )
            if up is not None:
                ui_theme.info(
                    f"Arquivo recebido: <b>{up.name}</b>. "
                    f"A leitura efetiva acontece na aba <b>2. Zonas</b> "
                    f"(função de import suporta os mesmos formatos)."
                )

        elif entry_key == "area_desenhada":
            study["area_name"] = st.text_input(
                "Rótulo da área desenhada",
                study.get("area_name", ""),
                placeholder="ex.: Polígono do entorno da ponte",
            )
            study["analysis_polygon_wkt"] = st.text_area(
                "Polígono (WKT ou pares lat,lon separados por linha)",
                study.get("analysis_polygon_wkt", ""),
                placeholder="POLYGON((...))\nou\n-15.78,-47.93\n-15.79,-47.92\n...",
                height=120,
            )
            ui_theme.info(
                "Desenho interativo no mapa virá em versão futura. "
                "Por enquanto, cole o polígono em WKT ou liste pares lat,lon."
            )

        elif entry_key == "corredor":
            study["area_name"] = st.text_input(
                "Rótulo do corredor",
                study.get("area_name", ""),
                placeholder="ex.: Corredor BR-XXX km 100–120",
            )
            c1, c2 = st.columns(2)
            with c1:
                study["corridor_start_lat"] = st.number_input(
                    "Lat início",
                    value=float(study.get("corridor_start_lat") or 0.0),
                    format="%.6f", step=0.001,
                )
                study["corridor_start_lon"] = st.number_input(
                    "Lon início",
                    value=float(study.get("corridor_start_lon") or 0.0),
                    format="%.6f", step=0.001,
                )
            with c2:
                study["corridor_end_lat"] = st.number_input(
                    "Lat fim",
                    value=float(study.get("corridor_end_lat") or 0.0),
                    format="%.6f", step=0.001,
                )
                study["corridor_end_lon"] = st.number_input(
                    "Lon fim",
                    value=float(study.get("corridor_end_lon") or 0.0),
                    format="%.6f", step=0.001,
                )
            study["corridor_buffer_km"] = st.number_input(
                "Buffer / faixa de análise (km)",
                min_value=0.05, max_value=50.0,
                value=float(study.get("corridor_buffer_km") or 1.0), step=0.1,
            )

    # ============================================================
    # BLOCO 2 — Área de coleta vs Área de análise
    # ============================================================
    st.markdown("### Área de coleta × Área de análise")
    st.caption("**Coleta:** raio para baixar/organizar dados de entorno. "
                "**Análise:** recorte efetivo usado no modelo. "
                "Geralmente análise ⊆ coleta.")
    c1, c2 = st.columns(2)
    with c1:
        study["collection_radius_km"] = st.number_input(
            "Raio de coleta (km)",
            min_value=0.1, max_value=2000.0,
            value=float(study.get("collection_radius_km") or 5.0),
            step=0.5,
            help="Faixa para dados de entorno (rede, POIs, barreiras).",
        )
    with c2:
        study["analysis_radius_km"] = st.number_input(
            "Raio de análise efetivo (km)",
            min_value=0.1, max_value=2000.0,
            value=float(study.get("analysis_radius_km") or 3.0),
            step=0.5,
            help="Recorte do estudo. Use raios pequenos para bairros (1–5 km) "
                 "e maiores para corredores regionais.",
        )

    if study["collection_radius_km"] > 500:
        ui_theme.warning_message(
            "Raios muito grandes (acima de 500 km) podem tornar a coleta de "
            "rede e a simulação lentas. Para estudos regionais, recomenda-se "
            "rede simplificada ou arquivos filtrados. Modo Avançado sugerido."
        )

    if study["analysis_radius_km"] > study["collection_radius_km"]:
        ui_theme.warning_message(
            "Análise é maior que a coleta — isso pode deixar regiões da análise "
            "sem dados de entorno."
        )

    # ============================================================
    # BLOCO 3 — Metadados do estudo
    # ============================================================
    st.markdown("### Metadados")
    c1, c2 = st.columns(2)
    with c1:
        study["name"] = st.text_input(
            "Nome do estudo",
            study.get("name", "Novo estudo"),
        )
        study["population"] = st.number_input(
            "População estimada da área (opcional)",
            min_value=0, max_value=10_000_000,
            value=int(study.get("population") or 0),
            step=500,
        )
        study["problem_type"] = st.selectbox(
            "Tipo principal de problema (opcional)",
            PROBLEM_TYPES,
            index=PROBLEM_TYPES.index(study.get("problem_type", "outro"))
            if study.get("problem_type") in PROBLEM_TYPES else len(PROBLEM_TYPES) - 1,
        )
    with c2:
        study["base_year"] = st.number_input(
            "Ano-base",
            min_value=2000, max_value=2100,
            value=int(study.get("base_year") or 2026), step=1,
        )
        study["horizon"] = st.number_input(
            "Horizonte do estudo",
            min_value=int(study["base_year"]), max_value=2100,
            value=int(study.get("horizon") or (int(study["base_year"]) + 10)),
            step=1,
        )
        study["mode"] = st.radio(
            "Modo de uso",
            ["Básico", "Avançado"],
            index=0 if study.get("mode", "Básico") == "Básico" else 1,
            horizontal=True,
            help="Básico bloqueia avanço com etapas incompletas. "
                 "Avançado permite seguir com aviso.",
        )

    # Aviso de população (não bloqueia)
    pop = study.get("population") or 0
    warn = validation.warn_population(pop)
    if warn:
        ui_theme.warning_message(
            "O ALIME foi concebido para estudos preliminares em áreas de "
            "pequeno porte. Áreas maiores podem exigir maior calibração, "
            "simplificação de rede e maior capacidade computacional."
        )
    elif pop > 0:
        ui_theme.success_message(
            f"População dentro do escopo prioritário do ALIME ({int(pop):,} hab)."
        )

    st.session_state["study"] = study

    # ============================================================
    # BLOCO 4 — Indicador de qualidade dos dados
    # ============================================================
    st.markdown("### Qualidade dos dados do estudo")
    level, desc = _data_quality_level()
    color = {
        "Sem dados":            ui_theme.PALETTE["text_mute"],
        "Dados mínimos":        ui_theme.PALETTE["orange"],
        "Dados intermediários": ui_theme.PALETTE["yellow"],
        "Dados calibrados":     ui_theme.PALETTE["green"],
    }.get(level, ui_theme.PALETTE["text_mute"])
    st.markdown(
        f"""
        <div class='alime-card' style='border-left:6px solid {color}'>
            <h4>{level}</h4>
            <div class='value' style='font-size:1.0rem'>{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ============================================================
    # Salvar / Próximas etapas
    # ============================================================
    st.markdown("---")
    cc = st.columns(2)
    with cc[0]:
        if st.button("💾 Salvar área de estudo", use_container_width=True):
            ui_theme.remember_status(
                "area_saved", "success",
                "Área de estudo salva. Próximo passo: cadastrar/importar zonas."
            )
    with cc[1]:
        if st.button("➡ Ir para Zonas", use_container_width=True):
            st.session_state["page"] = "2. Zonas"
            st.rerun()

    ui_theme.show_status("area_saved")
