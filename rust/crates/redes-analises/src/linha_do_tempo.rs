//! Linha do tempo dos agrupamentos (porta de `linha_do_tempo.py` e `viz/linha_do_tempo.py`).
//!
//! Uma faixa por agrupamento; cada item (palavra, autor, referência) vira um nó posicionado no
//! ano médio dos documentos em que aparece (nas referências, no ano da própria referência). A
//! rede é a do corpus completo. No máximo `max_nos` nós (os mais frequentes) e `por_faixa` por
//! faixa; arcos: ligações internas à faixa (as 3 mais fortes por nó) e as 6 cruzadas mais fortes;
//! rajadas de Kleinberg: as 10 mais fortes do corpus, com 3 documentos ou mais.

use std::collections::{BTreeMap, BTreeSet, HashMap};

use redes_core::parametros::{Matriz, Parametros, Unidade};
use redes_core::texto::chave;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};

use crate::corpus::{corpus_completo, Corpus};
use crate::db::{self, Erro};
use crate::rajadas::{self, Tipo};
use crate::util::*;

pub const MAX_NOS: usize = 40;
pub const POR_FAIXA: usize = 8;
pub const LIGACOES_POR_NO: usize = 3;
pub const LIGACOES_CRUZADAS: usize = 6;
pub const RAJADAS_MAXIMAS: usize = 10;
pub const RAJADA_MIN_DOCUMENTOS: usize = 3;
pub const PROPORCAO_DESCRITOR: f64 = 0.5;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct NoLinha {
    pub id: i64,
    pub rotulo: String,
    pub ano: i64,
    pub frequencia: i64,
    pub rajada: bool,
    pub rajada_inicio: Option<i64>,
    pub rajada_fim: Option<i64>,
    pub primeiro: i64,
    pub ultimo: i64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Faixa {
    pub indice: usize,
    pub rotulo: String,
    pub frequencia_total: i64,
    pub itens_total: usize,
    pub nos: Vec<NoLinha>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct LigacaoLinha {
    pub origem: i64,
    pub destino: i64,
    pub valor: f64,
    pub cruzada: bool,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct Omitidos {
    pub itens: usize,
    pub agrupamentos: usize,
    pub sem_ano: usize,
    pub descritores: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LinhaDoTempo {
    pub unidade: String,
    pub faixas: Vec<Faixa>,
    pub ligacoes: Vec<LigacaoLinha>,
    pub anos: Vec<i64>,
    pub atividade: bool,
    pub posicao: String,
    pub avisos: Vec<String>,
    pub omitidos: Omitidos,
    pub total_itens: usize,
    pub total_agrupamentos: usize,
}

fn vazio(unidade: &str, aviso: &str) -> LinhaDoTempo {
    LinhaDoTempo {
        unidade: unidade.into(),
        faixas: vec![],
        ligacoes: vec![],
        anos: vec![],
        atividade: false,
        posicao: String::new(),
        avisos: vec![aviso.into()],
        omitidos: Omitidos::default(),
        total_itens: 0,
        total_agrupamentos: 0,
    }
}

fn anos_das_referencias(c: &Connection, teto: Option<i64>) -> HashMap<i64, i64> {
    let mut por_grupo: BTreeMap<i64, Vec<i64>> = BTreeMap::new();
    let Ok(mut st) = c.prepare("SELECT ReferenceGroup_idReferenceGroup, year FROM Reference") else { return HashMap::new() };
    let Ok(mut linhas) = st.query([]) else { return HashMap::new() };
    while let Ok(Some(l)) = linhas.next() {
        let Ok(Some(g)) = l.get::<_, Option<i64>>(0) else { continue };
        let ano = match l.get_ref(1) {
            Ok(rusqlite::types::ValueRef::Integer(i)) => i.to_string(),
            Ok(rusqlite::types::ValueRef::Real(f)) => format!("{f}"),
            Ok(rusqlite::types::ValueRef::Text(t)) => String::from_utf8_lossy(t).into_owned(),
            _ => continue,
        };
        let p: String = ano.trim().chars().take(4).collect();
        let Ok(v) = p.parse::<i64>() else { continue };
        if (1400..=teto.unwrap_or(2100)).contains(&v) {
            por_grupo.entry(g).or_default().push(v);
        }
    }
    por_grupo.into_iter().map(|(g, mut v)| (g, db::mediana_baixa(&mut v))).collect()
}

/// Linha do tempo do corpus completo para os parâmetros dados (Words, Authors ou References em co-ocorrência).
pub fn constroi(c: &Connection, p: &Parametros, max_nos: usize, por_faixa: usize) -> Result<LinhaDoTempo, Erro> {
    if p.matriz != Matriz::CoOccurrence {
        return Err("A linha do tempo mostra itens (palavras, autores, referências) ao longo dos anos. Escolha uma análise de co-ocorrência para ver a figura.".into());
    }
    if !matches!(p.unidade, Unidade::Words | Unidade::Authors | Unidade::References) {
        return Err("A linha do tempo existe para palavras-chave, autores e referências em co-ocorrência.".into());
    }
    let corpus = corpus_completo(c, p)?;
    constroi_de(c, &corpus, max_nos.max(1), por_faixa.max(1))
}

fn nome_da_unidade(u: Unidade) -> &'static str {
    u.nome()
}

pub fn constroi_de(c: &Connection, corpus: &Corpus, max_nos: usize, por_faixa: usize) -> Result<LinhaDoTempo, Erro> {
    let unidade = nome_da_unidade(corpus.parametros.unidade);
    if corpus.grupos.is_empty() {
        return Ok(vazio(
            unidade,
            "Nenhum agrupamento se formou no corpus completo com estes parâmetros; não há o que mostrar na linha do tempo.",
        ));
    }
    let anos_doc = db::anos_dos_documentos(c)?;
    let referencias = corpus.parametros.unidade == Unidade::References;
    let teto_ref = anos_doc.values().max().map(|m| m + 1);
    let anos_ref = if referencias { anos_das_referencias(c, teto_ref) } else { HashMap::new() };
    let teto_ref = teto_ref.unwrap_or(2100);
    let atividade = !referencias;
    let total_docs = corpus.documentos_originais;
    let descritores: BTreeSet<i64> = if total_docs > 0 {
        corpus.frequencia.iter().filter(|(_, &f)| f as f64 / total_docs as f64 > PROPORCAO_DESCRITOR).map(|(&n, _)| n).collect()
    } else {
        BTreeSet::new()
    };
    let posicao = if referencias { "referencia" } else { "media" };
    let tipo = match corpus.parametros.unidade {
        Unidade::Words => Some(Tipo::Palavras),
        Unidade::References => Some(Tipo::Referencias),
        _ => None,
    };
    let mut forte: HashMap<String, rajadas::Rajada> = HashMap::new();
    if let Some(t) = tipo {
        for l in rajadas::calcula(c, t, RAJADAS_MAXIMAS, RAJADA_MIN_DOCUMENTOS, rajadas::S_PADRAO, rajadas::GAMA_PADRAO)?.rajadas {
            if l.documentos >= RAJADA_MIN_DOCUMENTOS {
                forte.insert(chave(&l.termo), l);
            }
        }
    }
    let mut candidatos: Vec<(usize, NoLinha)> = Vec::new();
    let mut sem_ano = 0usize;
    let mut omitidos_descritor = 0usize;
    let mut itens_por_faixa: BTreeMap<usize, usize> = BTreeMap::new();
    let mut freq_por_faixa: BTreeMap<usize, i64> = BTreeMap::new();
    for (indice, g) in corpus.grupos.iter().enumerate() {
        itens_por_faixa.insert(indice, g.nos.len());
        freq_por_faixa.insert(indice, g.nos.iter().map(|n| corpus.frequencia.get(n).copied().unwrap_or(0) as i64).sum());
        for &no in &g.nos {
            if descritores.contains(&no) {
                omitidos_descritor += 1;
                continue;
            }
            let (ano, primeiro, ultimo);
            if referencias {
                match anos_ref.get(&no) {
                    Some(&a) => {
                        ano = a;
                        primeiro = a;
                        ultimo = a;
                    }
                    None => {
                        sem_ano += 1;
                        continue;
                    }
                }
            } else {
                let ys: Vec<i64> = corpus.dataset.documentos_do_item(no).iter().filter_map(|d| anos_doc.get(d).copied()).collect();
                if ys.is_empty() {
                    sem_ano += 1;
                    continue;
                }
                let soma: i64 = ys.iter().sum();
                ano = (soma as f64 / ys.len() as f64 + 0.5).floor() as i64;
                primeiro = *ys.iter().min().unwrap();
                ultimo = *ys.iter().max().unwrap();
            }
            let mut nome = limpa(&corpus.rotulo(no));
            if nome.is_empty() {
                nome = format!("Item {no}");
            }
            let raj = forte.get(&chave(&nome));
            candidatos.push((
                indice,
                NoLinha {
                    id: no,
                    rotulo: nome,
                    ano,
                    frequencia: corpus.frequencia.get(&no).copied().unwrap_or(1) as i64,
                    rajada: raj.is_some(),
                    rajada_inicio: raj.filter(|_| atividade).map(|r| r.inicio),
                    rajada_fim: raj.filter(|_| atividade).map(|r| r.fim),
                    primeiro,
                    ultimo,
                },
            ));
        }
    }
    candidatos.sort_by(|a, b| {
        (-a.1.frequencia, &a.1.rotulo, a.1.id).cmp(&(-b.1.frequencia, &b.1.rotulo, b.1.id))
    });
    let mut escolhidos: BTreeMap<usize, Vec<NoLinha>> = BTreeMap::new();
    let mut total = 0usize;
    for (indice, no) in candidatos {
        if total >= max_nos {
            break;
        }
        if escolhidos.get(&indice).map_or(0, |v| v.len()) >= por_faixa {
            continue;
        }
        escolhidos.entry(indice).or_default().push(no);
        total += 1;
    }
    let mut indices: Vec<usize> = escolhidos.keys().copied().collect();
    indices.sort_by(|a, b| (-freq_por_faixa[a], *a).cmp(&(-freq_por_faixa[b], *b)));
    let mut faixas = Vec::new();
    for indice in indices {
        let mut nos = escolhidos.remove(&indice).unwrap();
        nos.sort_by(|a, b| (a.ano, -a.frequencia, &a.rotulo, a.id).cmp(&(b.ano, -b.frequencia, &b.rotulo, b.id)));
        let rot = limpa(&corpus.grupos[indice].exibicao);
        faixas.push(Faixa {
            indice,
            rotulo: if rot.is_empty() { format!("Agrupamento {}", indice + 1) } else { rot },
            frequencia_total: freq_por_faixa[&indice],
            itens_total: itens_por_faixa[&indice],
            nos,
        });
    }
    let mut avisos: Vec<String> = Vec::new();
    let itens_total: usize = itens_por_faixa.values().sum();
    let itens_de_fora = itens_total as i64 - total as i64 - sem_ano as i64 - omitidos_descritor as i64;
    let grupos_de_fora = corpus.grupos.len() - faixas.len();
    if omitidos_descritor > 0 {
        avisos.push(format!(
            "{} {} (presentes em mais de {}% dos documentos: descrevem o corpus, não distinguem temas).",
            omitidos_descritor,
            if omitidos_descritor == 1 { "termo-descritor omitido" } else { "termos-descritor omitidos" },
            (PROPORCAO_DESCRITOR * 100.0) as i64
        ));
    }
    if sem_ano > 0 {
        let motivo = if referencias {
            if sem_ano == 1 {
                format!("a referência não traz um ano válido, entre 1400 e {teto_ref}")
            } else {
                format!("as referências não trazem um ano válido, entre 1400 e {teto_ref}")
            }
        } else if anos_doc.is_empty() {
            "nenhum documento do projeto traz o ano de publicação".to_string()
        } else if sem_ano == 1 {
            "os documentos do item não trazem o ano".to_string()
        } else {
            "os documentos dos itens não trazem o ano".to_string()
        };
        avisos.push(format!(
            "{} {} ({}).",
            sem_ano,
            if sem_ano == 1 { "item sem ano foi omitido" } else { "itens sem ano foram omitidos" },
            motivo
        ));
    }
    if itens_de_fora > 0 || grupos_de_fora > 0 {
        let mut partes = vec![format!("{} {}", itens_de_fora.max(0), if itens_de_fora == 1 { "item ficou" } else { "itens ficaram" }) + " de fora"];
        if grupos_de_fora > 0 {
            partes.push(format!(
                "{} {} sem nenhum nó",
                grupos_de_fora,
                if grupos_de_fora == 1 { "agrupamento ficou" } else { "agrupamentos ficaram" }
            ));
        }
        avisos.push(format!(
            "A figura mostra os {} itens mais frequentes (no máximo {} no total e {} por faixa); {}.",
            total,
            max_nos,
            por_faixa,
            partes.join(" e ")
        ));
    }
    let omit = Omitidos { itens: itens_de_fora.max(0) as usize, agrupamentos: grupos_de_fora, sem_ano, descritores: omitidos_descritor };
    if faixas.is_empty() {
        let decisivo = if referencias {
            format!("Nenhuma referência dos agrupamentos tem ano válido (entre 1400 e {teto_ref}); não há o que mostrar na linha do tempo.")
        } else if anos_doc.is_empty() {
            "Nenhum documento do projeto traz o ano de publicação (todos os itens ficaram sem ano); não há o que mostrar na linha do tempo.".into()
        } else {
            "Nenhum item dos agrupamentos tem ano; não há o que mostrar na linha do tempo.".to_string()
        };
        avisos.insert(0, decisivo);
        return Ok(LinhaDoTempo {
            unidade: unidade.into(),
            faixas: vec![],
            ligacoes: vec![],
            anos: vec![],
            atividade,
            posicao: posicao.into(),
            avisos,
            omitidos: omit,
            total_itens: 0,
            total_agrupamentos: 0,
        });
    }
    let todos_anos: Vec<i64> = faixas.iter().flat_map(|f| f.nos.iter().map(|n| n.ano)).collect();
    let (a0, a1) = (*todos_anos.iter().min().unwrap(), *todos_anos.iter().max().unwrap());
    if a0 == a1 {
        avisos.push(format!(
            "Todos os itens mostrados caem no mesmo ano ({a0}): a linha do tempo não mostra evolução. Use um corpus que cubra mais de um ano."
        ));
    }
    let faixa_de: HashMap<i64, usize> = faixas.iter().enumerate().flat_map(|(i, f)| f.nos.iter().map(move |n| (n.id, i))).collect();
    let mut vizinhos: BTreeMap<i64, Vec<(f64, i64)>> = BTreeMap::new();
    let mut cruzadas: Vec<(f64, i64, i64)> = Vec::new();
    for (a, b, valor) in corpus.rede.arestas() {
        if !faixa_de.contains_key(&a) || !faixa_de.contains_key(&b) || !valor.is_finite() || valor <= 0.0 {
            continue;
        }
        if faixa_de[&a] == faixa_de[&b] {
            vizinhos.entry(a).or_default().push((valor, b));
            vizinhos.entry(b).or_default().push((valor, a));
        } else {
            cruzadas.push((valor, a, b));
        }
    }
    let mut internas: BTreeMap<(i64, i64), f64> = BTreeMap::new();
    for (no, lista) in vizinhos.iter_mut() {
        lista.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap().then(a.1.cmp(&b.1)));
        for &(valor, outro) in lista.iter().take(LIGACOES_POR_NO) {
            internas.insert(((*no).min(outro), (*no).max(outro)), valor);
        }
    }
    cruzadas.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap().then(a.1.cmp(&b.1)).then(a.2.cmp(&b.2)));
    let mut int_v: Vec<((i64, i64), f64)> = internas.into_iter().collect();
    int_v.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then(a.0.cmp(&b.0)));
    let mut ligacoes: Vec<LigacaoLinha> =
        int_v.into_iter().map(|((a, b), v)| LigacaoLinha { origem: a, destino: b, valor: py_round(v, 6), cruzada: false }).collect();
    ligacoes.extend(
        cruzadas.into_iter().take(LIGACOES_CRUZADAS).map(|(v, a, b)| LigacaoLinha { origem: a, destino: b, valor: py_round(v, 6), cruzada: true }),
    );
    Ok(LinhaDoTempo {
        unidade: unidade.into(),
        faixas,
        ligacoes,
        anos: vec![a0, a1],
        atividade,
        posicao: posicao.into(),
        avisos,
        omitidos: omit,
        total_itens: itens_total,
        total_agrupamentos: corpus.grupos.len(),
    })
}

