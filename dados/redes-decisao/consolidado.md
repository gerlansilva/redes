# Organização da rede e das ferramentas — decisão consolidada

Data: 20/11/2026. Base: quatro pareceres independentes e a tela real do projeto
`celii` (Referências, frequência 2: 9 grupos, 115 nós, 1.066 arestas).

| Lente | Relatório | O que trouxe |
|---|---|---|
| Interface | `rede-interface.md` | hierarquia invertida, filtro escondido, estado "todos ocultos", bug do reenquadramento |
| Visual | `rede-visual.md` | 75% de área morta, selos do tamanho dos nós, tipografia de projeção |
| Tarefas | `rede-tarefas.md` | foco que atenua em vez de esconder; recorte declarado; exportar o que se vê |
| Benchmark | `rede-benchmark.md` | palco + painel de ajustes; status do VOSviewer; seleção do SciMAT |

## Decisão

**A figura manda; os grupos ficam numa faixa logo abaixo do canvas, não numa
coluna lateral fixa.**

A tela passa a ter quatro zonas, nesta ordem:

1. **Cabeçalho**: título, recorte (`Referências · 115 de 1.139 itens · freq. mín. 2`)
   e duas ações: `Reenquadrar` e `Figura completa (SVG)`.
2. **Estado vivo**: `9 de 9 grupos · 115 de 115 nós · 1.066 arestas · 2 fora dos grupos`.
3. **Barra enxuta**: `Rótulos`, `Nós exibidos` e `Ajustes` (arestas e halos).
4. **Palco e faixa**: canvas de 520 px; abaixo, a faixa de agrupamentos em ordem
   1–9, com dois gestos separados.

### Por que não a coluna lateral

Três pareceres pediam painel lateral (esquerda ou direita). Ele foi recusado como
padrão:

- a 240 px, o canvas perde ~25% da largura em 1.280 px; o problema medido é
  sobra de área, não falta de coluna;
- na projeção, o participante precisa do mapa inteiro e da âncora espacial; uma
  coluna desloca o olhar para o painel do pesquisador;
- com 9 grupos, a faixa cabe inteira abaixo do canvas (3 linhas de 4 colunas em
  963 px), sem rolagem e sem tirar largura da figura.

A coluna lateral continua registrada como evolução para acervos com mais de 16
grupos, quando a faixa passaria a rolar demais. Nesta rodada, acima de 16 grupos
a faixa ganha rolagem interna limitada a 220 px.

### Dois gestos, não um

O conflito entre "filtrar" e "isolar" foi resolvido separando os verbos:

- **Ponto colorido** = isolar o grupo. É gesto de análise; o grupo continua no
  mapa com nós, halo, selo, rótulos e arestas internas, e somem apenas as linhas
  que o ligam aos outros grupos.
- **Nome do grupo** = destacar. É gesto de condução; o grupo fica em cor cheia,
  o resto recua para 16%, as conexões externas continuam visíveis e o mapa não
  é redesenhado. Um segundo clique, ou `Todo o mapa`, volta ao todo.
- **Seta ›** = abrir os detalhes, sem trocar o clique principal de contexto.

A regra veio do uso: esconder o grupo apagava justamente o que a conversa
precisava mostrar. Isolar mantém a âncora espacial e tira só a conexão — o
equivalente a olhar um agrupamento por dentro sem perder onde ele está.

## O que foi aplicado

### Recorte e estado

- `metaHalo` passa a declarar unidade, itens que entraram e frequência mínima;
  o `title` completa período e co-ocorrência.
- Linha de estado viva (`role="status"`, `aria-live="polite"`) com grupos, nós,
  arestas, itens fora dos grupos e, em destaque, o grupo focado com o número de
  conexões.
- Isolamento: com grupos isolados, a linha de estado passa a dizer
  `9 grupos · 115 de 115 nós · 1.066 arestas · 2 fora dos grupos · 1 de 9 grupos
  isolados`; nenhum nó, halo ou aresta interna desaparece.

### Ferramentas

- A barra de seis controles virou duas escolhas (`Rótulos`, `Nós exibidos`) e um
  disclosure `Ajustes` com `Arestas` e `Halos`.
- `Nós exibidos` mostra a contagem (`todos (115)`) e os cortes por grau com nome
  completo (`50 mais ligados`, `200 mais ligados`).
