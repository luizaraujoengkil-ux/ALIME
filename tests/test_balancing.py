"""Testes do balanceamento P/A.

Execução autônoma (sem pytest):

    python tests/test_balancing.py

Cobre o caso de teste real fornecido pelo usuário em maio/2026:

    9 zonas com ΣP = 9176 e ΣA = 8775
    factor esperado = 9176 / 8775 ≈ 1.0456980056980057

Também cobre idempotência (clicar "Aplicar" várias vezes não acumula)
e os métodos espelhados (ajustar_producoes, normalizar_para_total).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Permite executar como script standalone
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from modules.balancing import balance_vectors  # noqa: E402
from modules.validation import (  # noqa: E402
    validate_balancing,
    BALANCING_REFERENCE_CASE,
)


# Caso real fornecido pelo usuário
P_REAL = [1615, 1310, 1107, 881, 1038, 3050, 95, 50, 30]
A_REAL = [2900,  700,  600, 1050,  300, 3050, 95, 50, 30]
SUM_P_EXPECTED = 9176.0
SUM_A_EXPECTED = 8775.0
FACTOR_EXPECTED = 9176.0 / 8775.0          # 1.0456980056980057
TOL = 1e-9


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_sums_match_reference():
    _assert(abs(sum(P_REAL) - SUM_P_EXPECTED) < TOL,
            f"ΣP atual = {sum(P_REAL)}, esperado {SUM_P_EXPECTED}")
    _assert(abs(sum(A_REAL) - SUM_A_EXPECTED) < TOL,
            f"ΣA atual = {sum(A_REAL)}, esperado {SUM_A_EXPECTED}")


def test_ajustar_atracoes_factor_and_sums():
    r = balance_vectors(P_REAL, A_REAL, method="ajustar_atracoes")
    _assert(abs(r["factor"] - FACTOR_EXPECTED) < 1e-12,
            f"factor={r['factor']!r}, esperado {FACTOR_EXPECTED!r}")
    _assert(abs(r["sumP_original"] - SUM_P_EXPECTED) < TOL, "ΣP_original")
    _assert(abs(r["sumA_original"] - SUM_A_EXPECTED) < TOL, "ΣA_original")
    _assert(abs(r["sumP_final"]    - SUM_P_EXPECTED) < TOL, "ΣP_final deve = ΣP_original")
    _assert(abs(r["sumA_final"]    - SUM_P_EXPECTED) < 1e-6,
            f"ΣA_final={r['sumA_final']}, esperado {SUM_P_EXPECTED}")
    _assert(r["rel_error"] < 1e-9, f"erro relativo {r['rel_error']}")


def test_ajustar_atracoes_each_zone():
    """A_balanced[j] = A_original[j] · factor, P inalterado."""
    r = balance_vectors(P_REAL, A_REAL, method="ajustar_atracoes")
    expected_A = np.array(A_REAL) * FACTOR_EXPECTED
    _assert(np.allclose(r["A"], expected_A, atol=1e-9),
            f"A balanceada divergiu do esperado.\nGot:    {r['A']}\nExpect: {expected_A}")
    _assert(np.allclose(r["P"], np.array(P_REAL), atol=1e-9),
            "P deveria permanecer inalterada em ajustar_atracoes")


def test_idempotence_ajustar_atracoes():
    """Aplicar o balanceamento DUAS vezes (passando os originais ambas vezes)
    deve produzir o mesmo resultado — protege contra acumular o fator."""
    r1 = balance_vectors(P_REAL, A_REAL, method="ajustar_atracoes")
    r2 = balance_vectors(P_REAL, A_REAL, method="ajustar_atracoes")
    _assert(abs(r1["factor"] - r2["factor"]) < 1e-15, "factor mudou em re-chamada")
    _assert(np.allclose(r1["A"], r2["A"]), "A balanceada mudou em re-chamada")


def test_ajustar_producoes_mirror():
    """Espelho de ajustar_atracoes: A fica intacta, P recebe o fator inverso."""
    r = balance_vectors(P_REAL, A_REAL, method="ajustar_producoes")
    factor_expected = SUM_A_EXPECTED / SUM_P_EXPECTED   # 8775 / 9176
    _assert(abs(r["factor"] - factor_expected) < 1e-12,
            f"factor={r['factor']}, esperado {factor_expected}")
    _assert(np.allclose(r["A"], np.array(A_REAL)),
            "A deveria permanecer inalterada em ajustar_producoes")
    _assert(abs(r["sumP_final"] - SUM_A_EXPECTED) < 1e-6,
            "ΣP_final deveria igualar ΣA_original")


def test_validate_balancing_reports_ok():
    r = balance_vectors(P_REAL, A_REAL, method="ajustar_atracoes")
    chk = validate_balancing(P_REAL, A_REAL, r["P"], r["A"], "ajustar_atracoes")
    _assert(chk["ok"], f"validate_balancing reportou: {chk['messages']}")
    _assert(abs(chk["factor_expected"] - FACTOR_EXPECTED) < 1e-12,
            f"factor_expected={chk['factor_expected']}")


def test_reference_case_constants():
    ref = BALANCING_REFERENCE_CASE
    _assert(ref["expected"]["sum_P_original"] == SUM_P_EXPECTED, "ref P")
    _assert(ref["expected"]["sum_A_original"] == SUM_A_EXPECTED, "ref A")
    _assert(abs(ref["expected"]["factor"] - FACTOR_EXPECTED) < 1e-15, "ref factor")


def test_normalizar_para_total():
    """Normaliza ambos para um total alvo T = 10000."""
    T = 10000.0
    r = balance_vectors(P_REAL, A_REAL,
                        method="normalizar_para_total", target_total=T)
    _assert(abs(r["sumP_final"] - T) < 1e-6, f"ΣP_final={r['sumP_final']}")
    _assert(abs(r["sumA_final"] - T) < 1e-6, f"ΣA_final={r['sumA_final']}")


def test_manter_sem_balancear():
    r = balance_vectors(P_REAL, A_REAL, method="manter_sem_balancear")
    _assert(np.allclose(r["P"], np.array(P_REAL)), "P alterada indevidamente")
    _assert(np.allclose(r["A"], np.array(A_REAL)), "A alterada indevidamente")
    _assert(r["factor"] == 1.0, f"factor={r['factor']}, esperado 1.0")


# ============================================================
# Testes do esquema de 4 colunas (production_original,
# attraction_original, production_balanced, attraction_balanced)
# ============================================================
def test_schema_zones_module_creates_four_columns():
    """zones._coerce + reset_all_layers garantem as 4 colunas."""
    import pandas as pd
    from modules import zones as zones_mod

    df_in = pd.DataFrame({
        "zone_id": [f"ZT0{i+1}" for i in range(9)],
        "zone_name": ["Centro", "Norte", "Sul", "Ind", "Rural",
                      "Externo1", "Externo2", "Externo3", "Externo4"],
        "production": P_REAL,
        "attraction": A_REAL,
    })
    df = zones_mod.reset_all_layers(zones_mod._coerce(df_in))
    for c in ("production_original", "attraction_original",
              "production_balanced", "attraction_balanced",
              "balance_method", "factor_applied"):
        _assert(c in df.columns, f"coluna {c} ausente após reset_all_layers")
    # Originais = balanced = production/attraction (estado inicial)
    _assert(np.allclose(df["production_original"].astype(float), P_REAL),
            "production_original difere do input")
    _assert(np.allclose(df["attraction_original"].astype(float), A_REAL),
            "attraction_original difere do input")
    _assert(np.allclose(df["production_balanced"].astype(float), P_REAL),
            "production_balanced != production_original inicialmente")
    _assert(np.allclose(df["attraction_balanced"].astype(float), A_REAL),
            "attraction_balanced != attraction_original inicialmente")


def test_schema_balancing_updates_only_balanced_columns():
    """Após balanceamento, *_original ficam intactos; *_balanced recebe."""
    import pandas as pd
    from modules import zones as zones_mod

    df = pd.DataFrame({
        "zone_id": [f"ZT0{i+1}" for i in range(9)],
        "zone_name": ["x"] * 9,
        "production": P_REAL,
        "attraction": A_REAL,
    })
    df = zones_mod.reset_all_layers(zones_mod._coerce(df))

    # Simula o que trip_generation faz no botão "Aplicar balanceamento"
    P_orig = df["production_original"].to_numpy()
    A_orig = df["attraction_original"].to_numpy()
    res = balance_vectors(P_orig, A_orig, method="ajustar_atracoes")

    # Escreve apenas em _balanced
    df["production_balanced"] = res["P"]
    df["attraction_balanced"] = res["A"]
    df["balance_method"] = res["method"]
    df["factor_applied"] = round(res["factor"], 10)

    # Originais permanecem intactos
    _assert(np.allclose(df["production_original"].astype(float), P_REAL),
            "production_original foi sobrescrito (regressão!)")
    _assert(np.allclose(df["attraction_original"].astype(float), A_REAL),
            "attraction_original foi sobrescrito (regressão!)")
    # Balanced reflete o resultado do motor
    _assert(np.allclose(df["production_balanced"].astype(float), P_REAL),
            "production_balanced != P_original em ajustar_atracoes")
    expected_A = np.array(A_REAL) * FACTOR_EXPECTED
    _assert(np.allclose(df["attraction_balanced"].astype(float), expected_A, atol=1e-9),
            "attraction_balanced divergiu do esperado")
    _assert(df["balance_method"].iloc[0] == "ajustar_atracoes")
    _assert(abs(float(df["factor_applied"].iloc[0]) - FACTOR_EXPECTED) < 1e-8)


def test_get_balanced_vectors_returns_balanced():
    """Downstream consumir get_balanced_vectors() retorna o vetor balanceado."""
    import pandas as pd
    from modules import zones as zones_mod

    df = pd.DataFrame({
        "zone_id": [f"ZT0{i+1}" for i in range(9)],
        "zone_name": ["x"] * 9,
        "production": P_REAL,
        "attraction": A_REAL,
    })
    df = zones_mod.reset_all_layers(zones_mod._coerce(df))
    res = balance_vectors(df["production_original"].to_numpy(),
                          df["attraction_original"].to_numpy(),
                          method="ajustar_atracoes")
    df["production_balanced"] = res["P"]
    df["attraction_balanced"] = res["A"]

    P, A = zones_mod.get_balanced_vectors(df)
    _assert(abs(float(P.sum()) - SUM_P_EXPECTED) < 1e-6,
            f"ΣP balanceada incorreta: {P.sum()}")
    _assert(abs(float(A.sum()) - SUM_P_EXPECTED) < 1e-6,
            f"ΣA balanceada incorreta: {A.sum()}")


# ============================================================
# Runner standalone
# ============================================================
def _run_all() -> int:
    tests = [
        test_sums_match_reference,
        test_ajustar_atracoes_factor_and_sums,
        test_ajustar_atracoes_each_zone,
        test_idempotence_ajustar_atracoes,
        test_ajustar_producoes_mirror,
        test_validate_balancing_reports_ok,
        test_reference_case_constants,
        test_normalizar_para_total,
        test_manter_sem_balancear,
        test_schema_zones_module_creates_four_columns,
        test_schema_balancing_updates_only_balanced_columns,
        test_get_balanced_vectors_returns_balanced,
    ]
    failures = []
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except Exception as e:
            failures.append((t.__name__, repr(e)))
            print(f"  ✗ {t.__name__}: {e}")

    print()
    if failures:
        print(f"{len(failures)} testes FALHARAM:")
        for name, err in failures:
            print(f"  - {name}: {err}")
        return 1
    print(f"Todos os {len(tests)} testes passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
