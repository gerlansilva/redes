# Ajustes no Redes e na base Celi Lopes

Data: 20/11/2026. Projeto de trabalho: `dados/celi_corrigido.redes` (cópia de `dados/celi.redes`, que segue intacto).

## 1. Mudanças no código

### 1.1 Frequência mínima por tipo de análise

Antes o relatório completo escolhia uma frequência única para todas as análises (começava em 3 e descia até 1 apenas se não houvesse nenhum agrupamento). Com 53 documentos, a frequência 3 deixava todas as seções com um agrupamento só — em palavras-chave, uma rede de 3 nós.

Agora cada unidade tem uma frequência própria, em `redes/api.py:1504`:

| Análise | Frequência padrão |
| --- | --- |
| Palavras-chave | 2 |
| Cocitação de referências | 2 |
| Cocitação de autores | 2 |
| Periódicos citados | 2 |
| Frentes (acoplamento bibliográfico) | 2 |
| Colaboração entre autores | 1 |
| Países | 1 |
| Instituições (IES) | 1 |

A candidata só é trocada quando o resultado fica fraco (período com itens e nenhum agrupamento, ou menos de 15 nós agrupados) ou poluído (mais de 8 agrupamentos num período, ou metade deles com um documento só). Entre as candidatas aceitáveis fica a mais próxima do padrão. Os limites estão em `redes/api.py:1515-1517`; a avaliação em `_avalia_frequencia` (`redes/api.py:1520`) e a escolha em `_escolhe_frequencia` (`redes/api.py:1543`).

O texto da seção passou a dizer se a frequência é o padrão do tipo de análise ou se foi ajustada.

### 1.2 Plural nas legendas e dicas

As dicas dos gráficos escreviam "1 documentos" e "1 citações". Corrigido em:

- `redes/viz/descritiva.py:163` (nuvem de palavras-chave)
- `redes/viz/descritiva.py:213` (produção e citações por ano)
- `redes/viz/densidade.py:276` (mapa de densidade)

### 1.3 Testes

`PYTHONPATH=tests python -m pytest tests -q`: 749 passam, 53 pulados. Continua falhando apenas `tests/test_v3_05_icones.py::test_menu_com_rotulo_curto_e_nome_completo_no_titulo`, que é anterior a estas mudanças (o rótulo curto do menu "Cocitação de autores" tem espaço).

## 2. Correções na base

Todas as correções foram feitas por fusão de grupos (`edit.agrupa_sugestoes`), com cópia de segurança automática dentro de `dados/.celi_corrigido.redes.desfazer/`.

### 2.1 Palavras-chave: 109 → 104 grupos

| Mantida | Fundidas | Motivo |
| --- | --- | --- |
| STATISTICS-EDUCATION | EDUCATION-STATISTICS | mesmas palavras em outra ordem |
| STATISTICS-TEACHING | TEACHING-STATISTICS | mesmas palavras em outra ordem |
| (AUTO)BIOGRAPHICAL-NARRATIVE | AUTOBIOGRAPHICAL-NARRATIVES | grafia muito parecida |
| ENVIRONMENTAL-MATHEMATICAL-MODELING | ENVIRONMENT-MATHEMATICAL-MODELING | grafia muito parecida |
| MATHEMATICS-EDUCATION-AND-CHILDHOOD | MATHEMATICS-EDUCATION-IN-CHILDHOOD | grafia muito parecida |

Efeito direto: o termo "Education statistics", que aparecia como tema isolado em 2008–2014, deixou de existir como item separado.

### 2.2 Referências: 1.131 → 1.067 grupos

52 obras foram fundidas, absorvendo 64 referências duplicadas. Regra: mesmo primeiro autor e mesmo ano, com similaridade de 0,93 ou mais na string completa; a obra mantida é a citada pelo maior número de documentos (empate: a string mais longa). Lista completa em `dados/corrigido/fusoes-referencias.tsv`.

Exemplos: "Gal I., 2002, International Statistical Review" em quatro versões; "Passos C., 2006, Quadrante" em cinco; "Lopes C.E., 2013, Bolema" com diferença só de caixa; "Freire P., 1996, Pedagogia da autonomia" em quatro.

### 2.3 Autores citados: 613 → 566 grupos

44 conjuntos fundidos, absorvendo 47 grafias. Duas regras:

1. Lista explícita para transliteração e erro de digitação: Vygotsky (Vigotski/Vygotsky/Vigotsky), Coutinho (C.Q.S./C.Q.E.S./C.D.Q.E.S.), Passeggi (M.C./M.D.C./C.), Placco/Placo, Furlanetto/Furlanatto, Tardif/Tardiff, Burrill/Burril, delMas/Delmas.
2. Iniciais ausentes, quando o alargamento é único: "Wild C." → "Wild C.J.", "Garfield J." → "Garfield J.B.", "Grando R." → "Grando R.C.", "Lopes C." → "Lopes C.E.", entre outros.

