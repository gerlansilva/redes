# Mudanças

## 0.2.0 — 21/11/2026

### Interface
- Menu lateral por tarefa (**Temas**, **Citações**, **Colaboração**) e barra de
  resultados por bloco (**Visão geral**, **Mapas**, **Tabelas**, **Métodos**,
  **Comparar**).
- Cada análise mostra só as visões que lhe dizem respeito: Países (mapa e
  densidade), Instituições (rede e densidade) e Coautoria (rede, dendrograma,
  linha do tempo e densidade).
- O seletor de período começa em **Todos os períodos**; os recortes por período
  vêm depois.
- Frequência mínima automática: quando a rede passa de 14 temas, o corte sobe
  sozinho até 6 para manter a leitura possível; as predefinições *Padrão*,
  *Mais estrita* e *Mais ampla* continuam disponíveis.
- Saíram o **modo avançado**, a aba **Resumo** e o botão *Ignorar e reanalisar*:
  todos os parâmetros ficam à vista na própria análise.
- Saiu a faixa amarela de avisos: os limites mínimos continuam nos dados da API
  e por extenso no *Relatório completo*, mas não repetem o que a tela já mostra.
- Selo **Qualidade** (OK, Atenção, Ruim, Indefinido) resume a leitura do mapa.
- A marca passou a ser usada sozinha (a rede em halos), sem o nome ao lado: vale para o cabeçalho e a capa do *Relatório completo*, para o site e para o README.

### Correções
- Evolução temática: o *Relatório completo* e a aba *Evolução temática* mostravam contagens diferentes para o mesmo corpus (Celi, 2008-2014, 2015-2020, 2021-2026: 3 temas no relatório e 22 na aba). Causa: não era sobreposição nem contagem diferente de "temas", e sim a **frequência mínima**. A aba usava a da tela (1); o relatório ignorava a tela e escolhia sozinho a maior entre 3, 2 e 1 que ainda dava agrupamento em todos os períodos (3, com um tema por período). Agora o relatório gerado pela interface usa os parâmetros da tela (frequência e co-ocorrência mínimas, corte, tamanho da rede, similaridade e algoritmo); sem frequência informada (uso direto da API), mantém a escolha automática e a descreve no texto da seção ("escolhida automaticamente" ou "a mesma da tela").
- O mapa de evolução (relatório e interface) traz na própria figura os parâmetros que definem os temas ("frequência mínima 1 · coocorrência mínima 1 · rede de 2 a 15 itens"), para que qualquer diferença entre duas figuras seja explicável olhando só para elas.
- Mapa de evolução SVG: o rótulo do período do meio (ex.: 2015–2020) encostava no subtítulo; margem superior ampliada (74 para 100 px), legenda em duas linhas e largura mínima proporcional ao número de períodos. Conferido em corpora de 3 e 4 períodos.
- Textos do pacote: referências ao nome do projeto de origem em `grade.py` e no campo "nome do projeto" da interface passam a texto neutro.

### Números
- As análises por período **não mudam** para os mesmos parâmetros (há teste). Muda apenas a frequência mínima padrão do *Relatório completo* aberto pela interface, que passa a ser a da tela em vez da automática; com a automática por padrão na tela (frequência 1), os relatórios de corpora pequenos terão mais temas por período que antes (ex.: Celi, 3 para 22 temas na evolução). Para reproduzir o relatório antigo, informe `minimo_frequencia` igual ao valor antigo (ex.: 3) ou omita-o na API.

## 0.1.1

### Correções
- Louvain: a junção de grupos pequenos usava um mapa nó-grupo desatualizado e dava `IndexError` (`--algoritmo Louvain --rede-min 3`).
- Indicador de instituições: o indicador principal agora usa a mesma regra de união da unidade Instituições (antes divergia: 37 contra 35 em um dos corpora de teste).
- Fluxo Autor-País-IES lê "Authors with affiliations" nos formatos Scopus e OpenAlex.
- Lei de Lotka: curva esperada com 6 algarismos significativos (o gráfico log-log gerava `Infinity` e erro de console).
- `Cited by` vazio vira ausente (não zero) nos leitores CSV, OpenAlex e Scopus; médias e totais ignoram ausentes e a tela avisa. Projetos antigos precisam ser reconstruídos.
- Textos: "Sobre" aponta para a tela Base; nota de método de "Centros simples" descreve o critério real do nó principal.
- Erros de uso da CLI viram `redes: erro: ...` (código 2), sem traceback (`REDES_DEBUG=1` mostra); `constroi` não grava projeto vazio e `analisa` não cria arquivo em caminho inexistente. Projeto `.redes` inválido na interface dá mensagem clara.
- Densidade com poucos itens (ex.: 3 países) responde com aviso em vez de erro HTTP 400.
- Apresentação de termos: `GT12` e `COVID19` preservados, `GeoGebra`, siglas (SIPEM, IRAMUTEQ, SBEM) e numerais romanos em maiúsculas.

### Novidades
- `analisa` grava `<saida>_grupos.tsv` (ou `--saida-grupos`) com uma linha por grupo.
- `constroi`: `--sinonimos-em`, `--autor-por nome-completo`, `--normaliza-palavras radical`, `--nao-unir-periodicos` (unir periódicos que só diferem por caixa, acento ou pontuação passou a ser o padrão); `analisa`: `--ignorar`.
- `redes --version`.
- Nomenclatura própria: classe `ProjetoRedes`, extensão de projeto `.redes`, rótulo "CSV tabulado (Redes/WoS)", créditos metodológicos por artigo original (Kleinberg, 2002; Chen, 2006; Chen e Leydesdorff, 2014).
- Avisos de limite mínimo (faixa no topo; limites em `redes/avisos.py`).
- Evolução temática como aba padrão de Temas, Autores e Referências, com tabela por transição; demais abas em *Detalhe por período* (recolhido); dendrograma, densidade, duplo mapa, similitude e comparação de períodos só no modo avançado.
- Corpus de autor focal: Países, Instituições e leis de Lotka, Bradford e Zipf passam ao modo avançado ou saem do relatório com o motivo.
- Predefinições Padrão, Mais estrita e Mais ampla.
- Ícones SVG nas abas e no menu; *Salvar gráfico* (SVG, PNG e CSV) na visão geral; menu *Exportar*.
- Documentação, capturas de tela, exemplo sintético e `CITATION.cff`.

### Testes
- De 19 (correções) a 160 testes, incluindo testes de interface com Playwright.

## 0.1.0

Versão inicial: importação (CSV tabulado, BibTeX, RIS, OpenAlex, Web of Science, Scopus), redes de co-ocorrência e acoplamento, agrupamentos, diagrama estratégico, visão geral descritiva, mapas de evolução e relatórios em HTML.
