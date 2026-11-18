# Linha de comando

```text
redes [--version] {constroi,analisa,grade,web} ...
```

Erros de uso (arquivo ou projeto inexistente, período inválido, porta inválida) saem como `redes: erro: ...` com código 2, sem traceback. Para ver o traceback: `REDES_DEBUG=1`.

O projeto é um banco SQLite `.redes`. A interface web guarda os projetos em `~/redes-projetos/<nome>/dados.redes`.

## `redes constroi ENTRADA`

Importa um corpus e grava o projeto (padrão `dados.redes`).

| Opção | Efeito |
|---|---|
| `--formato {auto,csv,bibtex,ris,openalex,wos,scopus,zotero}` | formato (padrão: reconhecido pelo conteúdo) |
| `--saida SAIDA` | arquivo do projeto |
| `--periodos "2008-2014,2015-2020"` | faixas separadas por vírgula; padrão: intervalo real de anos |
| `--sinonimos ARQUIVO` | arquivo de sinônimos (`canônico = variante; variante`) |
| `--sinonimos-em palavras autores instituicoes periodicos paises todas` | unidades em que os sinônimos valem (padrão: palavras) |
| `--autor-por {abreviado,nome-completo}` | nome curto (`Lopes, C.E.`, padrão) ou coluna `Author full names` quando existir |
| `--normaliza-palavras {nenhuma,radical}` | `radical` une palavras de mesmo radical (statistics/statistical); desligado por padrão, confira as uniões antes de adotar |
| `--manter-repetidos` | não junta registros com o mesmo DOI ou título e ano |
| `--autores-referencia {primeiro,todos,lista}` | quem conta como autor citado: o primeiro autor da obra (padrão), todos, ou a lista inteira como um item |
| `--nao-unir-periodicos` | não junta periódicos que só diferem por caixa, acento ou pontuação (Suma/SUMA) |

## `redes analisa PROJETO`

Executa uma configuração por período e grava TSV. Sem `--saida`, o TSV-resumo vai para a tela.

| Opção | Valores / efeito |
|---|---|
| `--unidade` | `Words`, `Authors`, `References`, `AuthorsReference`, `ReferenceSources`, `Countries`, `Institutions` |
| `--matriz` | `CoOccurrence`, `BasicCoupling`, `AggregatedCouplingBasedOnAuthor`, `AggregatedCouplingBasedOnJournal` |
| `--algoritmo` | `CentersSimples`, `AverageLink`, `CompleteLink`, `SingleLink`, `SumLink`, `Louvain` |
| `--similaridade` | `AssociationStrength`, `EquivalenceIndex`, `InclusionIndex`, `JaccardIndex`, `SaltonCosine` |
| `--min-freq N`, `--min-cooc N` | frequência e co-ocorrência mínimas (padrão 1) |
| `--rede-min N`, `--rede-max N` | tamanho mínimo e máximo dos grupos (padrão 2 e 15) |
| `--corte X` | similaridade mínima para unir grupos hierárquicos |
| `--mapeadores` | `nucleo`, `interseccao`, `secundarios`, `kcore`, `uniao`, `acoplamento` |
| `--tamanho-minimo-agrupamento N` (ou `--componente-min`) | em Authors, Countries e Institutions, componentes menores ficam sem agrupamento (padrão 3 em Institutions, 1 nas demais) |
| `--k-core K` | k do mapeador `kcore` |
| `--palavras` | origem das palavras em Words: `autor`, `fonte`, `adicionada` |
| `--indices` | `h`, `g`, `hg`, `q2`, `media`, `soma`, `minimo`, `maximo` |
| `--ignorar ITEM [ITEM ...]` | descarta itens antes de montar a rede (sem distinguir caixa, acento ou pontuação); vários itens ou separados por `;`, a vírgula não separa |
| `--periodo [NOME ...]` | nomes dos períodos a analisar |
| `--saida ARQ` | TSV-resumo |
| `--saida-grupos ARQ` | TSV com uma linha por grupo (padrão `<saida>_grupos.tsv` quando há `--saida`) |
| `--halo PADRAO` | SVG da rede por período, ex.: `fig/rede_{periodo}.svg` |
| `--estrategico PADRAO` | SVG do diagrama estratégico |

Em `--halo` e `--estrategico`, `{periodo}` vira o número do período (1, 2, ...).

O TSV de grupos traz: periodo, unidade, grupo, nome, itens, n_itens, documentos, centralidade, densidade, quadrante.

Equivalências com a interface: Temas = `Words`; Coautoria = `Authors`; Autores (cocitação) = `AuthorsReference`; Referências = `References`; Frentes = `References` com `--matriz BasicCoupling`; Periódicos = `ReferenceSources`.

## `redes grade PROJETO`

Executa a grade completa de análises (`--saida`, padrão `analises.tsv`). Não grava os `_grupos.tsv`.

## `redes web`

`--porta` (padrão 8765), `--projetos DIR` (padrão `~/redes-projetos`), `--nao-abrir` (não abre o navegador). Escuta só em `127.0.0.1`.

## Exemplos testados

```bash
redes constroi examples/exemplo_sintetico.csv --saida exemplo.redes --periodos "2009-2013, 2014-2018, 2019-2023"
redes analisa exemplo.redes --unidade Words --saida palavras.tsv
redes analisa exemplo.redes --unidade Words --ignorar "Probability" --saida sem_prob.tsv
redes analisa exemplo.redes --unidade Words --algoritmo Louvain --saida louvain.tsv
redes analisa exemplo.redes --unidade Words --halo 'fig/rede_{periodo}.svg' --estrategico 'fig/estrategico_{periodo}.svg' --saida p.tsv
redes constroi corpus.csv --sinonimos sin.txt --sinonimos-em palavras autores --autor-por nome-completo \
      --normaliza-palavras radical --nao-unir-periodicos --saida corpus.redes
```