Não foram unidos, por ambiguidade: "Mendonca L." (L.O. ou L.D.O.), "Monteiro C." (C.E. ou C.E.F.), "Santos S." (S.A., S.S. ou S.S.S.) e "Souza L." (L.O., L.D.O. ou L.M.D.). Também ficaram de fora nomes com segundo sobrenome composto (por exemplo "Silva J.") para não fundir homônimos. Lista completa em `dados/corrigido/fusoes-autores-citados.tsv`.

## 3. Efeito nos mapas

Agrupamentos por período, antes (base original) e depois (base corrigida), com a nova política de frequência:

| Seção | 2008–2014 | 2015–2020 | 2021–2026 |
| --- | --- | --- | --- |
| Palavras-chave | 2 → 3 | 2 → 2 | 1 → 1 |
| Colaboração entre autores | 1 → 1 | 1 → 1 | 1 → 1 |
| Cocitação de referências | 2 → 3 | 5 → 6 | 3 → 5 |
| Cocitação de autores | 3 → 3 | 6 → 6 | 5 → 5 |
| Frentes (acoplamento) | 1 → 1 | 3 → 4 | 3 → 3 |
| Periódicos citados | 3 → 3 | 4 → 4 | 3 → 3 |

Itens por período na cocitação de referências caíram de 231/442/527 para 222/431/502, e na cocitação de autores de 145/263/320 para 139/244/304 — é o efeito esperado da deduplicação (menos nós, mesmos documentos).

Temas de palavras-chave na base corrigida, frequência 2 (arquivo `dados/corrigido/temas_grupos.tsv`):

- 2008–2014: "Statistics education" (8 documentos, 9 itens, tema motor); "Statistics education research" (2 itens); "Stochastic education" (2 itens).
- 2015–2020: "Statistics education" (13 documentos, 15 itens, motor); "GeoGebra/ensino de estatística" (2 itens).
- 2021–2026: "Statistics education" (14 documentos, 14 itens, motor), agora com narrativas (auto)biográficas, agência, IRAMUTEQ, probabilidade e formação.

## 4. Arquivos gerados

- `dados/celi_corrigido.redes` — base corrigida.
- `dados/corrigido/relatorio-completo.html` — relatório completo (6 seções; países e IES ficam de fora por serem pouco informativos num corpus de autora focal).
- `dados/corrigido/temas.tsv`, `temas_grupos.tsv` e `Words-{1,2,3}.svg` — palavras-chave.
- `dados/corrigido/{Authors,References,AuthorsReference,ReferenceSources,Countries,Institutions}.tsv` e `*_grupos.tsv` — demais análises.
- `dados/corrigido/evolucao-tematica.svg`, `sobreposicao-tematica.svg`, `evolucao-tematica.net` — mapa longitudinal.
- `dados/corrigido/fusoes-*.tsv` — registro de cada fusão.
- `dados/relatorio-completo.html` e `dados/analises/` — versão anterior (base original), mantida para comparação.
- `dados/analises/temas_freq1.tsv` — variante de palavras-chave com frequência 1, para conversa na entrevista.

## 5. Como reproduzir

```bash
cd ~/Documents/redes
~/venv_redes/bin/redes web                       # interface em http://127.0.0.1:8765
~/venv_redes/bin/redes analisa dados/celi_corrigido.redes --unidade Words \
  --min-freq 2 --saida dados/corrigido/temas.tsv \
  --halo "dados/corrigido/Words-{periodo}.svg"
~/venv_redes/bin/redes grade dados/celi_corrigido.redes --saida dados/corrigido/grade.tsv
```

O relatório completo é gerado pela interface (menu Exportar) ou por `api.gera_relatorio_completo`; ele grava `relatorio-completo.html` com as figuras embutidas.

## 6. Pendências e ressalvas

- "Referências distintas" na visão geral continua 1.131: a tabela conta strings de citação, não obras depois da deduplicação (1.067 grupos). As análises usam os grupos.
- As tabelas de ranking da visão geral leem o nome do item, não o do grupo. Por isso "Vygotsky" ainda pode aparecer em três linhas numa listagem de autores citados, embora a cocitação já use o grupo unido.
- Pares de referências com similaridade entre 0,90 e 0,93 não foram fundidos. Há um caso duvidoso em 2011 ("A Educação Estocástica nas aulas de Matemática" contra "A estocástica no currículo de matemática"), que pode ser dois trabalhos distintos.
- Os quatro autores ambíguos listados em 2.3 precisam de conferência manual.
- Países e IES continuam fora do relatório: com um autor em 100% dos documentos, essas análises não sustentam leitura.
- Os dois artigos de 2026 têm zero citações e o crescimento anual de 3,9% é artefato dos extremos da série (1 artigo em 2008).

