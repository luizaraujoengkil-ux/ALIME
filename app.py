"""ALIME — Análise Local Integrada de Mobilidade e Engenharia.

App Streamlit principal. Concentra a navegação por etapas e o estado
global do estudo via `st.session_state`.

Execução:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from modules import ui_theme
from modules import (
    __version__,
    __release_date__,
    __author__,
    __author_email__,
    __author_affiliation__,
)
from modules import (
    city_setup,
    zones,
    trip_generation,
    trip_distribution,
    modal_split,
    network_assignment,
    interferences,
    scenarios,
    scenario_library,
    comparison,
    social_cost,
    report_generator,
    data_update,
)


# ============================================================
# Inicialização da página
# ============================================================
ui_theme.configure_page()
ui_theme.inject_css()


# ============================================================
# Estado global do estudo
# ============================================================
def init_state() -> None:
    """Garante que as chaves principais existam no session_state."""
    defaults: dict = {
        "study": {
            "name": "Novo estudo",
            "municipality": "",
            "uf": "",
            "population": 0,
            "base_year": 2025,
            "horizon": 2035,
            "problem_type": "outro",
            "mode": "Básico",
        },
        "zones": None,          # DataFrame de zonas
        "od_matrix": None,      # numpy array (n,n)
        "od_zone_ids": None,    # list dos zone_ids alinhados à matriz
        "impedance": None,      # numpy array (n,n)
        "modal_split": {        # repartição global default
            "veiculo_leve":     0.55,
            "veiculo_pesado":   0.05,
            "transporte_coletivo": 0.10,
            "a_pe":             0.20,
            "bicicleta":        0.05,
            "outros":           0.05,
        },
        "modal_matrices": {},   # {modo: matriz}
        "network": None,        # dict com nodes, edges, graph
        "assignment": None,     # dict com link flows e métricas
        "interferences": [],    # lista de dicts
        "base_scenario": None,  # snapshot do cenário-base
        "scenarios": [],        # lista de cenários (até 5)
        "page": "Início",
        "params": {
            "beta": 2.0,
            "friction": "potencia",
            "min_distance_km": 0.3,
            "default_speed_kmh": 35.0,
            "occupancy": 1.4,
            "value_of_time_brl_h": 18.0,
            "operating_days": 252,
        },
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ============================================================
# Sidebar - navegação por etapas
# ============================================================
PAGES = [
    ("Início",              "🏠"),
    ("1. Município",        "🏙"),
    ("2. Zonas",            "🗺"),
    ("3. Geração",          "📈"),
    ("4. Distribuição",     "🔀"),
    ("5. Repartição Modal", "🚲"),
    ("6. Atribuição",       "🛣"),
    ("7. Interferências",   "⚠"),
    ("8. Cenários",         "🧪"),
    ("Biblioteca",          "📚"),
    ("Comparação",          "📊"),
    ("Custo Social",        "💸"),
    ("Relatórios",          "📝"),
    ("Atualização",         "🔄"),
]


def render_sidebar() -> None:
    p = ui_theme.PALETTE
    with st.sidebar:
        # ----- Cabeçalho: nome + autoria + versão + data -----
        st.markdown(
            f"""
            <div style="padding:0.4rem 0 0.9rem 0;
                        border-bottom:1px solid {p['border']};
                        margin-bottom:0.9rem;">
                <div style="font-size:1.9rem;font-weight:800;color:{p['yellow']};
                            letter-spacing:6px;line-height:1;">ALIME</div>
                <div style="font-size:0.72rem;color:{p['text_mute']};
                            margin-top:6px;line-height:1.3;">
                    Análise Local Integrada<br/>de Mobilidade e Engenharia
                </div>
                <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap;">
                    <span class="alime-badge yellow">v{__version__}</span>
                    <span class="alime-badge blue">{__release_date__}</span>
                </div>
                <div style="margin-top:10px;font-size:0.72rem;color:{p['text_mute']};
                            line-height:1.4;">
                    Desenvolvido por<br/>
                    <span style="color:{p['text']};font-weight:600;">{__author__}</span><br/>
                    <a href="mailto:{__author_email__}"
                       style="color:{p['orange']};text-decoration:none;">
                       {__author_email__}</a><br/>
                    <span style="font-size:0.68rem;">{__author_affiliation__}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**Etapas do estudo**")
        for name, icon in PAGES:
            label = f"{icon}  {name}"
            if st.button(label, key=f"nav_{name}", use_container_width=True):
                st.session_state["page"] = name

        st.markdown("---")
        st.caption(
            f"Estudo: **{st.session_state['study'].get('name','—')}**\n\n"
            f"Modo: **{st.session_state['study'].get('mode','Básico')}**"
        )


# ============================================================
# Topbar
# ============================================================
def render_topbar() -> None:
    col1, col2, col3, col4 = st.columns([5, 1, 1, 1])
    with col1:
        st.markdown(
            f"<h3 style='margin:0'>📍 {st.session_state['study'].get('name', 'Novo estudo')}"
            f" — {st.session_state['study'].get('municipality') or 'município ?'} / "
            f"{st.session_state['study'].get('uf') or '??'}</h3>",
            unsafe_allow_html=True,
        )
    with col2:
        if st.button("💾 Salvar", key="top_save"):
            ui_theme.ok("Estado do estudo salvo na sessão. Para persistir em arquivo, use a aba Biblioteca de Cenários.")
    with col3:
        if st.button("⚙ Config", key="top_cfg"):
            st.session_state["page"] = "Atualização"
    with col4:
        if st.button("❓ Ajuda", key="top_help"):
            st.session_state["page"] = "Início"