- `Reenquadrar` e `Figura completa (SVG)` subiram para o cabeçalho. O botão de
  exportação agora diz que a figura é a completa, com todos os grupos.
- O reset de zoom duplicado (`⤢`) foi removido; `+`, `−` e `Reenquadrar` bastam.
- `Reenquadrar` calcula o conjunto visível antes de medir a área e sempre enquadra
  só o que está na tela, inclusive depois de mudar `Nós exibidos`.
- Isolar ou religar grupos não reenquadra o mapa, porque nada sai da figura;
  destacar um grupo também não mexe no enquadramento.

### Leitura e acessibilidade

- Tipografia do bloco: título 15 px, status 12 px, legenda 12,5 px, controles
  11,5–12 px, rótulos de nó 12 px, selos 12 px com raio 12.
- Contraste: textos secundários do bloco passam de `--tinta-suave` (3,06:1) para
  `--tinta-fraca` (4,76:1).
- Alvos: ponto com 27 px efetivos, linha de 38 px, botões de 32 px, zoom 36 px.
- Grupo isolado: fundo neutro, nome em tom secundário, anel do ponto tracejado,
  `aria-pressed="false"`; o grupo inteiro continua no mapa.
- Grupo em destaque: fundo lavanda, nome em negrito, `aria-pressed="true"`; o
  canvas mostra só o campeão do grupo focado para não cobrir o desenho.
- Legenda em ordem 1–9; acima de 16 grupos, rolagem interna com teto de 220 px.

## O que fica para depois

Por ordem de retorno:

1. **Exportar o estado visto** (PNG do canvas ou SVG filtrado). Hoje `Figura
   completa (SVG)` é honesta, mas não entrega o recorte da tela.
2. **Legenda lateral automática acima de 16 grupos**, com busca, mantendo a faixa
   como padrão.
3. **Seleção persistente com painel de detalhes** que encolhe o canvas em vez de
   cobri-lo; inclui conexões do grupo com os demais e os 5 itens principais.
4. **Teclado completo**: lista com roving tabindex, `Espaço` isola, `Enter`
   destaca, `Esc` limpa; canvas focável com setas.
5. **Modo apresentação**: sem abas, qualidade e estatísticas técnicas; fonte
   maior; legenda em duas linhas.
6. **Distinguir os números dos pontos de virada dos números dos grupos** no
   canvas; hoje os dois usam algarismos e podem ser confundidos.

Não vale: coluna lateral fixa por padrão, modo escuro, animação de força,
edição manual de layout, árvore de filtros, assistente em etapas.

## Critérios de aceite

1. Com 9 grupos, o estado mostra `9 grupos · 115 de 115 nós · 1.066 arestas
   · 2 fora dos grupos`.
2. Isolar um grupo mantém `115 de 115` nós, as arestas internas e o halo;
   some só a linha que o liga aos outros grupos, e o estado passa a
   `1 de 9 grupos isolados`.
3. Isolar todos tira as linhas entre grupos e as ligações com nós fora dos
   grupos, mantém os 9 halos e oferece `religar todos`. Nenhum nó desaparece.
4. Destacar um grupo custa um clique; voltar ao todo custa um clique; o resto do
   mapa permanece visível.
5. Um grupo isolado continua legível na faixa (fundo neutro + anel tracejado), e
   o mesmo ponto o religa.
6. `Reenquadrar` enquadra exatamente o visível, inclusive após mudar `Nós
   exibidos`.
7. Nenhum texto essencial do bloco abaixo de 11,5 px; contraste ≥4,5:1.
8. `Figura completa (SVG)` não promete o estado filtrado.

## Verificação

- Capturas: `nova-rede-topo.png`, `nova-rede-foco2.png`, `isolado-final.png`,
  `isolados-todos.png`.
- Contagem instrumental no canvas (grupo 1 isolado, 9 grupos/115 nós): zero
  linhas cruzadas tocando o grupo isolado, zero linhas dele para nós fora dos
  grupos, 43 arestas internas preservadas e 481 linhas entre os demais grupos.
- Testes: 749 passam, 53 pulados; permanece só a falha anterior de
  `tests/test_v3_05_icones.py::test_menu_com_rotulo_curto_e_nome_completo_no_titulo`.