## 7. Correções na interface (20/11)

Depois da entrevista de teste, dois problemas na tela de coautoria:

**7.1 Layout de halos espalhava redes pequenas.** Em `redes/viz/halo.py`:

- o anel dos agrupamentos deixou de ter raio fixo (0,34 da largura) e passou a ser calculado pelo diâmetro somado dos halos, limitado a 0,34. Com dois grupos, eles ficam lado a lado em vez de nas duas pontas da figura;
- nós sem agrupamento passaram a ficar na órbita do agrupamento com que mais se ligam (arestas compartilhadas), não numa circunferência do tamanho da tela. Isso encurtou as arestas longas;
- o enquadramento passou a ser feito uma única vez, no fim, escalando centros, halos e nós juntos (até 1,9×). Antes só os centros eram esticados (até 2,2×), o que abria vãos entre grupos que já estavam na distância certa;
- a mola de refinamento dos nós soltos só roda a partir de 24 soltos, quando a órbita por grupo fica apertada. Abaixo disso ela desmanchava a órbita e espalhava o desenho.

Efeito no projeto `celii` (53 documentos, 1 período): a rede de coautoria passou de x 68–943 / y 196–661 para x 184–814 / y 144–695, com os dois agrupamentos adjacentes.

**7.2 Rótulos vinham desligados.** Em `redes/ui/app.js`, o padrão da rede em halos passou de `nenhum` para `principais` (estado inicial, reset e reabertura do projeto). Quem quiser o mapa sem nomes troca no seletor "Rótulos".

**Frequência mínima de autores mantida em 1.** A frequência 2 reduziria a rede de 29 para 14 autores e deixaria de fora justamente Fitzallen e Pfannkuch, que assinam um artigo cada e são as duas parcerias internacionais do corpus. Para a conversa sobre inserção internacional, os dois precisam aparecer.

**7.3 Nós sobrepostos dentro do halo.** A posição interna vinha de uma mola normalizada num círculo cujo diâmetro dependia só do número de nós. Em rede de estrela (Celi e vários coautores), as folhas se acumulavam no centro e os círculos se sobrepunham. Agora o diâmetro mínimo é calculado a partir do raio dos próprios nós: para cada par, o desenho exige `raio_a + raio_b + 5` de distância, e o halo cresce até caber. Verificação na base `celii`, autores, frequência 1: menor folga entre dois nós passou a 10,2 px; palavras-chave 2021–2026, 15,8 px; referências, 16,3 px. Nenhum par se toca.

Com isso o enquadramento final pôde ampliar o desenho (até 2,6× com um ou dois grupos, 1,9× com mais), porque os nós já não dependem de um raio fixo para se separar.

**7.4 Auditoria nas demais redes.** Verifiquei todas as unidades nos dois projetos (base corrigida com 3 períodos e o projeto `celii` com 1): palavras-chave, autores, países, instituições, autores citados, referências em cocitação e referências em acoplamento (frentes). Medida: menor folga entre dois nós (negativa = sobreposição), menor folga entre halos, nó fora do próprio halo e halo cortado pela borda.

- Sobreposição de nós: nenhuma em nenhuma unidade. A menor folga geral é 2,0 px, no caso mais denso (autores citados no `celii`: 162 nós em 12 grupos).
- Nós fora do halo: nenhum. A causa era a normalização pela maior coordenada; um nó na diagonal ficava a √2 do raio. Passou a normalizar pela distância.
- Halos cortados pela borda: nenhum.
- Halos sobrepostos: um caso, o mesmo de 162 nós (13,5 px de sobreposição). O desenho continua legível porque os nós foram separados por um último ajuste; o alerta de "Qualidade: atenção" da própria tela recomenda reduzir os nós exibidos.

Acréscimos em `redes/viz/halo.py`: folga mínima entre nós proporcional ao tamanho do grupo (5 px até 40 nós, 3 px até 90, 1,5 px acima), raio do halo incluindo o maior nó do grupo e ajuste final que separa apenas os nós, sem mover centros.

## 8. Organização das redes — decisão com três agentes

Três auditorias independentes foram feitas: layout (algoritmo), UX (tela) e medição empírica em 72 execuções nos corpora Celi corrigido, `celii` e SERJ. Os relatórios estão em `dados/redes-decisao/layout.md` e `dados/redes-decisao/ux.md`; a medição ficou em `/tmp/layout_exp/RELATORIO.md`.

