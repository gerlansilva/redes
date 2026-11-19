//! Parâmetros, método e indicadores de cada análise (porta de `metodo.py`).
//!
//! Todo relatório traz, para cada análise, o bloco "Parâmetros e método": os
//! parâmetros efetivamente adotados, uma descrição em linguagem simples do que
//! o código faz ("Como funciona") e a tabela de indicadores, calculada dos
//! resultados recebidos. As tabelas passam por um [`Numerador`], para que cada
//! relatório aplique a sua numeração.

use crate::dados::*;
use crate::texto::*;

pub const ROTULOS_MEDIDA: &[(&str, &str)] = &[
    ("documentos", "Documentos"),
    ("h", "Índice h"),
    ("g", "Índice g"),
    ("hg", "Índice hg"),
    ("q2", "Índice Q2"),
    ("media", "Citações médias"),
    ("soma", "Citações totais"),
    ("minimo", "Citações mínimas"),
    ("maximo", "Citações máximas"),
];

pub fn rotulo_medida(m: &str) -> &str {
    ROTULOS_MEDIDA.iter().find(|(k, _)| *k == m).map(|(_, v)| *v).unwrap_or(m)
}

/// Rótulos de mapeador dos títulos de diagrama (`report.ROTULOS_MAPEADOR`).
pub fn rotulo_mapeador_titulo(m: &str) -> &str {
    match m {
        "nucleo" => "Documentos centrais",
        "interseccao" => "Documentos de interseção",
        "secundarios" => "Documentos secundários",
        "kcore" => "Documentos k-core",
        "uniao" => "Documentos da união",
        "acoplamento" => "Documentos de acoplamento",
        _ => m,
    }
}

fn rotulo_unidade(u: &str) -> &str {
    match u {
        "Words" => "Palavras-chave",
        "Authors" => "Autores",
        "References" => "Referências",
        "AuthorsReference" => "Autores de referência",
        "ReferenceSources" => "Fontes de referência",
        "Countries" => "Países",
        "Institutions" => "Instituições (IES)",
        _ => u,
    }
}

pub fn item_unidade(u: &str) -> &str {
    match u {
        "Words" => "palavras",
        "Authors" => "autores",
        "References" => "referências",
        "AuthorsReference" => "autores de referência",
        "ReferenceSources" => "fontes de referência",
        "Countries" => "países",
        "Institutions" => "instituições",
        _ => "itens",
    }
}

fn rotulo_matriz(m: &str) -> &str {
    match m {
        "CoOccurrence" => "Co-ocorrência",
        "BasicCoupling" => "Acoplamento básico",
        "AggregatedCouplingBasedOnAuthor" => "Acoplamento agregado por autor",
        "AggregatedCouplingBasedOnJournal" => "Acoplamento agregado por periódico",
        _ => m,
    }
}

fn rotulo_algoritmo(a: &str) -> &str {
    match a {
        "CentersSimples" => "Centros simples",
        "AverageLink" => "Ligação média",
        "CompleteLink" => "Ligação completa",
        "SingleLink" => "Ligação simples",
        "SumLink" => "Ligação por soma",
        "Louvain" => "Louvain",
        _ => a,
    }
}

fn rotulo_similaridade(s: &str) -> &str {
    match s {
        "AssociationStrength" => "Força de associação",
        "EquivalenceIndex" => "Índice de equivalência",
        "InclusionIndex" => "Índice de inclusão",
        "JaccardIndex" => "Índice de Jaccard",
        "SaltonCosine" => "Cosseno de Salton",
        _ => s,
    }
}

const SIMILARIDADES: &[&str] = &["AssociationStrength", "EquivalenceIndex", "InclusionIndex", "JaccardIndex", "SaltonCosine"];

fn formula(s: &str) -> &'static str {
    match s {
        "EquivalenceIndex" => "c<sub>ij</sub>² ÷ (f<sub>i</sub> · f<sub>j</sub>)",
        "AssociationStrength" => "c<sub>ij</sub> ÷ (f<sub>i</sub> · f<sub>j</sub>)",
        "InclusionIndex" => "c<sub>ij</sub> ÷ mín(f<sub>i</sub>, f<sub>j</sub>)",
        "JaccardIndex" => "c<sub>ij</sub> ÷ (f<sub>i</sub> + f<sub>j</sub> − c<sub>ij</sub>)",
        "SaltonCosine" => "c<sub>ij</sub>² ÷ √(f<sub>i</sub> · f<sub>j</sub>)",
        _ => "",
    }
}

fn explicacao_similaridade(s: &str) -> &'static str {
    match s {
        "EquivalenceIndex" => "vale 1 quando os dois itens sempre aparecem juntos e cai rápido quando um deles aparece muito sem o outro",
        "AssociationStrength" => "compara a ligação observada com a esperada se os itens fossem independentes; favorece pares de itens raros",
        "InclusionIndex" => "vale 1 quando o item menos frequente só aparece junto do outro; favorece itens raros contidos em itens comuns",
        "JaccardIndex" => "documentos com os dois itens divididos pelos documentos com pelo menos um deles",
        "SaltonCosine" => "o numerador é elevado ao quadrado; por isso o valor não fica limitado a 1, ao contrário do cosseno clássico",
        _ => "",
    }
}

fn rotulo_mapeador(m: &str) -> &str {
    match m {
        "nucleo" => "núcleo",
        "interseccao" => "interseção",
        "secundarios" => "secundários",
        "kcore" => "k-core",
        "uniao" => "união",
        "acoplamento" => "acoplamento",
        _ => m,
    }
}

fn rotulo_indice(i: &str) -> &str {
    match i {
        "h" => "h",
        "g" => "g",
        "hg" => "hg",
        "q2" => "q2",
        "media" => "média de citações",
        "soma" => "soma de citações",
        "minimo" => "mínimo de citações",
        "maximo" => "máximo de citações",
        _ => i,
    }
}

fn origem_palavras(o: &str) -> &str {
    match o {
        "autor" => "palavras-chave dos autores",
        "fonte" => "palavras-chave atribuídas pela fonte",
        "adicionada" => "palavras adicionadas na edição",
        _ => o,
    }
}

fn rotulo_temporal(s: &str) -> &str {
    match s {
        "AssociationStrength" => "força de associação",
        "EquivalenceIndex" => "índice de equivalência",
        "InclusionIndex" => "índice de inclusão",
        "JaccardIndex" => "índice de Jaccard",
        "SaltonCosine" => "cosseno de Salton",
        _ => s,
    }
}

pub const UNIDADES_LINHA_DO_TEMPO: &[&str] = &["Words", "Authors", "References"];

// Limiares e constantes dos módulos que fazem o cálculo (iguais aos do Python).
pub const LT_MAX_NOS: usize = 40;
pub const LT_POR_FAIXA: usize = 8;
pub const LT_LIGACOES_POR_NO: usize = 3;
pub const LT_LIGACOES_CRUZADAS: usize = 6;
pub const LT_RAJADAS_MAXIMAS: usize = 10;
pub const LT_RAJADA_MIN_DOCUMENTOS: usize = 3;
pub const PIVOS_PERCENTIL: f64 = 90.0;
pub const PIVOS_PROPORCAO_DESCRITOR: f64 = 0.5;
pub const PIVOS_MINIMO_NOS: usize = 40;
pub const TOPO_PIVOS: usize = 10;
pub const Q_GRUPO_GRANDE: usize = 5;
pub const Q_MINIMO_NOS: usize = 15;
pub const Q_MINIMO_NOS_SILHUETA: usize = 3;
pub const Q_LIMITE_NOS: usize = 2000;
const ROT_MINIMO_DOCUMENTOS: usize = 5;
const ROT_LIMITE_INDICATIVO: usize = 10;
const ROT_COBERTURA_MAXIMA: usize = 70;
const ROT_MINIMO_NO_GRUPO: usize = 2;

// ------------------------------------------------------------- qualidade

pub fn nivel_rotulo(n: &str) -> &'static str {
    match n {
        "ok" => "OK",
        "atencao" => "Atenção",
        "ruim" => "Ruim",
        _ => "Indefinido",
    }
}

fn nivel_icone(n: &str) -> &'static str {
    match n {
        "ok" => "✓",
        "atencao" => "!",
        "ruim" => "✕",
        _ => "?",
    }
}

pub fn selo_qualidade(nivel: &str) -> String {
    let n = if matches!(nivel, "ok" | "atencao" | "ruim" | "indefinido") { nivel } else { "indefinido" };
    format!(
        "<span class=\"selo-q selo-q-{n}\"><span aria-hidden=\"true\">{}</span> {}</span>",
        nivel_icone(n),
        nivel_rotulo(n)
    )
}

// -------------------------------------------------------------- quadrantes

/// Chave do quadrante pelas faixas (`metodo._quadrante`).
pub fn quadrante_chave(g: &GrupoRel) -> &'static str {
    if g.centralidade_faixa >= 0.5 && g.densidade_faixa >= 0.5 {
        "motor"
    } else if g.densidade_faixa >= 0.5 {
        "nicho"
    } else if g.centralidade_faixa >= 0.5 {
        "basico"
    } else {
        "emergente"
    }
}

pub fn quadrante_rotulo(g: &GrupoRel) -> &'static str {
    match quadrante_chave(g) {
        "motor" => "Motor",
        "nicho" => "Nicho",
        "basico" => "Básico",
        _ => "Emergente",
    }
}

fn nomes_quadrantes(unidade: &str) -> [&'static str; 4] {
    // motor, nicho, basico, emergente (em minúsculas)
    if unidade == "Countries" {
        ["núcleos", "isolados", "periféricos", "dispersa"]
    } else {
        ["motores", "nicho", "básicos", "emergentes"]
    }
}

// ---------------------------------------------------------------- grupos

/// (principal, subtítulo, indicativo) de um agrupamento.
pub fn nome_do_grupo(g: &GrupoRel) -> (String, Option<String>, bool) {
    let atual = g.nome_exibicao().to_string();
    let novo = g.rotulo_novo.as_deref().map(normaliza_espacos).unwrap_or_default();
    if novo.is_empty() {
        return (atual, None, false);
    }
    (novo, Some(atual), g.indicativo)
}

