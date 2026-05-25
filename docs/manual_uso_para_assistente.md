# Manual de uso do ALIME — para assistente de IA

> **Como usar este documento.** Cole este arquivo inteiro como **contexto inicial** num chat com ChatGPT/Claude/etc. Depois faça perguntas como *"estou na etapa 4 e apareceu nan, o que faço?"* ou *"qual β devo usar para uma cidade de 12 mil habitantes?"*. O assistente terá tudo o que precisa para te orientar.

---

## 1. Identidade do ALIME

- **Nome:** ALIME — Análise Local Integrada de Mobilidade e Engenharia
- **Tipo:** simulador exploratório de planejamento preliminar de mobilidade urbana
- **Aplicação prioritária:** municípios de pequeno porte (até ~20.000 habitantes), bairros, corredores, pontos críticos, áreas alagáveis. Áreas maiores são aceitas com aviso metodológico.
- **Tecnologia:** Python + Streamlit + Pandas/NumPy + Plotly + NetworkX + Folium (OSMnx opcional)
- **Genérico:** o ALIME **não está preso** a nenhuma cidade. Não há dados fixos de Matias Barbosa, Juiz de Fora, Tavares ou qualquer recorte real embutido.
- **Aviso metodológico permanente:** os resultados **não substituem** levantamento de campo, contagem volumétrica, pesquisa O-D domiciliar, microssimulação, EVTEA, orçamento executivo ou projeto de engenharia. Sempre citar este aviso em recomendações de obra.
- **Autoria:** Luiz Araujo — luiz.junior@ime.eb.br — IME (Instituto Militar de Engenharia)
- **Versão atual:** v0.3.0 — maio/2026

---

## 2. Modelo das 4 etapas (resumo matemático)

| Etapa | Pergunta | Saída principal |
|---|---|---|
| 1. Geração       | *Vou ou não vou?* | Vetores P_i (produção) e A_j (atração) por zona |
| 2. Distribuição  | *Para onde vou?*  | Matriz T_ij origem-destino |
| 3. Repartição    | *Como vou?*       | Matriz T_ij por modo |
| 4. Atribuição    | *Por onde vou?*   | Fluxos x_a por aresta da rede |

### Notação adotada

| Símbolo | Significado |
|---|---|
| `P_i` | produção da zona i (origem) — **original** |
| `A_j` | atração da zona j (destino) — **original** |
| `A'_j` | atração **balanceada** após ajuste para que ΣA'_j = ΣP_i |
| `c_ij` | custo generalizado entre i e j (geralmente tempo + atraso, em minutos) |
| `f(c_ij)` | função de atrito |
| `T_ij` | viagens entre i e j |
| `T_ij^m` | viagens entre i e j no modo m |
| `s_m` | participação do modo m (Σs_m = 1) |
| `x_a` | fluxo alocado na aresta a |
| `δ_{a,ij}` | 1 se a está no caminho mínimo entre i e j, 0 caso contrário |
| `β` | coeficiente de atrito (decay) |
| `c_min` | piso de custo (evita divisão por zero) |

### Fórmulas-chave

```
Balanceamento (ajustar atrações):
    F_A = ΣP_i / ΣA_j
    A'_j = A_j · F_A

Atrito potência:    f(c) = 1 / max(c, c_min)^β
Atrito exponencial: f(c) = exp(-β · max(c, c_min))

Gravitacional (normalizado por origem):
    T_ij = P_i · (A'_j · f(c_ij)) / Σ_j(A'_j · f(c_ij))
    Garante: Σ_j T_ij = P_i

Repartição modal:
    T_ij^m = T_ij · s_m,  com Σ_m s_m = 1

All-or-nothing:
    x_a = Σ_ij T_ij · δ_{a,ij}

Interferência ferroviária:
    tempo_ocupacao  = (L_trem / v_trem) · 60       [min]
    tempo_bloqueio  = tempo_ocupacao · fator_op    [min]
    tempo_total     = tempo_bloqueio + fila_min    [min]

Custo social:
    pessoas_afetadas = fluxo · ocupacao_media
    horas_perdidas   = pessoas_afetadas · atraso / 60
    custo_diario     = horas_perdidas · valor_tempo_hora
    custo_anual      = custo_diario · dias_uteis
    beneficio_anual  = custo_base - custo_cenario
    payback          = custo_obra / beneficio_anual
    B/C              = beneficio_anual / custo_obra
```

---

## 3. As 13 etapas do app (sidebar)