### O que foi decidido e aplicado

1. **Halos continuam sendo o padrão.** A proposta de trocar automaticamente para mapa de força acima de 20 grupos foi recusada nesta rodada: muda a identidade do app e do relatório, não foi testada com leitores e a medição mostrou que o ganho é só visual. Fica registrada como evolução possível, atrás de uma opção.

2. **Pós-passe de separação depois do crescimento dos halos** (`redes/viz/halo.py`). A verificação anterior rodava antes de o halo crescer para conter os nós; o crescimento podia invadir o vizinho sem nova checagem. Agora, se a folga de 6 px falhar, os halos são separados transladando centro e nós juntos. Guardas: deslocamento máximo de 40 px, ocupação de halos até 80% e reversão se algum par de nós encostar. Efeito medido: 11 das 12 redes com sobreposição ficaram com folga positiva; Celi e as 36 análises dos três períodos não mudaram; `celii` em autores citados passou de −13,5 px para +8,0 px.

3. **Enquadramento pelo que é desenhado** (`redes/ui/app.js`). A área do servidor (980×780) deixava ~35% de vazio de cada lado num canvas de 963×520. Agora o cálculo usa a caixa real dos halos e nós visíveis, com margem de 6 px, e centraliza no canvas. A altura do canvas subiu de 460 para 520 px.

4. **Rótulos principais por halo, não globais.** Antes os 16 maiores graus podiam cair em 6 dos 14 halos, deixando 8 halos sem nome. Agora sai um campeão por halo e só depois se completam as vagas. O texto também é posicionado fora do raio do nó (direita, acima, esquerda, abaixo) e não pode invadir outro rótulo.

5. **Corte de nós comunicado.** Quando a rede passa de 300 nós, a tela abre em top 200 e mostra "Mostrando os 200 nós mais conectados de 443. Ver todos". O link volta para todos. Halos de grupos sem nenhum nó visível deixam de ser desenhados.

6. **Controles mais claros.** "Arestas" e "Halos" passaram a mostrar/ocultar; "Ajustar" virou "Reenquadrar"; "SVG" virou "Figura SVG"; o canvas ganhou dica de arraste/rolagem e o reset de zoom ganhou rótulo acessível.

7. **Carregamento da rede.** Se a prévia ainda não tem token, a aba Rede deixa de se marcar como carregada e tenta de novo ao abrir.

### O que foi recusado ou adiado

- **Teto de 20 grupos na legenda**: a medição mostrou que a legenda de 60 não espremeu nenhuma figura (no máximo 36% da largura). Reduzir para 20 esconderia grupos sem ganho. Mantido 60, com "+N (ver tabela)".
- **Corte automático de nós no layout**: a política de frequência já evita os casos de 400–900 nós; no app o corte é de exibição. Não vale impor corte na figura publicada.
- **Desligar halos automaticamente**: não muda a geometria e perde o envelope do grupo; continua opção manual.
- **Mapa de força sem halos (regime F) e grade (regime G)**: documentados como evolução, não implementados.

### Limitações

A legibilidade das variantes foi medida por geometria, não por teste com leitores. O caso de 898 nós do SERJ continua sem solução de layout puro — só o corte de nós resolve. A fonte da legenda no relatório (12 px no viewBox, ~6,7 px renderizada) não foi alterada nesta rodada.

## 9. Filtro de agrupamentos na rede (20/11)

A versão antiga da tela de rede tinha um filtro de agrupamentos. Ele foi restaurado na legenda da rede em halos, no mesmo lugar em que os grupos já eram listados.

### O que mudou

- Cada item da legenda agora tem três partes: o **ponto colorido** (botão que mostra ou oculta o agrupamento), o **nome** (abre os detalhes, como antes) e a **quantidade de nós**. O ponto ganhou 5 px de área clicável em volta sem aumentar o desenho.
- O cabeçalho da legenda mostra "Agrupamentos", a contagem "N de M" e os atalhos **todos** e **nenhum**.
- Quando um agrupamento é ocultado, saem da rede os nós, as arestas internas e cruzadas, os rótulos, o selo numerado e o halo. As arestas entre halos também somem quando uma das pontas está oculta. O enquadramento (`Reenquadrar`) e o corte por grau passam a considerar só o que está visível.
- Agrupamentos ocultos continuam esmaecidos na legenda e podem ser religados pelo mesmo ponto; "todos" restaura a rede inteira.
- O filtro zera ao trocar de análise, de período ou de projeto, para não transportar uma seleção para outra rede.
- Texto de Ajuda acrescentado: "Na rede, clique no ponto colorido da legenda para mostrar ou ocultar um agrupamento; o nome abre os detalhes."