## Segunda rodada (20/11/2026)

O que saiu do backlog e entrou no programa:

- **Exportar o estado visto**: `Imagem da tela (PNG)` baixa o canvas como está
  (recorte de nós, grupos isolados, foco) e uma faixa com projeto, unidade,
  período, frequência, contagem e data. `Figura completa (SVG)` continua sendo a
  rede inteira.
- **Sessão por projeto**: `redes.sessao.<caminho>` guarda os parâmetros da última
  análise (unidade, matriz, período, frequência, co-ocorrência, corte, tamanho,
  mapeadores) e a vista da rede (rótulos, nós exibidos, arestas, halos, grupos
  isolados e foco). Reabrir o projeto restaura os campos, roda a prévia e
  reaplica a vista; nenhuma configuração é refeita à mão.
- **Teclado**: o canvas é focável; setas andam para o nó mais alinhado na
  direção, `Espaço` isola o grupo do nó, `Enter` destaca, `Esc` limpa, e `1–9` /
  `0` isolam e religam grupos fora de campos de texto.
- **Pontos de virada**: o número saiu do canvas (ficou o anel); o cabeçalho ganhou
  `N pontos de virada`, que abre a tabela, e a dica do nó mostra a posição.
- **Rótulo de grupo**: quando o nome vem do item central (referências e autores
  citados) e não há rótulo temático, o painel de detalhes diz isso e aponta a
  aba Base para renomear.
- **Nomenclatura**: `Reenquadrar` virou `Enquadrar`; o menu de coautoria passou a
  se chamar `Coautoria entre autores`.
- **Teste de ícones**: a checagem passou a aceitar rótulo curto que é categoria
  do nome completo (`Autores` em `Cocitação de autores`); a suíte fica verde.

## Terceira rodada (20/11/2026)

- **Painel docado**: a partir de 1280 px o detalhe do agrupamento abre ao lado
  do mapa. O cartão da rede reserva 380 px à direita; abas, parâmetros e o resto
  da página não encolhem. As métricas passam a 2×2 para caber na coluna.
- **Modo condução**: `Modo condução` esconde menu, topo, parâmetros, abas,
  estatísticas e o bloco de exportação; o cartão da rede ocupa a tela, a legenda
  ganha corpo 14 px e o canvas recebe o foco. `Esc` sai do mapa e, sem seleção,
  do modo. `Sair do modo condução` fica fixo no canto.
- **Filtro na legenda**: acima de 16 grupos aparecem `Filtrar grupos` (nome
  curto e original, sem acento e sem caixa) e um seletor de tamanho
  (`todos`, `5+`, `10+`, `15+ nós`). O filtro é só da lista: o mapa inteiro
  continua; a contagem mostra `N de M grupos`.
- **Cabeçalho da rede**: ações quebram linha em vez de espremer o texto;
  `Enquadrar` e os demais botões não partem no meio da palavra.
- **Troca de aba**: sair da aba Rede fecha o detalhe docado, para o painel não
  ficar preso dentro de um bloco oculto.
- **Linhas entre halos**: `Linhas` (`mostrar`/`ocultar`) fica na barra, ao lado
  de `Rótulos` e `Nós exibidos`, e esconde as ligações externas aos halos
  (entre agrupamentos e para nós fora deles). As arestas internas continuam; para esconder todas, o
  seletor `Arestas` segue em `Ajustes`. O atalho `L` alterna as linhas entre
  halos, e o estado é salvo na sessão.

## Corpus completo antes dos períodos (21/11/2026)

- **`Todos os períodos` no seletor**: com mais de um período, a análise abre no
  corpus inteiro, somando os documentos de todos os períodos. Cada período
  continua no mesmo seletor, para a leitura recortada. Projetos com um período
  só não ganham a opção.
- **Núcleo**: `ProjetoRedes.dataset(unidade, None)` monta o corpus completo,
  inclusive documentos sem data; `executa_periodo` aceita `periodo_id=None`.
  A linha do tempo e o relatório, que já rodavam no corpus, passam a usar o
  mesmo caminho.
- **API**: `periodo: "todos"` devolve o período virtual `Todos os períodos`
  (id nulo); a lista de documentos e a exportação TSV também passam a incluir
  o corpus inteiro. `periodo` ausente continua valendo o primeiro período.
