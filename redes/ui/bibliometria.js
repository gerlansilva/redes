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

async function carregarBibliometria() {
  const painel = document.getElementById("visaoBibliometria");
  if (!painel) return;
  if (!estado.projeto) {
    painel.innerHTML = '<p class="bib-vazio">Abra um projeto para ver o corpus.</p>';
    return;
  }
  const caminho = estado.projeto.caminho;
  if (!BIB.cache[caminho]) {
    painel.innerHTML = '<p class="bib-vazio">Calculando…</p>';
    try {
      BIB.cache[caminho] = await api(`/api/bibliometria?caminho=${encodeURIComponent(caminho)}`);
    } catch (erro) {
      painel.innerHTML = `<p class="bib-vazio">${bibEsc(erro.message)}</p>`;
      return;
    }
  }
  if (estado.projeto && estado.projeto.caminho === caminho) {
    renderizarBibliometria(painel, BIB.cache[caminho]);
    if (typeof atualizarMenuExportar === "function") atualizarMenuExportar();
  }
}

/* ------------------------------------------------------------ gráficos SVG */

function escalaBonita(maximo, passos = 4) {
  if (maximo <= 0) return { topo: 1, ticks: [0, 1] };
  const bruto = maximo / passos;
  const potencia = Math.pow(10, Math.floor(Math.log10(bruto)));
  const fracao = bruto / potencia;
  const passo = (fracao <= 1 ? 1 : fracao <= 2 ? 2 : fracao <= 5 ? 5 : 10) * potencia;
  const topo = Math.ceil(maximo / passo) * passo;
  const ticks = [];
  for (let v = 0; v <= topo + passo / 1000; v += passo) ticks.push(Math.round(v * 1000) / 1000);
  return { topo, ticks };
}

function graficoProducao(producao) {
  const L = 1100, A = 312, m = { e: 54, d: 62, t: 28, b: 30 };
  const w = L - m.e - m.d, h = A - m.t - m.b;
  const escD = escalaBonita(Math.max(...producao.map((p) => p.documentos)));
  const escC = escalaBonita(Math.max(...producao.map((p) => p.citacoes)));
  const passo = w / producao.length;
  const xc = (i) => m.e + i * passo + passo / 2;
  const yD = (v) => m.t + h - (v / escD.topo) * h;
  const yC = (v) => m.t + h - (v / escC.topo) * h;
  const grade = escD.ticks.map((v) =>
    `<line x1="${m.e}" x2="${L - m.d}" y1="${yD(v).toFixed(1)}" y2="${yD(v).toFixed(1)}" stroke="#E9ECF2"/>` +
    `<text x="${m.e - 8}" y="${(yD(v) + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="#2F2BFF">${bibNum.format(v)}</text>`).join("");
  const eixoC = escC.ticks.map((v) =>
    `<text x="${L - m.d + 8}" y="${(yC(v) + 4).toFixed(1)}" font-size="11" fill="#A16207">${bibNum.format(v)}</text>`).join("");
  const barras = producao.map((p, i) => {
    const altura = (p.documentos / escD.topo) * h;
    return `<rect x="${(m.e + i * passo + passo * 0.16).toFixed(1)}" y="${(m.t + h - altura).toFixed(1)}" ` +
      `width="${(passo * 0.68).toFixed(1)}" height="${altura.toFixed(1)}" rx="3" fill="#2F2BFF" fill-opacity=".85">` +
      `<title>${p.ano}: ${bibPlural(p.documentos, "documento", "documentos")}, ${bibNum.format(p.citacoes)} citações</title></rect>`;
  }).join("");
  const linha = producao.map((p, i) => `${i ? "L" : "M"}${xc(i).toFixed(1)},${yC(p.citacoes).toFixed(1)}`).join(" ");
  const pontos = producao.map((p, i) =>
    `<circle cx="${xc(i).toFixed(1)}" cy="${yC(p.citacoes).toFixed(1)}" r="3" fill="#FFC400" stroke="#fff" stroke-width="1">` +
    `<title>${p.ano}: ${bibNum.format(p.citacoes)} citações</title></circle>`).join("");
  const cada = Math.max(1, Math.ceil(producao.length / 14));
  const rotulos = producao.map((p, i) => (i % cada === 0 || i === producao.length - 1)
    ? `<text x="${xc(i).toFixed(1)}" y="${A - 10}" text-anchor="middle" font-size="11" fill="#64748B">${p.ano}</text>` : "").join("");
  const titulos =
    `<text x="${m.e - 8}" y="12" text-anchor="end" font-size="10.5" font-weight="600" fill="#2F2BFF">Docs</text>` +
    `<text x="${L - m.d + 8}" y="12" font-size="10.5" font-weight="600" fill="#A16207">Citações</text>`;
  return `<svg viewBox="0 0 ${L} ${A}" width="100%" role="img" aria-label="Produção e citações por ano">` +
    grade + `<line x1="${m.e}" y1="${m.t + h}" x2="${L - m.d}" y2="${m.t + h}" stroke="#DCE3F0"/>` +
    barras + `<path d="${linha}" fill="none" stroke="#FFC400" stroke-width="2.5" stroke-linejoin="round"/>` + pontos +
    eixoC + titulos + rotulos + `</svg>` +
    `<div class="bib-legenda"><span><i style="background:#2F2BFF"></i>Documentos por ano (eixo esquerdo)</span>` +
    `<span><i style="background:#FFC400"></i>Citações recebidas por ano de publicação (eixo direito)</span></div>`;
}

