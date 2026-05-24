# ALIME — Análise Local Integrada de Mobilidade e Engenharia

O **ALIME** é um simulador exploratório de apoio ao planejamento preliminar da mobilidade urbana, voltado prioritariamente a municípios de pequeno porte, especialmente localidades com até aproximadamente **20 mil habitantes**. A ferramenta é **genérica**: não é restrita a nenhum município específico — qualquer cidade dentro da faixa de aplicação pode ser modelada definindo suas próprias zonas, vetores de viagem e interferências.

Com o ALIME é possível estruturar zonas de análise, importar ou estimar vetores de produção e atração de viagens, gerar matrizes origem-destino, alocar fluxos de forma simplificada na rede viária, cadastrar interferências urbanas (ferrovias, alagamentos, pontes, gargalos, semáforos) e comparar cenários de **interdição**, **crescimento futuro** ou **melhoria de infraestrutura**.

O objetivo é apoiar a tomada de decisão inicial em cidades com baixa disponibilidade de recursos técnicos e financeiros, oferecendo uma base preliminar para **priorização de estudos, intervenções e investimentos em mobilidade urbana**.

> **Aviso metodológico.** O ALIME é uma ferramenta exploratória de apoio ao planejamento preliminar. Os resultados **não substituem** levantamento de campo, contagem volumétrica, pesquisa O-D domiciliar, microssimulação, EVTEA, orçamento executivo ou projeto de engenharia.

---

## Objetivo

Aplicar o **Modelo das 4 Etapas** do planejamento de transportes em estudos preliminares:

1. **Geração de viagens** — *Vou ou não vou?*
2. **Distribuição de viagens** — *Para onde vou?*
3. **Repartição modal** — *Como vou?*
4. **Atribuição de tráfego** — *Por onde vou?*

Adicionalmente, o ALIME oferece:

- Cadastro de interferências urbanas (ferrovia, alagamento, ponte, semáforo, etc.);
- Simulação de cenários (interdição, futuro, melhoria);
- Comparação de até **5 cenários favoritos**;
- Relatórios individuais e consolidados;
- Avaliação preliminar de tempo, atraso, custo social e benefício/custo.

---

## Perguntas que o ALIME ajuda a responder

- **Diagnóstico territorial:** quais zonas da cidade produzem e atraem mais viagens?
- **Padrões de deslocamento:** para onde tendem a ocorrer os principais fluxos?
- **Gargalos da rede:** quais trechos concentram o maior fluxo potencial?
- **Barreiras urbanas:** quais interferências (ferrovia, alagamento, ponte estreita, semáforo, gargalo) aumentam o tempo de deslocamento e o atraso diário?
- **Resiliência:** o que acontece se uma ponte, rua, passagem em nível ou via crítica for interditada (total ou parcialmente)?
- **Avaliação de obras:** qual o impacto de uma nova ponte, viaduto, túnel, passarela, ligação viária, retirada de passagem em nível ou duplicação?
- **Comparação de alternativas:** qual cenário apresenta maior redução de tempo, atraso e custo social anual?
- **Priorização de investimentos:** quais alternativas devem ser priorizadas para estudos técnicos posteriores (EVTEA, microssimulação, projeto executivo)?

---

## Tipos de cenários

O ALIME trabalha com **quatro grupos** de cenários e permite salvar até **5 cenários favoritos** para comparação direta com o cenário-base.

### Cenário-base

Representa a **situação atual** da cidade: rede viária, zonas, vetores P/A balanceados, matriz O-D, repartição modal, interferências e tempos estimados. Funciona como **marco de referência** contra o qual todos os outros cenários são comparados.

### Cenários de interdição

Avaliam o impacto de **bloqueios totais ou parciais** na rede:
- ponte ou viaduto interditado;
- rua ou rodovia bloqueada;
- passagem em nível fechada;
- via alagada ou com queda de barreira;
- obra temporária ou acidente;
- semáforo crítico com retenção;
- evento urbano com bloqueio parcial.

Em bloqueio total, a aresta é removida da rede; em bloqueio parcial, o tempo é multiplicado por um fator de penalidade.

### Cenários de melhoria

Avaliam o impacto de **obras e intervenções**:
- viaduto, ponte, túnel, passagem inferior/superior;
- passarela para pedestres;
- nova ligação viária ou rodoviária;
- duplicação de via;
- retirada de passagem em nível;
- requalificação de cruzamento;
- alteração de sentido ou nova rota de transporte coletivo;
- melhoria operacional (sinalização, capacidade).

O ALIME adiciona arestas novas, reduz ou elimina interferências existentes, e reatribui a demanda.

