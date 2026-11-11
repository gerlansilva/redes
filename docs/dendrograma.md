# Dendrograma: que análise podemos fazer?

O dendrograma aplica clusterização hierárquica aglomerativa à matriz de
similaridade de um período (palavras, autores, referências, países...). Cada
nó começa sozinho; a cada passo os dois grupos mais próximos se fundem, e a
altura da fusão registra a distância em que isso aconteceu. A distância é
`1 − similaridade` (equivalência por padrão; se a rede tiver valores acima de
1, eles são divididos pelo maior). Par sem aresta tem distância 1.

## O que o dendrograma permite analisar

1. **Estrutura temática hierárquica.** Mostra não só os temas, mas a ordem em
   que eles se formam e quais se aproximam antes de se juntar a outros.
2. **Granularidade.** A altura de corte controla o número de temas: cortar
   baixo dá muitos temas específicos, cortar alto dá poucos e amplos. O
   resultado sugere `n_grupos_sugerido` pelo maior salto entre fusões
   consecutivas (separação mais natural).
3. **Temas aninhados.** Um grupo do corte alto que se divide em subgrupos no
   corte baixo é um tema com subtemas; o mapa estratégico, que usa uma única
   partição, não mostra isso.
4. **Robustez frente à partição da rede.** `comparacao` mede a concordância
   entre o corte e os agrupamentos de Louvain/Centros Simples com o índice de
   Rand ajustado (ARI: 1 = idênticas, ~0 = acaso) e a informação mútua
   normalizada (NMI, de 0 a 1). Concordância alta indica temas estáveis entre
   métodos; baixa indica que o desenho dos temas depende do algoritmo.
5. **Outliers.** Nós que só se juntam perto da raiz (primeira fusão alta) ou
   que ficam isolados no corte são periféricos ou temas distintos do resto.
6. **Qualidade do ajuste.** A correlação cofenética compara as distâncias
   originais com as alturas do dendrograma. Abaixo de 0,6 a árvore distorce a
   rede; tente outra ligação. Com poucos nós (menos de 6) a hierarquia diz
   pouco.

## Escolha da ligação

- `media` (padrão): distância média entre os membros; equilibrada.
- `completa`: distância máxima; grupos compactos, separa mais.
- `simples`: distância mínima; encadeia e favorece grupos alongados.

## Como ler a figura

Raiz à esquerda, folhas à direita. A linha tracejada é o corte; abaixo dela os
ramos têm a cor do grupo e acima ficam em cinza. O raio do ponto da folha
reflete o peso do nó (quando informado). A escala inferior é a altura de
fusão.

## Na ferramenta

Aba **Dendrograma** (modo avançado), rota `/api/dendrograma`, com escolha da
ligação (média, completa ou simples) e do número de grupos; mostra a figura
(baixável em SVG), as frases de interpretação, a correlação cofenética e
ARI/NMI contra a rede. Para não travar, usa os **60 itens mais frequentes** do
período; o aviso diz quantos ficaram de fora. O relatório traz o mesmo bloco por
período.

## Uso

```python
from scimatpy import dendrograma
from scimatpy.viz.dendrograma import svg

res = dendrograma.constroi(resultado.rede, ligacao="media",
                           nomes={no: resultado.rotulo(no) for no in resultado.rede.nos},
                           pesos=resultado.frequencia_nos,
                           grupos_rede={no: i for i, g in enumerate(resultado.grupos)
                                        for no in g.nos})
particao = res.corte(n_grupos=5)          # ou res.corte(altura=0.7)
res.comparacao(particao)                  # {'ari', 'nmi', 'n_comparados', ...}
frases = dendrograma.interpreta(res, 5)   # lista de frases em português
figura = svg(res, n_grupos=5, titulo="Palavras, 2020")
```

`res` é um `dict` serializável em JSON com `nos`, `ordem`, `fusoes`
(`(a, b, altura, tamanho)` no estilo `linkage`: folhas são posições 0..n−1 em
`nos` e as fusões criam os rótulos n, n+1...), `alturas`, `coph`,
`n_grupos_sugerido`, `nomes`, `pesos` e `grupos_rede`.

## Limites

Python puro, O(n³): adequado a redes de até algumas centenas de nós (676 nós
rodam em poucos segundos). Na interface e no relatório o limite é de 60 itens. Em redes esparsas muitos pares têm distância 1 e as
fusões altas empatam; nesse caso o resultado depende da ordem dos nós e a
correlação cofenética tende a parecer alta. O dendrograma é uma leitura
complementar, não substitui a partição usada no mapa estratégico.
