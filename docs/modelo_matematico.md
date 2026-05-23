# Modelo Matemático do ALIME

## 1. Balanceamento de vetores

Sejam P_i (produção da zona i) e A_j (atração da zona j).

- ΣP = Σ_i P_i
- ΣA = Σ_j A_j

Quando ΣP ≠ ΣA, aplica-se uma das estratégias:

1. **Ajustar atrações:** F_A = ΣP / ΣA;  A'_j = A_j · F_A
2. **Ajustar produções:** F_P = ΣA / ΣP;  P'_i = P_i · F_P
3. **Normalizar para total T:**
   - P'_i = P_i · (T / ΣP)
   - A'_j = A_j · (T / ΣA)
4. **Manter sem balancear** (com aviso).

Implementação: `modules/balancing.py → balance_vectors()`.

---

## 2. Impedância (custo generalizado)

Forma geral:

    c_ij = α_d · d_ij + α_t · t_ij + α_b · B_ij + α_r · R_ij

Na versão atual (V01):

    c_ij = tempo_movimento + atraso_interferencias

com:

    tempo_movimento = (d_ij / v) · 60

Piso mínimo para evitar singularidades:

    d_ij ← max(d_ij, d_min)

Implementação: `modules/trip_distribution.py → impedance_from_distance()`.

---

## 3. Modelo gravitacional (normalizado por origem)

    T_ij = P_i · ( A_j · f(c_ij) ) / Σ_j ( A_j · f(c_ij) )

Funções de atrito:

- **Potência:**  f(c) = 1 / c^β
- **Exponencial:** f(c) = exp(-β · c)

Propriedade: Σ_j T_ij = P_i (linha respeita a produção).  
As colunas Σ_i T_ij podem divergir de A_j — o erro é calculado.

Implementação: `modules/trip_distribution.py → gravity_distribution()`.

---

## 4. Repartição modal

Versão básica:

    T_ij^m = T_ij · s_m

com Σ_m s_m = 1 (normalizado automaticamente).

Implementação: `modules/modal_split.py → split_matrix()`.

---

## 5. Atribuição all-or-nothing

    x_a = Σ_ij T_ij · δ_{a,ij}

onde δ_{a,ij} = 1 se a aresta `a` está no caminho mínimo (i,j).

Implementação: `modules/network_assignment.py → all_or_nothing()`.

---

## 6. Interferências ferroviárias

Para passagens em nível:

    tempo_ocupacao_min  = (L_trem [km] / v_trem [km/h]) · 60
    tempo_bloqueio_min  = tempo_ocupacao_min · fator_operacional
    tempo_total_interf  = tempo_bloqueio + tempo_dissipacao_fila

Para outras interferências, parametriza-se:

- `blocks_per_day`
- `average_blockage_min`
- `queue_dissipation_min`
- `capacity_reduction_percent`

Implementação: `modules/interferences.py → compute_rail()`.

---

## 7. Custo social

    pessoas_afetadas = fluxo_afetado · ocupacao_media
    horas_perdidas   = pessoas_afetadas · tempo_atraso_min / 60
    custo_atraso     = horas_perdidas  · valor_tempo_hora
    custo_anual      = custo_atraso    · dias_uteis

Para uma melhoria:

    beneficio_anual = custo_base - custo_cenario
    payback         = custo_obra / beneficio_anual
    IBC             = beneficio_anual / custo_obra

Valores default:

- `occupancy = 1.4`
- `value_of_time_brl_h = 18.0`
- `operating_days = 252`

Implementação: `modules/social_cost.py → social_cost()`.

---

## 8. Cenários

Cada cenário guarda um **snapshot** com:

- zonas, vetores P/A balanceados;
- matriz O-D, matriz por modo;
- matriz de impedância, rede, fluxos;
- interferências e seus parâmetros computados;
- custo social, custo de obra;
- intervenções e premissas.

### 8.1 Futuro

    P'_i = P_i · (1 + g_i)^n
    A'_j = A_j · (1 + h_j)^n

### 8.2 Interdição

- **Total:** remove a aresta da rede.
- **Parcial:** t'_a = t_a · fator + atraso_extra.

### 8.3 Melhoria

- Adiciona arestas novas.
- Reduz ou elimina interferências existentes.
- Re-aloca demanda na rede modificada.

---

## 9. Avisos metodológicos

> Modelo exploratório. Não substitui pesquisa O-D, microssimulação,
> EVTEA, orçamento ou projeto de engenharia.
