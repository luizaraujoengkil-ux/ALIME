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
    __coauthor__, __coauthor_email__,
)


REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "exports" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


DISCLAIMER_TXT = (
    "O ALIME é uma ferramenta exploratória de apoio ao planejamento preliminar. "
    "Os resultados não substituem levantamento de campo, contagem volumétrica, "
    "pesquisa O-D domiciliar, microssimulação, EVTEA, orçamento executivo ou "
    "projeto de engenharia."
)


def _bar_chart_b64(labels, values, title="", ylabel="", color="#E67E22",
                   money=False) -> str:
    """Gera um gráfico de barras (matplotlib) e devolve uma tag <img> base64.

    Retorna "" se matplotlib não estiver disponível ou se faltar dado — o
    relatório degrada graciosamente (sem gráfico).
    """
    if not labels or not values or len(labels) != len(values):
        return ""
    try:
        import io
        import base64
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.ticker import FuncFormatter

        fig, ax = plt.subplots(figsize=(7.2, 3.3))
        ax.bar(range(len(values)), values, color=color, zorder=3)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels([str(x) for x in labels], rotation=25, ha="right", fontsize=8)
        if title:
            ax.set_title(title, fontsize=11, color="#1a2230")
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=9)
        if money:
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: ui_theme.num_br(v)))
        ax.grid(axis="y", color="#e3e7ec", zorder=0)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=8)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110)
        plt.close(fig)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return (f'<p><img src="data:image/png;base64,{b64}" '
                f'style="max-width:100%;height:auto;"/></p>')
    except Exception:
        return ""


def _comparison_charts_md(base, favs, params) -> str:
    """Gráficos comparativos entre cenários (custo social e atraso)."""
    all_sc = ([base] if base else []) + list(favs or [])
    if not all_sc:
        return ""
    labels = [(s.get("name") or "?")[:24] for s in all_sc]
    costs = [sc_mod.social_cost(s.get("assignment", {}) or {}, params)["annual_cost_brl"]
             for s in all_sc]
    delays = [float((s.get("assignment", {}) or {}).get("delay_total_min", 0) or 0)
              for s in all_sc]
    c1 = _bar_chart_b64(labels, costs, "Custo social anual por cenário (R$)",
                        "R$/ano", color="#C0392B", money=True)
    c2 = _bar_chart_b64(labels, delays, "Atraso por cenário (min·pessoa/dia)",
                        "min·pessoa", color="#E67E22", money=True)
    if not (c1 or c2):
        return ""
    return "\n### Gráficos comparativos\n\n" + c1 + "\n" + c2