function graficoAcumulado(producao) {
  const L = 1100, A = 150, m = { e: 54, d: 62, t: 10, b: 26 };
  const w = L - m.e - m.d, h = A - m.t - m.b;
  const esc = escalaBonita(Math.max(...producao.map((p) => p.acumulado)), 3);
  const passo = w / Math.max(1, producao.length - 1);
  const x = (i) => producao.length > 1 ? m.e + i * passo : m.e + w / 2;
  const y = (v) => m.t + h - (v / esc.topo) * h;
  const linha = producao.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.acumulado).toFixed(1)}`).join(" ");
  const area = `${linha} L${x(producao.length - 1).toFixed(1)},${m.t + h} L${x(0).toFixed(1)},${m.t + h} Z`;
  const grade = esc.ticks.map((v) =>
    `<line x1="${m.e}" x2="${L - m.d}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="#E9ECF2"/>` +
    `<text x="${m.e - 8}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="#64748B">${bibNum.format(v)}</text>`).join("");
  const cada = Math.max(1, Math.ceil(producao.length / 14));
  const rotulos = producao.map((p, i) => (i % cada === 0 || i === producao.length - 1)
    ? `<text x="${x(i).toFixed(1)}" y="${A - 8}" text-anchor="middle" font-size="11" fill="#64748B">${p.ano}</text>` : "").join("");
  return `<svg viewBox="0 0 ${L} ${A}" width="100%" role="img" aria-label="Documentos acumulados">` +
    grade + `<path d="${area}" fill="#6A3BFF" fill-opacity=".12"/>` +
    `<path d="${linha}" fill="none" stroke="#6A3BFF" stroke-width="2.5" stroke-linejoin="round"/>` + rotulos + `</svg>`;
}

function graficoBarras(linhas, campo, cor) {
  const maior = Math.max(1, ...linhas.map((l) => l[campo]));
  return linhas.map((l) =>
    `<div class="bib-barra"><span class="bib-nome" title="${bibEsc(l.nome)}">${bibEsc(l.nome)}</span>` +
    `<span class="bib-trilho"><span style="width:${(100 * l[campo] / maior).toFixed(1)}%;background:${cor}"></span></span>` +
    `<b>${bibNum.format(l[campo])}</b></div>`).join("");
}