/// Cabeçalho, linhas (HTML) e colunas numéricas da tabela de agrupamentos de um período.
/// `ligar(posição, html)` envolve o nome num link.
pub fn tabela_agrupamentos(
    grupos: &[&GrupoRel],
    medidas: &[(String, String)],
    formato: &dyn Fn(f64) -> String,
    ligar: Option<&dyn Fn(usize, &str) -> String>,
) -> (Vec<String>, Vec<Vec<String>>, Vec<usize>) {
    let mut linhas = Vec::new();
    for (i, g) in grupos.iter().enumerate() {
        let posicao = i + 1;
        let novo = g.rotulo_novo.as_deref().map(normaliza_espacos).filter(|s| !s.is_empty());
        let nome = if let Some(novo) = novo {
            let mut principal = format!("<strong class=\"rot-novo\">{}</strong>", esc(&novo));
            if g.indicativo {
                principal.push_str(" <span class=\"rot-ind\">(indicativo)</span>");
            }
            let p = match ligar {
                Some(l) => l(posicao, &principal),
                None => principal,
            };
            format!("{p}<br><span class=\"rot-atual\">{}</span>", esc(g.nome_exibicao()))
        } else {
            let atual = esc(g.nome_exibicao());
            match ligar {
                Some(l) => l(posicao, &atual),
                None => atual,
            }
        };
        let nome = format!("<div class=\"cel-agrupamento\">{nome}</div>");
        let ano = match g.ano_medio {
            None => "—".to_string(),
            Some(a) => n2(Some(a), 1),
        };
        let mut linha = vec![
            posicao.to_string(),
            nome,
            g.itens().to_string(),
            n2(g.silhueta, 2),
            ano,
            g.documentos_nucleo.unwrap_or(0).to_string(),
            quadrante_rotulo(g).to_string(),
            formato(g.centralidade),
            formato(g.densidade),
        ];
        for (chave, _) in medidas {
            linha.push(formato(g.medidas.get(chave).copied().unwrap_or(0.0)));
        }
        linhas.push(linha);
    }
    let mut cab = strings(&["Nº", "Agrupamento", "Itens", "Silhueta", "Ano médio", "Documentos (núcleo)", "Quadrante", "Centralidade", "Densidade"]);
    cab.extend(medidas.iter().map(|(_, r)| r.clone()));
    let mut numericas = vec![0, 2, 3, 4, 5, 7, 8];
    numericas.extend(9..9 + medidas.len());
    (cab, linhas, numericas)
}

/// Índices dos grupos na ordem em que o relatório os numera: maior primeiro, desempate pelo rótulo.
pub fn ordem_grupos(p: &PeriodoRel) -> Vec<usize> {
    let mut v: Vec<usize> = (0..p.grupos.len()).collect();
    v.sort_by(|&a, &b| p.grupos[b].itens().cmp(&p.grupos[a].itens()).then_with(|| p.grupos[a].rotulo.cmp(&p.grupos[b].rotulo)));
    v
}

// ----------------------------------------------------------------- pivôs

fn lista_nomes(itens: &[String], limite: usize) -> String {
    let t = itens.iter().take(limite).cloned().collect::<Vec<_>>().join(", ");
    if itens.len() > limite {
        format!("{t} e mais {}", itens.len() - limite)
    } else {
        t
    }
}

fn nos_txt(n: usize) -> String {
    format!("{n} {}", if n == 1 { "nó" } else { "nós" })
}

/// Tabela "Pontos de virada" de um período, com as notas de leitura. Devolve ""
/// quando o período não tem dados de pontos de virada.
pub fn pivos_html(p: &PeriodoRel, num: &mut dyn Numerador, legenda: &str, classe_nota: &str) -> String {
    let Some(dados) = &p.pivos else { return String::new() };
    let mut partes: Vec<String> = Vec::new();
    if let Some(nc) = &dados.nao_calculado {
        return format!("<p class=\"{classe_nota}\">{}</p>", esc(nc));
    }
    if !dados.itens.is_empty() {
        let com_sigma = dados.itens.iter().any(|i| i.sigma.is_some());
        let mut cab = strings(&["Nº", "Item", "Intermediação", "Agrupamentos vizinhos", "Grupo", "Frequência"]);
        if com_sigma {
            cab.push("Sigma".into());
        }
        let mut linhas = Vec::new();
        for (pos, i) in dados.itens.iter().enumerate() {
            let principal = match i.grupo {
                Some(ix) if ix < p.grupos.len() => nome_do_grupo(&p.grupos[ix]).0,
                _ => "—".into(),
            };
            let mut l = vec![
                (pos + 1).to_string(),
                esc(&i.rotulo),
                n4(Some(i.intermediacao)),
                i.grupos_vizinhos.to_string(),
                esc(&principal),
                i.frequencia.to_string(),
            ];
            if com_sigma {
                l.push(n2(i.sigma, 3));
            }
            linhas.push(l);
        }
        let mut numericas = vec![0, 2, 3, 5];
        if com_sigma {
            numericas.push(6);
        }
        partes.push(num.tabela(&cab, &linhas, legenda, &numericas, false));
        let mut nota = String::from(
            "Pontos de virada: itens de intermediação alta (decil superior da rede) cujos vizinhos estão em dois ou mais \
             agrupamentos; ligam temas que, sem eles, ficariam mais separados. Intermediação normalizada, de 0 a 1.",
        );
        if com_sigma {
            nota.push_str(
                " Sigma = (intermediação + 1) elevado à força da rajada do termo; entre os pontos de virada, o ranking por sigma \
                 acompanha sobretudo a intermediação, não a força da rajada. A rajada de palavras-chave é calculada só sobre as \
                 palavras-chave dos autores.",
            );
        }
        partes.push(format!("<p class=\"{classe_nota}\">{}</p>", esc(&nota)));
    } else {
        let motivos: Vec<&String> = dados
            .avisos
            .iter()
            .filter(|a| !a.starts_with("Poucos dados") && !a.contains("fora do ranking"))
            .collect();
        let extra = if motivos.is_empty() { String::new() } else { format!(" {}", motivos.iter().map(|s| s.as_str()).collect::<Vec<_>>().join(" ")) };
        partes.push(format!("<p class=\"{classe_nota}\">Nenhum ponto de virada identificado neste período.{}</p>", esc(&extra)));
    }
    if !dados.termos_descritores.is_empty() {
        let nomes: Vec<String> = dados
            .termos_descritores
            .iter()
            .map(|t| format!("{} ({})", esc(&t.rotulo), pct0(t.proporcao_documentos)))
            .collect();
        partes.push(format!(
            "<p class=\"{classe_nota}\">Termos-descritor excluídos do ranking: {}. Aparecem em mais de {} dos documentos do período; \
             descrevem o corpus em vez de distinguir temas e ligam quase tudo, então não são lidos como pontos de virada.</p>",
            lista_nomes(&nomes, 8),
            pct0(PIVOS_PROPORCAO_DESCRITOR)
        ));
    }
    if !dados.suficiente {
        partes.push(format!(
            "<p class=\"{classe_nota}\"><strong>Poucos dados:</strong> a rede tem {} (o mínimo confiável é {}); leia os pontos de virada \
             como indício.</p>",
            nos_txt(dados.n_nos),
            PIVOS_MINIMO_NOS
        ));
    }
    partes.join("\n")
}

// ----------------------------------------------------- parâmetros e períodos

fn frequencia_efetiva(config: &ConfigRel, f: Option<usize>) -> usize {
    f.unwrap_or(config.minimo_frequencia)
}

fn no_e_peso(config: &ConfigRel) -> &'static str {
    match config.matriz.as_str() {
        "CoOccurrence" => "os itens",
        "BasicCoupling" => "os documentos",
        "AggregatedCouplingBasedOnAuthor" => "os autores",
        _ => "os periódicos",
    }
}

fn subst_filtro(unidade: &str) -> (&'static str, &'static str) {
    match unidade {
        "Authors" => ("autor", "autores"),
        "Countries" => ("país", "países"),
        _ => ("instituição", "instituições"),
    }
}

