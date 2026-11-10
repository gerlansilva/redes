# Comparativo — Redes e VOSviewer no corpus Batanero

## Resumo

O `batanero.json` tem 3.177 itens de referência. O corpus tem 4.139 citações
brutas, que viram 3.114 citações únicas depois de ignorar numeração,
hifenização, caixa, acento e pontuação. O Redes grava 3.064 referências porque
junta cerca de 50 pares que são a mesma citação com número de edição, bloco
repetido ou apóstrofo diferente.

Nenhuma referência do VOSviewer está ausente do Redes. A conferência de
conjuntos deu:

- citações únicas no arquivo: 3.114;
- citações únicas nos rótulos do VOSviewer: 3.114;
- interseção: 3.114;
- só no VOSviewer: 0;
- só no arquivo: 0.

## De onde vem a diferença 3.177 × 3.064

| Etapa | Itens |
|---|---:|
| Rótulos no VOSviewer | 3.177 |
| Citações únicas após normalização | 3.114 |
| Referências no Redes | 3.064 |

- **63 itens** do VOSviewer são a mesma citação repetida com numeração
  (`[10]`, `[12]`), hifenização de quebra de linha (`deve- lopment`) ou
  diferença de caixa.
- **50 itens** são a mesma obra com número de edição, bloco de fonte repetido
  ou apóstrofo diferente. Exemplos: `Teaching Statistics 10` e
  `Teaching Statistics 10 (3)`; `Memory and Cognition` e `Memory Cognition`;
  `adult's` e `adults`.

Nenhum desses pares é obra distinta. O Redes não agrupa por título e ano; a
redução vem só da conversão e da normalização.

## Cobertura das referências

Todos os 3.177 rótulos do VOSviewer viram uma referência do Redes. O caminho é:

1. 3.177 rótulos;
2. 3.114 citações únicas;
3. 3.064 referências gravadas, com os pares duplicados unidos.

O Redes também grava todos os vínculos documento–referência: 4.137. Cada
documento aponta para cada referência que cita. Nenhuma citação é descartada.

Auditoria dos vínculos, feita no banco do projeto:

- 4.139 citações brutas no arquivo;
- 2 delas são a mesma citação repetida dentro do mesmo documento;
- 4.137 vínculos gravados, exatamente as 4.137 citações restantes;
- 147 de 147 documentos com vínculo;
- em nenhum documento a contagem declarada difere dos vínculos gravados.

Cada um dos 3.177 rótulos do VOSviewer também foi conferido individualmente.
A planilha `docs/comparacao-itens-vosviewer.csv` traz, para cada rótulo, a
referência correspondente no Redes e o `idReference`. São 154 rótulos que não
casam por chave na primeira tentativa, mas todos os 154 estão no texto do
arquivo: a diferença é só a reconstrução de caixa e hífen do rótulo, não
ausência de dado.

## Fontes e autores: mapas conferidos

Os dois mapas exportados têm exatamente as contagens informadas:
`sourcebatanero.csv.json` com 1.895 itens e `autoresbatanero.csv.json` com
2.560. Comparados com o banco do projeto, mostram o que o VOSviewer está
contando.

### Fontes

- VOSviewer: 1.895 itens.
- **577** desses rótulos trazem a faixa de páginas colada no nome, como
  `advances in applied mathematics 12 4 pp. 428-454`.
- Removendo páginas, volume, ano e URL: **1.469 nomes distintos**.
- Redes: **1.464 nomes distintos** gravados em `ReferenceSource`.
- Nomes comuns aos dois: 1.147.

A diferença de 1.895 para 1.469 é a mesma revista repetida item a item, uma vez
por faixa de páginas. Depois de normalizar, as duas contagens ficam a 5 nomes
uma da outra (0,3%).

### Autores

- VOSviewer: 2.560 itens, 2.455 distintos depois de remover a numeração
  (`[10] cepeda-cuervo e.`).
- Redes: **1.672 autores individuais**.
- **Todos os 1.672 autores do Redes aparecem no mapa do VOSviewer. Cobertura de
  100%.**
- Dos 783 nomes distintos que sobram no VOSviewer, 116 são lixo evidente: `12`,
  `4`, `2nd ed.`, `3rd ed.`, `m.e.p.`, `a.`. O restante são fragmentos de
  título ou de outros campos, como `adult's statistical literacy: meanings c.`
  e `actas v jornadas thales`.

### O que isso significa

Os dois programas erram ao separar campos de referências mal formatadas. A
diferença é onde o erro cai:

- no VOSviewer, o campo da fonte engole páginas e volume, inflando a contagem
  de fontes, e o campo de autor engole pedaços de título, inflando a de autores;
- no Redes, sobram 317 nomes de fonte que também são lixo de leitura, como
  `1982a`, `41A`, `BATANERO C` e títulos inteiros.

Nenhum dos dois perde autor: os 1.672 do Redes estão todos no mapa do VOSviewer.
E o conjunto de referências é idêntico. A diferença de contagem é de extração de
campo em citação mal formatada, não de dado ausente.

## Conclusão

- Referências: **sem perda**. Os dois programas partem das mesmas 3.114
  citações únicas e todos os 3.177 rótulos do VOSviewer existem no Redes.
- Vínculos: **sem perda**. 4.137 de 4.139 citações brutas, e as 2 restantes são
  repetição da mesma citação no mesmo documento.
- VOSviewer: 3.177 itens, porque mantém 63 variantes de numeração e grafia.
- Redes: 3.064 referências, porque normaliza e une 50 pares duplicados.
- Fontes: 1.895 do VOSviewer contra 1.469 após remover páginas e volume; o
  Redes tem 1.464. Ficam a 0,3% uma da outra.
- Autores: **cobertura de 100%**. Todos os 1.672 autores do Redes estão no mapa
  do VOSviewer; os 2.560 incluem 116 rótulos que nem são nomes (`12`, `2nd
  ed.`) e centenas de fragmentos de título.
- Item a item: `docs/comparacao-itens-vosviewer.csv`.

## Como reproduzir

```bash
python3 scripts/comparar_vosviewer.py ~/Downloads/batanero.csv
python3 scripts/comparar_vosviewer.py ~/Downloads/celii.csv
python3 scripts/comparar_fontes_autores.py \
  ~/Desktop/sourcebatanero.csv.json \
  ~/Desktop/autoresbatanero.csv.json \
  ~/scimatpy-projetos/batanero-auditoria/dados.redes
```
