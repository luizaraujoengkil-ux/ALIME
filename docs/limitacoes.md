# Limitações do ALIME

> O ALIME é uma ferramenta **exploratória** de apoio ao planejamento
> preliminar. Os resultados **não substituem** levantamento de campo,
> contagem volumétrica, pesquisa O-D domiciliar, microssimulação,
> EVTEA, orçamento executivo ou projeto de engenharia.

## Limitações de modelagem

- **Gravitacional simplificado:** sem ajuste duplo (Furness), sem
  calibração formal a partir de pesquisa O-D real.
- **All-or-nothing:** toda a demanda do par (i,j) é alocada no caminho
  mínimo. Não há equilíbrio (BPR/Wardrop) nem capacidade.
- **Repartição modal global** (versão atual): coeficientes s_m fixos
  para todos os pares O-D no modo básico.
- **Rede simplificada:** se OSMnx não estiver disponível, o ALIME usa
  uma rede k-vizinhos dos centroides — abstração geométrica.
- **Sem matriz de tempo real:** velocidades são médias declaradas.

## Limitações de dados

- Vetores P/A frequentemente vêm de estimativas (não pesquisa O-D).
- Interferências têm parâmetros operacionais informados manualmente.
- Valor do tempo e ocupação média são genéricos (R$ 18/h, 1.4 p/v).

## O que o ALIME NÃO faz

- Microssimulação (Vissim, SUMO, Aimsun).
- Orçamento de obras detalhado.
- Análise ambiental / emissões formal.
- Modelo de uso do solo.
- Calibração automática via contagem volumétrica.

## Quando usar o ALIME

✅ Diagnóstico preliminar e priorização de intervenções  
✅ Estudos comparativos de cenários  
✅ Apresentações executivas para apoio à decisão  
✅ Treinamento e formação em planejamento de transportes  

## Quando NÃO usar o ALIME

❌ Projeto executivo de engenharia  
❌ EVTEA formal  
❌ Aprovação de investimento sem estudos complementares  
❌ Cidades >100 mil habitantes sem calibração específica  