- **Testes**: dataset do corpus soma períodos e a API reconhece o período
  virtual.

## Análises à vista e por bloco (21/11/2026)

- **Nada escondido**: todas as abas de resultado aparecem com o nome, nos dois
  modos. O `Modo avançado` continua controlando os parâmetros e a grade, mas
  não esconde mais `Dendrograma`, `Densidade`, `Duplo mapa` nem `Similitude`.
- **Fim do filtro da personalizada**: a análise personalizada deixou de
  remover `Densidade`, `Duplo mapa` e `Similitude`; essas visões valem para
  qualquer configuração.
- **Blocos na barra**: os rótulos `Visão geral`, `Rede`, `Tabelas`, `Métodos`
  e `Comparar` separam as abas. A barra quebra linha em vez de cortar nomes.
- **Sem “Detalhe por período”**: a evolução temática continua sendo a visão
  inicial quando há dois períodos ou mais, mas as demais abas ficam à vista,
  sem o antigo grupo recolhível.

## Menu lateral por tarefa (21/11/2026)

- **Grupos em linguagem direta**: `Estrutura conceitual`, `Estrutura
  intelectual`, `Estrutura social` e `Fontes` viraram `Temas`, `Citações`,
  `Colaboração` e `Periódicos`. As chaves das análises não mudaram; só a
  organização visível.
- **Três blocos, não quatro**: `Periódicos` passou a ser um item dentro de
  `Citações`, junto de autores citados, obras citadas e frentes — a cocitação
  de periódicos é uma análise de citação, e o bloco de um item só repetia o
  nome do próprio item. Ficaram `Temas` (1 item), `Citações` (4) e
  `Colaboração` (3).
- **Nenhum rótulo repetido**: o cabeçalho do bloco é a categoria e o item nomeia
  o objeto analisado. Por isso `Temas > Temas` virou `Temas > Palavras-chave`
  (`Coocorrência entre termos`), e `Periódicos > Periódicos` desapareceu. A
  regra vale também para a segunda linha: nenhuma descrição repete o nome do
  item (`Autores` + `Quem é citado junto`, não `Autores citados juntos`).
  Dois testes travam essas repetições.
- **Ordem de leitura**: `Visão geral` → `Temas` → `Citações` →
  `Colaboração`. É a sequência conceitual, intelectual e social usada no
  relatório.
- **Descrição em cada item**: abaixo do nome curto, uma linha diz o que a
  análise faz sem repetir o próprio nome (`Coocorrência entre termos`, `Quem é
  citado junto`, `Revistas citadas juntas` etc.). O nome completo continua no
  `title` e no `aria-label`. As descrições foram medidas na largura real do
  menu (151 px) e nenhuma é cortada.
- **Responsivo**: abaixo de 980 px a barra fica horizontal e as descrições
  somem; com o menu recolhido, ficam só os ícones e os títulos de bloco somem.
  A largura e o comportamento anterior do menu foram preservados.

Continua em aberto: revisão de toque em telas < 600 px e, na legenda com muitos
grupos, uma coluna lateral fixa em vez de rolagem.

## Barra de resultados sem repetição (21/11/2026)

- **Bloco `Rede` virou `Mapas`**: o rótulo ficava colado na aba `Rede de
  coautoria` e parecia uma segunda análise de rede. Com `Mapas`, a leitura é
  `MAPAS → Rede de coautoria · Diagrama estratégico · Ligações entre grupos`.
- **`Rede de agrupamentos` virou `Ligações entre grupos` e `Agrupamentos` virou
  `Grupos`**: os dois nomes antigos repetiam "rede"/"agrupamentos" entre um mapa
  e uma tabela. Agora o mapa e a tabela têm nomes distintos e o bloco `Tabelas`
  diz que ali são tabelas.
- **Evolução por unidade**: a aba, o título, a legenda, o vazio, as colunas da
  tabela e a nota deixaram de falar em "tema" quando a análise é de autores,
  referências, periódicos, países ou IES. `SUBSTANTIVO_GRUPO` fornece o nome
  (`grupo de autores`, `grupo de referências` etc.) e a aba passa a se chamar
  `Evolução dos grupos`. Ao trocar de unidade, a figura antiga é limpa antes do
  novo cálculo, para não ficar com legenda de uma análise e conteúdo de outra.