### Cenários futuros

Projetam **crescimento** de produção e atração de viagens, novos polos geradores ou zonas adicionais para horizontes definidos pelo usuário (5, 10, 20 anos). Permitem antecipar gargalos antes que se concretizem.

### Biblioteca de cenários (até 5 favoritos)

O usuário pode salvar **até 5 cenários favoritos** na biblioteca, exportá-los em JSON, renomeá-los, duplicá-los ou removê-los. A tela **Comparação** lê automaticamente o cenário-base + favoritos e gera tabela comparativa, rankings (melhor tempo, maior benefício, melhor B/C, mais crítico) e gráficos.

---

## Instalação

```powershell
cd alime_simulador
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **OSMnx é opcional.** Se a instalação falhar (algumas dependências GIS no Windows são chatas), o ALIME continua funcionando com rede simplificada baseada em k-vizinhos dos centroides.

---

## Execução

```powershell
streamlit run app.py
```

Ou pelo Streamlit Community Cloud, a partir de um fork público deste repositório.

---

## Estrutura de pastas

```
alime_simulador/
  app.py                       # Entrada principal Streamlit
  README.md
  requirements.txt
  runtime.txt                  # Versão Python (Streamlit Cloud)
  .streamlit/config.toml       # Tema oficial do app
  assets/
    styles.css                 # CSS do tema escuro/âmbar
    logo_placeholder.png
  data/
    demo/                      # Dados demo embutidos
    uploads/                   # Uploads do usuário
    exports/
      scenarios/               # Cenários salvos (JSON)
      reports/                 # Relatórios exportados (HTML/MD)
  modules/
    ui_theme.py                # Tema, paleta, helpers visuais
    city_setup.py              # Tela 1 - município e estudo
    zones.py                   # Tela 2 - zonas
    trip_generation.py         # Tela 3 - geração
    balancing.py               # Balanceamento P/A
    trip_distribution.py       # Tela 4 - distribuição (gravitacional)
    modal_split.py             # Tela 5 - repartição modal
    network_assignment.py      # Tela 6 - atribuição na rede
    interferences.py           # Tela 7 - interferências
    scenarios.py               # Tela 8 - cenários
    scenario_library.py        # Biblioteca de cenários (até 5)
    comparison.py              # Comparação multicenário
    social_cost.py             # Tempo × custo social
    report_generator.py        # Relatórios HTML/MD
    map_utils.py               # Helpers de mapa (folium)
    data_update.py             # Atualização de dados + metadata
    validation.py              # Validações genéricas
  docs/
    metodologia.md
    limitacoes.md
    modelo_matematico.md
