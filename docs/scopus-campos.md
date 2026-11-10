# Campos e demarcadores da Scopus

Este documento descreve como cada coluna do CSV exportado pela Scopus usa
vírgulas, ponto e vírgula, parênteses e quebras de linha. O objetivo é evitar
que um separador de uma coluna seja aplicado a outra coluna de texto livre —
por exemplo, cortar o título de um artigo porque ele contém `;`, ou cortar uma
referência citada porque ela tem vários autores separados por `;`.

Foi escrito a partir de uma exportação real de 59 registros e 45 colunas
(*European Early Childhood Education Research Journal*, 2007–2026), conferida
coluna por coluna.

## Reconhecimento automático

O Redes não depende do nome do arquivo nem da escolha manual para reconhecer a
Scopus. A ordem é:

1. Ler os primeiros 64 KB e decodificar como UTF-8 com BOM; se falhar, Latin-1.
2. Procurar marcadores de outros formatos: `TY  -` (RIS), `@article{` (BibTeX)
   e blocos `PT`/`ER` (Web of Science).
3. Se for CSV, detectar o separador pela linha de cabeçalho e comparar os
   nomes das colunas. A presença de `Author Keywords` com `Index Keywords`,
   ou de `Document Type`/`EID`, identifica a Scopus.
4. Aplicar o leitor Scopus, que já remove IDs de autor, divide listas por `;` e
   interpreta as referências pelo padrão `);`.
5. Devolver o formato reconhecido para a interface, que mostra no aviso de
   importação: “Base criada: N documentos (Scopus)”.

Se o usuário escolher **CSV SciMAT** por engano, mas o conteúdo for Scopus, o
leitor corrige para Scopus. O mesmo vale para OpenAlex. A escolha explícita só
é mantida quando o conteúdo confirma o formato.

## Regras gerais

1. **O arquivo é CSV no padrão RFC 4180.** Campos com vírgula, ponto e vírgula,
   aspas ou quebra de linha vêm entre aspas duplas. Use um leitor de CSV; nunca
   faça `split(",")` ou `split(";")` na linha inteira.
2. **O separador de campos pode mudar.** A Scopus exporta com vírgula, mas um
   arquivo reaberto e salvo no Excel pode vir com ponto e vírgula ou tabulação.
   Detecte o separador pela linha de cabeçalho, que não tem texto livre.
3. **Cada coluna tem o seu demarcador.** `;` separa listas em autores,
   palavras-chave, afiliações e referências; não separa título, resumo nem
   nome de periódico.
4. **`//` não é separador da Scopus.** Ele é o separador do CSV do SciMAT e
   aparece em URLs e em textos. Aplicá-lo ao CSV da Scopus quebra o dado.
5. **Vírgula nunca separa itens de uma lista Scopus.** Ela aparece dentro de
   nomes de autores, de afiliações, de títulos, de fontes e dos campos internos
   de uma referência citada.
6. **Parênteses não são listas.** Eles delimitam IDs de autor, país de
   publicação e o ano da referência. Vírgulas dentro deles não separam campos.
7. **Não confie na posição das colunas.** Use o nome do cabeçalho e aceite
   variantes (`Source title`/`Source`, `Cited by`/`Cited by (since 2021)`).

## Leitura do arquivo

- Codificação: UTF-8 com BOM é o padrão; aceite Latin-1 como alternativa.
- Separador: vírgula, ponto e vírgula ou tabulação.
- Cabeçalho: 45 colunas na exportação usada como referência.
- Linhas: um registro pode ocupar várias linhas físicas por causa de resumo e
  referências com quebra de linha dentro das aspas.
- Registros sem título devem ser descartados; registros sem autor ou sem ano
  entram, mas não participam das unidades que dependem desses campos.

## Identificação e bibliografia