- **Título da análise igual ao menu**: `Estrutura conceitual` virou
  `Palavras-chave em coocorrência`, o mesmo nome que aparece à esquerda. Os
  relatórios mantêm a seção `Estrutura conceitual`.

## Cada análise só mostra as abas que lhe servem (21/11/2026)

- **Lista explícita por análise**: `CONFIG_ABAS` deixou de completar toda
  análise com as mesmas visões (`dendrograma`, `linhatempo`, `densidade`,
  `duplomapa`, `similitude`). Cada unidade declara o que calcula.
- **Só onde se aplica**: `Similitude` (resumos) fica em palavras-chave;
  `Duplo mapa` (áreas das revistas) em periódicos; `Documentos` em
  palavras-chave e frentes; `Países` na unidade países; `Variantes unidas` na
  unidade instituições; `Evolução` em palavras-chave, autores citados e
  referências.
- **Comum a todas**: `Resumo`, a rede da unidade, `Diagrama estratégico`,
  `Ligações entre grupos`, `Grupos`, `Índices`, `Dendrograma`, `Linha do
  tempo`, `Densidade` e `Comparar períodos` (este último só com 2+ períodos).
- **Análise personalizada** usa a lista da unidade escolhida (ou de frentes,
  quando a matriz é acoplamento), em vez de mostrar tudo.
- **Troca de análise limpa a tela**: `escolherAnalise` chama
  `limparResultado()`, que zera resumo, rede, diagrama, ligações e evolução.
  Antes, o resultado da análise anterior ficava visível durante o cálculo e
  podia ser confundido com a nova análise.
- **Testes**: `test_cada_analise_so_oferece_abas_que_se_aplicam` fixa a
  aplicabilidade de cada aba e `test_troca_de_analise_limpa_o_resultado_anterior`
  guarda a limpeza.

## Frequência mínima: o que muda (verificação, 21/11/2026)

Medido no `batanero`, todos os períodos, palavras-chave, coocorrência mínima 2:

| freq. | docs | itens/nós | arestas | grupos |
|---|---|---|---|---|
| 1 | 147 | 344 | 98 | 11 |
| 2 | 147 | 90 | 98 | 11 |
| 3 | 147 | 55 | 84 | 8 |
| 4 | 147 | 43 | 65 | 7 |
| 5 | 147 | 35 | 55 | 5 |
| 6 | 147 | 24 | 43 | 4 |
| 8 | 147 | 15 | 30 | 3 |

- **Muda**: itens, nós, arestas, grupos, tamanho do maior grupo, densidade
  média, quadrantes, índices por grupo, evolução e comparação de períodos.
- **Não muda**: documentos, citações, autores, instituições, países,
  referências distintas e crescimento anual — são do corpus do período, não da
  rede filtrada. Por isso a Visão geral descritiva fica estável.
- **De 1 para 2** só saem os itens isolados: as arestas e os grupos ficam
  iguais (98 e 11 em palavras-chave; 3.682 e 66 em referências) porque nenhuma
  ligação depende de item com uma única ocorrência.
- **A partir de 3** a poda atinge a rede: caem arestas e grupos, não só nós.
- **No modo simples** a frequência pode subir sozinha: se a rede passar de 14
  grupos, o app aumenta a frequência até 6 (ou até o ponto em que sobrarem
  menos de 4), avisa na nota e mantém o valor. Usar `+`/`−` desliga esse ajuste
  automático (`personalizada`).
- **Análise personalizada** respeita o valor escolhido; no avançado, o número
  só vale depois de `Pré-visualizar`.

## Sem "Modo avançado": tudo à vista (21/11/2026)

- **O alternador saiu do menu**: `Modo avançado` deixou de existir. O corpo do
  documento nasce com `modo-avancado`, então todos os parâmetros, a grade
  completa e os itens de exportação aparecem desde o início.
- **Blocos abertos**: `Mais opções` e `Parâmetros avançados` vêm com `open`;
  o resumo de `Mais opções` fica oculto, e os campos entram direto no cartão.
- **Sem esconder por CSS**: saíram as regras
  `body:not(.modo-avancado) .so-avancado` e a que escondia os itens de corpus
  focal. Nada mais depende da classe para aparecer.