/// Linhas (parâmetro, valor em HTML) dos parâmetros efetivamente usados.
pub fn parametros_linhas(config: &ConfigRel, n_periodos: Option<usize>, resultados: &[PeriodoRel], frequencia: Option<usize>, medida_temporal: Option<&str>) -> Vec<Vec<String>> {
    let frequencia = frequencia_efetiva(config, frequencia);
    let cooc = config.matriz == "CoOccurrence";
    let minimo_aresta = if cooc { "Co-ocorrência mínima" } else { "Acoplamento mínimo" };
    let nos = no_e_peso(config);

    let corte = if config.corte != 0.0 && !matches!(config.algoritmo.as_str(), "CentersSimples" | "Louvain") {
        decimal(config.corte)
    } else if matches!(config.algoritmo.as_str(), "CentersSimples" | "Louvain") {
        format!("{} (não se aplica a {})", decimal(config.corte), rotulo_algoritmo(&config.algoritmo).to_lowercase())
    } else {
        "0 (sem corte)".to_string()
    };

    let mapeadores: Vec<String> = config
        .mapeadores
        .iter()
        .map(|m| {
            let r = rotulo_mapeador(m);
            if m == "kcore" {
                format!("{r} (k = {})", config.k_core)
            } else {
                r.to_string()
            }
        })
        .collect();

    let mut linhas: Vec<(String, String)> = vec![
        ("Unidade de análise".into(), esc(rotulo_unidade(&config.unidade))),
        ("Matriz".into(), esc(&format!("{} (nós: {})", rotulo_matriz(&config.matriz), nos))),
        (
            "Similaridade".into(),
            format!("{}: <code class=\"formula\">{}</code>", esc(rotulo_similaridade(&config.similaridade)), formula(&config.similaridade)),
        ),
        ("Algoritmo de agrupamento".into(), esc(rotulo_algoritmo(&config.algoritmo))),
        (
            "Frequência mínima".into(),
            esc(&format!(
                "{frequencia} (itens em menos de {frequencia} {} saem antes da rede)",
                plural(frequencia, "documento", "documentos")
            )),
        ),
        (
            minimo_aresta.into(),
            esc(&format!("{} (ligações com valor menor saem antes da normalização)", numero_py(config.minimo_coocorrencia))),
        ),
        (
            "Tamanho dos agrupamentos".into(),
            esc(&format!("mínimo {}, máximo {} nós", config.tamanho_minimo, config.tamanho_maximo)),
        ),
        ("Ponto de corte".into(), esc(&corte)),
        (
            "Mapeador de documentos".into(),
            esc(&if mapeadores.is_empty() { "nenhum".to_string() } else { mapeadores.join(", ") }),
        ),
        (
            "Medidas de desempenho".into(),
            esc(&format!("documentos, {}", config.indices.iter().map(|i| rotulo_indice(i)).collect::<Vec<_>>().join(", "))),
        ),
    ];
    if config.unidade == "Words" {
        let origens: Vec<&str> = config.palavras.iter().map(|o| origem_palavras(o)).collect();
        linhas.push((
            "Origem das palavras".into(),
            esc(&if origens.is_empty() { "todas (nenhuma origem marcada)".to_string() } else { origens.join(", ") }),
        ));
    }
    if matches!(config.unidade.as_str(), "Authors" | "Countries" | "Institutions") {
        let minimo_comp = config.agrupamento_minimo;
        let subst = subst_filtro(&config.unidade);
        let nome = if config.unidade == "Institutions" { "Tamanho mínimo do componente (IES)" } else { "Tamanho mínimo do agrupamento" };
        let valor = if minimo_comp > 1 {
            format!(
                "{minimo_comp} (componentes conexos da rede com menos de {minimo_comp} {} não viram agrupamento e ficam sem agrupamento, \
                 fora dos halos; nenhum nó nem aresta é apagado)",
                subst.1
            )
        } else {
            "1 (sem filtro: todo componente pode virar agrupamento)".to_string()
        };
        linhas.push((nome.into(), esc(&valor)));
    }
    if config.unidade == "Institutions" {
        linhas.push((
            "União de variantes de nome".into(),
            esc("automática e conservadora; cada união está na tabela \"variantes unidas\""),
        ));
    }
    linhas.push((
        "Termos ignorados".into(),
        if config.ignorar.is_empty() { "nenhum".into() } else { esc(&config.ignorar.join(", ")) },
    ));
    if !resultados.is_empty() {
        let info = periodos_info(resultados);
        let txt = info
            .iter()
            .map(|i| format!("{} ({} {})", esc(&i.0), inteiro(i.1), plural(i.1, "documento", "documentos")))
            .collect::<Vec<_>>()
            .join("; ");
        linhas.push(("Períodos".into(), format!("{}: {}", info.len(), txt)));
    }
    if let Some(mt) = medida_temporal {
        if !mt.is_empty() && cooc && n_periodos.map(|n| n >= 2).unwrap_or(true) {
            linhas.push(("Medida temporal (evolução e sobreposição)".into(), esc(rotulo_similaridade(mt))));
        }
    }
    linhas.into_iter().map(|(a, b)| vec![esc(&a), b]).collect()
}

/// `str(int)` quando inteiro, senão repr do float (como o `{config.minimo_coocorrencia}` do Python).
fn numero_py(v: f64) -> String {
    if v == v.trunc() && v.abs() < 1e15 {
        format!("{}", v as i64)
    } else {
        format!("{v}")
    }
}

/// (período, documentos, com itens, itens) por período.
fn periodos_info(r: &[PeriodoRel]) -> Vec<(String, usize, usize, usize)> {
    r.iter().map(|p| (p.nome.clone(), p.documentos, p.docs_com_itens(), p.itens)).collect()
}

/// Tabelas de parâmetros e dos períodos.
pub fn parametros_html(config: &ConfigRel, n_periodos: Option<usize>, resultados: &[PeriodoRel], frequencia: Option<usize>, medida_temporal: Option<&str>, num: &mut dyn Numerador, rotulo: &str) -> String {
    let sufixo = if rotulo.is_empty() { String::new() } else { format!(" — {rotulo}") };
    let mut partes = vec![num.tabela(
        &strings(&["Parâmetro", "Valor"]),
        &parametros_linhas(config, n_periodos, resultados, frequencia, medida_temporal),
        &format!("Parâmetros adotados na análise{sufixo}."),
        &[],
        false,
    )];
    if !resultados.is_empty() {
        let linhas: Vec<Vec<String>> = periodos_info(resultados)
            .iter()
            .map(|i| vec![esc(&i.0), inteiro(i.1), inteiro(i.2), inteiro(i.3)])
            .collect();
        partes.push(num.tabela(
            &["Período".to_string(), "Documentos".into(), "Documentos com itens".into(), format!("Grupos de {}", item_unidade(&config.unidade))],
            &linhas,
            &format!("Períodos e documentos analisados{sufixo}."),
            &[1, 2, 3],
            false,
        ));
    }
    partes.join("\n")
}

// -------------------------------------------------------------- algoritmo

/// Como o código chega aos agrupamentos, em linguagem simples.
pub fn algoritmo_html(config: &ConfigRel, medida_temporal: Option<&str>, n_periodos: Option<usize>, com_duplo: bool, com_similitude: bool) -> String {
    let frequencia = config.minimo_frequencia;
    let unidade = item_unidade(&config.unidade);
    let mut p: Vec<String> = vec!["<div class=\"metodo\">".into()];

    // 1. Rede
    match config.matriz.as_str() {
        "CoOccurrence" => p.push(format!(
            "<p><strong>1. Rede.</strong> Cada item (um grupo de {unidade}, unificado pela edição da base) é um nó. Dois itens ficam \
             ligados quando aparecem no mesmo documento, e o peso da ligação é o número de documentos do período que contêm os dois \
             (co-ocorrência, c<sub>ij</sub>). A frequência f<sub>i</sub> de um item é o número de documentos que o contêm.</p>"
        )),
        "BasicCoupling" => p.push(format!(
            "<p><strong>1. Rede.</strong> Cada documento do período é um nó. Dois documentos ficam ligados quando têm {unidade} em \
             comum, e o peso é o número de itens compartilhados (acoplamento, c<sub>ij</sub>). A frequência f<sub>i</sub> de um \
             documento é o seu número de itens. Com referências como itens, é o acoplamento bibliográfico.</p>"
        )),
        m => {
            let quem = if m == "AggregatedCouplingBasedOnAuthor" { "autor" } else { "periódico" };
            p.push(format!(
                "<p><strong>1. Rede.</strong> Cada {quem} é um nó. Para cada um, reúne-se o conjunto de {unidade} de todos os seus \
                 documentos; dois nós ficam ligados quando esses conjuntos têm itens em comum, e o peso é o tamanho da interseção \
                 (acoplamento agregado, c<sub>ij</sub>). A frequência f<sub>i</sub> é o número de documentos do {quem}. Quem aparece \
                 em muitos documentos tende a se ligar a quase todos os demais.</p>"
            ));
        }
    }
    if config.unidade == "Institutions" {
        p.push(texto_ies_nomes());
    }

    // 2. Redução
    p.push(format!(
        "<p><strong>2. Redução.</strong> Antes de montar a rede, saem os termos ignorados e os itens que aparecem em menos de \
         {frequencia} {} (frequência mínima). Depois de montada, saem as ligações com peso menor que {}. Itens que ficam sem \
         nenhuma ligação continuam na rede, mas não entram em agrupamento.</p>",
        plural(frequencia, "documento", "documentos"),
        numero_py(config.minimo_coocorrencia)
    ));

    // 3. Similaridade
    let itens: String = SIMILARIDADES
        .iter()
        .map(|nome| {
            let marca = if *nome == config.similaridade { " <em>(adotada)</em>" } else { "" };
            format!(
                "<li>{}{marca}: <code class=\"formula\">{}</code> — {}.</li>",
                rotulo_similaridade(nome),
                formula(nome),
                explicacao_similaridade(nome)
            )
        })
        .collect();
    p.push(format!(
        "<p><strong>3. Normalização.</strong> O peso bruto de cada ligação é trocado por uma medida de similaridade que desconta a \
         frequência dos dois nós (c<sub>ij</sub> é o peso bruto; f<sub>i</sub> e f<sub>j</sub> são as frequências). As medidas \
         disponíveis são:</p><ul>{itens}</ul>"
    ));

    // 4. Agrupamento
    let extra = if matches!(config.unidade.as_str(), "Authors" | "Countries" | "Institutions") { texto_ies_componentes(config) } else { String::new() };
    p.push(format!("<p><strong>4. Agrupamento.</strong> {}{extra}</p>", texto_algoritmo(config)));

    // 5. Diagrama estratégico
    p.push(
        "<p><strong>5. Centralidade, densidade e quadrantes.</strong> Para cada agrupamento, a centralidade de Callon é 10 × a soma \
         dos pesos das ligações entre o agrupamento e nós de fora dele (quanto ele se liga ao resto da rede); a densidade de Callon \
         é 100 × a soma dos pesos das ligações internas ÷ o número de nós (quão coeso ele é). No diagrama estratégico, cada medida \
         vira uma faixa: a posição do agrupamento na ordenação do período dividida pelo número de agrupamentos (de 1/n a 1). O \
         plano é cortado em 0,5 nos dois eixos: <em>motor</em> (centralidade e densidade altas), <em>nicho</em> (só densidade alta), \
         <em>básico ou transversal</em> (só centralidade alta) e <em>emergente ou em declínio</em> (as duas baixas). Como as faixas \
         são posições, e não valores, o quadrante diz como o agrupamento se compara aos outros do mesmo período.</p>"
            .to_string(),
    );

    // 6. Documentos e desempenho
    p.push(format!("<p><strong>6. Documentos e desempenho.</strong> {}</p>", texto_mapeadores(config)));

    // 7. Evolução
    let evolui = medida_temporal.map(|m| !m.is_empty()).unwrap_or(false) && config.matriz == "CoOccurrence" && n_periodos.map(|n| n >= 2).unwrap_or(true);
    let sentenca_medida = if evolui {
        let mt = medida_temporal.unwrap();
        let nome = rotulo_temporal(mt);
        let f = formula(mt);
        let medida = if f.is_empty() { format!("o {nome}") } else { format!("o {nome} (<code class=\"formula\">{f}</code>)") };
        format!(
            "A medida temporal é {medida}, aplicada aos conjuntos de itens: f<sub>i</sub> e f<sub>j</sub> são os tamanhos dos dois \
             conjuntos e c<sub>ij</sub> o número de itens que têm em comum. "
        )
    } else {
        "A medida temporal é uma das mesmas medidas de similaridade, aplicada aos conjuntos de itens. ".to_string()
    };
    p.push(format!(
        "<p><strong>7. Evolução e sobreposição entre períodos.</strong> No mapa de evolução, um agrupamento de um período se liga a \
         um agrupamento do período seguinte quando os dois compartilham itens; cada agrupamento de origem mantém, no máximo, os três \
         elos mais fortes, e o elo é destacado quando um nó principal está no outro agrupamento. O mapa de sobreposição compara \
         todos os pares de períodos usando o conjunto de itens que ficou em agrupamentos em cada um. {sentenca_medida}</p>"
    ));
    p.push(
        "<p><strong>8. Dendrograma.</strong> Análise complementar sobre a mesma rede de cada período (até os 60 itens mais \
         frequentes). Cada item começa sozinho; a cada passo juntam-se os dois grupos mais próximos, com distância 1 − similaridade \
         (a similaridade da rede, dividida pelo maior valor se passar de 1; par sem ligação tem distância 1) e ligação média (média \
         das distâncias entre os membros). A altura da fusão é a distância em que os grupos se juntam. O corte sugerido fica no \
         maior salto entre fusões consecutivas; a correlação cofenética mede o quanto a árvore preserva as distâncias originais, e \
         ARI e NMI comparam o corte com os agrupamentos da rede (1 = idêntico).</p>"
            .to_string(),
    );
    let mut proximo = 9;
    if config.matriz == "CoOccurrence" && UNIDADES_LINHA_DO_TEMPO.contains(&config.unidade.as_str()) {
        p.push(texto_linha_do_tempo(config, proximo));
        proximo += 1;
    }
    if config.matriz == "CoOccurrence" {
        p.push(texto_densidade(proximo));
        proximo += 1;
    }
    if com_duplo {
        p.push(texto_duplo_mapa(proximo));
        proximo += 1;
    }
    if com_similitude {
        p.push(texto_similitude(proximo));
        proximo += 1;
    }
    p.push(texto_pivos(proximo));
    proximo += 1;
    p.push(texto_qualidade(config, proximo));
    p.push("</div>".into());
    p.join("\n")
}

