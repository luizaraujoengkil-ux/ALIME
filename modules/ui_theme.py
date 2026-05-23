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
    "bg_main":   "#070A0D",
    "bg_second": "#111820",
    "bg_card":   "#151F2A",
    "yellow":    "#F5B700",
    "orange":    "#FF7A00",
    "green":     "#3ECF5E",
    "red":       "#E53935",
    "blue":      "#28A8FF",
    "text":      "#F4F4F4",
    "text_mute": "#B8C0CC",
    "border":    "#27313D",
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
    st.markdown(
        """
        <div class="alime-hero">
            <div class="logo">ALIME</div>
            <div class="sub">Análise Local Integrada de Mobilidade e Engenharia</div>
            <div class="sub">Simulador de apoio ao planejamento da mobilidade urbana em municípios de pequeno porte.</div>
            <div class="tag">Do diagnóstico territorial à priorização de intervenções.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(num: int | str, title: str) -> None:
    """Título de seção numerada (estilo etapa)."""
    st.markdown(
        f"""
        <h2 style="margin-top:0.5rem">
          <span style="background:{PALETTE['yellow']};color:#1a1a1a;
                       padding:2px 10px;border-radius:8px;margin-right:10px;
                       font-weight:800;">{num}</span> {title}
        </h2>
        """,
        unsafe_allow_html=True,
    )


def disclaimer_box() -> None:
    st.markdown(
        f'<div class="alime-warn"><b>Aviso metodológico.</b> {DISCLAIMER}</div>',
        unsafe_allow_html=True,
    )