- **Mudar um parâmetro roda a análise**: frequência, predefinições, unidade,
  matriz, similaridade, algoritmo, mapeadores, palavras, corte, tamanho do
  grupo e co-ocorrência mínima agendam a prévia (500 ms). O botão
  `Pré-visualizar` continua para repetir quando quiser.
- **Frequência manual é respeitada**: sem modo simples, o ajuste automático de
  frequência não roda; o valor que o usuário escolher é o valor usado.
- **Países e IES** seguem fora da unidade manual (já tinham saído na rodada
  anterior); continuam nas análises próprias do menu.

## Avisos repetidos fora da faixa (21/11/2026)

- **`termo_generico` e `autor_focal` saíram da faixa de avisos**: eram dois
  parágrafos amarelos que repetiam o que a própria tela já mostrava (o termo
  dominante aparece no Resumo com o botão `Ignorar e reanalisar`; o corpus
  focal já vem marcado no projeto).
- **Chips `aviso` do menu removidos**: `Países` e `Instituições` exibiam um
  selo amarelo "aviso" em corpus de autor focal. O item continua na lista, sem
  o selo.
- **O que fica**: avisos de limite que mudam a leitura — período pequeno, tema
  dominante, poucas referências em comum, grupos fracos, um só periódico.
  Os dados de `termo_generico` e `autor_focal` continuam no JSON da API e no
  relatório; só a tela não os repete.

## Fim da aba Resumo e foco de Países (21/11/2026)

- **A aba `Resumo` saiu**: o cartão em prosa, a grade por quadrante, o aviso de
  termo genérico com o botão `Ignorar e reanalisar` e os estados de carregamento
  do resumo foram removidos do HTML, do JS e do CSS. A aba existia em todas as
  análises e repetia, em outra forma, o que já está em Índices, Grupos,
  Diagrama e na faixa de avisos.
- **Abertura de cada análise**: a primeira aba é `Evolução` quando a análise
  tem evolução; nas demais, a aba padrão declarada em `CONFIG_ABAS.padrao`
  (`paises` em Países, `rede` nas outras). No modo personalizado, `rede`.
- **Qualidade continua**: o selo de qualidade e o popover seguem na barra; só
  o resumo em prosa deixou de existir. Ao trocar de análise, o selo é escondido
  junto com o resultado anterior.
- **Países agora tem duas visões**: `Países` (mapa da colaboração) e
  `Densidade`. Saíram rede de halos, diagrama estratégico, ligações entre
  grupos, grupos, índices, dendrograma, linha do tempo e comparação de períodos
  dessa análise; a barra mostra só os blocos `Mapas` e `Métodos`.
- **Sem o resumo, o `Ignorar e reanalisar` também saiu**: os dados de
  `termo_generico` e `autor_focal` continuam na API e no relatório, mas não há
  mais botão na tela para remover um termo dominante.

## Instituições com rede e densidade (21/11/2026)

- **IES passou a ter duas visões**: `Rede de instituições` (halos da
  colaboração entre IES) e `Densidade`. Saíram variantes unidas, diagrama
  estratégico, ligações entre grupos, grupos, índices, dendrograma, linha do
  tempo e comparação de períodos; a barra mostra só `Mapas` e `Métodos`.
- **A consolidação de nomes não se perde**: a tabela de variantes unidas
  continua na API (`ies`) e no relatório completo; só a aba não aparece.
- **Países e IES agora são as duas análises enxutas**: mapa + densidade e rede
  + densidade, respectivamente. As demais seguem com o conjunto completo de
  visões declarado em `CONFIG_ABAS`.

## Coautoria com quatro visões (21/11/2026)

- **Coautoria ficou com `Rede de coautoria`, `Dendrograma`, `Linha do tempo` e
  `Densidade`**, nos blocos `Mapas` e `Métodos`. Saíram diagrama estratégico,
  ligações entre grupos, grupos, índices e comparação de períodos.
- **Três análises agora são enxutas**: Países (mapa + densidade), Instituições
  (rede + densidade) e Coautoria (rede, dendrograma, linha do tempo e
  densidade). As demais mantêm o conjunto completo de `CONFIG_ABAS`.

## App desktop em Tauri (21/11/2026)