```

---

## Fluxo do usuário

1. Criar ou abrir estudo
2. Informar dados básicos do município
3. Delimitar área e criar/importar zonas
4. Inserir produção e atração de viagens
5. Balancear vetores
6. Gerar matriz O-D (gravitacional)
7. Definir repartição modal
8. Alocar viagens na rede
9. Cadastrar interferências
10. Rodar cenário-base
11. Criar cenários (futuro / interdição / melhoria)
12. Salvar até 5 cenários favoritos
13. Comparar cenários
14. Gerar relatórios

---

## Entradas de dados aceitas pelo ALIME

O ALIME é **agnóstico ao formato e ao nome dos arquivos**. Não há lista pré-definida de arquivos obrigatórios nem nomenclatura fixa — basta que os dados importados contenham os campos compatíveis descritos abaixo.

Tipos de entrada suportados:

- **Cadastro manual de zonas** (formulário dentro do app);
- **CSV ou Excel** com zonas;
- **CSV ou Excel** com vetores de produção e atração;
- **CSV ou Excel** com matriz de impedância;
- **GeoJSON / KML / KMZ** para geometrias de zonas (centroides e/ou polígonos);
- **Centroides** das zonas via latitude/longitude;
- **Rede viária** importada ou gerada automaticamente quando há centroides;
- **Cenários salvos** previamente em **JSON** (biblioteca de cenários).

### Campos compatíveis

Para a tabela de **zonas**, o ALIME procura colunas com nomes equivalentes a:

- `zone_id`
- `zone_name`
- `zone_type`
- `population`
- `jobs`
- `schools`
- `commerce`
- `industry`
- `production`
- `attraction`
- `generation_weight`
- `attraction_weight`
- `centroid_lat`
- `centroid_lon`
- `notes`

Para **vetores de produção e atração** (etapa 3), basta um arquivo com:

- `zone_id`
- `production`
- `attraction`

O ALIME tem detector automático de colunas: aliases comuns como `zona`, `id`, `produção`, `atração`, `origem`, `destino`, `lat`, `lon` são reconhecidos. Se a heurística falhar, o usuário mapeia manualmente as colunas na própria interface.

Para a **matriz de impedância** (etapa 4), basta uma matriz **quadrada** cuja primeira coluna e cabeçalho contenham os `zone_id` na **mesma ordem** das zonas cadastradas no estudo.

---

## Matriz de impedância

A etapa 4 (Distribuição) **exige uma matriz de impedância válida** para rodar o modelo gravitacional. Sem ela, o ALIME **não gera** matriz O-D — exibe um aviso e bloqueia o cálculo.

A matriz de impedância representa o **custo generalizado** de viajar entre cada par de zonas. Pode estar expressa em:

- **tempo** (minutos) — opção mais comum;
- **distância** (km);
- **custo generalizado** (combinação de tempo + atraso por interferências + outros pesos).

### Como o ALIME obtém a matriz

Dentro da etapa 4, o usuário escolhe **uma** das três fontes genéricas:

- **Calcular dos centroides** — usa Haversine sobre `centroid_lat` / `centroid_lon` e converte em tempo via velocidade média configurável. Exige centroides válidos em **todas** as zonas; se algum estiver faltando, o ALIME lista os `zone_id` problemáticos e bloqueia o cálculo.
- **Importar CSV/Excel** — upload de matriz quadrada com índices iguais aos `zone_id` cadastrados.
- **Editar manualmente** — editor visual de uma matriz n×n diretamente na interface.

### Validação automática

Antes de aceitar uma matriz, o ALIME verifica:

- shape quadrado e compatível com o número de zonas;
- ausência de **NaN** e **infinitos**;
- valores **≥ 0**;
- tratamento da diagonal (zeros são substituídos por um custo mínimo configurável para evitar singularidades no atrito);
- denominador gravitacional `Σ_j(A_j · f(c_ij)) > 0` para cada origem.

Se algo falha, o usuário vê uma mensagem amigável (em vermelho) no lugar dos cards — **nunca um `nan` silencioso**.

---

## Modelo matemático (resumido)

O ALIME combina **balanceamento de vetores**, **distribuição gravitacional**, **repartição modal**, **atribuição all-or-nothing**, **modelagem de interferências urbanas** e **avaliação exploratória de custo social**. Detalhes completos em [`docs/modelo_matematico.md`](docs/modelo_matematico.md).

**Notação adotada:**

| Símbolo | Significado |
|---|---|
| `P_i` | produção de viagens da zona `i` (origem) |
| `A_j` | atração de viagens da zona `j` (destino) |
| `A'_j` | atração **balanceada** após ajuste para que `Σ A'_j = Σ P_i` |
| `c_ij` | custo generalizado entre `i` e `j` (tempo + atraso) |
| `f(c_ij)` | função de atrito (impedância) |
| `T_ij` | viagens estimadas entre `i` e `j` (matriz O-D) |
| `T_ij^m` | viagens entre `i` e `j` no modo `m` |
| `s_m` | participação do modo `m` na repartição |
| `x_a` | fluxo alocado na aresta `a` da rede |
| `δ_{a,ij}` | 1 se a aresta `a` está no caminho mínimo `(i,j)`, 0 caso contrário |

### 1. Balanceamento de vetores

Quando `Σ P_i ≠ Σ A_j`, o ALIME aplica um fator de ajuste para garantir conservação de viagens. Estratégia padrão (ajustar atrações):

```
F_A = Σ P_i / Σ A_j
A'_j = A_j · F_A
```

Outras opções: ajustar produções (`P'_i = P_i · F_P`), normalizar ambos para um total alvo, ou manter sem balancear (com aviso).

### 2. Distribuição gravitacional (normalizada por origem)

A matriz O-D é gerada por modelo gravitacional usando as atrações **já balanceadas**:

```
T_ij = P_i · ( A'_j · f(c_ij) )  /  Σ_j ( A'_j · f(c_ij) )
```

Por construção, `Σ_j T_ij = P_i` (cada linha respeita a produção). As colunas podem divergir ligeiramente de `A'_j`; o erro de fechamento é calculado e exibido.

### 3. Custo generalizado e atrito

```
c_ij = tempo_movimento + atraso_interferencias
f(c_ij) = 1 / max(c_ij, c_min)^β       (atrito potência)
f(c_ij) = exp(-β · max(c_ij, c_min))   (atrito exponencial)
```

O usuário escolhe a função de atrito, o coeficiente `β` e o custo mínimo `c_min` (piso que evita divisão por zero).

### 4. Repartição modal

```
T_ij^m = T_ij · s_m,   com   Σ_m s_m = 1
```

