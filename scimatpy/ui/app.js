"use strict";

const $ = (id) => document.getElementById(id);
const nf = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

const UNIDADES = {
  Words: "Palavras", Authors: "Autores", References: "Referências",
  AuthorsReference: "Autores de referência",
  ReferenceSources: "Fontes de referência", Countries: "Países",
};
const TOTAL_POR_PERIODO = Object.keys(UNIDADES).length * 27;
const ALGORITMOS = {
  CentersSimples: "Centros simples", AverageLink: "Média",
  CompleteLink: "Completa", SingleLink: "Simples", SumLink: "Soma",
  Louvain: "Louvain",
};
const QUADRANTES = {
  motor: "Motor", nicho: "Nicho", basico: "Básico", emergente: "Emergente",
};
const QUADRANTES_PAISES = {
  motor: "Núcleo", nicho: "Isolado", basico: "Disperso", emergente: "Periférico",
};
function rotuloQuadrante(chave, unidade) {
  return (unidade === "Countries" ? QUADRANTES_PAISES : QUADRANTES)[chave];
}
const MEDIDAS_TEMPORAIS = {
  EquivalenceIndex: "índice de equivalência",
  AssociationStrength: "força de associação",
  InclusionIndex: "índice de inclusão",
  JaccardIndex: "índice de Jaccard",
  SaltonCosine: "cosseno de Salton",
};

const GRUPOS_ANALISE = {
  conceitual: "Estrutura conceitual",
  citados: "Estrutura intelectual",
  referencias: "Estrutura intelectual",
  frentes: "Estrutura intelectual",
  autores: "Estrutura social",
  paises: "Estrutura social",
  veiculos: "Fontes",
};
const ROTULO_UNIDADE = {
  Words: "Palavras", Authors: "Autores", References: "Referências",
  AuthorsReference: "Autores de referência",
  ReferenceSources: "Fontes de referência", Countries: "Países",
};
const ROTULO_MATRIZ = {
  CoOccurrence: "Co-ocorrência", BasicCoupling: "Acoplamento",
  AggregatedCouplingBasedOnAuthor: "Acoplamento agregado (autor)",
  AggregatedCouplingBasedOnJournal: "Acoplamento agregado (periódico)",
};

const CONFIG_ABAS = {
  conceitual: { abas: ["rede", "diagrama", "agrupamentos", "grupos", "indices", "documentos", "longitudinal"],
                padrao: "diagrama", redeRotulo: "Rede de co-ocorrência" },
  citados: { abas: ["rede", "diagrama", "agrupamentos", "grupos", "indices", "longitudinal"],
             padrao: "rede", redeRotulo: "Rede de cocitação" },
  referencias: { abas: ["rede", "diagrama", "agrupamentos", "grupos", "indices", "longitudinal"],
                 padrao: "rede", redeRotulo: "Rede de cocitação" },
  frentes: { abas: ["rede", "diagrama", "agrupamentos", "grupos", "indices", "documentos", "longitudinal"],
             padrao: "rede", redeRotulo: "Rede de acoplamento" },
  autores: { abas: ["rede", "diagrama", "agrupamentos", "grupos", "indices", "longitudinal"],
             padrao: "rede", redeRotulo: "Rede de coautoria" },
  paises: { abas: ["paises", "rede", "diagrama", "agrupamentos", "grupos", "indices", "longitudinal"],
            padrao: "paises", redeRotulo: "Rede de países" },
  veiculos: { abas: ["rede", "diagrama", "agrupamentos", "grupos", "indices", "longitudinal"],
              padrao: "rede", redeRotulo: "Rede de periódicos" },
};
const ABAS_TODAS = ["resumo", "rede", "paises", "diagrama", "agrupamentos",
                    "grupos", "indices", "documentos", "longitudinal"];
// No modo simples só aparecem estas abas; as demais ficam no modo avançado.
const ABAS_SIMPLES = ["resumo", "rede", "paises", "diagrama", "longitudinal"];

// Limites da frequência mínima automática (modo simples).
const LIMITE_TEMAS = 14;
const MINIMO_TEMAS = 4;
const FREQUENCIA_MAXIMA_AUTO = 6;
// Resumo: temas com menos documentos que isto vão para "Outros".
const DOCS_MINIMOS_RESUMO = 3;
const MAXIMO_TEMAS_RESUMO = 12;
const FRACAO_TEMA_GENERICO = 0.35;

const SUBSTANTIVO_GRUPO = {
  Words: ["tema", "temas"],
  Authors: ["grupo de autores", "grupos de autores"],
  AuthorsReference: ["grupo de autores citados", "grupos de autores citados"],
  References: ["grupo de referências", "grupos de referências"],
  ReferenceSources: ["grupo de periódicos", "grupos de periódicos"],
  Countries: ["grupo de países", "grupos de países"],
};
const INTERPRETACAO = {
  motor: "Centrais e bem desenvolvidos: sustentam o campo.",
  basico: "Centrais, mas ainda pouco desenvolvidos: assuntos de base que atravessam o campo.",
  nicho: "Bem desenvolvidos, porém isolados: assuntos especializados.",
  emergente: "Pouco centrais e pouco desenvolvidos: temas em surgimento ou em declínio.",
};
const INTERPRETACAO_PAISES = {
  motor: "Países centrais e muito conectados na colaboração.",
  basico: "Países com muitas ligações, mas pouco coesas entre si.",
  nicho: "Parcerias intensas, porém fechadas entre poucos países.",
  emergente: "Países na periferia da rede de colaboração.",
};
const ORDEM_QUADRANTES = ["motor", "basico", "nicho", "emergente"];

const ANALISES = [
  { chave: "conceitual", nome: "Estrutura conceitual",
    descricao: "Palavras-chave em co-ocorrência: os temas que estruturam o campo.",
    unidade: "Words", matriz: "CoOccurrence", similaridade: "EquivalenceIndex",
    algoritmo: "CentersSimples", mapeadores: "nucleo,interseccao",
    palavras: "autor,fonte", corte: "0", rede: "2-15" },
  { chave: "autores", nome: "Colaboração entre autores",
    descricao: "Quem publica com quem, pela co-ocorrência de autores nos documentos.",
    unidade: "Authors", matriz: "CoOccurrence", similaridade: "EquivalenceIndex",
    algoritmo: "CentersSimples", mapeadores: "nucleo,interseccao",
    palavras: "autor,fonte", corte: "0", rede: "2-15" },
  { chave: "paises", nome: "Colaboração entre países",
    descricao: "Cooperação internacional: países que assinam os mesmos documentos.",
    unidade: "Countries", matriz: "CoOccurrence", similaridade: "EquivalenceIndex",
    algoritmo: "CentersSimples", mapeadores: "nucleo,interseccao",
    palavras: "autor,fonte", corte: "0", rede: "2-15" },
  { chave: "citados", nome: "Cocitação de autores",
    descricao: "Autores citados em conjunto, formando a base intelectual do campo.",
    unidade: "AuthorsReference", matriz: "CoOccurrence",
    similaridade: "EquivalenceIndex", algoritmo: "CentersSimples",
    mapeadores: "nucleo,interseccao", palavras: "autor,fonte",
    corte: "0", rede: "2-15" },
  { chave: "referencias", nome: "Cocitação de referências",
    descricao: "Obras citadas em conjunto pelos documentos do corpus.",
    unidade: "References", matriz: "CoOccurrence",
    similaridade: "EquivalenceIndex", algoritmo: "CentersSimples",
    mapeadores: "nucleo,interseccao", palavras: "autor,fonte",
    corte: "0", rede: "2-15" },
  { chave: "frentes", nome: "Frentes de pesquisa",
    descricao: "Documentos ligados por referências compartilhadas (acoplamento bibliográfico).",
    unidade: "References", matriz: "BasicCoupling",
    similaridade: "EquivalenceIndex", algoritmo: "CentersSimples",
    mapeadores: "nucleo,interseccao", palavras: "autor,fonte",
    corte: "0", rede: "2-15" },
  { chave: "veiculos", nome: "Periódicos citados",
    descricao: "Periódicos citados em conjunto nas referências do corpus.",
    unidade: "ReferenceSources", matriz: "CoOccurrence",
    similaridade: "EquivalenceIndex", algoritmo: "CentersSimples",
    mapeadores: "nucleo,interseccao", palavras: "autor,fonte",
    corte: "0", rede: "2-15" },
];

const estado = {
  ignorar: [],
  projeto: null,
  freq: 1,
  resultado: null,
  trabalho: null,
  download: null,
  base: null,
  execucoes: [],
  contador: 0,
  temporizadorToast: null,
  token: null,
  pedidoGrupo: 0,
  desatualizada: false,
  aplicandoAnalise: false,
  avancado: false,
  calculando: false,
  pendente: false,
  autoFreq: true,
  temporizadorPrevia: null,
  docsToken: null,
};

document.addEventListener("DOMContentLoaded", iniciar);

async function iniciar() {
  prepararZoomEstrategico();
  let avancado = false;
  try { avancado = localStorage.getItem("redes.avancado") === "1"; } catch (_) { /* sem armazenamento */ }
  aplicarModo(avancado);
  ligarEventos();
  aplicaMenuRecolhido(localStorage.getItem("redes.menu.recolhido") === "1");
  $("freqValor").textContent = String(estado.freq);
  $("freqMenos").disabled = estado.freq <= 1;
  aplicarAnalise("conceitual");
  ajustarCorteAbas();
  window.addEventListener("resize", ajustarCorteAbas);
  document.querySelector(".abas").addEventListener("scroll", ajustarCorteAbas);
  await carregarInicio();
}

function ligarEventos() {
  $("fecharBase").addEventListener("click", fecharBase);
  $("modalBase").addEventListener("click", (evento) => {
    if (evento.target === $("modalBase")) fecharBase();
  });
  $("baseTipo").addEventListener("change", carregarBase);
  $("buscaBase").addEventListener("input", () => {
    if (estado.base) renderizarGruposBase(estado.base);
  });
  $("btnJuntar").addEventListener("click", juntarGruposBase);
  $("btnDesfazerBase").addEventListener("click", () => editarBase({ acao: "desfazer" }));
  $("btnSugerirPeriodos").addEventListener("click", () => {
    const quantidade = $("sugestaoQuantidade").value;
    editarBase({ acao: "sugerir-periodos", quantidade: quantidade ? Number(quantidade) : null });
  });
  $("formPeriodo").addEventListener("submit", (evento) => {
    evento.preventDefault();
    editarBase({
      acao: "criar-periodo",
      nome: $("periodoNome").value,
      inicio: Number($("periodoInicio").value),
      fim: Number($("periodoFim").value),
    });
  });
  $("formSubstituir").addEventListener("submit", (evento) => {
    evento.preventDefault();
    editarBase({
      acao: "substituir",
      tipo: $("baseTipo").value,
      de: $("substituirDe").value,
      para: $("substituirPara").value,
    });
  });
  $("fecharModal").addEventListener("click", fecharModal);
  $("modal").addEventListener("click", (evento) => {
    if (evento.target === $("modal")) fecharModal();
  });

  $("btnProjeto").addEventListener("click", abrirModal);
  $("marcaInicio").addEventListener("click", (evento) => {
    evento.preventDefault();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  document.querySelectorAll("[data-nav]").forEach((item) => {
    item.addEventListener("click", () => navegar(item.dataset.nav));
  });

  $("fecharAjuda").addEventListener("click", fecharAjuda);
  $("modalAjuda").addEventListener("click", (evento) => {
    if (evento.target === $("modalAjuda")) fecharAjuda();
  });
  $("fecharSobre").addEventListener("click", fecharSobre);
  $("modalSobre").addEventListener("click", (evento) => {
    if (evento.target === $("modalSobre")) fecharSobre();
  });
  $("btnRecolher").addEventListener("click", () => {
    const app = document.querySelector(".app");
    aplicaMenuRecolhido(!app.classList.contains("recolhida"));
  });
  $("btnAbrirCaminho").addEventListener("click", () => {
    const caminho = $("caminhoProjeto").value.trim();
    if (!caminho) { mostrarToast("Informe o caminho do projeto.", true); return; }
    abrir(caminho);
  });
  $("caminhoProjeto").addEventListener("keydown", (evento) => {
    if (evento.key === "Enter") $("btnAbrirCaminho").click();
  });

  $("btnPreview").addEventListener("click", previsualizar);
  $("btnGrade").addEventListener("click", rodarGrade);
  $("btnCancelar").addEventListener("click", cancelarTrabalho);
  $("btnExportar").addEventListener("click", () => {
    if (estado.download) window.location.href = estado.download;
  });
  $("exportarTipo").addEventListener("change", (evento) => {
    const tipo = evento.target.value;
    evento.target.value = "";
    if (!tipo) return;
    exportar(tipo);
  });
  $("btnRelatorio").addEventListener("click", () => gerarRelatorio("html"));

  $("freqMenos").addEventListener("click", () => mudaFrequencia(-1));
  $("freqMais").addEventListener("click", () => mudaFrequencia(1));
  $("modoAvancado").addEventListener("change", (evento) => {
    mudarModo(evento.target.checked);
  });
  $("periodo").addEventListener("change", () => {
    if (!estado.projeto) return;
    if (estado.avancado) {
      previsualizar();
    } else {
      redefinirFrequencia();
      mostrarCarregandoResumo();
      agendarPrevia();
    }
  });
  for (const id of ["unidade", "matriz", "similaridade", "algoritmo",
                    "mapeadores", "palavras", "corte", "rede"]) {
    $(id).addEventListener("change", () => {
      marcarDesatualizada();
      marcarPersonalizada();
    });
  }
  $("analise").addEventListener("change", () => {
    escolherAnalise($("analise").value, false);
  });
  document.querySelectorAll(".nav-analise[data-analise]").forEach((item) => {
    item.addEventListener("click", () => {
      const chave = item.dataset.analise;
      if (chave === "visao") {
        mostrarVisaoGeral();
        return;
      }
      escolherAnalise(chave, true);
    });
  });

  $("arquivo").addEventListener("change", escolheArquivo);
  $("formImportar").addEventListener("submit", importar);

  let temporizadorBusca = null;
  $("buscaDocumentos").addEventListener("input", () => {
    clearTimeout(temporizadorBusca);
    temporizadorBusca = setTimeout(carregarDocumentos, 250);
  });

  document.querySelectorAll(".aba[data-aba]").forEach((aba) => {
    const selecionar = () => selecionarAba(aba.dataset.aba);
    aba.addEventListener("click", selecionar);
    aba.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        selecionar();
      }
    });
  });

  $("fecharDrawer").addEventListener("click", fecharDrawer);
  $("drawer").addEventListener("click", (evento) => {
    if (evento.target === $("drawer")) fecharDrawer();
  });

  $("figHalo").addEventListener("click", () => {
    if ($("caixaHalo").dataset.arrastou === "1") return;
    abrirLightbox("figHalo");
  });
  $("figEstrategico").addEventListener("click", () => {
    if ($("caixaEstrategico").dataset.arrastou === "1") return;
    abrirLightbox("figEstrategico");
  });  $("figMapa").addEventListener("click", () => {
    if ($("caixaMapa").dataset.arrastou === "1") return;
    abrirLightbox("figMapa");
  });
  $("svgMapa").addEventListener("click", () => abrirLightbox("figMapa"));
  ligarMapa();
  ligarDiagrama();
  $("svgEstrategico").addEventListener("click", () => abrirLightbox("figEstrategico"));
  $("rotulosDiagrama").addEventListener("change", (evento) => {
    diagramaUI.rotulos = evento.target.value;
    desenharDiagrama();
  });
  $("svgRede").addEventListener("click", () => abrirLightbox("figHalo"));
  $("figAgrupamentos").addEventListener("click", () => abrirLightbox("figAgrupamentos"));
  $("svgAgrupamentos").addEventListener("click", () => abrirLightbox("figAgrupamentos"));
  $("rotulosRede").addEventListener("change", (evento) => {
    redeUI.rotulos = evento.target.value;
    agendarDesenho();
  });
  $("focoRede").addEventListener("change", (evento) => {
    redeUI.foco = Number(evento.target.value) || 0;
    agendarDesenho();
  });
  $("ajustarRede").addEventListener("click", ajustarRede);
  $("zoomHalo").addEventListener("click", (evento) => {
    const botao = evento.target.closest("[data-zoom]");
    if (!botao) return;
    const usandoCanvas = redeUI.dados && !$("canvasHalo").hidden;
    if (usandoCanvas) {
      const centro = [redeUI.largura / 2, redeUI.altura / 2];
      if (botao.dataset.zoom === "mais") zoomRede(1.3, centro[0], centro[1]);
      else if (botao.dataset.zoom === "menos") zoomRede(1 / 1.3, centro[0], centro[1]);
      else ajustarRede();
    } else if (zoomHalo) {
      zoomHalo.acao(botao.dataset.zoom);
    }
  });
  $("zoomEstrategico").addEventListener("click", (evento) => {
    const botao = evento.target.closest("[data-zoom]");
    if (!botao) return;
    const usandoCanvas = diagramaUI.dados && !$("canvasEstrategico").hidden;
    if (usandoCanvas) {
      zoomDiagrama(botao.dataset.zoom);
    } else if (zoomEstrategico) {
      zoomEstrategico.acao(botao.dataset.zoom);
    }
  });
  $("imagemLightbox").addEventListener("click", (evento) => evento.stopPropagation());
  $("lightbox").addEventListener("click", fecharLightbox);
  $("fecharLightbox").addEventListener("click", fecharLightbox);

  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") {
      fecharLightbox();
      fecharDrawer();
      fecharModal();
      fecharAjuda();
      fecharSobre();
    }
  });
}

/* ------------------------------------------------------------------- início */

async function carregarInicio() {
  try {
    const dados = await api("/api/projetos");
    $("workspace").textContent = `Projetos em ${dados.workspace}`;
    renderizarRecentes(dados.projetos);

    const ultimo = localStorage.getItem("scimatpy.projeto");
    let alvo = dados.projetos.find((projeto) => projeto.caminho === ultimo);
    if (!alvo && dados.projetos.length === 1) alvo = dados.projetos[0];

    if (alvo) {
      const aberto = await abrir(alvo.caminho);
      if (aberto) return;
    }
    abrirModal();
  } catch (erro) {
    mostrarToast(erro.message, true);
    abrirModal();
  }
}

function renderizarRecentes(projetos) {
  const caixa = $("recentes");
  caixa.replaceChildren();

  if (!projetos.length) {
    const vazio = document.createElement("div");
    vazio.className = "dica";
    vazio.style.cssText = "font-size:11.5px;color:#8A94A6";
    vazio.textContent = "Nenhum projeto ainda. Importe um corpus abaixo.";
    caixa.append(vazio);
    return;
  }

  for (const projeto of projetos) {
    const botao = document.createElement("button");
    botao.type = "button";
    botao.className = "recente";

    const bloco = document.createElement("div");
    const nome = document.createElement("div");
    nome.className = "nome";
    nome.textContent = projeto.nome;
    const caminho = document.createElement("div");
    caminho.className = "caminho";
    caminho.textContent = projeto.caminho;
    bloco.append(nome, caminho);

    const espaco = document.createElement("div");
    espaco.className = "espaco";
    const seta = document.createElement("span");
    seta.textContent = "→";
    seta.style.color = "#8A94A6";

    botao.append(bloco, espaco, seta);
    botao.addEventListener("click", () => abrir(projeto.caminho));
    caixa.append(botao);
  }
}