Arquivos: `redes/ui/app.js` (estado `gruposOcultos`, funções `alternarGrupoRede`, `filtrarGrupos` e `atualizarLegendaRede`, filtro no desenho e nos selos), `redes/ui/style.css` (cabeçalho, botões e estado oculto) e `redes/ui/index.html` (Ajuda).

### Verificação

Reproduzi a configuração da captura antiga: `celii`, cocitação de referências, frequência mínima 2 — **9 agrupamentos e 115 nós**. Com um grupo oculto, a legenda passa a "8 de 9" e os 15 nós daquele grupo somem com halo, selo e rótulos; com "nenhum", restam apenas os 2 nós sem agrupamento. Capturas em `/tmp/opencode/prev/filtro-9grupos*.png`.

Testes: 749 passam, 53 pulados; permanece só a falha anterior de `tests/test_v3_05_icones.py::test_menu_com_rotulo_curto_e_nome_completo_no_titulo`, que não envolve esta mudança.

## 10. Organização da rede e das ferramentas (20/11)

Quatro pareceres independentes — interface, visual, tarefas de entrevista e benchmark (VOSviewer, SciMAT, biblioshiny, Gephi, CiteSpace) — foram consolidados em `dados/redes-decisao/consolidado.md`. A decisão: a figura manda; os grupos ficam numa faixa abaixo do canvas, não numa coluna lateral fixa.

### Por que faixa, não coluna

A coluna lateral de 240 px foi recusada como padrão: tira ~25% da largura do canvas em 1.280 px, desloca o olhar do participante para o painel do pesquisador e não resolve o problema medido (sobra de área, não falta de coluna). Com 9 grupos, a faixa cabe em 3 linhas de 4 colunas nos 963 px atuais. Acima de 16 grupos, a faixa rola dentro de um teto de 220 px; a coluna automática fica registrada como evolução, não como padrão.

### Dois gestos separados

- **Ponto colorido**: oculta/mostra o grupo. Remove nós, arestas, rótulo, selo e halo; o estado vivo acompanha.
- **Nome do grupo**: destaca o grupo (cor cheia; resto a 16%), mantém as conexões externas e não redesenha o mapa. Segundo clique ou "Todo o mapa" volta ao todo.
- **Seta ›**: abre os detalhes, sem tirar o clique principal do contexto.

### O que mudou no app

`redes/ui/index.html`: cabeçalho com `Reenquadrar` e `Figura completa (SVG)`; linha de estado; barra com `Rótulos`, `Nós exibidos` e `Ajustes` (arestas/halos); sobreposição "todos ocultos"; remoção do reset de zoom duplicado.

`redes/ui/app.js`: metadados com recorte e frequência; estado vivo (`role=status`); `calcularVisiveis()` compartilhado por desenho, área e enquadramento; foco não destrutivo; ocultação com reenquadramento automático; contagem dinâmica em `Nós exibidos`; um rótulo por halo quando há foco; selos 12 px; estado "todos ocultos"; exportação rotulada como figura completa.

`redes/ui/style.css`: título 15 px, status 12 px, legenda 12,5 px, controles 11,5–12 px; contraste de `--tinta-suave` para `--tinta-fraca`; alvos maiores (ponto 27 px efetivos, linha 38 px, botões 32 px, zoom 36 px); grupo oculto tachado e com ponto vazado; grupo em foco com fundo lavanda; disclosure de ajustes; estado vazio centralizado.

### Verificação

Caso `celii` > Referências > freq. 2: 9 grupos, 115 nós, 1.066 arestas. Estado inicial: `9 de 9 grupos · 115 de 115 nós · 1.066 arestas · 2 fora dos grupos`. Ocultar o grupo 1: `8 de 9 · 100 de 115`. Foco no grupo 1: 15 nós e 125 conexões, resto atenuado, só o campeão rotulado. "Ocultar todos": frase e botão de retorno. Capturas em `/tmp/opencode/prev/nova-rede-topo.png`, `nova-rede-foco2.png`, `nova-rede-oculto2.png`, `nova-rede-tudo-oculto.png` e `nova-rede-ajustes.png`.

Testes: 749 passam, 53 pulados; permanece só a falha anterior de `tests/test_v3_05_icones.py::test_menu_com_rotulo_curto_e_nome_completo_no_titulo`.

### Adiado

Exportar o estado visto (PNG/SVG filtrado), coluna lateral automática acima de 16 grupos, painel de seleção persistente, teclado completo com roving tabindex, modo apresentação e separação visual entre números de pontos de virada e números de grupos.

## 11. Filtro de agrupamentos: isolar, não ocultar (20/11)

