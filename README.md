# ALIME — Análise Local Integrada de Mobilidade e Engenharia

Simulador exploratório de apoio ao planejamento preliminar da mobilidade urbana em municípios de pequeno porte (até ~20 mil habitantes).

> **Aviso metodológico:** O ALIME é uma ferramenta exploratória de apoio ao planejamento preliminar. Os resultados **não substituem** levantamento de campo, contagem volumétrica, pesquisa O-D domiciliar, microssimulação, EVTEA, orçamento executivo ou projeto de engenharia.

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
- Comparação de até 5 cenários favoritos;
- Relatórios individuais e consolidados;
- Avaliação preliminar de tempo, atraso, custo social e benefício/custo.

---

## Instalação

```powershell
cd alime_simulador
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **OSMnx é opcional.** Se a instalação falhar (algumas dependências GIS no Windows são chatas), o ALIME continua funcionando com rede simplificada.

---

## Execução

```powershell
streamlit run app.py
```

---

## Estrutura de pastas

```
alime_simulador/
  app.py                       # Entrada principal Streamlit
  README.md
  requirements.txt
  assets/
    styles.css                 # CSS do tema escuro/amarelo
    logo_placeholder.png       # Placeholder textual
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
    network_assignment.py      # Tela 6 - alocação na rede
    interferences.py           # Tela 7 - interferências
    scenarios.py               # Tela 8 - cenários
    scenario_library.py        # Biblioteca de cenários (até 5)
    comparison.py              # Comparação multicenário
    social_cost.py             # Tempo x custo social
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

## Modelo matemático (resumido)

Ver `docs/modelo_matematico.md` para detalhes. Em resumo:

- **Balanceamento:** `A'_j = A_j * (ΣP / ΣA)` (ou simétrico)
- **Gravitacional:** `T_ij = P_i * (A_j * f(c_ij)) / Σ_j(A_j * f(c_ij))`
- **Atrito:** `f(c) = 1/c^β` (potência) ou `exp(-β·c)` (exponencial)
- **Custo:** `c_ij = tempo_movimento + atraso_interferencias`
- **Repartição modal:** `T_ij^m = T_ij · s_m`
- **All-or-nothing:** `x_a = Σ_ij T_ij · δ_a,ij` (caminho mínimo)
- **Ferrovia:** `t_bloq = (L_trem / v_trem) · 60 · fator_operacional`
- **Custo social:** `C = pessoas · atraso/60 · valor_hora · dias_ano`

---

## Limitações

- Modelo gravitacional simplificado, sem calibração formal com pesquisa O-D
- Atribuição all-or-nothing (não considera congestionamento)
- Custos sociais baseados em valores genéricos do tempo
- Não substitui EVTEA, contagem volumétrica nem microssimulação

Ver `docs/limitacoes.md`.

---

## Próximos passos

- Calibração com dados reais quando disponíveis
- Equilíbrio incremental para atribuição
- Modelos logit para repartição modal
- Integração com bases oficiais (DNIT, IBGE, ANTT)
- Exportação PDF nativa
