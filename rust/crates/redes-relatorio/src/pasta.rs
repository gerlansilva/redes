//! Relatório em pasta de páginas (porta de `report.py`): índice, visão geral, uma
//! pasta por análise com páginas de período e de agrupamento.
//!
//! [`paginas`] devolve tudo em memória (caminho relativo -> conteúdo); [`gera_pasta`]
//! grava no disco. As figuras vão em `images/*.svg` e as páginas as referenciam.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use crate::abnt::referencia_abnt;
use crate::css::CSS_PASTA;
use crate::dados::*;
use crate::metodo::{self, ordem_grupos, quadrante_rotulo, rotulo_mapeador_titulo, rotulo_medida};
use crate::svg;
use crate::texto::*;
use crate::unico::{diagrama_do_periodo, halo_do_periodo, rede_do_grupo};
use crate::LOGO_SVG;

type Mapa = BTreeMap<String, String>;

fn pagina(titulo: &str, corpo: &str, profundidade: usize, voltar: Option<&str>) -> String {
    let raiz = "../".repeat(profundidade);
    let mut corpo = corpo.to_string();
    if let Some(v) = voltar {
        corpo = format!("<nav class=\"voltar\"><a href=\"{v}\">← Relatório completo</a></nav>\n{corpo}");
    }
    format!(
        "<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n<title>{}</title>\n<style>{}</style>\n</head>\n<body>\n\
<header class=\"cabecalho\">\n<p class=\"marca-relatorio\">Redes · mapeamento e análise da produção científica</p>\n\
<img class=\"logo-relatorio\" src=\"logo.svg\" alt=\"Redes\">\n</header>\n{}\n<footer class=\"fonte\">Gerado por Redes.</footer>\n</body>\n</html>\n",
        esc(titulo),
        CSS_PASTA,
        corpo
    )
    .replace("src=\"images/", &format!("src=\"{raiz}images/"))
    .replace("src=\"logo.svg\"", &format!("src=\"{raiz}logo.svg\""))
}

fn tab(cab: &[&str], linhas: &[Vec<String>], legenda: Option<&str>, numericas: &[usize], larguras: &[&str]) -> String {
    let c: Vec<String> = cab.iter().map(|s| s.to_string()).collect();
    tabela_html(&c, linhas, legenda, numericas, larguras)
}

fn nome_no(p: &PeriodoRel, id: i64) -> String {
    p.rede.as_ref().and_then(|r| r.nos.iter().find(|n| n.id == id)).map(|n| n.rotulo.clone()).unwrap_or_else(|| id.to_string())
}

/// Ligações do agrupamento: (internas, externas), pelo peso decrescente.
fn ligacoes(p: &PeriodoRel, g: &GrupoRel) -> (Vec<ArestaRel>, Vec<ArestaRel>) {
    let nos: std::collections::HashSet<i64> = g.nos.iter().copied().collect();
    let (mut i, mut e) = (Vec::new(), Vec::new());
    if let Some(r) = &p.rede {
        for a in &r.arestas {
            let (x, y) = (nos.contains(&a.a), nos.contains(&a.b));
            if x && y {
                i.push(a.clone());
            } else if x || y {
                e.push(a.clone());
            }
        }
    }
    let ord = |v: &mut Vec<ArestaRel>| v.sort_by(|a, b| b.peso.partial_cmp(&a.peso).unwrap_or(std::cmp::Ordering::Equal));
    ord(&mut i);
    ord(&mut e);
    (i, e)
}