// ----------------------------------------------------------------------- SVG

pub const LARGURA: i64 = 1100;
const COL_ESQ: i64 = 214;
const MARGEM_DIR: i64 = 44;
const TOPO: i64 = 88;
const LINHA: f64 = 26.0;
const FAIXA_MIN: f64 = 44.0;
const PAD: f64 = 9.0;
const LIMITE_ROTULO: usize = 34;
const ROTULO_FAIXA_PX: f64 = (COL_ESQ - 34) as f64;
const PAD_X: f64 = 16.0;
const MEDIDA_SEGURA: f64 = 1.05;
const CINZA_ARCO: &str = "#9AA3B2";
const VERMELHO: &str = "#DC2626";
const PALETA: [&str; 15] = [
    "#4C6FFF", "#00A344", "#8B5CF6", "#D97706", "#0E7490", "#DB2777", "#65A30D", "#0284C7", "#DC2626", "#0F766E", "#A16207",
    "#7C3AED", "#BE185D", "#4D7C0F", "#0369A1",
];

const ESTILO: &str = ".lt-fundo{fill:var(--sk-fundo,#fff)}.lt-tit{fill:var(--sk-texto,#14204A);font-size:16px;font-weight:700}\
.lt-sub{fill:var(--sk-fraco,#64748B);font-size:11.5px}.lt-rot{fill:var(--sk-texto,#14204A);font-size:11px;unicode-bidi:plaintext}\
.lt-faixa{fill:var(--sk-texto,#14204A);font-size:12px;font-weight:700;unicode-bidi:plaintext}\
.lt-meta{fill:var(--sk-fraco,#64748B);font-size:10.5px}.lt-eixo{fill:var(--sk-fraco,#64748B);font-size:11px}\
.lt-halo{stroke:var(--sk-fundo,#fff);stroke-width:3;paint-order:stroke;stroke-linejoin:round}.lt-aviso{fill:#9A3412;font-size:11.5px}";

