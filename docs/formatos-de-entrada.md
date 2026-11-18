# Formatos de entrada

O Redes reconhece o formato pelo conteúdo do arquivo (a extensão é só o último recurso). Para forçar um formato: `redes constroi arquivo --formato {csv,bibtex,ris,openalex,wos,scopus,zotero}`; na interface, use *Opções > Formato*. Arquivos em UTF-8 (com ou sem BOM) ou Latin-1.

Os exemplos abaixo são mínimos e fictícios; todos foram importados com `redes constroi`. Sem referências, as análises de cocitação e as frentes ficam vazias. Sem afiliação com país, Países e Instituições ficam vazios.

| Formato | Arquivo | Reconhecido por |
|---|---|---|
| CSV tabulado (Redes/WoS) | `.csv` | colunas `Title` e `Authors` ou `Year` |
| Scopus | `.csv` | `Index Keywords`, `Document Type`, `EID` ou `Author(s) ID` |
| OpenAlex | `.csv` | `OpenAlex ID`, `Source Keywords` ou `Author full names` sem colunas da Scopus |
| Zotero | `.csv` | `Item Type` com `Publication Year` ou `Publication Title` |
| Web of Science | `.txt` | linhas `PT ...` |
| BibTeX | `.bib` | entradas `@article{...` |
| RIS | `.ris` | linhas `TY  -` |

## CSV tabulado do Redes

Obrigatórias: `Title`, `Authors`, `Year`. Opcionais: `Citations`, `Journal`, `Doi`, `Type`, `Abstract`, `Affiliations`, `AuthorKeywords`, `SourceKeywords`, `References`. Listas (autores, afiliações, palavras, referências) separadas por `//`. `Citations` vazio conta como ausente, não como zero.

```csv
Title,Authors,Year,Citations,Journal,Doi,Type,Abstract,Affiliations,AuthorKeywords,SourceKeywords,References
Exemplo A,Alves M.A.//Barros T.,2010,3,Revista Exemplo,10.0000/a,article,Resumo ficticio,"Universidade Exemplo Norte, Brazil",estatistica//ensino,educacao,"Modelo A., Livro de exemplo, (2001)"
```

## Scopus (CSV)

Colunas lidas: `Authors`, `Author full names`, `Title`, `Year`, `Source title`, `Cited by` (e variantes), `DOI`, `Affiliations`, `Abstract`, `Author Keywords` (palavras do autor), `Index Keywords` (palavras da fonte), `References`, `Document Type`. Separador de campo: vírgula, ponto e vírgula ou tabulação. Listas separadas por `;`; as referências terminam em `(ano)`. Exemplo completo: [`examples/exemplo_sintetico.csv`](../examples/exemplo_sintetico.csv).

## OpenAlex (CSV)

Colunas: `Authors`, `Author full names`, `Title`, `Year`, `Source title`, `Cited by`, `DOI`, `Affiliations`, `Abstract`, `Author Keywords`, `Source Keywords`, `References`, `OpenAlex ID`; também aceita a exportação do site (`Author` separado por `|`, `Citation count`). Sem `Author Keywords`, procura "Palavras-chave:" no fim do resumo. `--sinonimos` vale como lista de equivalências de palavras.

```csv
Authors,Author full names,Title,Year,Source title,Cited by,DOI,Affiliations,Abstract,Author Keywords,References,OpenAlex ID
"Alves, M., Barros, T.","Alves, Maria; Barros, Tiago",Exemplo A,2010,Revista Exemplo,3,10.0000/a,"Universidade Exemplo Norte, Brazil",Resumo ficticio,estatistica; ensino,"Modelo A., Livro de exemplo, (2001)",W1
```

## Web of Science (texto simples)

Exportação "Plain Text": registros de `PT` a `ER`. Campos: `AU`/`AF` (autores), `TI`, `SO`, `PY`, `TC` (citações), `DE` (palavras do autor), `ID` (palavras da fonte), `CR` (referências), `C1` (afiliações), `AB`, `DI`.

```text
FN Exemplo
VR 1.0
PT J
AU Alves, M
   Barros, T
TI Exemplo A
SO REVISTA EXEMPLO
DE estatistica; ensino
CR Modelo A, 2001, LIVRO EXEMPLO
PY 2010
TC 3
ER

EF
```

## BibTeX

`@article`, `@inproceedings`, `@book` etc. Campos: `author` (`Sobrenome, Nome and ...`), `title`, `journal`/`booktitle`, `year`, `keywords`, `abstract`, `doi`. BibTeX não traz referências citadas.

```bibtex
@article{a1,
  author = {Alves, Maria and Barros, Tiago},
  title = {Exemplo A},
  journal = {Revista Exemplo},
  year = {2010},
  keywords = {estatistica; ensino}
}
```

## RIS

Tags usadas: `TI`/`T1`, `AU`/`A1`, `PY`/`Y1`/`DA`, `JO`/`JF`/`T2`, `KW`, `DO`, `AB`/`N2`, `N1` (de onde sai "Cited By: n"), `C1`, `TY`. Serve também para o RIS do Zotero e do EndNote.

```text
TY  - JOUR
TI  - Exemplo A
AU  - Alves, Maria
PY  - 2010
JO  - Revista Exemplo
KW  - estatistica
ER  - 
```

## Zotero (CSV)

Colunas: `Item Type`, `Publication Year`, `Author` (`Sobrenome, Nome; ...`), `Title`, `Publication Title`, `DOI`, `Abstract Note`, `Manual Tags`, `Automatic Tags`, `Extra` (com "Cited By: n").

```csv
Item Type,Publication Year,Author,Title,Publication Title,DOI,Abstract Note,Manual Tags,Automatic Tags,Extra
journalArticle,2010,"Alves, Maria; Barros, Tiago",Exemplo A,Revista Exemplo,10.0000/a,Resumo ficticio,estatistica; ensino,,Cited By: 3
```

## Arquivo de sinônimos

Uma linha por termo: `canônico = variante; variante`. Linhas e fins de linha com `#` são comentários.

```text
# palavras-chave
Statistical literacy = literacy; statistical literacy
```

Uso: `redes constroi corpus.csv --sinonimos sin.txt --sinonimos-em palavras autores`.