fn pagina_periodo(saida: &mut Mapa, base: &str, sec: &SecaoAnalise, p: &PeriodoRel, indice: usize, voltar: Option<&str>) {
    let cfg = &sec.config;
    let ordem = ordem_grupos(p);
    let grupos: Vec<&GrupoRel> = ordem.iter().map(|&i| &p.grupos[i]).collect();
    let mapeadores: Vec<String> = if cfg.mapeadores.is_empty() { vec!["nucleo".into()] } else { cfg.mapeadores.clone() };
    let mut corpo: Vec<String> = vec![
        "<p><a href=\"index.html\">Índice</a></p>".into(),
        format!("<h1>Relatório — Redes — {}</h1>", esc(&p.nome)),
        "<h2>Parâmetros do período</h2>".into(),
        tab(
            &["Parâmetro", "Valor"],
            &[
                vec!["Frequência mínima".into(), sec.frequencia.unwrap_or(cfg.minimo_frequencia).to_string()],
                vec!["Coocorrência mínima".into(), numero(cfg.minimo_coocorrencia)],
                vec!["No período".into(), p.documentos.to_string()],
                vec!["Itens".into(), p.itens.to_string()],
                vec!["Agrupamentos".into(), grupos.len().to_string()],
            ],
            None,
            &[],
            &[],
        ),
    ];

    // Imagens do período
    let mut diagramas: Vec<String> = vec!["<h2>Diagramas estratégicos</h2>".into()];
    for m in &mapeadores {
        let rm = rotulo_mapeador_titulo(m);
        let mut linhas = Vec::new();
        for med in ORDEM_MEDIDAS {
            let nome = format!("strategicDiagram-period{indice}-{m}-{med}.svg");
            let titulo = format!("Diagrama estratégico — {} — {} — {}", p.nome, rm, rotulo_medida(med));
            let figura = if *med == "documentos" && *m == cfg.mapeador_principal() {
                diagrama_do_periodo(p, cfg)
            } else {
                svg::diagrama_svg(p, &cfg.unidade, &titulo, Some(&format!("{m}:{med}")), Some(rotulo_medida(med)))
            };
            let Some(f) = figura else { continue };
            saida.insert(format!("{base}images/{nome}"), f);
            linhas.push(vec![
                esc(&format!("{rm} — {}", rotulo_medida(med))),
                format!("<img src=\"images/{nome}\" alt=\"Diagrama estratégico — {} — {}\" width=\"760\">", esc(rm), esc(rotulo_medida(med))),
            ]);
        }
        if !linhas.is_empty() {
            diagramas.push(tab(&["Medida de desempenho", "Diagrama estratégico"], &linhas, Some(&format!("Diagramas estratégicos — {rm}")), &[], &["26%", "74%"]));
        }
    }
    diagramas.push(
        "<p class=\"fonte\">O tamanho das esferas segue a medida de desempenho indicada em cada diagrama; o quadrante usa a centralidade e a densidade de Callon.</p>".into(),
    );

    if let Some(h) = halo_do_periodo(p, cfg) {
        saida.insert(format!("{base}images/wholeNetwork-period{indice}.svg"), h);
        corpo.push("<h2>Rede completa</h2>".into());
        corpo.push(format!("<p><img src=\"images/wholeNetwork-period{indice}.svg\" alt=\"Rede completa — {}\" width=\"100%\"></p>", esc(&p.nome)));
        let mut c = Contador::default();
        let t = metodo::pivos_html(p, &mut c, &format!("Pontos de virada — {}", p.nome), "fonte");
        if !t.is_empty() {
            corpo.push("<h2>Pontos de virada</h2>".into());
            corpo.push(t);
        }
    }

    // Quadro de métricas com a rede de cada agrupamento
    let prefixo = format!("{}:", mapeadores[0]);
    let mut cartoes = Vec::new();
    for (pos, &gi) in ordem.iter().enumerate() {
        let g = &p.grupos[gi];
        let mut met = vec![
            format!("Itens: {}", g.itens()),
            format!("Centralidade: {}", numero(g.centralidade)),
            format!("Densidade: {}", numero(g.densidade)),
            format!("Quadrante: {}", quadrante_rotulo(g)),
        ];
        for nome in ["documentos", "h", "g", "hg"] {
            met.push(format!("{}: {}", rotulo_medida(nome), numero(g.medidas.get(&format!("{prefixo}{nome}")).copied().unwrap_or(0.0))));
        }
        let (principal, sub, _) = metodo::nome_do_grupo(g);
        let mut nome = format!("<a href=\"period{indice}-cluster{pos}.html\">{}</a>", esc(&principal));
        if let Some(s) = sub {
            nome.push_str(&format!("<br><span class=\"rot-atual\">{}</span>", esc(&s)));
        }
        let arq = format!("clusterNetwork-period{indice}-cluster{pos}.svg");
        let figura = match rede_do_grupo(p, gi) {
            Some(f) => {
                saida.insert(format!("{base}images/{arq}"), f);
                format!("<img src=\"images/{arq}\" alt=\"Rede de {}\" width=\"320\">", esc(&principal))
            }
            None => "—".into(),
        };
        cartoes.push(vec![nome, met.join("<br>"), figura]);
    }
    corpo.push("<h2>Métricas e rede de cada agrupamento</h2>".into());
    corpo.push(tab(&["Agrupamento", "Métricas", "Rede do agrupamento"], &cartoes, Some("Quadro de métricas com a rede de cada agrupamento"), &[], &["24%", "26%", "50%"]));

    let medidas: Vec<(String, String)> = ORDEM_MEDIDAS.iter().map(|m| (format!("{prefixo}{m}"), rotulo_medida(m).to_string())).collect();
    let ligar = |pos: usize, t: &str| format!("<a href=\"period{indice}-cluster{}.html\">{t}</a>", pos - 1);
    let (cab, linhas, numericas) = metodo::tabela_agrupamentos(&grupos, &medidas, &|v| numero(v), Some(&ligar));
    corpo.push("<h2>Agrupamentos</h2>".into());
    let cabs: Vec<&str> = cab.iter().map(|s| s.as_str()).collect();
    corpo.push(tab(&cabs, &linhas, Some("Agrupamentos do período"), &numericas, &[]));
    corpo.push(
        "<p class=\"fonte\">Silhueta: coesão média dos itens do agrupamento (de −1 a 1; “—” quando o agrupamento tem poucos itens). Ano médio: dos documentos do núcleo. Rótulo em destaque: termos distintivos do período; abaixo, o nome do item central.</p>".into(),
    );

    if cfg.unidade == "Institutions" {
        if p.ies.is_some() {
            corpo.push("<h2>Variantes unidas</h2>".into());
            corpo.push(metodo::ies_html(p, &mut Contador::default(), &sec.rotulo.to_lowercase()));
        }
    } else if matches!(cfg.unidade.as_str(), "Authors" | "Countries") {
        corpo.push(metodo::filtro_agrupamento_html(p, &cfg.unidade));
    }
    corpo.extend(diagramas);
    saida.insert(format!("{base}period{indice}.html"), pagina(&format!("Relatório — Redes — {}", p.nome), &corpo.join("\n"), base.matches('/').count(), voltar));
}