fn texto_linha_do_tempo(config: &ConfigRel, numero: usize) -> String {
    let referencias = config.unidade == "References";
    let a = if referencias {
        "Cada referência fica no ano da própria obra. "
    } else {
        "Cada item fica no seu ano médio, a média dos anos dos documentos em que aparece, arredondada; a linha fina atrás do nó vai \
         do primeiro ao último ano do item e, quando o item tem rajada, um traço vermelho sobre essa linha marca os anos da rajada. "
    };
    let b = if referencias {
        ", calculadas sobre as referências citadas"
    } else if config.unidade == "Words" {
        ", calculadas só sobre as palavras-chave dos autores (a rede de palavras pode incluir também as de fonte)"
    } else {
        " (não há rajada para autores)"
    };
    format!(
        "<p><strong>{numero}. Linha do tempo.</strong> Figura complementar sobre o corpus completo (todos os documentos do projeto, \
         sem dividir em períodos), com os mesmos parâmetros e o mesmo algoritmo desta análise. Cada agrupamento vira uma faixa; só \
         aparecem os {} itens mais frequentes no total e, no máximo, {} por faixa. {a}O tamanho do nó segue a frequência. Os arcos \
         mostram as {} ligações mais fortes de cada nó dentro da faixa e as {} mais fortes entre faixas. O anel vermelho marca \
         rajadas (Kleinberg): as {} mais fortes do corpus, com pelo menos {} documentos{b}. Itens sem ano ficam de fora, com aviso; \
         os termos-descritor (presentes em mais de {} dos documentos) também, como nos pontos de virada.</p>",
        LT_MAX_NOS,
        LT_POR_FAIXA,
        LT_LIGACOES_POR_NO,
        LT_LIGACOES_CRUZADAS,
        LT_RAJADAS_MAXIMAS,
        LT_RAJADA_MIN_DOCUMENTOS,
        pct0(PIVOS_PROPORCAO_DESCRITOR)
    )
}

fn texto_densidade(numero: usize) -> String {
    format!(
        "<p><strong>{numero}. Mapa de densidade.</strong> Figura complementar sobre o corpus completo, com os mesmos parâmetros e o \
         mesmo algoritmo desta análise. Entram os 150 itens mais frequentes da rede (padrão; a tela aceita de 20 a 300). A \
         similaridade entre dois itens é a força da ligação na rede, dividida pela maior ligação entre os itens do mapa. As \
         posições vêm de um layout de atração e repulsão no plano (energia do tipo VOS): minimiza-se a soma de \
         s<sub>ij</sub>·d<sub>ij</sub>² − c·Σ ln d<sub>ij</sub> por descida de gradiente com momento (600 iterações, semente \
         fixa, c = 4), de modo que o resultado se repete; itens soltos, muito afastados do conjunto (além de 1,3 vez o percentil \
         85 da distância ao centro), têm o excesso de distância reduzido a 25% antes de escalar o mapa. A densidade em cada ponto \
         da imagem é a soma de núcleos gaussianos centrados nos itens, cada um com peso igual à frequência do item (número de \
         documentos); o desvio-padrão do núcleo (largura de banda) é a suavização × 0,8% da largura do quadro, com suavização \
         padrão 4 (de 1 a 9). A soma é normalizada pelo máximo, para ficar entre 0 e 1, e elevada a 0,8 para realçar as áreas \
         médias; a cor vai do branco (0) ao amarelo (1). Os rótulos aparecem por ordem de frequência, sem sobreposição e inteiros \
         dentro do quadro, até o máximo de 40; nomes com mais de 26 caracteres são cortados e o texto inteiro fica na dica do \
         item. O mapa não é calculado para acoplamento nem cocitação, cujos nós são documentos.</p>"
    )
}

fn texto_duplo_mapa(numero: usize) -> String {
    format!(
        "<p><strong>{numero}. Duplo mapa de áreas das revistas.</strong> Figura complementar sobre o corpus completo, que não \
         depende do tipo de rede da análise (nem do período). Cada referência de cada documento conta como uma citação da revista \
         do documento para a revista da referência (com os grupos de revistas editados na base); referências sem periódico \
         identificado e grupos ocultos ficam de fora, e o total delas é informado. À esquerda entram as 10 revistas que mais citam \
         (padrão; a tela aceita de 3 a 30) e, à direita, as 16 mais citadas por elas (de 5 a 40). A área de cada revista é \
         inferida por palavras do <em>nome</em> da revista: cada área tem uma lista de termos (palavra inteira, início de palavra \
         ou expressão, sem considerar acento nem caixa) e vale a primeira área da lista cujo termo aparece no nome, na ordem \
         Educação, Matemática e estatística, Saúde e psiquiatria, Psicologia, Ciências sociais, Multidisciplinar; a revista sem \
         nenhum termo fica em \"Não classificado\". É uma classificação <strong>aproximada</strong>: não usa categorias de base \
         alguma, nomes ambíguos podem cair na área errada e as listas (módulo <code>areas</code>, ou arquivo apontado por \
         <code>REDES_AREAS</code>, com fixação de área por revista) podem ser ajustadas. A figura traz a tabela revista → área, \
         com o termo que decidiu cada caso, e a porcentagem de citações e de revistas sem área. As faixas somam as citações entre \
         cada par de áreas, só entre as revistas desenhadas, com a mesma escala de largura em todas elas (no máximo 40 pixels por \
         citação, ajustada para que o total ocupe cerca de 360 pixels); a ordem das áreas da direita é a que cruza menos faixas. \
         As áreas não vêm de categorias de uma base e as faixas são contagens simples, sem z-score. O mapa não é calculado quando \
         a base não traz o periódico dos documentos ou o periódico das referências.</p>"
    )
}