Substitui o comportamento descrito nas seções 9 e 10. Ao usar o filtro, ficou claro que apagar o agrupamento removia justamente o que a conversa precisava mostrar. A regra passou a ser: **o grupo nunca sai do mapa; somem apenas as linhas que o ligam aos outros grupos**.

### O que muda

- **Ponto colorido**: isola o agrupamento. Nós, halo, selo, rótulos e arestas internas continuam; saem as arestas entre esse grupo e os demais e as linhas dele para nós fora dos grupos. Clicar de novo religa.
- **Nome do grupo**: continua destacando o grupo no mapa (resto a 16%).
- **Seta ›**: continua abrindo os detalhes.
- **`isolar todos` / `religar todos`**: substituem `ocultar todos` / `mostrar todos`. Com todos isolados, o mapa vira nove ilhas, sem perder nenhum nó.
- O estado vivo passou a `9 grupos · 115 de 115 nós · 1.066 arestas · 2 fora dos grupos · 1 de 9 grupos isolados`; a contagem de grupos não cai mais.
- A sobreposição "Todos os agrupamentos estão ocultos" foi removida, porque não existe mais canvas vazio por filtro.
- `Reenquadrar` não é mais disparado ao isolar: nada muda de lugar; o enquadramento só depende de `Nós exibidos`.
- Na faixa, grupo isolado ganha fundo neutro, nome em tom secundário e anel tracejado no ponto; `aria-pressed="false"` e o título dizem "Religar …".
- Texto de Ajuda atualizado para a nova regra.

### Arquivos

`redes/ui/app.js`: `gruposOcultos` virou `gruposIsolados`; `calcularVisiveis()` e `areaRede()` deixaram de excluir grupos; o desenho pula as arestas cruzadas (`dados.cruzadas`), as agregadas (`dados.entre`) e as linhas para nós fora dos grupos (`dados.soltas`) quando uma das pontas está isolada; selos e rótulos não são mais suprimidos.

`redes/ui/index.html`: sobreposição e botão `Mostrar todos` removidos; ajuda e título da exportação atualizados.

`redes/ui/style.css`: `.item-legenda.oculto` (tachado) virou `.item-legenda.isolado` (fundo neutro + anel tracejado); regras da sobreposição removidas.

### Verificação

Caso `celii` > Referências > freq. 2 (9 grupos, 115 nós, 1.066 arestas). Com o grupo 1 isolado, a contagem instrumental no canvas deu zero linhas cruzadas tocando o grupo, zero ligações dele com nós fora dos grupos, 43 arestas internas preservadas e 481 linhas entre os demais. Testes: 749 passam, 53 pulados; permanece só a falha anterior de `tests/test_v3_05_icones.py::test_menu_com_rotulo_curto_e_nome_completo_no_titulo`.

## 12. Painel docado, modo condução e busca na legenda (20/11)

Terceira rodada do backlog de interface, depois da exportação da vista e da
sessão por projeto.

### O que muda

- **Painel docado (≥1280 px)**: abrir um agrupamento pela rede não cobre mais o
  mapa. O cartão da rede reserva 380 px à direita e o painel fica ali, com as
  métricas em 2×2; abas, parâmetros e o topo continuam na largura cheia. Abaixo
  de 1280 px o painel volta a ser o diálogo que cobre a tela. `aria-modal`
  acompanha: `false` quando docado, `true` quando sobreposto.
- **Modo condução**: `Modo condução` esconde menu lateral, topo, parâmetros,
  abas, estatísticas e o bloco de exportação; o cartão da rede ocupa a tela e a
  legenda passa a corpo 14 px. O canvas recebe o foco sem abrir dica; `Esc` sai
  do mapa e, quando não há nada selecionado, do modo. Sair devolve o foco ao
  botão.
- **Busca na legenda**: com mais de 16 grupos aparece `Buscar agrupamento`.
  O filtro é local (nome curto e original, sem acento e sem diferenciar caixa),
  mostra `N de M grupos` e não mexe em nós, halos nem arestas.
- **Cabeçalho da rede**: as ações quebram linha e não partem mais no meio da
  palavra; o título e a meta ficam na primeira linha.
- **Troca de aba**: sair da aba Rede fecha o detalhe, para o painel não ficar
  preso a um bloco oculto.

### Arquivos

`redes/ui/app.js`: `ditarModoDrawer()`, `aplicarModoConducao()`,
`entrarModoConducao()`, `modoConducaoAtivo()`; filtro `atualizarLegendaRede()`
e campo `buscaLegenda`; `selecionarAba()` fecha o detalhe; `ligarTecladoRede()`
não seleciona nó ao entrar em condução.