fn pagina_cluster(saida: &mut Mapa, base: &str, sec: &SecaoAnalise, p: &PeriodoRel, gi: usize, pos: usize, indice: usize, estendido: bool, voltar: Option<&str>) {
    let g = &p.grupos[gi];
    let (internas, externas) = ligacoes(p, g);
    let (principal, sub, indicativo) = metodo::nome_do_grupo(g);
    let nome_html = format!("{}{}", esc(&principal), if indicativo { " <span class=\"rot-ind\">(indicativo)</span>" } else { "" });
    let mut corpo: Vec<String> = vec![
        format!("<p><a href=\"index.html\">Índice</a> · <a href=\"period{indice}.html\">{}</a></p>", esc(&p.nome)),
        format!("<h1>{} — {}</h1>", esc(&p.nome), esc(&principal)),
    ];
    if let Some(s) = &sub {
        corpo.push(format!("<p class=\"rot-atual\">Rótulo atual (item central): {}</p>", esc(s)));
    }
    let mut info = vec![
        vec!["Nome".into(), nome_html],
        vec!["Itens".into(), g.itens().to_string()],
        vec!["Densidade".into(), numero(g.densidade)],
        vec!["Faixa de densidade".into(), numero(g.densidade_faixa)],
        vec!["Centralidade".into(), numero(g.centralidade)],
        vec!["Faixa de centralidade".into(), numero(g.centralidade_faixa)],
        vec!["Quadrante".into(), quadrante_rotulo(g).to_string()],
    ];
    if let Some(s) = &sub {
        info.push(vec!["Nome atual (item central)".into(), esc(s)]);
    }
    corpo.push("<h2>Informações do agrupamento</h2>".into());
    corpo.push(tab(&["Medida", "Valor"], &info, None, &[], &[]));
    corpo.push("<h2>Rede do agrupamento</h2>".into());
    corpo.push(format!("<p><img src=\"images/clusterNetwork-period{indice}-cluster{pos}.svg\" alt=\"Rede do agrupamento {}\" width=\"720\"></p>", esc(&principal)));
    let lin = |v: &[ArestaRel]| -> Vec<Vec<String>> { v.iter().map(|a| vec![esc(&nome_no(p, a.a)), esc(&nome_no(p, a.b)), numero(a.peso)]).collect() };
    corpo.push("<h2>Ligações internas</h2>".into());
    corpo.push(tab(&["Nó A", "Nó B", "Peso"], &lin(&internas), Some("Ligações internas"), &[2], &[]));
    corpo.push("<h2>Ligações externas</h2>".into());
    corpo.push(tab(&["Nó A", "Nó B", "Peso"], &lin(&externas), Some("Ligações externas"), &[2], &[]));
    if estendido && !g.documentos.is_empty() {
        corpo.push("<h2>Documentos por mapeador</h2>".into());
        for (m, docs) in &g.documentos {
            let titulo = rotulo_mapeador_titulo(m);
            let linhas: Vec<Vec<String>> = docs
                .iter()
                .map(|d| {
                    vec![
                        esc(&d.titulo),
                        esc(&d.autores),
                        esc(&d.ano),
                        esc(&d.fonte),
                        d.citacoes.to_string(),
                        d.referencias.iter().map(|r| esc(&referencia_abnt(r))).collect::<Vec<_>>().join("<br>"),
                    ]
                })
                .collect();
            corpo.push(tab(&["Título", "Autores", "Ano", "Fonte", "Citações", "Referências (ABNT)"], &linhas, Some(&format!("{titulo} ({})", linhas.len())), &[4], &["28%", "14%", "6%", "14%", "7%", "31%"]));
            let medidas: Vec<Vec<String>> = ORDEM_MEDIDAS
                .iter()
                .map(|n| vec![rotulo_medida(n).to_string(), numero(g.medidas.get(&format!("{m}:{n}")).copied().unwrap_or(0.0))])
                .collect();
            corpo.push(tab(&["Medida", "Valor"], &medidas, Some(&format!("{titulo} — medidas de desempenho")), &[1], &[]));
        }
    }
    let _ = sec;
    saida.insert(format!("{base}period{indice}-cluster{pos}.html"), pagina(&format!("{} — {} · Redes", p.nome, principal), &corpo.join("\n"), base.matches('/').count(), voltar));
}

