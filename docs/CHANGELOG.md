# Mudanças

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
