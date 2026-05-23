# Metodologia ALIME

O ALIME implementa, de forma simplificada, o **Modelo das 4 Etapas** do
planejamento de transportes, voltado a municípios de pequeno porte
(até ~20 mil habitantes).

## 4 Etapas

| Etapa | Pergunta | Saída principal |
|---|---|---|
| Geração       | Vou ou não vou?  | Vetores P_i e A_j |
| Distribuição  | Para onde vou?   | Matriz O-D T_ij |
| Repartição    | Como vou?        | Matriz T_ij por modo |
| Atribuição    | Por onde vou?    | Fluxos x_a por aresta |

## Pré-etapas

- **Zoneamento.** Define unidades de análise (residencial, comercial,
  centro, externo etc.). Cada zona tem produção P_i, atração A_j,
  população, centroide e tipo de uso predominante.
- **Balanceamento.** Garante ΣP ≈ ΣA antes da distribuição.

## Pós-etapas

- **Interferências.** Cadastro de barreiras urbanas (ferrovias,
  alagamentos, pontes, semáforos etc.) com penalidade de tempo/atraso.
- **Cenários.** Snapshot do estado completo para cenários
  futuro / interdição / melhoria.
- **Custo social.** Conversão monetária do atraso.

## Fluxo recomendado

1. **Município** — dados básicos.
2. **Zonas** — criar ou importar.
3. **Geração** — vetores P/A + balanceamento.
4. **Distribuição** — modelo gravitacional.
5. **Repartição modal** — participação por modo.
6. **Atribuição** — all-or-nothing.
7. **Interferências** — cadastrar barreiras.
8. **Cenário-base** — snapshot da situação atual.
9. **Cenários alternativos** — futuro / interdição / melhoria.
10. **Biblioteca** — salvar até 5 favoritos.
11. **Comparação** — analisar B/C, custo social, ranking.
12. **Relatórios** — exportar Markdown / HTML.

## Limitações estruturais

Ver `limitacoes.md`.
