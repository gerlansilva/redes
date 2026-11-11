# Duplo mapa de áreas das revistas

Versão simplificada do *dual-map overlay* do CiteSpace. Mostra de que áreas do
conhecimento vêm as referências do corpus.

- **Esquerda:** as revistas que publicam os documentos do corpus (as `N` que mais citam).
- **Direita:** as revistas citadas por elas (as `M` mais citadas por esse conjunto).
- **Cores e blocos:** cada revista fica numa **área**; as áreas formam blocos com barra colorida.
- **Faixas:** ligam uma área da esquerda a uma área da direita. A largura é o número de
  citações (referências) entre as revistas desenhadas, na mesma escala para todas as faixas.

## Classificação aproximada (leia antes de usar)

A área de cada revista é inferida por **palavras do nome** da revista. Não há base de
categorias (Scopus, WoS, OpenAlex) por trás. Por isso:

- uma revista cujo nome não diz a área (`Cognition`, `Science`) pode ficar em
  "Não classificado" ou numa área inadequada;
- vale a **primeira** área da lista cujo termo aparece no nome (a ordem importa:
  *Educational Studies in Mathematics* fica em Educação, não em Matemática);
- a figura, a nota "Como ler", o método e os relatórios dizem que a classificação é aproximada.

A figura mostra a porcentagem de citações recebidas, de citações feitas e de revistas
**sem área**. A tabela **revista → área → termo que decidiu** acompanha a figura (na tela,
nos relatórios e na resposta da API), com as revistas desenhadas e as 15 sem área mais
frequentes que ficaram de fora, para você conferir e corrigir.

### Corrigir ou ampliar as áreas

As áreas e os termos ficam em `redes/areas.py` (lista `AREAS`). Sintaxe dos termos,
sem considerar acento nem caixa:

| Termo | Casa com |
|---|---|
| `educ*` | palavra que começa com `educ` (educação, education, educational) |
| `math` | a palavra inteira `math` |
| `early childhood` | as palavras seguidas, nessa ordem |
| `=nature` | o nome inteiro é `nature` |

Sem mexer no código, aponte a variável de ambiente `REDES_AREAS` para um JSON:

```json
{"areas": [{"nome": "Física", "cor": "#0284C7", "termos": ["physic*", "optic*"]}],
 "revistas": {"Revista Brasileira de Ensino de Física": "Física"},
 "substitui": false}
```

- `areas` entram antes das padrão (ou no lugar delas, com `"substitui": true`);
- `revistas` fixa a área pelo nome exato, acima de qualquer termo (o termo aparece como `(fixada)`).

## O que entra nas contagens

- Cada referência de cada documento do **corpus completo** (todos os períodos) é uma
  citação da revista do documento para a revista da referência.
- Valem os grupos de revistas citadas editados na base; grupos ocultos e referências sem
  periódico (`Sem fonte`) ficam de fora, e o total delas é informado.
- A análise escolhida na tela não muda o mapa (não depende do tipo de rede).
- Não se aplica quando a base não traz o periódico dos documentos ou o periódico das
  referências: a tela e a API dizem isso com uma mensagem clara.
- Diferenças em relação ao CiteSpace: áreas por nome (não por categorias de base) e faixas
  por contagem simples (sem z-score).

## Onde está

| Parte | Arquivo |
|---|---|
| Classificação por palavras (configurável) | `redes/areas.py` |
| Cálculo (puro) | `redes/duplo_mapa.py` (`calcula`, `le_citacoes`) |
| SVG | `redes/viz/duplo_mapa.py` |
| Rota | `GET`/`POST /api/duplo-mapa` |
| Tela | aba **Duplo mapa** (modo avançado, depois de "Densidade") |
| Exportar | menu Exportar → "Duplo mapa de áreas (SVG)" |
| Relatórios | seção "Duplo mapa de áreas das revistas (corpus completo)" (pasta e arquivo único); no arquivo único aparece uma vez, na primeira análise |
| Método | item numerado em `redes/metodo.py` (`_texto_duplo_mapa`) |

## Rota `/api/duplo-mapa`

Parâmetros: `token` (de uma análise já calculada) **ou** `projeto`/`caminho`;
`max_esq` (3 a 30, padrão 10) e `max_dir` (5 a 40, padrão 16); `baixar=1` devolve o SVG
(`duplo-mapa.svg`) com título. Valores fora do limite são ajustados; valor que não é número
dá erro 400 com o nome do parâmetro.

Resposta: `svg`, `nota`, `avisos`, `areas`, `fluxos` (área → área), `tabela`
(revista → área → termo), `cobertura` (porcentagens sem área, referências sem periódico),
`n_esquerda`, `n_direita`, `total_esquerda`, `total_direita`, `max_esq`, `max_dir`.
