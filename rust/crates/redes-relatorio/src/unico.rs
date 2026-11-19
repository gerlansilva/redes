//! Relatório completo em arquivo único (porta de `relatorio_unico.py`).
//!
//! Um .html autocontido (CSS e SVG embutidos, sem JavaScript), pensado para ler,
//! citar e imprimir ou salvar em PDF. A numeração é contínua, no estilo de artigo:
//! seções "4", subseções "4.2", "Figura 6 — …" e "Tabela 3 — …".

use std::collections::HashSet;
use std::path::Path;

use crate::css::{CSS_PASTA, CSS_UNICO_EXTRA};
use crate::dados::*;
use crate::metodo::{self, rotulo_medida};
use crate::svg;
use crate::texto::*;

/// Acima disso, as redes de agrupamento ficam só nos maiores grupos de cada período.
pub const LIMITE_BYTES: usize = 15 * 1024 * 1024;
const LIMITES_REDES: [Option<usize>; 4] = [None, Some(12), Some(6), Some(3)];

/// Numeração contínua e sumário do documento em construção.
#[derive(Default)]
pub struct Doc {
    pub figuras: usize,
    pub tabelas: usize,
    /// (nível, âncora, texto)
    pub sumario: Vec<(u8, String, String)>,
    ancoras: HashSet<String>,
}

impl Doc {
    pub fn ancora(&mut self, base: &str) -> String {
        let (mut nome, mut i) = (base.to_string(), 2);
        while self.ancoras.contains(&nome) {
            nome = format!("{base}-{i}");
            i += 1;
        }
        self.ancoras.insert(nome.clone());
        nome
    }

    pub fn cabecalho(&mut self, nivel: u8, numero: &str, texto: &str, base: &str, no_sumario: bool) -> String {
        let id = self.ancora(base);
        let titulo = if numero.is_empty() { texto.to_string() } else { format!("{numero} {texto}") };
        if no_sumario {
            self.sumario.push((nivel, id.clone(), titulo.clone()));
        }
        format!("<h{nivel} id=\"{id}\">{}</h{nivel}>", esc(&titulo))
    }

    pub fn figura(&mut self, svg: &str, legenda: &str) -> String {
        self.figuras += 1;
        let id = self.ancora(&format!("fig-{}", self.figuras));
        let svg = prefixa_ids(svg, &id);
        format!("<figure id=\"{id}\">{svg}<figcaption>Figura {} — {}</figcaption></figure>", self.figuras, esc(legenda))
    }
}

impl Numerador for Doc {
    fn tabela(&mut self, cabecalho: &[String], linhas: &[Vec<String>], legenda: &str, numericas: &[usize], larga: bool) -> String {
        self.tabelas += 1;
        let id = self.ancora(&format!("tab-{}", self.tabelas));
        let html = tabela_html(cabecalho, linhas, Some(&format!("Tabela {} — {legenda}", self.tabelas)), numericas, &[]);
        let marca = format!(" id=\"{id}\"{}", if larga { " class=\"larga\"" } else { "" });
        let html = html.replacen("<table>", &format!("<table{marca}>"), 1);
        if larga {
            format!("<div class=\"rolagem\">{html}</div>")
        } else {
            html
        }
    }
}