async function abrir(caminho) {
  if (trabalhoEmAndamento()) {
    mostrarToast("Aguarde a execução atual terminar.", true);
    return false;
  }
  try {
    const projeto = await api("/api/abrir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caminho }),
    });
    aplicarProjeto(projeto);
    fecharModal();
    await previsualizar();
    mostrarVisaoGeral();
    return true;
  } catch (erro) {
    mostrarToast(erro.message, true);
    return false;
  }
}

function aplicarProjeto(projeto) {
  // Descarta o que a tela guardava do projeto anterior (mesmo caminho reimportado inclusive).
  if (typeof BIB !== "undefined") {
    BIB.cache = {};
    const painel = $("visaoBibliometria");
    if (painel) painel.innerHTML = '<p class="bib-vazio">Calculando…</p>';
  }
  estado.projeto = projeto;
  estado.ignorar = [];
  estado.resultado = null;
  estado.download = null;
  estado.execucoes = [];
  estado.contador = 0;
  estado.token = null;
  redefinirFrequencia();
  localStorage.setItem("scimatpy.projeto", projeto.caminho);

  $("projetoNome").textContent = projeto.nome;
  $("projetoArquivo").textContent = "· " + nomeArquivo(projeto.caminho);
  const periodos = projeto.periodos.length;
  $("projetoMeta").textContent = `${projeto.documentos} documentos · ` +
    `${periodos} ${periodos === 1 ? "período" : "períodos"} · ` +
    `${projeto.unidades.length} unidades`;
  $("estado").classList.remove("erro");
  $("estadoTexto").textContent = "Base importada";

  const select = $("periodo");
  select.replaceChildren();
  for (const periodo of projeto.periodos) {
    const opcao = document.createElement("option");
    opcao.value = String(periodo.id);
    opcao.textContent = periodo.nome;
    select.append(opcao);
  }
  select.disabled = false;

  $("btnPreview").disabled = false;
  $("btnGrade").disabled = false;
  $("exportarTipo").disabled = true;
  $("btnRelatorio").disabled = true;
  $("btnExportar").disabled = true;
  $("rotuloGrade").textContent =
    `Grade completa · ${TOTAL_POR_PERIODO * periodos}`;

  const primeiro = projeto.periodos[0];
  const ultimo = projeto.periodos[projeto.periodos.length - 1];
  const inicio = primeiro ? primeiro.nome.split(/[–\-]/)[0].trim() : "";
  const fim = ultimo ? ultimo.nome.split(/[–\-]/).pop().trim() : "";
  $("vgPeriodo").textContent = inicio && fim ? `${inicio}–${fim}` : "—";
  $("vgDocumentos").textContent = nf.format(projeto.documentos);
  $("vgPeriodos").textContent = nf.format(projeto.periodos.length);
  $("vgUnidades").textContent = nf.format(projeto.unidades.length);

  limparResultado();
}

function limparResultado() {
  renderizarResumoVazio("Calculando o resumo…");
  limparRedeInterativa();
  redeUI.carregada = false;
  $("figHalo").hidden = true;
  $("figEstrategico").hidden = true;
  $("figAgrupamentos").hidden = true;
  $("vazioHalo").hidden = false;
  $("vazioEstrategico").hidden = false;
  $("vazioAgrupamentos").hidden = false;
  $("vazioHalo").textContent = "Execute uma prévia para ver a rede";
  $("vazioEstrategico").textContent = "Execute uma prévia para ver os quadrantes";
  $("vazioAgrupamentos").textContent = "Execute uma prévia para ver a rede de agrupamentos";
  $("svgAgrupamentos").hidden = true;
  $("estatHalo").replaceChildren();
  $("estatEstrategico").replaceChildren();
  for (const id of ["visaoDocumentos", "visaoNos", "visaoArestas", "visaoGrupos"]) {
    $(id).textContent = "—";
  }
  $("metaHalo").textContent = "—";
  $("metaEstrategico").textContent = "Callon · faixas normalizadas";
  $("metaGrupos").textContent = "ordenados por número de itens";
  $("metaAgrupamentos").textContent = "temas ligados pela associação entre seus itens";
  $("linkGrupos").textContent = "—";

  const corpo = $("gruposCorpo");
  corpo.replaceChildren();
  const linha = document.createElement("tr");
  const celula = document.createElement("td");
  celula.colSpan = 7;
  celula.style.color = "#8A94A6";
  celula.textContent = "Nenhuma análise executada.";
  linha.append(celula);
  corpo.append(linha);
  $("rodapeTabela").textContent =
    "Quadrantes pela mediana das faixas normalizadas de centralidade e densidade de Callon.";

  $("indicesCorpo").replaceChildren(linhaVazia("Nenhuma análise executada.", 12));
  $("linkIndices").textContent = "—";
  $("documentosCorpo").replaceChildren(linhaVazia("Nenhuma análise executada.", 6));
  $("metaDocumentos").textContent = "—";
  $("rodapeDocumentos").textContent = "—";
  $("mapasLongitudinais").hidden = true;
  $("vazioLongitudinal").hidden = false;
  $("vazioLongitudinal").textContent =
    "Abra a aba Comparar períodos para montar os mapas.";
  $("downloadEvolucao").hidden = true;
  $("metaLongitudinal").textContent = "evolução temática e sobreposição";
  $("rodapeLongitudinal").textContent =
    "A comparação usa os mesmos parâmetros da análise.";
}

/* ---------------------------------------------------------------- análise */

function parametros() {
  const [minimo, maximo] = $("rede").value.split("-").map(Number);
  const mapeadores = $("mapeadores").value.split(",").filter(Boolean);
  const palavras = $("palavras").value.split(",").filter(Boolean);
  return {
    projeto: estado.projeto.caminho,
    unidade: $("unidade").value,
    matriz: $("matriz").value,
    similaridade: $("similaridade").value,
    algoritmo: $("algoritmo").value,
    minimo_frequencia: estado.freq,
    minimo_coocorrencia: 1,
    tamanho_minimo: minimo,
    tamanho_maximo: maximo,
    corte: Number($("corte").value) || 0,
    mapeadores,
    palavras,
    periodo: Number($("periodo").value),
    ignorar: estado.ignorar || [],
  };
}

function selecionarAba(chave) {
  const aba = document.querySelector(`.aba[data-aba="${chave}"]`);
  if (!aba) return;
  for (const outra of document.querySelectorAll(".aba[data-aba]")) {
    const ativa = outra === aba;
    outra.classList.toggle("ativa", ativa);
    outra.setAttribute("aria-selected", ativa ? "true" : "false");
  }
  mostrarAba(chave);
  if (chave === "longitudinal") compararPeriodos();
}

function abasDaAnalise(chave) {
  const cfg = CONFIG_ABAS[chave];
  let abas = cfg ? ["resumo", ...cfg.abas] : ABAS_TODAS;
  const totalPeriodos = estado.projeto ? estado.projeto.periodos.length : 0;
  if (totalPeriodos < 2) abas = abas.filter((aba) => aba !== "longitudinal");
  if (!estado.avancado) abas = abas.filter((aba) => ABAS_SIMPLES.includes(aba));
  return abas;
}

// manter: preserva a aba atual quando ela continua disponível.
function aplicarAbas(chave, manter = false) {
  const cfg = CONFIG_ABAS[chave];
  const abas = abasDaAnalise(chave);
  const abaRede = document.querySelector('.aba[data-aba="rede"]');
  if (abaRede) abaRede.textContent = (cfg && cfg.redeRotulo) || "Rede";
  for (const aba of document.querySelectorAll(".aba[data-aba]")) {
    aba.classList.toggle("oculta", !abas.includes(aba.dataset.aba));
  }
  const atual = document.querySelector(".aba.ativa");
  if (manter && atual && abas.includes(atual.dataset.aba)) {
    ajustarCorteAbas();
    return;
  }
  selecionarAba("resumo");
  ajustarCorteAbas();
}

const BLOCO_POR_ABA = {
  resumo: "blocoResumo",
  rede: "blocoRede",
  paises: "blocoPaises",
  diagrama: "blocoDiagrama",
  agrupamentos: "blocoAgrupamentos",
  grupos: "blocoGrupos",
  indices: "blocoIndices",
  documentos: "blocoDocumentos",
  longitudinal: "blocoLongitudinal",
};

function abaAtual() {
  const aba = document.querySelector(".aba.ativa");
  return aba ? aba.dataset.aba : "";
}

function mostrarAba(chave) {
  const alvo = BLOCO_POR_ABA[chave];
  if (!alvo) return;
  // Rede interativa e lista de documentos só são buscadas quando a aba abre.
  if (chave === "rede" && estado.resultado && !redeUI.carregada) {
    carregarRedeInterativa(estado.resultado);
  }
  if (chave === "documentos" && estado.token && estado.docsToken !== estado.token) {
    carregarDocumentos();
  }
  for (const bloco of document.querySelectorAll("[data-bloco]")) {
    const visivel = bloco.dataset.bloco === alvo;
    bloco.classList.toggle("oculta", !visivel);
    bloco.hidden = !visivel;
  }
  // Re-renderiza figuras que dependem do tamanho do canvas ao voltarem a ficar visíveis.
  if (chave === "rede" && typeof redeUI !== "undefined" && redeUI.dados) {
    agendarDesenho();
  }
  if (chave === "diagrama" && typeof diagramaUI !== "undefined" && diagramaUI.dados) {
    requestAnimationFrame(() => {
      ajustarCanvasDiagrama();
      desenharDiagrama();
    });
  }
  if (chave === "paises" && typeof mapaUI !== "undefined" && mapaUI.dados) {
    requestAnimationFrame(() => {
      ajustarCanvasMapa();
      desenharMapa();
    });
  }
}

function ajustarCorteAbas() {
  const abas = document.querySelector(".abas");
  if (!abas) return;
  const inicio = abas.scrollLeft > 1;
  const fim = abas.scrollLeft + abas.clientWidth < abas.scrollWidth - 1;
  abas.classList.toggle("corte-inicio", inicio);
  abas.classList.toggle("corte-fim", fim);
}

function analiseSelecionada() {
  return ANALISES.find((item) => item.chave === $("analise").value) || null;
}

function descricaoPersonalizada() {
  return "Personalizada — configuração manual: ajuste os parâmetros e execute a prévia.";
}

function mostrarVisaoGeral() {
  if (typeof carregarBibliometria === "function") carregarBibliometria();
  for (const item of document.querySelectorAll(".nav-analise[data-analise]")) {
    item.classList.toggle("ativa", item.dataset.analise === "visao");
  }
  const visao = $("visaoGeral");
  if (visao) {
    visao.classList.remove("oculta");
    visao.hidden = false;
  }
  for (const seletor of [".parametros", ".barra-resultados", ".acoes-finais"]) {
    const el = document.querySelector(seletor);
    if (el) el.classList.add("oculta");
  }
  for (const bloco of document.querySelectorAll("[data-bloco]")) {
    bloco.classList.add("oculta");
    bloco.hidden = true;
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function mostrarAnalise() {
  const visao = $("visaoGeral");
  if (visao) {
    visao.classList.add("oculta");
    visao.hidden = true;
  }
  for (const seletor of [".parametros", ".barra-resultados", ".acoes-finais"]) {
    const el = document.querySelector(seletor);
    if (el) el.classList.remove("oculta");
  }
}

function sincronizarAnalises() {
  const chave = $("analise").value;
  for (const item of document.querySelectorAll(".nav-analise[data-analise]")) {
    item.classList.toggle("ativa", item.dataset.analise === chave);
  }
  rotuloAnaliseAtual();
}

function rotuloAnaliseAtual() {
  const analise = analiseSelecionada();
  const chave = $("analise").value;
  const sobre = $("sobreAnalise");
  const titulo = $("tituloAnalise");
  const sub = $("subtituloAnalise");
  if (sobre) sobre.textContent = GRUPOS_ANALISE[chave] || "Visão geral";
  if (analise) {
    if (titulo) titulo.textContent = analise.nome;
    if (sub) sub.textContent = analise.descricao;
  } else {
    if (titulo) titulo.textContent = "Análise personalizada";
    if (sub) sub.textContent = "Configuração manual dos parâmetros do período.";
  }
}

function escolherAnalise(chave, executar) {
  if (chave === "personalizada") {
    marcarPersonalizada();
    return;
  }
  aplicarAnalise(chave);
  if (!executar) return;
  if (estado.avancado) {
    previsualizar();
  } else {
    redefinirFrequencia();
    mostrarCarregandoResumo();
    agendarPrevia();
  }
}

function aplicarAnalise(chave) {
  const analise = ANALISES.find((item) => item.chave === chave);
  if (!analise) return;
  mostrarAnalise();
  const valores = { unidade: analise.unidade, matriz: analise.matriz,
                    similaridade: analise.similaridade,
                    algoritmo: analise.algoritmo,
                    mapeadores: analise.mapeadores,
                    palavras: analise.palavras, corte: analise.corte,
                    rede: analise.rede };
  let mudou = false;
  for (const [campo, valor] of Object.entries(valores)) {
    if ($(campo).value !== valor) mudou = true;
  }
  estado.aplicandoAnalise = true;
  for (const [campo, valor] of Object.entries(valores)) $(campo).value = valor;
  estado.aplicandoAnalise = false;
  $("analise").value = analise.chave;
  const fixa = $("analiseFixa");
  if (fixa) {
    fixa.hidden = false;
    fixa.textContent =
      `Unidade: ${ROTULO_UNIDADE[analise.unidade] || analise.unidade}  ·  ` +
      `Matriz: ${ROTULO_MATRIZ[analise.matriz] || analise.matriz}`;
  }
  const campos = document.querySelector(".campos");
  if (campos) campos.classList.add("restringida");
  aplicarAbas(analise.chave);
  sincronizarAnalises();
  if (mudou) marcarDesatualizada();
}

function marcarPersonalizada() {
  if (estado.aplicandoAnalise) return;
  if ($("analise").value === "personalizada") return;
  $("analise").value = "personalizada";
  const fixa = $("analiseFixa");
  if (fixa) fixa.hidden = true;
  const campos = document.querySelector(".campos");
  if (campos) campos.classList.remove("restringida");
  aplicarAbas(null);
  sincronizarAnalises();
}

function marcarDesatualizada() {
  if (!estado.resultado) return;
  estado.desatualizada = true;
  const selo = $("seloPrevia");
  selo.textContent = "Prévia desatualizada";
  selo.classList.add("alerta");
}

/* ------------------------------------------------------- modo simples/avançado */

function aplicarModo(avancado) {
  estado.avancado = avancado;
  document.body.classList.toggle("modo-avancado", avancado);
  $("modoAvancado").checked = avancado;
}

function mudarModo(avancado) {
  aplicarModo(avancado);
  try { localStorage.setItem("redes.avancado", avancado ? "1" : "0"); } catch (_) { /* sem armazenamento */ }
  aplicarAbas($("analise").value, true);
  if (!avancado && estado.projeto && estado.resultado) {
    // Volta ao modo simples: recalcula com a frequência mínima automática.
    redefinirFrequencia();
    mostrarCarregandoResumo();
    agendarPrevia();
  }
}

/* ------------------------------------------------------- execução da prévia */

function agendarPrevia(atraso = 350) {
  clearTimeout(estado.temporizadorPrevia);
  estado.temporizadorPrevia = setTimeout(previsualizar, atraso);
}

function atualizarFrequenciaTela() {
  $("freqValor").textContent = String(estado.freq);
  $("freqMenos").disabled = estado.freq <= 1;
}

function redefinirFrequencia() {
  estado.freq = 1;
  estado.autoFreq = true;
  atualizarFrequenciaTela();
  mostrarNotaAuto("");
}

function mostrarNotaAuto(texto) {
  const nota = $("notaAuto");
  nota.textContent = texto;
  nota.hidden = !texto;
}

function plural(n, singular, pluralTexto) {
  return `${nf.format(n)} ${n === 1 ? singular : pluralTexto}`;
}

function substantivoGrupo(resultado) {
  if (resultado.parametros.matriz === "BasicCoupling") {
    return ["frente de pesquisa", "frentes de pesquisa"];
  }
  return SUBSTANTIVO_GRUPO[resultado.parametros.unidade] || ["grupo", "grupos"];
}

function analisar() {
  return api("/api/analisa", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parametros()),
  });
}

// Modo simples: sobe a frequência mínima até sobrarem poucos temas, sem
// deixar a análise vazia, e explica o que foi feito.
async function ajustarFrequencia(resultado) {
  const inicial = estado.freq;
  const temasInicial = resultado.grupos.length;
  const [sing, plur] = substantivoGrupo(resultado);
  let atual = resultado;
  let recusado = null;
  while (atual.grupos.length > LIMITE_TEMAS && estado.freq < FREQUENCIA_MAXIMA_AUTO) {
    if (estado.pendente) return atual;
    estado.freq += 1;
    atualizarFrequenciaTela();
    $("estadoTexto").textContent = `Ajustando frequência (${estado.freq})…`;
    let proximo = null;
    try { proximo = await analisar(); } catch (_) { proximo = null; }
    if (!proximo || proximo.grupos.length < MINIMO_TEMAS) {
      recusado = proximo ? proximo.grupos.length : 0;
      estado.freq -= 1;
      atualizarFrequenciaTela();
      if (estado.pendente) return atual;
      atual = await analisar();
      break;
    }
    atual = proximo;
  }

  const final = atual.grupos.length;
  const partes = [];
  if (estado.freq > inicial) {
    partes.push(`Frequência mínima ajustada de ${inicial} para ${estado.freq} para evitar ` +
      `pulverização: eram ${plural(temasInicial, sing, plur)}, agora ${final}.`);
  } else if (recusado !== null) {
    partes.push(`Há ${plural(temasInicial, sing, plur)}, mas subir a frequência mínima ` +
      `deixaria só ${recusado}; mantive ${estado.freq}.`);
  }
  if (estado.freq > inicial && recusado !== null) {
    partes.push(`Subir mais deixaria só ${recusado}.`);
  }
  if (final > LIMITE_TEMAS && recusado === null && estado.freq > inicial) {
    partes.push(`Ainda restam ${plural(final, sing, plur)}; use + e − para ajustar.`);
  }
  mostrarNotaAuto(partes.join(" "));
  return atual;
}

async function previsualizar() {
  if (!estado.projeto) return;
  clearTimeout(estado.temporizadorPrevia);
  if (trabalhoEmAndamento()) {
    mostrarToast("Aguarde a grade terminar para pré-visualizar.", true);
    return;
  }
  if (estado.calculando) {
    // Já há um cálculo em curso: refaz com os parâmetros novos ao terminar.
    estado.pendente = true;
    return;
  }

  estado.calculando = true;
  estado.pendente = false;
  const botao = $("btnPreview");
  botao.dataset.calculando = "1";
  botao.disabled = true;
  botao.textContent = "Calculando…";
  $("carregandoHalo").hidden = false;
  $("carregandoEstrategico").hidden = false;
  $("estadoTexto").textContent = "Calculando…";
  if (!estado.resultado || estado.desatualizada) mostrarCarregandoResumo();

  try {
    let resultado = await analisar();
    if (!estado.avancado && estado.autoFreq) {
      resultado = await ajustarFrequencia(resultado);
    } else {
      mostrarNotaAuto("");
    }
    if (!estado.pendente) {
      estado.resultado = resultado;
      renderizarResultado(resultado);
    }
  } catch (erro) {
    mostrarToast(erro.message, true);
    renderizarResumoVazio(erro.message);
  } finally {
    estado.calculando = false;
    botao.dataset.calculando = "0";
    botao.disabled = !estado.projeto || trabalhoEmAndamento();
    botao.textContent = "Pré-visualizar";
    $("carregandoHalo").hidden = true;
    $("carregandoEstrategico").hidden = true;
    if (!trabalhoEmAndamento()) {
      $("estadoTexto").textContent = estado.projeto ? "Base importada" : "Sem projeto";
    }
    if (estado.pendente) {
      estado.pendente = false;
      previsualizar();
    }
  }
}