def _prioritization_md(study: dict | None) -> str:
    """Seção de priorização de intervenções — o panorama de decisão."""
    if not study or not study.get("rows"):
        return ""
    rows = [r for r in study["rows"] if r.get("n_intervencoes", 0) > 0]
    if not rows:
        return ""
    has_costs = study.get("has_costs", False)
    out = ["\n---\n", "## Priorização de intervenções — panorama de decisão\n",
           "Avaliação de **todas as combinações** de intervenção (2ⁿ): cada "
           "'melhoria' elimina o atraso de um cruzamento (ex.: viaduto). O quadro "
           "abaixo orienta **onde investir** com maior retorno.\n"]

    if has_costs:
        pbs = [r for r in rows if r.get("payback_anos") is not None]
        rec = min(pbs, key=lambda r: r["payback_anos"]) if pbs else None
        if rec:
            out.append(
                f"\n> **Recomendação:** priorizar **{rec['cruzamentos_melhorados']}** — "
                f"benefício {ui_theme.brl(rec['beneficio_anual'])}/ano, "
                f"custo de obra {ui_theme.brl(rec['custo_obra'])}, "
                f"**payback {ui_theme.num_br(rec['payback_anos'], 1)} anos** "
                f"(IBC {ui_theme.num_br(rec['ibc'], 2)}).\n")
        rk = sorted(pbs, key=lambda r: r["payback_anos"]) or rows
    else:
        rec = max(rows, key=lambda r: r["beneficio_anual"])
        out.append(
            f"\n> **Recomendação:** maior benefício em "
            f"**{rec['cruzamentos_melhorados']}** "
            f"({ui_theme.brl(rec['beneficio_anual'])}/ano). Informe o custo de obra "
            f"(etapa 8) para ranquear por payback/IBC.\n")
        rk = sorted(rows, key=lambda r: r["beneficio_anual"], reverse=True)

    top = rk[:8]
    if has_costs:
        out.append("\n| Intervenção(ões) | Benefício/ano | Custo de obra | Payback (anos) | IBC |")
        out.append("|---|---|---|---|---|")
        for r in top:
            out.append(f"| {r['cruzamentos_melhorados']} | "
                       f"{ui_theme.brl(r['beneficio_anual'])} | "
                       f"{ui_theme.brl(r['custo_obra'])} | "
                       f"{ui_theme.num_br(r['payback_anos'], 1)} | "
                       f"{ui_theme.num_br(r['ibc'], 2)} |")
        chart = _bar_chart_b64([r['cruzamentos_melhorados'][:22] for r in top],
                               [r['payback_anos'] for r in top],
                               "Payback por intervenção (anos)", "anos", color="#2E9BFF")
    else:
        out.append("\n| Intervenção(ões) | Benefício/ano | Atraso anual (viagens·min) |")
        out.append("|---|---|---|")
        for r in top:
            out.append(f"| {r['cruzamentos_melhorados']} | "
                       f"{ui_theme.brl(r['beneficio_anual'])} | "
                       f"{ui_theme.num_br(r['atraso_anual'])} |")
        chart = _bar_chart_b64([r['cruzamentos_melhorados'][:22] for r in top],
                               [r['beneficio_anual'] for r in top],
                               "Benefício anual por intervenção (R$)", "R$/ano",
                               color="#1F6F2C", money=True)
    if chart:
        out.append("\n" + chart)
    return "\n".join(out)


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
| Σ viagens | {ui_theme.num_br(ind.get('total_trips', 0))} |
| Veh·km | {ui_theme.num_br(ind.get('veh_km', 0))} |
| Tempo médio (min) | {ui_theme.num_br(ind.get('avg_time_min', 0), 2)} |
| Distância média (km) | {ui_theme.num_br(ind.get('avg_dist_km', 0), 3)} |
| Atraso (min·pessoa) | {ui_theme.num_br(ind.get('delay_total_min', 0))} |
| Horas perdidas/dia | {ui_theme.num_br(cost['hours_lost'], 1)} |
| Custo social diário | {ui_theme.brl(cost['daily_cost_brl'])} |
| Custo social anual | {ui_theme.brl(cost['annual_cost_brl'])} |
| Custo da obra | {ui_theme.brl(sc.get('cost_estimate', 0))} |

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
                    "tempo médio (min)": ui_theme.num_br(ind.get("avg_time_min", 0), 2),
                    "atraso (min·pessoa)": ui_theme.num_br(ind.get("delay_total_min", 0)),
                    "custo anual (R$)": ui_theme.brl(cost["annual_cost_brl"]),
                    "custo obra (R$)": ui_theme.brl(sc.get("cost_estimate", 0)),
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
            out.append(_comparison_charts_md(base, favs, params))

    # Priorização de intervenções (panorama de decisão) — se houver estudo 2^n
    if scope in ("base", "consolidado"):
        out.append(_prioritization_md(st.session_state.get("intervention_study")))

    out.append("\n---\n")
    out.append("## Limitações\n")
    out.append("- Modelo gravitacional exploratório, sem calibração formal.\n")
    out.append("- Atribuição all-or-nothing (sem congestionamento).\n")
    out.append("- Custos sociais baseados em valor do tempo genérico.\n")
    out.append("- Rede simplificada (k-vizinhos) por padrão.\n")
    out.append("\n---\n")
    out.append(
        f"**Desenvolvido por:**  \n"
        f"{__author__} — <{__author_email__}>  \n"
        f"{__coauthor__} — <{__coauthor_email__}>  \n"
        f"{__author_affiliation__}  \n"
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
            # Apenas visualizar o relatório já indica conclusão da etapa
            st.session_state["report_generated"] = True
            with st.container(border=True):
                st.markdown(md, unsafe_allow_html=True)
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
            with st.container(border=True):
                st.markdown(md, unsafe_allow_html=True)
            _download_row(md, f"relatorio_{sc['scenario_id']}", f"ALIME — {sc['name']}")

    with tab3:
        if base is None:
            ui_theme.warn("Gere o cenário-base antes.")
        else:
            md = build_markdown("consolidado", study, params, base, favs)
            with st.container(border=True):
                st.markdown(md, unsafe_allow_html=True)
            _download_row(md, "relatorio_consolidado", "ALIME — Relatório consolidado")
