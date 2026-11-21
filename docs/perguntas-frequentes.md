# Perguntas frequentes

**Meus dados saem da máquina?** Não. O servidor escuta só em `127.0.0.1` e os projetos ficam em `~/redes-projetos`.

**Que arquivo devo exportar?** Scopus (CSV com referências), Web of Science (texto simples), OpenAlex (CSV), Zotero, BibTeX ou RIS. Para cocitação e frentes o arquivo precisa ter referências citadas (Scopus, WoS e OpenAlex trazem; BibTeX, RIS e Zotero em geral não). Veja [formatos-de-entrada.md](formatos-de-entrada.md).

**O que significa o selo "Qualidade"?** Ele resume a leitura do resultado (OK, Atenção, Ruim ou Indefinido). Os limites mínimos que o sustentam estão em [analises.md](analises.md#avisos-de-limite-mínimo) e aparecem por extenso no *Relatório completo*.

**Por que Países e Instituições aparecem com atenção?** Quando o corpus é de autor focal (um autor em mais de 80% dos documentos), essas redes dizem pouco; o selo avisa, mas a análise continua disponível.

**A aba Evolução temática não aparece.** Ela exige 2 períodos ou mais e a análise Temas, Autores ou Referências. Defina períodos na importação (`2008-2014, 2015-2020`) ou em *Base*.

**Onde estão Dendrograma, Densidade, Duplo mapa e Similitude?** Na barra de resultados da própria análise (métodos e mapas), junto das demais visões. Cada análise mostra só as abas que se aplicam a ela.

**Todos os temas ficam num grupo só.** Um termo muito genérico domina a rede. Suba a frequência mínima (predefinição *Mais estrita*), troque o algoritmo para Louvain no campo *Algoritmo* ou use `--ignorar` na CLI.

**Palavras-chave com grafias diferentes aparecem separadas.** Use um arquivo de sinônimos (`--sinonimos`) ou `--normaliza-palavras radical` (revise as uniões). Na tela *Base* há sugestões de grafias.

**Citações aparecem como ausentes.** `Cited by` vazio é tratado como ausente, não como zero. Projetos construídos com versões anteriores à 0.1.1 guardam 0: reconstrua com `redes constroi`.

**Como abro um projeto existente?** Na tela de importação, *Abrir projeto existente*, informe o caminho do `.redes`; ou use `redes web --projetos PASTA`.

**O relatório completo abriu em branco ou o navegador bloqueou?** Ele abre em nova aba; libere pop-ups para `127.0.0.1`.

**Como citar?** Veja [CITATION.cff](../CITATION.cff).
