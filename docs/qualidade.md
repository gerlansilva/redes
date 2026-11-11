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

| Selo | Quando |
|---|---|
| Ruim | Q abaixo de 0,15 ou silhueta média abaixo de 0 |
| Atenção | Q abaixo de 0,30; razão abaixo de 0,6; silhueta média abaixo de 0,10; mais de 30% dos itens com silhueta negativa; menos de 60% dos itens em agrupamentos; rede fragmentada (mais componentes do que a metade dos itens); ou unidade Autores (coautoria nunca passa de Atenção) |
| Indefinido | Menos de 15 itens, menos de 2 agrupamentos ou rede sem ligação positiva. Nenhum número é mostrado como 0 |
| OK | Nenhum dos alertas acima |

Leitura prudente, não aprovação: a maioria das redes reais fica em
"Atenção" e isso não invalida o mapa.

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
