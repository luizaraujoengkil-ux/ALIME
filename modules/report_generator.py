"""Gerador de relatórios (HTML/Markdown).

Três modalidades:
- Relatório do cenário-base
- Relatório individual de um cenário
- Relatório consolidado (base + favoritos)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from . import ui_theme, social_cost as sc_mod
from . import (
    __version__, __release_date__,
    __author__, __author_email__, __author_affiliation__,
)


REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "exports" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


DISCLAIMER_TXT = (
    "O ALIME é uma ferramenta exploratória de apoio ao planejamento preliminar. "
    "Os resultados não substituem levantamento de campo, contagem volumétrica, "
    "pesquisa O-D domiciliar, microssimulação, EVTEA, orçamento executivo ou "
    "projeto de engenharia."
)


def _scenario_md_section(sc: dict, params: dict) -> str:
    ind = sc.get("assignment", {}) or {}
    cost = sc_mod.social_cost(ind, params)
    intvs = sc.get("interventions") or []
    intv_lines = "\n".join(f"- {i}" for i in intvs) if intvs else "_(sem intervenções)_"
    return f"""
## {sc.get('name')}
- **Tipo:** {sc.get('type')}
- **Horizonte:** {sc.get('horizon_year')}
- **Criado em:** {sc.get('created_at')}
- **Descrição:** {sc.get('description') or '—'}

### Indicadores

| Indicador | Valor |
|---|---|
| Σ viagens | {ind.get('total_trips', 0):,.0f} |
| Veh·km | {ind.get('veh_km', 0):,.0f} |
| Tempo médio (min) | {ind.get('avg_time_min', 0):.2f} |
| Distância média (km) | {ind.get('avg_dist_km', 0):.3f} |
| Atraso (min·pessoa) | {ind.get('delay_total_min', 0):,.0f} |
| Horas perdidas/dia | {cost['hours_lost']:,.1f} |
| Custo social diário (R$) | R$ {cost['daily_cost_brl']:,.0f} |
| Custo social anual (R$) | R$ {cost['annual_cost_brl']:,.0f} |
| Custo da obra (R$) | R$ {sc.get('cost_estimate', 0):,.0f} |

