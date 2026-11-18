/* Exportação dos gráficos da Visão geral descritiva: SVG, PNG (2x, fundo branco) e dados (CSV).
   Tudo roda no navegador; nada sai da máquina e nenhuma fonte externa é usada. */
"use strict";

const EXPORTAR_BIB = { dados: {} };
const FONTE_SEGURA = "Helvetica, Arial, sans-serif";
const ICONE_SALVAR = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" ' +
  'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
  '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/></svg>';

function botaoExportarBib() {
  return '<span class="bib-exp">' +
    `<button type="button" class="bib-exportar" title="Salvar gráfico" aria-label="Salvar gráfico" ` +
    `aria-haspopup="menu" aria-expanded="false">${ICONE_SALVAR}</button>` +
    '<span class="bib-exp-menu" role="menu" hidden>' +
    '<button type="button" role="menuitem" data-exp-bib="svg">SVG</button>' +
    '<button type="button" role="menuitem" data-exp-bib="png">PNG</button>' +
    '<button type="button" role="menuitem" data-exp-bib="csv">Dados (CSV)</button></span></span>';
}

function nomeArquivoBib(titulo, extensao) {
  const limpo = (t) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const projeto = limpo(estado.projeto ? estado.projeto.nome : "projeto") || "projeto";
  return `${projeto}-${limpo(titulo) || "grafico"}.${extensao}`;
}

function baixarBlobBib(blob, nome) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

