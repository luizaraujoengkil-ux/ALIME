"""Tema visual e helpers de UI para o ALIME.

Cuida de:
- injetar styles.css na página;
- configurar a página;
- expor a paleta de cores como dicionário;
- fornecer helpers (card de indicador, banners, hero).
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st


PALETTE = {
    # Fundos — navy profundo
    "bg_main":   "#0A1628",
    "bg_second": "#11203A",
    "bg_card":   "#16294A",
    # Primária — âmbar dessaturado (não confundir: a chave continua "yellow"
    # por compatibilidade com módulos legados)
    "yellow":    "#D4A93C",
    "orange":    "#E07856",   # terra/coral
    "green":     "#82C39E",   # moss/sage
    "red":       "#C75444",   # crimson dessaturado
    "blue":      "#6BA8C9",   # teal-info
    "sage":      "#7BA890",
    "text":      "#F4F1E8",
    "text_mute": "#A8B5C5",
    "border":    "#1F3552",
}

# Aviso obrigatório que deve aparecer em relatórios e em pontos-chave
DISCLAIMER = (
    "O ALIME é uma ferramenta exploratória de apoio ao planejamento preliminar. "
    "Os resultados não substituem levantamento de campo, contagem volumétrica, "
    "pesquisa O-D domiciliar, microssimulação, EVTEA, orçamento executivo ou "
    "projeto de engenharia."
)


def configure_page() -> None:
    """Configura a página Streamlit (deve ser a primeira chamada)."""
    st.set_page_config(
        page_title="ALIME — Mobilidade e Engenharia",
        page_icon="🟡",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_css() -> None:
    """Carrega o styles.css e injeta no app."""
    css_path = Path(__file__).resolve().parent.parent / "assets" / "styles.css"
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def card(label: str, value: str, delta: str | None = None, color: str = "yellow") -> None:
    """Renderiza um card de indicador.

    Parâmetros:
        label: rótulo do indicador (caixa alta no card).
        value: valor formatado.
        delta: variação opcional (ex.: '-12% vs base').
        color: classe de cor do delta ('up'=verde, 'down'=vermelho).
    """
    delta_html = ""
    if delta:
        klass = "delta-up" if color == "up" else "delta-down" if color == "down" else ""
        delta_html = f'<div class="{klass}">{delta}</div>'
    st.markdown(
        f"""
        <div class="alime-card">
            <h4>{label}</h4>
            <div class="value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def warn(msg: str) -> None:
    st.markdown(f'<div class="alime-warn">⚠ {msg}</div>', unsafe_allow_html=True)


def info(msg: str) -> None:
    st.markdown(f'<div class="alime-info">ℹ {msg}</div>', unsafe_allow_html=True)


def ok(msg: str) -> None:
    st.markdown(f'<div class="alime-ok">✓ {msg}</div>', unsafe_allow_html=True)


def hero() -> None:
    """Renderiza o bloco hero da tela inicial."""
    from . import (
        __version__, __release_date__,
        __author__, __author_email__, __author_affiliation__,
    )
    st.markdown(
        f"""
        <div class="alime-hero">
            <div class="logo">ALIME</div>
            <div class="sub">Análise Local Integrada de Mobilidade e Engenharia</div>
            <div class="sub">Simulador de apoio ao planejamento da mobilidade urbana em municípios de pequeno porte.</div>
            <div class="tag">Do diagnóstico territorial à priorização de intervenções.</div>
            <div style="margin-top:1.4rem;display:flex;justify-content:center;gap:8px;flex-wrap:wrap;">
                <span class="alime-badge yellow">versão {__version__}</span>
                <span class="alime-badge blue">{__release_date__}</span>
            </div>
            <div style="margin-top:1.1rem;color:{PALETTE['text_mute']};font-size:0.85rem;line-height:1.5;">
                Desenvolvido por
                <span style="color:{PALETTE['text']};font-weight:700;">{__author__}</span> ·
                <a href="mailto:{__author_email__}" style="color:{PALETTE['orange']};text-decoration:none;">
                    {__author_email__}
                </a><br/>
                <span style="font-size:0.78rem;">{__author_affiliation__}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(num: int | str, title: str) -> None:
    """Título de seção numerada (estilo etapa)."""
    st.markdown(
        f"""
        <h2 style="margin-top:0.5rem">
          <span style="background:{PALETTE['yellow']};color:{PALETTE['bg_main']};
                       padding:2px 10px;border-radius:8px;margin-right:10px;
                       font-weight:700;">{num}</span> {title}
        </h2>
        """,
        unsafe_allow_html=True,
    )


def disclaimer_box() -> None:
    st.markdown(
        f'<div class="alime-warn"><b>Aviso metodológico.</b> {DISCLAIMER}</div>',
        unsafe_allow_html=True,
    )
