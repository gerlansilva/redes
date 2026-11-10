/* Bibliometria descritiva: produção, autores, fontes, países, palavras e leis. */
"use strict";

const BIB = { cache: {}, carregando: false };

function bibEsc(texto) {
  return String(texto ?? "").replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

const bibNum = new Intl.NumberFormat("pt-BR");
const bibDec = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

function bibPlural(n, um, varios) {
  return `${bibNum.format(n)} ${n === 1 ? um : varios}`;
}

async function mostrarBibliometria() {
  mostrarVisaoGeral();            // esconde parâmetros, abas e a visão geral
  esconderVisaoGeralSemPainel();
  for (const item of document.querySelectorAll(".nav-analise[data-analise]")) {
    item.classList.toggle("ativa", item.dataset.analise === "bibliometria");
  }
  const painel = document.getElementById("visaoBibliometria");
  painel.classList.remove("oculta");
  painel.hidden = false;
  if (!estado.projeto) {
    painel.innerHTML = '<div class="visao-geral-cab"><div class="sobre">Bibliometria</div>' +
      "<h2>Bibliometria</h2><p>Abra um projeto para ver a produção do corpus.</p></div>";
    return;
  }
  const caminho = estado.projeto.caminho;
  if (!BIB.cache[caminho]) {
    painel.innerHTML = '<div class="visao-geral-cab"><div class="sobre">Bibliometria</div>' +
      "<h2>Bibliometria</h2><p>Calculando…</p></div>";
    try {
      BIB.cache[caminho] = await api(`/api/bibliometria?caminho=${encodeURIComponent(caminho)}`);
    } catch (erro) {
      painel.innerHTML = `<div class="visao-geral-cab"><h2>Bibliometria</h2><p>${bibEsc(erro.message)}</p></div>`;
      return;
    }
  }
  if (estado.projeto.caminho === caminho) renderizarBibliometria(painel, BIB.cache[caminho]);
}

function esconderVisaoGeralSemPainel() {
  const visao = document.getElementById("visaoGeral");
  if (visao) { visao.classList.add("oculta"); visao.hidden = true; }
}

/* ------------------------------------------------------------ gráficos SVG */

function graficoProducao(producao) {
  const L = 760, A = 260, m = { e: 46, d: 46, t: 16, b: 30 };
  const w = L - m.e - m.d, h = A - m.t - m.b;
  const maxD = Math.max(1, ...producao.map((p) => p.documentos));
  const maxA = Math.max(1, ...producao.map((p) => p.acumulado));
  const passo = w / producao.length;
  const barras = producao.map((p, i) => {
    const altura = (p.documentos / maxD) * h;
    return `<rect x="${(m.e + i * passo + passo * 0.14).toFixed(1)}" y="${(m.t + h - altura).toFixed(1)}" ` +
      `width="${(passo * 0.72).toFixed(1)}" height="${altura.toFixed(1)}" rx="3" fill="#2F2BFF" fill-opacity=".85">` +
      `<title>${p.ano}: ${bibPlural(p.documentos, "documento", "documentos")}, ${bibNum.format(p.citacoes)} citações</title></rect>`;
  }).join("");
  const linha = producao.map((p, i) =>
    `${i ? "L" : "M"}${(m.e + i * passo + passo / 2).toFixed(1)},${(m.t + h - (p.acumulado / maxA) * h).toFixed(1)}`).join(" ");
  const cada = Math.max(1, Math.ceil(producao.length / 12));
  const rotulos = producao.map((p, i) => (i % cada === 0 || i === producao.length - 1)
    ? `<text x="${(m.e + i * passo + passo / 2).toFixed(1)}" y="${A - 10}" text-anchor="middle" font-size="11" fill="#64748B">${p.ano}</text>` : "").join("");
  const eixo = (valor, x, anchor, cor) =>
    `<text x="${x}" y="${m.t + 4}" text-anchor="${anchor}" font-size="11" fill="${cor}">${bibNum.format(valor)}</text>`;
  return `<svg viewBox="0 0 ${L} ${A}" width="100%" role="img" aria-label="Produção científica anual">` +
    `<line x1="${m.e}" y1="${m.t + h}" x2="${L - m.d}" y2="${m.t + h}" stroke="#DCE3F0"/>` +
    barras + `<path d="${linha}" fill="none" stroke="#FFC400" stroke-width="2.5"/>` +
    eixo(maxD, m.e - 8, "end", "#2F2BFF") + eixo(maxA, L - m.d + 8, "start", "#A16207") + rotulos + `</svg>` +
    `<div class="bib-legenda"><span><i style="background:#2F2BFF"></i>Documentos por ano</span>` +
    `<span><i style="background:#FFC400"></i>Acumulado</span></div>`;
}

function graficoBarras(linhas, campo, cor) {
  const maior = Math.max(1, ...linhas.map((l) => l[campo]));
  return linhas.map((l) =>
    `<div class="bib-barra"><span class="bib-nome" title="${bibEsc(l.nome)}">${bibEsc(l.nome)}</span>` +
    `<span class="bib-trilho"><span style="width:${(100 * l[campo] / maior).toFixed(1)}%;background:${cor}"></span></span>` +
    `<b>${bibNum.format(l[campo])}</b></div>`).join("");
}

function graficoLogLog(pontos, x, y, esperada, rotuloX, rotuloY) {
  const L = 360, A = 230, m = 38;
  const xs = pontos.map((p) => Math.log10(p[x])), ys = pontos.map((p) => Math.log10(p[y]));
  const minX = Math.min(...xs), maxX = Math.max(...xs, minX + 0.1);
  const minY = Math.min(...ys, 0), maxY = Math.max(...ys, minY + 0.1);
  const px = (v) => m + ((v - minX) / (maxX - minX)) * (L - m - 14);
  const py = (v) => A - m - ((v - minY) / (maxY - minY)) * (A - m - 14);
  const pts = pontos.map((p) =>
    `<circle cx="${px(Math.log10(p[x])).toFixed(1)}" cy="${py(Math.log10(p[y])).toFixed(1)}" r="4.5" fill="#2F2BFF" fill-opacity=".8">` +
    `<title>${rotuloX} ${bibNum.format(p[x])}: ${bibNum.format(p[y])}</title></circle>`).join("");
  let teorica = "";
  if (esperada) {
    const caminho = pontos.map((p, i) => {
      const valor = Math.log10(esperada(p));
      return `${i ? "L" : "M"}${px(Math.log10(p[x])).toFixed(1)},${py(valor).toFixed(1)}`;
    }).join(" ");
    teorica = `<path d="${caminho}" fill="none" stroke="#FFC400" stroke-width="2" stroke-dasharray="5 4"/>`;
  }
  return `<svg viewBox="0 0 ${L} ${A}" width="100%" role="img">` +
    `<line x1="${m}" y1="${A - m}" x2="${L - 10}" y2="${A - m}" stroke="#DCE3F0"/>` +
    `<line x1="${m}" y1="10" x2="${m}" y2="${A - m}" stroke="#DCE3F0"/>` + teorica + pts +
    `<text x="${(L + m) / 2}" y="${A - 8}" text-anchor="middle" font-size="11" fill="#64748B">${rotuloX} (log)</text>` +
    `<text x="12" y="${A / 2}" font-size="11" fill="#64748B" transform="rotate(-90 12 ${A / 2})" text-anchor="middle">${rotuloY} (log)</text></svg>`;
}

/* ---------------------------------------------------------------- tabelas */

function tabelaBib(colunas, linhas, legenda) {
  if (!linhas.length) return '<p class="bib-vazio">Sem dados no corpus.</p>';
  const cab = colunas.map((c) => `<th${c.num ? ' class="num"' : ""}>${bibEsc(c.rotulo)}</th>`).join("");
  const corpo = linhas.map((l) => "<tr>" + colunas.map((c) =>
    `<td${c.num ? ' class="num"' : ""}>${c.num ? bibNum.format(l[c.campo] ?? 0) : bibEsc(l[c.campo])}</td>`).join("") + "</tr>").join("");
  return `<table class="bib-tabela" aria-label="${bibEsc(legenda)}"><thead><tr>${cab}</tr></thead><tbody>${corpo}</tbody></table>`;
}

function cartaoBib(rotulo, valor, detalhe) {
  return `<article class="info-cartao"><span class="rotulo">${bibEsc(rotulo)}</span>` +
    `<strong>${valor}</strong><span class="detalhe">${bibEsc(detalhe || "")}</span></article>`;
}

function secaoBib(titulo, descricao, conteudo, classe = "") {
  return `<section class="bib-secao ${classe}"><header><h3>${bibEsc(titulo)}</h3>` +
    (descricao ? `<p>${bibEsc(descricao)}</p>` : "") + `</header>${conteudo}</section>`;
}

/* ---------------------------------------------------------------- render */

function renderizarBibliometria(painel, d) {
  if (d.vazio) {
    painel.innerHTML = '<div class="visao-geral-cab"><h2>Bibliometria</h2><p>O projeto não tem documentos.</p></div>';
    return;
  }
  const p = d.principal;
  const intervalo = p.primeiro_ano ? `${p.primeiro_ano}–${p.ultimo_ano}` : "—";
  const cartoes = [
    cartaoBib("Documentos", bibNum.format(p.documentos), intervalo),
    cartaoBib("Autores", bibNum.format(p.autores), `${bibDec.format(p.autores_por_documento ?? 0)} por documento`),
    cartaoBib("Fontes", bibNum.format(p.fontes), "periódicos do corpus"),
    cartaoBib("Palavras-chave", bibNum.format(p.palavras_chave), "dos autores"),
    cartaoBib("Países", bibNum.format(p.paises), p.coautoria_internacional != null
      ? `${bibDec.format(p.coautoria_internacional)}% em coautoria internacional` : "sem afiliações"),
    cartaoBib("Referências", bibNum.format(p.referencias), "distintas"),
    cartaoBib("Citações", bibNum.format(p.citacoes), `${bibDec.format(p.citacoes_por_documento)} por documento`),
    cartaoBib("Crescimento anual", p.crescimento_anual != null ? `${bibDec.format(p.crescimento_anual)}%` : "—", "taxa composta da produção"),
    cartaoBib("Autor único", bibNum.format(p.documentos_autor_unico), "documentos"),
    cartaoBib("Índice de colaboração", p.indice_colaboracao != null ? bibDec.format(p.indice_colaboracao) : "—", "autores por documento em coautoria"),
  ].join("");

  const colAutores = [{ rotulo: "Autor", campo: "nome" }, { rotulo: "Docs", campo: "documentos", num: 1 },
    { rotulo: "Citações", campo: "citacoes", num: 1 }, { rotulo: "h", campo: "h", num: 1 }];
  const colFontes = [{ rotulo: "Fonte", campo: "nome" }, { rotulo: "Docs", campo: "documentos", num: 1 },
    { rotulo: "Citações", campo: "citacoes", num: 1 }];
  const colPaises = [{ rotulo: "País", campo: "nome" }, { rotulo: "Docs", campo: "documentos", num: 1 },
    { rotulo: "Citações", campo: "citacoes", num: 1 }];
  const colPalavras = [{ rotulo: "Palavra-chave", campo: "nome" }, { rotulo: "Docs", campo: "documentos", num: 1 }];
  const colCitadas = [{ rotulo: "Fonte citada", campo: "nome" }, { rotulo: "Docs que citam", campo: "documentos", num: 1 }];
  const colCitados = [{ rotulo: "Documento", campo: "titulo" }, { rotulo: "Ano", campo: "ano" },
    { rotulo: "Citações", campo: "citacoes", num: 1 }];

  const lotkaTxt = d.lotka.beta != null
    ? `Expoente estimado β = ${bibDec.format(d.lotka.beta)} (o clássico é 2). ${bibPlural(d.lotka.autores, "autor", "autores")}.`
    : "Poucos pontos para estimar o expoente.";
  const zipfTxt = d.zipf.expoente != null
    ? `Inclinação estimada ${bibDec.format(d.zipf.expoente)} (o clássico é 1). ${bibPlural(d.zipf.palavras, "palavra-chave", "palavras-chave")}.`
    : "Poucos pontos para estimar a inclinação.";
  const bradfordTxt = d.bradford.zonas.length > 1
    ? `${bibPlural(d.bradford.fontes, "fonte", "fontes")} em ${d.bradford.zonas.length} zonas com cerca de um terço dos documentos cada.`
    : "O corpus tem uma única fonte ou poucas fontes: a lei de Bradford não se aplica.";
  const zonas = tabelaBib([{ rotulo: "Zona", campo: "zona", num: 1 }, { rotulo: "Fontes", campo: "fontes", num: 1 },
    { rotulo: "Documentos", campo: "documentos", num: 1 }], d.bradford.zonas, "Zonas de Bradford");

  const distrib = tabelaBib([{ rotulo: "Autores por documento", campo: "autores", num: 1 },
    { rotulo: "Documentos", campo: "documentos", num: 1 }], d.coautoria.distribuicao, "Autores por documento");
  const pares = tabelaBib([{ rotulo: "Par de coautores", campo: "autores" },
    { rotulo: "Docs", campo: "documentos", num: 1 }], d.coautoria.pares, "Pares de coautores");

  painel.innerHTML =
    '<div class="visao-geral-cab"><div class="sobre">Corpus</div><h2>Bibliometria</h2>' +
    "<p>Produção, impacto e distribuição de autores, fontes, países e palavras-chave.</p></div>" +
    `<div class="info-geral bib-cartoes">${cartoes}</div>` +
    secaoBib("Produção científica anual", "Documentos por ano (barras) e total acumulado (linha).",
      graficoProducao(d.producao), "bib-larga") +
    '<div class="bib-grade">' +
    secaoBib("Autores mais produtivos", "Por número de documentos; h calculado dentro do corpus.", tabelaBib(colAutores, d.autores, "Autores")) +
    secaoBib("Fontes mais produtivas", "Periódicos que mais publicam no corpus.", tabelaBib(colFontes, d.fontes, "Fontes")) +
    secaoBib("Países", "Países de afiliação, por número de documentos.", tabelaBib(colPaises, d.paises, "Países")) +
    secaoBib("Palavras-chave", "Palavras-chave dos autores, já unidas pelos grupos da base.", graficoBarras(d.palavras, "documentos", "#6A3BFF")) +
    secaoBib("Fontes mais citadas", "Periódicos mais presentes nas listas de referências.", tabelaBib(colCitadas, d.fontes_citadas, "Fontes citadas")) +
    secaoBib("Documentos mais citados", "Citações recebidas, conforme a base de origem.", tabelaBib(colCitados, d.mais_citados, "Mais citados")) +
    secaoBib("Coautoria", "Quantos autores assinam cada documento e as parcerias mais frequentes.", distrib + pares) +
    "</div>" +
    '<div class="bib-grade bib-leis">' +
    secaoBib("Lei de Lotka", lotkaTxt, graficoLogLog(d.lotka.pontos, "documentos", "proporcao",
      (pt) => pt.esperada, "Documentos por autor", "Proporção de autores")) +
    secaoBib("Lei de Bradford", bradfordTxt, zonas) +
    secaoBib("Lei de Zipf", zipfTxt, graficoLogLog(d.zipf.pontos, "posto", "frequencia", null,
      "Posição da palavra", "Frequência")) +
    "</div>";
}