/// Prefixa os ids do SVG (e suas referências) para evitar colisões no documento.
pub fn prefixa_ids(svg: &str, prefixo: &str) -> String {
    let mut ids: Vec<String> = Vec::new();
    let b = svg.as_bytes();
    let padrao = "id=\"";
    let mut i = 0;
    while let Some(p) = svg[i..].find(padrao) {
        let ini = i + p;
        // precisa vir depois de espaço em branco (não `data-id=`, `grid=`)
        let ok = ini > 0 && (b[ini - 1] as char).is_whitespace();
        let fim_valor = svg[ini + padrao.len()..].find('"').map(|x| ini + padrao.len() + x);
        match fim_valor {
            Some(f) => {
                if ok {
                    let v = &svg[ini + padrao.len()..f];
                    if !v.is_empty() && !ids.iter().any(|x| x == v) {
                        ids.push(v.to_string());
                    }
                }
                i = f + 1;
            }
            None => break,
        }
    }
    if ids.is_empty() {
        return svg.to_string();
    }
    let mut ordenados = ids.clone();
    ordenados.sort_by_key(|x| std::cmp::Reverse(x.len()));
    let mut out = svg.to_string();
    for id in &ordenados {
        let novo = format!("{prefixo}-{id}");
        out = out.replace(&format!("id=\"{id}\""), &format!("id=\"{novo}\""));
        out = out.replace(&format!("url(#{id})"), &format!("url(#{novo})"));
        out = out.replace(&format!("href=\"#{id}\""), &format!("href=\"#{novo}\""));
    }
    // aria-labelledby / aria-describedby: listas de ids
    for attr in ["aria-labelledby", "aria-describedby"] {
        let marca = format!("{attr}=\"");
        let mut resultado = String::new();
        let mut resto = out.as_str();
        while let Some(p) = resto.find(&marca) {
            resultado.push_str(&resto[..p + marca.len()]);
            let apos = &resto[p + marca.len()..];
            match apos.find('"') {
                Some(f) => {
                    let lista: Vec<String> = apos[..f].split_whitespace().map(|x| if ids.iter().any(|i| i == x) { format!("{prefixo}-{x}") } else { x.to_string() }).collect();
                    resultado.push_str(&lista.join(" "));
                    resto = &apos[f..];
                }
                None => {
                    resto = apos;
                    break;
                }
            }
        }
        resultado.push_str(resto);
        out = resultado;
    }
    out
}

/// Renderiza blocos livres no documento.
fn blocos_html(doc: &mut Doc, blocos: &[Bloco], classe_nota: &str) -> String {
    let mut v = Vec::new();
    for b in blocos {
        v.push(match b {
            Bloco::Html { html } => html.clone(),
            Bloco::Nota { texto } => format!("<p class=\"{classe_nota}\">{}</p>", esc(texto)),
            Bloco::Fonte { texto } => format!("<p class=\"fonte\">{}</p>", esc(texto)),
            Bloco::Subtitulo { texto } => format!("<h5>{}</h5>", esc(texto)),
            Bloco::Figura { svg, legenda } => doc.figura(svg, legenda),
            Bloco::Tabela { cabecalho, linhas, legenda, numericas, larga } => doc.tabela(cabecalho, linhas, legenda, numericas, *larga),
            Bloco::Lista { itens } => format!("<ul>{}</ul>", itens.iter().map(|i| format!("<li>{}</li>", esc(i))).collect::<String>()),
        });
    }
    v.join("\n")
}

fn logo_capa() -> String {
    let svg = crate::LOGO_SVG;
    let ini = svg.find("<svg").unwrap_or(0);
    svg[ini..].replacen("<svg ", "<svg class=\"logo-capa\" ", 1)
}

fn visao_geral_html(doc: &mut Doc, v: &VisaoGeral) -> String {
    let mut corpo: Vec<String> = Vec::new();
    if !v.lacunas.is_empty() {
        corpo.push(format!(
            "<div class=\"aviso\"><b>O que falta neste corpus</b><ul>{}</ul></div>",
            v.lacunas.iter().map(|t| format!("<li>{}</li>", esc(t))).collect::<String>()
        ));
    }
    if !v.cartoes.is_empty() {
        let linhas: Vec<Vec<String>> = v.cartoes.iter().map(|l| l.iter().map(|c| esc(c)).collect()).collect();
        corpo.push(doc.tabela(&strings(&["Indicador", "Valor", "Observação"]), &linhas, "Informações principais", &[1], false));
    }
    let mut k = 0;
    for s in &v.subsecoes {
        k += 1;
        corpo.push(doc.cabecalho(3, &format!("1.{k}"), &s.titulo, &format!("vg-{k}"), true));
        let mut j = 0;
        for b in &s.blocos {
            match b {
                Bloco::Subtitulo { texto } => {
                    j += 1;
                    corpo.push(doc.cabecalho(4, &format!("1.{k}.{j}"), texto, &format!("vg-{k}-{j}"), false));
                }
                outro => corpo.push(blocos_html(doc, std::slice::from_ref(outro), "fonte")),
            }
        }
    }
    if !v.sem_metodo {
        k += 1;
        corpo.push(doc.cabecalho(3, &format!("1.{k}"), "Método e parâmetros", &format!("vg-{k}"), true));
        corpo.push(metodo::metodo_bibliometria_html(doc, v.parametros.as_deref()));
    }
    corpo.into_iter().filter(|c| !c.is_empty()).collect::<Vec<_>>().join("\n")
}