function renderizarResultado(resultado) {
  estado.token = resultado.token || null;
  estado.desatualizada = false;
  $("seloPrevia").textContent = "Prévia sob demanda";
  $("seloPrevia").classList.remove("alerta");
  fecharDrawer();
  renderizarResumo(resultado);
  const resumo = resultado.resumo;
  const unidade = UNIDADES[resultado.parametros.unidade];

  $("metaHalo").textContent =
    `${unidade} · ${resumo.grupos} agrupamentos · ${resumo.nos} nós`;
  $("metaEstrategico").textContent =
    `Callon · ${resultado.periodo.nome}`;
  $("metaGrupos").textContent =
    `${resultado.periodo.nome} · ${unidade.toLowerCase()}`;

  $("visaoDocumentos").textContent = nf.format(resumo.documentos);
  $("visaoNos").textContent = nf.format(resumo.nos);
  $("visaoArestas").textContent = nf.format(resumo.arestas);
  $("visaoGrupos").textContent = nf.format(resumo.grupos);
  $("visaoGruposDetalhe").textContent =
    resultado.parametros.unidade === "Countries"
      ? "grupos de países" : "temas identificados";

  const halo = resultado.figuras.halo;
  const estrategico = resultado.figuras.estrategico;
  const mapa = resultado.figuras.mapa;
  const paises = resultado.paises;

  if (mapa) {
    $("figMapa").src = mapa;
    $("figMapa").hidden = true;
    $("canvasMapa").hidden = false;
    $("vazioMapa").hidden = true;
    $("zoomMapa").hidden = false;
    $("svgMapa").hidden = false;
    $("notaMapa").hidden = false;
    $("metaMapa").textContent =
      `${resultado.periodo.nome} · ${paises.paises} países · ${paises.cooperacoes} cooperações`;
    $("estatMapa").replaceChildren(
      estatistica("Documentos", paises.documentos),
      estatistica("Países", paises.paises),
      estatistica("Cooperações", paises.cooperacoes),
      estatistica("Internacional", paises.internacionais),
    );
    carregarMapa(resultado.token);
  } else {
    $("figMapa").hidden = true;
    $("canvasMapa").hidden = true;
    $("zoomMapa").hidden = true;
    $("svgMapa").hidden = true;
    $("notaMapa").hidden = true;
    $("vazioMapa").hidden = false;
    $("metaMapa").textContent =
      estado.resultado?.parametros.unidade === "Countries"
        ? "disponível na matriz de coocorrência"
        : "disponível na unidade Países";
    $("estatMapa").replaceChildren();
    mapaUI.dados = null;
  }

  if (halo) {
    $("figHalo").src = halo;
    $("figHalo").hidden = false;
    $("vazioHalo").hidden = true;
    $("zoomHalo").hidden = false;
  } else {
    $("figHalo").hidden = true;
    $("zoomHalo").hidden = true;
    $("vazioHalo").hidden = false;
    $("vazioHalo").textContent = "Sem agrupamentos nesta configuração";
  }

  if (estrategico) {
    $("figEstrategico").src = estrategico;
    $("figEstrategico").hidden = true;
    $("canvasEstrategico").hidden = false;
    $("vazioEstrategico").hidden = true;
    $("zoomEstrategico").hidden = false;
    $("svgEstrategico").hidden = false;
    $("notaDiagrama").hidden = false;
    carregarDiagrama(resultado.token);
  } else {
    $("figEstrategico").hidden = true;
    $("canvasEstrategico").hidden = true;
    $("zoomEstrategico").hidden = true;
    $("svgEstrategico").hidden = true;
    $("notaDiagrama").hidden = true;
    $("legendaDiagrama").hidden = true;
    $("vazioEstrategico").hidden = false;
    $("vazioEstrategico").textContent = "Sem agrupamentos nesta configuração";
    diagramaUI.dados = null;
  }

  const agrupamentos = resultado.figuras.agrupamentos;
  if (agrupamentos) {
    $("figAgrupamentos").src = agrupamentos;
    $("figAgrupamentos").hidden = false;
    $("vazioAgrupamentos").hidden = true;
    $("svgAgrupamentos").hidden = false;
    $("metaAgrupamentos").textContent =
      `${resultado.periodo.nome} · ${resumo.grupos} temas`;
  } else {
    $("figAgrupamentos").hidden = true;
    $("svgAgrupamentos").hidden = true;
    $("vazioAgrupamentos").hidden = false;
    $("metaAgrupamentos").textContent =
      "temas ligados pela associação entre seus itens";
  }

  prepararZoomEstrategico();
  if (zoomHalo) zoomHalo.reset();
  limparRedeInterativa();
  redeUI.carregada = false;
  if (abaAtual() === "rede") carregarRedeInterativa(resultado);
  if (halo) $("zoomHalo").hidden = false;

  $("estatHalo").replaceChildren(
    estatistica("Nós", resumo.nos),
    estatistica("Arestas", resumo.arestas),
    estatistica("Densidade média", nf.format(resumo.densidade_media)),
    estatistica("Maior halo", resumo.maior_grupo),
  );
  $("estatEstrategico").replaceChildren(
    estatistica("Motores", resultado.quadrantes.motor, "#2F2BFF"),
    estatistica("Nicho", resultado.quadrantes.nicho, "#067647"),
    estatistica("Básicos", resultado.quadrantes.basico, "#0B1F66"),
    estatistica("Emergentes", resultado.quadrantes.emergente, "#A16207"),
  );

  renderizarTabela(resultado);
  renderizarIndices(resultado);
  $("exportarTipo").disabled = false;
  $("btnRelatorio").disabled = false;
  estado.docsToken = null;
  if (abaAtual() === "documentos") carregarDocumentos();
  $("mapasLongitudinais").hidden = true;
  $("vazioLongitudinal").hidden = false;
  $("vazioLongitudinal").textContent =
    "Abra a aba Comparar períodos para montar os mapas.";
  $("downloadEvolucao").hidden = true;
  $("linkGrupos").textContent = `${resumo.grupos} grupos`;
}


/* ------------------------------------------------------------------- resumo */

// "STATISTICAL-REASONING" vira "Statistical reasoning"; nomes de pessoas e
// países ficam com cada palavra capitalizada.
function nomeLegivel(texto, unidade) {
  const base = String(texto || "").replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim().toLowerCase();
  if (!base) return "—";
  if (["Authors", "AuthorsReference", "Countries"].includes(unidade)) {
    return base.replace(/(^|\s)(\p{L})/gu, (_, espaco, letra) => espaco + letra.toUpperCase());
  }
  return base.charAt(0).toUpperCase() + base.slice(1);
}

function itemLegivel(texto, unidade) {
  const base = nomeLegivel(texto, unidade);
  return ["Authors", "AuthorsReference", "Countries"].includes(unidade)
    ? base : base.charAt(0).toLowerCase() + base.slice(1);
}

function listaComE(itens) {
  try {
    return new Intl.ListFormat("pt-BR", { style: "long", type: "conjunction" }).format(itens);
  } catch (_) {
    return itens.length > 1
      ? `${itens.slice(0, -1).join(", ")} e ${itens[itens.length - 1]}` : itens.join("");
  }
}

function mostrarCarregandoResumo() {
  const p = document.createElement("p");
  p.className = "resumo-carregando";
  p.textContent = "Calculando o resumo…";
  $("resumoCorpo").replaceChildren(p);
  $("metaResumo").textContent = "—";
}

function renderizarResumoVazio(texto) {
  const p = document.createElement("p");
  p.className = "resumo-vazio";
  p.textContent = texto;
  $("resumoCorpo").replaceChildren(p);
  $("metaResumo").textContent = "—";
}

function elemento(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

function linhaTema(grupo, unidade, maximo, comQuadrante) {
  const linha = elemento("button", `tema-linha ${grupo.quadrante}`);
  linha.type = "button";
  linha.addEventListener("click", () => abrirGrupo(grupo.selo));
  const nome = nomeLegivel(grupo.rotulo, unidade);
  const docs = grupo.documentos || 0;
  const selo = elemento("span", `selo ${grupo.quadrante}`, String(grupo.selo));
  const titulo = elemento("span", "tema-nome", nome);
  titulo.title = nome;
  const contagem = elemento("span", "tema-docs", plural(docs, "doc", "docs"));
  const barra = elemento("span", "tema-barra");
  const preenchimento = document.createElement("i");
  preenchimento.style.width = `${Math.max(3, Math.round((docs / maximo) * 100))}%`;
  barra.append(preenchimento);
  let itens = (grupo.nos || []).slice(0, 4).map((no) => itemLegivel(no, unidade)).join(" · ");
  if (comQuadrante) {
    itens = `${rotuloQuadrante(grupo.quadrante, unidade)} · ${itens}`;
  }
  const lista = elemento("span", "tema-itens", itens);
  lista.title = (grupo.nos || []).map((no) => itemLegivel(no, unidade)).join(", ");
  linha.append(selo, titulo, contagem, barra, lista);
  return linha;
}

function renderizarResumo(resultado) {
  const corpo = $("resumoCorpo");
  const unidade = resultado.parametros.unidade;
  const grupos = resultado.grupos || [];
  const totalDocs = resultado.resumo.documentos;
  const [sing, plur] = substantivoGrupo(resultado);
  $("metaResumo").textContent =
    `${resultado.periodo.nome} · frequência mínima ${resultado.parametros.minimo_frequencia}`;

  if (!grupos.length) {
    renderizarResumoVazio("Nenhum agrupamento nesta configuração. Reduza a frequência mínima.");
    return;
  }

  const porDocs = [...grupos].sort((a, b) =>
    (b.documentos - a.documentos) || (b.itens - a.itens) || (a.selo - b.selo));
  const maximo = Math.max(1, porDocs[0].documentos || 1);

  // Temas visíveis: com pelo menos 3 documentos, no máximo 12. Se sobrarem
  // menos de 4, baixa a régua para 2 documentos e, em último caso, mostra os
  // 6 maiores: um resumo vazio não ajuda, mas 12 temas de 1 documento também não.
  let visiveis = porDocs.filter((g) => g.documentos >= DOCS_MINIMOS_RESUMO);
  if (visiveis.length < MINIMO_TEMAS) visiveis = porDocs.filter((g) => g.documentos >= 2);
  if (visiveis.length < MINIMO_TEMAS) visiveis = porDocs.slice(0, 6);
  visiveis = visiveis.slice(0, MAXIMO_TEMAS_RESUMO);
  const conjuntoVisiveis = new Set(visiveis.map((g) => g.selo));
  const pequenos = porDocs.filter((g) => !conjuntoVisiveis.has(g.selo));

  // Frase de leitura
  const motores = porDocs.filter((g) => g.quadrante === "motor");
  const nomesMotores = motores.slice(0, 3).map((g) => nomeLegivel(g.rotulo, unidade));
  const rotuloMotor = unidade === "Words"
    ? (motores.length === 1 ? "Tema motor" : "Temas motores")
    : (unidade === "Countries" ? "Núcleo"
      : (motores.length === 1 ? "Grupo motor" : "Grupos motores"));
  const verbo = totalDocs === 1 ? "forma" : "formam";
  const frase = `${plural(totalDocs, "documento", "documentos")} ${verbo} ` +
    `${plural(grupos.length, sing, plur)}.`;
  const listaMotores = listaComE(nomesMotores);
  const fraseMotor = nomesMotores.length
    ? `${rotuloMotor}: ${listaMotores}${listaMotores.endsWith(".") ? "" : "."}`
    : (unidade === "Words" ? "Nenhum tema motor nesta configuração." : "Nenhum grupo motor nesta configuração.");

  const leitura = elemento("div", "resumo-leitura");
  leitura.append(elemento("div", "rotulo-secao", "Leitura rápida"),
    elemento("p", "", frase), elemento("p", "", fraseMotor));

  const blocos = [leitura];

  // Etiqueta genérica: um tema que cobre quase todo o corpus.
  const generico = unidade === "Words" && totalDocs
    ? porDocs.find((g) => g.documentos / totalDocs >= FRACAO_TEMA_GENERICO) : null;
  if (generico) {
    const pct = Math.round((generico.documentos / totalDocs) * 100);
    const aviso = elemento("div", "resumo-aviso");
    const texto = elemento("span", "",
      `"${nomeLegivel(generico.rotulo, unidade)}" cobre ${pct}% dos documentos ` +
      `(${generico.documentos} de ${totalDocs}). Etiquetas genéricas, como o nome do ` +
      "periódico ou da área, escondem os demais temas: ignore-a para ver os demais temas.");
    const botao = elemento("button", "botao-mini", "Ignorar e reanalisar");
    botao.type = "button";
    botao.addEventListener("click", () => {
      estado.ignorar = [...new Set([...(estado.ignorar || []), generico.rotulo])];
      previsualizar();
    });
    aviso.append(texto, botao);
    blocos.push(aviso);
  }

  // Temas por quadrante
  const interpretacao = unidade === "Countries" ? INTERPRETACAO_PAISES : INTERPRETACAO;
  const grade = elemento("div", "resumo-quadrantes");
  for (const chave of ORDEM_QUADRANTES) {
    const doQuadrante = visiveis.filter((g) => g.quadrante === chave);
    const totalQuadrante = grupos.filter((g) => g.quadrante === chave).length;
    const bloco = elemento("section", `quadrante-bloco ${chave}`);
    const cab = elemento("div", "quadrante-cab");
    cab.append(elemento("h3", "", rotuloQuadrante(chave, unidade)),
      elemento("span", "qtd", plural(totalQuadrante, sing, plur)));
    bloco.append(cab, elemento("p", "", interpretacao[chave]));
    if (doQuadrante.length) {
      for (const grupo of doQuadrante) bloco.append(linhaTema(grupo, unidade, maximo, false));
    } else {
      bloco.append(elemento("div", "nenhum",
        totalQuadrante ? `Só ${plur} de poucos documentos, em “Outros”.` : "Nenhum nesta análise."));
    }
    grade.append(bloco);
  }
  blocos.push(grade);

  if (pequenos.length) {
    const detalhes = elemento("details", "resumo-outros");
    const fem = sing.startsWith("frente");
    const nomePequenos = pequenos.length === 1
      ? `${fem ? "Outra" : "Outro"} ${sing} ${fem ? "pequena" : "pequeno"}`
      : `${fem ? "Outras" : "Outros"} ${pequenos.length} ${plur} ${fem ? "pequenas" : "pequenos"}`;
    detalhes.append(elemento("summary", "", nomePequenos));
    const lista = elemento("div", "lista");
    for (const grupo of pequenos) lista.append(linhaTema(grupo, unidade, maximo, true));
    detalhes.append(lista);
    blocos.push(detalhes);
  }

  corpo.replaceChildren(...blocos);
}

function renderizarTabela(resultado) {
  const grupos = resultado.grupos;
  const corpo = $("gruposCorpo");
  corpo.replaceChildren();

  if (!grupos.length) {
    const linha = document.createElement("tr");
    const celula = document.createElement("td");
    celula.colSpan = 7;
    celula.style.color = "#8A94A6";
    celula.textContent = "Nenhum agrupamento nesta configuração.";
    linha.append(celula);
    corpo.append(linha);
    $("rodapeTabela").textContent =
      "Aumente a rede ou reduza a frequência mínima para ver grupos.";
    return;
  }

  const maiorCentralidade = Math.max(...grupos.map((g) => g.centralidade), 0.001);
  const maiorDensidade = Math.max(...grupos.map((g) => g.densidade), 0.001);

  for (const grupo of grupos) {
    const linha = document.createElement("tr");
    linha.className = "linha-grupo";
    linha.tabIndex = 0;
    const abrir = () => abrirGrupo(grupo.selo);
    linha.addEventListener("click", abrir);
    linha.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        abrir();
      }
    });

    const celulaSelo = document.createElement("td");
    const selo = document.createElement("span");
    selo.className = `selo ${grupo.quadrante}`;
    selo.textContent = String(grupo.selo);
    celulaSelo.append(selo);

    const celulaNome = document.createElement("td");
    celulaNome.className = "grupo";
    celulaNome.textContent = grupo.rotulo;
    celulaNome.title = grupo.nos.join(", ");

    const celulaItens = document.createElement("td");
    celulaItens.className = "num";
    celulaItens.textContent = String(grupo.itens);

    const celulaCentralidade = document.createElement("td");
    celulaCentralidade.className = "num";
    celulaCentralidade.append(medida(grupo.centralidade,
      grupo.centralidade / maiorCentralidade));

    const celulaDensidade = document.createElement("td");
    celulaDensidade.className = "num";
    celulaDensidade.append(medida(grupo.densidade,
      grupo.densidade / maiorDensidade));

    const celulaQuadrante = document.createElement("td");
    const etiqueta = document.createElement("span");
    etiqueta.className = `quadrante ${grupo.quadrante}`;
    etiqueta.textContent =
      rotuloQuadrante(grupo.quadrante, resultado.parametros.unidade);
    celulaQuadrante.append(etiqueta);

    const celulaSeta = document.createElement("td");
    celulaSeta.className = "seta-grupo";
    celulaSeta.textContent = "›";

    linha.append(celulaSelo, celulaNome, celulaItens, celulaCentralidade,
      celulaDensidade, celulaQuadrante, celulaSeta);
    corpo.append(linha);
  }

  $("rodapeTabela").textContent =
    `${grupos.length} agrupamentos · ${resultado.resumo.documentos} documentos ` +
    `no período · quadrante pela faixa normalizada de Callon`;
}

function medida(valor, fracao) {
  const caixa = document.createElement("span");
  caixa.className = "valor-medida";
  const barra = document.createElement("span");
  barra.className = "barra";
  const preenchimento = document.createElement("i");
  preenchimento.style.width = `${Math.max(1, Math.round(fracao * 100))}%`;
  barra.append(preenchimento);
  caixa.append(barra, document.createTextNode(nf.format(valor)));
  return caixa;
}

/* ------------------------------------------------------------------ detalhe */

async function abrirGrupo(selo) {
  if (!estado.token) {
    mostrarToast("Execute a prévia novamente para abrir o agrupamento.", true);
    return;
  }

  const pedido = ++estado.pedidoGrupo;
  $("drawer").hidden = false;
  $("drawerSelo").className = "selo";
  $("drawerSelo").textContent = String(selo);
  $("drawerTitulo").textContent = "Carregando agrupamento…";
  $("drawerQuadrante").replaceChildren();
  $("drawerMetricas").replaceChildren();
  $("drawerItensQtd").textContent = "";
  $("drawerDocsQtd").textContent = "";
  $("drawerItens").replaceChildren(textoVazio("lendo os itens…"));
  $("drawerDocumentos").replaceChildren();
  $("drawerCorpo").scrollTop = 0;

  try {
    const dados = await api(`/api/grupo?token=${encodeURIComponent(estado.token)}` +
      `&selo=${encodeURIComponent(selo)}`);
    if (pedido !== estado.pedidoGrupo) return;
    renderizarDrawer(dados);
  } catch (erro) {
    if (pedido !== estado.pedidoGrupo) return;
    fecharDrawer();
    mostrarToast(erro.message, true);
  }
}

