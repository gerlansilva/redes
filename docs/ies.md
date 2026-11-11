# Unidade Instituições (IES)

Código em `redes/ies.py` e no passo de componentes de
`redes/pipeline.py`. Análise "Colaboração entre instituições (IES)":
instituições que assinam os mesmos documentos.

## União de variantes

Só quando a normalização é inequívoca:

- caixa, acentos, pontuação e espaços não contam;
- ligações (de, of, the, da, do, del) não contam;
- Univ., University, Universidade e Universidad valem o mesmo, e também
  instituto/institute e faculdade/faculty;
- sigla entre parênteses é ignorada;
- país depois de hífen ou barra é ignorado ("Univ. de São Paulo - Brazil").

Não une: ordem de palavras diferente, uma palavra a mais ou a menos, tradução
além das listadas, erro de digitação (isso fica com as sugestões de grafia, que
a pessoa confere). O mesmo nome com países diferentes não é unido entre países.
A grafia adotada é a mais usada; no empate, a com acentos, com menos maiúsculas
e a mais completa.

Cada união fica na tabela **variantes unidas** (nome adotado, variante,
documentos, motivo), na aba **IES** e no relatório.

## Componente mínimo

Antes de aceitar um agrupamento, calculam-se os componentes conexos da rede.
Componentes com menos de N instituições (padrão **3**, parâmetro "tamanho mínimo
do componente") não viram agrupamento e ficam fora dos halos, "sem agrupamento".
A aba e o relatório informam quantos componentes de 2 a N − 1 instituições e
quantas instituições isoladas ficaram de fora.

## Rótulos

Os agrupamentos de IES mantêm o nome da instituição líder (rótulos por tema só
valem para palavras-chave e referências).