fn texto_similitude(numero: usize) -> String {
    format!(
        "<p><strong>{numero}. Similitude dos resumos.</strong> Figura complementar sobre os resumos do corpus completo (a tela \
         também aceita um período); não depende do tipo de rede da análise. <em>Texto:</em> entram os resumos com pelo menos 15 \
         palavras, sem avisos de direitos autorais. O idioma (inglês, português ou espanhol) é detectado resumo a resumo: cada \
         palavra funcional vale 1 ponto para o idioma em que existe (meio ponto se está em dois, como \"de\"), e caracteres e \
         terminações típicas (ã, õ, ç, -ção; ñ, -ción; -tion, -ing) somam pontos; vence o idioma com mais pontos (inglês no \
         empate sem evidência). Frases longas com idioma claramente diferente, nos resumos bilíngues, são desconsideradas. Saem as \
         palavras vazias e os termos genéricos de resumo (\"objetivo\", \"results\", \"resultados\") do idioma do resumo, palavras \
         de até 2 letras e as que o usuário pedir para ignorar. <em>Lematização leve</em>, sem rede e sem bibliotecas externas: \
         plural e gênero, particípios e gerúndios (-ando, -ado, -endo/-indo, -iendo), 3ª pessoa do plural e pretérito (-am, -ou, \
         -aram, -en), advérbios em -mente e -ly, -ção/-ções, -dade/-dad, -ing/-ed em inglês; só une quando a forma mais simples \
         aparece nos resumos (ou quando duas formas apontam para o mesmo verbo), e \"estatístico\" se une a \"estatística\" (idem \
         em es e en). Formas de idiomas diferentes <strong>nunca</strong> se fundem. <em>Palavras:</em> as 60 formas mais \
         frequentes (a tela aceita de 30 a 100) que aparecem em ao menos 3 segmentos (2 quando o idioma tem menos de 12); com \
         vários idiomas, cada um recebe ao menos 10 palavras e o resto é dividido pelo número de resumos, e idiomas com menos de 5 \
         resumos ficam de fora. <em>Segmento:</em> o resumo inteiro (padrão) ou grupos de frases de cerca de 14 palavras. \
         <em>Índice</em> de associação entre cada par de palavras, a partir dos segmentos em que aparecem juntas: Jaccard (padrão, \
         c/(a+b−c)), cosseno (c/√(ab)), binomial (−log10 da probabilidade hipergeométrica de ao menos c coocorrências) ou \
         coocorrência bruta. <em>Árvore máxima:</em> algoritmo de Kruskal, que escolhe as ligações em ordem decrescente de índice \
         sem fechar ciclos (empate decidido pela ordem alfabética), de modo que o grafo mantém só os laços mais fortes necessários; \
         palavras que nunca coocorrem ficam em componentes separados. A tela soma <em>arestas extras</em> (padrão 20% do número de \
         ligações da árvore, de 0 a 50%), as mais fortes fora da árvore, tracejadas, só para a leitura. <em>Blocos:</em> \
         comunidades pelo método de Louvain sobre a árvore, com resolução 1 e semente 7; o resultado é determinístico. \
         <em>Desenho:</em> cada bloco é arrumado sozinho (molas e separação de caixas) e os blocos são dispostos entre si sem que \
         as manchas se toquem; o tamanho do ponto cresce com a raiz da frequência (raio de 4,5 a 14); a largura dos rótulos vem de \
         uma tabela embutida de larguras com folga de 20%, sem depender de fontes. A figura é acompanhada da tabela de parâmetros \
         e da tabela das palavras (frequência, bloco e grau). Não usa etiquetas gramaticais nem dicionário de lemas; a \
         lematização é aproximada e a escolha das palavras, do índice e do segmento muda a figura.</p>"
    )
}

fn texto_pivos(numero: usize) -> String {
    format!(
        "<p><strong>{numero}. Pontos de virada e sigma.</strong> Em cada período, a intermediação de cada nó (quantos caminhos \
         mínimos entre outros pares passam por ele) é normalizada pelo número de pares possíveis, (n − 1)(n − 2)/2, e vai de 0 a \
         1. É ponto de virada o nó com intermediação no decil superior (percentil 90 entre os nós com intermediação positiva) \
         <em>e</em> com vizinhos em pelo menos dois agrupamentos. Termos presentes em mais de 50% dos documentos do período \
         (termo-descritor) saem do ranking, porque descrevem o corpus em vez de distinguir temas. Com menos de {PIVOS_MINIMO_NOS} \
         nós, a lista é só indício e o relatório avisa. O sigma (Chen, 2006) é (intermediação + 1) elevado à força da rajada do \
         termo; só existe para quem tem rajada (palavras-chave e referências em co-ocorrência) e a coluna só aparece quando algum \
         ponto de virada tem rajada. Como o sigma é um produto (o logaritmo do sigma é a força da rajada vezes ln(intermediação + \
         1)), entre os pontos de virada, que já têm intermediação alta, quem ordena o ranking por sigma é sobretudo a \
         intermediação: nas redes testadas a correlação de Spearman do sigma com a intermediação ficou entre 0,89 e 0,97, e com a \
         força da rajada, entre 0,21 e 0,60. A rajada das palavras-chave é calculada só sobre as palavras-chave dos autores (a \
         rede de palavras pode incluir também as de fonte), e a das referências, sobre as referências citadas. A tabela lista no \
         máximo {TOPO_PIVOS} pontos de virada.</p>"
    )
}

fn texto_qualidade(config: &ConfigRel, numero: usize) -> String {
    let g = Q_GRUPO_GRANDE;
    let mut p: Vec<String> = Vec::new();
    p.push(format!(
        "<p><strong>{numero}. Qualidade do mapa.</strong> O selo diz se o mapa é feito de agrupamentos de verdade: olha quantos \
         itens estão em agrupamentos de {g} ou mais itens e se a rede se partiu em pares e itens isolados. Duas medidas, descritas \
         a seguir, dizem se a divisão em agrupamentos se destaca na rede (a <em>nitidez</em>).</p>"
    ));
    p.push(format!(
        "<ul><li><em>Modularidade Q</em> (força da divisão): compara as ligações que ficam dentro dos agrupamentos com as que se \
         esperariam se a rede fosse sorteada, ponderando pela similaridade; vai de cerca de 0 (como dividir ao acaso) a perto de 1 \
         (grupos bem separados). O item sem agrupamento conta como um grupo de um item só. Compara-se com o <em>Q do Louvain</em> \
         porque o Louvain procura justamente o maior Q possível: se o Q desta divisão é bem menor, existe outra divisão mais \
         nítida (razão Q/Q<sub>Louvain</sub> abaixo de 0,60).</li><li><em>Silhueta</em>: para cada item, quanto mais perto ele \
         está do próprio agrupamento do que do agrupamento vizinho mais próximo (distância = 1 − similaridade normalizada, como no \
         dendrograma), de −1 a 1; valor negativo indica item possivelmente mal alocado. Agrupamentos com menos de \
         {Q_MINIMO_NOS_SILHUETA} itens ficam fora (a silhueta de um grupo tão pequeno não informa nada) e aparecem com “—”. Em \
         redes com mais de {Q_LIMITE_NOS} itens agrupados a silhueta é dispensada, para a análise não ficar lenta.</li></ul>"
    ));
    p.push(format!(
        "<p><strong>Selo de qualidade.</strong> <em>Ruim</em>: menos de 50% dos itens em agrupamentos de {g} ou mais itens (o \
         resto está solto ou em pares e trios, e há pouco o que ler). <em>Atenção</em>: de 50% a menos de 80% dos itens em \
         agrupamentos de {g} ou mais; ou rede fragmentada (há mais componentes do que a metade dos itens, isto é, o componente \
         médio tem menos de 2 itens, quase só itens isolados e pares). <em>OK</em>: 80% ou mais dos itens em agrupamentos de {g} \
         ou mais, e rede não fragmentada. <em>Indefinido</em>: menos de {Q_MINIMO_NOS} itens, menos de 2 agrupamentos ou rede sem \
         ligações com valor positivo; nesses casos nenhum número é mostrado como 0, porque não houve avaliação.</p>"
    ));
    p.push(format!(
        "<p><strong>Avisos de nitidez.</strong> Q abaixo de 0,30 (abaixo de 0,15, “muito fraca”); razão Q/Q<sub>Louvain</sub> \
         abaixo de 0,60; silhueta média abaixo de 0,05 (abaixo de 0,00, os itens ficam em média mais perto de outros grupos); e \
         mais de 30% dos itens com silhueta negativa geram um aviso, mas <em>não mudam o selo</em>. Em 43 mapas de bases reais \
         julgados à vista, esses sinais ficaram baixos tanto em mapas legíveis quanto em ilegíveis: redes densas (acoplamento \
         bibliográfico, referências) dão Q e silhueta baixos mesmo com agrupamentos grandes e coesos, e redes de pares isolados \
         dão Q alto sem nada a ler. Já a fração de itens em agrupamentos de {g} ou mais separou os dois casos.</p>"
    ));
    p.push(
        "<p><strong>Aviso.</strong> O selo é uma leitura prudente da estrutura, não uma aprovação: <em>Atenção</em> <em>não \
         invalida o mapa</em>, só marca que parte dos itens está solta ou em grupos pequenos. <em>Ruim</em> quer dizer que, com \
         estes parâmetros, quase nada forma agrupamento de verdade; vale tentar uma frequência mínima maior.</p>"
            .to_string(),
    );
    if config.unidade == "Authors" {
        p.push(
            "<p><strong>Atenção com autores.</strong> Em redes de coautoria, um Q alto é em geral um artefato: cada documento liga \
             todos os seus autores entre si e a rede se parte em muitos grupos pequenos e isolados, que a modularidade premia sem \
             que haja estrutura temática. Leia o Q junto com o aviso de rede fragmentada e com o número de itens por agrupamento. \
             Por isso, com autores, o selo nunca é <em>OK</em>: no máximo <em>Atenção</em>.</p>"
                .to_string(),
        );
    }
    p.push(format!(
        "<p><strong>{}. Rótulos dos agrupamentos.</strong> O <em>rótulo novo</em> traz os termos que mais distinguem o \
         agrupamento dos demais documentos do mesmo período, pela razão de verossimilhança de Dunning (G²): comparam-se os \
         documentos do núcleo do agrupamento com todos os outros documentos do período, e sobem os termos bem mais frequentes no \
         agrupamento. Os termos vêm das palavras do título, das palavras-chave dos autores (expressão inteira) e, do resumo, \
         apenas de pares de palavras (bigramas), porque palavra solta de resumo é genérica demais; um termo precisa aparecer em \
         pelo menos {ROT_MINIMO_NO_GRUPO} documentos do agrupamento, e singular, plural e acento são unidos. É preciso ao menos \
         {ROT_MINIMO_DOCUMENTOS} documentos no núcleo; com {ROT_MINIMO_DOCUMENTOS} a {} o rótulo sai marcado como \
         <em>(indicativo)</em>, e com {ROT_LIMITE_INDICATIVO} ou mais é firme. Agrupamento que cobre mais de \
         {ROT_COBERTURA_MAXIMA}% dos documentos do período não recebe rótulo (não distingue nada). O rótulo atual, tirado do item \
         central, continua como subtítulo, e onde não há rótulo novo vale só ele. Nas tabelas, <em>Ano médio</em> é a média do \
         ano de publicação dos documentos do núcleo.</p>",
        numero + 1,
        ROT_LIMITE_INDICATIVO - 1
    ));
    p.join("\n")
}