| # | Página              | O que o usuário faz                                       | Etapa marcada como concluída quando…                          |
|---|---------------------|-----------------------------------------------------------|---------------------------------------------------------------|
| 1 | Área de Estudo      | Define recorte (município/ponto/arquivo/polígono/corredor)| Tem `name` + `area_name OR municipality OR center_lat/lon` + `base_year` |
| 2 | Zonas               | Cadastra/importa zonas                                    | ≥ 2 zonas e clicou em "💾 Salvar alterações"                  |
| 3 | Geração             | Vetores P/A + balanceamento                               | Clicou em "⚙ Aplicar balanceamento"                           |
| 4 | Distribuição        | Matriz de impedância + matriz O-D                         | Clicou em "🧮 Calcular matriz O-D" sem erro                   |
| 5 | Repartição Modal    | % por modo                                                | Clicou em "⚙ Aplicar repartição"                              |
| 6 | Atribuição          | Construção de rede + all-or-nothing                       | Clicou em "🧮 Construir rede e alocar"                        |
| 7 | Interferências      | Cadastra barreiras/gargalos                               | Adicionou interferência OU clicou "Confirmar: não há"          |
| 8 | Cenários            | Gera cenário-base e alternativas                          | Clicou em "✅ Gerar cenário-base"                              |
| 9 | Biblioteca          | Salva até 5 favoritos                                     | Salvou 1 favorito OU clicou "Não desejo salvar"               |
| 10| Comparação          | Tabela + rankings + gráficos                              | Tem base + favorito OU clicou "Não realizar comparação"        |
| 11| Custo Social        | Ajusta valor do tempo, ocupação, dias                     | Visitou e configurou                                          |
| 12| Relatórios          | Gera HTML/Markdown                                        | Visualizou markdown gerado                                    |
| 13| Atualização         | Metadata, exemplo, reset, checklist                       | Opcional                                                      |

---

## 4. Como iniciar um estudo (5 modos)

Na tela inicial, o usuário escolhe **uma** das opções:

| Modo | Use quando… | Campos necessários                                          |
|---|---|---|
| 🏙 Município / localidade | Cidade pequena, bairro, distrito          | `area_name` + UF/país (opcionais)                          |
| 📍 Ponto no mapa         | Cruzamento crítico, ponte, acesso         | `center_lat`, `center_lon`                                  |
| 📁 Arquivo geográfico    | Já tem KML/KMZ/GeoJSON/SHP                | Upload do arquivo                                           |
| ✏ Polígono desenhado     | Recorte arbitrário                        | WKT ou pares `lat,lon` colados                              |
| ↔ Corredor / eixo        | Trecho rodoviário, ferroviário, fluvial   | 2 pontos + buffer (km)                                     |

Em todos os 5 modos, depois define **raio de coleta** (km) e **raio de análise** (km). Regra: análise ≤ coleta.

---

## 5. Área de coleta × Área de análise

- **Coleta:** raio em torno do ponto/área usado para baixar dados de entorno (rede, POIs, barreiras). Pode ser maior que o estudo.
- **Análise:** recorte efetivo do modelo (zonas, P/A, O-D, atribuição).

Intervalos sugeridos:

| Recorte               | Coleta sugerida |
|-----------------------|-----------------|
| Bairro / local        | 1–5 km          |
| Cidade pequena        | 5–20 km         |
| Município + entorno   | 20–50 km        |
| Ligação intermunicipal| 50–150 km       |
| Corredor regional     | 150–500 km      |
| Macroanálise          | > 500 km (modo Avançado, aviso de performance) |

---

## 6. Níveis de qualidade dos dados

| Nível | Dados mínimos | Saída |
|---|---|---|
| **Dados mínimos**        | área + ≥2 zonas + pesos manuais             | matriz O-D preliminar, linhas de desejo |
| **Dados intermediários** | + matriz de impedância e/ou interferências  | matriz balanceada, atribuição simplificada, cenário-base |
| **Dados calibrados**     | + pesquisa O-D real + contagens             | comparação confiável, relatório técnico preliminar |

O ALIME mostra o nível na etapa 1. Sempre ser honesto sobre o nível ao recomendar decisões.

---

## 7. Etapa 3 — Geração (regras importantes)

- O motor SEMPRE usa `production_original` e `attraction_original` como entrada.
- O balanceamento escreve em `production_balanced` e `attraction_balanced`.
- **Idempotente:** clicar "Aplicar" 1 ou 100 vezes dá o mesmo resultado (o fator é sempre calculado dos originais).
- Tabela mostra 4 colunas P/A lado a lado + método + fator.
- Card "Conferência da atração balanceada" tem: `zone_id | attraction_original | attraction_balanced | delta_attraction`.

Métodos disponíveis:

