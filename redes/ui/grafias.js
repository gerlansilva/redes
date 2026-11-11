/* Revisão de grafias: variantes de autores, palavras-chave, IES e países, com agrupamento. */
"use strict";

const GRAFIA = { dados: null, tipo: "autor" };

function grafiaEsc(texto) {
  return String(texto ?? "").replace(/[&<>"]/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function grafiaChave(tipo) {
  return `redes.grafias.${tipo}`;
}

function grafiaCarregarLista() {
  try {
    $("grafiaLista").value = localStorage.getItem(grafiaChave($("grafiaTipo").value)) || "";
  } catch (e) { /* sem armazenamento: segue vazio */ }
}

function grafiaGuardarLista() {
  try {
    localStorage.setItem(grafiaChave($("grafiaTipo").value), $("grafiaLista").value);
  } catch (e) { /* sem armazenamento: a lista vale só nesta sessão */ }
}

async function grafiaBuscar() {
  if (!estado.projeto) return;
  const tipo = $("grafiaTipo").value;
  const botao = $("btnGrafiaBuscar");
  botao.disabled = true;
  $("grafiaResumo").textContent = "Procurando…";
  try {
    grafiaGuardarLista();
    GRAFIA.tipo = tipo;
    GRAFIA.dados = await api("/api/sugestoes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caminho: estado.projeto.caminho, tipo, lista: $("grafiaLista").value }),
    });
    grafiaMostrar();
  } catch (erro) {
    $("grafiaResumo").textContent = "";
    mostrarToast(erro.message, true);
  } finally {
    botao.disabled = false;
  }
}

function grafiaMostrar() {
  const d = GRAFIA.dados;
  const caixa = $("grafiaResultado");
  const nomes = { autor: "autores", palavra: "palavras-chave", ies: "instituições", pais: "países" };
  const altas = d.grupos.filter((g) => g.confianca === "alta").length;
  $("grafiaResumo").textContent = d.total
    ? `${d.total} grupo(s) de variantes em ${d.itens} ${nomes[d.tipo]}` +
      (altas ? ` · ${altas} de confiança alta` : "") +
      (d.total > d.grupos.length ? ` · mostrando ${d.grupos.length}` : "")
    : `Nenhuma variante encontrada em ${d.itens} ${nomes[d.tipo]}.`;
  $("grafiaAcoes").hidden = !d.grupos.length;

  const partes = d.grupos.map((g, i) => {
    const membros = g.membros.map((m) =>
      `<li><span>${grafiaEsc(m.nome)}</span><b>${m.documentos}</b></li>`).join("");
    const opcoes = g.membros.map((m) => `<option value="${grafiaEsc(m.nome)}">`).join("");
    return `<div class="grafia-grupo ${g.confianca}" data-i="${i}">
      <label class="grafia-marca"><input type="checkbox" class="grafia-sel" ${g.confianca === "alta" ? "checked" : ""}>
        <span class="g-selo ${g.confianca}">${g.confianca === "alta" ? "Confiança alta" : "Conferir"}</span>
        ${g.informada ? '<span class="g-selo informada">Da sua lista</span>' : ""}</label>
      <div class="grafia-corpo">
        <label class="grafia-final"><span>Grafia final</span>
          <input class="grafia-canonico" list="grafia-opcoes-${i}" value="${grafiaEsc(g.canonico)}" spellcheck="false">
          <datalist id="grafia-opcoes-${i}">${opcoes}</datalist></label>
        <ul class="grafia-membros">${membros}</ul>
        <div class="dica">${grafiaEsc(g.motivo)}</div>
      </div></div>`;
  });
  let faltou = "";
  if (d.sem_correspondencia && d.sem_correspondencia.length) {
    faltou = `<p class="dica grafia-faltou">Sem correspondência na base: ${
      d.sem_correspondencia.map(grafiaEsc).join("; ")}.</p>`;
  }
  caixa.innerHTML = partes.join("") + faltou;
}

function grafiaMarcar(modo) {
  document.querySelectorAll("#grafiaResultado .grafia-grupo").forEach((cartao) => {
    const marcar = modo === "alta" ? cartao.classList.contains("alta") : false;
    cartao.querySelector(".grafia-sel").checked = marcar;
  });
}

async function grafiaAplicar() {
  const agrupamentos = [];
  document.querySelectorAll("#grafiaResultado .grafia-grupo").forEach((cartao) => {
    if (!cartao.querySelector(".grafia-sel").checked) return;
    const grupo = GRAFIA.dados.grupos[Number(cartao.dataset.i)];
    agrupamentos.push({
      canonico: cartao.querySelector(".grafia-canonico").value.trim(),
      membros: grupo.membros.map((m) => m.id),
    });
  });
  if (!agrupamentos.length) {
    mostrarToast("Marque ao menos um grupo para agrupar.", true);
    return;
  }
  if (agrupamentos.some((a) => !a.canonico)) {
    mostrarToast("Toda grafia final precisa de um texto.", true);
    return;
  }
  await editarBase({ acao: "agrupar-sugestoes", tipo: GRAFIA.tipo, agrupamentos });
  await grafiaBuscar();
}

function iniciarGrafias() {
  if (!$("btnGrafiaBuscar")) return;
  $("btnGrafiaBuscar").addEventListener("click", grafiaBuscar);
  $("btnGrafiaAplicar").addEventListener("click", grafiaAplicar);
  $("btnGrafiaAlta").addEventListener("click", () => grafiaMarcar("alta"));
  $("btnGrafiaLimpar").addEventListener("click", () => grafiaMarcar("nenhuma"));
  $("grafiaTipo").addEventListener("change", () => {
    grafiaCarregarLista();
    GRAFIA.dados = null;
    $("grafiaResultado").innerHTML = "";
    $("grafiaResumo").textContent = "";
    $("grafiaAcoes").hidden = true;
  });
  $("grafiaLista").addEventListener("change", grafiaGuardarLista);
  grafiaCarregarLista();
}

document.addEventListener("DOMContentLoaded", iniciarGrafias);
