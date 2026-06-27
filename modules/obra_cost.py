"""Estimador de custo de obra de arte (viaduto, ponte, mergulhão, passarela).

A largura do tabuleiro é montada a partir do nº de faixas (referência DNIT) +
acostamento + guarda-corpo + passarela. O comprimento vem direto (m) ou de
dois pontos (lat/lon início e fim, distância haversine). Custo = área × custo/m².

Tudo é editável para se ajustar à realidade local — os defaults seguem o DNIT.
"""
from __future__ import annotations

import math

# Referências DNIT / valores-padrão (editáveis na tela)
DNIT_LANE_WIDTH = 3.60   # m — largura de faixa de tráfego (rodovia DNIT)
BARRIER_WIDTH = 0.40     # m por lado — guarda-corpo / defensa (New Jersey)

# Preset por tipo de obra: custo/m² (R$), largura de faixa, acostamento/lado.
# Acostamento default URBANO (0,6 m) — em via urbana o viaduto não leva o
# acostamento rodoviário de 2,5 m. Para rodovia, aumente esse campo na tela.
STRUCTURE_PRESETS = {
    "Viaduto":                       {"cost_m2": 18000.0, "lane": 3.60, "shoulder": 0.60, "pedestrian": False},
    "Ponte":                         {"cost_m2": 20000.0, "lane": 3.60, "shoulder": 0.60, "pedestrian": False},
    "Mergulhão (passagem inferior)": {"cost_m2": 16000.0, "lane": 3.60, "shoulder": 0.60, "pedestrian": False},
    "Passarela (pedestres)":         {"cost_m2": 12000.0, "lane": 0.00, "shoulder": 0.00, "pedestrian": True},
}


