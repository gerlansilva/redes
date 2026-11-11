# Similitude dos resumos (estilo IRaMuTeQ)

Mostra, num grafo, **quais palavras dos resumos aparecem juntas**. Cada ponto é uma palavra
(já reduzida à forma básica), o tamanho do ponto é a frequência, as linhas são os laços mais
fortes e as cores são **blocos temáticos**. Fica na aba **Similitude** (modo avançado, depois
de "Duplo mapa"), no menu **Exportar** (SVG, GraphML e CSV) e nos relatórios.

Funciona com resumos em **inglês, português e espanhol**, no mesmo projeto. Roda inteira no
computador do usuário, sem rede e sem baixar nada. O código está em `redes/similitude.py`
(cálculo) e `redes/viz/similitude.py` (SVG).

## Como é calculado

1. **Texto.** Resumos com pelo menos 15 palavras, sem aviso de direitos autorais (`©`,
   "copyright", "all rights reserved") nem marcadores como "no abstract available". A aba
   pode restringir a um período.
2. **Idioma por resumo** (`en`, `pt`, `es`). Cada palavra funcional vale 1 ponto para o idioma em
   que existe (meio ponto se está em dois, como "de" ou "que"). Caracteres e terminações
   típicas somam pontos: `ã õ ç` e `-ção` (pt), `ñ ¿ ¡` e `-ción` (es), `-tion`, `-ing` (en).
   Vence o idioma de mais pontos; sem evidência, inglês. Em resumo bilíngue (a mesma ideia nas
   duas línguas), frases longas com idioma claramente diferente são descartadas, e o resumo
   fica com a versão do idioma que domina o corpus (ou do idioma escolhido na tela).
3. **Palavras vazias e genéricas**, por idioma: artigos, preposições, pronomes, formas de
   *ser/estar/ter/haver/poder*, números e os termos de praxe de resumo ("objetivo",
   "resultados", "results", "se analiza", "we propose"). Palavras de até 2 letras também saem.
   Dá para pedir mais palavras a ignorar na tela (ou `ignorar` na API).
4. **Lematização leve.** Sem dicionário, sem rede, sem biblioteca externa (NLTK e spaCy não são
   usados). Regras por idioma, **conservadoras**: uma forma só se une à mais simples quando
   esta aparece nos resumos (ou quando duas formas diferentes apontam para o mesmo verbo).

   | Idioma | O que é unido |
   |---|---|
   | pt | plural (`-s`, `-es`, `-ões/-ães/-ãos → -ão`, `-ais/-eis → -al/-el`, `-ns → -m`), gênero (`aluna → aluno`, `professora → professor`, `-osa/-iva/-ana/-eira`), particípio e gerúndio (`ensinado`, `ensinando → ensinar`), 3ª pessoa do plural e pretérito (`ensinam`, `ensinou`), `-mente` (`estatisticamente → estatística`), `-ção/-ções`, `-dade/-dades` |
   | es | plural (`-s`, `-es`, `-ones → -ón`, `-ces → -z`, `-ades → -ad`, `jóvenes → joven`), gênero, particípio e gerúndio (`enseñado`, `enseñando → enseñar`), `-an/-aron/-ieron`, `-mente`, `-ción/-ciones` |
   | en | plural (`-s`, `-ies`, `-ches`, irregulares como `children`, `analyses`), `-ing/-ed` (`learning`, `learned → learn`), `-ly`, `-ization` |

   Não são unidos de propósito: diminutivos, aumentativos, e feminino de adjetivos em `-ica`
   (`estatística` é a disciplina; `estatístico` se une a ela por uma lista curta de exceções,
   como `statistical → statistics`). Formas de idiomas diferentes **nunca** se fundem; cada
   palavra é identificada por idioma e lema (`pt:estatística`, `es:estadística`).
5. **Palavras do grafo.** As `n_formas` mais frequentes (30 a 100, padrão 60) que aparecem em
   pelo menos 3 segmentos (2 quando o idioma tem menos de 12). Com vários idiomas cada um
   recebe uma cota mínima de 10 palavras e o resto é dividido em proporção ao número de
   resumos; idioma com menos de 5 resumos fica de fora (e a tela avisa).
6. **Segmento** (`segmento`): `resumo` (o resumo inteiro, padrão) ou `frase` (grupos de frases
   de cerca de 14 palavras, parecido com os segmentos do IRaMuTeQ).
7. **Índice** (`indice`) entre cada par de palavras, a partir dos segmentos em que aparecem
   juntas (`c`) e dos segmentos de cada uma (`a`, `b`):

   | `indice` | Fórmula | Quando usar |
   |---|---|---|
   | `jaccard` (padrão) | `c / (a + b − c)` | equilibrado; não superestima palavras muito frequentes |
   | `cosseno` | `c / √(a·b)` | parecido com Jaccard, favorece um pouco as frequentes |
   | `binomial` | `−log10 P(X ≥ c)`, hipergeométrica | destaca associações improváveis ao acaso; mais lento com 100 palavras |
   | `cooc` | `c` | o do IRaMuTeQ por padrão; domina quem é muito frequente |
