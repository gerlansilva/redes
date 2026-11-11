# Pendências do Redes

Estado em 11/11/2026. Este documento substitui o diagnóstico anterior: os
itens que descreviam lacunas de análise, interface, relatório e testes foram
fechados e constam aqui apenas como registro. O que resta está na seção
**O que falta**, no fim.

## Resumo

O núcleo de análise, a interface web e os relatórios estão completos para as
sete unidades (com Países e Instituições), quatro matrizes, seis algoritmos e
cinco similaridades. A
paridade com o fork Java cobre 540 comparações, sem divergência. A suíte tem
mais de 560 casos de teste.

As análises novas (qualidade, rótulos, linha do tempo, pontos de virada,
densidade, dendrograma, IES e Sankey) estão entregues, com arestas conhecidas
listadas em **O que falta**. Fora isso, falta distribuição: um repositório onde a
integração contínua, já escrita, possa rodar. É decisão externa ao código, não
implementação de análise. O produto é só a interface web no navegador do
computador (sem aplicativo desktop).

## O que foi fechado

1. **Esquema `.redes`** — `redes/schema.py` traz o DDL completo, versão
   `v1_03`: 31 tabelas, 87 índices e 34 gatilhos, incluindo afiliações,
   categorias de assunto e as tabelas da unidade Países. Um projeto importado
   com 489 afiliações abre no verificador Java do fork e devolve os mesmos
   documentos e agrupamentos.
2. **Grade de análises** — 162 linhas, todas distintas. O eixo final foi
   separado em `MAPEADOR` (seis mapeadores) e `MEDIDA` (oito índices), e o TSV
   mostra `eixo`, `mapeador`, `medida` e `valor_medida`. São 540 comparações
   com a referência Java (135 no corpus completo e 405 nos três períodos),
   com 0 divergências; as 27 linhas da unidade Países não têm referência.
3. **Mapeadores, corte e palavras** — `kcore` e `acoplamento` entraram em
   `MAPEADORES`; o corte é repassado aos quatro algoritmos hierárquicos;
   `Configuracao.palavras` escolhe as origens (`autor`, `fonte`,
   `adicionada`, vazio = todas).
4. **Índices** — calculados por agrupamento e por mapeador, visíveis na aba
   **Índices**, no detalhe do grupo e nas exportações.
5. **Relatórios** — HTML (índice, período e agrupamento, simples e estendido,
   com referências ABNT), com rede completa, rede de agrupamentos, quadro de
   métricas com a rede de cada agrupamento e diagrama estratégico por mapeador
   e medida. O relatório em LaTeX foi retirado: só HTML.
6. **Mapas longitudinais** — evolução, sobreposição e Pajek na aba **Comparar
   períodos**.
7. **Edição da base** — períodos, grupos (renomear, separar, juntar),
   substituição global e desfazer com dez cópias de segurança.
8. **Importação** — BibTeX, OpenAlex, CSV genérico, WoS (texto ISI), Scopus
   (CSV) e a unidade Países a partir das afiliações. O formato é reconhecido
   pelo conteúdo, não pela extensão.
9. **Exportações** — grupos XML, Pajek, GraphML, TSV de índices e de
   documentos, além do download das figuras.