`redes/ui/index.html`: botão `Modo condução` no cabeçalho da rede; `drawerNota`
e o restante do painel.

`redes/ui/style.css`: bloco `modo condução`; painel docado em `@media
(min-width: 1280px)`; `.busca-legenda`; foco visível no canvas; ações do
cabeçalho com quebra e `white-space: nowrap`.

### Verificação

Na Batanero (Palavras, 20 grupos, 176 nós): painel docado a 380 px com mapa de
583 px; métricas em duas colunas; condução em 1296×470 com só `blocoRede`
visível e exportação oculta; busca `rand` reduziu a legenda a 1 de 20 grupos;
tecla `1` isolou o grupo 1; `Esc` saiu do modo e devolveu o foco ao botão.
Suíte: 750 passam, 53 pulados, 128 subtestes.

### Complemento: ocultar as linhas entre halos

`Linhas` (`mostrar`/`ocultar`) fica na barra, ao lado de `Rótulos` e `Nós
exibidos`, e esconde as ligações externas aos halos: entre agrupamentos e para
nós fora deles. As arestas internas de cada halo continuam, e a rede segue
clicável. O atalho `L`
alterna o mesmo estado, salvo na vista da sessão. Para esconder todas as
arestas, `Ajustes` mantém `Arestas` (e `Halos`).

### Complemento: filtro de grupos só na legenda

Acima de 16 agrupamentos a legenda ganhou `Filtrar grupos` (nome curto ou
original, sem acento e sem diferenciar caixa) e um seletor de tamanho
(`todos`, `5+`, `10+`, `15+ nós`). O filtro não mexe no mapa: nós, halos,
arestas e rótulos continuam; só a lista e a contagem (`N de M grupos`) mudam.
Os dois critérios se somam.

### Complemento: análise do corpus completo

Com mais de um período, o seletor abre em `Todos os períodos`: a análise soma
os documentos de todos os períodos e mostra a estrutura geral. Os períodos
continuam logo abaixo no mesmo seletor, para quem quiser a leitura recortada.
Projetos com um período só não exibem a opção. A lista de documentos e a
exportação TSV acompanham o recorte: no corpus completo, saem os 147
documentos da Batanero, não os 49 de um período.

### Complemento: análises à vista, separadas por bloco

Todas as abas de resultado passaram a mostrar o nome, inclusive as inativas, e
ganharam rótulos de bloco na barra: `Visão geral`, `Rede`, `Tabelas`,
`Métodos` e `Comparar`. O `Modo avançado` não esconde mais `Dendrograma`,
`Densidade`, `Duplo mapa` e `Similitude`; ele fica só com os parâmetros e a
grade. A análise personalizada também deixou de sumir com `Densidade`,
`Duplo mapa` e `Similitude`. O antigo `Detalhe por período` saiu: a evolução
temática continua abrindo primeiro quando há dois períodos ou mais, mas as
outras abas ficam todas à vista.

### Complemento: menu lateral por tarefa

O menu da esquerda deixou de usar os nomes acadêmicos como primeira leitura:
`Temas`, `Citações` e `Colaboração` substituem, respectivamente, `Estrutura
conceitual`, `Estrutura intelectual` e `Estrutura social`; `Fontes` saiu como
bloco e `Periódicos` virou item de `Citações`, pois cocitação de periódicos é
análise de citação. Cada análise ganhou uma linha de descrição logo abaixo do
nome (`Coocorrência entre termos`, `Quem é citado junto`, `Revistas citadas
juntas` etc.), mantendo o nome completo no `title` e no `aria-label`. A
descrição nunca repete o nome do item: acrescenta o que a análise faz.
O cabeçalho do bloco nomeia a categoria e o item nomeia o objeto analisado, sem
repetição (`Temas > Palavras-chave`, não `Temas > Temas`). A ordem segue o
relatório: visão geral, temas, citações e colaboração. Em telas estreitas as
descrições somem; com o menu recolhido, ficam só os ícones. As chaves e as
análises em si não mudaram.

### Complemento: barra de resultados sem nomes repetidos

A barra de resultados repetia palavras entre blocos e abas: o bloco `Rede`
ficava ao lado da aba `Rede de coautoria`, e `Rede de agrupamentos` convivia
com `Agrupamentos`. O bloco virou `Mapas`; o mapa de grupos virou `Ligações
entre grupos` e a tabela virou `Grupos`. A aba de evolução passou a se chamar
`Evolução dos grupos` fora de palavras-chave, com legenda, colunas e nota
falando do grupo daquela unidade (`grupo de autores`, `grupo de referências`,
`grupo de periódicos` etc.). Ao trocar de análise, a figura antiga é limpa
antes do novo cálculo. O título da análise de palavras-chave passou a ser
`Palavras-chave em coocorrência`, igual ao item do menu; os relatórios mantêm a
seção `Estrutura conceitual`.

