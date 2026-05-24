"""Validações genéricas reutilizadas pelos módulos do ALIME."""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


# Aliases comuns aceitos para detecção automática de colunas
COLUMN_ALIASES: dict[str, list[str]] = {
    "zone_id":    ["zone_id", "zone", "id", "zona", "id_zona", "codigo", "cod"],
    "production": ["production", "producao", "produção", "origem", "p", "prod"],
    "attraction": ["attraction", "atracao", "atração", "destino", "a", "atra"],
    "population": ["population", "populacao", "população", "pop", "habitantes"],
    "notes":      ["notes", "observacoes", "obs", "comentario", "comentário"],
}


def detect_columns(df: pd.DataFrame, target_keys: Iterable[str]) -> dict[str, str | None]:
    """Tenta detectar automaticamente colunas pelos aliases conhecidos.

    Devolve um dicionário {key_alvo: nome_da_coluna_encontrada_ou_None}.
    A detecção é case-insensitive e ignora acentos no nome da coluna.
    """
    import unicodedata

    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
        return s.strip()

    normalized = {norm(c): c for c in df.columns}
    out: dict[str, str | None] = {}
    for key in target_keys:
        aliases = COLUMN_ALIASES.get(key, [key])
        found: str | None = None
        for a in aliases:
            n = norm(a)
            if n in normalized:
                found = normalized[n]
                break
        out[key] = found
    return out


def warn_population(pop: int | float) -> str | None:
    """Retorna mensagem de aviso se a população exceder 20 mil habitantes."""
    try:
        p = float(pop)
    except Exception:
        return None
    if p > 20_000:
        return (
            "Este simulador foi concebido para municípios de pequeno porte; "
            "resultados para cidades maiores exigem maior calibração."
        )
    return None


def numeric_clean(s: pd.Series, fill: float = 0.0) -> pd.Series:
    """Converte para numérico (errors='coerce') e preenche NaN com `fill`."""
    return pd.to_numeric(s, errors="coerce").fillna(fill)


def percentages_normalize(values: dict[str, float]) -> tuple[dict[str, float], bool]:
    """Garante que os percentuais somem 100% (1.0). Retorna (dict, foi_normalizado).

    Se a soma já estiver em [0.99, 1.01], devolve sem mexer.
    """
    total = sum(values.values())
    if total <= 0:
        return values, False
    if 0.99 <= total <= 1.01:
        return values, False
    return {k: v / total for k, v in values.items()}, True


def safe_min_distance(d: np.ndarray, dmin: float) -> np.ndarray:
    """Aplica piso mínimo na matriz de distâncias para evitar divisão por zero."""
    return np.where(d < dmin, dmin, d)


# ============================================================
# Validação do balanceamento P/A
# ============================================================
def validate_balancing(
    productions_original: list | np.ndarray,
    attractions_original: list | np.ndarray,
    productions_balanced: list | np.ndarray,
    attractions_balanced: list | np.ndarray,
    method: str,
    tol_rel: float = 1e-6,
) -> dict:
    """Verifica a consistência do balanceamento P/A.

    Regras aplicadas (matemática mínima):

    - "ajustar_atracoes":
        * P_balanced[i] deve ser igual a P_original[i] (não muda)
        * Σ A_balanced ≈ Σ P_original
        * factor = Σ P_original / Σ A_original
        * A_balanced[j] = A_original[j] · factor

    - "ajustar_producoes":
        * A_balanced[j] deve ser igual a A_original[j] (não muda)
        * Σ P_balanced ≈ Σ A_original
        * factor = Σ A_original / Σ P_original

    Retorna dict com `ok` (bool), `factor_expected`, `factor_observed`,
    `messages` (lista de problemas) e somatórios.
    """
    Po = np.asarray(productions_original, dtype=float)
    Ao = np.asarray(attractions_original, dtype=float)
    Pb = np.asarray(productions_balanced, dtype=float)
    Ab = np.asarray(attractions_balanced, dtype=float)

    sumPo, sumAo = float(Po.sum()), float(Ao.sum())
    sumPb, sumAb = float(Pb.sum()), float(Ab.sum())
    messages: list[str] = []

    if method == "ajustar_atracoes":
        factor_expected = sumPo / sumAo if sumAo > 0 else float("nan")
        factor_observed = sumAb / sumAo if sumAo > 0 else float("nan")
        # P deve ficar inalterado
        if not np.allclose(Po, Pb, rtol=tol_rel, atol=1e-6):
            messages.append("production_balanced deveria ser igual a production_original.")
        # Σ A balanceada ≈ Σ P original
        if abs(sumAb - sumPo) / max(sumPo, 1e-9) > tol_rel:
            messages.append(
                f"Σ A_balanced ({sumAb:.6f}) ≠ Σ P_original ({sumPo:.6f})."
            )
    elif method == "ajustar_producoes":
        factor_expected = sumAo / sumPo if sumPo > 0 else float("nan")
        factor_observed = sumPb / sumPo if sumPo > 0 else float("nan")
        # A deve ficar inalterada
        if not np.allclose(Ao, Ab, rtol=tol_rel, atol=1e-6):
            messages.append("attraction_balanced deveria ser igual a attraction_original.")
        if abs(sumPb - sumAo) / max(sumAo, 1e-9) > tol_rel:
            messages.append(
                f"Σ P_balanced ({sumPb:.6f}) ≠ Σ A_original ({sumAo:.6f})."
            )
    elif method in ("normalizar_para_total", "manter_sem_balancear"):
        factor_expected = float("nan")
        factor_observed = float("nan")
    else:
        return {"ok": False, "messages": [f"Método desconhecido: {method}"]}

    # Diferença factor_expected vs observed
    if not (np.isnan(factor_expected) or np.isnan(factor_observed)):
        if abs(factor_observed - factor_expected) > 1e-6:
            messages.append(
                f"factor observado={factor_observed:.10f} ≠ "
                f"factor esperado={factor_expected:.10f}"
            )

    return {
        "ok": len(messages) == 0,
        "factor_expected": factor_expected,
        "factor_observed": factor_observed,
        "sum_P_original": sumPo,
        "sum_A_original": sumAo,
        "sum_P_balanced": sumPb,
        "sum_A_balanced": sumAb,
        "messages": messages,
    }


# Caso de teste de referência fornecido pelo usuário
BALANCING_REFERENCE_CASE = {
    "zone_ids": ["ZT01", "ZT02", "ZT03", "ZT04", "ZT05",
                 "ZTE01", "ZTE02", "ZTE03", "ZTE04"],
    "production": [1615, 1310, 1107,  881, 1038, 3050,  95, 50, 30],
    "attraction": [2900,  700,  600, 1050,  300, 3050,  95, 50, 30],
    "method": "ajustar_atracoes",
    "expected": {
        "sum_P_original": 9176.0,
        "sum_A_original": 8775.0,
        "factor": 9176.0 / 8775.0,             # ≈ 1.0456980056980057
        "sum_A_balanced": 9176.0,
    },
}