### Intervenções
{intv_lines}
"""


def build_markdown(scope: str, study: dict, params: dict,
                    base: dict | None, favs: list[dict] | None,
                    single: dict | None = None) -> str:
    """Monta o markdown do relatório.

    scope: "base", "individual", "consolidado"
    """
    out = []
    out.append("# ALIME — Relatório\n")
    out.append(f"_Gerado em {datetime.now().isoformat(timespec='seconds')} · "
               f"ALIME v{__version__} ({__release_date__})_\n")
    out.append(f"\n**Estudo:** {study.get('name')}  ")
    out.append(f"**Município:** {study.get('municipality')}/{study.get('uf')}  ")
    out.append(f"**População:** {study.get('population')}  ")
    out.append(f"**Ano-base:** {study.get('base_year')} → **Horizonte:** {study.get('horizon')}  ")
    out.append(f"**Problema principal:** {study.get('problem_type')}\n")
    out.append(f"\n> **Aviso metodológico.** {DISCLAIMER_TXT}\n")

    if scope == "base" and base:
        out.append("## Cenário-base — Situação Atual")
        out.append(_scenario_md_section(base, params))
    elif scope == "individual" and single:
        out.append(_scenario_md_section(single, params))
    elif scope == "consolidado":
        out.append("## Cenário-base")
        if base:
            out.append(_scenario_md_section(base, params))
        out.append("## Cenários comparados")
        for sc in (favs or []):
            out.append(_scenario_md_section(sc, params))

        # Tabela comparativa
        if base:
            rows = []
            all_sc = [base] + list(favs or [])
            for sc in all_sc:
                ind = sc.get("assignment", {}) or {}
                cost = sc_mod.social_cost(ind, params)
                rows.append({
                    "cenário": sc.get("name"),
                    "tempo médio (min)": round(ind.get("avg_time_min", 0), 2),
                    "atraso (min·pessoa)": round(ind.get("delay_total_min", 0), 0),
                    "custo anual (R$)": round(cost["annual_cost_brl"], 0),
                    "custo obra (R$)": round(sc.get("cost_estimate", 0), 0),
                })
            df = pd.DataFrame(rows)
            out.append("\n### Tabela consolidada\n")
            # Tabela markdown sem depender de `tabulate` (não instalado no deploy).
            _hdr = list(df.columns)
            _tbl = ["| " + " | ".join(str(c) for c in _hdr) + " |",
                    "| " + " | ".join("---" for _ in _hdr) + " |"]
            for _, _r in df.iterrows():
                _tbl.append("| " + " | ".join(str(_r[c]) for c in _hdr) + " |")
            out.append("\n".join(_tbl))

    out.append("\n---\n")
    out.append("## Limitações\n")
    out.append("- Modelo gravitacional exploratório, sem calibração formal.\n")
    out.append("- Atribuição all-or-nothing (sem congestionamento).\n")
    out.append("- Custos sociais baseados em valor do tempo genérico.\n")
    out.append("- Rede simplificada (k-vizinhos) por padrão.\n")
    out.append("\n---\n")
    out.append(
        f"**Desenvolvido por {__author__}** — "
        f"<{__author_email__}> · {__author_affiliation__}  \n"
        f"ALIME v{__version__} · {__release_date__}\n"
    )
    return "\n".join(out)


_REPORT_CSS = """
@page { size: A4 portrait; margin: 1.8cm; }
body { font-family: Helvetica, Arial, sans-serif; color:#1a2230; font-size:11pt; line-height:1.45; }
h1 { color:#9a6b00; border-bottom:2px solid #F5B700; padding-bottom:4px; font-size:20pt; }
h2 { color:#C0392B; font-size:15pt; margin-top:14pt; }
h3 { color:#1f6f9c; font-size:12.5pt; margin-top:10pt; }
table { border-collapse:collapse; width:100%; margin:8pt 0; }
th, td { border:1px solid #c8d0da; padding:4px 8px; text-align:left; }
th { background:#f2c14e; color:#1a2230; }
blockquote { border-left:3px solid #E53935; padding:6px 12px; background:#fdecea; color:#5a1a16; }
code { color:#b3541e; background:#f3f4f6; padding:1px 4px; }
em { color:#5a6473; }
hr { border:none; border-top:1px solid #d6dbe2; }
"""


def markdown_to_html(md: str, title: str = "Relatório ALIME") -> str:
    """Converte o Markdown do relatório em HTML renderizado (tema documento).

    Usa a biblioteca `markdown` (com tabelas); se ausente, cai para o markdown
    cru escapado dentro de <pre>.
    """
    try:
        import markdown as _md
        body = _md.markdown(
            md, extensions=["tables", "fenced_code", "sane_lists", "nl2br"])
    except Exception:
        import html as ihtml
        body = f"<pre>{ihtml.escape(md)}</pre>"
    return (f"<!doctype html><html lang=\"pt-br\"><head><meta charset=\"utf-8\"/>"
            f"<title>{title}</title><style>{_REPORT_CSS}</style></head>"
            f"<body>{body}</body></html>")


def html_to_pdf(html: str) -> bytes | None:
    """Converte HTML em PDF (xhtml2pdf/pisa, Python puro). None se indisponível."""
    try:
        import io
        from xhtml2pdf import pisa
    except Exception:
        return None
    try:
        buf = io.BytesIO()
        result = pisa.CreatePDF(src=html, dest=buf, encoding="utf-8")
        if result.err:
            return None
        return buf.getvalue()
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _pdf_bytes(html: str) -> bytes | None:
    """PDF cacheado por conteúdo (evita regerar a cada rerun)."""
    return html_to_pdf(html)


def _download_row(md: str, base_name: str, title: str) -> None:
    """Botões de download: Markdown, HTML renderizado e PDF."""
    html = markdown_to_html(md, title=title)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("⬇ Markdown", md.encode("utf-8"),
                           file_name=f"{base_name}.md", mime="text/markdown",
                           key=f"md_{base_name}", use_container_width=True)
    with c2:
        st.download_button("⬇ HTML", html.encode("utf-8"),
                           file_name=f"{base_name}.html", mime="text/html",
                           key=f"html_{base_name}", use_container_width=True)
    with c3:
        pdf = _pdf_bytes(html)
        if pdf:
            st.download_button("⬇ PDF", pdf, file_name=f"{base_name}.pdf",
                               mime="application/pdf", key=f"pdf_{base_name}",
                               use_container_width=True)
        else:
            st.button("⬇ PDF", disabled=True, key=f"pdf_{base_name}",
                      use_container_width=True,
                      help="Gerador de PDF indisponível neste ambiente.")


def render() -> None:
    from . import workflow
    if not workflow.render_guard("relatorios"):
        return
    ui_theme.section_title("📝", "Relatórios")
    ui_theme.disclaimer_box()

    study = st.session_state["study"]
    params = st.session_state["params"]
    base = st.session_state.get("base_scenario")
    favs = st.session_state.get("favorite_scenarios", [])

    tab1, tab2, tab3 = st.tabs(["Cenário-base", "Individual", "Consolidado"])

    with tab1:
        if base is None:
            ui_theme.warning_message("Gere o cenário-base antes.")
        else:
            md = build_markdown("base", study, params, base, favs)
            st.code(md[:1200] + ("…" if len(md) > 1200 else ""), language="markdown")
            # Apenas visualizar o markdown já indica conclusão da etapa
            st.session_state["report_generated"] = True
            _download_row(md, "relatorio_base", "ALIME — Cenário-base")

    with tab2:
        all_scs = ([base] if base else []) + favs
        if not all_scs:
            ui_theme.warn("Sem cenários disponíveis.")
        else:
            names = [f"{s['scenario_id']} - {s['name']}" for s in all_scs]
            sel = st.selectbox("Cenário", names)
            sc = all_scs[names.index(sel)]
            md = build_markdown("individual", study, params, base, favs, single=sc)
            st.code(md[:1200] + ("…" if len(md) > 1200 else ""), language="markdown")
            _download_row(md, f"relatorio_{sc['scenario_id']}", f"ALIME — {sc['name']}")

    with tab3:
        if base is None:
            ui_theme.warn("Gere o cenário-base antes.")
        else:
            md = build_markdown("consolidado", study, params, base, favs)
            st.code(md[:1500] + ("…" if len(md) > 1500 else ""), language="markdown")
            _download_row(md, "relatorio_consolidado", "ALIME — Relatório consolidado")