- **Novo app `desktop/` (Tauri 2)**: abre a interface local do Redes em uma
  janela própria, sem navegador. O servidor Python (`redes web`) vai embutido
  como sidecar gerado pelo PyInstaller — o usuário não instala Python.
- **Fluxo**: o Rust usa a porta preferida 47823 (a mesma entre execuções,
  para preservar o `localStorage`), sobe o sidecar com `--porta <porta>
  --nao-abrir`, espera o servidor responder e navega a janela para
  `http://127.0.0.1:<porta>/`. Se a porta estiver ocupada, escolhe a próxima livre.
- **Encerramento**: ao sair, o app mata o sidecar; como o PyInstaller onefile
  cria dois processos, o servidor recebe o PID do app em `REDES_PAI_PID` e um
  vigia sai sozinho quando o app desaparece (inclusive em encerramento forçado).
- **Tela de abertura** (`desktop/splash/`): logo e “Abrindo o servidor local…”;
  em caso de falha, mostra uma mensagem com o caminho de projetos.
- **Empacotamento**: `desktop/scripts/build-sidecar.sh` gera
  `binaries/redes-servidor-<triple>`; `tauri build` produz `Redes.app` e o DMG.
  Ícones vêm de `redes/assets/logo.svg` (`scripts/gerar-icones.sh`).
- **Versão 0.3.0**: é a versão do app desktop, independente da versão do pacote
  Python (0.1.1). A configuração, o `Cargo.toml` e o `package.json` andam juntos
  (há teste).
- **GitHub**: workflow `.github/workflows/tauri.yml` roda no `macos-latest`,
  gera o DMG, publica o artefato e, em tag `v*` ou execução manual com
  `versao`, cria/atualiza o Release com `Redes-<versão>-macOS-arm64.dmg` e o
  `.sha256`.
- **Limite**: o build é arm64 (Apple Silicon). Intel exigiria um runner ou
  sidecar x86_64; o app é assinado ad hoc e não é notarizado.

### Assinatura do app (complemento)

- **`signingIdentity: "-"`**: o Tauri assina o bundle e os dois executáveis
  (`redes-desktop` e `redes-servidor`) em modo ad hoc. Sem isso, o app saía
  apenas com a assinatura do linker e o `codesign --verify --deep` acusava
  recurso ausente. O DMG publicado foi conferido depois de montado.
- **Não notarizado**: o release explica o clique com o botão direito em
  **Redes > Abrir** na primeira execução.

## Sem faixa amarela de avisos (21/11/2026)

- **A faixa `avisos` saiu da análise**: o bloco amarelo abaixo dos parâmetros
  (tema dominante, grupos fracos, período pequeno) não aparece mais em nenhuma
  aba, nem na evolução. Só a tela mudou: `resultado.avisos` continua na API e o
  relatório completo continua com a seção de motivos e limites.
- **Código compartilhado**: a remoção vale para a interface web e para o app
  desktop (macOS e Windows), porque as três usam o mesmo `redes/ui`.
- **O que fica**: o selo de qualidade, o aviso do Resumo (quando houver) e as
  notas de método dentro das próprias tabelas, que explicam um número em vez de
  alertar sobre o corpus.

## Ícone só com a marca (21/11/2026)

- **O ícone não leva o nome**: `redes/assets/logo.svg` é a assinatura completa
  (marca + palavra "Redes"); para o app foi criado `redes/assets/logo-icone.svg`
  com apenas a rede em halos sobre um quadrado branco de cantos arredondados.
  `desktop/scripts/gerar-icones.sh` passou a partir desse arquivo, então o
  `.icns` (macOS) e o `.ico` (Windows) saem sem texto.
- **A interface não mudou**: as telas já usavam `redes/ui/logo-mark.svg`, que é
  só a marca. O nome do produto continua no título da janela e no menu.

## Windows (21/11/2026)

- **Mesmo código, dois instaladores**: o app Tauri é multiplataforma; o que muda
  é o empacotamento. O workflow ganhou o trabalho `exe` (`windows-latest`,
  instalador NSIS) e um trabalho `release` que roda depois dos dois builds e
  publica `Redes-<versão>-macOS-<arq>.dmg` e
  `Redes-<versão>-Windows-x64-setup.exe`, cada um com `.sha256`.
