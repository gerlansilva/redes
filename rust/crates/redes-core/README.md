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

- Unidade `Institutions` não está portada (depende de `ies.py`, `paises.py` e
  `sugestoes.py`): devolve `Erro::NaoSuportado`.
- `componente_minimo` (filtro de componentes pequenos em Authors/Countries) e
  centralidades de nó (`grau`, `intermediacao`, ...) não foram portados.
- Em redes de acoplamento o Python mostra, no TSV de grupos, o nome do item cujo
  id coincide com o do documento (quirk de `ResultadoPeriodo.item`); aqui os nós
  de acoplamento levam o título do documento.
- Mapeador `nucleo` em acoplamento básico reproduz o Python: consulta
  `documentos_do_item` com o id do documento.
- Quando o Louvain do Python levanta `KeyError` (rótulo de comunidade que não é
  representante), o Rust devolve erro.
- Arestas de peso zero do acoplamento só são criadas se `min_cooc <= 0` (o
  Python as cria e remove: mesmo resultado, menos memória).
