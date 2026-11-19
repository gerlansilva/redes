# redes-core

Núcleo de análise do Redes em Rust (porta de `redes/*.py`): leitura de projetos
`.redes` (SQLite embutido, sem dependências do sistema), rede de co-ocorrência e
de acoplamento (básico e agregado por autor/periódico), similaridades
(equivalência, associação, inclusão, Jaccard, Salton), agrupamento (centros
simples, ligações média/completa/simples/soma e Louvain), medidas de Callon,
quadrantes e índices h/g/hg/q2/média/soma/mín/máx.

```rust
use redes_core::{executar, Parametros, Projeto, Unidade};
let projeto = Projeto::abrir("exemplo.redes")?;
let res = executar(&projeto, &Parametros { unidade: Unidade::Words, ..Default::default() })?;
let json = serde_json::to_string(&res)?;   // grupos, nos, arestas, estrategico, resumo
```

`executar_periodos` roda vários períodos (ou todos). `Parametros` é
serializável (JSON). Linha de comando:

```
redes-cli analisa projeto.redes --unidade Words --algoritmo Louvain --periodo 2011–2016 [--formato tsv|json] [--sem-rede]
```

`--formato tsv` imprime as mesmas colunas de `python3 -m redes analisa`.

### Segunda leva (também com paridade verificada)

- **Instituições** (`Unidade::Institutions`, `ies.rs`, `paises.rs`): instituição de cada
  afiliação, união de variantes inequívocas (caixa, acento, ligações, Univ./University, sigla
  entre parênteses, país depois de hífen; mesmo nome em países diferentes não se une),
  tabela de uniões em `Resultado::ies`. Tabelas de países e palavras vazias vêm de
  `src/tabelas.rs`, gerado por `tests/gera_tabelas.py`.
- **`componente_minimo`** (`Parametros`): componentes com menos nós que isto não viram
  agrupamento (padrão 3 em Institutions, 1 em Authors/Countries). Efeito em
  `Resultado::filtro_agrupamento`. Countries está completa (leitura, filtro e paridade).
- **Centralidades de nó** (`centralidade.rs`): grau ponderado, intermediação de Brandes
  (custo 1/peso), proximidade, autovetor e PageRank.
- **Pontos de virada** (`pivos.rs`): decil superior de intermediação com vizinhos em 2+
  agrupamentos; termos presentes em mais de 50% dos documentos ficam como descritores.
- **Qualidade e selo** (`qualidade.rs`): modularidade Q, Q do Louvain e razão, silhueta
  (por nó, por grupo, média, % negativa), regra do selo ok/atencao/ruim e avisos em pt-BR.
- **Rótulos por tema** (`rotulos.rs`): termos distintivos por LLR de Dunning, só em Words e
  References (`Grupo::tema`); nas demais unidades vale o líder (`Grupo::exibicao`).
  `Grupo::nome_exibido()` devolve um ou outro.
- **Longitudinal** (`longitudinal.rs`): `evolucao(projeto, params, medida, limite_elos)`
  roda todos os períodos e monta elos por sobreposição (as cinco medidas), transições
  (continuam/somem/surgem), matriz de sobreposição entre períodos e `Evolucao::pajek()`.
- **Resultado**: `Resumo::documentos_projeto` (total do projeto) e `Grupo::citacoes`
  (citações do núcleo do tema; no acoplamento básico, dos próprios documentos). Os campos
  novos são `Option`/`#[serde(default)]`: JSON antigo continua válido.

Os cálculos mais caros só rodam se pedidos em `Parametros::extras`
(`centralidades`, `pivos`, `qualidade`, `rotulos`) e vêm em `Resultado::centralidades`,
`pontos_de_virada`, `qualidade` e `Grupo::tema`. Para ter a rede e os conjuntos internos use
`executar_analise` (devolve `Analise`, com os mesmos cálculos como métodos). CLI:

```
redes-cli analisa projeto.redes --unidade Institutions --componente-minimo 3 \
    --extras centralidades pivos qualidade rotulos
redes-cli longitudinal projeto.redes --unidade Words --medida JaccardIndex --pajek evolucao.net
```

