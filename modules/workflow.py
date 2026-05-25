"""Workflow / trilha de progresso do ALIME.

Camada de orquestração que mostra ao usuário em qual etapa ele está,
quais já foram concluídas e qual a próxima etapa recomendada.

Não interfere na matemática nem no estado dos dados — apenas LÊ
flags existentes (`zones_saved`, `balancing_applied`, etc.) e
deriva status visual em `st.session_state["workflow_status"]`.

API pública:
    init_workflow_status()       — inicializa o dicionário no session_state
    set_step_status(key, status) — marca uma etapa manualmente
    get_step_status(key)         — lê o status atual
    evaluate_workflow()          — re-deriva status a partir das flags
    get_next_step()              — devolve a próxima etapa pendente
    can_access_step(key, mode)   — checa se a etapa pode ser acessada
    render_progress_trail(key)   — renderiza os chips no topo
    render_next_step_hint(key)   — renderiza o card de "próximo passo"
    render_guard(key)            — combina trilha + hint + bloqueio
    render_consistency_check()   — checklist "Verificação do estudo"
    mark_skipped(key, message)   — marca explicitamente uma etapa como concluída
                                    sem que a ação principal tenha sido feita
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd
import streamlit as st

from . import ui_theme


# ============================================================
# Catálogo das 13 etapas
# ============================================================
WORKFLOW_STEPS = [
    {"key": "municipio",         "label": "1·Área de Estudo",  "page": "1. Município"},
    {"key": "zonas",             "label": "2·Zonas",           "page": "2. Zonas"},
    {"key": "geracao",           "label": "3·Geração",         "page": "3. Geração"},
    {"key": "distribuicao",      "label": "4·Distribuição",    "page": "4. Distribuição"},
    {"key": "reparticao_modal",  "label": "5·Repartição",      "page": "5. Repartição Modal"},
    {"key": "atribuicao",        "label": "6·Atribuição",      "page": "6. Atribuição"},
    {"key": "interferencias",    "label": "7·Interferências",  "page": "7. Interferências"},
    {"key": "cenarios",          "label": "8·Cenários",        "page": "8. Cenários"},
    {"key": "biblioteca",        "label": "9·Biblioteca",      "page": "Biblioteca"},
    {"key": "comparacao",        "label": "10·Comparação",     "page": "Comparação"},
    {"key": "custo_social",      "label": "11·Custo Social",   "page": "Custo Social"},
    {"key": "relatorios",        "label": "12·Relatórios",     "page": "Relatórios"},
    {"key": "atualizacao",       "label": "13·Atualização",    "page": "Atualização",
     "optional": True},
]

STEP_KEYS = [s["key"] for s in WORKFLOW_STEPS]
STEP_BY_KEY = {s["key"]: s for s in WORKFLOW_STEPS}

VALID_STATUS = ("not_started", "in_progress", "completed", "error", "blocked")

STATUS_ICON = {
    "completed":   "✓",
    "in_progress": "●",
    "not_started": "○",
    "error":       "✗",
    "blocked":     "⛔",
}

# Dicas de próximo passo por etapa pendente
HINTS = {
    "municipio":        "Defina a área de estudo (município, ponto, arquivo, polígono ou corredor) e ano-base.",
    "zonas":            "Cadastre ou importe as zonas de análise (mínimo 2 zonas).",
    "geracao":          "Informe os vetores de produção e atração e aplique o balanceamento.",
    "distribuicao":     "Configure a matriz de impedância e gere a matriz O-D.",
    "reparticao_modal": "Defina os percentuais por modo (soma 100%) e aplique.",
    "atribuicao":       "Construa a rede e aloque os fluxos.",
    "interferencias":   "Cadastre interferências urbanas ou confirme que não há.",
    "cenarios":         "Gere o cenário-base; em seguida crie alternativas.",
    "biblioteca":       "Salve até 5 cenários favoritos para comparação.",
    "comparacao":       "Visualize a comparação entre cenário-base e favoritos.",
    "custo_social":     "Ajuste valor do tempo, ocupação e dias úteis.",
    "relatorios":       "Gere o relatório consolidado (HTML/Markdown).",
    "atualizacao":      "Verifique a metadata do estudo.",
}


# ============================================================
# Estado central
# ============================================================
def init_workflow_status() -> None:
    """Garante que o dicionário de status exista em session_state."""
    if "workflow_status" not in st.session_state:
        st.session_state["workflow_status"] = {k: "not_started" for k in STEP_KEYS}
    if "skipped_steps" not in st.session_state:
        st.session_state["skipped_steps"] = set()


def set_step_status(key: str, status: str) -> None:
    """Marca explicitamente uma etapa com um status."""
    init_workflow_status()
    if status not in VALID_STATUS:
        raise ValueError(f"Status inválido: {status!r}")
    if key not in STEP_KEYS:
        raise ValueError(f"Step desconhecido: {key!r}")
    st.session_state["workflow_status"][key] = status


def get_step_status(key: str) -> str:
    init_workflow_status()
    return st.session_state["workflow_status"].get(key, "not_started")


def mark_skipped(key: str, message: str | None = None) -> None:
    """Marca uma etapa como concluída por decisão explícita do usuário
    (ex.: "não há interferências"). A etapa fica visualmente 'completed'."""
    init_workflow_status()
    st.session_state["skipped_steps"].add(key)
    set_step_status(key, "completed")
    if message:
        ui_theme.remember_status(f"skip_{key}", "success", message)


# ============================================================
# Avaliação automática a partir das flags existentes
# ============================================================
def _sum_production(zones_df) -> float:
    if zones_df is None or zones_df.empty:
        return 0.0
    col = "production_balanced" if "production_balanced" in zones_df.columns else "production"
    return float(pd.to_numeric(zones_df.get(col), errors="coerce").fillna(0).sum())


def _sum_attraction(zones_df) -> float:
    if zones_df is None or zones_df.empty:
        return 0.0
    col = "attraction_balanced" if "attraction_balanced" in zones_df.columns else "attraction"
    return float(pd.to_numeric(zones_df.get(col), errors="coerce").fillna(0).sum())


def evaluate_workflow() -> dict[str, str]:
    """Re-avalia status de cada etapa a partir das flags existentes
    em session_state. Atualiza st.session_state["workflow_status"]."""
    init_workflow_status()
    s = st.session_state
    skipped = s["skipped_steps"]
    out: dict[str, str] = {}

    # 1. Área de estudo (município/ponto/arquivo/polígono/corredor)
    study = s.get("study") or {}
    # Considera concluída se: nome do estudo + alguma identificação da área
    # (nome de área, município OU coordenada central diferente de 0,0).
    has_area_id = bool(
        study.get("area_name") or study.get("municipality")
        or (study.get("center_lat") not in (None, 0.0, 0))
        or (study.get("center_lon") not in (None, 0.0, 0))
    )
    has_name = study.get("name") and study.get("name") != "Novo estudo"
    has_year = (study.get("base_year") or 0) > 0
    if has_name and has_area_id and has_year:
        out["municipio"] = "completed"
    elif has_name or has_area_id:
        out["municipio"] = "in_progress"
    else:
        out["municipio"] = "not_started"

    # 2. Zonas
    zones = s.get("zones")
    if zones is None or zones.empty:
        out["zonas"] = "not_started"
    elif len(zones) < 2:
        out["zonas"] = "in_progress"
    else:
        out["zonas"] = "completed" if s.get("zones_saved") else "in_progress"

    # 3. Geração
    sumP = _sum_production(zones)
    sumA = _sum_attraction(zones)
    if s.get("balancing_applied"):
        out["geracao"] = "completed"
    elif s.get("vectors_saved") or (sumP > 0 and sumA > 0):
        out["geracao"] = "in_progress"
    else:
        out["geracao"] = "not_started"

    # 4. Distribuição
    od = s.get("od_matrix")
    if s.get("od_matrix_generated") and od is not None:
        out["distribuicao"] = "completed"
    elif s.get("impedance") is not None:
        out["distribuicao"] = "in_progress"
    else:
        out["distribuicao"] = "not_started"

    # 5. Repartição modal
    out["reparticao_modal"] = "completed" if s.get("modal_applied") else "not_started"

    # 6. Atribuição
    out["atribuicao"] = "completed" if s.get("assignment_done") else "not_started"

    # 7. Interferências
    inters = s.get("interferences") or []
    if inters or "interferencias" in skipped:
        out["interferencias"] = "completed"
    else:
        out["interferencias"] = "not_started"

    # 8. Cenários
    if s.get("base_scenario"):
        out["cenarios"] = "completed"
    elif s.get("scenarios"):
        out["cenarios"] = "in_progress"
    else:
        out["cenarios"] = "not_started"

    # 9. Biblioteca
    favs = s.get("favorite_scenarios") or []
    if favs or "biblioteca" in skipped:
        out["biblioteca"] = "completed"
    else:
        out["biblioteca"] = "not_started"

    # 10. Comparação
    if (s.get("base_scenario") and favs) or "comparacao" in skipped:
        out["comparacao"] = "completed"
    else:
        out["comparacao"] = "not_started"

    # 11. Custo Social
    if s.get("social_cost_computed") or "custo_social" in skipped:
        out["custo_social"] = "completed"
    else:
        out["custo_social"] = "not_started"

    # 12. Relatórios
    out["relatorios"] = "completed" if s.get("report_generated") else "not_started"

    # 13. Atualização (opcional)
    out["atualizacao"] = "completed" if s.get("atualizacao_done") else "not_started"

    s["workflow_status"].update(out)
    return out


# ============================================================
# Navegação
# ============================================================
def get_next_step() -> dict | None:
    """Devolve a próxima etapa não-completada (ignora as opcionais)."""
    status = evaluate_workflow()
    for step in WORKFLOW_STEPS:
        if step.get("optional"):
            continue
        if status.get(step["key"]) != "completed":
            return step
    return None


def can_access_step(key: str, mode: str = "Básico") -> bool:
    """Modo Avançado: sempre True.
    Modo Básico: bloqueia se alguma etapa anterior obrigatória estiver
    'not_started' (in_progress é tolerado para não travar demais)."""
    if mode == "Avançado":
        return True
    if key not in STEP_BY_KEY:
        return True
    idx = STEP_KEYS.index(key)
    status = evaluate_workflow()
    for k in STEP_KEYS[:idx]:
        if STEP_BY_KEY[k].get("optional"):
            continue
        st = status.get(k, "not_started")
        if st == "not_started":
            return False
    return True


# ============================================================
# Componentes visuais
# ============================================================
def render_progress_trail(current_key: str | None = None) -> None:
    """Trilha horizontal com os 13 chips de etapa."""
    status = evaluate_workflow()
    chips: list[str] = []
    for step in WORKFLOW_STEPS:
        s = status.get(step["key"], "not_started")
        klass = f"trail-chip {s}"
        if step["key"] == current_key:
            klass += " current"
        icon = STATUS_ICON.get(s, "○")
        chips.append(
            f'<span class="{klass}" title="{step["page"]}">{icon} {step["label"]}</span>'
        )
    sep = '<span class="trail-sep">›</span>'
    html = '<div class="alime-trail">' + sep.join(chips) + '</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_next_step_hint(current_key: str | None = None) -> None:
    """Card pequeno com a próxima etapa recomendada."""
    nxt = get_next_step()
    if nxt is None:
        ui_theme.success_message(
            "Todas as etapas obrigatórias concluídas! Você pode gerar o relatório consolidado."
        )
        return
    hint = HINTS.get(nxt["key"], "Continue para a próxima etapa.")
    if current_key == nxt["key"]:
        ui_theme.info(
            f"Você está na etapa recomendada: <b>{nxt['label']}</b>. {hint}"
        )
    else:
        ui_theme.info(
            f"Próximo passo: <b>{nxt['label']}</b> — {hint}"
        )


def render_guard(current_key: str) -> bool:
    """Combina trilha + hint + bloqueio. Retorna True se a página
    pode renderizar normalmente; False se foi bloqueada (modo Básico).
    """
    init_workflow_status()
    render_progress_trail(current_key)

    mode = (st.session_state.get("study") or {}).get("mode", "Básico")
    accessible = can_access_step(current_key, mode)

    if accessible:
        render_next_step_hint(current_key)
        return True

    # Bloqueio em modo Básico
    if mode == "Básico":
        ui_theme.error_message(
            "<b>Etapa anterior não concluída.</b> "
            "No modo Básico você precisa concluir as etapas anteriores "
            "antes de seguir. Volte e conclua, ou troque para modo "
            "<b>Avançado</b> na aba <b>1. Município</b>."
        )
        nxt = get_next_step()
        if nxt:
            if st.button(f"⬅ Ir para a próxima etapa pendente: {nxt['label']}",
                         use_container_width=True):
                st.session_state["page"] = nxt["page"]
                st.rerun()
        return False

    # Modo Avançado: alerta forte mas continua
    ui_theme.warning_message(
        "<b>Você está avançando com uma etapa anterior incompleta.</b> "
        "Os resultados podem ser inconsistentes."
    )
    render_next_step_hint(current_key)
    return True


def render_consistency_check() -> None:
    """Checklist 'Verificação do estudo' — útil em Configurações/Atualização."""
    status = evaluate_workflow()
    s = st.session_state
    items: list[tuple[str, str]] = [
        ("Município preenchido",          status.get("municipio", "not_started")),
        ("Zonas cadastradas (≥ 2)",       status.get("zonas", "not_started")),
        ("Vetores P/A salvos",
         "completed" if s.get("vectors_saved") or status.get("geracao") == "completed"
         else "not_started"),
        ("Balanceamento aplicado",
         "completed" if s.get("balancing_applied") else "not_started"),
        ("Matriz de impedância carregada",
         "completed" if s.get("impedance") is not None else "not_started"),
        ("Matriz O-D calculada",          status.get("distribuicao", "not_started")),
        ("Repartição modal definida",     status.get("reparticao_modal", "not_started")),
        ("Atribuição realizada",          status.get("atribuicao", "not_started")),
        ("Interferências revisadas",      status.get("interferencias", "not_started")),
        ("Cenário-base gerado",           status.get("cenarios", "not_started")),
        ("Cenários salvos na biblioteca", status.get("biblioteca", "not_started")),
        ("Custo social configurado",      status.get("custo_social", "not_started")),
        ("Relatório gerado",              status.get("relatorios", "not_started")),
    ]
    lines = []
    for label, st_val in items:
        icon = STATUS_ICON.get(st_val, "○")
        klass = f"check-{st_val}"
        lines.append(f'<li class="{klass}">{icon}&nbsp; {label}</li>')
    html = ('<div class="alime-card"><h4>Verificação do estudo</h4>'
            f'<ul class="alime-checklist">{"".join(lines)}</ul></div>')
    st.markdown(html, unsafe_allow_html=True)