function renderizarDrawer(dados) {
  const grupo = dados.grupo;
  const selo = $("drawerSelo");
  selo.className = `selo ${grupo.quadrante}`;
  selo.textContent = String(grupo.selo);

  $("drawerTitulo").textContent = grupo.rotulo;
  $("drawerQuadrante").replaceChildren(
    etiquetaQuadrante(grupo.quadrante,
                      estado.resultado?.parametros.unidade));

  $("drawerMetricas").replaceChildren(
    metrica("Itens", grupo.itens),
    metrica("Centralidade", nf.format(grupo.centralidade)),
    metrica("Densidade", nf.format(grupo.densidade)),
    metrica("Documentos", dados.documentos.length),
  );

  const itens = $("drawerItens");
  itens.replaceChildren();
  $("drawerItensQtd").textContent = `(${dados.itens.length})`;
  if (!dados.itens.length) {
    itens.append(textoVazio("Nenhum item neste agrupamento."));
  } else {
    for (const item of dados.itens) {
      const linha = document.createElement("div");
      linha.className = "item-linha";
      const nome = document.createElement("span");
      nome.className = "nome";
      nome.textContent = item.rotulo;

      const numeros = document.createElement("span");
      numeros.className = "numeros";
      numeros.append(
        document.createTextNode("freq "), forte(item.frequencia),
        document.createTextNode("  ·  grau "), forte(nf.format(item.grau)),
        document.createTextNode("  ·  "), forte(item.documentos), texto(item.documentos === 1 ? " doc" : " docs"),
      );

      linha.append(nome, numeros);
      itens.append(linha);
    }
  }

  const documentos = $("drawerDocumentos");
  documentos.replaceChildren();
  $("drawerDocsQtd").textContent = `(${dados.documentos.length})`;
  if (!dados.documentos.length) {
    documentos.append(textoVazio("Nenhum documento associado."));
  } else {
    for (const documento of dados.documentos) {
      const cartao = document.createElement("div");
      cartao.className = "doc-card";

      const titulo = document.createElement("div");
      titulo.className = "titulo";
      titulo.textContent = documento.titulo || "(sem título)";

      const autores = document.createElement("div");
      autores.className = "autores";
      autores.textContent = documento.autores || "Autoria não informada";

      const fonte = document.createElement("div");
      fonte.className = "fonte";
      if (documento.ano) fonte.append(texto(documento.ano));
      if (documento.fonte) fonte.append(texto(documento.fonte));
      const citacoes = document.createElement("span");
      citacoes.className = "citacoes";
      citacoes.textContent = `${documento.citacoes} citações`;
      fonte.append(citacoes);

      cartao.append(titulo, autores, fonte);
      documentos.append(cartao);
    }
  }
}

function metrica(rotulo, valor) {
  const caixa = document.createElement("div");
  const nome = document.createElement("div");
  nome.className = "rotulo-metrica";
  nome.textContent = rotulo;
  const conteudo = document.createElement("div");
  conteudo.className = "valor-metrica";
  conteudo.textContent = String(valor);
  caixa.append(nome, conteudo);
  return caixa;
}

function etiquetaQuadrante(chave, unidade) {
  const etiqueta = document.createElement("span");
  etiqueta.className = `quadrante ${chave}`;
  etiqueta.textContent = rotuloQuadrante(chave, unidade);
  return etiqueta;
}

function textoVazio(conteudo) {
  const elemento = document.createElement("div");
  elemento.className = "drawer-vazio";
  elemento.textContent = conteudo;
  return elemento;
}

function fecharDrawer() {
  estado.pedidoGrupo += 1;
  $("drawer").hidden = true;
}

function estatistica(rotulo, valor, cor, titulo) {
  const item = document.createElement("span");
  if (titulo) item.title = titulo;
  if (cor) {
    const marca = document.createElement("i");
    marca.className = "marca-quadrante";
    marca.style.background = cor;
    item.append(marca);
  }
  item.append(document.createTextNode(`${rotulo} `));
  item.append(forte(valor));
  return item;
}

function forte(valor) {
  const elemento = document.createElement("b");
  elemento.textContent = String(valor);
  return elemento;
}

function texto(conteudo, cor) {
  const elemento = document.createElement("span");
  elemento.textContent = conteudo;
  if (cor) elemento.style.color = cor;
  return elemento;
}

/* -------------------------------------------------------------------- grade */

