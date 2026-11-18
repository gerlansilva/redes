# Análises

Cada análise do menu lateral é uma combinação de **unidade** (o que vira nó) e **matriz** (como os nós se ligam). Em todas, o corpus é dividido em períodos, os itens são ligados por similaridade (padrão: índice de equivalência), agrupados e medidos por centralidade e densidade.

| Menu | Pergunta que responde | Unidade / matriz (CLI) |
|---|---|---|
| Visão geral | Qual é o perfil do corpus? | (descritiva) |
| Periódicos | Que periódicos são citados em conjunto? | `ReferenceSources` / `CoOccurrence` |
| Temas | O que se escreve, e quais temas se destacam? | `Words` / `CoOccurrence` |
| Autores | Em quais autores o campo se apoia? | `AuthorsReference` / `CoOccurrence` |
| Referências | Quais obras formam a base intelectual? | `References` / `CoOccurrence` |
| Frentes | Que documentos se ligam por referências comuns? | `References` / `BasicCoupling` |
| Coautoria | Quem publica com quem? | `Authors` / `CoOccurrence` |
| Países | Que países colaboram? | `Countries` / `CoOccurrence` |
| Instituições | Que instituições colaboram? | `Institutions` / `CoOccurrence` |

Parâmetros comuns (padrão): frequência mínima automática (1 na CLI), co-ocorrência mínima 1, similaridade equivalência, algoritmo centros simples, mapeadores núcleo + interseção, tamanho do grupo 2 a 15 itens. Na interface, *Mais opções* traz frequência mínima e as predefinições **Padrão**, **Mais estrita** (frequência 3, co-ocorrência 2: menos temas, mais sustentados) e **Mais ampla** (1 e 1). O modo avançado libera similaridade, algoritmo (inclusive Louvain, de Blondel et al., 2008), mapeadores, co-ocorrência mínima, corte e tamanho do grupo.

## Visão geral descritiva

Quando usar: sempre, primeiro. Mostra documentos, autores, fontes, palavras-chave, instituições, países, referências, citações, crescimento anual e índice de colaboração; produção e citações por ano; autores e fontes mais produtivos; nuvem de palavras; rajadas (Kleinberg, 2002); leis de Lotka, Bradford e Zipf (só no modo avançado quando o corpus é de autor focal). Cada gráfico tem o botão *Salvar gráfico* (SVG, PNG 2x e CSV com dados). Citações ausentes (`Cited by` vazio) são tratadas como ausentes, não como zero, e a tela avisa quando faltam dados.

## Estrutura conceitual: Temas

Pergunta: que temas estruturam o campo e como mudam? Palavras-chave em co-ocorrência (Callon et al., 1991). O mapa de **Evolução temática** (aba padrão, com 2 períodos ou mais) mostra, por transição, quais temas continuam, somem ou surgem, a sobreposição e os itens em comum (Cobo et al., 2011). "Ligação fraca" é um só item em comum com nós principais diferentes. Em *Detalhe por período* (recolhido) ficam Resumo, Rede, Diagrama estratégico e Linha do tempo; os demais (Rede de agrupamentos, Agrupamentos, Índices, Documentos, Dendrograma, Densidade, Duplo mapa, Similitude, Comparar períodos) exigem o modo avançado.

Como ler o **diagrama estratégico**: eixo horizontal = centralidade, vertical = densidade (faixas normalizadas, quadrantes pela mediana). *Motor*: central e desenvolvido; *Básico*: central, pouco desenvolvido; *Nicho*: desenvolvido, isolado; *Emergente*: periférico e pouco desenvolvido (surgindo ou declinando). Esferas = nós; números = agrupamentos.

## Estrutura intelectual: Autores, Referências, Frentes, Periódicos

Cocitação: itens citados juntos pelos mesmos documentos. Autores = autor citado (primeiro autor da obra, por padrão); Referências = obras; Periódicos = fontes citadas. Evolução temática vale para Autores e Referências. **Frentes** liga *documentos* por referências compartilhadas (acoplamento bibliográfico), e fica sem aba de evolução. Limite: poucos itens citados por 2 ou mais documentos deixam a rede sem base (aviso abaixo de 10).

## Estrutura social: Coautoria, Países, Instituições

Redes de quem assina junto. **Países** inclui mapa de colaboração e exige afiliação com país (formato "Instituição, País"); **Instituições** une nomes só quando a variante é inequívoca (caixa, acentos, pontuação, Univ./University, sigla entre parênteses). Em corpus de autor focal, Países e Instituições dizem pouco: aparecem só no modo avançado, com selo "aviso".

## Índices, relatório e exportação

*Índices*: documentos, h, g, hg, Q2, média, soma, mínimo, máximo e citações por grupo. *Relatório completo*: HTML com todas as análises que a base permite, período a período (arquivo único ou pasta). Rajadas e pontos de virada (sigma; Chen, 2006) e o duplo mapa (Chen e Leydesdorff, 2014) aparecem no relatório e no modo avançado.

## Avisos de limite mínimo

Faixa amarela no topo; não bloqueia nada. Limites (`redes/avisos.py`, tabela `LIMITES`):

| Aviso | Limite |
|---|---|
| Período pequeno | menos de 20 documentos |
| Temas fracos | mais de 50% dos temas com no máximo 1 documento |
| Tema dominante | um tema com mais de 40% dos documentos |
| Termo genérico | termo em 35% ou mais dos documentos (períodos com 10 ou mais) |
| Pouca base de cocitação | menos de 10 itens citados por 2 ou mais documentos |
| Autor focal | um autor em mais de 80% dos documentos (1 ou 2 autores focais) |

Como interpretar: aviso = leia o resultado como indício. Para tema dominante ou termo genérico, use *Ignorar e reanalisar* (ou `--ignorar`) e veja os demais temas; para períodos pequenos, junte períodos (*Base*) ou suba a frequência mínima.

## Selo de qualidade

*Qualidade: OK / Atenção / Ruim / Indefinido* resume se o mapa é feito de grupos de verdade (cobertura dos itens em agrupamentos de 5 ou mais itens, fragmentação da rede). Em coautoria há um teto em "Atenção".