function escXml(texto) {
  return String(texto ?? "").replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function quebraLinhas(texto, maximo) {
  const linhas = [];
  let atual = "";
  for (const palavra of String(texto || "").split(/\s+/).filter(Boolean)) {
    if ((atual + " " + palavra).trim().length > maximo && atual) { linhas.push(atual); atual = palavra; }
    else atual = (atual + " " + palavra).trim();
  }
  if (atual) linhas.push(atual);
  return linhas;
}

/* ------------------------------------------------------ dados da seção */

function tabelasDaSecao(secao) {
  return [...secao.querySelectorAll("table.bib-tabela")].map((tabela) => ({
    colunas: [...tabela.querySelectorAll("thead th")].map((th) => th.textContent.trim()),
    linhas: [...tabela.querySelectorAll("tbody tr")].map((tr) =>
      [...tr.querySelectorAll("td")].map((td) => td.textContent.trim())),
    titulo: tabela.getAttribute("aria-label") || "",
  }));
}

function barrasDaSecao(secao) {
  const linhas = [...secao.querySelectorAll(".bib-barra")].map((b) => [
    (b.querySelector(".bib-nome") || {}).textContent || "", (b.querySelector("b") || {}).textContent || ""]);
  return linhas.length ? [{ colunas: ["Item", "Documentos"], linhas, titulo: "" }] : [];
}

// Valores plotados: os registrados na renderização ou, na falta deles, as tabelas e barras da seção.
function blocosDeDados(secao, titulo) {
  const registrado = EXPORTAR_BIB.dados[titulo];
  if (registrado) return [registrado];
  const tabelas = tabelasDaSecao(secao);
  return tabelas.length ? tabelas : barrasDaSecao(secao);
}

function numeroCsv(valor) {
  if (valor === null || valor === undefined) return "";
  if (typeof valor === "number") return Number.isInteger(valor) ? String(valor) : String(valor).replace(".", ",");
  return String(valor);
}

function celulaCsv(valor) {
  const texto = numeroCsv(valor);
  return /[";\n\r]/.test(texto) ? `"${texto.replace(/"/g, '""')}"` : texto;
}

function gerarCsv(blocos) {
  const partes = blocos.map((b) => [b.colunas.map(celulaCsv).join(";"),
    ...b.linhas.map((l) => l.map(celulaCsv).join(";"))].join("\r\n"));
  return "﻿" + partes.join("\r\n\r\n") + "\r\n";
}

/* ------------------------------------------------------------ figura */

function svgDaSecao(secao) {
  return [...secao.querySelectorAll("svg")].find((s) => !s.closest("header") && !s.closest(".bib-controles")) || null;
}

function dimensoesSvg(svg) {
  const vb = svg.viewBox && svg.viewBox.baseVal;
  if (vb && vb.width) return [vb.width, vb.height];
  return [parseFloat(svg.getAttribute("width")) || 600, parseFloat(svg.getAttribute("height")) || 300];
}

// Gráfico de barras horizontais feito a partir da tabela (para seções sem SVG próprio).
function svgDeBarras(bloco) {
  const colunaNumerica = bloco.colunas.findIndex((c, i) => i > 0 &&
    bloco.linhas.length && bloco.linhas.every((l) => /^[\d.,\s]+$/.test(l[i] || "")));
  if (colunaNumerica < 0) return null;
  const linhas = bloco.linhas.slice(0, 20);
  const valor = (l) => Number(String(l[colunaNumerica]).replace(/\./g, "").replace(",", ".")) || 0;
  const maior = Math.max(1, ...linhas.map(valor));
  const L = 760, margemE = 300, passo = 24, topo = 8;
  const A = topo + passo * linhas.length + 8;
  const barras = linhas.map((l, i) => {
    const y = topo + i * passo;
    const nome = l[0].length > 46 ? l[0].slice(0, 45) + "…" : l[0];
    const largura = ((L - margemE - 70) * valor(l)) / maior;
    return `<text x="${margemE - 8}" y="${y + 15}" text-anchor="end" font-size="12" fill="#33405E">${escXml(nome)}</text>` +
      `<rect x="${margemE}" y="${y + 3}" width="${largura.toFixed(1)}" height="16" rx="3" fill="#2F2BFF" fill-opacity=".85"/>` +
      `<text x="${(margemE + largura + 6).toFixed(1)}" y="${y + 15}" font-size="12" fill="#14204A">${escXml(l[colunaNumerica])}</text>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${L} ${A}" width="${L}" height="${A}" ` +
    `font-family="${FONTE_SEGURA}">${barras}</svg>`;
}

// Monta o arquivo final: título, descrição, a figura e a legenda, sobre fundo branco.
function comporFigura(secao, titulo) {
  const descricao = (secao.querySelector("header p") || {}).textContent || "";
  const legenda = [...secao.querySelectorAll(".bib-legenda span")].map((s) => s.textContent.trim());
  let interior, largura, altura;
  const original = svgDaSecao(secao);
  if (original) {
    [largura, altura] = dimensoesSvg(original);
    const copia = original.cloneNode(true);
    copia.removeAttribute("width"); copia.removeAttribute("height"); copia.removeAttribute("style");
    copia.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    if (!copia.getAttribute("viewBox")) copia.setAttribute("viewBox", `0 0 ${largura} ${altura}`);
    if (!copia.getAttribute("font-family")) copia.setAttribute("font-family", FONTE_SEGURA);
    interior = copia;
  } else {
    const blocos = blocosDeDados(secao, titulo);
    const texto = blocos.length ? svgDeBarras(blocos[0]) : null;
    if (!texto) return null;
    const doc = new DOMParser().parseFromString(texto, "image/svg+xml").documentElement;
    [largura, altura] = dimensoesSvg(doc);
    interior = doc;
  }
  const W = Math.max(Math.ceil(largura), 640), margem = 24;
  const colunas = Math.floor((W - 2 * margem) / 6.6);
  const linhasDescricao = quebraLinhas(descricao, colunas);
  const rodape = [...quebraLinhas(legenda.join("  ·  "), colunas),
    `Projeto: ${estado.projeto ? estado.projeto.nome : ""} · Redes`];
  const cabecalho = 40 + 16 * linhasDescricao.length + 8;
  const H = cabecalho + Math.ceil(altura) + 14 + 16 * rodape.length + 12;
  const x = (W - largura) / 2;
  interior.setAttribute("x", x.toFixed(1)); interior.setAttribute("y", String(cabecalho));
  interior.setAttribute("width", String(largura)); interior.setAttribute("height", String(altura));
  const texto = (linhas, y0, tam, cor, peso = "normal") => linhas.map((l, i) =>
    `<text x="${margem}" y="${y0 + 16 * i}" font-size="${tam}" font-weight="${peso}" fill="${cor}">${escXml(l)}</text>`).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" ` +
    `font-family="${FONTE_SEGURA}" role="img" aria-label="${escXml(titulo)}">` +
    `<rect width="100%" height="100%" fill="#ffffff"/>` +
    `<text x="${margem}" y="28" font-size="18" font-weight="700" fill="#14204A">${escXml(titulo)}</text>` +
    texto(linhasDescricao, 48, 12, "#64748B") +
    new XMLSerializer().serializeToString(interior) +
    texto(rodape, cabecalho + Math.ceil(altura) + 24, 11, "#64748B") + `</svg>`;
  return { svg, largura: W, altura: H };
}

function svgParaPng(svg, largura, altura) {
  return new Promise((resolver, rejeitar) => {
    const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
    const imagem = new Image();
    imagem.onload = () => {
      const escala = 2;
      const tela = document.createElement("canvas");
      tela.width = Math.round(largura * escala);
      tela.height = Math.round(altura * escala);
      const ctx = tela.getContext("2d");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, tela.width, tela.height);
      ctx.drawImage(imagem, 0, 0, tela.width, tela.height);
      URL.revokeObjectURL(url);
      tela.toBlob((blob) => (blob ? resolver(blob) : rejeitar(new Error("não foi possível gerar o PNG"))), "image/png");
    };
    imagem.onerror = () => { URL.revokeObjectURL(url); rejeitar(new Error("não foi possível desenhar o gráfico")); };
    imagem.src = url;
  });
}

/* ------------------------------------------------------------- ações */

function tituloDaSecao(secao) {
  return (secao.querySelector("header h3") || {}).textContent || "grafico";
}

async function exportarSecaoBib(secao, formato) {
  const titulo = tituloDaSecao(secao);
  try {
    if (formato === "csv") {
      const blocos = blocosDeDados(secao, titulo);
      if (!blocos.length) throw new Error("este gráfico não tem dados tabulares para exportar");
      baixarBlobBib(new Blob([gerarCsv(blocos)], { type: "text/csv;charset=utf-8" }), nomeArquivoBib(titulo, "csv"));
      return;
    }
    const figura = comporFigura(secao, titulo);
    if (!figura) throw new Error("este gráfico ainda não está pronto para exportar");
    if (formato === "svg") {
      baixarBlobBib(new Blob([figura.svg], { type: "image/svg+xml;charset=utf-8" }), nomeArquivoBib(titulo, "svg"));
    } else {
      const png = await svgParaPng(figura.svg, figura.largura, figura.altura);
      baixarBlobBib(png, nomeArquivoBib(titulo, "png"));
    }
  } catch (erro) {
    if (typeof mostrarToast === "function") mostrarToast(erro.message, true);
  }
}

function fecharMenusBib(exceto) {
  for (const menu of document.querySelectorAll(".bib-exp-menu")) {
    if (menu === exceto) continue;
    menu.hidden = true;
    const botao = menu.parentElement.querySelector(".bib-exportar");
    if (botao) botao.setAttribute("aria-expanded", "false");
  }
}

// Liga os botões de uma renderização nova; `dados` registra os valores plotados por título.
function instalarExportacaoBib(painel, registros) {
  EXPORTAR_BIB.dados = registros || {};
  if (painel.dataset.exportacaoLigada) return;
  painel.dataset.exportacaoLigada = "1";
  painel.addEventListener("click", (evento) => {
    const botao = evento.target.closest(".bib-exportar");
    if (botao) {
      const menu = botao.parentElement.querySelector(".bib-exp-menu");
      const secao = botao.closest(".bib-secao");
      const abrir = menu.hidden;
      fecharMenusBib(abrir ? menu : null);
      menu.hidden = !abrir;
      botao.setAttribute("aria-expanded", abrir ? "true" : "false");
      if (abrir) {
        const csv = menu.querySelector('[data-exp-bib="csv"]');
        csv.hidden = blocosDeDados(secao, tituloDaSecao(secao)).length === 0;
        // Gráficos que carregam depois (nuvem, rajadas, fluxo) só oferecem SVG e PNG quando prontos.
        const pronta = Boolean(svgDaSecao(secao)) || (!csv.hidden && Boolean(blocosDeDados(secao, tituloDaSecao(secao))[0]
          && svgDeBarras(blocosDeDados(secao, tituloDaSecao(secao))[0])));
        menu.querySelector('[data-exp-bib="svg"]').hidden = !pronta;
        menu.querySelector('[data-exp-bib="png"]').hidden = !pronta;
        const primeiro = menu.querySelector("button:not([hidden])");
        if (primeiro) primeiro.focus();
      }
      return;
    }
    const item = evento.target.closest("[data-exp-bib]");
    if (item) {
      const secao = item.closest(".bib-secao");
      fecharMenusBib(null);
      exportarSecaoBib(secao, item.dataset.expBib);
      return;
    }
  });
  painel.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") {
      const aberto = painel.querySelector(".bib-exp-menu:not([hidden])");
      if (aberto) { const b = aberto.parentElement.querySelector(".bib-exportar"); fecharMenusBib(null); b.focus(); }
    }
  });
  document.addEventListener("click", (evento) => {
    if (!evento.target.closest(".bib-exp")) fecharMenusBib(null);
  });
}
