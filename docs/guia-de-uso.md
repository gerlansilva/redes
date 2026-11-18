# Guia de uso

Passo a passo da interface web. As capturas usam dois corpora públicos de artigos (53 e 147 documentos). Quer testar sem dados próprios? Use [`examples/exemplo_sintetico.csv`](../examples/exemplo_sintetico.csv).

## 1. Abrir

```bash
redes web
```

Abre `http://127.0.0.1:8765` (use `--porta` para mudar e `--nao-abrir` para não abrir o navegador).

![Boas-vindas](imagens/01-boas-vindas.png)

## 2. Importar o corpus

Clique em *Começar*, arraste ou escolha o arquivo exportado. Em *Opções* (aberto abaixo) ficam o formato (detectado automaticamente), o nome do projeto e os **períodos**: vazio = divisão automática em 1 a 4 períodos; `unico` = um só; ou faixas como `2008-2014, 2015-2020, 2021-2026`. Clique em *Importar e abrir*.

![Importação com Opções abertas](imagens/02-importacao-opcoes.png)

## 3. Visão geral

Perfil do corpus: totais, produção e citações por ano, autores e fontes, nuvem de palavras, rajadas e leis bibliométricas. O que faltar nos dados (por exemplo, citações vazias) é dito na tela.

![Visão geral descritiva](imagens/03-visao-geral-celi.png)

Cada gráfico tem o botão *Salvar gráfico* (SVG, PNG ou dados em CSV):

![Salvar gráfico](imagens/04-visao-geral-salvar-grafico.png)

## 4. Temas e evolução temática

Em *Temas*, a aba padrão é a **Evolução temática**: cada coluna é um período e cada círculo, um tema; linhas ligam temas que compartilham itens.

![Evolução temática, corpus de 53 documentos](imagens/05-evolucao-tematica-celi.png)

![Evolução temática, corpus de 147 documentos](imagens/06-evolucao-tematica-batanero.png)

Também funciona em janelas menores (1280 x 800):

![Evolução temática em 1280x800](imagens/22-evolucao-tematica-celi-1280x800.png)

### Avisos de limite mínimo

A faixa amarela avisa quando os dados são poucos (período com menos de 20 documentos, tema dominante etc.). Não bloqueia a análise: leia como indício. *Mais opções* traz frequência mínima e as predefinições Padrão, Mais estrita e Mais ampla.

![Aviso de limite mínimo](imagens/16-aviso-limite-minimo-celi.png)

![Aviso de limite mínimo, outro corpus](imagens/17-aviso-limite-minimo-batanero.png)

## 5. Detalhe por período

*Detalhe por período* (recolhido por padrão) abre as visões de cada período, uma por vez.

![Detalhe por período recolhido](imagens/09-detalhe-por-periodo-recolhido.png)

![Detalhe por período aberto, Resumo](imagens/10-detalhe-por-periodo-aberto-celi.png)

![Detalhe por período aberto, outro corpus](imagens/11-detalhe-por-periodo-aberto-batanero.png)

### Diagrama estratégico

Quadrantes Motor, Básico, Nicho e Emergente (veja [analises.md](analises.md)).

![Diagrama estratégico](imagens/07-diagrama-estrategico-celi.png)

![Diagrama estratégico, outro corpus](imagens/08-diagrama-estrategico-batanero.png)

### Rede de co-ocorrência

![Rede em halos](imagens/15-rede-coocorrencia-batanero.png)

## 6. Estrutura intelectual: cocitação de autores

*Autores* mostra quem é citado em conjunto e como esses grupos evoluem. As capturas usam a predefinição *Mais estrita*.

![Cocitação de autores, evolução](imagens/12-cocitacao-autores-evolucao-batanero.png)

![Cocitação de autores, outro corpus](imagens/13-cocitacao-autores-evolucao-celi.png)

## 7. Coautoria

![Coautoria](imagens/14-coautoria-batanero.png)

## 8. Modo avançado

A chave *Modo avançado* (menu lateral) mostra todos os parâmetros, a grade completa de análises e as demais abas.

![Modo avançado](imagens/18-modo-avancado.png)

## 9. Exportar

O menu *Exportar* gera relatórios HTML e dados (TSV, Pajek, GraphML, XML de grupos, SVG).

![Menu Exportar](imagens/19-menu-exportar.png)

## 10. Relatório completo

*Relatório completo* (menu lateral) abre em nova aba um HTML com todas as análises que a base permite, período a período.

![Relatório completo, visão geral](imagens/20-relatorio-completo-visao-geral.png)

![Relatório completo, evolução](imagens/21-relatorio-completo-evolucao.png)

## Base e grafias

A tela *Base* edita períodos e junta grafias de autores, palavras-chave, instituições e países, com sugestões e desfazer.