### Paridade da segunda leva

`tests/gera_referencia2.py` roda o Python em 47 configurações por projeto (Institutions com
todos os algoritmos e filtros, componente mínimo em Authors/Countries, e as sete unidades/
matrizes com extras ligados) e em 7 mapas longitudinais por projeto com 2+ períodos, e grava
`tests/referencia2/*.json.gz`; `tests/paridade2.rs` compara tudo (nós, grupos, citações, filtro,
uniões de IES, as cinco centralidades de cada nó, pivôs, qualidade e seus avisos, rótulos por
tema, elos, transições, sobreposição e o texto Pajek). Resultado: 0 divergências em 6
projetos (serj_auto, novo142, eecera59_auto, zotero, segat, novo142_auto), 376 análises e
14 mapas. Rodar em release (`cargo test --release -p redes-core`).

Dois detalhes para igualar o Python: a silhueta soma as distâncias de cada nó a cada grupo
em ordem de coluna (como o produto de matrizes do numpy), e `pct_silhueta_negativa` pode
diferir de um item quando a silhueta é zero em teoria (ruído de 1e-16 com sinal que depende da
ordem das somas do BLAS); o teste aceita essa folga, contada pelos empates.

## Paridade com o Python

`tests/gera_referencia.py` roda o Python (`redes.pipeline.executa_periodo`) em
113 configurações por projeto (todos os algoritmos e similaridades, frequência
mínima, tamanho de grupo, mapeadores, origem das palavras, corte, `--ignorar`,
unidades Words/Authors/References/AuthorsReference/ReferenceSources/Countries,
acoplamento básico e agregado) e grava `tests/referencia/*.json.gz`.
`tests/paridade.rs` refaz tudo em Rust e compara: contagens, nós e principal de
cada grupo, centralidade, densidade, faixas, documentos mapeados (soma e soma de
quadrados dos ids), índices de desempenho, frequências e somas das arestas
(tolerância relativa 1e-9). Os projetos `.redes` não vão ao repositório: o teste
os procura em `$REDES_DADOS`, `<repo>/tests/dados` e `/home/claude/t`, e é pulado
se não os achar.

Resultado: 0 divergências em 5 projetos (serj_auto, novo142, eecera59_auto,
zotero, segat), 904 análises.

Para igualar o Python bit a bit foi preciso reproduzir: `sum()` com soma
compensada de Neumaier (Python 3.12+), ordem de inserção dos vizinhos (somas do
Louvain), ordem de iteração de `set` de inteiros do CPython (agregação do
Louvain) e `round` com desempate par.

## Divergências e limites conhecidos

- Ainda não portado: rajadas (Kleinberg) e a medida sigma dos pontos de virada (`rajada` e
  `sigma` ficam `None`); as figuras SVG de `longitudinal.py` (o app desenha a partir de
  `Evolucao`); `qualidade.tabela_grupos` (ano médio dos documentos); sugestões de grafia
  (`sugestoes.py`, só a parte que a unidade Institutions usa foi portada); siglas extras
  pela variável `REDES_SIGLAS` nos rótulos por tema.
- Classes de caracteres Unicode (`\w`, `\d`, categoria Mn) usam `char::is_alphanumeric` e
  faixas de marcas combinantes: iguais ao Python para texto latino, podem diferir em
  escritas raras.
- Em redes de acoplamento o Python mostra, no TSV de grupos, o nome do item cujo
  id coincide com o do documento (quirk de `ResultadoPeriodo.item`); aqui os nós
  de acoplamento levam o título do documento.
- Mapeador `nucleo` em acoplamento básico reproduz o Python: consulta
  `documentos_do_item` com o id do documento.
- Quando o Louvain do Python levanta `KeyError` (rótulo de comunidade que não é
  representante), o Rust devolve erro.
- Arestas de peso zero do acoplamento só são criadas se `min_cooc <= 0` (o
  Python as cria e remove: mesmo resultado, menos memória).