fn pagina_indice_analise(saida: &mut Mapa, base: &str, sec: &SecaoAnalise, medida: &str, voltar: Option<&str>) {
    let mut linhas = Vec::new();
    for (i, p) in sec.periodos.iter().enumerate() {
        linhas.push(vec![
            format!("<a href=\"period{i}.html\">{}</a>", esc(&p.nome)),
            p.docs_com_itens().to_string(),
            p.itens.to_string(),
            p.grupos.len().to_string(),
            format!("{}/{}", p.rede_nos, p.rede_arestas),
        ]);
    }
    let mut c = Contador::default();
    let mt = sec.medida_temporal.as_deref().unwrap_or(medida);
    let com_duplo = sec.extras.iter().any(|e| e.tipo == TipoExtra::DuploMapa);
    let com_sim = sec.extras.iter().any(|e| e.tipo == TipoExtra::Similitude);
    let mut tit = |t: &str| format!("<h3>{}</h3>", esc(t));
    let metodo_html = metodo::metodo_html(&sec.config, Some(sec.periodos.len()), &sec.periodos, sec.total.as_ref(), sec.frequencia, Some(mt), &mut c, &sec.rotulo.to_lowercase(), &mut tit, com_duplo, com_sim);
    let mut corpo: Vec<String> = vec![
        "<h1>Relatório — Redes</h1>".into(),
        "<p>Relatório gerado automaticamente a partir do projeto analisado.</p>".into(),
        "<h2>Parâmetros e método</h2>".into(),
        metodo_html,
        "<h2>Resultados dos períodos</h2>".into(),
    ];
    let t = c.tabela(&strings(&["Período", "Documentos", "Itens", "Agrupamentos", "Nós/arestas"]), &linhas, "Resumo por período", &[1, 2, 3, 4], false);
    corpo.push(t);
    for e in &sec.extras {
        let titulo = e.titulo.clone().unwrap_or_else(|| e.tipo.titulo_padrao().to_string());
        corpo.push(format!("<h2 id=\"{}\">{}</h2>", e.tipo.ancora(), esc(&titulo)));
        for (k, b) in e.blocos.iter().enumerate() {
            match b {
                Bloco::Html { html } => corpo.push(html.clone()),
                Bloco::Nota { texto } => corpo.push(format!("<p class=\"nota\">{}</p>", esc(texto))),
                Bloco::Fonte { texto } => corpo.push(format!("<p class=\"fonte\">{}</p>", esc(texto))),
                Bloco::Subtitulo { texto } => corpo.push(format!("<h3>{}</h3>", esc(texto))),
                Bloco::Figura { svg, legenda } => {
                    let arq = format!("{}-{k}.svg", e.tipo.ancora());
                    saida.insert(format!("{base}images/{arq}"), svg.clone());
                    corpo.push(format!("<p><img src=\"images/{arq}\" alt=\"{}\" style=\"max-width:100%\"></p>", esc(legenda)));
                }
                Bloco::Tabela { cabecalho, linhas, legenda, numericas, larga } => corpo.push(c.tabela(cabecalho, linhas, legenda, numericas, *larga)),
                Bloco::Lista { itens } => corpo.push(format!("<ul>{}</ul>", itens.iter().map(|i| format!("<li>{}</li>", esc(i))).collect::<String>())),
            }
        }
    }
    saida.insert(format!("{base}index.html"), pagina("Relatório — Redes", &corpo.join("\n"), base.matches('/').count(), voltar));
}

