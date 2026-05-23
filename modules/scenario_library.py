"""Biblioteca de cenários — favoritos (até 5) + persistência em JSON."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from . import ui_theme


MAX_FAVORITES = 5
EXPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "exports" / "scenarios"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _favorites() -> list[dict]:
    return st.session_state.setdefault("favorite_scenarios", [])


def add_to_favorites(sc: dict) -> tuple[bool, str]:
    favs = _favorites()
    if len(favs) >= MAX_FAVORITES:
        return False, ("Limite de 5 cenários salvos atingido. "
                       "Remova ou substitua um cenário.")
    favs.append(sc)
    return True, f"Cenário '{sc['name']}' salvo na biblioteca."


def export_scenario_json(sc: dict) -> Path:
    fname = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{sc['scenario_id']}.json"
    path = EXPORT_DIR / fname
    with path.open("w", encoding="utf-8") as f:
        json.dump(sc, f, ensure_ascii=False, indent=2, default=str)
    return path


def import_scenario_json(file) -> dict:
    data = json.loads(file.read().decode("utf-8"))
    return data


def render() -> None:
    ui_theme.section_title("📚", "Biblioteca de Cenários")
    st.markdown(
        "<p style='color:#B8C0CC'>Salve até 5 cenários favoritos para comparação. "
        "Você pode renomear, duplicar, exportar (JSON) ou remover.</p>",
        unsafe_allow_html=True,
    )

    scs = st.session_state.get("scenarios", [])
    favs = _favorites()

    # ---- Adicionar à biblioteca ----
    st.markdown("### Adicionar à biblioteca")
    if not scs:
        ui_theme.info("Nenhum cenário gerado ainda. Vá à aba **8. Cenários**.")
    else:
        opts = [f"{s['scenario_id']} - {s['name']} ({s['type']})" for s in scs]
        sel = st.selectbox("Selecione um cenário", opts)
        if st.button("⭐ Salvar cenário para comparação"):
            idx = opts.index(sel)
            ok, msg = add_to_favorites(scs[idx])
            (ui_theme.ok if ok else ui_theme.warn)(msg)

    # ---- Importar JSON ----
    st.markdown("### Importar cenário JSON")
    up = st.file_uploader("Arquivo JSON de cenário", type=["json"], key="lib_up")
    if up is not None:
        try:
            sc = import_scenario_json(up)
            ok, msg = add_to_favorites(sc)
            (ui_theme.ok if ok else ui_theme.warn)(msg)
        except Exception as e:
            ui_theme.warn(f"Falha ao importar: {e}")

    # ---- Listar / gerenciar favoritos ----
    st.markdown("### Favoritos")
    if not favs:
        ui_theme.info("Biblioteca vazia.")
        return
    for i, sc in enumerate(favs):
        with st.container(border=True):
            c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 1, 1, 1])
            with c1:
                new_name = st.text_input("Nome", value=sc["name"], key=f"rn_{i}")
                sc["name"] = new_name
            with c2:
                st.write(f"**Tipo:** {sc['type']}")
                st.write(f"**Horizonte:** {sc.get('horizon_year','—')}")
            with c3:
                ind = sc.get("assignment", {})
                st.write(f"**Σ viagens:** {ind.get('total_trips',0):,.0f}")
                st.write(f"**Tempo médio:** {ind.get('avg_time_min',0):.1f} min")
            with c4:
                if st.button("⧉ Duplicar", key=f"dup_{i}"):
                    if len(favs) >= MAX_FAVORITES:
                        ui_theme.warn("Limite de 5 cenários salvos atingido. "
                                       "Remova ou substitua um cenário.")
                    else:
                        from copy import deepcopy
                        clone = deepcopy(sc)
                        clone["scenario_id"] = sc["scenario_id"] + "-d"
                        clone["name"] = sc["name"] + " (cópia)"
                        favs.append(clone)
            with c5:
                if st.button("💾 JSON", key=f"exp_{i}"):
                    p = export_scenario_json(sc)
                    ui_theme.ok(f"Exportado: {p}")
            with c6:
                if st.button("🗑", key=f"del_{i}"):
                    favs.pop(i)
                    ui_theme.ok("Cenário removido.")
                    st.rerun()
