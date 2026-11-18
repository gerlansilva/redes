# Redes

**Redes** é uma ferramenta de mapeamento e análise da produção científica
(bibliometria e análise de redes), com interface web local em português. Foi
criada por Gerlan Silva da Silva (UFSCar, ORCID 0000-0002-9996-9983) para as
análises da sua tese de doutorado em Educação, sobre a constituição do campo de
pesquisa em Educação Estatística.

O fluxo inteiro roda em Python (NetworkX e NumPy): ler o corpus, montar a
matriz, normalizar, agrupar, medir, desenhar e relatar. Nenhum dado sai da
máquina.

## O que faz

- Importa CSV tabulado, BibTeX, RIS, OpenAlex, Web of Science e Scopus.
- Unidades de análise: palavras-chave, autores, referências, autores citados,
  fontes citadas, países e instituições.
- Redes de co-ocorrência, acoplamento e acoplamento agregado; similaridades
  (equivalência, associação, inclusão, Jaccard e Salton).
- Agrupamento por centros simples, ligações (média, completa, simples e soma) e
  Louvain; centralidade e densidade; diagrama estratégico; mapas de evolução
  e de sobreposição entre períodos.
- Visão geral descritiva, leis de Lotka, Bradford e Zipf, rajadas, colaboração
  entre países, fluxo autor-país-instituição e relatórios em HTML.
- Exportações: Pajek (`.net`), GraphML, XML de grupos, TSV e SVG.

## Instalação

Requer Python 3.10 ou mais novo.

```bash
python3 -m venv ~/venv_redes
~/venv_redes/bin/pip install .          # ou: pip install -e ".[teste]" para desenvolvimento
~/venv_redes/bin/redes --help           # analisa, constroi, grade, web
```

## Uso

```bash
redes constroi corpus.csv --saida meu_projeto/dados.redes
redes analisa meu_projeto/dados.redes --unidade Words --saida palavras.tsv
redes grade meu_projeto/dados.redes --saida grade.tsv
redes web                               # http://127.0.0.1:8765
```

O projeto é um banco SQLite com a extensão `.redes`. A interface web guarda os
projetos em `~/redes-projetos` (mude com `--projetos`) e escuta apenas em
`127.0.0.1`.

## Testes

```bash
pip install -e ".[teste]"
pytest
```

Os testes de interface usam Playwright; sem o navegador instalado eles são
pulados.

## Licença

GPL-3.0-or-later. Veja `LICENSE`.
