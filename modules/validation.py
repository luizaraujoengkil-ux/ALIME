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