pub fn nome_unidade(u: &str) -> &str {
    match u {
        "Words" => "Palavras-chave",
        "Authors" => "Autores",
        "References" => "Referências",
        "AuthorsReference" => "Autores citados",
        "ReferenceSources" => "Fontes citadas",
        "Countries" => "Países",
        "Institutions" => "Instituições",
        o => o,
    }
}

fn passo(span: i64) -> i64 {
    for p in [1, 2, 5, 10, 20, 25, 50, 100] {
        if span as f64 / p as f64 <= 14.0 {
            return p;
        }
    }
    200
}

fn svg_simples(mensagem: &str, titulo: &str, p: &str) -> String {
    let mensagem = limpa(mensagem);
    let tit = if limpa(titulo).is_empty() { "Linha do tempo".to_string() } else { limpa(titulo) };
    format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{l}\" height=\"110\" viewBox=\"0 0 {l} 110\" font-family=\"{f}\" role=\"img\" \
         aria-labelledby=\"{p}-t {p}-d\"><title id=\"{p}-t\">{t}</title><desc id=\"{p}-d\">{m}</desc><style>{e}</style>\
         <rect class=\"lt-fundo\" width=\"{l}\" height=\"110\"/><text class=\"lt-tit\" x=\"16\" y=\"30\">{tt}</text>\
         <text class=\"lt-aviso\" x=\"16\" y=\"64\">{mm}</text></svg>",
        l = LARGURA,
        f = FONTE_INTER,
        p = p,
        t = esc_limpo(&tit),
        m = esc(&mensagem),
        e = ESTILO,
        tt = esc_limpo(&cabe(&tit, (LARGURA - 32) as f64, 16.0, true)),
        mm = esc_limpo(&cabe(&mensagem, (LARGURA - 32) as f64, 11.5, false))
    )
}