1. **Ajustar atrações:** `F = ΣP_orig / ΣA_orig` → `A'_j = A_j · F`, P inalterado.
2. **Ajustar produções:** `F = ΣA_orig / ΣP_orig` → `P'_i = P_i · F`, A inalterado.
3. **Normalizar para total alvo T:** P e A ambos reescalados para somar T.
4. **Manter sem balancear:** apenas avisa que matriz O-D pode não fechar.

---

## 8. Etapa 4 — Distribuição (regras importantes)

A etapa exige **matriz de impedância válida**. Sem ela, o sistema **bloqueia** o cálculo e exibe aviso (não gera NaN).

### Três fontes de impedância

| Fonte | Como obter |
|---|---|
| 🌍 **Calcular dos centroides** | Exige `centroid_lat`/`centroid_lon` válidos em todas as zonas. Usa Haversine + velocidade média. |
| 📥 **Importar CSV/Excel** | Matriz quadrada com índices = `zone_id` na mesma ordem. |
| ✏ **Editar manualmente** | Editor visual n×n dentro da interface. |

### Validações automáticas

Antes de aceitar:
- shape quadrado e compatível com nº de zonas
- sem NaN, sem Inf
- valores ≥ 0
- diagonal (zeros viram `c_min` no atrito)
- denominador gravitacional `Σ_j(A_j · f) > 0` por origem

Se algo falha, o usuário vê erro **descritivo** (vermelho), nunca "nan" silencioso.

### Parâmetros da gravidade

- `β` (atrito) — default 2.0. Maior β → atrito mais forte → viagens locais. Menor β → viagens mais longas.
- `função` — potência ou exponencial. Potência é mais comum.
- `c_min` (custo mínimo) — default 1.0 min. Piso para evitar 1/0^β.

**Regra prática:** β entre 1.0 e 2.5 para cidades pequenas; 2.0 a 3.0 para análises locais (bairro). Se a O-D ficar muito "lisa" (todos pares parecidos), aumente β. Se ficar muito "concentrada" (1-2 pares dominam), reduza β.

---

## 9. Etapa 5 — Repartição modal

Sugestões por porte de cidade (apenas referência — sempre validar com dados locais):

| Modo | Cidade pequena (<20k) | Cidade média (20-100k) | Bairro denso |
|---|---|---|---|
| Veículo leve | 50–60% | 55–65% | 30–45% |
| Veículo pesado | 3–8% | 4–10% | 3–8% |
| Transporte coletivo | 5–15% | 15–30% | 10–25% |
| A pé | 15–30% | 8–15% | 25–45% |
| Bicicleta | 3–10% | 2–8% | 5–15% |
| Outros | 2–5% | 2–5% | 2–5% |

Sempre normalizar para somar 100%. O ALIME normaliza automaticamente se não fechar.

---

## 10. Etapa 6 — Atribuição

- Método: **all-or-nothing** sobre rede k-vizinhos (k=3 default).
- Toda demanda do par (i,j) vai no caminho mínimo.
- **Não considera congestionamento** nem capacidade — limitação importante.
- OSMnx é opcional; se ausente, usa rede k-vizinhos geométrica.

---

## 11. Etapa 7 — Interferências

Tipos suportados (lista não-exaustiva):
- passagem em nível ferroviária / rodoviária crítica
- ponte estreita / viaduto crítico
- via alagada / queda de barreira
- semáforo / gargalo / funil
- obra / acidente / bloqueio temporário
- bueiro / galeria / área de risco

Campos genéricos: `name, type, geometry, affected_zones, affected_modes, blocks_per_day, average_blockage_min, queue_dissipation_min, capacity_reduction_percent, risk_level, periodicity, lat, lon, notes`.

Campos extras para ferrovia: `train_speed_kmh, train_length_km, operational_factor, trains_per_day`. O sistema calcula `tempo_bloqueio` e `tempo_total` automaticamente.

Periodicidades: `permanente | recorrente | temporária | sazonal | eventual | por período`.

---

## 12. Etapa 8 — Cenários (4 tipos)

| Tipo | O que muda no modelo |
|---|---|
| **Base** | Snapshot da situação atual completa |
| **Futuro** | `P_i(t+n) = P_i · (1+g_i)^n`, `A_j(t+n) = A_j · (1+h_j)^n`, recalcula tudo |
| **Interdição** | Remove arestas (total) ou multiplica tempo por fator (parcial) |
| **Melhoria** | Adiciona arestas novas, reduz/zera interferências, reatribui |

Cada cenário guarda snapshot: zonas, vetores balanceados, O-D, modal, impedância, rede, fluxos, interferências, custo social, custo da obra, intervenções.