async function rodarGrade() {
  if (!estado.projeto || trabalhoEmAndamento()) return;
  const dados = parametros();
  delete dados.periodo;

  travaParametros(true);
  $("btnGrade").disabled = true;
  $("btnPreview").disabled = true;
  $("progresso").hidden = false;
  $("btnCancelar").hidden = false;
  $("btnCancelar").disabled = true;
  $("btnCancelar").textContent = "Cancelar";
  $("progressoBarra").style.width = "0%";
  $("progressoTexto").textContent = "iniciando…";
  $("estadoTexto").textContent = "Executando grade";

  try {
    const trabalho = await api("/api/grade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    estado.trabalho = trabalho;
    $("btnCancelar").disabled = false;
    atualizarProgresso(trabalho);
    agendarConsulta(trabalho.id);
  } catch (erro) {
    finalizarGrade();
    mostrarToast(erro.message, true);
  }
}

function agendarConsulta(id) {
  setTimeout(async () => {
    try {
      const trabalho = await api(`/api/trabalho/${id}`);
      estado.trabalho = trabalho;
      atualizarProgresso(trabalho);

      if (trabalho.estado === "executando") {
        agendarConsulta(id);
        return;
      }
      concluirTrabalho(trabalho);
    } catch (erro) {
      finalizarGrade();
      mostrarToast(erro.message, true);
    }
  }, 700);
}

function atualizarProgresso(trabalho) {
  const total = trabalho.total || 1;
  const fracao = Math.min(1, trabalho.feito / total);
  $("progressoBarra").style.width = `${Math.round(fracao * 100)}%`;
  $("progressoTexto").textContent =
    `${trabalho.feito} de ${trabalho.total} · ${Math.round(fracao * 100)}%`;
  $("progresso").title = trabalho.mensagem || "";
}

function concluirTrabalho(trabalho) {
  finalizarGrade();

  if (trabalho.estado === "concluido") {
    estado.download = trabalho.resultado.download;
    $("btnExportar").disabled = false;
    $("progressoTexto").textContent =
      `${trabalho.resultado.analises} análises · ${trabalho.resultado.periodos} ` +
      `${trabalho.resultado.periodos === 1 ? "período" : "períodos"}`;
    mostrarToast(`Grade concluída: ${trabalho.resultado.analises} análises. ` +
      "Use \"Baixar grade\" para o TSV.");
  } else if (trabalho.estado === "cancelado") {
    $("progressoTexto").textContent = "Execução cancelada";
    mostrarToast("Execução cancelada.");
  } else {
    $("progressoTexto").textContent = "Falha na execução";
    mostrarToast(trabalho.erro || "Falha na execução da grade.", true);
  }
}

function finalizarGrade() {
  $("btnGrade").disabled = !estado.projeto;
  $("btnPreview").disabled = !estado.projeto;
  $("btnCancelar").hidden = true;
  $("estadoTexto").textContent = estado.projeto ? "Base importada" : "Sem projeto";
  estado.trabalho = null;
  travaParametros(false);
}

function travaParametros(travado) {
  for (const id of ["unidade", "matriz", "similaridade", "algoritmo", "rede",
                    "periodo", "freqMenos", "freqMais"]) {
    $(id).disabled = travado;
  }
  if (!travado) {
    $("freqMenos").disabled = estado.freq <= 1;
    $("periodo").disabled = !estado.projeto;
  }
}

async function cancelarTrabalho() {
  if (!estado.trabalho || estado.trabalho.estado !== "executando") return;
  $("btnCancelar").disabled = true;
  $("btnCancelar").textContent = "Cancelando…";
  try {
    await api(`/api/trabalho/${estado.trabalho.id}/cancelar`, { method: "POST" });
  } catch (erro) {
    mostrarToast(erro.message, true);
  }
}

function trabalhoEmAndamento() {
  return Boolean(estado.trabalho && estado.trabalho.estado === "executando");
}

/* ------------------------------------------------------------------- importar */

function escolheArquivo() {
  const arquivo = $("arquivo").files[0];
  if (!arquivo) return;

  const textoArquivo = $("textoArquivo");
  textoArquivo.replaceChildren();
  const nome = document.createElement("b");
  nome.textContent = arquivo.name;
  textoArquivo.append(nome, document.createElement("br"),
    document.createTextNode(`${(arquivo.size / 1024 / 1024).toFixed(1)} MB`));

  if (!$("nomeProjeto").value.trim()) {
    $("nomeProjeto").value = nomeSemExtensao(arquivo.name);
  }
}

async function importar(evento) {
  evento.preventDefault();
  if (trabalhoEmAndamento()) {
    mostrarToast("Aguarde a execução atual terminar.", true);
    return;
  }

  const arquivo = $("arquivo").files[0];
  if (!arquivo) {
    mostrarToast("Escolha o arquivo do corpus.", true);
    return;
  }

  const formato = $("formato").value;
  const parametros = new URLSearchParams({
    formato,
    periodos: $("periodos").value,
    nome: $("nomeProjeto").value,
  });

  const botao = $("btnImportar");
  botao.disabled = true;
  $("importando").hidden = false;

  try {
    const resposta = await fetch(`/api/importar?${parametros}`, {
      method: "POST",
      headers: { "X-Nome-Arquivo": encodeURIComponent(arquivo.name) },
      body: arquivo,
    });
    const dados = await resposta.json();
    if (!resposta.ok) throw new Error(dados.erro || `falha ${resposta.status}`);

    aplicarProjeto(dados.projeto);
    fecharModal();
    const nomes = {
      csv: "CSV SciMAT", bibtex: "BibTeX", ris: "RIS",
      openalex: "OpenAlex", wos: "Web of Science", scopus: "Scopus",
    };
    mostrarToast(
      `Base criada: ${dados.resumo.documentos} documentos ` +
      `(${nomes[dados.formato] || dados.formato}).`);
    await previsualizar();
    mostrarVisaoGeral();
  } catch (erro) {
    mostrarToast(erro.message, true);
  } finally {
    botao.disabled = false;
    $("importando").hidden = true;
  }
}

function nomeSemExtensao(nome) {
  return nome.replace(/\.[^.]+$/, "");
}

/* --------------------------------------------------------------------- apoio */

function mudaFrequencia(passo) {
  estado.freq = Math.max(1, Math.min(50, estado.freq + passo));
  estado.autoFreq = false;
  atualizarFrequenciaTela();
  mostrarNotaAuto("");
  if (estado.avancado) {
    marcarDesatualizada();
  } else {
    agendarPrevia(500);
  }
}

async function abrirModal() {
  $("modal").hidden = false;
  try {
    const dados = await api("/api/projetos");
    $("workspace").textContent = `Projetos em ${dados.workspace}`;
    renderizarRecentes(dados.projetos);
  } catch (erro) {
    mostrarToast(erro.message, true);
  }
  $("caminhoProjeto").focus();
}

function fecharModal() {
  $("modal").hidden = true;
}

/* Atalhos da barra lateral: cada item leva a uma parte da mesma página. */
function navegar(destino) {
  const rolar = (alvo) => alvo && alvo.scrollIntoView({ behavior: "smooth", block: "start" });
  if (destino === "analise") {
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else if (destino === "projeto") {
    abrirModal();
  } else if (destino === "corpus") {
    abrirModal();
    setTimeout(() => {
      const secao = $("secaoImportar");
      if (secao) secao.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 60);
  } else if (destino === "periodos") {
    if (!estado.projeto) {
      mostrarToast("Abra um projeto para editar os períodos.", true);
      return;
    }
    abrirBase();
  } else if (destino === "config") {
    rolar(document.querySelector(".parametros"));
  } else if (destino === "ajuda") {
    abrirAjuda();
  } else if (destino === "sobre") {
    abrirSobre();
  }
}

function aplicaMenuRecolhido(recolhido) {
  const app = document.querySelector(".app");
  if (!app) return;
  app.classList.toggle("recolhida", recolhido);
  const botao = $("btnRecolher");
  if (botao) {
    botao.setAttribute("aria-expanded", recolhido ? "false" : "true");
    botao.setAttribute("aria-label", recolhido ? "Expandir menu" : "Recolher menu");
    botao.title = recolhido ? "Expandir menu" : "Recolher menu";
  }
  localStorage.setItem("redes.menu.recolhido", recolhido ? "1" : "0");
}

function abrirAjuda() {
  $("modalAjuda").hidden = false;
}

function fecharAjuda() {
  const caixa = $("modalAjuda");
  if (caixa) caixa.hidden = true;
}

function abrirSobre() {
  const caixa = $("modalSobre");
  if (caixa) caixa.hidden = false;
}

function fecharSobre() {
  const caixa = $("modalSobre");
  if (caixa) caixa.hidden = true;
}

function abrirLightbox(id) {
  const imagem = $(id);
  if (!imagem.src) return;
  $("imagemLightbox").src = imagem.src;
  const baixar = $("baixarLightbox");
  baixar.href = imagem.src + (imagem.src.includes("?") ? "&" : "?") + "download=1";
  baixar.hidden = !new URL(imagem.src).pathname.startsWith("/figura/");
  $("lightbox").hidden = false;
  if (zoomLuz) zoomLuz.reset();
}

function fecharLightbox() {
  $("lightbox").hidden = true;
  $("imagemLightbox").removeAttribute("src");
}

function mostrarToast(mensagem, erro = false) {
  const caixa = $("toast");
  caixa.textContent = mensagem;
  caixa.classList.toggle("erro", erro);
  caixa.hidden = false;
  clearTimeout(estado.temporizadorToast);
  estado.temporizadorToast = setTimeout(() => { caixa.hidden = true; }, 6000);
}

function hora() {
  return new Date().toLocaleTimeString("pt-BR",
    { hour: "2-digit", minute: "2-digit" });
}

function nomeArquivo(caminho) {
  return caminho.split("/").pop();
}

async function api(url, opcoes = {}) {
  const resposta = await fetch(url, opcoes);
  const tipo = resposta.headers.get("content-type") || "";
  const dados = tipo.includes("application/json")
    ? await resposta.json() : await resposta.text();
  if (!resposta.ok) {
    throw new Error((dados && dados.erro) || `falha ${resposta.status}`);
  }
  return dados;
}

/* ------------------------------------------------------- zoom das figuras */

let zoomEstrategico = null;
let zoomHalo = null;
let zoomLuz = null;

function criarZoomImagem(caixa, img, opcoes = {}) {
  const z = { escala: 1, x: 0, y: 0, arrastando: false, moveu: false,
              px: 0, py: 0, ix: 0, iy: 0 };

  const aplicar = () => {
    if (z.escala <= 1.001) {
      z.escala = 1;
      z.x = 0;
      z.y = 0;
      img.style.transform = "";
      caixa.classList.remove("zoom-ativo");
      return;
    }
    img.style.transform =
      `translate(${z.x.toFixed(2)}px, ${z.y.toFixed(2)}px) scale(${z.escala.toFixed(4)})`;
    caixa.classList.add("zoom-ativo");
  };

  const margem = opcoes.margem || 16;

  const limites = () => {
    const w = Math.max(1, caixa.clientWidth - margem);
    const h = Math.max(1, caixa.clientHeight - margem);
    const mx = Math.max(0, (img.offsetWidth * z.escala - w) / 2);
    const my = Math.max(0, (img.offsetHeight * z.escala - h) / 2);
    z.x = Math.min(mx, Math.max(-mx, z.x));
    z.y = Math.min(my, Math.max(-my, z.y));
  };

  const zoom = (fator, cx, cy) => {
    const antes = z.escala;
    const depois = Math.min(opcoes.maximo || 8, Math.max(1, antes * fator));
    if (Math.abs(depois - antes) < 1e-4) return;
    const largura = caixa.clientWidth;
    const altura = caixa.clientHeight;
    const ox = (cx === undefined ? largura / 2 : cx) - largura / 2;
    const oy = (cy === undefined ? altura / 2 : cy) - altura / 2;
    z.x = ox - (ox - z.x) * (depois / antes);
    z.y = oy - (oy - z.y) * (depois / antes);
    z.escala = depois;
    limites();
    aplicar();
  };

  const reset = () => {
    z.arrastando = false;
    z.escala = 1;
    z.x = 0;
    z.y = 0;
    aplicar();
  };

  caixa.addEventListener("wheel", (evento) => {
    if (evento.target !== img) return;
    if (!(opcoes.sempreZoom || evento.ctrlKey || evento.metaKey || z.escala > 1)) return;
    evento.preventDefault();
    const r = caixa.getBoundingClientRect();
    zoom(Math.exp(-evento.deltaY * 0.0018),
         evento.clientX - r.left, evento.clientY - r.top);
  }, { passive: false });

  img.addEventListener("pointerdown", (evento) => {
    if (z.escala <= 1 || evento.button !== 0) return;
    evento.preventDefault();
    z.arrastando = true;
    z.moveu = false;
    z.px = evento.clientX;
    z.py = evento.clientY;
    z.ix = z.x;
    z.iy = z.y;
    try { img.setPointerCapture(evento.pointerId); } catch (_) { /* opcional */ }
  });

  img.addEventListener("pointermove", (evento) => {
    if (!z.arrastando) return;
    const dx = evento.clientX - z.px;
    const dy = evento.clientY - z.py;
    if (Math.abs(dx) + Math.abs(dy) > 2) z.moveu = true;
    z.x = z.ix + dx;
    z.y = z.iy + dy;
    limites();
    aplicar();
  });

  const terminar = () => {
    if (!z.arrastando) return;
    z.arrastando = false;
    if (z.moveu) {
      caixa.dataset.arrastou = "1";
      setTimeout(() => { delete caixa.dataset.arrastou; }, 0);
    }
  };
  img.addEventListener("pointerup", terminar);
  img.addEventListener("pointercancel", terminar);
  img.addEventListener("dblclick", (evento) => {
    evento.preventDefault();
    const r = caixa.getBoundingClientRect();
    zoom(z.escala > 1 ? 1 / z.escala : 2,
         evento.clientX - r.left, evento.clientY - r.top);
  });

  const reajustar = () => {
    if (z.escala <= 1) return;
    limites();
    aplicar();
  };

  return {
    reset,
    reajustar,
    acao(nome) {
      if (nome === "mais") zoom(1.3);
      else if (nome === "menos") zoom(1 / 1.3);
      else reset();
    },
  };
}

function prepararZoomEstrategico() {
  if (zoomEstrategico) {
    zoomEstrategico.reset();
    zoomHalo.reset();
    zoomLuz.reset();
    return;
  }
  zoomEstrategico = criarZoomImagem($("caixaEstrategico"), $("figEstrategico"));
  zoomHalo = criarZoomImagem($("caixaHalo"), $("figHalo"));
  zoomLuz = criarZoomImagem($("lightbox"), $("imagemLightbox"),
                             { sempreZoom: true, maximo: 12, margem: 64 });

  let agendado = 0;
  window.addEventListener("resize", () => {
    if (agendado) return;
    agendado = requestAnimationFrame(() => {
      agendado = 0;
      zoomEstrategico.reajustar();
      zoomHalo.reajustar();
      zoomLuz.reajustar();
    });
  });
}

/* ------------------------------------------------------- rede interativa */

const redeUI = {
  dados: null,
  ctx: null,
  largura: 0,
  altura: 0,
  escala: 1,
  tx: 0,
  ty: 0,
  ajuste: 1,
  rotulos: "nenhum",
  foco: 0,
  visiveis: null,
  arrastando: false,
  moveu: false,
  inicio: null,
  dica: null,
  raf: 0,
  pedido: 0,
  eventos: false,
  zoomManual: false,
  selos: [],
  porGrupo: null,
  posicao: new Map(),
  avisouTodos: false,
  carregada: false,
};

function limparRedeInterativa() {
  redeUI.pedido += 1;
  redeUI.dados = null;
  redeUI.dica = null;
  redeUI.visiveis = null;
  redeUI.selos = [];
  redeUI.porGrupo = null;
  redeUI.avisouTodos = false;
  if (redeUI.raf) cancelAnimationFrame(redeUI.raf);
  redeUI.raf = 0;
  $("canvasHalo").hidden = true;
  $("acoesRede").hidden = true;
  $("zoomHalo").hidden = true;
  $("legendaRede").hidden = true;
  $("avisoVolume").hidden = true;
  $("dicaNo").hidden = true;
  $("rotulosRede").value = "nenhum";
  $("focoRede").value = "0";
  redeUI.rotulos = "nenhum";
  redeUI.foco = 0;
}

async function carregarRedeInterativa(resultado) {
  limparRedeInterativa();
  redeUI.carregada = true;
  if (!estado.token || !resultado.resumo.grupos) return;
  const pedido = ++redeUI.pedido;
  $("carregandoHalo").hidden = false;
  try {
    const dados = await api(`/api/rede?token=${encodeURIComponent(estado.token)}`);
    if (pedido !== redeUI.pedido) return;
    prepararRede(dados);
  } catch (_) {
    // A figura SVG continua disponível como alternativa.
  } finally {
    if (pedido === redeUI.pedido) $("carregandoHalo").hidden = true;
  }
}

function prepararRede(dados) {
  redeUI.dados = dados;
  redeUI.visiveis = null;
  redeUI.dica = null;
  redeUI.posicao = new Map(dados.nos.map((no) => [no.id, no]));

  const grupos = dados.grupos;
  redeUI.porGrupo = grupos.map(() => ({ arestas: [], nos: [] }));
  for (const ligacao of dados.internas) redeUI.porGrupo[ligacao.g].arestas.push(ligacao);
  for (const no of dados.nos) {
    if (no.grupo >= 0 && redeUI.porGrupo[no.grupo]) redeUI.porGrupo[no.grupo].nos.push(no);
  }

  const legenda = $("legendaRede");
  legenda.replaceChildren();
  for (const grupo of grupos) {
    const item = document.createElement("div");
    item.className = "item-legenda";
    item.title = `Abrir ${grupo.rotulo}`;
    const ponto = document.createElement("span");
    ponto.className = "ponto";
    ponto.style.color = grupo.cor;
    const nome = document.createElement("span");
    nome.className = "nome";
    nome.textContent = `${grupo.indice}. ${grupo.rotulo_curto}`;
    const qtd = document.createElement("span");
    qtd.className = "qtd";
    qtd.textContent = String(grupo.nos);
    item.append(ponto, nome, qtd);
    item.addEventListener("click", () => abrirGrupo(grupo.indice));
    legenda.append(item);
  }

  const aviso = $("avisoVolume");
  const meta = dados.meta;
  if (meta.grupos > 30 || meta.nos > 600) {
    aviso.textContent = `Volume alto: ${nf.format(meta.grupos)} agrupamentos e ` +
      `${nf.format(meta.nos)} nós. Use "Nós" para ver só os principais, ` +
      `aproxime com a roda do mouse ou aumente a frequência mínima.`;
    aviso.hidden = false;
  } else {
    aviso.hidden = true;
  }

  if (!redeUI.eventos) {
    ligarEventosRede();
    redeUI.eventos = true;
  }

  $("figHalo").hidden = true;
  $("vazioHalo").hidden = true;
  $("canvasHalo").hidden = false;
  $("acoesRede").hidden = false;
  $("zoomHalo").hidden = false;
  $("legendaRede").hidden = grupos.length === 0;
  $("rotulosRede").value = redeUI.rotulos;
  $("focoRede").value = String(redeUI.foco);

  dimensionarCanvas();
  ajustarRede();
}

function dimensionarCanvas() {
  const caixa = $("caixaHalo");
  const canvas = $("canvasHalo");
  const largura = Math.max(1, caixa.clientWidth);
  const altura = Math.max(1, caixa.clientHeight);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(largura * dpr);
  canvas.height = Math.round(altura * dpr);
  canvas.style.width = `${largura}px`;
  canvas.style.height = `${altura}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  redeUI.ctx = ctx;
  redeUI.largura = largura;
  redeUI.altura = altura;
}

function areaRede() {
  const dados = redeUI.dados;
  return {
    x0: 18,
    y0: 70,
    x1: Math.max(200, dados.area.largura - 18),
    y1: Math.max(200, dados.altura - 22),
  };
}

function escalaAjuste() {
  const area = areaRede();
  return Math.min((redeUI.largura - 12) / (area.x1 - area.x0),
                  (redeUI.altura - 12) / (area.y1 - area.y0));
}

function ajustarRede() {
  const dados = redeUI.dados;
  if (!dados) return;
  const largura = redeUI.largura;
  const altura = redeUI.altura;
  const area = areaRede();
  const escala = escalaAjuste();
  redeUI.ajuste = escala;
  redeUI.escala = escala;
  redeUI.zoomManual = false;
  redeUI.tx = (largura - (area.x1 - area.x0) * escala) / 2 - area.x0 * escala;
  redeUI.ty = (altura - (area.y1 - area.y0) * escala) / 2 - area.y0 * escala;
  agendarDesenho();
}

function limitarPan() {
  const dados = redeUI.dados;
  if (!dados) return;
  const largura = redeUI.largura;
  const altura = redeUI.altura;
  const area = areaRede();
  const pw = (area.x1 - area.x0) * redeUI.escala;
  const ph = (area.y1 - area.y0) * redeUI.escala;
  const cx = (largura - pw) / 2 - area.x0 * redeUI.escala;
  const cy = (altura - ph) / 2 - area.y0 * redeUI.escala;
  const mx = Math.max(0, (pw - largura) / 2) + 48;
  const my = Math.max(0, (ph - altura) / 2) + 48;
  redeUI.tx = Math.min(cx + mx, Math.max(cx - mx, redeUI.tx));
  redeUI.ty = Math.min(cy + my, Math.max(cy - my, redeUI.ty));
}

function zoomRede(fator, cx, cy) {
  const dados = redeUI.dados;
  if (!dados) return;
  const antes = redeUI.escala;
  const depois = Math.min(16, Math.max(redeUI.ajuste, antes * fator));
  if (Math.abs(depois - antes) < 1e-5) return;
  const mx = (cx - redeUI.tx) / antes;
  const my = (cy - redeUI.ty) / antes;
  redeUI.escala = depois;
  redeUI.zoomManual = depois > redeUI.ajuste + 1e-3;
  redeUI.tx = cx - mx * depois;
  redeUI.ty = cy - my * depois;
  limitarPan();
  agendarDesenho();
}

function agendarDesenho() {
  if (redeUI.raf) return;
  redeUI.raf = requestAnimationFrame(() => {
    redeUI.raf = 0;
    desenharRede();
  });
}

function desenharRede() {
  const dados = redeUI.dados;
  const ctx = redeUI.ctx;
  if (!dados || !ctx) return;

  const largura = redeUI.largura;
  const altura = redeUI.altura;
  const escala = redeUI.escala;
  const tx = redeUI.tx;
  const ty = redeUI.ty;

  let visiveis = null;
  if (redeUI.foco > 0 && dados.nos.length > redeUI.foco) {
    const ordenados = dados.nos.slice().sort(
      (a, b) => b.grau - a.grau || b.frequencia - a.frequencia || a.id - b.id);
    visiveis = new Set(ordenados.slice(0, redeUI.foco).map((no) => no.id));
  }
  redeUI.visiveis = visiveis;

  ctx.clearRect(0, 0, largura, altura);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, largura, altura);

  ctx.save();
  ctx.translate(tx, ty);
  ctx.scale(escala, escala);
  ctx.lineCap = "round";

  ctx.globalAlpha = 0.09;
  for (const grupo of dados.grupos) {
    ctx.fillStyle = grupo.cor;
    ctx.beginPath();
    ctx.arc(grupo.x, grupo.y, grupo.raio, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  ctx.strokeStyle = "#CBD5E1";
  ctx.globalAlpha = 0.62;
  const cruzadas = dados.cruzadas || [];
  if (cruzadas.length && cruzadas.length <= 600) {
    for (const ligacao of cruzadas) {
      if (visiveis &&
          !(visiveis.has(ligacao.a) && visiveis.has(ligacao.b))) continue;
      const a = redeUI.posicao.get(ligacao.a);
      const b = redeUI.posicao.get(ligacao.b);
      if (!a || !b) continue;
      ctx.lineWidth =
        (1.0 + 0.9 * Math.min(ligacao.peso, 1)) / escala;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
  } else {
    for (const ligacao of dados.entre) {
      if (ligacao.peso < 2) continue;
      const a = dados.grupos[ligacao.gi];
      const b = dados.grupos[ligacao.gj];
      ctx.lineWidth = (1.2 + 0.35 * Math.min(ligacao.peso, 10)) / escala;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
  }

  ctx.globalAlpha = 0.55;
  ctx.lineWidth = 0.8 / escala;
  for (const ligacao of dados.soltas) {
    if (visiveis && !(visiveis.has(ligacao.a) && visiveis.has(ligacao.b))) continue;
    const a = redeUI.posicao.get(ligacao.a);
    const b = redeUI.posicao.get(ligacao.b);
    if (!a || !b) continue;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  for (let i = 0; i < dados.grupos.length; i++) {
    const grupo = dados.grupos[i];
    const bloco = redeUI.porGrupo[i];
    ctx.strokeStyle = grupo.cor;
    ctx.globalAlpha = Math.max(0.18,
      Math.min(0.55, 8 / Math.sqrt(Math.max(1, bloco.arestas.length))));
    ctx.lineWidth = 1.15 / escala;
    ctx.beginPath();
    for (const ligacao of bloco.arestas) {
      if (visiveis && !(visiveis.has(ligacao.a) && visiveis.has(ligacao.b))) continue;
      const a = redeUI.posicao.get(ligacao.a);
      const b = redeUI.posicao.get(ligacao.b);
      if (!a || !b) continue;
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
    }
    ctx.stroke();

    ctx.globalAlpha = 1;
    ctx.fillStyle = grupo.cor;
    ctx.beginPath();
    for (const no of bloco.nos) {
      if (visiveis && !visiveis.has(no.id)) continue;
      ctx.moveTo(no.x + no.raio, no.y);
      ctx.arc(no.x, no.y, no.raio, 0, Math.PI * 2);
    }
    ctx.fill();
  }

  ctx.fillStyle = "#ffffff";
  ctx.strokeStyle = "#64748B";
  ctx.globalAlpha = 1;
  ctx.lineWidth = 1.1 / escala;
  ctx.beginPath();
  for (const no of dados.soltos.map((id) => redeUI.posicao.get(id)).filter(Boolean)) {
    if (visiveis && !visiveis.has(no.id)) continue;
    ctx.moveTo(no.x + no.raio, no.y);
    ctx.arc(no.x, no.y, no.raio, 0, Math.PI * 2);
  }
  ctx.fill();
  ctx.stroke();

  ctx.restore();

  desenharSelos();
  desenharRotulos(visiveis);

  if (redeUI.dica) desenharDestaque(redeUI.dica);
}

function desenharSelos() {
  const dados = redeUI.dados;
  const ctx = redeUI.ctx;
  const escala = redeUI.escala;
  redeUI.selos = [];
  const ocupados = [];
  const ordenados = dados.grupos.slice().sort(
    (a, b) => b.nos - a.nos || a.indice - b.indice);

  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = "700 11px Inter, Arial, sans-serif";

  for (const grupo of ordenados) {
    const x = grupo.selo_x * escala + redeUI.tx;
    const y = grupo.selo_y * escala + redeUI.ty;
    if (x < 14 || x > redeUI.largura - 14 || y < 14 || y > redeUI.altura - 14) continue;
    if (ocupados.some((ponto) => Math.hypot(ponto[0] - x, ponto[1] - y) < 26)) continue;
    ocupados.push([x, y]);
    redeUI.selos.push({ x, y, indice: grupo.indice });

    ctx.beginPath();
    ctx.arc(x, y, 10, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,255,255,.96)";
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = grupo.cor;
    ctx.stroke();
    ctx.fillStyle = grupo.cor;
    ctx.fillText(String(grupo.indice), x, y + 0.5);
  }
}

function desenharRotulos(visiveis) {
  if (redeUI.rotulos === "nenhum") return;
  const dados = redeUI.dados;
  const ctx = redeUI.ctx;

  let alvos;
  if (redeUI.rotulos === "todos") {
    const elegiveis = dados.nos.filter((no) => !visiveis || visiveis.has(no.id));
    alvos = elegiveis.slice().sort(
      (a, b) => b.grau - a.grau || b.frequencia - a.frequencia).slice(0, 400);
    if (elegiveis.length > 400 && !redeUI.avisouTodos) {
      redeUI.avisouTodos = true;
      mostrarToast("Rótulos limitados aos 400 nós de maior grau.");
    }
  } else {
    alvos = dados.nos.slice()
      .sort((a, b) => b.grau - a.grau || b.frequencia - a.frequencia)
      .filter((no) => !visiveis || visiveis.has(no.id))
      .slice(0, 16);
  }

  ctx.font = "600 10.5px Inter, Arial, sans-serif";
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";

  const caixas = [];
  for (const no of alvos) {
    const ancoraX = no.x * redeUI.escala + redeUI.tx;
    const y = no.y * redeUI.escala + redeUI.ty;
    if (ancoraX < -30 || ancoraX > redeUI.largura + 30 ||
        y < -10 || y > redeUI.altura + 10) continue;
    const texto = textoNo(no);
    const largura = ctx.measureText(texto).width;
    let x = ancoraX + 5;
    if (x + largura > redeUI.largura - 4) x = ancoraX - largura - 5;
    const linha = Math.min(redeUI.altura - 10, Math.max(12, y));
    const caixa = [x - 2, linha - 7, x + largura + 2, linha + 7];
    if (caixas.some((outra) => !(caixa[2] < outra[0] || caixa[0] > outra[2] ||
                                 caixa[3] < outra[1] || caixa[1] > outra[3]))) continue;
    caixas.push(caixa);
    ctx.lineWidth = 3;
    ctx.strokeStyle = "rgba(255,255,255,.92)";
    ctx.strokeText(texto, x, linha);
    ctx.fillStyle = "#0B1F66";
    ctx.fillText(texto, x, linha);
  }
}

function textoNo(no) {
  let texto = no.rotulo || "";
  if (redeUI.dados.meta.unidade === "Words") {
    texto = texto.replace(/-/g, " ");
    texto = texto.charAt(0) + texto.slice(1).toLowerCase();
  }
  return texto.length > 24 ? `${texto.slice(0, 23)}…` : texto;
}

function desenharDestaque(no) {
  const ctx = redeUI.ctx;
  const x = no.x * redeUI.escala + redeUI.tx;
  const y = no.y * redeUI.escala + redeUI.ty;
  ctx.beginPath();
  ctx.arc(x, y, Math.max(7, no.raio * redeUI.escala + 4), 0, Math.PI * 2);
  ctx.strokeStyle = "#0B1F66";
  ctx.lineWidth = 2;
  ctx.stroke();
}

function posicaoRelativa(evento) {
  const r = $("canvasHalo").getBoundingClientRect();
  return [evento.clientX - r.left, evento.clientY - r.top];
}

function noEm(x, y) {
  const dados = redeUI.dados;
  if (!dados) return null;
  let melhor = null;
  let menor = 16;
  for (const no of dados.nos) {
    if (redeUI.visiveis && !redeUI.visiveis.has(no.id)) continue;
    const sx = no.x * redeUI.escala + redeUI.tx;
    const sy = no.y * redeUI.escala + redeUI.ty;
    const distancia = Math.hypot(sx - x, sy - y);
    const limite = Math.max(9, no.raio * redeUI.escala + 4);
    if (distancia <= limite && distancia < menor) {
      menor = distancia;
      melhor = no;
    }
  }
  return melhor;
}

function seloEm(x, y) {
  return redeUI.selos.find(
    (selo) => Math.hypot(selo.x - x, selo.y - y) <= 13) || null;
}

function mostrarDica(no, x, y) {
  const caixa = $("dicaNo");
  if (!no) {
    caixa.hidden = true;
    return;
  }
  const grupo = redeUI.dados.grupos[no.grupo];
  caixa.replaceChildren();
  const titulo = document.createElement("b");
  titulo.textContent = no.rotulo;
  const detalhe = document.createElement("span");
  detalhe.textContent = `${grupo ? grupo.rotulo_curto : "Sem agrupamento"} · ` +
    `freq ${no.frequencia} · grau ${nf.format(no.grau)}`;
  caixa.append(titulo, document.createElement("br"), detalhe);
  caixa.hidden = false;
  const limite = Math.max(12, $("caixaHalo").clientWidth - caixa.offsetWidth - 16);
  caixa.style.left = `${Math.min(limite, Math.max(8, x))}px`;
  caixa.style.top = `${Math.min($("caixaHalo").clientHeight - 10, Math.max(46, y))}px`;
}

function ligarEventosRede() {
  const canvas = $("canvasHalo");
  const caixa = $("caixaHalo");

  canvas.classList.add("interativa");

  canvas.addEventListener("pointerdown", (evento) => {
    if (evento.button !== 0 || !redeUI.dados) return;
    redeUI.arrastando = true;
    redeUI.moveu = false;
    redeUI.inicio = [evento.clientX, evento.clientY,
                     redeUI.tx, redeUI.ty];
    canvas.classList.add("arrastando");
    try { canvas.setPointerCapture(evento.pointerId); } catch (_) { /* opcional */ }
  });

  canvas.addEventListener("pointermove", (evento) => {
    if (!redeUI.dados) return;
    const [x, y] = posicaoRelativa(evento);
    if (redeUI.arrastando) {
      const dx = evento.clientX - redeUI.inicio[0];
      const dy = evento.clientY - redeUI.inicio[1];
      if (Math.abs(dx) + Math.abs(dy) > 2) redeUI.moveu = true;
      redeUI.tx = redeUI.inicio[2] + dx;
      redeUI.ty = redeUI.inicio[3] + dy;
      limitarPan();
      mostrarDica(null);
      agendarDesenho();
      return;
    }
    const no = noEm(x, y);
    if ((no ? no.id : null) !== (redeUI.dica ? redeUI.dica.id : null)) {
      redeUI.dica = no;
      mostrarDica(no, x, y);
      agendarDesenho();
    } else if (no) {
      mostrarDica(no, x, y);
    }
  });

  const terminar = (evento) => {
    if (!redeUI.arrastando) return;
    redeUI.arrastando = false;
    canvas.classList.remove("arrastando");
    if (redeUI.moveu) return;
    const [x, y] = posicaoRelativa(evento);
    const selo = seloEm(x, y);
    if (selo) { abrirGrupo(selo.indice); return; }
    const no = noEm(x, y);
    if (no && no.grupo >= 0) abrirGrupo(no.grupo + 1);
  };
  canvas.addEventListener("pointerup", terminar);
  canvas.addEventListener("pointercancel", () => {
    redeUI.arrastando = false;
    canvas.classList.remove("arrastando");
  });
  canvas.addEventListener("pointerleave", () => {
    if (redeUI.arrastando) return;
    redeUI.dica = null;
    mostrarDica(null);
    agendarDesenho();
  });

  canvas.addEventListener("wheel", (evento) => {
    if (!redeUI.dados) return;
    evento.preventDefault();
    const [x, y] = posicaoRelativa(evento);
    zoomRede(Math.exp(-evento.deltaY * 0.0018), x, y);
  }, { passive: false });

  canvas.addEventListener("dblclick", (evento) => {
    const [x, y] = posicaoRelativa(evento);
    zoomRede(redeUI.escala > redeUI.ajuste * 1.01 ? 1 / redeUI.escala : 2, x, y);
  });

  new ResizeObserver(() => {
    if (!redeUI.dados) return;
    const centro = [
      (redeUI.largura / 2 - redeUI.tx) / redeUI.escala,
      (redeUI.altura / 2 - redeUI.ty) / redeUI.escala,
    ];
    const manual = redeUI.zoomManual;
    dimensionarCanvas();
    if (!manual) {
      ajustarRede();
      return;
    }
    redeUI.ajuste = escalaAjuste();
    redeUI.escala = Math.max(redeUI.escala, redeUI.ajuste);
    redeUI.tx = redeUI.largura / 2 - centro[0] * redeUI.escala;
    redeUI.ty = redeUI.altura / 2 - centro[1] * redeUI.escala;
    limitarPan();
    agendarDesenho();
  }).observe(caixa);
}

/* ------------------------------------------------ índices, documentos e mapas */

const ROTULOS_MAPEADOR = {
  nucleo: "Núcleo", interseccao: "Interseção", secundarios: "Secundários",
  kcore: "k-core", uniao: "União", acoplamento: "Acoplamento",
};

function renderizarIndices(resultado) {
  const corpo = $("indicesCorpo");
  corpo.replaceChildren();
  const grupos = resultado.grupos || [];
  $("linkIndices").textContent = `${grupos.length} grupos`;

  if (!grupos.length) {
    const linha = document.createElement("tr");
    const celula = document.createElement("td");
    celula.colSpan = 12;
    celula.style.color = "#8A94A6";
    celula.textContent = "Nenhum agrupamento nesta configuração.";
    linha.append(celula);
    corpo.append(linha);
    return;
  }

  for (const grupo of grupos) {
    for (const [mapeador, medidas] of Object.entries(grupo.medidas || {})) {
      const linha = document.createElement("tr");
      const celulas = [
        String(grupo.selo),
        grupo.rotulo,
        ROTULOS_MAPEADOR[mapeador] || mapeador,
      ];
      for (const nome of ["documentos", "h", "g", "hg", "q2", "media",
        "soma", "minimo", "maximo"]) {
        celulas.push(nf.format(medidas[nome] ?? 0));
      }
      celulas.forEach((valor, indice) => {
        const celula = document.createElement("td");
        if (indice >= 3) celula.className = "num";
        celula.textContent = valor;
        linha.append(celula);
      });
      linha.addEventListener("click", () => abrirGrupo(grupo.selo));
      linha.style.cursor = "pointer";
      corpo.append(linha);
    }
  }
}

async function carregarDocumentos() {
  const corpo = $("documentosCorpo");
  if (!estado.token) return;
  const token = estado.token;
  estado.docsToken = token;
  const busca = $("buscaDocumentos").value.trim();
  corpo.replaceChildren(linhaVazia("lendo os documentos…", 6));
  try {
    const dados = await api(`/api/documentos?token=${encodeURIComponent(token)}` +
      `&busca=${encodeURIComponent(busca)}`);
    if (token !== estado.token) return;
    $("metaDocumentos").textContent = `${dados.total} documentos · ${dados.periodo}`;
    corpo.replaceChildren();
    if (!dados.documentos.length) {
      corpo.append(linhaVazia("Nenhum documento encontrado.", 6));
      return;
    }
    dados.documentos.forEach((doc, indice) => {
      const linha = document.createElement("tr");
      const valores = [String(indice + 1), doc.titulo, doc.autores, doc.ano,
        doc.fonte, String(doc.citacoes)];
      valores.forEach((valor, posicao) => {
        const celula = document.createElement("td");
        if (posicao === 3 || posicao === 5) celula.className = "num";
        celula.textContent = valor || "—";
        if (posicao === 1) celula.title = valor;
        linha.append(celula);
      });
      corpo.append(linha);
    });
    $("rodapeDocumentos").textContent =
      `${dados.total} documentos no período ${dados.periodo}.`;
  } catch (erro) {
    corpo.replaceChildren(linhaVazia(erro.message, 6));
  }
}

function linhaVazia(texto, colunas) {
  const linha = document.createElement("tr");
  const celula = document.createElement("td");
  celula.colSpan = colunas;
  celula.style.color = "#8A94A6";
  celula.textContent = texto;
  linha.append(celula);
  return linha;
}

async function compararPeriodos() {
  if (!estado.projeto) return;
  if (!estado.resultado) {
    mostrarToast("Execute uma prévia antes de comparar períodos.", true);
    return;
  }
  $("vazioLongitudinal").hidden = false;
  $("vazioLongitudinal").textContent = "calculando os mapas…";
  $("mapasLongitudinais").hidden = true;
  const dados = parametros();
  delete dados.periodo;
  try {
    const mapa = await api("/api/longitudinal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    $("figEvolucao").src = mapa.figuras.evolucao;
    $("figEvolucao").hidden = false;
    $("figSobreposicao").src = mapa.figuras.sobreposicao;
    $("figSobreposicao").hidden = false;
    $("mapasLongitudinais").hidden = false;
    $("vazioLongitudinal").hidden = true;
    $("downloadEvolucao").href = mapa.download;
    $("downloadEvolucao").hidden = false;
    $("metaLongitudinal").textContent =
      `${mapa.periodos.length} períodos · ${mapa.nos} agrupamentos · ${mapa.elos} elos`;
    $("rodapeLongitudinal").textContent =
      `Medida de sobreposição: ` +
      `${MEDIDAS_TEMPORAIS[mapa.medida] || mapa.medida}. ` +
      "Elos ligam agrupamentos de períodos consecutivos que compartilham itens.";
  } catch (erro) {
    $("vazioLongitudinal").textContent = erro.message;
    mostrarToast(erro.message, true);
  }
}

function exportar(tipo) {
  if (!estado.token) {
    mostrarToast("Execute uma prévia antes de exportar.", true);
    return;
  }
  window.location.href = `/api/exportar?token=${encodeURIComponent(estado.token)}` +
    `&tipo=${encodeURIComponent(tipo)}`;
}

async function gerarRelatorio(formato) {
  if (!estado.projeto) return;
  const dados = parametros();
  delete dados.periodo;
  dados.formato = formato;
  dados.estendido = true;
  const botao = $("btnRelatorio");
  botao.disabled = true;
  botao.textContent = "Gerando…";
  try {
    const relatorio = await api("/api/relatorio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    const link = document.createElement("a");
    link.href = relatorio.url;
    link.target = "_blank";
    link.rel = "noopener";
    document.body.append(link);
    link.click();
    link.remove();
    mostrarToast("Relatório aberto em nova aba.");
  } catch (erro) {
    mostrarToast(erro.message, true);
  } finally {
    botao.disabled = false;
    botao.textContent = "Relatório";
  }
}

/* ------------------------------------------------------------- edição da base */

const TIPOS_GRUPO = {
  palavra: "Palavras", autor: "Autores", referencia: "Referências",
  autor_referencia: "Autores de referência", fonte: "Fontes de referência",
};

function abrirBase() {
  if (!estado.projeto) return;
  $("modalBase").hidden = false;
  carregarBase();
}

function fecharBase() {
  $("modalBase").hidden = true;
}

async function carregarBase() {
  if (!estado.projeto) return;
  try {
    const base = await api(`/api/base?caminho=${encodeURIComponent(
      estado.projeto.caminho)}`);
    estado.base = base;
    renderizarBase(base);
  } catch (erro) {
    mostrarToast(erro.message, true);
  }
}

function renderizarBase(base) {
  $("baseResumo").textContent =
    `${base.documentos} documentos · ${base.periodos.length} períodos · ` +
    `caminho ${base.caminho}`;
  $("baseUndo").textContent = base.desfazer
    ? `${base.desfazer} alteração(ões) guardada(s)` : "nada para desfazer";

  const periodos = $("basePeriodos");
  periodos.replaceChildren();
  for (const periodo of base.periodos) {
    const item = document.createElement("div");
    item.className = "item-base";

    const nome = document.createElement("input");
    nome.type = "text";
    nome.value = periodo.nome;
    nome.className = "nome";

    const inicio = document.createElement("input");
    inicio.type = "number";
    inicio.className = "ano";
    inicio.value = periodo.inicio ?? "";
    inicio.placeholder = "ano";

    const fim = document.createElement("input");
    fim.type = "number";
    fim.className = "ano";
    fim.value = periodo.fim ?? "";
    fim.placeholder = "ano";

    const contagem = document.createElement("span");
    contagem.className = "contagem";
    contagem.textContent =
      `${periodo.documentos} ${periodo.documentos === 1 ? "doc" : "docs"} · ${periodo.datas} datas`;

    const salvar = botaoMini("Salvar", () => editarBase({
      acao: "renomear-periodo", id: periodo.id, nome: nome.value,
    }));
    const redistribuir = botaoMini("Redistribuir", () => editarBase({
      acao: "redistribuir-periodo", id: periodo.id,
      inicio: Number(inicio.value), fim: Number(fim.value),
    }));
    const excluir = botaoMini("Excluir", () => {
      if (!confirm(`Excluir o período ${periodo.nome}?`)) return;
      editarBase({ acao: "excluir-periodo", id: periodo.id });
    }, "perigo");

    item.append(nome, inicio, fim, contagem, salvar, redistribuir, excluir);
    periodos.append(item);
  }

  renderizarGruposBase(base);
}

function chaveBusca(texto) {
  return (texto || "").normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function renderizarGruposBase(base) {
  const tipo = $("baseTipo").value;
  const todos = base.grupos[tipo] || [];
  const busca = chaveBusca($("buscaBase").value.trim());
  const grupos = busca
    ? todos.filter((grupo) => chaveBusca(grupo.nome).includes(busca))
    : todos;
  $("baseGrupoTotal").textContent = busca
    ? `${grupos.length} de ${todos.length} grupos`
    : `${grupos.length} grupos`;
  const lista = $("baseGrupos");
  lista.replaceChildren();

  const origem = $("baseOrigem");
  const destino = $("baseDestino");
  origem.replaceChildren();
  destino.replaceChildren();
  for (const grupo of todos) {
    for (const select of [origem, destino]) {
      const opcao = document.createElement("option");
      opcao.value = String(grupo.id);
      opcao.textContent = grupo.nome;
      select.append(opcao);
    }
  }
  if (destino.options.length > 1) destino.selectedIndex = 1;

  if (!grupos.length) {
    const vazio = document.createElement("div");
    vazio.className = "dica";
    vazio.textContent = busca
      ? "Nenhum grupo com esse termo." : "Nenhum grupo neste tipo.";
    lista.append(vazio);
    return;
  }

  for (const grupo of grupos.slice(0, 400)) {
    const item = document.createElement("div");
    item.className = "item-base";

    const nome = document.createElement("input");
    nome.type = "text";
    nome.value = grupo.nome;
    nome.className = "nome";

    const contagem = document.createElement("span");
    contagem.className = "contagem";
    contagem.textContent =
      `${grupo.itens} ${grupo.itens === 1 ? "item" : "itens"} · ` +
      `${grupo.documentos} ${grupo.documentos === 1 ? "doc" : "docs"}`;

    const salvar = botaoMini("Salvar", () => editarBase({
      acao: "renomear-grupo", tipo, id: grupo.id, nome: nome.value,
    }));
    const parada = botaoMini(grupo.parada ? "Reativar" : "Parar", () => editarBase({
      acao: "marcar-parada", tipo, id: grupo.id, parada: !grupo.parada,
    }));

    item.append(nome, contagem, salvar, parada);
    lista.append(item);
  }
}

function botaoMini(texto, acao, classe = "") {
  const botao = document.createElement("button");
  botao.type = "button";
  botao.className = "botao-mini" + (classe ? ` ${classe}` : "");
  botao.textContent = texto;
  botao.addEventListener("click", acao);
  return botao;
}

async function editarBase(dados) {
  try {
    const base = await api("/api/base", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...dados, caminho: estado.projeto.caminho }),
    });
    renderizarBase(base);
    if (typeof BIB !== "undefined") BIB.cache = {};
    const projeto = await api("/api/abrir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caminho: estado.projeto.caminho }),
    });
    aplicarProjeto(projeto);
    const visao = $("visaoGeral");
    if (visao && !visao.hidden && !visao.classList.contains("oculta")
        && typeof carregarBibliometria === "function") carregarBibliometria();
    mostrarToast("Base atualizada.");
  } catch (erro) {
    mostrarToast(erro.message, true);
  }
}

async function juntarGruposBase() {
  const tipo = $("baseTipo").value;
  const origem = Number($("baseOrigem").value);
  const destino = Number($("baseDestino").value);
  if (!origem || !destino || origem === destino) {
    mostrarToast("Escolha dois grupos diferentes.", true);
    return;
  }
  if (!confirm("O grupo de origem será absorvido pelo destino. Continuar?")) return;
  await editarBase({ acao: "juntar-grupos", tipo, origem, destino });
}

/* ------------------------------------------------------- mapa interativo */

const mapaUI = {
  dados: null,
  ctx: null,
  largura: 0,
  altura: 0,
  dpr: 1,
  base: 1,
  offx: 0,
  offy: 0,
  zoom: 1,
  pan: { x: 0, y: 0 },
  sobre: -1,
  selecionado: -1,
  arrastando: false,
  moveu: false,
  inicio: null,
  pedido: 0,
  caminhos: [],
};

async function carregarMapa(token) {
  if (!token || token !== estado.token) return;
  const pedido = ++mapaUI.pedido;
  try {
    const resposta = await fetch(
      `/api/mapa?token=${encodeURIComponent(token)}`);
    if (!resposta.ok) throw new Error("mapa indisponível");
    const dados = await resposta.json();
    if (pedido !== mapaUI.pedido) return;
    mapaUI.dados = dados;
    mapaUI.selecionado = -1;
    mapaUI.sobre = -1;
    prepararMapa();
  } catch (erro) {
    $("canvasMapa").hidden = true;
    $("figMapa").hidden = false;
  }
}

function prepararMapa() {
  const dados = mapaUI.dados;
  if (!dados) return;
  const canvas = $("canvasMapa");
  mapaUI.ctx = canvas.getContext("2d");
  mapaUI.caminhos = dados.contorno.map((item) => ({
    d: item.n,
    caminho: new Path2D(item.d),
  }));
  mapaUI.geoAtivos = new Set(dados.paises.map((pais) => pais.geo));
  mapaUI.zoom = 1;
  mapaUI.pan = { x: 0, y: 0 };
  // O cartão pode estar em transição de layout: mede depois do quadro.
  requestAnimationFrame(() => {
    ajustarCanvasMapa();
    desenharMapa();
  });
}

function ajustarCanvasMapa() {
  const dados = mapaUI.dados;
  const caixa = $("caixaMapa");
  const canvas = $("canvasMapa");
  if (!dados || !caixa || !canvas) return;
  const largura = Math.max(240, caixa.clientWidth);
  const altura = Math.max(200, caixa.clientHeight);
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(largura * dpr);
  canvas.height = Math.round(altura * dpr);
  mapaUI.largura = largura;
  mapaUI.altura = altura;
  mapaUI.dpr = dpr;
  mapaUI.base = Math.min(largura / dados.largura, altura / dados.altura);
  mapaUI.offx = (largura - dados.largura * mapaUI.base) / 2;
  mapaUI.offy = (altura - dados.altura * mapaUI.base) / 2;
}

function desenharMapa() {
  const dados = mapaUI.dados;
  const ctx = mapaUI.ctx;
  if (!dados || !ctx) return;
  const canvas = $("canvasMapa");
  if (canvas && canvas.width !== Math.round(mapaUI.largura * mapaUI.dpr)) {
    ajustarCanvasMapa();
  }
  const { largura, altura, dpr, base, offx, offy } = mapaUI;
  const z = mapaUI.zoom;
  const tx = offx + mapaUI.pan.x;
  const ty = offy + mapaUI.pan.y;
  const foco = mapaUI.sobre >= 0 ? mapaUI.sobre : mapaUI.selecionado;
  const maximo = Math.max(1, dados.maximo);
  const maxPeso = Math.max(1, dados.max_peso);

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
  ctx.fillStyle = "#F7F8FB";
  ctx.fillRect(0, 0, largura, altura);

  ctx.save();
  ctx.translate(tx, ty);
  ctx.scale(base * z, base * z);

  for (const item of mapaUI.caminhos) {
    ctx.fillStyle = mapaUI.geoAtivos.has(item.d) ? "#D6CFF8" : "#ECEAF5";
    ctx.fill(item.caminho, "evenodd");
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = 0.6 / (base * z);
    ctx.stroke(item.caminho);
  }

  ctx.lineCap = "round";
  for (const [i, j, peso] of dados.ligacoes) {
    const a = dados.paises[i];
    const b = dados.paises[j];
    if (!a || !b) continue;
    const destaque = foco >= 0 && (foco === i || foco === j);
    ctx.globalAlpha = foco < 0
      ? 0.2 + 0.45 * (peso / maxPeso)
      : (destaque ? 0.8 : 0.06);
    ctx.strokeStyle = destaque ? "#2F2BFF" : "#6A3BFF";
    ctx.lineWidth = 0.8 + 4.2 * (peso / maxPeso);
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const curvatura = Math.min(0.22, 0.1 + peso * 0.02);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.quadraticCurveTo(mx - dy * curvatura, my + dx * curvatura, b.x, b.y);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  const candidatos = [];
  for (let i = 0; i < dados.paises.length; i += 1) {
    const pais = dados.paises[i];
    const raio = 4 + 17 * Math.sqrt(pais.documentos / maximo);
    const ativo = i === mapaUI.selecionado;
    const apontado = i === mapaUI.sobre;
    ctx.beginPath();
    ctx.arc(pais.x, pais.y, raio, 0, Math.PI * 2);
    ctx.fillStyle = ativo ? "#2F2BFF" : "#FFFFFF";
    ctx.fill();
    ctx.lineWidth = ativo ? 2.4 : 2;
    ctx.strokeStyle = ativo ? "#FFC400" : "#2F2BFF";
    if (apontado && !ativo) {
      ctx.lineWidth = 3;
      ctx.strokeStyle = "#6A3BFF";
    }
    ctx.stroke();
    if (apontado || ativo) {
      candidatos.push({ pais, raio, forte: true });
    }
  }

  const principais = dados.paises
    .slice()
    .sort((a, b) => b.documentos - a.documentos)
    .slice(0, 14);
  for (const pais of principais) {
    const raio = 4 + 17 * Math.sqrt(pais.documentos / maximo);
    candidatos.push({ pais, raio, forte: false });
  }

  ctx.restore();

  ctx.font = "600 11px Inter, Arial, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";
  const ocupados = [];
  for (const candidato of candidatos) {
    const texto = `${candidato.pais.nome} ${candidato.pais.documentos}`;
    const x = candidato.pais.x * base * z + tx;
    const y = (candidato.pais.y - candidato.raio) * base * z + ty - 5;
    const largura = texto.length * 7.0 + 12;
    const caixa = [x - largura / 2, y - 9, largura, 17];
    const colide = ocupados.some((outra) => !(
      caixa[0] + caixa[2] < outra[0] || outra[0] + outra[2] < caixa[0] ||
      caixa[1] + caixa[3] < outra[1] || outra[1] + outra[3] < caixa[1]));
    if (colide && !candidato.forte) continue;
    ocupados.push(caixa);
    ctx.strokeStyle = "rgba(255,255,255,0.92)";
    ctx.lineWidth = 3.4;
    ctx.strokeText(texto, x, y);
    ctx.fillStyle = candidato.forte ? "#0B1F66" : "#33415C";
    ctx.fillText(texto, x, y);
  }
}

function pontoMapa(evento) {
  const retangulo = $("canvasMapa").getBoundingClientRect();
  const largura = mapaUI.dados.largura;
  const altura = mapaUI.dados.altura;
  const base = mapaUI.base * mapaUI.zoom;
  const x = (evento.clientX - retangulo.left - mapaUI.offx - mapaUI.pan.x) / base;
  const y = (evento.clientY - retangulo.top - mapaUI.offy - mapaUI.pan.y) / base;
  return { x, y, dentro: x >= 0 && y >= 0 && x <= largura && y <= altura };
}

function paisNoMapa(x, y) {
  const dados = mapaUI.dados;
  if (!dados) return -1;
  const maximo = Math.max(1, dados.maximo);
  let melhor = -1;
  let distancia = Infinity;
  for (let i = 0; i < dados.paises.length; i += 1) {
    const pais = dados.paises[i];
    const raio = 4 + 17 * Math.sqrt(pais.documentos / maximo);
    const d = Math.hypot(pais.x - x, pais.y - y);
    if (d <= Math.max(raio + 3, 8) && d < distancia) {
      distancia = d;
      melhor = i;
    }
  }
  return melhor;
}

function dicaDoMapa(indice) {
  const dados = mapaUI.dados;
  const dica = $("dicaMapa");
  if (!dados || indice < 0) {
    dica.hidden = true;
    return;
  }
  const pais = dados.paises[indice];
  const parceiros = dados.ligacoes
    .filter(([i, j]) => i === indice || j === indice)
    .map(([i, j, peso]) => ({ outro: dados.paises[i === indice ? j : i], peso }))
    .sort((a, b) => b.peso - a.peso)
    .slice(0, 3)
    .map((item) => `${item.outro.nome} (${item.peso})`)
    .join(", ");
  dica.replaceChildren();
  const titulo = document.createElement("b");
  titulo.textContent = pais.nome;
  const linha = document.createElement("div");
  linha.textContent =
    `${pais.documentos} documentos · ${pais.parceiros} parceiros`;
  dica.append(titulo, linha);
  if (parceiros) {
    const extra = document.createElement("span");
    extra.textContent = `Principais: ${parceiros}`;
    dica.append(extra);
  }
  dica.hidden = false;
}

function ligarMapa() {
  const canvas = $("canvasMapa");
  if (!canvas) return;

  canvas.addEventListener("pointerdown", (evento) => {
    if (!mapaUI.dados) return;
    mapaUI.arrastando = true;
    mapaUI.moveu = false;
    mapaUI.inicio = { x: evento.clientX, y: evento.clientY,
                      pan: { ...mapaUI.pan } };
    canvas.classList.add("arrastando");
    try { canvas.setPointerCapture(evento.pointerId); } catch (_) { /* sintético */ }
  });

  canvas.addEventListener("pointermove", (evento) => {
    if (!mapaUI.dados) return;
    if (mapaUI.arrastando) {
      const dx = evento.clientX - mapaUI.inicio.x;
      const dy = evento.clientY - mapaUI.inicio.y;
      if (Math.hypot(dx, dy) > 3) mapaUI.moveu = true;
      mapaUI.pan = { x: mapaUI.inicio.pan.x + dx,
                     y: mapaUI.inicio.pan.y + dy };
      desenharMapa();
      return;
    }
    const ponto = pontoMapa(evento);
    const indice = paisNoMapa(ponto.x, ponto.y);
    if (indice !== mapaUI.sobre) {
      mapaUI.sobre = indice;
      dicaDoMapa(indice);
      desenharMapa();
    }
    const dica = $("dicaMapa");
    if (indice >= 0) {
      const retangulo = $("caixaMapa").getBoundingClientRect();
      const x = evento.clientX - retangulo.left;
      const y = evento.clientY - retangulo.top;
      const larguraDica = dica.offsetWidth || 210;
      const paraEsquerda = x + larguraDica + 24 > retangulo.width;
      dica.style.left = `${x}px`;
      dica.style.top = `${y}px`;
      dica.style.transform = paraEsquerda
        ? "translate(-100%, -100%) translate(-8px, -2px)"
        : "translate(12px, -100%)";
    }
    canvas.style.cursor = indice >= 0 ? "pointer" : "grab";
  });

  const soltar = (evento) => {
    if (!mapaUI.arrastando) return;
    mapaUI.arrastando = false;
    canvas.classList.remove("arrastando");
    if (mapaUI.moveu) return;
    const ponto = pontoMapa(evento);
    const indice = paisNoMapa(ponto.x, ponto.y);
    mapaUI.selecionado = indice === mapaUI.selecionado ? -1 : indice;
    mapaUI.sobre = indice;
    dicaDoMapa(indice);
    desenharMapa();
  };
  canvas.addEventListener("pointerup", soltar);
  canvas.addEventListener("pointercancel", soltar);
  canvas.addEventListener("pointerleave", () => {
    if (mapaUI.arrastando) return;
    mapaUI.sobre = -1;
    $("dicaMapa").hidden = true;
    desenharMapa();
  });

  canvas.addEventListener("wheel", (evento) => {
    if (!mapaUI.dados) return;
    evento.preventDefault();
    const retangulo = canvas.getBoundingClientRect();
    const px = evento.clientX - retangulo.left - mapaUI.offx - mapaUI.pan.x;
    const py = evento.clientY - retangulo.top - mapaUI.offy - mapaUI.pan.y;
    const fator = Math.exp(-evento.deltaY * 0.0015);
    const zoom = Math.min(8, Math.max(0.8, mapaUI.zoom * fator));
    const escala = zoom / mapaUI.zoom;
    mapaUI.pan.x -= px * (escala - 1);
    mapaUI.pan.y -= py * (escala - 1);
    mapaUI.zoom = zoom;
    desenharMapa();
  }, { passive: false });

  canvas.addEventListener("dblclick", () => {
    mapaUI.zoom = 1;
    mapaUI.pan = { x: 0, y: 0 };
    mapaUI.selecionado = -1;
    desenharMapa();
  });

  document.querySelectorAll("#zoomMapa [data-zoom]").forEach((botao) => {
    botao.addEventListener("click", () => {
      const acao = botao.dataset.zoom;
      if (acao === "reset") {
        mapaUI.zoom = 1;
        mapaUI.pan = { x: 0, y: 0 };
      } else {
        const fator = acao === "mais" ? 1.35 : 1 / 1.35;
        mapaUI.zoom = Math.min(8, Math.max(0.8, mapaUI.zoom * fator));
      }
      desenharMapa();
    });
  });

  window.addEventListener("resize", () => {
    if (!mapaUI.dados) return;
    ajustarCanvasMapa();
    desenharMapa();
  });
}

/* -------------------------------------------------- diagrama estratégico */

const diagramaUI = {
  dados: null,
  ctx: null,
  largura: 0,
  altura: 0,
  dpr: 1,
  area: { x0: 0, x1: 0, y0: 0, y1: 0 },
  limites: { x0: 0, x1: 1, y0: 0, y1: 1 },
  dominio: { x0: 0, x1: 1, y0: 0, y1: 1 },
  novo: true,
  sobre: null,
  selecionado: null,
  arrastando: false,
  moveu: false,
  inicio: null,
  rotulos: "nenhum",
  pedido: 0,
};

async function carregarDiagrama(token) {
  if (!token || token !== estado.token) return;
  $("legendaDiagrama").hidden = true;
  const pedido = ++diagramaUI.pedido;
  try {
    const resposta = await fetch(
      `/api/estrategico?token=${encodeURIComponent(token)}`);
    if (!resposta.ok) throw new Error("diagrama indisponível");
    const dados = await resposta.json();
    if (pedido !== diagramaUI.pedido) return;
    diagramaUI.dados = dados;
    diagramaUI.ctx = $("canvasEstrategico").getContext("2d");
    diagramaUI.sobre = null;
    diagramaUI.selecionado = null;
    diagramaUI.novo = true;
    diagramaUI.rotulos = dados.pontos.length <= 12 ? "todos"
      : (dados.pontos.length <= 40 ? "principais" : "nenhum");
    $("rotulosDiagrama").value = diagramaUI.rotulos;
    const contagens = estado.resultado?.quadrantes || {};
    $("estatEstrategico").replaceChildren(...dados.quadrantes.map((item) =>
      estatistica(item.curto, contagens[item.chave] ?? 0, item.cor,
                  `${item.rotulo}: ${item.descricao}`)));
    montarLegendaDiagrama();
    requestAnimationFrame(() => {
      ajustarCanvasDiagrama();
      desenharDiagrama();
    });
  } catch (erro) {
    $("canvasEstrategico").hidden = true;
    $("figEstrategico").hidden = false;
    $("zoomEstrategico").hidden = false;
    $("legendaDiagrama").hidden = true;
  }
}

function raioDiagrama(ponto) {
  const dados = diagramaUI.dados;
  const maximo = Math.max(1, dados.max_nos);
  const total = dados.pontos.length;
  const base = total > 400 ? 2.2 : (total > 200 ? 3 : (total > 120 ? 4
    : (total > 80 ? 5 : (total > 40 ? 6 : 8))));
  const amplitude = total > 400 ? 5 : (total > 200 ? 6 : (total > 120 ? 9
    : (total > 80 ? 11 : (total > 40 ? 14 : 20))));
  return base + amplitude * Math.sqrt(ponto.nos / maximo);
}

function raioSelo() {
  const total = diagramaUI.dados?.pontos.length || 0;
  return total > 400 ? 7 : (total > 120 ? 9 : 11);
}

function ajustarCanvasDiagrama() {
  const dados = diagramaUI.dados;
  const caixa = $("caixaEstrategico");
  const canvas = $("canvasEstrategico");
  if (!dados || !caixa || !canvas) return;
  const largura = Math.max(260, caixa.clientWidth);
  const altura = Math.max(200, caixa.clientHeight);
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(largura * dpr);
  canvas.height = Math.round(altura * dpr);
  const margem_esq = largura < 560 ? 50 : 64;
  const margem_base = largura < 560 ? 42 : 48;
  diagramaUI.largura = largura;
  diagramaUI.altura = altura;
  diagramaUI.dpr = dpr;
  diagramaUI.area = {
    x0: margem_esq,
    x1: largura - 26,
    y0: 24,
    y1: altura - margem_base,
  };

  // Folga nas bordas: a esfera do valor extremo precisa caber inteira
  // dentro da moldura do diagrama, com o selo ainda visível.
  const area = diagramaUI.area;
  const raio = Math.max(...dados.pontos.map(raioDiagrama), 6) + raioSelo() + 2;
  const largura_util = Math.max(60, (area.x1 - area.x0) - 2 * raio);
  const altura_util = Math.max(60, (area.y1 - area.y0) - 2 * raio);
  const folga_x = raio / largura_util;
  const folga_y = raio / altura_util;
  diagramaUI.limites = {
    x0: -folga_x,
    x1: 1 + folga_x,
    y0: -folga_y,
    y1: 1 + folga_y,
  };
  if (diagramaUI.novo) {
    diagramaUI.dominio = { ...diagramaUI.limites };
    diagramaUI.novo = false;
  } else {
    const atual = diagramaUI.dominio;
    const largura_atual = atual.x1 - atual.x0;
    const altura_atual = atual.y1 - atual.y0;
    const limites = diagramaUI.limites;
    if (largura_atual >= (limites.x1 - limites.x0) - 1e-6) {
      atual.x0 = limites.x0;
      atual.x1 = limites.x1;
    }
    if (altura_atual >= (limites.y1 - limites.y0) - 1e-6) {
      atual.y0 = limites.y0;
      atual.y1 = limites.y1;
    }
  }
}

function escalaDiagramaX(valor) {
  const a = diagramaUI.area;
  const d = diagramaUI.dominio;
  return a.x0 + (valor - d.x0) / (d.x1 - d.x0) * (a.x1 - a.x0);
}

function escalaDiagramaY(valor) {
  const a = diagramaUI.area;
  const d = diagramaUI.dominio;
  return a.y1 - (valor - d.y0) / (d.y1 - d.y0) * (a.y1 - a.y0);
}

function valorDiagramaX(x) {
  const a = diagramaUI.area;
  const d = diagramaUI.dominio;
  return d.x0 + (x - a.x0) / (a.x1 - a.x0) * (d.x1 - d.x0);
}

function valorDiagramaY(y) {
  const a = diagramaUI.area;
  const d = diagramaUI.dominio;
  return d.y1 - (y - a.y0) / (a.y1 - a.y0) * (d.y1 - d.y0);
}

function comAlfa(hex, alfa) {
  const limpo = hex.replace("#", "");
  const inteiro = parseInt(limpo.length === 3
    ? limpo.split("").map((c) => c + c).join("") : limpo, 16);
  return `rgba(${(inteiro >> 16) & 255}, ${(inteiro >> 8) & 255}, ` +
    `${inteiro & 255}, ${alfa})`;
}

function corDoQuadrante(chave) {
  const achado = (diagramaUI.dados.quadrantes || [])
    .find((item) => item.chave === chave);
  return achado ? achado.cor : "#2F2BFF";
}

function rotuloDoQuadrante(chave) {
  const achado = (diagramaUI.dados.quadrantes || [])
    .find((item) => item.chave === chave);
  return achado ? achado.rotulo : "";
}

function colideCaixa(caixa, outras) {
  return outras.some((outra) => !(
    caixa[0] + caixa[2] < outra[0] || outra[0] + outra[2] < caixa[0] ||
    caixa[1] + caixa[3] < outra[1] || outra[1] + outra[3] < caixa[1]));
}

function rotulosDosQuadrantes(ctx, dados, regioes) {
  const nomes = {};
  for (const item of dados.quadrantes) nomes[item.chave] = item.curto;

  ctx.font = "700 9px Inter, Arial, sans-serif";
  ctx.textBaseline = "top";
  ctx.textAlign = "left";
  for (const [chave, x, y, largura_regiao, altura_regiao] of regioes) {
    // Em quadrantes estreitos (zoom) o rótulo sairia pela moldura.
    if (largura_regiao < 88 || altura_regiao < 42) continue;
    const texto = (nomes[chave] || "").toUpperCase();
    if (!texto) continue;
    const largura_texto = ctx.measureText(texto).width;
    const caixa = { largura: largura_texto + 10, altura: 18 };
    const margem = 9;
    const cantos = [
      [x + margem, y + margem],
      [x + largura_regiao - margem - caixa.largura, y + margem],
      [x + margem, y + altura_regiao - margem - caixa.altura],
      [x + largura_regiao - margem - caixa.largura,
       y + altura_regiao - margem - caixa.altura],
    ];
    let melhor = cantos[0];
    let menor = Infinity;
    for (const [cx, cy] of cantos) {
      let ocupados = 0;
      for (const ponto of dados.pontos) {
        const sx = escalaDiagramaX(ponto.x);
        const sy = escalaDiagramaY(ponto.y);
        const raio = raioDiagrama(ponto);
        if (sx + raio >= cx && sx - raio <= cx + caixa.largura &&
            sy + raio >= cy && sy - raio <= cy + caixa.altura) {
          ocupados += 1;
        }
      }
      if (ocupados < menor) {
        menor = ocupados;
        melhor = [cx, cy];
      }
    }
    ctx.globalAlpha = 0.55;
    ctx.fillStyle = corDoQuadrante(chave);
    ctx.fillText(texto, melhor[0] + 5, melhor[1] + 4);
    ctx.globalAlpha = 1;
  }
}

function desenharDiagrama() {
  const dados = diagramaUI.dados;
  const ctx = diagramaUI.ctx;
  if (!dados || !ctx) return;
  const { largura, altura, dpr, area } = diagramaUI;
  const dominio = diagramaUI.dominio;

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, largura, altura);

  const fundo = {};
  for (const item of dados.quadrantes) fundo[item.chave] = item.fundo;

  ctx.save();
  ctx.beginPath();
  ctx.rect(area.x0, area.y0, area.x1 - area.x0, area.y1 - area.y0);
  ctx.clip();

  // Os quadrantes pintam a área inteira do gráfico, inclusive a folga que
  // deixa as esferas das extremidades dentro da moldura.
  const meio_x = Math.min(Math.max(escalaDiagramaX(0.5), area.x0), area.x1);
  const meio_y = Math.min(Math.max(escalaDiagramaY(0.5), area.y0), area.y1);
  const regioes = [
    ["nicho", area.x0, area.y0, meio_x - area.x0, meio_y - area.y0],
    ["motor", meio_x, area.y0, area.x1 - meio_x, meio_y - area.y0],
    ["emergente", area.x0, meio_y, meio_x - area.x0, area.y1 - meio_y],
    ["basico", meio_x, meio_y, area.x1 - meio_x, area.y1 - meio_y],
  ];
  for (const [chave, x, y, largura_regiao, altura_regiao] of regioes) {
    if (largura_regiao <= 0 || altura_regiao <= 0) continue;
    ctx.fillStyle = fundo[chave] || "#F7F8FB";
    ctx.fillRect(x, y, largura_regiao, altura_regiao);
  }

  rotulosDosQuadrantes(ctx, dados, regioes);

  if (dominio.x0 <= 0.5 && 0.5 <= dominio.x1 &&
      dominio.y0 <= 0.5 && 0.5 <= dominio.y1) {
    ctx.setLineDash([5, 5]);
    ctx.strokeStyle = "#94A3B8";
    ctx.beginPath();
    ctx.moveTo(meio_x, area.y0);
    ctx.lineTo(meio_x, area.y1);
    ctx.moveTo(area.x0, meio_y);
    ctx.lineTo(area.x1, meio_y);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Esferas no padrão da figura: preenchimento translúcido, contorno na cor
  // do quadrante e selo numerado do lado de fora.
  const esferas = [];
  for (const ponto of dados.pontos) {
    const sx = escalaDiagramaX(ponto.x);
    const sy = escalaDiagramaY(ponto.y);
    const raio = raioDiagrama(ponto);
    if (sx + raio < area.x0 || sx - raio > area.x1 ||
        sy + raio < area.y0 || sy - raio > area.y1) continue;
    esferas.push({ ponto, sx, sy, raio, cor: corDoQuadrante(ponto.quadrante) });
  }
  esferas.sort((a, b) => b.raio - a.raio);

  for (const esfera of esferas) {
    const ativo = esfera.ponto === diagramaUI.selecionado;
    const apontado = esfera.ponto === diagramaUI.sobre;
    ctx.beginPath();
    ctx.arc(esfera.sx, esfera.sy, esfera.raio, 0, Math.PI * 2);
    ctx.fillStyle = comAlfa(esfera.cor, ativo ? 0.9 : 0.16);
    ctx.fill();
    ctx.lineWidth = ativo || apontado ? 2.2 : 1.4;
    ctx.strokeStyle = esfera.cor;
    ctx.stroke();
  }

  const centro = { x: (area.x0 + area.x1) / 2, y: (area.y0 + area.y1) / 2 };
  const rb = raioSelo();
  const ocupados = esferas.map((e) => [e.sx, e.sy, e.raio]);
  const selos = esferas.slice().sort((a, b) => b.ponto.nos - a.ponto.nos);
  const total = dados.pontos.length;
  // Acima de certo volume, só os maiores recebem selo: o resto se identifica
  // pela dica e pela legenda, que continua listando todos.
  const limiteSelos = total > 400 ? 36 : (total > 250 ? 60
    : (total > 150 ? 90 : (total > 90 ? 120 : 1000)));
  const muitos = total > 250;
  const forcados = [];
  const selosOcupados = [];
  let selosDesenhados = 0;

  for (const esfera of selos) {
    const emFoco = esfera.ponto === diagramaUI.sobre ||
      esfera.ponto === diagramaUI.selecionado;
    if (!emFoco && selosDesenhados >= limiteSelos) continue;
    if (muitos && esfera.ponto.nos < 2 && !emFoco) continue;
    let ux = esfera.sx - centro.x;
    let uy = centro.y - esfera.sy;
    const norma = Math.hypot(ux, uy) || 1;
    ux /= norma;
    uy /= norma;
    const direcoes = [[ux, uy], [-uy, ux], [uy, -ux], [-ux, -uy],
                      [0, -1], [1, 0], [0, 1], [-1, 0]];
    let escolhido = null;
    for (const [dx, dy] of direcoes) {
      const distancia = esfera.raio + rb + 1;
      let bx = esfera.sx + dx * distancia;
      let by = esfera.sy + dy * distancia;
      bx = Math.min(Math.max(bx, area.x0 + rb + 1), area.x1 - rb - 1);
      by = Math.min(Math.max(by, area.y0 + rb + 1), area.y1 - rb - 1);
      const colide = ocupados.some((outro) =>
        Math.hypot(bx - outro[0], by - outro[1]) < rb + outro[2] - 1);
      if (!colide) {
        escolhido = [bx, by];
        break;
      }
    }
    if (!escolhido) continue;
    ocupados.push([escolhido[0], escolhido[1], rb]);
    selosOcupados.push([escolhido[0], escolhido[1], rb]);
    if (esfera.ponto === diagramaUI.sobre ||
        esfera.ponto === diagramaUI.selecionado) {
      forcados.push({ esfera, x: escolhido[0], y: escolhido[1] });
      continue;
    }
    selosDesenhados += 1;
    desenharSelo(ctx, escolhido[0], escolhido[1], rb, esfera.cor,
                 esfera.ponto.selo);
  }

  // O agrupamento em foco sempre mostra o selo, mesmo sobre outro.
  for (const { esfera, x, y } of forcados) {
    desenharSelo(ctx, x, y, rb + 1, esfera.cor, esfera.ponto.selo);
  }
  diagramaUI.selos = selosOcupados;

  const modo = diagramaUI.rotulos;
  if (modo !== "nenhum") {
    desenharNomesDiagrama(ctx, dados, area);
  }

  ctx.restore();

  // Moldura e eixos: fixos, fora do alcance do zoom.
  ctx.strokeStyle = "#E2E8F0";
  ctx.lineWidth = 1;
  ctx.strokeRect(area.x0 + 0.5, area.y0 + 0.5,
                 area.x1 - area.x0 - 1, area.y1 - area.y0 - 1);

  ctx.font = "500 10.5px Inter, Arial, sans-serif";
  ctx.fillStyle = "#64748B";
  ctx.textAlign = "center";
  ctx.textBaseline = "bottom";
  ctx.fillText(dados.eixos.x, (area.x0 + area.x1) / 2, altura - 9);
  ctx.save();
  ctx.translate(13, (area.y0 + area.y1) / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(dados.eixos.y, 0, 0);
  ctx.restore();
}

function desenharSelo(ctx, x, y, raio, cor, selo) {
  ctx.beginPath();
  ctx.arc(x, y, raio, 0, Math.PI * 2);
  ctx.fillStyle = "#FFFFFF";
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = cor;
  ctx.stroke();
  ctx.font = `700 ${Math.max(7.5, raio * 0.95).toFixed(1)}px Inter, Arial, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = cor;
  ctx.fillText(String(selo), x, y + 0.5);
}

function desenharNomesDiagrama(ctx, dados, area) {
  const modo = diagramaUI.rotulos;
  let limite = modo === "todos" ? 120 : 12;
  const forcados = [diagramaUI.sobre, diagramaUI.selecionado].filter(Boolean);
  const candidatos = [];
  for (const ponto of forcados) candidatos.push(ponto);
  for (const ponto of dados.pontos.slice().sort((a, b) => b.nos - a.nos)) {
    if (!candidatos.includes(ponto)) candidatos.push(ponto);
  }
  limite = Math.max(limite, forcados.length);

  ctx.font = "600 11px Inter, Arial, sans-serif";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";
  const selos = diagramaUI.selos || [];
  const ocupados = [];
  let desenhados = 0;
  for (const ponto of candidatos) {
    if (desenhados >= limite) break;
    const sx = escalaDiagramaX(ponto.x);
    const sy = escalaDiagramaY(ponto.y);
    if (sx < area.x0 - 40 || sx > area.x1 + 40 ||
        sy < area.y0 - 40 || sy > area.y1 + 40) continue;
    const raio = raioDiagrama(ponto);
    const limite_texto = dados.pontos.length > 25 ? 24 : 34;
    const texto = ponto.nome.length > limite_texto
      ? `${ponto.nome.slice(0, limite_texto - 3)}…` : ponto.nome;
    const largura_texto = ctx.measureText(texto).width;
    const opcoes = [
      { x: sx + raio + 7, y: sy, alinhamento: "left" },
      { x: sx - raio - 7, y: sy, alinhamento: "right" },
      { x: sx, y: sy - raio - 7, alinhamento: "center" },
      { x: sx, y: sy + raio + 7, alinhamento: "center" },
    ];
    let escolhida = null;
    for (const opcao of opcoes) {
      const esquerda = opcao.alinhamento === "left" ? opcao.x :
        (opcao.alinhamento === "right" ? opcao.x - largura_texto
          : opcao.x - largura_texto / 2);
      const caixa = [esquerda, opcao.y - 8, largura_texto, 16];
      if (caixa[0] < area.x0 + 2 || caixa[0] + caixa[2] > area.x1 - 2) continue;
      if (caixa[1] < area.y0 + 2 || caixa[1] + caixa[3] > area.y1 - 2) continue;
      if (colideCaixa(caixa, ocupados)) continue;
      const cobre_selo = selos.some((selo) => colideCaixa(
        caixa, [[selo[0] - selo[2], selo[1] - selo[2],
                 selo[2] * 2, selo[2] * 2]]));
      if (cobre_selo) continue;
      const cobre = dados.pontos.some((outro) => {
        if (outro === ponto) return false;
        const ox = escalaDiagramaX(outro.x);
        const oy = escalaDiagramaY(outro.y);
        const or = raioDiagrama(outro);
        return colideCaixa(caixa, [[ox - or, oy - or, or * 2, or * 2]]);
      });
      if (cobre) continue;
      escolhida = { ...opcao, caixa };
      break;
    }
    const forcado = ponto === diagramaUI.sobre || ponto === diagramaUI.selecionado;
    if (!escolhida && forcado) {
      const esquerda = sx + raio + 7;
      escolhida = { x: esquerda, y: sy, alinhamento: "left",
                    caixa: [esquerda, sy - 8, largura_texto, 16] };
    }
    if (!escolhida) continue;
    ocupados.push(escolhida.caixa);
    desenhados += 1;

    let ancora = null;
    let origem = null;
    if (escolhida.alinhamento === "left") {
      ancora = [escolhida.x - 2, escolhida.y];
      origem = [sx + raio + 1, sy];
    } else if (escolhida.alinhamento === "right") {
      ancora = [escolhida.x + 2, escolhida.y];
      origem = [sx - raio - 1, sy];
    } else {
      const acima = escolhida.caixa[1] + escolhida.caixa[3] / 2 < sy;
      ancora = [escolhida.x,
                acima ? escolhida.caixa[1] + escolhida.caixa[3] - 3
                  : escolhida.caixa[1] + 3];
      origem = [sx, sy + (acima ? -raio - 1 : raio + 1)];
    }
    if (ancora && Math.hypot(ancora[0] - origem[0],
                             ancora[1] - origem[1]) > 14) {
      ctx.strokeStyle = "rgba(100, 116, 139, 0.45)";
      ctx.lineWidth = 0.9;
      ctx.beginPath();
      ctx.moveTo(origem[0], origem[1]);
      ctx.lineTo(ancora[0], ancora[1]);
      ctx.stroke();
    }

    ctx.textAlign = escolhida.alinhamento;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.94)";
    ctx.lineWidth = 3.4;
    ctx.strokeText(texto, escolhida.x, escolhida.y);
    ctx.fillStyle = forcado ? "#0B1F66" : "#33415C";
    ctx.fillText(texto, escolhida.x, escolhida.y);
  }
}

function pontoNoDiagrama(x, y) {
  const dados = diagramaUI.dados;
  if (!dados) return null;
  const area = diagramaUI.area;
  if (x < area.x0 || x > area.x1 || y < area.y0 || y > area.y1) return null;
  let melhor = null;
  let menor = Infinity;
  for (const ponto of dados.pontos) {
    const raio = Math.max(raioDiagrama(ponto), 9);
    const distancia = Math.hypot(escalaDiagramaX(ponto.x) - x,
                                 escalaDiagramaY(ponto.y) - y);
    if (distancia <= raio + 3 && distancia < menor) {
      menor = distancia;
      melhor = ponto;
    }
  }
  return melhor;
}

function dicaDoDiagrama(ponto) {
  const dica = $("dicaDiagrama");
  if (!ponto) {
    dica.hidden = true;
    return;
  }
  dica.replaceChildren();
  const titulo = document.createElement("b");
  titulo.textContent = `${ponto.selo} · ${ponto.nome}`;
  const linha = document.createElement("div");
  linha.textContent =
    `${nf.format(ponto.nos)} nós · ${nf.format(ponto.documentos)} documentos`;
  const medidas = document.createElement("div");
  medidas.textContent =
    `centralidade ${nf.format(ponto.centralidade)} · ` +
    `densidade ${nf.format(ponto.densidade)}`;
  const quadrante = document.createElement("span");
  quadrante.textContent = rotuloDoQuadrante(ponto.quadrante);
  dica.append(titulo, linha, medidas, quadrante);
  dica.hidden = false;
}

function posicionarDica(dica, evento) {
  const caixa = $("caixaEstrategico").getBoundingClientRect();
  const x = evento.clientX - caixa.left;
  const y = evento.clientY - caixa.top;
  const largura = dica.offsetWidth || 220;
  const para_esquerda = x + largura + 24 > caixa.width;
  dica.style.left = `${x}px`;
  dica.style.top = `${y}px`;
  dica.style.transform = para_esquerda
    ? "translate(-100%, -100%) translate(-8px, -2px)"
    : "translate(12px, -100%)";
}

function aplicarZoomDiagrama(fator, cx, cy) {
  const area = diagramaUI.area;
  const dominio = diagramaUI.dominio;
  const limites = diagramaUI.limites;
  const px = cx === undefined ? (area.x0 + area.x1) / 2 : cx;
  const py = cy === undefined ? (area.y0 + area.y1) / 2 : cy;
  const alvo_x = valorDiagramaX(px);
  const alvo_y = valorDiagramaY(py);
  const largura = dominio.x1 - dominio.x0;
  const altura = dominio.y1 - dominio.y0;
  const nova_largura = Math.min(limites.x1 - limites.x0,
                                Math.max(0.04, largura / fator));
  const nova_altura = Math.min(limites.y1 - limites.y0,
                               Math.max(0.04, altura / fator));
  let x0 = alvo_x - (alvo_x - dominio.x0) * (nova_largura / largura);
  let y0 = alvo_y - (alvo_y - dominio.y0) * (nova_altura / altura);
  x0 = Math.min(Math.max(x0, limites.x0), limites.x1 - nova_largura);
  y0 = Math.min(Math.max(y0, limites.y0), limites.y1 - nova_altura);
  diagramaUI.dominio = { x0, x1: x0 + nova_largura,
                         y0, y1: y0 + nova_altura };
  desenharDiagrama();
}

function zoomDiagrama(acao) {
  if (acao === "reset") {
    diagramaUI.dominio = { ...diagramaUI.limites };
    desenharDiagrama();
  } else {
    aplicarZoomDiagrama(acao === "mais" ? 1.4 : 1 / 1.4);
  }
}

/* ------------------------------------------------------ legenda adaptável */

function montarLegendaDiagrama() {
  const dados = diagramaUI.dados;
  if (!dados) {
    $("legendaDiagrama").hidden = true;
    return;
  }
  const pontos = dados.pontos.slice().sort((a, b) => a.selo - b.selo);
  const fragmento = document.createDocumentFragment();
  for (const ponto of pontos) {
    const item = document.createElement("span");
    item.className = "legenda-item";
    item.title = `${ponto.nome} · ${nf.format(ponto.nos)} nós · ` +
      rotuloDoQuadrante(ponto.quadrante);
    const selo = document.createElement("span");
    selo.className = "legenda-selo";
    selo.style.color = corDoQuadrante(ponto.quadrante);
    selo.textContent = String(ponto.selo);
    const nome = document.createElement("span");
    nome.className = "legenda-nome";
    nome.textContent = ponto.nome;
    const nos = document.createElement("span");
    nos.className = "legenda-nos";
    nos.textContent = `(${nf.format(ponto.nos)})`;
    item.append(selo, nome, nos);
    fragmento.append(item);
  }
  $("legendaLista").replaceChildren(fragmento);
  $("legendaQtd").textContent =
    `${nf.format(pontos.length)} ${pontos.length === 1
      ? "agrupamento" : "agrupamentos"}`;
  $("legendaDiagrama").hidden = false;
  alternarLegenda(pontos.length <= 24);
}

function alternarLegenda(abrir) {
  const lista = $("legendaLista");
  const botao = $("alternarLegenda");
  if (!lista || !botao) return;
  lista.hidden = !abrir;
  botao.setAttribute("aria-expanded", abrir ? "true" : "false");
  botao.querySelector(".legenda-sinal").textContent = abrir ? "−" : "+";
}

function ligarDiagrama() {
  const canvas = $("canvasEstrategico");
  if (!canvas) return;

  const dentroDaArea = (x, y) => {
    const a = diagramaUI.area;
    return x >= a.x0 && x <= a.x1 && y >= a.y0 && y <= a.y1;
  };

  $("alternarLegenda").addEventListener("click", () => {
    alternarLegenda($("legendaLista").hidden);
  });

  canvas.addEventListener("pointerdown", (evento) => {
    if (!diagramaUI.dados || evento.button !== 0) return;
    const retangulo = canvas.getBoundingClientRect();
    if (!dentroDaArea(evento.clientX - retangulo.left,
                      evento.clientY - retangulo.top)) return;
    diagramaUI.arrastando = true;
    diagramaUI.moveu = false;
    diagramaUI.inicio = { x: evento.clientX, y: evento.clientY,
                          dominio: { ...diagramaUI.dominio } };
    canvas.classList.add("arrastando");
    try { canvas.setPointerCapture(evento.pointerId); } catch (_) { /* sintético */ }
  });

  canvas.addEventListener("pointermove", (evento) => {
    if (!diagramaUI.dados) return;
    const retangulo = canvas.getBoundingClientRect();
    const x = evento.clientX - retangulo.left;
    const y = evento.clientY - retangulo.top;
    if (diagramaUI.arrastando) {
      const area = diagramaUI.area;
      const inicio = diagramaUI.inicio;
      const largura = diagramaUI.dominio.x1 - diagramaUI.dominio.x0;
      const altura = diagramaUI.dominio.y1 - diagramaUI.dominio.y0;
      const dx = -(x - (inicio.x - retangulo.left)) /
        (area.x1 - area.x0) * largura;
      const dy = (y - (inicio.y - retangulo.top)) /
        (area.y1 - area.y0) * altura;
      if (Math.hypot(x - (inicio.x - retangulo.left),
                     y - (inicio.y - retangulo.top)) > 3) {
        diagramaUI.moveu = true;
      }
      const limites = diagramaUI.limites;
      let x0 = inicio.dominio.x0 + dx;
      let y0 = inicio.dominio.y0 + dy;
      x0 = Math.min(Math.max(x0, limites.x0), limites.x1 - largura);
      y0 = Math.min(Math.max(y0, limites.y0), limites.y1 - altura);
      diagramaUI.dominio = { x0, x1: x0 + largura, y0, y1: y0 + altura };
      desenharDiagrama();
      return;
    }
    if (!dentroDaArea(x, y)) {
      if (diagramaUI.sobre) {
        diagramaUI.sobre = null;
        $("dicaDiagrama").hidden = true;
        desenharDiagrama();
      }
      canvas.style.cursor = "grab";
      return;
    }
    const ponto = pontoNoDiagrama(x, y);
    if (ponto !== diagramaUI.sobre) {
      diagramaUI.sobre = ponto;
      dicaDoDiagrama(ponto);
      desenharDiagrama();
    }
    if (ponto) posicionarDica($("dicaDiagrama"), evento);
    canvas.style.cursor = ponto ? "pointer" : "grab";
  });

  const soltar = (evento) => {
    if (!diagramaUI.arrastando) return;
    diagramaUI.arrastando = false;
    canvas.classList.remove("arrastando");
    if (diagramaUI.moveu) return;
    const retangulo = canvas.getBoundingClientRect();
    const x = evento.clientX - retangulo.left;
    const y = evento.clientY - retangulo.top;
    if (!dentroDaArea(x, y)) return;
    const ponto = pontoNoDiagrama(x, y);
    diagramaUI.selecionado = ponto === diagramaUI.selecionado ? null : ponto;
    diagramaUI.sobre = ponto;
    dicaDoDiagrama(ponto);
    desenharDiagrama();
    if (ponto) abrirGrupo(ponto.selo);
  };
  canvas.addEventListener("pointerup", soltar);
  canvas.addEventListener("pointercancel", soltar);
  canvas.addEventListener("pointerleave", () => {
    if (diagramaUI.arrastando) return;
    diagramaUI.sobre = null;
    $("dicaDiagrama").hidden = true;
    desenharDiagrama();
  });

  canvas.addEventListener("wheel", (evento) => {
    if (!diagramaUI.dados) return;
    const retangulo = canvas.getBoundingClientRect();
    const x = evento.clientX - retangulo.left;
    const y = evento.clientY - retangulo.top;
    if (!dentroDaArea(x, y)) return;
    evento.preventDefault();
    aplicarZoomDiagrama(Math.exp(-evento.deltaY * 0.0015), x, y);
  }, { passive: false });

  canvas.addEventListener("dblclick", () => zoomDiagrama("reset"));

  let agendado = 0;
  const reajustar = () => {
    if (!diagramaUI.dados) return;
    ajustarCanvasDiagrama();
    desenharDiagrama();
  };
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(() => {
      if (agendado) return;
      agendado = requestAnimationFrame(() => { agendado = 0; reajustar(); });
    }).observe($("caixaEstrategico"));
  }
  window.addEventListener("resize", reajustar);
}