| Campo | Conteúdo | Demarcador interno | Leitura segura |
|---|---|---|---|
| `Title` | Título do documento | `;`, `:`, `,`, `(`, `)` e quebra de linha são texto | Não dividir; só normalizar espaços |
| `Year` | Ano de publicação | nenhum | Inteiro; pode vir vazio em *in press* |
| `Source title` | Nome do periódico ou evento | `,` e `;` podem fazer parte do nome | Não dividir |
| `Abbreviated Source Title` | Forma abreviada | pontos e vírgulas fazem parte | Não dividir |
| `Volume` | Volume | nenhum | Texto ou inteiro |
| `Issue` | Número | nenhum | Texto ou inteiro |
| `Art. No.` | Número do artigo | nenhum | Texto; costuma vir vazio |
| `Page start` / `Page end` | Páginas | nenhum | Inteiro ou texto (`iii`) |
| `DOI` | DOI | `/`, `.`, `:` | Texto; não dividir |
| `Link` | URL do registro | `//`, `:`, `?`, `&` | Texto; mais de um link pode vir separado por `;` |
| `EID` | Identificador Scopus | `-` | Texto |
| `ISSN` / `ISBN` / `CODEN` | Identificadores | hífen; pode haver mais de um | Texto; não dividir por vírgula |
| `PubMed ID` | PMID | nenhum | Texto |
| `Document Type` | Artigo, editorial, errata etc. | nenhum | Texto |
| `Publication Stage` | `Final`, `Article in Press` | nenhum | Texto |
| `Language of Original Document` | Idioma | pode haver mais de um, separado por `;` | Lista por `;` |
| `Open Access` | Situação de acesso | `;` separa rótulos | Lista por `;` |
| `Source` | Base de origem (`Scopus`) | nenhum | Texto |

## Autores e afiliações

| Campo | Formato | Demarcador | Cuidado |
|---|---|---|---|
| `Authors` | `Sobrenome, Iniciais; Sobrenome, Iniciais` | `;` entre autores; `,` entre sobrenome e iniciais | O formato preferido para a análise |
| `Author full names` | `Sobrenome, Nome (ID); Sobrenome, Nome (ID)` | `;` entre autores; `(ID)` após o nome | Remover o `(ID)` antes de usar |
| `Author(s) ID` | `36967424000; 30667536200` | `;` | Mesma ordem de `Authors` |
| `Affiliations` | `Instituição, Departamento, Cidade, País; ...` | `;` entre afiliações; `,` dentro de cada uma | Não dividir por vírgula |
| `Authors with affiliations` | `Autor, Instituição, ..., País; Autor, Instituição, ...` | `;` entre pares; `,` dentro do par | Ambíguo; não usar para extrair autores |
| `Correspondence Address` | `Nome; Afiliação; email: ...` | `;` entre as partes | `,` dentro do endereço é texto |
| `Editors` | Lista de editores | `;` | Mesmo formato de `Authors` |

`Author full names` pode conter o ID numérico entre parênteses. O ID não faz
parte do nome. Exemplo:

```
Garrity, Sheila (36967424000); Canavan, John (30667536200)
```

vira:

```
Garrity, Sheila; Canavan, John
```

O campo `Authors with affiliations` não deve ser usado para montar a lista de
autores: cada item tem vírgulas da afiliação e o ponto e vírgula pode aparecer
dentro de nomes de instituições. Use `Authors`; se ele não existir, use
`Author full names` sem os IDs.

## Países

O país não tem coluna própria na exportação da Scopus: ele é o último segmento
da afiliação.

```
Universidad de Granada, Granada, Spain; Loughborough University,
Loughborough, United Kingdom
```

Regras usadas pelo Redes:

1. Dividir `Affiliations` por `;` (cada parte é uma instituição).
2. Em cada parte, dividir por `,` e olhar os três últimos segmentos.
3. Reconhecer o país pelo nome, sem diferenciar maiúsculas e acentos
   (`Spain`, `USA`, `United Kingdom`, `Russian Federation`, `Türkiye`).
4. Gravar o nome canônico em português, sem repetição por documento
   (`Espanha`, `Estados Unidos`, `Reino Unido`, `Rússia`, `Turquia`).
5. `England`, `Scotland`, `Wales` e `Northern Ireland` entram como
   `Reino Unido`; `Hong Kong` e `Taiwan` são mantidos separados.

No OpenAlex, a coluna `Country` é usada quando as afiliações não trazem o país.
No Web of Science e no RIS, o país é lido do fim de `C1`. A unidade **Países**
usa os mesmos documentos, matrizes, similaridades e agrupamentos das demais
unidades.

## Palavras-chave e resumo