fn texto_ies_nomes() -> String {
    "<p><em>Nomes das instituições.</em> A instituição de cada afiliação é o trecho que a nomeia (por exemplo, o segmento com \
     \"Universidade\" ou \"University\"). Antes de montar a rede, as variantes do mesmo nome são unidas, e só quando a \
     normalização é inequívoca: caixa, acentos, pontuação e espaços não contam; ligações (de, of, the) são desprezadas; Univ., \
     University, Universidade e Universidad valem o mesmo (e também instituto/institute e faculdade/faculty); sigla entre \
     parênteses e país depois de hífen ou barra são ignorados. Não se une quando a ordem das palavras muda, quando falta ou sobra \
     uma palavra, nem por semelhança de grafia. O mesmo nome com países diferentes não é unido entre países. A grafia adotada é \
     a mais frequente. Cada união fica registrada na tabela \"variantes unidas\", com a grafia adotada, as variantes, o número \
     de documentos e o motivo.</p>"
        .to_string()
}

fn texto_ies_componentes(config: &ConfigRel) -> String {
    let minimo = config.agrupamento_minimo;
    if minimo <= 1 {
        return String::new();
    }
    let plural = subst_filtro(&config.unidade).1;
    let redes = match config.unidade.as_str() {
        "Authors" => "de coautoria",
        "Countries" => "de países",
        _ => "de instituições",
    };
    let padrao = if config.unidade == "Institutions" { 3 } else { 1 };
    format!(
        " Na rede {redes}, antes de aceitar um agrupamento calculam-se os componentes conexos da rede (conjuntos de {plural} \
         ligados entre si, direta ou indiretamente). Componentes com menos de {minimo} {plural} não viram agrupamento e não \
         entram nos halos: seus nós ficam como \"sem agrupamento\" (para Q e silhueta, cada um conta como grupo próprio). Nenhum \
         nó nem aresta é apagado e a frequência mínima não muda. O parâmetro é o tamanho mínimo do agrupamento (padrão {padrao}, \
         aqui {minimo})."
    )
}

fn texto_algoritmo(config: &ConfigRel) -> String {
    let (tmin, tmax) = (config.tamanho_minimo, config.tamanho_maximo);
    let nome = rotulo_algoritmo(&config.algoritmo);
    match config.algoritmo.as_str() {
        "CentersSimples" => format!(
            "<em>{nome}</em> (centros simples). As ligações são ordenadas da mais forte para a mais fraca e percorridas em \
             sequência, contando quantas vezes cada nó aparece. Quando um nó chega a {} ligações, ele vira o centro de um \
             agrupamento e leva consigo os vizinhos dessas ligações (até {tmax} nós). Todas as ligações que tocam o agrupamento \
             saem da lista e a varredura continua. Se a lista termina sem formar agrupamento, o limite cai uma unidade e a \
             varredura recomeça, até o mínimo de {tmin} nós. O centro dá o nome ao agrupamento; nós que não chegam a nenhum \
             ficam de fora. O ponto de corte não é usado.",
            tmax as i64 - 1
        ),
        "AverageLink" | "CompleteLink" | "SingleLink" | "SumLink" => {
            let criterio = match config.algoritmo.as_str() {
                "AverageLink" => "a média dos pesos das ligações que existem entre os dois grupos",
                "CompleteLink" => "o menor peso entre as ligações que existem entre os dois grupos",
                "SingleLink" => "o maior peso entre as ligações que existem entre os dois grupos",
                _ => "a soma dos pesos das ligações entre os dois grupos",
            };
            format!(
                "<em>{nome}</em> (aglomeração hierárquica). Cada nó começa sozinho. A cada passo, juntam-se os dois grupos ligados \
                 com o maior valor, que aqui é {criterio}; pares sem nenhuma ligação nunca se juntam. Só entram na disputa pares \
                 com valor maior ou igual ao ponto de corte ({}). O processo para quando não há mais par elegível ou quando a \
                 melhor junção passaria de {tmax} nós. Grupos com pelo menos {tmin} nós viram agrupamentos; os demais ficam de \
                 fora. O nó principal é o último nó do agrupamento cuja similaridade média com os vizinhos é menor que a do \
                 primeiro nó (critério fixo, que não escolhe o máximo).",
                decimal(config.corte)
            )
        }
        _ => format!(
            "<em>{nome}</em> (detecção de comunidades por modularidade). Cada nó começa numa comunidade própria e é movido para a \
             comunidade vizinha que mais aumenta a modularidade, usando os pesos normalizados; depois as comunidades viram nós de \
             uma rede menor e o processo se repete até nada mais mudar. Em seguida, o tamanho é ajustado: comunidades com menos de \
             {tmin} nós são absorvidas pela vizinha de ligação total mais forte, e as com mais de {tmax} nós são partidas, \
             retirando as ligações mais fracas até que o grupo se separe. O nó principal é o de maior soma de ligações dentro do \
             grupo. O ponto de corte não é usado."
        ),
    }
}

fn texto_mapeadores(config: &ConfigRel) -> String {
    let descricao = |m: &str| -> Option<String> {
        Some(match m {
            "nucleo" => "<em>núcleo</em>: documentos que contêm os dois itens de pelo menos uma ligação interna do agrupamento".to_string(),
            "interseccao" => "<em>interseção</em>: documentos que contêm todos os itens do agrupamento".to_string(),
            "secundarios" => "<em>secundários</em>: documentos presentes em um número ímpar de itens do agrupamento (diferença simétrica acumulada)".to_string(),
            "kcore" => format!("<em>k-core</em>: documentos com pelo menos {} itens do agrupamento", config.k_core),
            "uniao" => "<em>união</em>: documentos que contêm algum item do agrupamento".to_string(),
            "acoplamento" => "<em>acoplamento</em>: os próprios nós, que já são documentos".to_string(),
            _ => return None,
        })
    };
    let usados: Vec<String> = config.mapeadores.iter().filter_map(|m| descricao(m)).collect();
    let mut texto = if usados.is_empty() { String::new() } else { format!("Cada agrupamento recebe os documentos do mapeador adotado — {}. ", usados.join("; ")) };
    if config.matriz == "BasicCoupling" && !config.mapeadores.iter().any(|m| m == "acoplamento") {
        texto.push_str(
            "Atenção: no acoplamento básico os nós já são documentos, e os mapeadores por itens não os encontram; o adequado é o \
             mapeador de acoplamento, e com os adotados as medidas de desempenho saem zeradas ou quase. ",
        );
    }
    texto.push_str(
        "Sobre esses documentos calculam-se, a partir das citações registradas na base (sem recontar citações): o <em>índice \
         h</em>, o maior h tal que h documentos têm pelo menos h citações; o <em>índice g</em>, o maior g tal que os g documentos \
         mais citados somam pelo menos g² citações; o <em>hg</em>, raiz de h × g; e o <em>q2</em>, raiz de h × a mediana das \
         citações dos h documentos do núcleo h (a mediana superior, o maior dos dois valores centrais, quando h é par). \
         Documentos sem citação não entram em h, g e q2. Também são calculados a soma, a média, o mínimo e o máximo de citações e \
         o número de documentos.",
    );
    texto
}

// ------------------------------------------------------- ies e filtro

/// Nota do efeito do tamanho mínimo do agrupamento (autores e países; IES tem a sua).
pub fn filtro_agrupamento_html(p: &PeriodoRel, unidade: &str) -> String {
    let Some(info) = &p.filtro_agrupamento else { return String::new() };
    if info.minimo <= 1 || unidade == "Institutions" {
        return String::new();
    }
    let plural = subst_filtro(unidade).1;
    format!(
        "<p class=\"nota\">Componentes com menos de {} {plural} não viram agrupamento e ficam sem agrupamento: {} grupos antes do \
         filtro, {} depois; {} {plural} ficaram sem agrupamento ({} isolados).</p>",
        info.minimo,
        info.grupos_antes,
        info.grupos_depois,
        inteiro(info.nos_sem_agrupamento),
        inteiro(info.isolados)
    )
}

/// Tabela "variantes unidas" e nota dos componentes sem agrupamento (rede de IES).
pub fn ies_html(p: &PeriodoRel, num: &mut dyn Numerador, rotulo: &str) -> String {
    let Some(info) = &p.ies else { return String::new() };
    let sufixo = if rotulo.is_empty() { String::new() } else { format!(" — {rotulo}") };
    let mut partes = Vec::new();
    let mut linhas = Vec::new();
    for u in &info.unioes {
        for v in &u.variantes {
            linhas.push(vec![esc(&u.adotado), esc(&v.nome), inteiro(v.documentos), esc(&v.motivo)]);
        }
    }
    if !linhas.is_empty() {
        partes.push(num.tabela(
            &strings(&["Nome adotado", "Variante", "Documentos", "Motivo da união"]),
            &linhas,
            &format!(
                "Variantes unidas{sufixo}: {} {} variantes do nome unidas.",
                info.unioes.len(),
                plural(info.unioes.len(), "instituição teve", "instituições tiveram")
            ),
            &[2],
            false,
        ));
    } else {
        partes.push(
            "<p class=\"nota\">Variantes unidas: nenhuma. Nenhum nome de instituição tinha variante inequívoca nesta base.</p>".to_string(),
        );
    }
    let nota = if info.componente_minimo > 1 {
        format!(
            "Componentes com menos de {} instituições não viram agrupamento e ficam sem agrupamento: {} {} de 2 a {} instituições e \
             {} {}.",
            info.componente_minimo,
            info.componentes_pequenos,
            plural(info.componentes_pequenos, "componente", "componentes"),
            info.componente_minimo - 1,
            info.isolados,
            plural(info.isolados, "instituição isolada", "instituições isoladas")
        )
    } else {
        "Todos os componentes podem virar agrupamento.".to_string()
    };
    partes.push(format!("<p class=\"nota\">{nota}</p>"));
    partes.join("\n")
}

// ------------------------------------------------------------ indicadores

pub struct IndicadorEscopo {
    pub escopo: String,
    pub documentos: Option<usize>,
    pub documentos_com_itens: Option<usize>,
    pub grafias: Option<usize>,
    pub grupos: Option<usize>,
    pub itens_reduzidos: Option<usize>,
    pub rede_nos: Option<usize>,
    pub rede_arestas: Option<usize>,
    pub agrupamentos: usize,
    pub maior_agrupamento: usize,
    pub itens_agrupados: Option<usize>,
    pub itens_sem_agrupamento: Option<usize>,
    /// motor, nicho, básico, emergente.
    pub quadrantes: [usize; 4],
    pub qualidade: Option<Qualidade>,
}

