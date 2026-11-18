# Desenvolvimento

## Ambiente

```bash
git clone https://github.com/gerlansilva/redes && cd redes
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[teste]"
pytest -q
```

Dependências: `networkx`, `numpy`; extra `teste`: `pytest`, `playwright` (os testes de interface usam o Chrome do sistema e são pulados sem ele).

## Estrutura do pacote `redes/`

| Parte | Arquivos |
|---|---|
| Entrada | `loaders/` (um leitor por formato; `__init__.py` reconhece o formato), `references.py`, `normaliza.py`, `words.py`, `text_utils.py`, `paises.py` |
| Projeto (`.redes`, SQLite) | `build.py`, `schema.py`, `kb.py`, `edit.py`, `projeto.py` |
| Análise | `pipeline.py`, `mappers.py`, `network.py`, `similarity.py`, `clustering.py`, `measures.py`, `longitudinal.py`, `qualidade.py`, `avisos.py`, `rajadas.py`, `pivos.py` |
| Bibliometria | `bibliometria.py`, `fluxos.py`, `ies.py`, `aggregate.py` |
| Figuras | `viz/` (halo, estratégico, mapa, dendrograma, densidade, linha do tempo, duplo mapa, similitude) |
| Saídas | `report.py`, `relatorio_unico.py`, `exports.py`, `grade.py` |
| Interface | `api.py` (servidor local), `ui/` (HTML, CSS e JavaScript sem dependências externas) |
| CLI | `cli.py`, `__main__.py` |

`tests/` tem um arquivo por tema (`test_correcaoNN_*`, `test_v2_*`, `test_v3_*`). `tests/conftest.py` traz um projeto sintético mínimo.

## Como contribuir

1. Abra uma *issue* descrevendo o problema ou a ideia.
2. Crie um ramo, escreva um teste que falha e depois a correção.
3. Rode `pytest -q` (todos devem passar) (o teste `test_v2_01_sem_referencias_externas` impede que o nome de outras ferramentas apareça no pacote).
4. Mensagens de commit em português, um tema por commit.
5. Não inclua dados pessoais nem corpora com texto protegido nos testes: use dados sintéticos como `examples/exemplo_sintetico.csv`.

Os limites dos avisos ficam em `redes/avisos.py` (`LIMITES`); os textos de método, em `redes/metodo.py`.