10. **Rede de países** — renderizador padrão das demais redes (halos), aba
    **Países**, mapa interativo na matriz de coocorrência e diagrama
    estratégico com rótulos próprios ("Núcleos de cooperação", "Grupos
    isolados", "Periféricos", "Cooperação dispersa").
11. **Diagrama estratégico interativo** — canvas no padrão da figura
    estática: quadrantes, esferas translúcidas com contorno e selo numerado,
    eixos apenas com títulos (sem números nem malha, só a cruz tracejada em
    0,5), quadrantes pintando toda a área do gráfico e nome curto de cada
    quadrante no canto com menos esferas (omitido quando o zoom estreita a
    área), dica com centralidade e
    densidade e clique para abrir o agrupamento. O zoom e o arraste valem só
    dentro da área do gráfico; a moldura e os eixos ficam fixos, e o domínio
    tem folga para nenhuma esfera cruzar a borda. A **Legenda** numérica é
    adaptável ao volume: abre sozinha até 24 agrupamentos e, acima disso, fica
    recolhida, com colunas e rolagem vertical; os selos no gráfico priorizam os
    maiores e são limitados nos recortes com centenas de grupos. O botão
    **SVG** exporta a versão estática e os rótulos dos quadrantes acompanham a
    unidade (temas ou países).
12. **Análises nomeadas** — o seletor **Análise** reúne presets com nome e
    descrição: Estrutura conceitual (palavras), Colaboração entre autores,
    Colaboração entre países, Cocitação de autores, Cocitação de referências,
    Frentes de pesquisa (acoplamento de documentos por referências) e
    Periódicos citados. As análises ficam num menu lateral agrupado por
    propósito (conceitual, intelectual, social e fontes), no estilo do
    bibliometrix; clicar aplica o preset e executa a prévia. O cartão mostra a
    unidade e a matriz fixas e esconde esses campos nas análises nomeadas.
    Ajustar qualquer campo passa para **Personalizada** e marca a prévia como
    desatualizada. As abas de resultado exibem um bloco por vez e se adaptam a
    cada análise: a aba **Rede** muda de nome, **Países** só aparece na
    colaboração entre países e **Documentos** só quando os nós são documentos.
    A barra lateral ficou enxuta: menu de análises agrupado e atalhos Base,
    Ajuda e Sobre; saíram "Fluxo do projeto" e "Execuções", e o cabeçalho
    redundante foi unido ao cartão de parâmetros, que agora traz o nome da
    análise como título. A linha de resumo numérico duplicada também saiu.
    Ao abrir um projeto, a tela cai na **Visão geral** do corpus (período,
    documentos, recortes e unidades, mais os quatro cartões de resumo); a
    configuração de parâmetros e as abas de resultado só aparecem quando uma
    análise é escolhida no menu.
13. **Rede de agrupamentos** — nova aba em todas as análises: cada tema é um
    nó, com tamanho proporcional aos itens, cor pelo quadrante do diagrama
    estratégico e aresta pela associação entre temas (índice de equivalência
    de Callon, c(A,B)² / c(A)·c(B)). É a "cluster network" do SciMAT, até
    então só presente no relatório.
14. **Mapa temporal condicionado** — a aba **Comparar períodos** (mapa de
    evolução e de sobreposição) só aparece quando o projeto tem dois períodos
    ou mais, em vez de quebrar com um período único.
15. **Parâmetros recolhidos** — o cartão mostra só **Unidade**, **Matriz** e
    frequência mínima; similaridade, algoritmo, mapeadores, palavras, corte e
    tamanho da rede ficam em **Parâmetros avançados**, recolhidos.
16. **Marca e figuras** — as figuras geradas dizem "Redes ·"; as 20 figuras
    antigas do vault Obsidian que traziam "Bibliomapa/SciMAT" no rodapé foram
    atualizadas para "Redes".
17. **Testes** — esquema e contadores, grade, opções de análise,
    similaridade, medidas e índices, agrupamentos, mapeadores, carregadores,
    conversão de referências, figuras e API da interface; depois, também as
    análises novas (itens 18 a 26).
18. **Qualidade do mapa** — `qualidade.py`: modularidade Q ponderada, Q do
    Louvain como régua (razão), silhueta por agrupamento (grupos com menos de 3
    itens ficam fora; acima de 2000 itens agrupados é dispensada) e selo OK,
    Atenção, Ruim ou Indefinido. Desde 11/11/2026 o selo depende só da estrutura
    (itens em agrupamentos de 5 ou mais: Ruim abaixo de 50%, OK a partir de 80%;
    rede fragmentada; em coautoria nunca passa de Atenção); Q, razão e silhueta
    viram avisos de nitidez. Limiares e justificativa em `docs/qualidade.md`.
19. **Rótulos por tema** — `rotulos.py`: termos que distinguem cada
    agrupamento dos demais documentos do período (LLR de Dunning sobre título,
    palavras-chave e bigramas do resumo). Só para palavras-chave e referências;
    autores, países e IES mantêm o nome do líder. Menos de 5 documentos ou
    cobertura acima de 70%: sem rótulo; 5 a 9: indicativo.
20. **Fluxo Autor – País – IES (Sankey)** — `fluxos.py` e `viz/sankey.py`, com
    ligação autor–instituição exata, inferida ou ausente, e queda para País →
    IES quando não há ligação. Nenhum vínculo é inventado.
21. **Dendrograma** — `dendrograma.py` e aba no modo avançado: corte, cofenética,
    ARI/NMI contra a rede, 60 itens mais frequentes (`docs/dendrograma.md`).
22. **Linha do tempo e pontos de virada** — `linha_do_tempo.py`, `pivos.py`:
    faixa por agrupamento no corpus completo, rajadas de Kleinberg, pontos de
    virada (intermediação no decil superior e vizinhos em 2 ou mais
    agrupamentos) e sigma para quem tem rajada (`docs/linha-do-tempo.md`).
23. **Mapa de densidade** — `viz/densidade.py`: layout tipo VOS e núcleos
    gaussianos ponderados pela frequência, em SVG próprio (`docs/densidade.md`).
24. **Unidade Instituições (IES)** — `ies.py`: união de variantes só quando
    inequívoca, tabela "variantes unidas" com o motivo, e componente mínimo de
    3 instituições (`docs/ies.md`).
25. **Parâmetros e método por análise nos relatórios** — `metodo.py`: cada
    análise traz parâmetros adotados, algoritmo em linguagem simples,
    indicadores por período, e as seções de qualidade, rótulos, linha do tempo,
    densidade, pontos de virada e IES, com as constantes lidas do código.
26. **Termos em maiúsculas do SciMAT** — `redes/texto.py` (`termo_legivel`) é
    a única função de apresentação: `STATISTICAL-REASONING` sai como
    "Statistical reasoning", `E-LEARNING` como "E-learning", e as siglas da lista
    (`SPSS`, `PISA`, `ICME`, `TIMSS`, configurável por `registra_siglas` ou
    `REDES_SIGLAS`) ficam em maiúsculas. Só palavras-chave em co-ocorrência;
    caixa mista, autores, países, IES, periódicos e referências não mudam, e o
    dado guardado, os ids e as chaves de agrupamento também não. Vale para a
    interface (inclusive a busca da Base, que acha o texto exibido e o
    original), as figuras, as tabelas, os dois relatórios, as exportações
    (Pajek, GraphML, TSV de índices) e os rótulos automáticos.

## Decisões que fecharam pendências

- **Referências sem agrupamento semântico.** A normalização trata apenas
  caixa, acento, pontuação e numeração; não há fusão por semelhança de título
  ou de autoria. É uma decisão de método, não uma lacuna.
- **Frequência mínima padrão 1.** Nenhum item é descartado por padrão, para
  que corpora pequenos não fiquem vazios; o seletor sobe a partir de 1.
- **Mapa restrito à coocorrência.** No acoplamento os nós são documentos, e o
  cartão avisa em vez de desenhar um mapa sem sentido.
- **Muitos vínculos entre grupos.** Acima de 600 ligações entre agrupamentos a
  interface recebe o traço agregado em vez das ligações individuais; o desenho
  continua legível e o payload cai de 13 MB para 3,9 MB no pior caso.

## Limites conhecidos

Não são pendências, mas convém registrar:

- `References` com frequência 1 no corpus SERJ tem 9.744 nós, 292.911 arestas
  e 677 grupos; a análise leva cerca de 20 s e o resultado é completo.
- Acima de 600 nós a interface avisa e sugere o filtro "Nós" ou aumentar a
  frequência; acima de 400 agrupamentos o layout usa a ordenação circular.
- A prévia é síncrona e a grade roda uma análise por vez, de propósito, para
  não competir por memória.
- Caixa dos termos: a sigla só fica em maiúsculas se estiver na lista de
  `texto.py` (não há detecção pelo corpus); termo curto fora dela sai como
  "Pisa". Nomes próprios em caixa alta e com espaço saem como "South africa",
  de propósito (regra simples, sem lista de países). Títulos de documentos em
  caixa alta (rede de acoplamento), o XML de grupos (formato de troca da base)
  e a aba de revisão de grafias mostram o texto guardado.

## Estresse no SERJ (11/11/2026)

Corrigido: mapeador `acoplamento` só com a matriz `BasicCoupling` (400 claro
na API e opção oculta na tela); `_divide` do Louvain sem recalcular
componentes a cada aresta; ligação hierárquica com valores de pares
guardados e monte ordenado; `tamanho_maximo` limitado ao grau máximo;
cancelamento da grade dentro do pipeline e do agrupamento (`cancelado()`);
`corte` e demais números exigem valor finito; abortos de conexão do cliente
não imprimem traceback. Todas as versões rápidas têm teste de equivalência
contra a formulação literal (`tests/test_estresse_correcoes.py`).

Registrado, não feito (ganho pequeno frente ao risco):

- **Frequência automática do relatório completo** (`_escolhe_frequencia`):
  tenta 3, 2 e 1 e descarta os resultados das tentativas que não servem.
  Guardar resultados entre seções não ajuda, porque cada seção tem unidade e
  matriz próprias. O ganho barato (reaproveitar o resultado da frequência
  escolhida em `gera_html` e no mapa longitudinal, que antes refaziam a
  análise duas vezes) já foi aplicado.
- **Figuras repetidas no relatório completo** — feito em 11/11/2026, veja
  "Desempenho do relatório completo" abaixo.

## Desempenho do relatório completo (11/11/2026)

Medido em `serj_auto.redes` (8 análises, 4 períodos), máquina de 2 núcleos e
compartilhada. Perfil (cProfile): o tempo era o desenho das figuras (layouts de
mola do halo, 60%), os pontos de virada (intermediação), o mapa de densidade, os
rótulos por tema e a análise em si; o arquivo único ainda regenerava a pasta de
páginas (1.255 arquivos) só para descartá-la.

| Relatório completo (arquivo único) | Antes | Depois |
|---|---|---|
| serj_auto | 23,4 s | 7,3 s |
| serj | 31,6 s | 9,8 s |
| novo142 | 20,1 s | 6,4 s |
| arquivos gravados (serj_auto) | 1.370 | 1 |
| pasta de páginas (serj_auto) | 15,3 s | 11,9 s |

O que mudou, sem alterar a saída (HTML idêntico ao do processo único sem cache em
serj, serj_auto, novo142 e eecera59, e a pasta de páginas idêntica, arquivo por
arquivo, em serj_auto; `tests/test_desempenho_relatorio.py`):

- arquivo único sem a pasta de páginas;
- cache por conteúdo (`cache_figuras.py`): chave = impressão do resultado do
  período (configuração, rede, agrupamentos, nomes) + título, rótulos e estado do
  projeto; vale só dentro de uma geração de relatório (`escopo`), é esvaziado se
  uma constante de cálculo mudar, e cobre halo, linha do tempo, densidade, pontos
  de virada, rótulos, qualidade e rajadas;
- processos trabalhadores (`paralelo.py`, `trabalhador.py`): cada análise vai para
  um processo, que devolve o que desenhou; falhou, o principal refaz;
- intermediação de Brandes com listas em vez de dicionários (1,6 vez mais rápida,
  mesmo resultado bit a bit), `sem_acentos` com cache, cache de corpora de rótulos
  de 4 para 12 períodos, `norm` do relaxamento dos nós soltos sem o invólucro.

Fica: o layout de mola do NetworkX (cerca de um quarto do tempo restante) é
cálculo de NumPy sobre matrizes pequenas; uma versão própria foi medida e só
ganhou 10%, então não entrou. Com um só núcleo o ganho vem do cache e da pasta
suprimida (13 a 14 s no serj_auto).

## Estresse completo no SERJ (11/11/2026)

`scripts`: corpus completo de `serj.redes` (280 documentos), cada análise de ponta
a ponta, sem o filtro de frequência do relatório:

(Selo conforme a regra de 11/11/2026, itens em agrupamentos de 5 ou mais.)

| Unidade (freq. 1) | Nós | Agrupamentos | Selo | Qualidade | Rótulos | Pontos de virada | Linha do tempo | Densidade | Halo | Pico de memória |
|---|---|---|---|---|---|---|---|---|---|---|
| Palavras | 676 | 132 | Atenção | 0,03 s | 0,11 s | 1,0 s | 0,06 s | 0,5 s | 4,3 s | 72 MB |
| Referências | 9.715 | 672 | OK | 0,9 s (silhueta dispensada) | 0,12 s | pulado (limite de 800 nós, avisa) | 2,9 s | 0,7 s | 13,2 s | 265 MB |
| Instituições | 334 | 42 | Ruim | 0,01 s | 0,00 s | 0,01 s | 0,01 s | 0,6 s | 2,7 s | 69 MB |

Nenhuma etapa trava nem estoura memória; a mais cara é o desenho do halo da rede
de referências sem filtro (13 s), que o relatório completo evita ao escolher
frequência mínima 3.

## O que falta

Fechado em 11/11/2026 (constava aqui): selo quase sempre "Atenção" (limiar de
coesão 0,10 para 0,05, com a distribuição antes e depois em `docs/qualidade.md`),
estresse completo no SERJ (acima), figuras repetidas e tempo do relatório completo
(acima), integração contínua (`.github/workflows/tests.yml`: unittest em Linux e
macOS, Playwright opcional, instalação limpa; falta só um repositório onde rodar)
e empacotamento Python (`pyproject.toml` com o comando `redes`, conferido num
ambiente virtual limpo, instruções no README).

**Selo "Ruim" decidido em 11/11/2026** (substitui a pergunta sobre "3 ou mais
famílias de alerta"): o selo agora depende só da estrutura do mapa, e Q, razão e
silhueta viram avisos de nitidez. Justificativa: em 43 mapas de bases reais vistos
um a um (halo e diagrama estratégico), o selo antigo concordou com o julgamento
visual em 4 (9 dos 21 mapas bons saíam Ruim; nenhum dos 12 inutilizáveis saía Ruim),
as regras por 2, 3 ou 4 famílias em 6, 5 e 7, e a regra nova ("Ruim" com menos de
50% dos itens em agrupamentos de 5 ou mais; OK a partir de 80%) em 39. Os limiares
vieram de uma amostra e foram conferidos em outra, julgada às cegas. Distribuição
nos 323 períodos com selo definido, antes e depois: OK 14% → 45%, Atenção 66% → 23%,
Ruim 20% → 32% (78% dos Ruins são Autores e Instituições, redes de pares e trios).
Tabelas, método e limites em `docs/qualidade.md`. Um só avaliador julgou os mapas; se
o usuário discordar do critério ("Ruim = menos da metade dos itens em grupos de 5 ou
mais"), basta mexer em `GRUPO_GRANDE` e nos limiares 50/80 de `qualidade.py`.

Depende de decisão do usuário:

1. **Duplo mapa simplificado.** Só se o usuário quiser uma versão simplificada do
   mapa ao lado do completo. *Pergunta: quer essa versão? Se sim, simplificada
   como (só os maiores agrupamentos, sem arestas fracas, ou outra regra)?*
2. ~~Rótulos por tema fora de palavras-chave e referências.~~ Decidido: autores,
   países e IES ficam com o nome do líder do agrupamento.
3. ~~Publicação do pacote.~~ Decidido: uso local. O pacote já se instala com
   `pip install .`; PyPI e índice interno não serão usados por enquanto.
4. **Paridade na integração contínua.** `scripts/paridade*.py` e a grade exigem o
   fork Java compilado em `/tmp/demo/celii`. *Pergunta: o fork pode ir para o
   repositório (ou ser publicado como artefato) para a paridade rodar na
   integração contínua?*

## Verificação

```bash
cd ~/Documents/redes
python3 -m unittest discover -s tests -t . -q     # mais de 400 casos, OK
python3 scripts/grade.py completo                 # 162 análises, 135 comparações, 0 divergências
python3 scripts/grade.py periodos                 # 162 análises, 405 comparações, 0 divergências
```

Esquema conferido em um projeto recém-importado:

```python
versao: v1_03
tabelas: 31
indices: 87
gatilhos: 34
afiliacoes: 489
```