Os percentuais são normalizados automaticamente se a soma diferir de 100%.

### 5. Atribuição all-or-nothing

Toda a demanda de cada par `(i,j)` é alocada no **caminho mínimo** da rede:

```
x_a = Σ_ij T_ij · δ_{a,ij}
```

Implementação via `networkx.shortest_path` sobre uma rede k-vizinhos (ou rede importada, ou OSMnx quando disponível).

### 6. Interferências urbanas

Para passagens em nível **ferroviárias**, o tempo de impacto por evento é:

```
tempo_ocupacao  = (L_trem / v_trem) · 60
tempo_bloqueio  = tempo_ocupacao · fator_operacional
tempo_total     = tempo_bloqueio + tempo_dissipacao_fila
```

Outras interferências (**alagamento, semáforo, ponte estreita, gargalo, obra, acidente**) são parametrizadas por `blocks_per_day`, `average_blockage_min` e `queue_dissipation_min`.

### 7. Custo social do atraso

A conversão monetária do atraso segue uma cadeia simples:

- **Pessoas afetadas:** quantas pessoas são impactadas em média a cada evento de interferência (fluxo de veículos × ocupação média);
- **Horas perdidas:** quantas horas-pessoa de atraso por dia o conjunto de interferências gera;
- **Valor do tempo (R$/h):** quanto cada hora-pessoa perdida representa em valor monetário (configurável pelo usuário);
- **Custo diário:** horas perdidas × valor do tempo;
- **Custo anual:** custo diário × número de dias úteis no ano;
- **Benefício anual de uma intervenção:** diferença entre o custo anual do cenário-base e o custo anual do cenário com a obra proposta (`custo_base − custo_cenario`).

Em forma de fórmula:

```
pessoas_afetadas = fluxo_afetado · ocupacao_media
horas_perdidas   = pessoas_afetadas · tempo_atraso / 60
custo_diario     = horas_perdidas · valor_tempo_hora
custo_anual      = custo_diario · dias_uteis
beneficio_anual  = custo_base - custo_cenario
payback          = custo_obra / beneficio_anual
B/C              = beneficio_anual / custo_obra
```

Valores default: ocupação 1,4 pessoas/veículo, valor do tempo R$ 18/h, 252 dias úteis/ano — todos ajustáveis pelo usuário.

---

## Limitações

- **Modelo exploratório:** o ALIME é uma ferramenta de apoio à decisão preliminar, não um modelo definitivo.
- **Dependência da qualidade dos dados de entrada:** zonas mal definidas, vetores P/A imprecisos ou matriz de impedância grosseira produzem resultados igualmente grosseiros.
- **Modelo gravitacional simplificado:** sem calibração formal a partir de pesquisa O-D real; coeficiente β é informado manualmente.
- **Atribuição all-or-nothing:** toda a demanda de cada par O-D é alocada no caminho mínimo, sem multi-caminho.
- **Sem congestionamento calibrado:** não há função capacidade-velocidade (BPR) nem equilíbrio de Wardrop; tempos não dependem do fluxo alocado.
- **Repartição modal global** na versão atual (modo básico); modo por zona/par O-D fica para versões futuras.
- **Custos sociais baseados em valores genéricos** do tempo, não em pesquisa local.
- **Não substitui** EVTEA, contagem volumétrica, pesquisa O-D domiciliar, microssimulação ou projeto executivo.

Ver [`docs/limitacoes.md`](docs/limitacoes.md) para a lista completa.

---

## Evoluções futuras

- **Integração com OSMnx** para baixar rede viária real de qualquer município brasileiro;
- **Alocação avançada** com equilíbrio incremental (BPR) ou stochastic user equilibrium;
- **Calibração com contagens reais** (volumes por hora-pico) para ajustar β e validar fluxos;
- **Modelos de repartição modal mais robustos** (logit binomial/multinomial em vez de coeficientes fixos);
- **Modo avançado de repartição modal** por zona ou por par O-D;
- **Integração com bases oficiais** (IBGE, IPEA, DNIT, ANTT, SNV) para preenchimento automático;
- **Exportação GIS** (shapefile, GeoJSON, GPKG) das zonas, rede e fluxos alocados;
- **Integração futura com SUMO e AequilibraE** para microssimulação encadeada;
- **Exportação PDF nativa** (atualmente HTML + Markdown);
- **Calibração automática de β** via método dos mínimos quadrados sobre matriz de referência.

---

## Autoria

Desenvolvido por **Luiz Araujo** — [luiz.junior@ime.eb.br](mailto:luiz.junior@ime.eb.br)
IME — Instituto Militar de Engenharia