fn pagina_geral(dados: &DadosRelatorio, saida: &mut Mapa) {
    let mut c = Contador::default();
    let mut corpo: Vec<String> = vec!["<h1>Visão geral descritiva do corpus</h1>".into()];
    if let Some(v) = &dados.visao_geral {
        for l in &v.lacunas {
            corpo.push(format!("<p class=\"nota\">{}</p>", esc(l)));
        }
        if !v.cartoes.is_empty() {
            let linhas: Vec<Vec<String>> = v.cartoes.iter().map(|l| l.iter().map(|x| esc(x)).collect()).collect();
            corpo.push(c.tabela(&strings(&["Indicador", "Valor", "Observação"]), &linhas, "Informações principais", &[], false));
        }
        for (k, s) in v.subsecoes.iter().enumerate() {
            corpo.push(format!("<h2>{}</h2>", esc(&s.titulo)));
            for (j, b) in s.blocos.iter().enumerate() {
                match b {
                    Bloco::Html { html } => corpo.push(html.clone()),
                    Bloco::Nota { texto } => corpo.push(format!("<p class=\"nota\">{}</p>", esc(texto))),
                    Bloco::Fonte { texto } => corpo.push(format!("<p class=\"fonte\">{}</p>", esc(texto))),
                    Bloco::Subtitulo { texto } => corpo.push(format!("<h3>{}</h3>", esc(texto))),
                    Bloco::Figura { svg, legenda } => {
                        let arq = format!("geral-{k}-{j}.svg");
                        saida.insert(format!("images/{arq}"), svg.clone());
                        corpo.push(format!("<p><img src=\"images/{arq}\" alt=\"{}\" style=\"max-width:100%\"></p>", esc(legenda)));
                    }
                    Bloco::Tabela { cabecalho, linhas, legenda, numericas, larga } => corpo.push(c.tabela(cabecalho, linhas, legenda, numericas, *larga)),
                    Bloco::Lista { itens } => corpo.push(format!("<ul>{}</ul>", itens.iter().map(|i| format!("<li>{}</li>", esc(i))).collect::<String>())),
                }
            }
        }
        if !v.sem_metodo {
            corpo.push("<h2>Método e parâmetros</h2>".into());
            corpo.push(metodo::metodo_bibliometria_html(&mut c, v.parametros.as_deref()));
        }
    } else {
        corpo.push("<p>Este projeto não trouxe a visão geral descritiva.</p>".into());
    }
    corpo.push("<p><a href=\"index.html\">Índice</a></p>".into());
    saida.insert("bibliometria.html".into(), pagina("Visão geral descritiva — Redes", &corpo.join("\n"), 0, None));
}