- **Sidecar com extensão**: no Windows o PyInstaller gera `redes-servidor.exe`;
  `build-sidecar.sh` renomeia para `redes-servidor-<triple>.exe`, que é o nome
  que o Tauri espera.
- **Vigia do processo pai**: `os.kill(pid, 0)` não serve no Windows (a chamada
  encerra o processo em vez de consultá-lo). O sidecar usa
  `OpenProcess` + `GetExitCodeProcess` quando `os.name == "nt"`.

## Hardened runtime e o sidecar (21/11/2026)

- **Sintoma**: depois de assinar o app em modo ad hoc, a janela ficava na tela
  de abertura. O log do sidecar mostrava `Failed to load Python shared library
  ... different Team IDs`.
- **Causa**: o Tauri liga o *hardened runtime* por padrão. Com ele, o macOS só
  carrega bibliotecas assinadas com o mesmo Team ID do processo; o
  `Python.framework` extraído pelo PyInstaller é assinado pela PSF, então o
  `dlopen` era recusado.
- **Correção**: `entitlements.plist` com `disable-library-validation`,
  `allow-unsigned-executable-memory` e `allow-dyld-environment-variables`,
  aplicado pelo Tauri ao app **e** ao sidecar (conferido com
  `codesign -d --entitlements -`). O app voltou a subir o servidor e a fechar
  sem deixar processo vivo.
- **Lição**: `codesign --verify` aprovado não garante que o app abre; o teste
  tem de abrir o app e pedir a página em `127.0.0.1`.

## Release v0.4.0 (21/11/2026)

- **Publicado**: https://github.com/gerlansilva/redes/releases/tag/v0.4.0 com
  `Redes-0.4.0-macOS-arm64.dmg` (18,9 MB) e
  `Redes-0.4.0-Windows-x64-setup.exe` (26,1 MB), cada um com `.sha256`.
- **Conferido**: DMG baixado do release, montado, `codesign --verify --deep`
  aprovado, sidecar respondendo 200 e app abrindo e fechando sem deixar
  processo. Instalador do Windows é NSIS válido (PE32).
- **v0.3.0**: ficou com aviso no release — o app abria, mas o servidor interno
  não subia no macOS atual. A correção entrou na 0.4.0.
- **CI**: o trabalho de release precisa de `actions/checkout` para o `gh`
  descobrir o repositório; sem isso, `gh release create` falha.

## Capturas de tela atualizadas (21/11/2026)

- **22 imagens viraram 14**: saíram as capturas de recursos removidos (faixa
  amarela de avisos, modo avançado, aba Resumo, detalhe por período recolhido) e
  entraram Países (mapa) e Instituições (rede), que agora têm aba própria.
- **Padrão de captura**: 1296 x 827 (janela do navegador do app), sempre a partir
  dos dois projetos públicos (`celii`, 53 documentos, e `batanero`, 147
  documentos e 3 períodos).
- **Textos alinhados**: `README.md`, `docs/guia-de-uso.md`, `docs/analises.md` e
  `docs/perguntas-frequentes.md` deixaram de citar modo avançado, faixa amarela,
  *Ignorar e reanalisar* e *Detalhe por período*; o guia passa a descrever os
  grupos Temas, Citações e Colaboração e a barra de resultados.

## A marca é o arquivo oficial, sem redesenho (21/11/2026)

- **Fonte única**: `redes/assets/logo.png`, o arquivo entregue pela coordenação,
  usado como está (1254 x 1254, mesmo SHA-256 `4c296f46…` em todas as cópias).
  Não há versão redesenhada: `logo.svg`, `logo-mark.svg` e `logo-icone.svg`
  foram removidos.
- **Onde aparece**: favicon, abertura, menu lateral, capa e cabeçalho do
  relatório, tela de abertura do app desktop, ícones `.icns`/`.ico` (gerados a
  partir do PNG) e README. O nome do produto continua como texto.
- **Servidor**: `/static/` passou a servir binários (PNG e ICO) além de
  HTML/CSS/JS/SVG; antes tentava ler tudo como UTF-8 e devolvia erro.
- **Relatório único**: a marca entra embutida em `data:image/png;base64`, para o
  HTML continuar sem arquivos externos.
- **Tamanhos**: README 180 px; capa do relatório 150 px; cabeçalho 40 px.