fn indicadores_do_periodo(p: &PeriodoRel) -> IndicadorEscopo {
    let mut q = [0usize; 4];
    for g in &p.grupos {
        q[match quadrante_chave(g) {
            "motor" => 0,
            "nicho" => 1,
            "basico" => 2,
            _ => 3,
        }] += 1;
    }
    IndicadorEscopo {
        escopo: p.nome.clone(),
        documentos: Some(p.documentos),
        documentos_com_itens: Some(p.docs_com_itens()),
        grafias: p.grafias,
        grupos: Some(p.itens),
        itens_reduzidos: Some(p.itens_reduzidos),
        rede_nos: Some(p.rede_nos),
        rede_arestas: Some(p.rede_arestas),
        agrupamentos: p.grupos.len(),
        maior_agrupamento: p.maior_grupo(),
        itens_agrupados: Some(p.agrupados()),
        itens_sem_agrupamento: Some(p.sem_agrupamento()),
        quadrantes: q,
        qualidade: p.qualidade.clone(),
    }
}

/// Indicadores por análise: primeiro o corpus completo, depois cada período.
pub fn indicadores(resultados: &[PeriodoRel], total: Option<&TotalRel>) -> Vec<IndicadorEscopo> {
    if resultados.is_empty() {
        return vec![];
    }
    let lista: Vec<IndicadorEscopo> = resultados.iter().map(indicadores_do_periodo).collect();
    if lista.len() == 1 {
        return lista;
    }
    let soma = |f: &dyn Fn(&PeriodoRel) -> usize| resultados.iter().map(f).sum::<usize>();
    let mut q = [0usize; 4];
    for l in &lista {
        for i in 0..4 {
            q[i] += l.quadrantes[i];
        }
    }
    let t = total.cloned().unwrap_or_default();
    let tot = IndicadorEscopo {
        escopo: "Todos os períodos".into(),
        documentos: t.documentos.or(Some(soma(&|p| p.documentos))),
        documentos_com_itens: t.documentos_com_itens.or(Some(soma(&|p| p.docs_com_itens()))),
        grafias: t.grafias,
        grupos: t.itens,
        itens_reduzidos: t.itens_reduzidos,
        rede_nos: None,
        rede_arestas: None,
        agrupamentos: lista.iter().map(|x| x.agrupamentos).sum(),
        maior_agrupamento: lista.iter().map(|x| x.maior_agrupamento).max().unwrap_or(0),
        itens_agrupados: t.itens_agrupados,
        itens_sem_agrupamento: None,
        quadrantes: q,
        qualidade: None,
    };
    let mut v = vec![tot];
    v.extend(lista);
    v
}

/// Cabeçalho e linhas (já formatadas) da tabela de indicadores.
pub fn indicadores_linhas(dados: &[IndicadorEscopo], config: &ConfigRel, frequencia: Option<usize>) -> (Vec<String>, Vec<Vec<String>>) {
    let frequencia = frequencia_efetiva(config, frequencia);
    let unidade = item_unidade(&config.unidade);
    let nomes = nomes_quadrantes(&config.unidade);

    let numero_ = |v: Option<usize>| v.map(inteiro).unwrap_or_else(|| "—".into());
    let rede = |x: &IndicadorEscopo| match (x.rede_nos, x.rede_arestas) {
        (Some(n), Some(a)) => format!("{} {} · {} {}", inteiro(n), plural(n, "nó", "nós"), inteiro(a), plural(a, "aresta", "arestas")),
        _ => "—".into(),
    };
    let quadrantes = |x: &IndicadorEscopo| {
        if x.agrupamentos == 0 {
            return "—".to_string();
        }
        (0..4).map(|k| format!("{} {}", nomes[k], x.quadrantes[k])).collect::<Vec<_>>().join(" · ")
    };
    let maior = |x: &IndicadorEscopo| {
        let n = x.maior_agrupamento;
        if n > 0 {
            format!("{} {}", inteiro(n), plural(n, "nó", "nós"))
        } else {
            "—".into()
        }
    };

    let mut cab = vec!["Indicador".to_string()];
    cab.extend(dados.iter().map(|x| x.escopo.clone()));
    let mut linhas: Vec<Vec<String>> = Vec::new();
    let mut add = |nome: String, f: &dyn Fn(&IndicadorEscopo) -> String| {
        let mut l = vec![nome];
        l.extend(dados.iter().map(|x| f(x)));
        linhas.push(l);
    };
    add("Documentos".into(), &|x| numero_(x.documentos));
    add("Documentos com pelo menos um item".into(), &|x| numero_(x.documentos_com_itens));
    if dados.iter().any(|x| x.grafias.is_some()) {
        add("Grafias distintas na base".into(), &|x| numero_(x.grafias));
    }
    add(format!("Grupos de {unidade} (itens)"), &|x| numero_(x.grupos));
    add(format!("Itens após redução (freq. ≥ {frequencia})"), &|x| numero_(x.itens_reduzidos));
    add("Rede".into(), &|x| rede(x));
    add(format!("Agrupamentos (freq. ≥ {frequencia})"), &|x| inteiro(x.agrupamentos));
    add("Maior agrupamento".into(), &|x| maior(x));
    add("Nós em agrupamentos".into(), &|x| numero_(x.itens_agrupados));
    add("Nós da rede sem agrupamento".into(), &|x| numero_(x.itens_sem_agrupamento));
    add("Quadrantes".into(), &|x| quadrantes(x));
    if dados.iter().any(|x| x.qualidade.is_some()) {
        let q = |x: &IndicadorEscopo, f: &dyn Fn(&Qualidade) -> Option<f64>, casas: usize, pct: bool| -> String {
            match &x.qualidade {
                Some(ql) if ql.nivel != "indefinido" => match f(ql) {
                    Some(v) => format!("{}{}", n2(Some(v), if pct { 0 } else { casas }), if pct { "%" } else { "" }),
                    None => "—".into(),
                },
                _ => "—".into(),
            }
        };
        let pct_agrupados = |x: &IndicadorEscopo| match &x.qualidade {
            Some(ql) if ql.n_nos > 0 => {
                if ql.nivel == "indefinido" && ql.pct_agrupados == 0.0 {
                    "—".to_string()
                } else {
                    format!("{}%", n2(Some(ql.pct_agrupados), 0))
                }
            }
            _ => "—".into(),
        };
        let pct_grandes = |x: &IndicadorEscopo| match &x.qualidade {
            Some(ql) if ql.n_nos > 0 && ql.nivel != "indefinido" => match ql.pct_em_grupos_grandes {
                Some(v) => format!("{}%", n2(Some(v), 0)),
                None => "—".into(),
            },
            _ => "—".into(),
        };
        add("Modularidade Q".into(), &|x| q(x, &|ql| ql.q, 2, false));
        add("Q do Louvain (referência)".into(), &|x| q(x, &|ql| ql.q_louvain, 2, false));
        add("Silhueta média".into(), &|x| q(x, &|ql| ql.silhueta_media, 2, false));
        add("% dos itens em agrupamentos".into(), &|x| pct_agrupados(x));
        add(format!("% dos itens em agrupamentos de {Q_GRUPO_GRANDE}+ itens"), &|x| pct_grandes(x));
        add("Qualidade do mapa".into(), &|x| match &x.qualidade {
            Some(ql) => selo_qualidade(&ql.nivel),
            None => "—".into(),
        });
    }
    (cab, linhas.into_iter().map(|l| std::iter::once(esc(&l[0])).chain(l.into_iter().skip(1)).collect()).collect())
}

fn avisos_html(dados: &[IndicadorEscopo]) -> String {
    let por_periodo: Vec<&IndicadorEscopo> = dados.iter().filter(|x| x.qualidade.is_some()).collect();
    let multiplos = por_periodo.len() > 1;
    let mut blocos = Vec::new();
    for x in por_periodo {
        let avisos = &x.qualidade.as_ref().unwrap().avisos;
        if avisos.is_empty() {
            continue;
        }
        let itens: String = avisos.iter().map(|a| format!("<li>{}</li>", esc(a))).collect();
        let titulo = if multiplos { format!("Avisos de qualidade — {}", esc(&x.escopo)) } else { "Avisos de qualidade".to_string() };
        blocos.push(format!("<p><strong>{titulo}</strong></p><ul>{itens}</ul>"));
    }
    if blocos.is_empty() {
        return String::new();
    }
    format!(
        "<div class=\"avisos-qualidade\">{}<p class=\"fonte\">Como ler o selo: veja “Qualidade do mapa e rótulos” em “Como \
         funciona”. Atenção não invalida o mapa; os avisos de nitidez não mudam o selo.</p></div>",
        blocos.join("")
    )
}

/// Tabela de indicadores mais a nota de leitura.
pub fn indicadores_html(resultados: &[PeriodoRel], total: Option<&TotalRel>, config: &ConfigRel, frequencia: Option<usize>, num: &mut dyn Numerador, rotulo: &str) -> String {
    if resultados.is_empty() {
        return String::new();
    }
    let dados = indicadores(resultados, total);
    let (cab, linhas) = indicadores_linhas(&dados, config, frequencia);
    let sufixo = if rotulo.is_empty() { String::new() } else { format!(" — {rotulo}") };
    let legenda = if dados.len() == 1 {
        format!("Indicadores da análise{sufixo}.")
    } else {
        format!("Indicadores da análise, para todos os períodos e por período{sufixo}.")
    };
    let mut nota = "Rede: nós e arestas depois da redução e do corte de ligações. Quadrantes: regra descrita em “Como funciona”.".to_string();
    if dados.len() > 1 {
        nota = format!(
            "Todos os períodos: documentos e itens são a união dos períodos; agrupamentos e quadrantes são somados; o maior \
             agrupamento é o maior dos períodos; a rede não se soma entre períodos. {nota}"
        );
    }
    let numericas: Vec<usize> = (1..cab.len()).collect();
    format!(
        "<div class=\"rolagem\">{}</div><p class=\"fonte\">{}</p>{}",
        num.tabela(&cab, &linhas, &legenda, &numericas, false),
        esc(&nota),
        avisos_html(&dados)
    )
}