function graficoLogLog(pontos, x, y, esperada, rotuloX, rotuloY) {
  const L = 360, A = 250, mE = 46, mD = 18, mT = 14, mB = 52;
  const area = { x0: mE, x1: L - mD, y0: mT, y1: A - mB };
  const xs = pontos.map((p) => Math.log10(p[x])), ys = pontos.map((p) => Math.log10(p[y]));
  // Folga de 6% nos dois eixos: nenhum ponto fica em cima do eixo ou da borda.
  const dominio = (vals, minimo) => {
    const lo = Math.min(...vals, ...(minimo === undefined ? [] : [minimo]));
    const hi = Math.max(...vals, lo + 0.1);
    const folga = (hi - lo) * 0.06;
    return [lo - folga, hi + folga];
  };
  const [minX, maxX] = dominio(xs), [minY, maxY] = dominio(ys);
  const px = (v) => area.x0 + ((v - minX) / (maxX - minX)) * (area.x1 - area.x0);
  const py = (v) => area.y1 - ((v - minY) / (maxY - minY)) * (area.y1 - area.y0);
  const raio = pontos.length > 80 ? 2.6 : pontos.length > 30 ? 3.4 : 4.5;
  const idClip = "clip" + Math.abs(pontos.length * 31 + Math.round(minX * 100) + Math.round(maxY * 100));
  const pts = pontos.map((p) =>
    `<circle cx="${px(Math.log10(p[x])).toFixed(1)}" cy="${py(Math.log10(p[y])).toFixed(1)}" r="${raio}" fill="#2F2BFF" fill-opacity=".75">` +
    `<title>${rotuloX} ${bibNum.format(p[x])}: ${bibNum.format(p[y])}</title></circle>`).join("");
  let teorica = "";
  if (esperada) {
    // Só valores positivos e finitos: log10(0) não é desenhável.
    const caminho = pontos.filter((p) => esperada(p) > 0 && Number.isFinite(esperada(p))).map((p, i) => {
      const valor = Math.log10(esperada(p));
      return `${i ? "L" : "M"}${px(Math.log10(p[x])).toFixed(1)},${py(valor).toFixed(1)}`;
    }).join(" ");
    if (caminho) teorica = `<path d="${caminho}" fill="none" stroke="#FFC400" stroke-width="2" stroke-dasharray="5 4" clip-path="url(#${idClip})"/>`;
  }
  // Marcas dos eixos nas potências de 10 que cabem no intervalo.
  const marcas = (lo, hi) => {
    const out = [];
    for (let k = Math.ceil(lo); k <= Math.floor(hi); k++) out.push(k);
    return out;
  };
  const rot = (k) => (k >= 0 ? bibNum.format(Math.pow(10, k))
    : "0," + "0".repeat(-k - 1) + "1");
  let eixos = "";
  for (const k of marcas(minX, maxX)) {
    const cx = px(k).toFixed(1);
    eixos += `<line x1="${cx}" y1="${area.y1}" x2="${cx}" y2="${area.y1 + 4}" stroke="#B8C2D6"/>` +
      `<text x="${cx}" y="${area.y1 + 16}" text-anchor="middle" font-size="10" fill="#64748B">${rot(k)}</text>`;
  }
  for (const k of marcas(minY, maxY)) {
    const cy = py(k).toFixed(1);
    eixos += `<line x1="${area.x0 - 4}" y1="${cy}" x2="${area.x0}" y2="${cy}" stroke="#B8C2D6"/>` +
      `<line x1="${area.x0}" y1="${cy}" x2="${area.x1}" y2="${cy}" stroke="#EEF1F8"/>` +
      `<text x="${area.x0 - 7}" y="${(Number(cy) + 3.5).toFixed(1)}" text-anchor="end" font-size="10" fill="#64748B">${rot(k)}</text>`;
  }
  return `<svg viewBox="0 0 ${L} ${A}" width="100%" role="img">` +
    `<defs><clipPath id="${idClip}"><rect x="${area.x0}" y="${area.y0}" width="${area.x1 - area.x0}" height="${area.y1 - area.y0}"/></clipPath></defs>` +
    eixos +
    `<line x1="${area.x0}" y1="${area.y1}" x2="${area.x1}" y2="${area.y1}" stroke="#DCE3F0"/>` +
    `<line x1="${area.x0}" y1="${area.y0}" x2="${area.x0}" y2="${area.y1}" stroke="#DCE3F0"/>` +
    `<g clip-path="url(#${idClip})">${pts}</g>` + teorica +
    `<text x="${(area.x0 + area.x1) / 2}" y="${A - 8}" text-anchor="middle" font-size="11" fill="#64748B">${rotuloX} (log)</text>` +
    `<text x="12" y="${(area.y0 + area.y1) / 2}" font-size="11" fill="#64748B" transform="rotate(-90 12 ${(area.y0 + area.y1) / 2})" text-anchor="middle">${rotuloY} (log)</text></svg>`;
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
  const exportar = typeof botaoExportarBib === "function" ? botaoExportarBib() : "";
  return `<section class="bib-secao ${classe}"><header><div class="bib-cab"><h3>${bibEsc(titulo)}</h3>${exportar}</div>` +
    (descricao ? `<p>${bibEsc(descricao)}</p>` : "") + `</header>${conteudo}</section>`;
}

