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

  painel.innerHTML =
    `<div class="info-geral bib-cartoes">${cartoes}</div>` +
    secaoBib("Produção e citações por ano", "Documentos publicados (barras) e citações que esses documentos receberam (linha).",
      graficoProducao(d.producao), "bib-larga") +
    secaoBib("Documentos acumulados", "Total de documentos do corpus ao longo dos anos.",
      graficoAcumulado(d.producao), "bib-larga") +
    secaoNuvem() + secaoRajadas() +
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
    '<div class="bib-grade bib-leis">' +
    secaoBib("Lei de Lotka", lotkaTxt, graficoLogLog(d.lotka.pontos, "documentos", "proporcao",
      (pt) => pt.esperada, "Documentos por autor", "Proporção de autores")) +
    secaoBib("Lei de Bradford", bradfordTxt, zonas) +
    secaoBib("Lei de Zipf", zipfTxt, graficoLogLog(d.zipf.pontos, "posto", "frequencia", null,
      "Posição da palavra", "Frequência")) +
    "</div>";
  iniciarNuvem();
  iniciarRajadas();
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
      "Diferente do CiteSpace, a contagem é de documentos do corpus que usam o termo ou citam a referência, " +
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