/// Todas as páginas e imagens do relatório em pasta (caminho relativo -> conteúdo).
pub fn paginas(dados: &DadosRelatorio) -> Mapa {
    let mut saida = Mapa::new();
    saida.insert("logo.svg".into(), LOGO_SVG.to_string());
    let medida = if dados.medida_temporal.is_empty() { "EquivalenceIndex" } else { &dados.medida_temporal };
    let completo = dados.secoes.len() > 1 || dados.visao_geral.is_some();
    let mut sumario = Vec::new();
    let mut blocos = Vec::new();
    if completo {
        pagina_geral(dados, &mut saida);
        sumario.push("<a href=\"bibliometria.html\">1 Visão geral descritiva</a>".to_string());
        blocos.push("<h2 id=\"visao\">1 Visão geral descritiva</h2><p><a href=\"bibliometria.html\">Produção e citações, rankings, leis bibliométricas, nuvens de palavras e rajadas</a></p>".to_string());
    }
    let mut c = Contador::default();
    let mut n_fig = 0;
    let primeira = if completo { 2 } else { 1 };
    for (k, sec) in dados.secoes.iter().enumerate() {
        let pos = primeira + k;
        let pasta = if sec.chave.is_empty() { slug(&sec.rotulo) } else { slug(&sec.chave) };
        let base = if completo { format!("{pasta}/") } else { String::new() };
        let voltar = if completo { Some("../index.html") } else { None };
        pagina_indice_analise(&mut saida, &base, sec, medida, voltar);
        for (i, p) in sec.periodos.iter().enumerate() {
            pagina_periodo(&mut saida, &base, sec, p, i, voltar);
            for (posg, &gi) in ordem_grupos(p).iter().enumerate() {
                pagina_cluster(&mut saida, &base, sec, p, gi, posg, i, dados.estendido, voltar);
            }
        }
        if !completo {
            continue;
        }
        let ancora = format!("s{pos}");
        sumario.push(format!("<a href=\"#{ancora}\">{pos} {}</a>", esc(&sec.rotulo)));
        let linhas: Vec<Vec<String>> = sec
            .periodos
            .iter()
            .enumerate()
            .map(|(i, p)| vec![format!("<a href=\"{pasta}/period{i}.html\">{}</a>", esc(&p.nome)), p.itens.to_string(), p.grupos.len().to_string(), format!("{} nós", p.maior_grupo())])
            .collect();
        let mut b = vec![
            format!("<h2 id=\"{ancora}\">{pos} {}</h2>", esc(&sec.rotulo)),
            format!("<p>{}</p>", esc(&sec.descricao)),
            tabela_html(&strings(&["Período", "Itens", "Grupos", "Maior grupo"]), &linhas, Some(&format!("{pos}.1 Por período")), &[1, 2], &[]),
            format!("<p><a href=\"{pasta}/index.html\">Configuração, mapa de evolução e sobreposição</a></p>"),
        ];
        for e in &sec.extras {
            b.push(format!("<p><a href=\"{pasta}/index.html#{}\">{}</a></p>", e.tipo.ancora(), esc(e.titulo.as_deref().unwrap_or(e.tipo.titulo_padrao()))));
        }
        let mut miniaturas = Vec::new();
        let mapeador = sec.config.mapeador_principal().to_string();
        for (i, p) in sec.periodos.iter().enumerate() {
            if p.grupos.is_empty() {
                continue;
            }
            for (arq, leg) in [(format!("strategicDiagram-period{i}-{mapeador}-documentos.svg"), "Diagrama estratégico"), (format!("wholeNetwork-period{i}.svg"), "Rede do período")] {
                if !saida.contains_key(&format!("{pasta}/images/{arq}")) {
                    continue;
                }
                n_fig += 1;
                miniaturas.push(format!(
                    "<figure><a href=\"{pasta}/period{i}.html\"><img src=\"{pasta}/images/{arq}\" alt=\"{} {}\" loading=\"lazy\"></a><figcaption>Figura {n_fig} — {} de {}, {}.</figcaption></figure>",
                    esc(leg),
                    esc(&p.nome),
                    leg.to_lowercase(),
                    esc(&sec.rotulo.to_lowercase()),
                    esc(&p.nome)
                ));
            }
        }
        if !miniaturas.is_empty() {
            b.push(format!("<div class=\"miniaturas\">{}</div>", miniaturas.concat()));
        }
        b.push(format!("<h3 id=\"{ancora}-metodo\">{pos}.2 Parâmetros e método</h3>"));
        let mt = sec.medida_temporal.as_deref().unwrap_or(medida);
        let com_duplo = sec.extras.iter().any(|e| e.tipo == TipoExtra::DuploMapa);
        let com_sim = sec.extras.iter().any(|e| e.tipo == TipoExtra::Similitude);
        let mut tit = |t: &str| format!("<h4>{}</h4>", esc(t));
        b.push(metodo::metodo_html(&sec.config, Some(dados.projeto.periodos.len().max(sec.periodos.len())), &sec.periodos, sec.total.as_ref(), sec.frequencia, Some(mt), &mut c, &sec.rotulo.to_lowercase(), &mut tit, com_duplo, com_sim));
        blocos.push(b.join("\n"));
    }
    if completo {
        if !dados.ignoradas.is_empty() {
            sumario.push("<a href=\"#nao-gerados\">Não gerados</a>".into());
            blocos.push(format!(
                "<h2 id=\"nao-gerados\">Análises não geradas</h2><ul>{}</ul>",
                dados.ignoradas.iter().map(|i| format!("<li><b>{}</b>: {}</li>", esc(&i.rotulo), esc(&i.motivo))).collect::<String>()
            ));
        }
        let mut corpo = vec![
            "<h1>Relatório completo — Redes</h1>".to_string(),
            format!("<nav class=\"sumario\">{}</nav>", sumario.join(" ")),
            "<p>Cada seção traz o quadro por período, o diagrama estratégico e a rede de cada período; os links levam às páginas de período e de cada agrupamento.</p>".into(),
        ];
        corpo.extend(blocos);
        saida.insert("index.html".into(), pagina("Relatório completo — Redes", &corpo.join("\n"), 0, None));
    }
    saida
}

/// Grava o relatório em pasta e devolve o caminho do `index.html`.
pub fn gera_pasta(destino: &Path, dados: &DadosRelatorio) -> std::io::Result<PathBuf> {
    for (rel, conteudo) in paginas(dados) {
        let caminho = destino.join(&rel);
        if let Some(pai) = caminho.parent() {
            std::fs::create_dir_all(pai)?;
        }
        std::fs::write(caminho, conteudo)?;
    }
    Ok(destino.join("index.html"))
}