/// Bloco completo: parâmetros, indicadores e método.
#[allow(clippy::too_many_arguments)]
pub fn metodo_html(
    config: &ConfigRel,
    n_periodos: Option<usize>,
    resultados: &[PeriodoRel],
    total: Option<&TotalRel>,
    frequencia: Option<usize>,
    medida_temporal: Option<&str>,
    num: &mut dyn Numerador,
    rotulo: &str,
    titulo: &mut dyn FnMut(&str) -> String,
    com_duplo: bool,
    com_similitude: bool,
) -> String {
    let mut partes = vec![titulo("Parâmetros adotados"), parametros_html(config, n_periodos, resultados, frequencia, medida_temporal, num, rotulo)];
    if !resultados.is_empty() {
        partes.push(titulo("Indicadores"));
        partes.push(indicadores_html(resultados, total, config, frequencia, num, rotulo));
    }
    partes.push(titulo("Como funciona"));
    partes.push(algoritmo_html(config, medida_temporal, n_periodos, com_duplo, com_similitude));
    partes.join("\n")
}

// ------------------------------------------------------------ bibliometria

/// Método da visão geral descritiva.
pub fn metodo_bibliometria_html(num: &mut dyn Numerador, parametros: Option<&[Vec<String>]>) -> String {
    let (s, gama, minimo, limite, vazias, academicas) = (2.0, 1.0, 3, 20, 320usize, 110usize);
    let padrao: Vec<Vec<String>> = vec![
        vec!["Rajadas: razão entre a taxa de rajada e a taxa de base (s)".into(), decimal(s)],
        vec!["Rajadas: custo de entrar no estado de rajada (γ)".into(), format!("{} × ln(número de anos)", decimal(gama))],
        vec!["Rajadas: mínimo de documentos do termo".into(), minimo.to_string()],
        vec!["Rankings: itens mostrados".into(), limite.to_string()],
        vec!["Nuvem de palavras: termos desenhados".into(), "70".into()],
        vec!["Nuvem de títulos: palavras vazias (português, espanhol e inglês)".into(), inteiro(vazias)],
        vec!["Nuvem de títulos: termos acadêmicos genéricos".into(), inteiro(academicas)],
        vec!["Nuvem de títulos: mínimo para uma expressão de duas palavras".into(), "2 títulos".into()],
        vec!["Zipf: posições usadas no ajuste".into(), "até 200".into()],
        vec!["Bradford: zonas".into(), "3, com cerca de um terço dos documentos cada".into()],
    ];
    let parametros: Vec<Vec<String>> = parametros.map(|p| p.to_vec()).unwrap_or(padrao);
    let linhas: Vec<Vec<String>> = parametros.iter().map(|l| l.iter().map(|c| esc(c)).collect()).collect();
    let texto = format!(
        "<div class=\"metodo\">\n\
<p><strong>Contagens.</strong> Autores, palavras-chave, fontes, instituições e países contam documentos: cada documento vale 1 \
para cada nome, por mais que o nome se repita nele. Quando a base foi editada, vale o nome do grupo; grupos marcados como parada \
ficam de fora. As citações são as registradas na base de origem na data da exportação, somadas por documento.</p>\n\
<p><strong>Produção anual.</strong> O ano é o da data de publicação (ou o ano do registro, se faltar). A figura mostra os \
documentos por ano, com os anos vazios entre o primeiro e o último, e as citações somadas dos documentos publicados em cada ano, \
não as citações recebidas naquele ano. O crescimento anual é a taxa composta entre a produção do primeiro e a do último ano, \
(n<sub>último</sub> ÷ n<sub>primeiro</sub>)<sup>1/anos</sup> − 1, e por isso oscila com um único ano atípico.</p>\n\
<p><strong>Autores, fontes, instituições (IES) e países.</strong> Cada ranking mostra os {limite} primeiros por número de \
documentos, com desempate alfabético, e as citações somadas desses documentos. As instituições vêm do nome da organização na \
afiliação, unificado pelos apelidos cadastrados; os países vêm do país da afiliação. O <em>índice h</em> de cada autor usa só os \
documentos do corpus: é o maior h tal que h de seus documentos têm pelo menos h citações.</p>\n\
<p><strong>Lei de Lotka.</strong> Conta quantos autores publicaram 1, 2, 3… documentos e compara a proporção observada com a \
esperada, (6 ÷ π²) ÷ n². O expoente β é o oposto da inclinação da reta de mínimos quadrados entre log n e log da proporção de \
autores, exigindo pelo menos três valores distintos de n; o valor clássico é 2.</p>\n\
<p><strong>Lei de Bradford.</strong> Ordena as fontes pelo número de documentos e as divide em três zonas que reúnem cerca de um \
terço dos documentos cada. A fonte que cruza o limite fica na zona em que começa. O multiplicador de cada zona é o número de \
fontes dela dividido pelo da primeira.</p>\n\
<p><strong>Lei de Zipf.</strong> Ordena as palavras-chave dos autores pela frequência em documentos e ajusta uma reta, por \
mínimos quadrados, entre log da posição e log da frequência, nas primeiras 200 posições. O expoente é o oposto da inclinação; o \
valor clássico é 1.</p>\n\
<p><strong>Fluxo Autor – País – IES (Sankey).</strong> Cada faixa liga um nome da coluna da esquerda a um da coluna seguinte e \
sua largura é o número de documentos em que o par aparece. O vínculo autor–instituição é exato quando a base traz a afiliação de \
cada autor (Scopus); é inferido quando o documento tem uma só instituição ou um só país; documentos ambíguos ficam de fora e o \
relatório diz quantos. Entram os autores, países e instituições mais frequentes.</p>\n\
<p><strong>Nuvem de palavras-chave.</strong> Mostra as palavras-chave dos autores, contadas por documento. Os termos guardados \
em maiúsculas e com hífen (STATISTICAL-REASONING) aparecem em forma legível (Statistical reasoning); as siglas conhecidas \
(SPSS, PISA) ficam em maiúsculas. O tamanho da letra cresce com a raiz quadrada da frequência, e as palavras são colocadas em \
espiral, do termo mais frequente ao menos frequente, sem sobreposição.</p>\n\
<p><strong>Nuvem de títulos.</strong> Os títulos são quebrados em palavras. Saem as palavras com menos de três letras, as {} \
palavras vazias de português, espanhol e inglês (artigos, preposições, conjunções) e os {} termos genéricos da escrita \
acadêmica (como estudo, análise, research e approach). Singular, plural e acento são unificados, mantendo a grafia mais \
frequente, e cada termo vale 1 por título. Expressões de duas palavras seguidas, sem palavra descartada no meio, aparecem à \
parte quando se repetem em pelo menos 2 títulos.</p>\n\
<p><strong>Rajadas (Kleinberg).</strong> Para cada palavra-chave ou referência, a série é, ano a ano, o número de documentos que \
a contêm entre os documentos do ano que têm algum termo do mesmo tipo. Um autômato de dois estados compara a taxa de base do \
termo, p<sub>0</sub> (total de documentos com o termo ÷ total na base), com uma taxa de rajada p<sub>1</sub> = s × p<sub>0</sub>, \
com s = {} (limitada a 0,95). Em cada ano, o custo é o oposto do logaritmo da verossimilhança binomial. Subir ao estado de \
rajada custa γ × ln(n), com γ = {} e n igual ao número de anos; descer é grátis. O caminho de menor custo total, encontrado por \
programação dinâmica (Viterbi), define os anos em rajada. A força é a soma, nesses anos, da diferença entre o custo na taxa de \
base e na taxa de rajada. Só entram termos com pelo menos {minimo} documentos, e cada termo aparece uma vez, com a rajada mais \
forte. A contagem é de documentos do corpus que usam o termo ou citam a referência, e não de citações recebidas. Séries curtas \
(menos de 8 anos) ou bases pequenas (menos de 100 documentos) geram aviso, pois as rajadas ficam instáveis.</p>\n\
</div>",
        inteiro(vazias),
        inteiro(academicas),
        decimal(s),
        decimal(gama)
    );
    format!("{texto}\n{}", num.tabela(&strings(&["Parâmetro", "Valor"]), &linhas, "Parâmetros da visão geral descritiva.", &[], false))
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn parametros_basicos() {
        let c = ConfigRel { minimo_frequencia: 3, tamanho_maximo: 15, ..Default::default() };
        let l = parametros_linhas(&c, Some(4), &[], None, Some("EquivalenceIndex"));
        let achar = |k: &str| l.iter().find(|x| x[0] == k).map(|x| x[1].clone()).unwrap();
        assert_eq!(achar("Frequência mínima"), "3 (itens em menos de 3 documentos saem antes da rede)");
        assert_eq!(achar("Ponto de corte"), "0 (não se aplica a centros simples)");
        assert_eq!(achar("Tamanho dos agrupamentos"), "mínimo 2, máximo 15 nós");
        assert_eq!(achar("Mapeador de documentos"), "núcleo");
        assert_eq!(achar("Co-ocorrência mínima"), "1 (ligações com valor menor saem antes da normalização)");
        assert_eq!(achar("Origem das palavras"), "palavras-chave dos autores, palavras-chave atribuídas pela fonte");
    }

    #[test]
    fn metodo_numera_secoes() {
        let c = ConfigRel::default();
        let h = algoritmo_html(&c, Some("EquivalenceIndex"), Some(4), true, true);
        for n in ["<strong>1. Rede.", "<strong>8. Dendrograma.", "<strong>9. Linha do tempo.", "<strong>10. Mapa de densidade.", "<strong>11. Duplo mapa", "<strong>12. Similitude", "<strong>13. Pontos de virada", "<strong>14. Qualidade do mapa.", "<strong>15. Rótulos"] {
            assert!(h.contains(n), "falta {n}");
        }
    }
}
