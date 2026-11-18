# Perguntas frequentes

**Meus dados saem da máquina?** Não. O servidor escuta só em `127.0.0.1` e os projetos ficam em `~/redes-projetos`.

**Que arquivo devo exportar?** Scopus (CSV com referências), Web of Science (texto simples), OpenAlex (CSV), Zotero, BibTeX ou RIS. Para cocitação e frentes o arquivo precisa ter referências citadas (Scopus, WoS e OpenAlex trazem; BibTeX, RIS e Zotero em geral não). Veja [formatos-de-entrada.md](formatos-de-entrada.md).

**O que significa a faixa amarela?** Um aviso de limite mínimo: o resultado é válido, mas deve ser lido como indício. Veja [analises.md](analises.md#avisos-de-limite-mínimo).

**Por que Países e Instituições estão marcados "aviso" ou ausentes?** O corpus é de autor focal (um autor em mais de 80% dos documentos). Ligue o *Modo avançado* para vê-los.

**A aba Evolução temática não aparece.** Ela exige 2 períodos ou mais e a análise Temas, Autores ou Referências. Defina períodos na importação (`2008-2014, 2015-2020`) ou em *Base*.

**Onde estão Dendrograma, Densidade, Duplo mapa e Similitude?** No *Modo avançado*, dentro de *Detalhe por período*.

**Todos os temas ficam num grupo só.** Um termo muito genérico domina a rede. Use *Ignorar e reanalisar* ou `--ignorar`, suba a frequência mínima (predefinição *Mais estrita*) ou use o algoritmo Louvain (`--algoritmo Louvain`).

**Palavras-chave com grafias diferentes aparecem separadas.** Use um arquivo de sinônimos (`--sinonimos`) ou `--normaliza-palavras radical` (revise as uniões). Na tela *Base* há sugestões de grafias.

**Citações aparecem como ausentes.** `Cited by` vazio é tratado como ausente, não como zero. Projetos construídos com versões anteriores à 0.1.1 guardam 0: reconstrua com `redes constroi`.

**Como abro um projeto existente?** Na tela de importação, *Abrir projeto existente*, informe o caminho do `.redes`; ou use `redes web --projetos PASTA`.

**O relatório completo abriu em branco ou o navegador bloqueou?** Ele abre em nova aba; libere pop-ups para `127.0.0.1`.

**Como citar?** Veja [CITATION.cff](../CITATION.cff).