---

## 13. Biblioteca + Comparação

- Até **5 cenários favoritos** + 1 cenário-base.
- Comparação compara base contra cada favorito.
- Indicadores comparativos: tempo médio, distância média, atraso total, custo social anual, benefício anual, custo da obra, payback, **B/C**.
- 4 rankings: melhor tempo / maior benefício / melhor B/C / mais crítico.

**Como interpretar B/C:**
- B/C < 1 → benefício menor que custo → não recomendado por essa análise preliminar
- B/C = 1 → empata
- B/C entre 1 e 2 → benefício moderado, vale estudo mais profundo
- B/C > 2 → benefício forte, prioridade alta
- B/C = ∞ → não havia custo de obra cadastrado (preencher)

**Lembrar sempre:** B/C do ALIME é **preliminar**. Não substitui EVTEA.

---

## 14. Custo social — defaults e ajustes

- Ocupação média: **1,4 pessoas/veículo** (default; ajuste por estudo local)
- Valor do tempo: **R$ 18/h** (default; cidade pequena pode usar R$ 12–15; cidade grande R$ 20–30)
- Dias úteis/ano: **252** (default; alguns estudos usam 260)

---

## 15. Modo Básico vs Modo Avançado

| Aspecto | Básico | Avançado |
|---|---|---|
| Trilha de progresso | Mostra normalmente | Mostra normalmente |
| Pular etapa | Bloqueia (botão "Ir para etapa pendente") | Permite com aviso forte |
| Avisos | Os mesmos | Os mesmos |
| Raio > 500 km | Aviso | Aviso |
| População > 20k | Aviso | Aviso |

Trocar de modo: aba **1. Área de Estudo** → radio "Modo de uso".

---

## 16. Tipos de status (trilha)

| Status | Significado | Cor |
|---|---|---|
| `not_started` | Etapa nunca foi acessada / sem dados | cinza |
| `in_progress` | Etapa tem dados parciais | âmbar |
| `completed`   | Etapa concluída com sucesso | verde |
| `error`       | Etapa com erro grave | vermelho |
| `blocked`     | Etapa bloqueada por dependência | vermelho |
| `current`     | Etapa em que o usuário está agora | anel teal |

---

## 17. Glossário rápido

- **Centroide:** ponto representativo de uma zona (lat/lon).
- **Custo generalizado:** combinação de tempo + atraso (+ pesos opcionais), usado como impedância.
- **Linha de desejo:** linha reta entre origem e destino com espessura ∝ viagens.
- **Heatmap O-D:** matriz colorida mostrando intensidade T_ij.
- **k-vizinhos:** rede simplificada onde cada centroide conecta aos k mais próximos.
- **All-or-nothing:** toda demanda de (i,j) no caminho mínimo único.
- **Furness:** ajuste duplo iterativo (não implementado nesta versão — gravitacional simples normalizado por origem).
- **Fator de balanceamento:** F = ΣP / ΣA quando se ajusta atrações.

---

## 18. Erros comuns e como resolver

| Sintoma                                    | Causa provável                                              | O que fazer                                                |
|--------------------------------------------|-------------------------------------------------------------|------------------------------------------------------------|
| Cards mostram "—" em vez de número         | Etapa anterior não foi concluída                            | Voltar e completar                                         |
| "Centroides ausentes nas zonas: Z01, Z02…" | Centroide vazio nas zonas listadas                          | Etapa 2 → preencher `centroid_lat/lon` OU importar matriz  |
| "Nenhuma matriz de impedância carregada"   | Não escolheu fonte na aba "1. Matriz de Impedância"         | Escolher centroides, importar ou editar                    |
| "ΣP = 0 — produções vazias"                | Tabela de zonas sem coluna `production` preenchida          | Etapa 3 → preencher P e A, salvar                          |
| "Σ por destino diverge muito de A"         | Gravitacional não fecha colunas — normal                    | Sem ação obrigatória; aplicar Furness em versão futura     |
| Tabela "balanced" igual a "original"       | Variável Streamlit ficou stale (bug v0.2)                   | Já corrigido em v0.3; clicar de novo                       |
| "Etapa anterior não concluída" (Básico)    | Tentando pular etapa                                        | Concluir a anterior OU trocar para Avançado                |
| "Comparação vazia"                         | Sem favoritos salvos                                        | Biblioteca → ⭐ Salvar cenário                              |
| Mapa em branco                             | Folium/streamlit-folium não instalado                       | `pip install folium streamlit-folium`                      |
| B/C = ∞                                    | Custo da obra ficou 0 ao criar cenário de melhoria          | Editar cenário e preencher `custo_estimado`                |

