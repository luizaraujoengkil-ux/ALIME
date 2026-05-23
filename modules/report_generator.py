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
            out.append(df.to_markdown(index=False))

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


def markdown_to_html(md: str, title: str = "Relatório ALIME") -> str:
    """Conversão simplificada Markdown→HTML mantendo o tema do ALIME."""
    import html as ihtml
    safe = ihtml.escape(md)
    return f"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <style>
    body {{ background:#070A0D; color:#F4F4F4; font-family:Segoe UI,Roboto,Arial; padding:32px; }}
    h1,h2,h3 {{ color:#F5B700; }}
    table {{ border-collapse:collapse; background:#151F2A; }}
    th, td {{ border:1px solid #27313D; padding:6px 10px; }}
    pre {{ background:#111820; padding:10px; border-left:4px solid #F5B700; white-space:pre-wrap; }}
    blockquote {{ border-left:4px solid #E53935; padding:8px 14px;
                  background:rgba(229,57,53,0.08); color:#F4F4F4; }}
    code {{ color:#FF7A00; }}
  </style>
</head>
<body>
<pre>{safe}</pre>
</body></html>
"""


def render() -> None:
    ui_theme.section_title("📝", "Relatórios")
    ui_theme.disclaimer_box()

    study = st.session_state["study"]
    params = st.session_state["params"]
    base = st.session_state.get("base_scenario")
    favs = st.session_state.get("favorite_scenarios", [])

    tab1, tab2, tab3 = st.tabs(["Cenário-base", "Individual", "Consolidado"])

    with tab1:
        if base is None:
            ui_theme.warn("Gere o cenário-base antes.")
        else:
            md = build_markdown("base", study, params, base, favs)
            st.code(md[:1200] + ("…" if len(md) > 1200 else ""), language="markdown")
            colA, colB = st.columns(2)
            with colA:
                st.download_button("⬇ Baixar Markdown", md.encode("utf-8"),
                                   file_name="relatorio_base.md",
                                   mime="text/markdown")
            with colB:
                html = markdown_to_html(md, title="ALIME — Cenário-base")
                st.download_button("⬇ Baixar HTML", html.encode("utf-8"),
                                   file_name="relatorio_base.html",
                                   mime="text/html")

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
            st.download_button("⬇ Baixar Markdown", md.encode("utf-8"),
                               file_name=f"relatorio_{sc['scenario_id']}.md",
                               mime="text/markdown")
            html = markdown_to_html(md, title=f"ALIME — {sc['name']}")
            st.download_button("⬇ Baixar HTML", html.encode("utf-8"),
                               file_name=f"relatorio_{sc['scenario_id']}.html",
                               mime="text/html")

    with tab3:
        if base is None:
            ui_theme.warn("Gere o cenário-base antes.")
        else:
            md = build_markdown("consolidado", study, params, base, favs)
            st.code(md[:1500] + ("…" if len(md) > 1500 else ""), language="markdown")
            colA, colB = st.columns(2)
            with colA:
                st.download_button("⬇ Baixar Markdown", md.encode("utf-8"),
                                   file_name="relatorio_consolidado.md",
                                   mime="text/markdown")
            with colB:
                html = markdown_to_html(md, title="ALIME — Relatório consolidado")
                st.download_button("⬇ Baixar HTML", html.encode("utf-8"),
                                   file_name="relatorio_consolidado.html",
                                   mime="text/html")