| Campo | Conteúdo | Demarcador | Leitura segura |
|---|---|---|---|
| `Author Keywords` | Palavras do autor | `;` entre termos; `,` pode fazer parte do termo | Lista por `;`, sem dividir vírgula |
| `Index Keywords` | Palavras de índice (*Keywords Plus*) | `;` entre termos | Lista por `;`; pode vir vazio |
| `Abstract` | Resumo | `;`, `,`, `(`, `)`, `//` e quebra de linha | Texto livre; não dividir |

`Index Keywords` depende do documento e da exportação. Na base analisada, a
coluna veio presente e vazia em todos os 59 registros; não é falha do leitor.
Quando vazia, a unidade **Palavras** usa apenas `Author Keywords`.

## Referências citadas

`References` é a coluna mais ambígua. O texto bruto tem este formato:

```
Alasuutari M., Título do trabalho, European Early Childhood Education
Research Journal, 18, 2, pp. 149-161, (2010); Baumeister R.F.; Leary M.R.,
Título do trabalho, Psychological Bulletin, 117, pp. 497-529, (1995)
```

Problemas:

- `;` separa **referências diferentes**, mas também separa **autores dentro da
  mesma referência** (`Baumeister R.F.; Leary M.R.`).
- `,` separa os campos internos da referência, mas também aparece em títulos,
  nomes de periódicos e nomes de lugares.
- O ano vem no fim, entre parênteses.
- Páginas vêm como `pp. 149-161` ou `p. 4`.
- Volume e número vêm como números soltos antes das páginas.
- Livros podem vir sem editora (`Bryman A., Social Research Methods, (2004)`).

### Fonte repetida

Algumas exportações enriquecidas (OpenAlex processado pelo NotebookLM) repetem
título, fonte, volume e páginas dentro da mesma referência:

```
Batanero Bernabeu C., Estepa A., Godino J.D., Suma, 9, pp. 25-31,
Suma 9 Pp. 25-31, 9, pp. 25-31, (1991)
```

O localizador de fonte do Redes:

1. remove o ano, as páginas do fim e o DOI;
2. divide a referência em segmentos por vírgula;
3. compara a cauda com uma janela anterior, em tokens;
4. aceita o casamento quando só sobram números ou marcadores de volume/página;
5. usa a primeira ocorrência como fonte, separa volume e páginas e descarta a
   repetição.

O resultado do exemplo é
`Batanero Bernabeu C.; Estepa A.; Godino J.D., 1991, Suma, V9, P25-31, `.
A regra só age quando há repetição; referências normais continuam passando
pelo caminho antigo.

Regra de separação usada pelo Redes:

1. Dividir o bloco de referências em `);` — o ponto e vírgula imediatamente
   depois do ano entre parênteses marca o fim de uma referência.
2. Dentro de cada referência, dividir por vírgulas **somente fora de
   parênteses e colchetes**. Isso preserva `Childhood (Copenhagen, Denmark)`.
3. Retirar o ano do fim e as páginas de `pp.`/`p.`.
4. Retirar DOI do fim, se existir.
5. Recolher volume, número e sufixos numéricos do fim.
6. O primeiro segmento é o autor, se parecer nome de pessoa.
7. O último segmento restante é a fonte, se houver volume, páginas ou nome de
   periódico/evento reconhecível.
8. O restante é o título.

O formato final tem seis campos fixos, lidos por posição:

```
AUTOR, ANO, FONTE, Vvolume, Ppáginas, Título
```

Exemplo:

```
Bryman A., 2004, Sem fonte, , , Social Research Methods
```

`Sem fonte` não significa referência descartada: significa que o texto da
Scopus não trouxe periódico, anais ou editora. É o caso de livros e relatórios
em que a exportação omite a editora. A referência continua na unidade
**Referências**; só não contribui para **Fontes de referência**.

## Financiamento, conferência e campos de apoio