# ============================================================
# Página inicial (hero)
# ============================================================
def render_home() -> None:
    ui_theme.hero()

    # ---- Bloco "Por onde começar?" ----
    p = ui_theme.PALETTE
    st.markdown(
        f"""
        <div class='alime-card' style='border-left:6px solid {p["yellow"]};
                                       margin-top:0.5rem'>
            <h4 style='margin-bottom:0.4rem'>Por onde começar?</h4>
            <div style='color:{p["text"]};font-size:0.95rem;line-height:1.55'>
                Escolha <b>uma</b> das três opções abaixo.
                Se é seu primeiro contato com o ALIME, recomendamos
                <b style='color:{p["yellow"]}'>Abrir estudo demonstrativo</b> —
                ele já vem com 8 zonas e leva você direto para a etapa
                <b>2. Zonas</b>. A partir daí, basta seguir o fluxo
                <span style='color:{p["text_mute"]}'>
                    2 → 3 → 4 → 5 → 6 → 7 → 8
                </span>
                pelo menu lateral.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- 3 CTAs ----
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(
            "<div style='text-align:center;color:#A8B5C5;font-size:0.78rem;"
            "margin-bottom:0.3rem'>do zero, com seus dados</div>",
            unsafe_allow_html=True,
        )
        if st.button("➕ Criar novo estudo", use_container_width=True, key="cta_new"):
            st.session_state["page"] = "1. Município"
            st.rerun()
        st.markdown(
            "<div style='text-align:center;color:#A8B5C5;font-size:0.75rem;"
            "margin-top:0.3rem;line-height:1.4'>"
            "Vai para <b>1. Município</b> em branco. Você preenche tudo manualmente."
            "</div>",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"<div style='text-align:center;color:{p['yellow']};font-size:0.78rem;"
            "margin-bottom:0.3rem;font-weight:700'>★ recomendado para começar</div>",
            unsafe_allow_html=True,
        )
        if st.button("📂 Abrir estudo demonstrativo",
                     use_container_width=True, key="cta_demo"):
            from modules import data_update
            data_update.load_demo()
            st.rerun()
        st.markdown(
            "<div style='text-align:center;color:#A8B5C5;font-size:0.75rem;"
            "margin-top:0.3rem;line-height:1.4'>"
            "Carrega <b>8 zonas-exemplo</b> e leva você direto para <b>2. Zonas</b>. "
            "Daí execute 3 → 4 → 5 → 6."
            "</div>",
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            "<div style='text-align:center;color:#A8B5C5;font-size:0.78rem;"
            "margin-bottom:0.3rem'>continuar trabalho salvo</div>",
            unsafe_allow_html=True,
        )
        if st.button("⬆ Importar estudo existente",
                     use_container_width=True, key="cta_import"):
            st.session_state["page"] = "Biblioteca"
            st.rerun()
        st.markdown(
            "<div style='text-align:center;color:#A8B5C5;font-size:0.75rem;"
            "margin-top:0.3rem;line-height:1.4'>"
            "Vai para <b>Biblioteca</b>, onde você faz upload de um <b>.json</b> "
            "salvo anteriormente."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### Modelo das 4 Etapas")
    cc = st.columns(4)
    steps = [
        ("Geração",       "Vou ou não vou?",   ui_theme.PALETTE["yellow"]),
        ("Distribuição",  "Para onde vou?",    ui_theme.PALETTE["orange"]),
        ("Repartição",    "Como vou?",         ui_theme.PALETTE["green"]),
        ("Atribuição",    "Por onde vou?",     ui_theme.PALETTE["blue"]),
    ]
    for col, (title, q, color) in zip(cc, steps):
        with col:
            st.markdown(
                f"""
                <div class='alime-card' style='border-left:6px solid {color}'>
                    <h4>{title}</h4>
                    <div class='value' style='font-size:1.1rem'>{q}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("---")
    ui_theme.disclaimer_box()


# ============================================================
# Roteamento
# ============================================================
def main() -> None:
    render_sidebar()

    page = st.session_state["page"]

    # Topbar (nome do estudo + Salvar/Config/Ajuda) só aparece DEPOIS que o
    # usuário entra em uma etapa de trabalho. Na tela de boas-vindas, o hero
    # já cumpre o papel de identidade visual.
    if page != "Início":
        render_topbar()
        st.markdown("---")

    if page == "Início":
        render_home()
    elif page == "1. Município":
        city_setup.render()
    elif page == "2. Zonas":
        zones.render()
    elif page == "3. Geração":
        trip_generation.render()
    elif page == "4. Distribuição":
        trip_distribution.render()
    elif page == "5. Repartição Modal":
        modal_split.render()
    elif page == "6. Atribuição":
        network_assignment.render()
    elif page == "7. Interferências":
        interferences.render()
    elif page == "8. Cenários":
        scenarios.render()
    elif page == "Biblioteca":
        scenario_library.render()
    elif page == "Comparação":
        comparison.render()
    elif page == "Custo Social":
        social_cost.render()
    elif page == "Relatórios":
        report_generator.render()
    elif page == "Atualização":
        data_update.render()
    else:
        render_home()


if __name__ == "__main__":
    main()