/* ---------------------------------------------------------------- render */

function renderizarBibliometria(painel, d) {
  if (d.vazio) {
    painel.innerHTML = '<p class="bib-vazio">O projeto não tem documentos.</p>';
    return;
  }
  const p = d.principal;
  const intervalo = p.primeiro_ano ? `${p.primeiro_ano}–${p.ultimo_ano}` : "—";
  const cartoes = [
    cartaoBib("Documentos", bibNum.format(p.documentos), intervalo),
    cartaoBib("Períodos", bibNum.format(estado.projeto.periodos.length),
      estado.projeto.periodos.map((x) => x.nome).join(" · ")),
    cartaoBib("Autores", bibNum.format(p.autores),
      `${bibDec.format(p.autores_por_documento ?? 0)} por documento · ${bibNum.format(p.documentos_autor_unico)} de autor único`),
    cartaoBib("Fontes", bibNum.format(p.fontes), "periódicos do corpus"),
    cartaoBib("Palavras-chave", bibNum.format(p.palavras_chave), "dos autores"),
    cartaoBib("Instituições", bibNum.format(p.instituicoes ?? 0), "distintas, pelas afiliações"),
    cartaoBib("Países", bibNum.format(p.paises), p.coautoria_internacional != null
      ? `${bibDec.format(p.coautoria_internacional)}% em coautoria internacional` : "sem afiliações"),
    cartaoBib("Referências", bibNum.format(p.referencias), "distintas"),
    cartaoBib("Citações", bibNum.format(p.citacoes), `${bibDec.format(p.citacoes_por_documento)} por documento`),
    cartaoBib("Crescimento anual", p.crescimento_anual != null ? `${bibDec.format(p.crescimento_anual)}%` : "—", "taxa composta da produção"),
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

  const focal = Boolean(d.corpus && d.corpus.focal);
  const lacunas = (d.lacunas || []).length
    ? `<div class="bib-lacunas"><b>O que falta neste corpus</b><ul>${
      d.lacunas.map((t) => `<li>${bibEsc(t)}</li>`).join("")}</ul></div>` : "";

  painel.innerHTML =
    lacunas +
    `<div class="info-geral bib-cartoes">${cartoes}</div>` +
    secaoBib("Produção e citações por ano", "Documentos publicados (barras) e citações que esses documentos receberam (linha).",
      graficoProducao(d.producao), "bib-larga") +
    secaoBib("Documentos acumulados", "Total de documentos do corpus ao longo dos anos.",
      graficoAcumulado(d.producao), "bib-larga") +
    secaoNuvem() + secaoRajadas() + secaoFluxo() +
    '<div class="bib-grade">' +
    secaoBib("Autores mais produtivos", "Por número de documentos; h calculado dentro do corpus.", tabelaBib(colAutores, d.autores, "Autores")) +
    secaoBib("Fontes mais produtivas", "Periódicos que mais publicam no corpus.", tabelaBib(colFontes, d.fontes, "Fontes")) +
    secaoBib("Instituições (IES)", "Instituição lida da afiliação; use Revisar grafias para unir variantes.", tabelaBib(colPaises.map((c) => c.campo === "nome" ? { ...c, rotulo: "Instituição" } : c), d.instituicoes || [], "Instituições")) +
    secaoBib("Países", "Países de afiliação, por número de documentos.", tabelaBib(colPaises, d.paises, "Países")) +
    secaoBib("Palavras-chave", "Palavras-chave dos autores, já unidas pelos grupos da base.", graficoBarras(d.palavras, "documentos", "#6A3BFF")) +
    secaoBib("Fontes mais citadas", "Periódicos mais presentes nas listas de referências.", tabelaBib(colCitadas, d.fontes_citadas, "Fontes citadas")) +
    secaoBib("Documentos mais citados", "Citações recebidas, conforme a base de origem.", tabelaBib(colCitados, d.mais_citados, "Mais citados")) +
    secaoBib("Coautoria", "Quantos autores assinam cada documento e as parcerias mais frequentes.", distrib + pares) +
    "</div>" +
    (focal ? '<p class="bib-aviso so-se-focal">Leis de Lotka, Bradford e Zipf: pouco informativo para este corpus ' +
      '(um autor está em mais de 80% dos documentos).</p>' : "") +
    `<div class="bib-grade bib-leis${focal ? " so-se-focal" : ""}">` +
    secaoBib("Lei de Lotka", lotkaTxt, graficoLogLog(d.lotka.pontos, "documentos", "proporcao",
      (pt) => pt.esperada, "Documentos por autor", "Proporção de autores")) +
    secaoBib("Lei de Bradford", bradfordTxt, zonas) +
    secaoBib("Lei de Zipf", zipfTxt, graficoLogLog(d.zipf.pontos, "posto", "frequencia", null,
      "Posição da palavra", "Frequência")) +
    "</div>";
  iniciarNuvem();
  iniciarRajadas();
  iniciarFluxo();
  if (typeof instalarExportacaoBib === "function") instalarExportacaoBib(painel, dadosPlotados(d));
}

// Valores plotados de cada gráfico, para o CSV (as tabelas saem do próprio HTML).
function dadosPlotados(d) {
  const colunasDe = (pontos) => (pontos && pontos.length ? Object.keys(pontos[0]) : []);
  const bloco = (colunas, linhas) => ({ colunas, linhas: linhas.map((l) => colunas.map((c) => l[c])) });
  return {
    "Produção e citações por ano": bloco(["ano", "documentos", "citacoes", "acumulado"], d.producao),
    "Documentos acumulados": bloco(["ano", "acumulado"], d.producao),
    "Palavras-chave": bloco(["nome", "documentos", "citacoes"], d.palavras || []),
    "Lei de Lotka": bloco(colunasDe(d.lotka.pontos), d.lotka.pontos),
    "Lei de Zipf": bloco(colunasDe(d.zipf.pontos), d.zipf.pontos),
  };
}

/* ------------------------------------------------- nuvem de palavras e rajadas */

function secaoNuvem() {
  return secaoBib("Nuvem de palavras",
    "Os termos mais frequentes. Clique numa palavra para ocultá-la e recalcular.",
    '<div class="bib-controles">' +
    '<label>Fonte <select id="nuvemFonte"><option value="palavras">Palavras-chave dos autores</option>' +
    '<option value="titulos">Títulos dos documentos</option></select></label>' +
    '<label class="bib-so-titulos"><input type="checkbox" id="nuvemExpr"> Expressões de duas palavras</label>' +
    '<label class="bib-so-titulos"><input type="checkbox" id="nuvemAcad" checked> Ocultar termos genéricos (estudo, análise, research…)</label>' +
    '<label>Ocultar <input type="text" id="nuvemOcultar" placeholder="ex.: statistics, students"></label>' +
    '<button type="button" class="botao-mini" id="nuvemAtualizar">Atualizar</button></div>' +
    '<div id="nuvemSaida" class="bib-saida">Calculando…</div><div id="nuvemExtra"></div>',
    "bib-larga");
}

function secaoRajadas() {
  return secaoBib("Rajadas (bursts)",
    "Termos cuja presença no corpus cresceu de repente, por Kleinberg (2002). A barra vermelha marca os anos da rajada.",
    '<div class="bib-controles">' +
    '<label>Termos <select id="rajadaTipo"><option value="palavras">Palavras-chave dos autores</option>' +
    '<option value="referencias">Referências citadas</option></select></label>' +
    '<label>Mínimo de documentos <select id="rajadaMinimo"><option value="2">2</option>' +
    '<option value="3" selected>3</option><option value="5">5</option><option value="8">8</option></select></label></div>' +
    '<div id="rajadaSaida" class="bib-saida">Calculando…</div>',
    "bib-larga");
}

function pedirTexto(url) { return api(url); }

async function atualizarNuvem() {
  const saida = document.getElementById("nuvemSaida");
  if (!saida || !estado.projeto) return;
  const fonte = document.getElementById("nuvemFonte").value;
  const titulos = fonte === "titulos";
  for (const el of document.querySelectorAll(".bib-so-titulos")) el.hidden = !titulos;
  const parametrosUrl = new URLSearchParams({
    caminho: estado.projeto.caminho, fonte,
    ocultar: document.getElementById("nuvemOcultar").value,
    academicas: document.getElementById("nuvemAcad").checked ? "1" : "0",
    expressoes: titulos && document.getElementById("nuvemExpr").checked ? "1" : "0",
  });
  saida.textContent = "Calculando…";
  try {
    const dados = await pedirTexto(`/api/nuvem?${parametrosUrl}`);
    saida.innerHTML = dados.svg || '<p class="bib-vazio">Nenhum termo para mostrar.</p>';
    const extra = document.getElementById("nuvemExtra");
    extra.innerHTML = dados.expressoes && dados.expressoes.length
      ? '<p class="bib-nota">Expressões frequentes nos títulos: ' +
        dados.expressoes.map((e) => `${bibEsc(e.termo)} (${e.documentos})`).join(" · ") + "</p>" : "";
  } catch (erro) {
    saida.innerHTML = `<p class="bib-vazio">${bibEsc(erro.message)}</p>`;
  }
}

function iniciarNuvem() {
  const fonte = document.getElementById("nuvemFonte");
  if (!fonte) return;
  const saida = document.getElementById("nuvemSaida");
  fonte.addEventListener("change", atualizarNuvem);
  document.getElementById("nuvemExpr").addEventListener("change", atualizarNuvem);
  document.getElementById("nuvemAcad").addEventListener("change", atualizarNuvem);
  document.getElementById("nuvemAtualizar").addEventListener("click", atualizarNuvem);
  document.getElementById("nuvemOcultar").addEventListener("keydown", (e) => {
    if (e.key === "Enter") atualizarNuvem();
  });
  saida.addEventListener("click", (evento) => {
    const palavra = evento.target.closest("text[data-termo]");
    if (!palavra) return;
    const campo = document.getElementById("nuvemOcultar");
    const atual = campo.value.split(",").map((t) => t.trim()).filter(Boolean);
    if (!atual.includes(palavra.dataset.termo)) atual.push(palavra.dataset.termo);
    campo.value = atual.join(", ");
    atualizarNuvem();
  });
  atualizarNuvem();
}

async function atualizarRajadas() {
  const saida = document.getElementById("rajadaSaida");
  if (!saida || !estado.projeto) return;
  const parametrosUrl = new URLSearchParams({
    caminho: estado.projeto.caminho,
    tipo: document.getElementById("rajadaTipo").value,
    minimo: document.getElementById("rajadaMinimo").value,
  });
  saida.textContent = "Calculando…";
  try {
    const dados = await pedirTexto(`/api/rajadas?${parametrosUrl}`);
    const avisos = (dados.avisos || []).map((a) => `<p class="bib-nota bib-aviso">${bibEsc(a)}</p>`).join("");
    saida.innerHTML = avisos + (dados.svg ? `<div class="bib-rolagem">${dados.svg}</div>` : "") +
      '<p class="bib-nota">Força: ganho de verossimilhança do estado de rajada (s = 2, γ = 1). ' +
      "A contagem é de documentos do corpus que usam o termo ou citam a referência, " +
      "e não de citações recebidas.</p>";
  } catch (erro) {
    saida.innerHTML = `<p class="bib-vazio">${bibEsc(erro.message)}</p>`;
  }
}

function iniciarRajadas() {
  const tipo = document.getElementById("rajadaTipo");
  if (!tipo) return;
  tipo.addEventListener("change", atualizarRajadas);
  document.getElementById("rajadaMinimo").addEventListener("change", atualizarRajadas);
  atualizarRajadas();
}

/* ------------------------------------------------ fluxo Autor – País – IES */

function secaoFluxo() {
  const opcoes = (valores, padrao) => valores.map((v) =>
    `<option value="${v}"${v === padrao ? " selected" : ""}>${v}</option>`).join("");
  return secaoBib("Fluxo Autor – País – IES",
    "De onde vêm os autores mais produtivos: autor, país de afiliação e instituição. A espessura é o número de documentos em que o par ocorre.",
    '<div class="bib-controles">' +
    `<label>Autores <select id="fluxoAutores">${opcoes([8, 10, 15, 20, 30], 15)}</select></label>` +
    `<label>Países <select id="fluxoPaises">${opcoes([5, 8, 10, 15, 20], 10)}</select></label>` +
    `<label>Instituições <select id="fluxoIes">${opcoes([8, 10, 15, 20, 30], 15)}</select></label>` +
    '<a class="botao-mini" id="fluxoBaixar" href="#" download="fluxo-autor-pais-ies.svg">Baixar SVG</a></div>' +
    '<div id="fluxoSaida" class="bib-saida">Calculando…</div>',
    "bib-larga bib-fluxo");
}

function parametrosFluxo() {
  const valor = (id) => (document.getElementById(id) || {}).value || "";
  return new URLSearchParams({
    caminho: estado.projeto ? estado.projeto.caminho : "",
    autores: valor("fluxoAutores"), paises: valor("fluxoPaises"), ies: valor("fluxoIes"),
  });
}

function urlBaixarFluxo() {
  const parametrosUrl = parametrosFluxo();
  parametrosUrl.set("baixar", "1");
  return `/api/fluxo?${parametrosUrl}`;
}

function tabelaFluxo(d) {
  const nome = Object.fromEntries(d.nos.map((n) => [n.id, n.nome]));
  const linhas = d.ligacoes.slice().sort((a, b) => b.valor - a.valor).map((l) =>
    `<tr><td>${bibEsc(nome[l.origem])}</td><td>${bibEsc(nome[l.destino])}</td><td class="num">${bibNum.format(l.valor)}</td></tr>`).join("");
  return '<details class="bib-detalhes"><summary>Ver os fluxos como tabela</summary>' +
    '<div class="bib-rolagem"><table class="bib-tabela"><thead><tr><th>De</th><th>Para</th><th class="num">Documentos</th></tr></thead>' +
    `<tbody>${linhas}</tbody></table></div></details>`;
}

async function atualizarFluxo() {
  const saida = document.getElementById("fluxoSaida");
  if (!saida || !estado.projeto) return;
  const baixar = document.getElementById("fluxoBaixar");
  saida.textContent = "Calculando…";
  try {
    const d = await api(`/api/fluxo?${parametrosFluxo()}`);
    const avisos = (d.avisos || []).length
      ? `<div class="bib-lacunas"><b>O que falta</b><ul>${d.avisos.map((t) => `<li>${bibEsc(t)}</li>`).join("")}</ul></div>` : "";
    const nota = d.svg
      ? `<p class="bib-nota">${bibEsc((d.notas || []).join(" "))} Qualidade da ligação: ${bibEsc(d.rotulo_qualidade || "")}.</p>` : "";
    saida.innerHTML = avisos + (d.svg ? `<div class="bib-rolagem">${d.svg}</div>${nota}${tabelaFluxo(d)}` : "");
    if (baixar) {
      baixar.href = d.svg ? urlBaixarFluxo() : "#";
      baixar.toggleAttribute("hidden", !d.svg);
    }
  } catch (erro) {
    saida.innerHTML = `<p class="bib-vazio">${bibEsc(erro.message)}</p>`;
  }
}

function iniciarFluxo() {
  const autores = document.getElementById("fluxoAutores");
  if (!autores) return;
  for (const id of ["fluxoAutores", "fluxoPaises", "fluxoIes"]) {
    document.getElementById(id).addEventListener("change", atualizarFluxo);
  }
  atualizarFluxo();
}