| Campo | Conteúdo | Demarcador | Leitura segura |
|---|---|---|---|
| `Funding Details` | `Patrocinador, número do auxílio; ...` | `;` entre patrocinadores; `,` entre patrocinador e auxílio | Lista por `;` |
| `Funding Texts` | Texto corrido do financiamento | `;`, `,`, `(`, `)` | Texto livre; não dividir |
| `Sponsors` | Patrocinadores | `;` | Lista por `;` |
| `Conference name` | Nome do evento | `,`, `;`, `:` | Texto livre; não dividir |
| `Conference date` | Data do evento | `,` e intervalos | Texto livre; não dividir |
| `Conference location` | Cidade, país | `,` | Texto livre; não dividir |
| `Conference code` | Código | nenhum | Texto |
| `Molecular Sequence Numbers` | Números de sequência | `;` | Lista por `;`; costuma vir vazio |
| `Chemicals/CAS` | Produtos químicos | `;` | Lista por `;`; costuma vir vazio |
| `Tradenames` | Marcas | `;` | Lista por `;`; costuma vir vazio |
| `Manufacturers` | Fabricantes | `;` | Lista por `;`; costuma vir vazio |

## Variantes de cabeçalho

A Scopus muda o nome de algumas colunas entre versões e entre exportações:

- `Cited by`, `Cited by (since 2016)`, `Cited by (since 2021)`: casar pelo
  prefixo `Cited by`, não pelo nome exato.
- `Source title` e `Source`: aceitar os dois.
- `Authors` e `Author full names`: preferir `Authors`; usar o segundo como
  alternativa.
- `Index Keywords` pode não vir na exportação; `Author Keywords` pode vir
  vazio.

## O que o Redes faz hoje

- `scimatpy/loaders/scopus.py`: detecta codificação e separador, lê o CSV,
  remove IDs de autores e converte as referências.
- `scimatpy/loaders/__init__.py`: detecta o formato pelo conteúdo, não pela
  extensão. Um `scopus.csv` não cai mais no leitor CSV do SciMAT; um arquivo
  Scopus salvo como `.txt` também é reconhecido.
- `scimatpy/api.py`: corrige o formato genérico `csv` para Scopus quando o
  conteúdo é Scopus e devolve `formato` no resultado da importação.
- `scimatpy/ui/app.js`: envia o formato escolhido ou `auto`; o servidor decide
  pelo conteúdo e a interface mostra o formato reconhecido.
- `scimatpy/paises.py`: reconhece o país no fim das afiliações, no `Country` do
  OpenAlex e nos endereços do WoS/RIS, e grava o nome canônico em português.
- `scimatpy/references.py`: separa referências por `);`, divide campos por
  vírgulas fora de parênteses e monta os seis campos fixos.
- `scimatpy/build.py`: converte as referências, agrupa autores, fontes e
  palavras e grava o projeto `.redes`.

Testes que cobrem esses casos:

- CSV da Scopus com vírgula, com ponto e vírgula e com BOM.
- `Cited by (since 2021)`.
- Referência com vários autores separados por `;`.
- Vírgula dentro de parênteses no nome da fonte.
- Autor com ID numérico em `Author full names`.
- Detecção de formato pelo conteúdo.

## Outras bases: diferenças que quebram o mesmo campo

| Base | Autores | Palavras-chave | Referências | Cuidado |
|---|---|---|---|---|
| CSV do SciMAT | `//` | `//` | já convertidas | Não usar `;` |
| OpenAlex CSV | `Authors` com vírgulas; `Author full names` com `;` | `;` | texto livre, mesmo leitor da Scopus | `Author full names` também é lista |
| Web of Science texto | um `AU` por linha | `DE` e `ID`, com `;` ou barra vertical | um `CR` por linha | campos de duas letras e continuação de linha |
| RIS | um `AU` por linha | um `KW` por linha | nem sempre presente | tags de duas letras, sem separador de lista |
| BibTeX | `and` entre autores | `keywords`, com `;` ou `,` | nem sempre presente | chaves e aspas aninhadas |

## Checklist para uma nova exportação

1. Abrir o arquivo e confirmar codificação e separador.
2. Listar as colunas e classificar cada uma como escalar, lista ou texto livre.
3. Procurar o separador de lista **dentro** de campos de texto livre; se
   aparecer, não usar esse separador na coluna.
4. Testar os quatro casos que mais quebram:
   - título com `;`;
   - fonte com vírgula dentro de parênteses;
   - referência com vários autores separados por `;`;
   - campo vazio (`Index Keywords`, `Art. No.`, `ISBN`).
5. Importar com `--formato auto` e conferir as contagens de documentos,
   autores, palavras, fontes e referências.
6. Comparar uma amostra de referências convertidas com o texto bruto.
