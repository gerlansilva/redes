# Linha do tempo e pontos de virada

Código em `scimatpy/linha_do_tempo.py`, `scimatpy/viz/linha_do_tempo.py` e
`scimatpy/pivos.py`. Aba **Linha do tempo** (modo avançado), rota
`/api/linha-do-tempo`, e seções no relatório.

## Linha do tempo (estilo CiteSpace)

- Usa o **corpus completo**: todos os documentos do projeto, sem criar período
  nem gravar nada (a base é aberta só para leitura), com a configuração e o
  algoritmo da análise.
- Uma faixa por agrupamento. Cada item vira um nó no **ano médio** dos
  documentos em que aparece (nas referências, no ano da própria obra). A linha
  fina atrás do nó vai do primeiro ao último ano; o tamanho do nó segue a
  frequência.
- Limites: 40 nós no total (os mais frequentes, escolhidos globalmente) e 8
  por faixa.
- Arcos: as 3 ligações mais fortes de cada nó dentro da faixa e as 6 mais
  fortes entre faixas.
- Rajadas (Kleinberg): anel vermelho nas 10 mais fortes do corpus com pelo
  menos 3 documentos.
- Itens sem ano ficam de fora, com aviso. Não vale para acoplamento nem
  cocitação de documentos.

## Pontos de virada e sigma

Por período, em redes de co-ocorrência:

- Intermediação de cada nó, normalizada por (n − 1)(n − 2)/2.
- **Ponto de virada:** intermediação no decil superior (percentil 90 entre os
  nós com intermediação positiva) **e** vizinhos em pelo menos dois
  agrupamentos. A tabela lista no máximo 10.
- **Termo-descritor:** presente em mais de 50% dos documentos do período; sai
  do ranking, porque descreve o corpus em vez de distinguir temas.
- **Sigma** = (intermediação normalizada + 1) elevado à força da rajada. Só
  existe para palavras-chave e referências com rajada; sem rajada o valor é
  vazio, nunca 1,0. Como a intermediação normalizada fica perto de zero, o
  sigma praticamente repete o ranking da força da rajada.
- Menos de 40 nós: a lista é só indício. Mais de 800 nós: a intermediação é
  pulada, com aviso.
