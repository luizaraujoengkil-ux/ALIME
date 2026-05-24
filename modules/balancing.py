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
    """Balanceia vetores P (produção) e A (atração) conforme o método escolhido.

    IMPORTANTE — as entradas `productions` e `attractions` devem ser sempre os
    valores ORIGINAIS, nunca valores já balanceados. Caso contrário, o fator
    aplicado em uma segunda chamada virá próximo de 1 (porque os totais já
    foram equalizados na primeira chamada).

    Matemática:

        ΣP_orig = Σ_i P_i
        ΣA_orig = Σ_j A_j

        "ajustar_atracoes":
            factor = ΣP_orig / ΣA_orig
            A'_j   = A_j · factor       (P_i permanece inalterado)

        "ajustar_producoes":
            factor = ΣA_orig / ΣP_orig
            P'_i   = P_i · factor       (A_j permanece inalterado)

        "normalizar_para_total" (T = target_total):
            P'_i = P_i · (T / ΣP_orig)
            A'_j = A_j · (T / ΣA_orig)

        "manter_sem_balancear":
            P e A retornam inalterados (apenas para diagnóstico).

    Retorna dict com:
        - P, A                        : vetores resultantes (np.ndarray)
        - sumP_original, sumA_original
        - sumP_final, sumA_final
        - factor                      : fator aplicado (1.0 se nada mudou)
        - rel_error                   : |ΣP_final - ΣA_final| / max(...)
        - method                      : método utilizado
        - diff_original               : sumP_original - sumA_original

    Exemplo (caso de teste fornecido pelo usuário em maio/2026):

        >>> P = [1615, 1310, 1107, 881, 1038, 3050, 95, 50, 30]   # ΣP = 9176
        >>> A = [2900,  700,  600,1050,  300, 3050, 95, 50, 30]   # ΣA = 8775
        >>> r = balance_vectors(P, A, method="ajustar_atracoes")
        >>> round(r["factor"], 6)
        1.045698
        >>> round(r["sumA_final"], 2)
        9176.0
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
        "diff_original": sumP - sumA,
        "factor": factor,
        "rel_error": err,
        "method": method,
    }
