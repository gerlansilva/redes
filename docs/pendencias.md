# Pendências do Redes

Estado em 10/11/2026. Este documento substitui o diagnóstico anterior: os
itens que descreviam lacunas de análise, interface, relatório e testes foram
fechados e constam aqui apenas como registro. O que resta está na seção
**O que falta**, no fim.

## Resumo

O núcleo de análise, a interface web e os relatórios estão completos para as
seis unidades, quatro matrizes, seis algoritmos e cinco similaridades. A
paridade com o fork Java cobre 540 comparações, sem divergência. A suíte tem
74 testes, todos passando.

Não há pendência funcional conhecida. O que falta é distribuição: instalador
desktop e integração contínua. Os dois dependem de decisões externas ao código
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
   com referências ABNT) e LaTeX, ambos com diagrama estratégico por mapeador
   e medida.
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
17. **Testes** — 74 testes: esquema e contadores, grade, opções de análise,
    similaridade, medidas e índices, agrupamentos, mapeadores, carregadores,
    conversão de referências, figuras e API da interface.

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

1. **Empacotamento desktop.** Só existe a interface web local (`scimatpy web`).
   Falta o empacotamento Tauri, o instalador e a assinatura para uso por não
   técnicos. Bloqueio: o diretório não é um repositório git, não há
   identidade de assinatura definida e é preciso escolher a plataforma alvo
   (macOS, Windows ou ambos).
2. **Integração contínua.** Não há pipeline. A suíte roda à mão
   (`python3 -m unittest discover -s tests -t .`) e a paridade depende de
   `/tmp/demo/celii` com o fork Java compilado. Bloqueio: sem repositório,
   não há onde executar o fluxo.
3. **Publicação do pacote (opcional).** `pyproject.toml` já descreve o pacote
   e o ponto de entrada `scimatpy`; falta decidir se ele será publicado em
   índice interno ou no PyPI, com as credenciais correspondentes.

## Verificação

```bash
cd ~/Documents/scimatpy
python3 -m unittest discover -s tests -t . -q     # 73 testes, OK
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
