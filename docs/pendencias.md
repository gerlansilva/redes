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
mais de 400 casos de teste.

As análises novas (qualidade, rótulos, linha do tempo, pontos de virada,
densidade, dendrograma, IES e Sankey) estão entregues, com arestas conhecidas
listadas em **O que falta**. Fora isso, falta distribuição: instalador desktop
e integração contínua. Os dois dependem de decisões externas ao código
(repositório, plataforma alvo e assinatura), não de implementação de análise.

## O que foi fechado

1. **Esquema `.redes`** — `scimatpy/schema.py` traz o DDL completo, versão
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
    análises novas (itens 18 a 25).
18. **Qualidade do mapa** — `qualidade.py`: modularidade Q ponderada, Q do
    Louvain como régua (razão), silhueta por agrupamento (grupos com menos de 3
    itens ficam fora; acima de 2000 itens agrupados é dispensada) e selo OK,
    Atenção, Ruim ou Indefinido. Em coautoria o selo nunca passa de Atenção.
    Limiares em `docs/qualidade.md`.
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

## O que falta

Arestas das análises novas:

1. **Selo quase sempre "Atenção".** Com os limiares atuais, a maioria das redes
   reais cai em Atenção; o selo informa pouco. Falta decidir se os limiares
   mudam ou se o selo ganha outra escala. Hoje o texto já avisa que isso não
   invalida o mapa.
2. **Termos em maiúsculas do SciMAT perdem a caixa.** Os termos que vêm em
   maiúsculas do importador do SciMAT não mantêm a caixa original nos rótulos
   novos. Falta preservar a grafia de siglas e nomes próprios.
3. **Estresse completo no corpus SERJ.** Qualidade, rótulos, linha do tempo,
   densidade, pontos de virada e IES não foram rodados de ponta a ponta no
   SERJ completo (References com 9.744 nós); falta medir tempo e memória.
4. **Duplo mapa simplificado.** Só se o usuário quiser: uma versão simplificada
   do mapa ao lado do mapa completo. Sem demanda, fica fora.
5. **Rótulos por tema fora de palavras-chave e referências.** Autores, países
   e IES seguem com o nome do líder, de propósito; só entra se houver um método
   que faça sentido para essas unidades.

Distribuição:

6. **Empacotamento desktop.** Só existe a interface web local (`scimatpy web`).
   Falta o empacotamento Tauri, o instalador e a assinatura para uso por não
   técnicos. Bloqueio: o diretório não é um repositório git, não há
   identidade de assinatura definida e é preciso escolher a plataforma alvo
   (macOS, Windows ou ambos).
7. **Integração contínua.** Não há pipeline. A suíte roda à mão
   (`python3 -m unittest discover -s tests -t .`) e a paridade depende de
   `/tmp/demo/celii` com o fork Java compilado. Bloqueio: sem repositório,
   não há onde executar o fluxo.
8. **Publicação do pacote (opcional).** `pyproject.toml` já descreve o pacote
   e o ponto de entrada `scimatpy`; falta decidir se ele será publicado em
   índice interno ou no PyPI, com as credenciais correspondentes.

## Verificação

```bash
cd ~/Documents/scimatpy
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