/// Figura gerada a partir da rede quando o dado não trouxe uma pronta.
pub fn diagrama_do_periodo(p: &PeriodoRel, config: &ConfigRel) -> Option<String> {
    if let Some(s) = &p.diagrama_svg {
        return Some(s.clone());
    }
    let mapeador = config.mapeador_principal();
    svg::diagrama_svg(p, &config.unidade, &format!("Diagrama estratégico — {}", p.nome), Some(&format!("{mapeador}:documentos")), Some(rotulo_medida("documentos")))
}

pub fn halo_do_periodo(p: &PeriodoRel, config: &ConfigRel) -> Option<String> {
    if let Some(s) = &p.halo_svg {
        return Some(s.clone());
    }
    let pivos: Vec<i64> = p.pivos.as_ref().map(|d| d.itens.iter().map(|i| i.no).collect()).unwrap_or_default();
    svg::halo_svg(p, &config.unidade, &config.matriz, &format!("Rede do período — {}", p.nome), &pivos)
}

pub fn rede_do_grupo(p: &PeriodoRel, indice: usize) -> Option<String> {
    if let Some(Some(s)) = p.redes_grupos.get(indice) {
        return Some(s.clone());
    }
    let g = p.grupos.get(indice)?;
    svg::rede_agrupamento_svg(p, g, &format!("{} — {}", p.nome, g.nome_exibicao()))
}

