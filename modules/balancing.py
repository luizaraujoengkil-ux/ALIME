"""Balanceamento de vetores Produção × Atração.

Em modelos clássicos de 4 etapas, ΣP deve ser igual a ΣA.  Este módulo
oferece quatro estratégias:

1. Ajustar atrações para igualar produções: F_A = ΣP / ΣA → A'_j = A_j · F_A
2. Ajustar produções para igualar atrações: F_P = ΣA / ΣP → P'_i = P_i · F_P
3. Normalizar ambos para um total alvo T: P' e A' são reescalados.
4. Manter sem balancear (apenas avisa).
"""
from __future__ import annotations

from typing import Literal
import numpy as np


Method = Literal[
    "ajustar_atracoes",
    "ajustar_producoes",
    "normalizar_para_total",
    "manter_sem_balancear",
]


def balance_vectors(
    productions: np.ndarray,
    attractions: np.ndarray,
    method: Method = "ajustar_atracoes",
    target_total: float | None = None,
) -> dict:
    """Balanceia vetores P e A conforme o método escolhido.

    Matemática:
        ΣP = Σ_i P_i
        ΣA = Σ_j A_j

        - "ajustar_atracoes":    A'_j = A_j · (ΣP / ΣA)
        - "ajustar_producoes":   P'_i = P_i · (ΣA / ΣP)
        - "normalizar_para_total": P'_i = P_i · (T/ΣP),  A'_j = A_j · (T/ΣA)
        - "manter_sem_balancear": devolve P e A inalterados.

    Retorna dict com: P', A', ΣP, ΣA, fator aplicado, erro relativo final, método.
    """
    P = np.asarray(productions, dtype=float).copy()
    A = np.asarray(attractions, dtype=float).copy()

    sumP = float(P.sum())
    sumA = float(A.sum())
    factor = 1.0

    if method == "ajustar_atracoes":
        if sumA > 0:
            factor = sumP / sumA
            A = A * factor
    elif method == "ajustar_producoes":
        if sumP > 0:
            factor = sumA / sumP
            P = P * factor
    elif method == "normalizar_para_total":
        T = float(target_total if target_total is not None else max(sumP, sumA))
        if sumP > 0:
            P = P * (T / sumP)
        if sumA > 0:
            A = A * (T / sumA)
        factor = T
    elif method == "manter_sem_balancear":
        pass
    else:
        raise ValueError(f"Método desconhecido: {method}")

    sumP_new = float(P.sum())
    sumA_new = float(A.sum())
    err = abs(sumP_new - sumA_new) / max(sumP_new, sumA_new, 1e-9)
    return {
        "P": P,
        "A": A,
        "sumP_original": sumP,
        "sumA_original": sumA,
        "sumP_final": sumP_new,
        "sumA_final": sumA_new,
        "factor": factor,
        "rel_error": err,
        "method": method,
    }