### Complemento: abas por análise

Cada análise passou a declarar as visões que fazem sentido para a sua unidade.
Similitude de resumos só em palavras-chave; duplo mapa de revistas só em
periódicos; documentos em palavras-chave e frentes; mapa de países e variantes
unidas apenas nas unidades correspondentes; evolução em palavras-chave,
autores citados e referências. Resumo, rede, diagrama estratégico, ligações
entre grupos, grupos, índices, dendrograma, linha do tempo, densidade e
comparar períodos valem em todas. A análise personalizada usa a mesma lista da
unidade escolhida. Ao trocar de análise, `limparResultado()` zera resumo, rede,
diagrama e evolução antes do novo cálculo, para não restar conteúdo da análise
anterior na tela.

### Complemento: fim do modo avançado

O alternador `Modo avançado` saiu. Todos os parâmetros — unidade, matriz,
frequência, predefinições, similaridade, algoritmo, mapeadores, palavras,
coocorrência mínima, corte, tamanho do agrupamento e tamanho do grupo — ficam
visíveis desde a abertura, com os blocos `Mais opções` e `Parâmetros
avançados` abertos. Alterar qualquer campo agenda a prévia em 500 ms; o botão
`Pré-visualizar` permanece para repetir. Como o modo simples deixou de existir,
o ajuste automático de frequência não sobrescreve mais o valor escolhido. As
regras de CSS que escondiam `so-avancado` e os itens de corpus focal foram
removidas, e o corpo do documento nasce com a classe `modo-avancado`.

### Complemento: avisos repetidos

A faixa amarela da análise deixou de mostrar `termo_generico` e `autor_focal`:
o primeiro repete o aviso do Resumo (que traz o botão "Ignorar e reanalisar")
e o segundo apenas qualifica o corpus, já sinalizado no projeto. O menu também
perdeu os selos "aviso" de Países e Instituições. Avisos de limite que alteram
a leitura (período pequeno, tema dominante, poucas referências em comum, grupos
fracos, um só periódico) continuam. A API e o relatório seguem com os dois
campos.

### Complemento: sem aba Resumo, Países com mapa e densidade

A aba `Resumo` foi removida de todas as análises, com o cartão, a grade por
quadrante e o botão `Ignorar e reanalisar`. Cada análise agora abre na
`Evolução` (quando existe) ou na visão padrão da própria análise; o selo de
qualidade continua na barra. Na análise de Países ficaram somente `Países` e
`Densidade`, com os blocos `Mapas` e `Métodos`. O relatório e a API seguem com
os campos de resumo e de avisos; só a tela não os exibe.

### Complemento: IES com rede e densidade

A análise de Instituições (IES) ficou com `Rede de instituições` e
`Densidade`, nos blocos `Mapas` e `Métodos`. As demais abas saíram da barra;
a tabela de variantes unidas continua disponível na API e no relatório
completo, apenas não tem mais aba própria.

### Complemento: Coautoria com quatro visões

Coautoria passou a mostrar `Rede de coautoria`, `Dendrograma`, `Linha do tempo`
e `Densidade`. Diagrama estratégico, ligações entre grupos, grupos, índices e
comparação de períodos saíram da barra dessa análise.

### Complemento: versão desktop em Tauri

Além da interface web, o Redes agora tem um app para macOS em Tauri 2: a mesma
tela em uma janela própria, com o servidor Python embutido como sidecar. O
build gera `Redes.app` e `Redes-0.3.0-macOS-arm64.dmg`; o workflow
`.github/workflows/tauri.yml` publica o DMG no GitHub Releases com o `.sha256`.
Como o app é assinado ad hoc, a primeira abertura pede o clique com o botão
direito em **Redes** e **Abrir**.

### Complemento: fim da faixa amarela

A faixa amarela com avisos de limite mínimo (tema dominante, grupos fracos,
período pequeno) saiu de todas as análises. Os mesmos avisos continuam nos
dados da API e no relatório completo, mas a tela não os repete. Como a
interface é compartilhada, a mudança vale para o navegador e para o app
desktop no macOS e no Windows.

### Complemento: ícone sem o nome e versão para Windows

O ícone do aplicativo passou a mostrar apenas a imagem da rede, sem a palavra
"Redes". No macOS isso vale para o ícone do Finder e do Dock; no Windows, para o
atalho e o instalador. Também entrou o build para Windows (instalador `.exe`),
feito a partir do mesmo código e da mesma interface do app de macOS.