struct Item<'a> {
    n: &'a NoLinha,
    r: f64,
    texto: String,
    completo: String,
    cx: f64,
    lado: char,
    linha: usize,
    cy: f64,
}

/// SVG autônomo da linha do tempo; `rotulos`: índice da faixa → rótulo novo.
pub fn svg(dados: &LinhaDoTempo, titulo: &str, rotulos: &BTreeMap<usize, String>) -> String {
    let p = format!("lt{}", hash8(&format!("{}{}{:?}", serde_json::to_string(dados).unwrap_or_default(), titulo, rotulos)));
    let faixas: Vec<&Faixa> = dados.faixas.iter().filter(|f| !f.nos.is_empty()).collect();
    let avisos: Vec<String> = dados.avisos.iter().map(|a| limpa(a)).filter(|a| !a.is_empty()).collect();
    if faixas.is_empty() {
        return svg_simples(avisos.first().map(|s| s.as_str()).unwrap_or("Não há agrupamentos para desenhar."), titulo, &p);
    }
    let atividade = dados.atividade;
    let unidade = dados.unidade.as_str();
    let anos_nos: Vec<i64> = faixas.iter().flat_map(|f| f.nos.iter().map(|n| n.ano)).collect();
    let (n0, n1) = (*anos_nos.iter().min().unwrap(), *anos_nos.iter().max().unwrap());
    let (a0, a1) = ((n0 - 1) as f64, (n1 + 1) as f64);
    let (x0, x1) = (COL_ESQ as f64, (LARGURA - MARGEM_DIR) as f64);
    let (area_e, area_d) = ((COL_ESQ - 10) as f64, (LARGURA - MARGEM_DIR + 4) as f64);
    let (xi, xf) = (x0 + PAD_X, x1 - PAD_X);
    let xx = |ano: f64| xi + (ano - a0) / (a1 - a0) * (xf - xi);
    let todos: Vec<&NoLinha> = faixas.iter().flat_map(|f| f.nos.iter()).collect();
    let fmax = todos.iter().map(|n| n.frequencia).max().unwrap().max(1);
    let fmin = todos.iter().map(|n| n.frequencia).min().unwrap();
    let rr = |freq: i64| 3.5 + 7.0 * (freq.max(0) as f64 / fmax as f64).sqrt();

    let mut layout: Vec<(f64, f64, &Faixa, Vec<Item>)> = Vec::new();
    let mut pos: HashMap<i64, (f64, f64, usize)> = HashMap::new();
    let mut y = TOPO as f64;
    for (i, faixa) in faixas.iter().enumerate() {
        let mut nos: Vec<&NoLinha> = faixa.nos.iter().collect();
        nos.sort_by(|a, b| (a.ano, -a.frequencia, &a.rotulo, a.id).cmp(&(b.ano, -b.frequencia, &b.rotulo, b.id)));
        let mut linhas_ocupadas: Vec<Vec<(f64, f64)>> = Vec::new();
        let mut itens: Vec<Item> = Vec::new();
        for n in nos {
            let r = rr(n.frequencia);
            let mut rotulo = limpa(&n.rotulo);
            if rotulo.is_empty() {
                rotulo = format!("Item {}", n.id);
            }
            let mut texto = curto(&rotulo, LIMITE_ROTULO);
            let raj_n = n.rajada;
            let cx = xx(n.ano as f64);
            let folga = if raj_n { 9.0 } else { 5.0 };
            let (lim_e, lim_d) = (area_e + 5.0, area_d - 5.0);
            let sobra_d = lim_d - (cx + r + folga);
            let sobra_e = (cx - r - folga) - lim_e;
            let medida = |t: &str| largura(t, 11.0, raj_n) * MEDIDA_SEGURA;
            let mut w = medida(&texto);
            let lado;
            if w <= sobra_d {
                lado = 'd';
            } else if w <= sobra_e {
                lado = 'e';
            } else {
                lado = if sobra_d >= sobra_e { 'd' } else { 'e' };
                texto = cabe_com(&texto, (if lado == 'd' { sobra_d } else { sobra_e }).max(20.0), &medida);
                w = medida(&texto);
            }
            let direita = (cx - r - 2.0, cx + r + folga + w);
            let esquerda = (cx - r - folga - w, cx + r + 2.0);
            let caixa = if lado == 'd' { direita } else { esquerda };
            let mut linha = None;
            for (k, ocupados) in linhas_ocupadas.iter_mut().enumerate() {
                if ocupados.iter().all(|&(a, b)| caixa.1 + 6.0 <= a || caixa.0 - 6.0 >= b) {
                    ocupados.push(caixa);
                    linha = Some(k);
                    break;
                }
            }
            let linha = linha.unwrap_or_else(|| {
                linhas_ocupadas.push(vec![caixa]);
                linhas_ocupadas.len() - 1
            });
            itens.push(Item { n, r, texto, completo: rotulo, cx, lado, linha, cy: 0.0 });
        }
        let altura = FAIXA_MIN.max(2.0 * PAD + linhas_ocupadas.len().max(1) as f64 * LINHA);
        let desloc = (altura - linhas_ocupadas.len() as f64 * LINHA) / 2.0;
        for it in itens.iter_mut() {
            it.cy = y + desloc + it.linha as f64 * LINHA + LINHA / 2.0;
            pos.insert(it.n.id, (it.cx, it.cy, i));
        }
        layout.push((y, altura, faixa, itens));
        y += altura + 3.0;
    }
    let fim_faixas = y;

    let teve_rajada = todos.iter().any(|n| n.rajada);
    let teve_linha = atividade && todos.iter().any(|n| n.ultimo > n.primeiro);
    let teve_cruzada = dados.ligacoes.iter().any(|l| l.cruzada);
    let teve_interna = dados.ligacoes.iter().any(|l| !l.cruzada);
    let modo = if dados.posicao.is_empty() { if atividade { "media" } else { "documento" } } else { dados.posicao.as_str() };
    let pos_texto = match modo {
        "referencia" => "posição = ano da própria referência",
        "media" => "posição = ano médio dos documentos do item",
        _ => "posição = ano do documento",
    };
    let mut itens_leg: Vec<(&str, String)> = vec![
        ("tam", format!("tamanho = frequência em documentos ({} a {})", fmin, fmax)),
        ("pos", pos_texto.to_string()),
    ];
    if teve_linha {
        itens_leg.push(("linha", "linha fina = do primeiro ao último ano em que o item aparece".into()));
    }
    if teve_rajada {
        itens_leg.push((
            "anel",
            format!(
                "anel vermelho = rajada de {} (3 documentos ou mais, entre as 10 mais fortes do corpus){}{}",
                if modo == "referencia" { "citação" } else { "uso" },
                if teve_linha { "; traço vermelho = anos da rajada" } else { "" },
                if unidade == "Words" { "; rajadas calculadas só sobre palavras-chave dos autores" } else { "" }
            ),
        ));
    }
    if teve_interna {
        itens_leg.push(("arco", "arco colorido = ligação dentro da faixa (as 3 mais fortes de cada item)".into()));
    }
    if teve_cruzada {
        itens_leg.push(("cinza", "arco cinza = ligação entre faixas (as 6 mais fortes)".into()));
    }
    let mut linhas_texto: Vec<(String, String, bool)> = Vec::new();
    for (tipo, texto) in &itens_leg {
        for (k, parte) in quebra(texto, (LARGURA - 72) as f64, 3, 11.5, false).into_iter().enumerate() {
            linhas_texto.push((if k == 0 { tipo.to_string() } else { String::new() }, parte, false));
        }
    }
    for aviso in &avisos {
        for parte in quebra(&format!("Aviso: {aviso}"), (LARGURA - 72) as f64, 3, 11.5, false) {
            linhas_texto.push((String::new(), parte, true));
        }
    }
    let y_eixo_baixo = fim_faixas + 20.0;
    let y_leg = y_eixo_baixo + 30.0;
    let h_tot = y_leg + 18.0 * linhas_texto.len() as f64 + 14.0;
    let cores: Vec<&str> = (0..faixas.len()).map(|i| PALETA[i % PALETA.len()]).collect();
    let n_itens = todos.len();
    let nome_un = nome_unidade(unidade);
    let titulo_fig = if limpa(titulo).is_empty() { "Linha do tempo dos agrupamentos".to_string() } else { limpa(titulo) };
    let sub = format!("{} · {} itens em {} agrupamentos · {}–{}", nome_un, n_itens, faixas.len(), n0, n1);
    let descricao = format!("{}. {}. Cada faixa é um agrupamento; o eixo horizontal vai de {} a {}.", titulo_fig, sub, a0 as i64, a1 as i64);

    let mut o: Vec<String> = Vec::new();
    o.push(format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{l}\" height=\"{h:.0}\" viewBox=\"0 0 {l} {h:.0}\" font-family=\"{f}\" role=\"img\" \
         aria-labelledby=\"{p}-t {p}-d\">",
        l = LARGURA,
        h = h_tot,
        f = FONTE_INTER,
        p = p
    ));
    o.push(format!("<title id=\"{p}-t\">{}</title><desc id=\"{p}-d\">{}</desc>", esc_limpo(&titulo_fig), esc_limpo(&descricao), p = p));
    o.push(format!("<style>{ESTILO}</style>"));
    o.push(format!(
        "<defs><clipPath id=\"{p}-area\"><rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{:.1}\"/></clipPath></defs>",
        area_e as i64,
        TOPO,
        (area_d - area_e) as i64,
        fim_faixas - TOPO as f64,
        p = p
    ));
    o.push(format!("<rect class=\"lt-fundo\" width=\"{}\" height=\"{:.0}\"/>", LARGURA, h_tot));
    o.push(format!(
        "<text class=\"lt-tit\" x=\"16\" y=\"28\">{}</text>",
        esc_limpo(&cabe(&titulo_fig, (LARGURA - 32) as f64, 16.0, true))
    ));
    o.push(format!("<text class=\"lt-sub\" x=\"16\" y=\"47\">{}</text>", esc_limpo(&sub)));
    for (i, (y0, h, _, _)) in layout.iter().enumerate() {
        let c = cores[i];
        o.push(format!(
            "<rect x=\"{}\" y=\"{:.1}\" width=\"{:.1}\" height=\"{:.1}\" fill=\"{}\" fill-opacity=\"{}\"/>",
            COL_ESQ - 10,
            y0,
            (LARGURA - MARGEM_DIR + 4 - COL_ESQ + 10) as f64,
            h,
            c,
            if i % 2 == 1 { "0.07" } else { "0.13" }
        ));
        o.push(format!("<rect x=\"4\" y=\"{:.1}\" width=\"4\" height=\"{:.1}\" fill=\"{}\"/>", y0, h, c));
    }
    let ps = passo((a1 - a0) as i64);
    let inicio = ((a0 as i64) / ps) * ps;
    for a in inicio..=(a1 as i64) {
        if (a as f64) < a0 || a % ps != 0 {
            continue;
        }
        let x = xx(a as f64);
        o.push(format!(
            "<line x1=\"{:.1}\" y1=\"{}\" x2=\"{:.1}\" y2=\"{:.1}\" stroke=\"#94A3B8\" stroke-opacity=\".28\"/>",
            x,
            TOPO - 6,
            x,
            fim_faixas
        ));
        for ty in [(TOPO - 12) as f64, y_eixo_baixo] {
            o.push(format!("<text class=\"lt-eixo\" x=\"{:.1}\" y=\"{:.1}\" text-anchor=\"middle\">{}</text>", x, ty, a));
        }
    }
    for (i, (y0, h, faixa, itens)) in layout.iter().enumerate() {
        let texto = match rotulos.get(&faixa.indice) {
            Some(t) if !t.is_empty() => limpa(t),
            _ => {
                let r = limpa(&faixa.rotulo);
                if r.is_empty() {
                    format!("Agrupamento {}", i + 1)
                } else {
                    r
                }
            }
        };
        let prefixo = format!("#{} ", i + 1);
        let n_linhas = if *h >= 60.0 { 2 } else { 1 };
        let disp = ROTULO_FAIXA_PX - largura(&prefixo, 12.0, true);
        let partes = quebra(&texto, disp, n_linhas, 12.0, true);
        let total_itens = faixa.itens_total;
        let meta = format!("{} de {} itens · freq. {}", itens.len(), total_itens, faixa.frequencia_total);
        let bloco = partes.len() as f64 * 14.0 + 13.0;
        let ty = y0 + (h - bloco) / 2.0 + 11.0;
        o.push(format!("<g><title>{}</title>", esc_limpo(&format!("{prefixo}{texto}"))));
        for (k, parte) in partes.iter().enumerate() {
            let pre = if k == 0 { esc(&prefixo) } else { String::new() };
            o.push(format!("<text class=\"lt-faixa\" x=\"14\" y=\"{:.1}\">{}{}</text>", ty + k as f64 * 14.0, pre, esc_limpo(parte)));
        }
        o.push(format!(
            "<text class=\"lt-meta\" x=\"14\" y=\"{:.1}\">{}</text></g>",
            ty + partes.len() as f64 * 14.0 + 1.0,
            esc_limpo(&cabe(&meta, ROTULO_FAIXA_PX, 10.5, false))
        ));
    }
    o.push(format!("<g class=\"lt-plot\" clip-path=\"url(#{p}-area)\">"));
    let mut ligs: Vec<&LigacaoLinha> = dados
        .ligacoes
        .iter()
        .filter(|l| pos.contains_key(&l.origem) && pos.contains_key(&l.destino) && l.valor.is_finite())
        .collect();
    let vmax = {
        let m = ligs.iter().map(|l| l.valor).fold(0.0f64, f64::max);
        if m == 0.0 {
            1.0
        } else {
            m
        }
    };
    ligs.sort_by(|a, b| {
        (a.cruzada, a.valor, a.origem, a.destino).partial_cmp(&(b.cruzada, b.valor, b.origem, b.destino)).unwrap()
    });
    for l in ligs {
        let (xa, ya, fa) = pos[&l.origem];
        let (xb, yb, fb) = pos[&l.destino];
        let sw = 0.7 + 1.9 * l.valor / vmax;
        if fa == fb {
            let dist = (xb - xa).abs() + (yb - ya).abs();
            let bulge = (6.0 + 0.1 * dist).min(18.0);
            let cx = ((xa + xb) / 2.0).max(area_e + 2.0).min(area_d - 2.0);
            let cy = ((ya + yb) / 2.0 - bulge).max(layout[fa].0 + 2.0);
            o.push(format!(
                "<path d=\"M{:.1},{:.1} Q{:.1},{:.1} {:.1},{:.1}\" fill=\"none\" stroke=\"{}\" stroke-opacity=\".5\" stroke-width=\"{:.2}\"/>",
                xa, ya, cx, cy, xb, yb, cores[fa], sw
            ));
        } else {
            let meio = (xa + xb) / 2.0;
            let desvio = if meio + 34.0 <= area_d - 2.0 { 34.0 } else { -34.0 };
            let cx = (meio + desvio).max(area_e + 2.0).min(area_d - 2.0);
            o.push(format!(
                "<path d=\"M{:.1},{:.1} Q{:.1},{:.1} {:.1},{:.1}\" fill=\"none\" stroke=\"{}\" stroke-opacity=\".38\" stroke-width=\"{:.2}\"/>",
                xa,
                ya,
                cx,
                (ya + yb) / 2.0,
                xb,
                yb,
                CINZA_ARCO,
                sw
            ));
        }
    }
    let corta = |a: f64, b: f64| -> Option<(f64, f64, bool, bool)> {
        let (e, d) = (a.max(a0), b.min(a1));
        if e < d {
            Some((e, d, a < a0, b > a1))
        } else {
            None
        }
    };
    for (i, (_, _, _, itens)) in layout.iter().enumerate() {
        let c = cores[i];
        if !atividade {
            continue;
        }
        for it in itens {
            let n = it.n;
            let (pr, ul) = (n.primeiro, n.ultimo);
            if ul <= pr {
                continue;
            }
            if let Some((e, d, ce, cd)) = corta(pr as f64, ul as f64) {
                o.push(format!(
                    "<line x1=\"{:.1}\" y1=\"{:.1}\" x2=\"{:.1}\" y2=\"{:.1}\" stroke=\"{}\" stroke-opacity=\".38\" stroke-width=\"1.1\"/>",
                    xx(e),
                    it.cy,
                    xx(d),
                    it.cy,
                    c
                ));
                for (flag, x, sinal) in [(ce, xx(e), 1.0), (cd, xx(d), -1.0)] {
                    if flag {
                        o.push(format!(
                            "<path d=\"M{:.1},{:.1} L{:.1},{:.1} L{:.1},{:.1}\" fill=\"none\" stroke=\"{}\" stroke-opacity=\".7\" stroke-width=\"1.2\"/>",
                            x + 4.0 * sinal,
                            it.cy - 3.0,
                            x,
                            it.cy,
                            x + 4.0 * sinal,
                            it.cy + 3.0,
                            c
                        ));
                    }
                }
            }
            if n.rajada {
                if let (Some(ri), Some(rf)) = (n.rajada_inicio, n.rajada_fim) {
                    if let Some((e, d, ce, cd)) = corta(ri as f64, rf as f64) {
                        o.push(format!(
                            "<line x1=\"{:.1}\" y1=\"{:.1}\" x2=\"{:.1}\" y2=\"{:.1}\" stroke=\"{}\" stroke-width=\"2.8\" stroke-linecap=\"round\"/>",
                            xx(e),
                            it.cy,
                            xx(d),
                            it.cy,
                            VERMELHO
                        ));
                        for (flag, x, sinal) in [(ce, xx(e), 1.0), (cd, xx(d), -1.0)] {
                            if flag {
                                o.push(format!(
                                    "<path class=\"lt-seta-rajada\" d=\"M{:.1},{:.1} L{:.1},{:.1} L{:.1},{:.1}\" fill=\"none\" stroke=\"{}\" stroke-width=\"1.6\"/>",
                                    x + 4.0 * sinal,
                                    it.cy - 3.5,
                                    x,
                                    it.cy,
                                    x + 4.0 * sinal,
                                    it.cy + 3.5,
                                    VERMELHO
                                ));
                            }
                        }
                    }
                }
            }
        }
    }
    o.push("</g>".into());
    for (i, (_, _, _, itens)) in layout.iter().enumerate() {
        let c = cores[i];
        for it in itens {
            let (n, r, cx, cy) = (it.n, it.r, it.cx, it.cy);
            let raj = n.rajada;
            let freq = n.frequencia;
            let dica_ano = if atividade {
                format!("Ano médio: {}\nAparece de {} a {}", n.ano, n.primeiro, n.ultimo)
            } else {
                format!("Ano: {}", n.ano)
            };
            let mut dica = format!("{}\nFrequência: {} documento{}\n{}", it.completo, freq, if freq == 1 { "" } else { "s" }, dica_ano);
            if raj {
                dica.push_str("\nRajada");
                if let (Some(a), Some(b)) = (n.rajada_inicio, n.rajada_fim) {
                    dica.push_str(&format!(" de {a} a {b}"));
                }
            }
            let (tx, ancora) = if it.lado == 'd' { (cx + r + if raj { 8.0 } else { 4.0 }, "start") } else { (cx - r - if raj { 8.0 } else { 4.0 }, "end") };
            o.push(format!("<g><title>{}</title>", esc_limpo(&dica)));
            if raj {
                o.push(format!(
                    "<circle cx=\"{:.1}\" cy=\"{:.1}\" r=\"{:.1}\" fill=\"none\" stroke=\"{}\" stroke-width=\"2\"/>",
                    cx,
                    cy,
                    r + 3.0,
                    VERMELHO
                ));
            }
            o.push(format!(
                "<circle cx=\"{:.1}\" cy=\"{:.1}\" r=\"{:.1}\" fill=\"{}\" fill-opacity=\".88\" stroke=\"#fff\" stroke-width=\"1\"/>",
                cx, cy, r, c
            ));
            let negrito = if raj { " font-weight=\"700\"" } else { "" };
            o.push(format!(
                "<text class=\"lt-rot lt-halo\" aria-hidden=\"true\" x=\"{:.1}\" y=\"{:.1}\" text-anchor=\"{}\"{}>{}</text>",
                tx,
                cy + 3.8,
                ancora,
                negrito,
                esc_limpo(&it.texto)
            ));
            o.push(format!(
                "<text class=\"lt-rot\" x=\"{:.1}\" y=\"{:.1}\" text-anchor=\"{}\"{}>{}</text></g>",
                tx,
                cy + 3.8,
                ancora,
                negrito,
                esc_limpo(&it.texto)
            ));
        }
    }
    let mut yl = y_leg;
    o.push(format!(
        "<line x1=\"16\" y1=\"{}\" x2=\"{}\" y2=\"{}\" stroke=\"#94A3B8\" stroke-opacity=\".35\"/>",
        pyf(y_leg - 14.0),
        LARGURA - 16,
        pyf(y_leg - 14.0)
    ));
    for (tipo, texto, aviso) in &linhas_texto {
        let cy = yl - 4.0;
        match tipo.as_str() {
            "tam" => o.push(format!(
                "<circle cx=\"22\" cy=\"{c}\" r=\"3.5\" fill=\"#64748B\" fill-opacity=\".8\"/><circle cx=\"36\" cy=\"{c}\" r=\"7\" fill=\"#64748B\" fill-opacity=\".8\"/>",
                c = pyf(cy)
            )),
            "linha" => o.push(format!(
                "<line x1=\"14\" y1=\"{c}\" x2=\"44\" y2=\"{c}\" stroke=\"#64748B\" stroke-opacity=\".7\" stroke-width=\"1.3\"/>",
                c = pyf(cy)
            )),
            "anel" => o.push(format!(
                "<circle cx=\"29\" cy=\"{c}\" r=\"6.5\" fill=\"none\" stroke=\"{v}\" stroke-width=\"2\"/><circle cx=\"29\" cy=\"{c}\" r=\"3.5\" fill=\"#64748B\"/>",
                c = pyf(cy),
                v = VERMELHO
            )),
            "arco" => o.push(format!(
                "<path d=\"M14,{} Q29,{} 44,{}\" fill=\"none\" stroke=\"{}\" stroke-opacity=\".6\" stroke-width=\"1.6\"/>",
                pyf(cy + 3.0),
                pyf(cy - 8.0),
                pyf(cy + 3.0),
                cores[0]
            )),
            "cinza" => o.push(format!(
                "<path d=\"M14,{} Q29,{} 44,{}\" fill=\"none\" stroke=\"{}\" stroke-opacity=\".7\" stroke-width=\"1.6\"/>",
                pyf(cy + 3.0),
                pyf(cy - 8.0),
                pyf(cy + 3.0),
                CINZA_ARCO
            )),
            "pos" => o.push(format!(
                "<path d=\"M14,{c} L44,{c} M40,{a} L44,{c} L40,{b}\" fill=\"none\" stroke=\"#64748B\" stroke-width=\"1.2\"/>",
                c = pyf(cy),
                a = pyf(cy - 3.0),
                b = pyf(cy + 3.0)
            )),
            _ => {}
        }
        o.push(format!("<text class=\"{}\" x=\"56\" y=\"{}\">{}</text>", if *aviso { "lt-aviso" } else { "lt-sub" }, pyf(yl), esc_limpo(texto)));
        yl += 18.0;
    }
    o.push("</svg>".into());
    o.join("\n")
}