8. **Árvore máxima.** Algoritmo de Kruskal: as ligações entram em ordem decrescente de índice,
   sem fechar ciclo (empate decidido pelo nome das palavras, então o resultado é sempre o
   mesmo). Sobram só os laços fortes necessários para manter as palavras conectadas; palavras
   que nunca coocorrem (como as de idiomas diferentes) ficam em componentes separados.
9. **Arestas extras** (`arestas_extras`, 0 a 50%, padrão 20%): as ligações mais fortes fora da
   árvore, desenhadas tracejadas, só para facilitar a leitura. Entram na contagem do grau.
10. **Blocos.** Comunidades pelo método de Louvain **sobre a árvore** (resolução 1, semente 7),
    numeradas do maior para o menor. Um bloco é um conjunto de palavras usadas juntas.

## Desenho

Layout em dois níveis: cada bloco é arrumado sozinho (molas sobre as ligações do bloco, depois
separação das caixas dos rótulos) e os blocos são dispostos entre si, sem que as manchas se
toquem. Raio do ponto e tamanho da letra crescem com a raiz da frequência. O `viewBox` sai da
geometria (pontos, rótulos, manchas, legenda e rodapé), então nada fica fora da área.

**Largura do texto: decisão.** O SVG precisa saber a largura dos rótulos para não os sobrepor,
e isso não pode depender de PIL, de fontes instaladas nem do navegador (o SVG é gerado no
servidor e também vai para relatórios). Usei a **tabela de larguras por caractere já embutida**
em `viz/linha_do_tempo.py` (Inter, 12 px), multiplicada por **1,20**. Medido no Chromium
(`getBBox`) com os rótulos de um projeto real: a tabela subestima o Inter 500 em até 2% no
pior rótulo, então o fator dá cerca de 7% de folga sobre o Inter e ainda cobre o DejaVu Sans,
a fonte de reserva mais larga (Arial e Helvetica são mais estreitas). O custo é um pouco de
espaço a mais entre rótulos. O teste `tests/test_similitude.py` repete a medição no navegador
quando o Playwright está instalado.

## API

`GET` ou `POST /api/similitude` (também pelo `token` de uma análise já calculada):

| Parâmetro | Valores | Padrão |
|---|---|---|
| `token` ou `projeto`/`caminho` | análise calculada, ou caminho do `.redes` | obrigatório um dos dois |
| `n_formas` | 30 a 100 | 60 |
| `indice` | `jaccard`, `cosseno`, `binomial`, `cooc` | `jaccard` |
| `segmento` | `resumo`, `frase` | `resumo` |
| `arestas_extras` | 0 a 50 (%) | 20 |
| `idioma` | `todos`, `en`, `pt`, `es` | `todos` |
| `periodo` | `todos`, id ou nome do período | `todos` |
| `ignorar` | lista (POST) ou texto separado por vírgula | nenhuma |
| `baixar` | `svg`, `graphml`, `csv` (palavras), `csv-arestas` | JSON na tela |

A resposta JSON traz `svg`, `nota`, `formas` (palavra, idioma, frequência, resumos, ocorrências,
bloco, grau), `arestas` (origem, destino, peso, tipo `arvore` ou `extra`), `comunidades`,
`docs_por_idioma`, `parametros`, `tabela_parametros` e `avisos`. Sem resumos (ou com resumos
curtos demais), a API responde 400 com uma mensagem em português.

## Como ler a figura

- **Ponto grande** = a palavra aparece em muitos resumos.
- **Linha cheia grossa** = laço forte (da árvore máxima). **Tracejada** = laço extra, mais fraco.
- **Cor e mancha** = bloco temático. Leia o bloco pelas palavras maiores dele (a legenda mostra
  as três mais frequentes de cada bloco).
- **Posição** não significa nada além de "quem está ligado a quem"; blocos próximos não são
  necessariamente mais parecidos.
- Com vários idiomas, palavras iguais em idiomas diferentes (`social`, `gráfico`) ganham o
  idioma entre parênteses; os blocos de idiomas diferentes aparecem separados.

## Limites

- Não é o IRaMuTeQ: não há etiquetas gramaticais nem o dicionário Lexique, então a lematização
  é aproximada (verbos irregulares, por exemplo, ficam como estão) e substantivos, adjetivos e
  verbos entram juntos.
- Poucos resumos (menos de umas 30) dão um grafo instável; o índice e o segmento mudam a figura.
- Resumos mal detectados (muito curtos, só siglas) caem em inglês.
