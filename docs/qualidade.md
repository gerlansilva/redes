# Qualidade do mapa e rótulos dos agrupamentos

Código em `scimatpy/qualidade.py` e `scimatpy/rotulos.py`. Vale para cada
período de uma análise e aparece no cartão da tela, nas tabelas de
agrupamentos e no relatório (seção "Qualidade do mapa" e "Rótulos dos
agrupamentos" do método).

## Medidas

- **Q (força da divisão).** Modularidade de Newman ponderada pela
  similaridade. Vai de cerca de 0 (como dividir ao acaso) a perto de 1. O item
  sem agrupamento conta como um grupo de um item só.
- **Q do Louvain e razão.** O mesmo cálculo para a partição do Louvain na
  mesma rede, como régua. `razao = Q / Q_Louvain`.
- **Silhueta.** Distância = 1 − similaridade normalizada (a mesma do
  dendrograma). De −1 a 1; negativa sugere item mal alocado. Agrupamentos com
  menos de 3 itens ficam fora e aparecem com "—". Acima de 2000 itens
  agrupados a silhueta é dispensada (matriz n × n).

## Selo

O selo responde "o mapa é feito de agrupamentos de verdade?". Depende só da estrutura:

| Selo | Quando |
|---|---|
| Ruim | Menos de 50% dos itens em agrupamentos de 5 ou mais itens (o resto está solto ou em pares e trios) |
| Atenção | De 50% a menos de 80% dos itens em agrupamentos de 5 ou mais; ou rede fragmentada (mais componentes do que a metade dos itens); ou unidade Autores (coautoria nunca passa de Atenção) |
| Indefinido | Menos de 15 itens, menos de 2 agrupamentos ou rede sem ligação positiva. Nenhum número é mostrado como 0 |
| OK | 80% ou mais dos itens em agrupamentos de 5 ou mais, rede não fragmentada e não coautoria |

Indicador novo: `pct_em_grupos_grandes` (% dos itens da rede em agrupamentos de
`GRUPO_GRANDE` = 5 ou mais itens; item sem agrupamento conta como fora). Aparece no
cartão, no popover e na tabela de indicadores do relatório.

**Avisos de nitidez (não mudam o selo).** Q abaixo de 0,30 (abaixo de 0,15, "muito
fraca"), razão abaixo de 0,6, silhueta média abaixo de 0,05 (abaixo de 0, itens mais
perto de outros grupos) e mais de 30% dos itens com silhueta negativa continuam
gerando avisos, seguidos de uma nota (`NOTA_NITIDEZ`) que diz que eles descrevem a
nitidez da divisão e não o selo. Os números seguem visíveis.

Leitura prudente, não aprovação: Atenção não invalida o mapa; Ruim quer dizer que,
com estes parâmetros, quase nada forma agrupamento de verdade (vale tentar uma
frequência mínima maior).

### Decisão sobre o selo "Ruim" (11/11/2026)

Pergunta: "Ruim" deve valer "3 ou mais famílias de alerta ao mesmo tempo"? Em vez de
decidir por simulação de distribuição, comparou-se cada regra com o julgamento visual
dos mapas (halo e diagrama estratégico, renderizados em PNG com Playwright).

*Método.* 29 períodos sorteados, estratificados pelo selo antigo e pelo número de
famílias de alerta (serj, serj_auto, novo142, eecera59; sete unidades), mais 14
períodos de uma segunda amostra sorteada à parte (2 por unidade) e julgada antes de
escolher a regra. Cada mapa foi visto sem o selo, com um critério fixado antes: **Bom**
(grupos de verdade, poucos itens soltos), **Regular** (núcleo legível, mas parte do
mapa em pares, trios ou itens soltos) e **Inutilizável** (menos da metade dos itens em
grupos de 5 ou mais; muitos nós soltos, grupos triviais ou rede fragmentada). Bom
deveria receber OK, Regular Atenção e Inutilizável Ruim. Os 43 julgamentos estão
descritos abaixo; o julgamento é de um só avaliador, então a tabela mede aderência a
essa leitura, não verdade absoluta.

*Achado central.* O selo antigo estava quase invertido em relação ao que se vê: dos 21
mapas Bons, 9 saíram Ruim e 11 Atenção (só 1 OK), e dos 12 Inutilizáveis nenhum saiu
Ruim, 3 saíram OK. Q, razão, silhueta e itens negativos medem a *nitidez*: em redes
densas (acoplamento, referências; de milhares a mais de 100 mil arestas) ficam baixos
mesmo com agrupamentos grandes e coesos, e em redes de pares isolados (coautoria,
instituições) o Q fica alto (0,62 a 0,96 em 10 dos 12 Inutilizáveis) sem nada a ler. A
fração de itens em agrupamentos de 5 ou mais separou os dois casos: Bons entre 83% e 99%
(exceto um, com 69%), Regulares entre 51% e 87%, Inutilizáveis entre 0% e 61%.

Selo (linhas) contra julgamento visual, 43 mapas:

| Visual \ selo | Antigo OK | Antigo Atenção | Antigo Ruim | Novo OK | Novo Atenção | Novo Ruim |
|---|---|---|---|---|---|---|
| Bom (21) | 1 | 11 | 9 | 20 | 1 | 0 |
| Regular (10) | 5 | 3 | 2 | 1 | 9 | 0 |
| Inutilizável (12) | 3 | 9 | 0 | 0 | 2 | 10 |
| Concordância exata | 4/43 | | | 39/43 | | |

Regras candidatas (concordância exata com Bom=OK, Regular=Atenção, Inutilizável=Ruim;
"Ruim certo" = Inutilizáveis que a regra acusa; "Ruim falso" = Bons ou Regulares que a
regra acusa), 43 mapas:

| Regra | Concordância | Ruim certo (de 12) | Ruim falso |
|---|---|---|---|
| Antiga (Q < 0,15 ou silhueta < 0) | 4 | 0 | 11 |
| Só Q (< 0,15 Ruim, < 0,30 Atenção) | 4 | 0 | 11 |
| Ruim com 3 ou mais famílias de alerta | 5 | 2 | 14 |
| Ruim com 2 ou mais famílias | 6 | 4 | 23 |
| Ruim com 4 ou mais famílias | 7 | 1 | 0 |
| **Nova: itens em grupos de 5+ (Ruim < 50%, OK >= 80%)** | **39** | **10** | **0** |

"Famílias" = força (Q < 0,30), razão (< 0,6), coesão (silhueta < 0,05 ou > 30%
negativos), cobertura (< 60% agrupados), fragmentação. As regras por famílias não
funcionam porque os 21 mapas Bons têm de 1 a 3 famílias acesas; qualquer regra que use
Q, razão ou silhueta como gatilho do selo acusa justamente os mapas bem agrupados de
redes densas.

*Sensibilidade e sobreajuste.* Limiares testados nos 43 mapas (Ruim abaixo de / OK a
partir de): 50/80 = 39 acertos; 50/85 = 38; 40/85 = 37; 50/90 = 33; 60/85 = 32. Há um
platô entre 50 e 85, então os valores redondos (metade dos itens; 4 em cada 5) não são
um ajuste fino. Os limiares nasceram da primeira amostra (26/29 em 50/85 e em 50/80); na
segunda, julgada às cegas antes, deram 12/14 (50/85) e 13/14 (50/80); a diferença é um
só mapa Bom com 83% (ficou 80, redondo, depois de ver isso: um ganho dentro do ruído). Os
4 erros restantes são casos de fronteira: dois mapas com ~60% dos itens em grupos grandes
mas centenas de grupos pequenos (Instituições e Palavras), que à vista ficam entre Regular
e Inutilizável e saem Atenção; um Regular com 87% que sai OK; um Bom com 69% que sai Atenção.

*Distribuição (323 períodos com selo definido, 4 projetos, todas as unidades e matrizes,
frequências 1 e 2, mais as análises do relatório):*

| Selo | Antes (silhueta < 0,05) | Depois (itens em grupos de 5+) |
|---|---|---|
| OK | 45 (14%) | 145 (45%) |
| Atenção | 214 (66%) | 74 (23%) |
| Ruim | 64 (20%) | 104 (32%) |
| Análises do relatório (44 períodos): OK / Atenção / Ruim | 7 / 35 / 2 | 21 / 7 / 16 |

O Ruim sobe de 20% para 32% porque agora acusa o que é visivelmente inútil. Por
unidade (OK / Atenção / Ruim, períodos com selo): Autores 0 / 1 / 46 e Instituições
0 / 6 / 35 (redes de pares e trios), Países 11 / 25 / 5, Referências 22 / 18 / 11,
Palavras 27 / 13 / 7, Autores de referências 40 / 7 / 0, Fontes de referências 45 / 4 / 0.
Ruim concentra-se em Autores e Instituições (78% dos Ruins). Motivos: 104 períodos
com menos de 50% em grupos de 5+ (Ruim), 74 com 50% a 80% (Atenção, 73 só por isso), 60 com
rede fragmentada, 47 coautoria. Os avisos de nitidez seguem acesos em 19% a 42% dos
períodos (silhueta < 0,05: 42%; mais de 30% negativos: 33%; razão < 0,6: 32%; Q < 0,30:
24%; Q < 0,15: 19%), sem efeito no selo.

Reproduzir: `python3 scripts/distribuicao_selo.py saida.json projeto.redes ...`
(grava `pct_em_grupos_grandes`, os motivos do selo e as notas de nitidez).

Limites: um só avaliador, 43 mapas e quatro bases (educação estatística); se o selo
passar a ser usado em outro domínio, vale repetir o julgamento visual. O critério visual
(itens em grupos triviais) é próximo do que o indicador mede por construção; o ganho
não vem de ajuste estatístico, e sim de trocar o gatilho do selo por algo que descreve
o que o usuário vê.

### Calibração anterior da coesão (11/11/2026, vale agora só para os avisos)


Esta calibração mexia no selo; depois ele passou a depender só da estrutura (seção
acima), e o limiar de coesão 0,05 ficou como limiar do aviso. Medida com
`scripts/distribuicao_selo.py` em serj, serj_auto, novo142 e eecera59:
todas as unidades e matrizes, frequências mínimas 1 e 2, mais as análises do
relatório completo (435 períodos, 323 com selo definido; os demais ficam
"Indefinido" por terem menos de 15 itens ou menos de 2 agrupamentos).

Régua: o Louvain maximiza o Q, então é a melhor divisão que a rede permite. Um
alerta que acusa essa divisão na maioria das redes mede a rede, não a divisão.
Nas bases reais, a partição do Louvain é acusada por Q < 0,30 em 23% dos períodos
e por Q < 0,15 em 9%, mas por silhueta média < 0,10 em 39%. A silhueta usa
distância 1 − similaridade, e par sem ligação direta fica a distância 1: numa
rede esparsa, mesmo um grupo bem separado dá valor baixo. O limiar de coesão
passou de 0,10 para **0,05** (a partição do Louvain é acusada em 21%, na faixa do
Q). Nada mais mudou: Q, razão, itens negativos e cobertura acusam entre 22% e 42%
dos períodos e discriminam.

| Selo (só períodos com selo definido) | Antes (silhueta < 0,10) | Depois (silhueta < 0,05) |
|---|---|---|
| OK | 27 (8%) | 45 (14%) |
| Atenção | 232 (72%) | 214 (66%) |
| Ruim | 64 (20%) | 64 (20%) |
| Análises do relatório (44 períodos): OK / Atenção / Ruim | 2 / 40 / 2 | 7 / 35 / 2 |

Motivos que sobram na Atenção (136 períodos acusam coesão < 0,05; 107 itens
negativos > 30%; 104 razão < 0,6; 76 Q < 0,30; 69 cobertura < 60%; 60 rede
fragmentada; 47 coautoria, em 23 deles como único motivo) são sinais reais, não
artefato de limiar: o algoritmo padrão (centros simples) acha divisões mais
fracas que o Louvain em mapas de referências, periódicos e países. O selo continua
conservador de propósito.

## Rótulos por tema

- **Onde vale.** Só palavras-chave (`Words`) e referências (`References`).
  Autores, países e instituições mantêm o nome do item líder.
- **Medida.** Razão de verossimilhança de Dunning (G²) entre os documentos do
  núcleo do agrupamento e os demais documentos do período. Só sobem termos
  mais frequentes no agrupamento.
- **Termos.** Palavras do título, palavras-chave dos autores (expressão
  inteira) e, do resumo, apenas bigramas. Singular, plural e acento são
  unidos; nada é traduzido. O termo precisa aparecer em pelo menos 2
  documentos do agrupamento, e um termo contido em outro é descartado.
- **Quando não há rótulo.** Menos de 5 documentos no núcleo, agrupamento que
  cobre mais de 70% do período, ou documentos sem título, resumo nem
  palavras-chave. Com 5 a 9 documentos o rótulo sai como indicativo.
- O rótulo antigo (item central) continua como subtítulo. A tabela traz também
  o ano médio dos documentos do núcleo.