---

## 19. Recomendações para o assistente IA

Quando responder ao usuário do ALIME:

1. **Sempre lembrar do aviso metodológico** ao recomendar decisões de obra/investimento. O ALIME é preliminar, não definitivo.
2. **Nunca inventar valores** numéricos do estudo do usuário. Se ele não disse o β, peça.
3. **Aprender o porte** da área antes de sugerir parâmetros (β, valor do tempo, ocupação).
4. **Citar o caminho exato no app** (aba/botão) ao orientar — ex.: "vá em **4. Distribuição → aba 1. Matriz de Impedância → 📥 Importar CSV**".
5. **Diferenciar Básico/Avançado** ao explicar bloqueios.
6. **Validar o nível de qualidade dos dados** antes de comparar cenários ou citar B/C.
7. **Lembrar de balancear** antes da distribuição, e que o motor já garante isso usando `*_balanced` automaticamente.
8. **Para problemas de NaN**, o primeiro suspeito é matriz de impedância inválida (sem centroides) na etapa 4.
9. **Não recomendar nenhuma cidade específica** como referência — o ALIME é genérico.
10. **Ao gerar texto para relatório**, manter linguagem técnica mas acessível e citar limitações na seção própria.

---

## 20. Decision tree resumida

```
Usuário abriu o ALIME pela primeira vez?
├─ SIM → Tela inicial, escolher um dos 5 modos de início
│         (ou carregar exemplo genérico se for só explorar)
└─ NÃO → Continuar de onde parou (sidebar mostra a etapa atual)

Usuário não sabe o que fazer?
├─ Olhar a trilha de progresso (chip verde = ok, âmbar = a fazer)
├─ Card azul "Próximo passo: X" diz exatamente o que clicar
└─ Aba "Atualização" tem o checklist completo do estudo

Apareceu erro vermelho?
├─ Ler a mensagem inteira — o ALIME sempre diz o que faltou
├─ Erro típico aponta o `zone_id` ou parâmetro problemático
└─ Voltar à etapa anterior e corrigir

Comparação mostra B/C inesperado?
├─ Conferir se o cenário tem `cost_estimate` > 0
├─ Conferir o valor do tempo em "Custo Social"
└─ Lembrar: B/C do ALIME é preliminar, não substitui EVTEA
```

---

## 21. Quick-reference: ordem de cliques para um estudo do zero

```
Tela Inicial
  → escolher modo (ex.: 🏙 Município / localidade)

1. Área de Estudo
  → preencher: nome estudo, nome área, UF, população, ano-base
  → escolher modo Básico/Avançado
  → "💾 Salvar área de estudo"
  → "➡ Ir para Zonas"

2. Zonas
  → cadastrar manual OU importar CSV/GeoJSON
  → garantir ≥ 2 zonas com zone_id, zone_name, lat/lon (se for usar centroides)
  → "💾 Salvar alterações"

3. Geração
  → preencher production e attraction nas zonas
  → "💾 Salvar vetores"
  → escolher método de balanceamento
  → "⚙ Aplicar balanceamento"

4. Distribuição
  → aba "1. Matriz de Impedância" → escolher fonte (centroides/importar/editar)
  → aba "2. Modelo Gravitacional" → ajustar β e função
  → "🧮 Calcular matriz O-D"

5. Repartição Modal
  → ajustar % por modo (Σ = 1)
  → "⚙ Aplicar repartição"

6. Atribuição
  → "🧮 Construir rede e alocar"

7. Interferências
  → cadastrar barreiras OU confirmar "não há"

8. Cenários
  → "✅ Gerar cenário-base"
  → aba Futuro / Interdição / Melhoria conforme caso

Biblioteca
  → "⭐ Salvar cenário para comparação"

Comparação
  → ler tabela + rankings + gráficos

Custo Social
  → ajustar parâmetros monetários

Relatórios
  → aba "Consolidado" → ⬇ Baixar HTML
```

---

## 22. Repositório e links úteis

- **Repositório:** https://github.com/luizaraujoengkil-ux/ALIME
- **Stack:** Python 3.12 · Streamlit · NumPy · Pandas · NetworkX · Folium · Plotly
- **Documentação interna:**
  - `docs/metodologia.md`
  - `docs/limitacoes.md`
  - `docs/modelo_matematico.md`
  - `docs/manual_uso_para_assistente.md` (este arquivo)

---

*Fim do manual.*
*Em caso de dúvida, sempre lembrar: o ALIME é exploratório, preliminar e não substitui levantamento de campo, EVTEA, microssimulação nem projeto executivo.*