/// HTML de uma análise. Devolve também quantas redes de agrupamento foram omitidas.
fn bloco_analise(doc: &mut Doc, secao: &SecaoAnalise, numero: usize, medida_temporal: &str, limite: Option<usize>, n_periodos_projeto: usize) -> (String, usize) {
    let mut omitidas = 0;
    let rotulo = &secao.rotulo;
    let rotulo_min = rotulo.to_lowercase();
    let resultados = &secao.periodos;
    let config = &secao.config;
    let mut partes: Vec<String> = vec![doc.cabecalho(2, &numero.to_string(), rotulo, &format!("s{numero}"), true), format!("<p>{}</p>", esc(&secao.descricao))];

    // X.1 Parâmetros e método
    partes.push(doc.cabecalho(3, &format!("{numero}.1"), "Parâmetros e método", &format!("s{numero}-parametros"), true));
    let mt = secao.medida_temporal.as_deref().unwrap_or(medida_temporal);
    let com_duplo = secao.extras.iter().any(|e| e.tipo == TipoExtra::DuploMapa);
    let com_sim = secao.extras.iter().any(|e| e.tipo == TipoExtra::Similitude);
    let metodo_final = metodo_com_doc(doc, config, n_periodos_projeto.max(resultados.len()), resultados, secao, mt, &rotulo_min, numero, com_duplo, com_sim);
    partes.push(metodo_final);

    // X.2 Por período
    partes.push(doc.cabecalho(3, &format!("{numero}.2"), "Por período", &format!("s{numero}-periodos"), true));
    let mut linhas = Vec::new();
    for r in resultados {
        let maior = r.grupos.iter().max_by(|a, b| a.itens().cmp(&b.itens()).then_with(|| a.rotulo.cmp(&b.rotulo)));
        let celula = match maior {
            Some(g) => {
                let (principal, sub, _) = metodo::nome_do_grupo(g);
                let mut c = format!("{} ({} itens)", esc(&principal), g.itens());
                if let Some(s) = sub {
                    c.push_str(&format!("<br><span class=\"rot-atual\">{}</span>", esc(&s)));
                }
                c
            }
            None => "—".into(),
        };
        linhas.push(vec![esc(&r.nome), inteiro(r.itens), r.grupos.len().to_string(), celula]);
    }
    partes.push(doc.tabela(&strings(&["Período", "Itens", "Grupos", "Maior grupo"]), &linhas, &format!("Resumo por período — {rotulo}."), &[1, 2], false));
    if config.unidade == "Institutions" {
        if let Some(p0) = resultados.first() {
            if p0.ies.is_some() {
                partes.push(metodo::ies_html(p0, doc, &rotulo_min));
            }
        }
    } else if matches!(config.unidade.as_str(), "Authors" | "Countries") {
        if let Some(p0) = resultados.first() {
            partes.push(metodo::filtro_agrupamento_html(p0, &config.unidade));
        }
    }

    // X.3 Períodos
    partes.push(doc.cabecalho(3, &format!("{numero}.3"), "Resultados de cada período", &format!("s{numero}-resultados"), true));
    let mapeador = config.mapeador_principal().to_string();
    for (indice, r) in resultados.iter().enumerate() {
        partes.push(doc.cabecalho(4, &format!("{numero}.3.{}", indice + 1), &r.nome, &format!("s{numero}-p{indice}"), true));
        let ordem = metodo::ordem_grupos(r);
        if ordem.is_empty() {
            partes.push(
                "<p class=\"nota\">Nenhum agrupamento se formou neste período com os parâmetros usados; por isso não há diagrama \
                 estratégico, rede nem tabela de agrupamentos para ele.</p>"
                    .into(),
            );
            continue;
        }
        partes.push(format!(
            "<p>{} documentos, {} itens e {} {}.</p>",
            inteiro(r.documentos),
            inteiro(r.itens),
            ordem.len(),
            if ordem.len() == 1 { "agrupamento" } else { "agrupamentos" }
        ));
        match diagrama_do_periodo(r, config) {
            Some(s) => partes.push(doc.figura(
                &s,
                &format!(
                    "Diagrama estratégico — {rotulo_min}, {}. O tamanho das esferas segue o número de documentos; o quadrante usa a \
                     centralidade e a densidade de Callon.",
                    r.nome
                ),
            )),
            None => partes.push("<p class=\"nota\">O diagrama estratégico não pôde ser desenhado para este período.</p>".into()),
        }
        if let Some(s) = halo_do_periodo(r, config) {
            let mut leg = format!("Rede do período — {rotulo_min}, {}.", r.nome);
            if s.contains("ponto de virada") {
                leg.push_str(" Os anéis numerados são os pontos de virada da tabela seguinte.");
            }
            partes.push(doc.figura(&s, &leg));
        }
        let tabela_pivos = metodo::pivos_html(r, doc, &format!("Pontos de virada de {rotulo_min}, {}.", r.nome), "nota");
        if !tabela_pivos.is_empty() {
            partes.push(doc.cabecalho(5, &format!("{numero}.3.{}.1", indice + 1), "Pontos de virada", &format!("s{numero}-p{indice}-pivos"), false));
            partes.push(tabela_pivos);
        }

        let prefixo = format!("{mapeador}:");
        let medidas: Vec<(String, String)> = crate::dados::ORDEM_MEDIDAS.iter().map(|m| (format!("{prefixo}{m}"), rotulo_medida(m).to_string())).collect();
        let grupos_ord: Vec<&GrupoRel> = ordem.iter().map(|&i| &r.grupos[i]).collect();
        let (cab, lin, num) = metodo::tabela_agrupamentos(&grupos_ord, &medidas, &n, None);
        partes.push(doc.tabela(&cab, &lin, &format!("Agrupamentos de {rotulo_min}, {}.", r.nome), &num, true));
        partes.push(
            "<p class=\"nota\">Silhueta: coesão média dos itens do agrupamento (de −1 a 1; “—” quando há poucos itens). Ano médio: \
             dos documentos do núcleo. Rótulo em destaque: termos distintivos do período; abaixo, o nome do item central.</p>"
                .into(),
        );

        let mostrados: Vec<usize> = match limite {
            None => ordem.clone(),
            Some(l) => ordem.iter().take(l).cloned().collect(),
        };
        if mostrados.len() < ordem.len() {
            omitidas += ordem.len() - mostrados.len();
            partes.push(format!(
                "<p class=\"nota\">Para manter o arquivo leve, as redes foram incluídas apenas para os {} maiores agrupamentos (de \
                 {}); as métricas de todos estão na tabela acima.</p>",
                mostrados.len(),
                ordem.len()
            ));
        }
        let mut figuras = Vec::new();
        for (posicao, &gi) in mostrados.iter().enumerate() {
            let g = &r.grupos[gi];
            let (principal, sub, _) = metodo::nome_do_grupo(g);
            if let Some(s) = rede_do_grupo(r, gi) {
                let mut nome = format!("“{principal}”");
                if let Some(sub) = sub {
                    nome.push_str(&format!(" (atual: “{sub}”)"));
                }
                figuras.push(doc.figura(&s, &format!("Rede do agrupamento {}, {nome}, {}.", posicao + 1, r.nome)));
            }
        }
        if !figuras.is_empty() {
            partes.push(format!("<div class=\"redes-grupos\">{}</div>", figuras.join("")));
        }
    }

    // X.4+ extras (evolução, linha do tempo, densidade, duplo mapa, similitude)
    let mut subsecao = 4;
    let evolui = resultados.len() >= 2 && config.matriz == "CoOccurrence";
    if evolui {
        partes.push(doc.cabecalho(3, &format!("{numero}.{subsecao}"), TipoExtra::Evolucao.titulo_padrao(), &format!("s{numero}-evolucao"), true));
        subsecao += 1;
        match secao.extras.iter().find(|e| e.tipo == TipoExtra::Evolucao).filter(|e| !e.blocos.is_empty()) {
            Some(e) => partes.push(blocos_html(doc, &e.blocos, "nota")),
            None => partes.push("<p class=\"nota\">Os mapas de evolução e sobreposição não puderam ser construídos.</p>".into()),
        }
    }
    for e in secao.extras.iter().filter(|e| e.tipo != TipoExtra::Evolucao && !e.blocos.is_empty()) {
        let titulo = e.titulo.as_deref().unwrap_or(e.tipo.titulo_padrao());
        partes.push(doc.cabecalho(3, &format!("{numero}.{subsecao}"), titulo, &format!("s{numero}-{}", e.tipo.ancora()), true));
        partes.push(blocos_html(doc, &e.blocos, "nota"));
        subsecao += 1;
    }
    // X.n Dendrograma
    partes.push(doc.cabecalho(3, &format!("{numero}.{subsecao}"), "Dendrograma (agrupamento hierárquico)", &format!("s{numero}-dendrograma"), true));
    partes.push(
        "<p>Complementa os agrupamentos da rede: junta, passo a passo, os itens mais parecidos (distância = 1 − similaridade; \
         ligação média). Cortar a árvore mais alto dá poucos temas amplos; mais baixo, muitos temas finos. A linha tracejada marca o \
         corte sugerido (maior salto entre fusões); a concordância com os agrupamentos da rede é medida por ARI e NMI (1 = idêntico).</p>"
            .into(),
    );
    for r in resultados {
        if r.dendrograma.is_empty() {
            if r.rede_nos < 3 {
                partes.push("<p class=\"nota\">Poucos itens neste período para um dendrograma (mínimo de 3).</p>".into());
            } else {
                partes.push(format!("<p class=\"nota\">Dendrograma de {} não disponível nesta geração.</p>", esc(&r.nome)));
            }
        } else {
            partes.push(blocos_html(doc, &r.dendrograma, "nota"));
        }
    }
    (partes.join("\n"), omitidas)
}