def deck_width(n_lanes: float, lane_width: float = DNIT_LANE_WIDTH,
               shoulder: float = 2.50, barrier: float = BARRIER_WIDTH,
               sidewalk_width: float = 0.0, sidewalk_sides: int = 0) -> float:
    """Largura total do tabuleiro (m) = faixas + 2·acostamento + 2·guarda-corpo
    + passarelas laterais."""
    w = n_lanes * lane_width + 2 * shoulder + 2 * barrier
    w += sidewalk_sides * sidewalk_width
    return max(w, 0.0)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre dois pontos (great-circle/haversine)."""
    R = 6_371_000.0
    rad = math.radians
    dlat = rad(lat2 - lat1)
    dlon = rad(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def estimate(width_m: float, length_m: float, cost_per_m2: float) -> dict:
    """Área (m²) e custo total (R$)."""
    area = max(width_m, 0.0) * max(length_m, 0.0)
    return {"area_m2": area, "cost_brl": area * cost_per_m2}


def render_estimator() -> None:
    """Tela do estimador (chamada como aba em Cenários)."""
    import streamlit as st
    from . import ui_theme

    st.markdown(
        "Estime a **área (m²)** e o **custo** de uma obra de arte. A largura segue "
        "referência **DNIT** (você dá o nº de faixas e o sistema monta a largura); "
        "o comprimento vem direto ou de dois pontos. Tudo editável."
    )

    c1, c2 = st.columns(2)
    with c1:
        stype = st.selectbox("Tipo de obra", list(STRUCTURE_PRESETS.keys()))
        preset = STRUCTURE_PRESETS[stype]
    with c2:
        cost_m2 = st.number_input(
            "Custo por m² (R$)", min_value=1000.0, max_value=60000.0,
            value=preset["cost_m2"], step=500.0,
            help="Viaduto ~R$ 16–20 mil/m². Ajuste à realidade local.")

    # --------- Largura do tabuleiro ---------
    st.markdown("##### Largura (montada por norma DNIT)")
    if preset["pedestrian"]:
        walk_w = st.number_input("Largura útil da passarela (m)", 1.0, 10.0, 3.0, 0.5)
        width = walk_w + 2 * BARRIER_WIDTH
        st.caption(f"Largura total ≈ **{width:.2f} m** "
                   f"(útil {walk_w:.1f} m + 2×{BARRIER_WIDTH:.2f} guarda-corpo).")
    else:
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            n_lanes = st.number_input("Nº de faixas", 1, 12, 2, 1,
                                      help="O sistema atribui a largura por faixa.")
        with d2:
            lane_w = st.number_input("Largura da faixa (m)", 2.5, 4.0,
                                     float(preset["lane"]), 0.05,
                                     help="DNIT: 3,60 m (rodovia); 3,00–3,50 m (urbana).")
        with d3:
            shoulder = st.number_input("Acostamento/lado (m)", 0.0, 4.0,
                                       float(preset["shoulder"]), 0.1)
        with d4:
            barrier = st.number_input("Guarda-corpo/lado (m)", 0.0, 1.0,
                                      BARRIER_WIDTH, 0.05)
        sidewalk = st.checkbox("Incluir passarela/calçada lateral")
        sw_width, sw_sides = 0.0, 0
        if sidewalk:
            s1, s2 = st.columns(2)
            with s1:
                sw_width = st.number_input("Largura da passarela/lado (m)", 0.5, 4.0, 1.5, 0.1)
            with s2:
                sw_sides = st.radio("Lados com passarela", [1, 2], horizontal=True)
        width = deck_width(n_lanes, lane_w, shoulder, barrier, sw_width, sw_sides)
        parts = (f"{n_lanes}×{lane_w:.2f} faixa + 2×{shoulder:.2f} acostamento "
                 f"+ 2×{barrier:.2f} guarda-corpo")
        if sidewalk:
            parts += f" + {sw_sides}×{sw_width:.2f} passarela"
        st.caption(f"Largura total do tabuleiro ≈ **{width:.2f} m** ({parts}).")

    # --------- Comprimento ---------
    st.markdown("##### Comprimento")
    mode = st.radio("Como informar o comprimento",
                    ["Direto (m)", "Por dois pontos (início/fim)"], horizontal=True)
    if mode.startswith("Direto"):
        length = st.number_input("Comprimento (m)", 1.0, 5000.0, 100.0, 5.0)
    else:
        p1, p2, p3, p4 = st.columns(4)
        with p1: la1 = st.number_input("Lat início", value=-21.872428, format="%.6f")
        with p2: lo1 = st.number_input("Lon início", value=-43.321183, format="%.6f")
        with p3: la2 = st.number_input("Lat fim", value=-21.871500, format="%.6f")
        with p4: lo2 = st.number_input("Lon fim", value=-43.320900, format="%.6f")
        length = haversine_m(la1, lo1, la2, lo2)
        st.caption(f"Comprimento entre os pontos ≈ **{ui_theme.num_br(length)} m** "
                   "(linha reta/haversine).")

    # --------- Resultado ---------
    est = estimate(width, length, cost_m2)
    st.markdown("##### Resultado")
    r = st.columns(3)
    with r[0]: ui_theme.card("Área", f"{ui_theme.num_br(est['area_m2'])} m²")
    with r[1]: ui_theme.card("Custo por m²", ui_theme.brl(cost_m2))
    with r[2]: ui_theme.card("Custo total estimado", ui_theme.brl(est['cost_brl']))
    st.caption(f"Conta: {ui_theme.num_br(est['area_m2'])} m² × "
               f"{ui_theme.brl(cost_m2)}/m² = **{ui_theme.brl(est['cost_brl'])}**  "
               f"(largura {ui_theme.num_br(width, 2)} m × comprimento "
               f"{ui_theme.num_br(length)} m).")

    st.session_state["last_obra_cost"] = {
        "type": stype, "width_m": width, "length_m": length,
        "area_m2": est["area_m2"], "cost_m2": cost_m2, "cost_brl": est["cost_brl"],
    }
    ui_theme.info("Próximo passo: atribuir este custo a uma interferência para o "
                  "ranking virar **custo-benefício** (payback / IBC).")