/// Monta o bloco de método com a numeração real do documento (h4 numerados e tabelas).
#[allow(clippy::too_many_arguments)]
fn metodo_com_doc(doc: &mut Doc, config: &ConfigRel, n_periodos: usize, resultados: &[PeriodoRel], secao: &SecaoAnalise, mt: &str, rotulo_min: &str, numero: usize, com_duplo: bool, com_sim: bool) -> String {
    // "Indicadores" só existe quando há resultados; a numeração segue as chamadas.
    let nomes: Vec<&str> = if resultados.is_empty() { vec!["Parâmetros adotados", "Como funciona"] } else { vec!["Parâmetros adotados", "Indicadores", "Como funciona"] };
    let cabs: Vec<String> = nomes
        .iter()
        .enumerate()
        .map(|(k, t)| doc.cabecalho(4, &format!("{numero}.1.{}", k + 1), t, &format!("s{numero}-metodo-{}", k + 1), false))
        .collect();
    let mut usado = 0usize;
    let mut titulo = |_t: &str| -> String {
        let c = cabs.get(usado).cloned().unwrap_or_default();
        usado += 1;
        c
    };
    metodo::metodo_html(config, Some(n_periodos), resultados, secao.total.as_ref(), secao.frequencia, Some(mt), doc, rotulo_min, &mut titulo, com_duplo, com_sim)
}

fn pagina(doc_titulo: &str, corpo: &str) -> String {
    format!(
        "<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n\
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n\
<title>{}</title>\n<style>{CSS_PASTA}{CSS_UNICO_EXTRA}</style>\n</head>\n<body>\n{corpo}\n\
<footer class=\"fonte\">Gerado por Redes.</footer>\n</body>\n</html>\n",
        esc(doc_titulo)
    )
}

fn monta(dados: &DadosRelatorio, limite: Option<usize>) -> (String, usize) {
    let mut doc = Doc::default();
    let mut omitidas = 0;
    let mut blocos: Vec<String> = Vec::new();
    let medida = if dados.medida_temporal.is_empty() { "EquivalenceIndex" } else { &dados.medida_temporal };
    let mut primeiro = 1;

    if let Some(v) = &dados.visao_geral {
        blocos.push(doc.cabecalho(2, "1", "Visão geral descritiva", "s1", true));
        let corpo = visao_geral_html(&mut doc, v);
        blocos.push(if corpo.is_empty() { "<p class=\"nota\">O corpus não tem documentos.</p>".into() } else { corpo });
        primeiro = 2;
    }
    let n_periodos = dados.projeto.periodos.len();
    for (i, secao) in dados.secoes.iter().enumerate() {
        let (t, n) = bloco_analise(&mut doc, secao, primeiro + i, medida, limite, n_periodos);
        blocos.push(t);
        omitidas += n;
    }
    if !dados.ignoradas.is_empty() {
        let numero = primeiro + dados.secoes.len();
        blocos.push(doc.cabecalho(2, &numero.to_string(), "Análises não geradas", "nao-geradas", true));
        blocos.push(format!(
            "<p>Estas análises não entraram no relatório, pelos motivos abaixo.</p><ul>{}</ul>",
            dados.ignoradas.iter().map(|i| format!("<li><b>{}</b>: {}</li>", esc(&i.rotulo), esc(&i.motivo))).collect::<String>()
        ));
    }

    // Sumário: lista plana, recuada por nível
    let mut sumario = String::from("<nav class=\"sumario\" aria-label=\"Sumário\"><h2 id=\"sumario\">Sumário</h2><ol>");
    for (nivel, id, texto) in &doc.sumario {
        sumario.push_str(&format!("<li class=\"n{nivel}\"><a href=\"#{id}\">{}</a></li>", esc(texto)));
    }
    sumario.push_str("</ol>");
    sumario.push_str(&format!("<p><small>{} figuras e {} tabelas.</small></p></nav>", doc.figuras, doc.tabelas));

    let data = dados.projeto.data.clone().unwrap_or_else(hoje_extenso);
    let mut capa = vec!["<header class=\"capa\">".to_string(), logo_capa(), "<h1>Relatório completo — Redes</h1>".to_string()];
    if !dados.projeto.nome.is_empty() {
        capa.push(format!("<p class=\"projeto\">{}</p>", esc(&dados.projeto.nome)));
    }
    capa.push("<dl>".into());
    capa.push(format!("<dt>Data</dt><dd>{}</dd>", esc(&data)));
    capa.push(format!("<dt>Documentos</dt><dd>{}</dd>", inteiro(dados.projeto.documentos)));
    capa.push(format!("<dt>Períodos</dt><dd>{}: {}</dd>", dados.projeto.periodos.len(), esc(&dados.projeto.periodos.join(", "))));
    capa.push(format!("<dt>Análises</dt><dd>{}</dd>", dados.secoes.len()));
    capa.push("</dl></header>".into());

    let corpo = format!("{}\n{}\n{}", capa.join("\n"), sumario, blocos.join("\n"));
    (pagina("Relatório completo — Redes", &corpo), omitidas)
}

/// HTML do relatório único em memória.
pub fn gera_html_unico(dados: &DadosRelatorio) -> String {
    let mut pagina = String::new();
    for (i, limite) in LIMITES_REDES.iter().enumerate() {
        let (p, _) = monta(dados, *limite);
        pagina = p;
        if pagina.len() <= LIMITE_BYTES || i == LIMITES_REDES.len() - 1 {
            break;
        }
    }
    pagina
}

/// Grava o relatório único num arquivo (cria as pastas) e devolve o caminho.
pub fn gera_arquivo_unico(caminho: &Path, dados: &DadosRelatorio) -> std::io::Result<std::path::PathBuf> {
    if let Some(pai) = caminho.parent() {
        std::fs::create_dir_all(pai)?;
    }
    std::fs::write(caminho, gera_html_unico(dados))?;
    Ok(caminho.to_path_buf())
}
