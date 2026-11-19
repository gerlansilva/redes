//! Análise de similitude dos resumos (estilo IRaMuTeQ): idioma por resumo, lematização leve,
//! formas ativas, coocorrência, índice (Jaccard, cosseno, binomial, coocorrência), árvore
//! máxima de Kruskal com arestas extras e blocos de Louvain. Porta `redes/similitude.py`.

use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

use indexmap::IndexMap;
use regex::Regex;
use rusqlite::Connection;
use serde::Serialize;

use crate::nx::{louvain, Grafo};
use crate::rajadas::ln_fatorial;
use crate::tabelas as t;
use crate::util::{pyf, py_round_int, sem_acentos};

pub type Erro = String;

pub const IDIOMAS: [&str; 3] = ["en", "pt", "es"];
pub const N_FORMAS: usize = 60;
pub const EXTRAS_PADRAO: usize = 20;
pub const MINIMO_PALAVRAS: usize = 15;
pub const MINIMO_DF: i64 = 3;
pub const MINIMO_DF_POUCOS: i64 = 2;
pub const MINIMO_RESUMOS_IDIOMA: i64 = 5;
pub const COTA_MINIMA_IDIOMA: usize = 10;
pub const FORMAS_POR_SEGMENTO: usize = 14;
pub const SEMENTE: u32 = 7;
pub const RESOLUCAO: f64 = 1.0;
pub const LIMITE_IGNORAR: usize = 200;
pub const TITULO: &str = "Análise de similitude dos resumos";
pub const MENSAGEM_SEM_RESUMOS: &str = "Este projeto não tem resumos (ou eles são curtos demais) para a análise de similitude. Importe uma base com resumos, como o Scopus, o Web of Science ou o OpenAlex.";

pub fn nome_idioma(l: &str) -> &'static str {
    match l {
        "en" => "inglês",
        "pt" => "português",
        _ => "espanhol",
    }
}
pub fn nome_indice(i: &str) -> &'static str {
    match i {
        "jaccard" => "Jaccard",
        "cosseno" => "cosseno (Salton)",
        "binomial" => "binomial (hipergeométrica)",
        _ => "coocorrência",
    }
}
pub fn nome_segmento(s: &str) -> &'static str {
    if s == "resumo" {
        "resumo inteiro"
    } else {
        "grupos de frases"
    }
}

fn idx(l: &str) -> usize {
    IDIOMAS.iter().position(|x| *x == l).unwrap()
}

fn normaliza(p: &str) -> String {
    sem_acentos(p).to_lowercase()
}

// ===================================================================== parâmetros e saída

#[derive(Clone, Debug)]
pub struct ParametrosSimilitude {
    pub n_formas: usize,
    pub indice: String,
    pub segmento: String,
    pub extras: usize,
    pub idioma: String,
    pub ignorar: Vec<String>,
    pub periodo: String,
    pub nivel_lema: u8,
}

impl Default for ParametrosSimilitude {
    fn default() -> Self {
        ParametrosSimilitude {
            n_formas: N_FORMAS,
            indice: "jaccard".into(),
            segmento: "resumo".into(),
            extras: EXTRAS_PADRAO,
            idioma: "todos".into(),
            ignorar: vec![],
            periodo: "todos".into(),
            nivel_lema: 2,
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct Forma {
    pub id: String,
    pub forma: String,
    pub idioma: String,
    pub frequencia: i64,
    pub resumos: usize,
    pub ocorrencias: i64,
    pub comunidade: usize,
    pub grau: i64,
}

#[derive(Clone, Debug, Serialize)]
pub struct ArestaSim {
    pub origem: String,
    pub destino: String,
    pub peso: f64,
    pub tipo: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct ComunidadeInfo {
    pub id: usize,
    pub n: usize,
    pub nome: String,
    pub idiomas: Vec<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ParametrosUsados {
    pub n_formas: usize,
    pub indice: String,
    pub segmento: String,
    pub extras: usize,
    pub idioma: String,
    pub periodo: String,
    pub ignorar: Vec<String>,
    pub semente: u32,
}

#[derive(Clone, Debug, Serialize)]
pub struct Similitude {
    pub parametros: ParametrosUsados,
    pub n_resumos: usize,
    pub n_lidos: usize,
    pub n_segmentos: usize,
    pub docs_por_idioma: IndexMap<String, i64>,
    pub idiomas_nas_formas: Vec<String>,
    pub formas: Vec<Forma>,
    pub arestas: Vec<ArestaSim>,
    pub comunidades: Vec<ComunidadeInfo>,
    pub n_arvore: usize,
    pub n_extras: usize,
    pub componentes: usize,
    pub avisos: Vec<String>,
}

// ===================================================================== palavras vazias

struct Vazias {
    por_idioma: [HashSet<String>; 3],
    gerais: HashSet<String>,
}

fn conj(listas: &[&[&str]]) -> HashSet<String> {
    let mut s = HashSet::new();
    for l in listas {
        for p in *l {
            s.insert(normaliza(p));
        }
    }
    s
}

fn vazias() -> &'static Vazias {
    static V: OnceLock<Vazias> = OnceLock::new();
    V.get_or_init(|| Vazias {
        por_idioma: [
            conj(&[t::VAZIAS_EN, t::EXTRA_EN]),
            conj(&[t::VAZIAS_PT, t::EXTRA_PT, t::GENERICAS_PT]),
            conj(&[t::VAZIAS_ES, t::EXTRA_ES, t::GENERICAS_ES]),
        ],
        gerais: conj(&[t::ACADEMICAS, t::PRAXE]),
    })
}

// ===================================================================== idioma

fn pesos_marcadores() -> &'static [HashMap<String, f64>; 3] {
    static P: OnceLock<[HashMap<String, f64>; 3]> = OnceLock::new();
    P.get_or_init(|| {
        let listas: [&[&str]; 3] = [t::MARCADORES_EN, t::MARCADORES_PT, t::MARCADORES_ES];
        let conjuntos: Vec<HashSet<String>> =
            listas.iter().map(|l| l.iter().map(|w| normaliza(w)).collect()).collect();
        let mut saida: [HashMap<String, f64>; 3] = Default::default();
        for (l, lista) in listas.iter().enumerate() {
            for w in *lista {
                let k = normaliza(w);
                let donos = conjuntos.iter().filter(|c| c.contains(&k)).count();
                saida[l].insert(k, 1.0 / donos as f64);
            }
        }
        saida
    })
}

fn termina(p: &str, sufixos: &[&str]) -> bool {
    sufixos.iter().any(|s| p.ends_with(s))
}

pub fn pontua_idiomas(palavras: &[String]) -> [f64; 3] {
    let pesos = pesos_marcadores();
    let mut pontos = [0.0f64; 3];
    for p in palavras {
        let k = normaliza(p);
        for l in 0..3 {
            pontos[l] += pesos[l].get(&k).copied().unwrap_or(0.0);
        }
        if p.chars().any(|c| "ãõç".contains(c)) {
            pontos[1] += 2.0;
        }
        if p.chars().any(|c| "ñ¿¡".contains(c)) {
            pontos[2] += 2.0;
        }
        if p.chars().count() < 4 {
            continue;
        }
        let n = p.chars().count();
        if termina(p, &["ção", "ções", "ões", "ão", "mente"]) {
            pontos[1] += 1.0;
        }
        if termina(p, &["ción", "ciones", "sión", "ía", "ñ"]) {
            pontos[2] += 1.0;
        }
        if termina(p, &["tion", "tions", "ing", "ness", "ity", "ies", "ed"]) && !(p.ends_with("ed") && n < 6) {
            pontos[0] += 0.5;
        }
    }
    pontos
}

fn decide(pontos: &[f64; 3], minimo: f64, razao: f64) -> Option<&'static str> {
    let mut ordem = [0usize, 1, 2];
    ordem.sort_by(|&a, &b| pontos[b].partial_cmp(&pontos[a]).unwrap().then(a.cmp(&b)));
    let (melhor, segundo) = (ordem[0], ordem[1]);
    if pontos[melhor] < minimo || pontos[melhor] <= pontos[segundo] * razao {
        return None;
    }
    Some(IDIOMAS[melhor])
}

pub fn palavras_do_texto(texto: &str) -> Vec<String> {
    static R: OnceLock<Regex> = OnceLock::new();
    let r = R.get_or_init(|| Regex::new(r"\p{L}+(?:['’\-]\p{L}+)*").unwrap());
    r.find_iter(texto).map(|m| m.as_str().to_string()).collect()
}

pub fn detecta_idioma_palavras(palavras: &[String]) -> &'static str {
    let pontos = pontua_idiomas(palavras);
    if let Some(d) = decide(&pontos, 1.0, 1.2) {
        return d;
    }
    let mut ordem = [0usize, 1, 2];
    ordem.sort_by(|&a, &b| pontos[b].partial_cmp(&pontos[a]).unwrap().then(a.cmp(&b)));
    if pontos[ordem[0]] > 0.0 {
        IDIOMAS[ordem[0]]
    } else {
        "en"
    }
}

pub fn detecta_idioma(texto: &str) -> &'static str {
    let p: Vec<String> = palavras_do_texto(texto).iter().map(|w| w.to_lowercase()).collect();
    detecta_idioma_palavras(&p)
}

// ===================================================================== lematização

fn irregulares(idioma: &str) -> &'static [(&'static str, &'static str)] {
    match idioma {
        "en" => &[
            ("children", "child"), ("people", "person"), ("men", "man"), ("women", "woman"),
            ("analyses", "analysis"), ("hypotheses", "hypothesis"), ("criteria", "criterion"),
            ("phenomena", "phenomenon"), ("media", "medium"), ("indices", "index"), ("matrices", "matrix"),
            ("data", "data"), ("taught", "teach"), ("thought", "think"), ("statistical", "statistics"),
            ("mathematical", "mathematics"), ("probabilistic", "probability"), ("statistic", "statistics"),
        ],
        "pt" => &[
            ("estatistico", "estatística"), ("matematico", "matemática"), ("probabilistico", "probabilidade"),
            ("meses", "mês"), ("paises", "país"),
        ],
        _ => &[
            ("estadistico", "estadística"), ("matematico", "matemática"), ("probabilistico", "probabilidad"),
            ("redes", "red"), ("meses", "mes"), ("paises", "país"), ("matrices", "matriz"),
        ],
    }
}

fn irregular(idioma: &str, chave: &str) -> Option<&'static str> {
    irregulares(idioma).iter().find(|(a, _)| *a == chave).map(|(_, b)| *b)
}

const PROTEGIDAS_EN: &[&str] = &[
    "bias", "focus", "status", "series", "species", "physics", "this", "has", "was", "does", "lens", "gas",
    "alias", "canvas", "atlas", "news", "analysis", "basis", "thesis", "hypothesis", "emphasis", "synthesis",
    "diagnosis", "crisis", "class", "process", "access", "success", "progress", "business", "consensus",
    "stimulus", "virus", "campus", "bonus", "census", "always", "perhaps", "across", "plus", "thus",
];
const VOGAIS: &str = "aeiouáéíóúâêôãõàü";

fn nc(w: &str) -> usize {
    w.chars().count()
}
/// `w[:-k]`
fn corta(w: &str, k: usize) -> String {
    let n = nc(w);
    w.chars().take(n.saturating_sub(k)).collect()
}
/// `w[-k]` (k >= 1)
fn do_fim(w: &str, k: usize) -> Option<char> {
    let n = nc(w);
    if k > n {
        None
    } else {
        w.chars().nth(n - k)
    }
}
/// O fim de `w` casa com o padrão de classes de caracteres (uma string de opções por posição).
fn casa(w: &str, padrao: &[&str]) -> bool {
    let cs: Vec<char> = w.chars().collect();
    if cs.len() < padrao.len() {
        return false;
    }
    let off = cs.len() - padrao.len();
    padrao.iter().enumerate().all(|(i, cls)| cls.contains(cs[off + i]))
}

fn singular_en(w: &str) -> String {
    if nc(w) <= 3 || PROTEGIDAS_EN.contains(&w) || termina(w, &["ss", "us", "is", "ics"]) {
        return w.into();
    }
    if w.ends_with("ies") && nc(w) > 4 {
        return corta(w, 3) + "y";
    }
    if termina(w, &["sses", "xes", "ches", "shes", "zzes"]) {
        return corta(w, 2);
    }
    if w.ends_with('s') && !w.ends_with("'s") {
        return corta(w, 1);
    }
    w.into()
}

fn s_generico(w: &str) -> Option<String> {
    if w.ends_with('s')
        && nc(w) > 3
        && do_fim(w, 2).map_or(false, |c| VOGAIS.contains(c))
        && !termina(w, &["is", "us", "ás", "és", "ís", "ós", "ús"])
    {
        return Some(corta(w, 1));
    }
    None
}

fn singular_pt(w: &str) -> String {
    let n = nc(w);
    if n < 4 || w.ends_with("mos") {
        return w.into();
    }
    if casa(w, &["çc", "õo", "e", "s"]) {
        return corta(w, 4) + "ção";
    }
    if n > 5 && casa(w, &["õo", "e", "s"]) {
        return corta(w, 3) + "ão";
    }
    if n > 5 && casa(w, &["ãa", "e", "s"]) {
        return corta(w, 3) + "ão";
    }
    if w.ends_with("ãos") {
        return corta(w, 1);
    }
    if termina(w, &["úteis", "uteis"]) {
        return corta(w, 5) + "útil";
    }
    if n > 5 && w.ends_with("ceis") {
        return corta(w, 4) + "cil";
    }
    if n > 4 && w.ends_with("ais") {
        return corta(w, 3) + "al";
    }
    if n > 5 && casa(w, &["eé", "i", "s"]) {
        return corta(w, 3) + "el";
    }
    if n > 4 && w.ends_with("ns") {
        return corta(w, 2) + "m";
    }
    if n > 7 && w.ends_with("eses") {
        return corta(w, 4) + "ês";
    }
    if w.ends_with("íses") {
        return corta(w, 4) + "ís";
    }
    if casa(w, &["aeiouáéíóúâêôãõ", "rz", "e", "s"]) && n > 4 {
        return corta(w, 2);
    }
    if termina(w, &["ois", "uis"]) {
        return corta(w, 1);
    }
    if let Some(s) = s_generico(w) {
        return s;
    }
    w.into()
}

fn singular_es(w: &str) -> String {
    let n = nc(w);
    if n < 4 || w.ends_with("mos") {
        return w.into();
    }
    if termina(w, &["ágenes", "agenes"]) {
        return corta(w, 6) + "agen";
    }
    if termina(w, &["ígenes", "igenes"]) {
        return corta(w, 6) + "igen";
    }
    if n > 5 && w.ends_with("ones") {
        return corta(w, 4) + "ón";
    }
    if w.ends_with("ades") || w.ends_with("udes") {
        return corta(w, 2);
    }
    if w.ends_with("yes") && n > 4 {
        return corta(w, 2);
    }
    if casa(w, &["aeiouáéíóú", "c", "e", "s"]) && !w.ends_with("ices") {
        return corta(w, 3) + "z";
    }
    if w.ends_with("ices") {
        return corta(w, 1);
    }
    if w.ends_with("bles") {
        return corta(w, 1);
    }
    if casa(w, &["aeiouáéíóú", "lr", "e", "s"]) && n > 4 {
        return corta(w, 2);
    }
    if casa(w, &["aeiouáéíóú", "n", "e", "s"]) && n > 4 {
        return sem_acentos(&corta(w, 2));
    }
    if w.ends_with("íses") {
        return corta(w, 4) + "ís";
    }
    if let Some(s) = s_generico(w) {
        return s;
    }
    w.into()
}

pub fn singulariza(palavra: &str, idioma: &str) -> String {
    let w = palavra.to_lowercase();
    if let Some(d) = irregular(idioma, &normaliza(&w)) {
        return d.into();
    }
    let s = match idioma {
        "en" => singular_en(&w),
        "pt" => singular_pt(&w),
        _ => singular_es(&w),
    };
    match irregular(idioma, &normaliza(&s)) {
        Some(d) => d.into(),
        None => s,
    }
}

type Cand = Vec<(String, bool)>;

fn verbos_romance(chave: &str, idioma: &str) -> Cand {
    let n = nc(chave);
    let mut c: Cand = vec![];
    if n < 6 {
        return c;
    }
    let pt = idioma == "pt";
    let e = |s: &str| chave.ends_with(s);
    if e("ando") {
        c.push((corta(chave, 4) + "ar", true));
    }
    if pt && e("endo") {
        c.push((corta(chave, 4) + "er", true));
    }
    if pt && e("indo") {
        c.push((corta(chave, 4) + "ir", true));
    }
    if !pt && e("iendo") {
        c.push((corta(chave, 5) + "er", true));
        c.push((corta(chave, 5) + "ir", true));
    }
    if !pt && e("yendo") {
        c.push((corta(chave, 5) + "ir", true));
    }
    if e("ado") || e("ada") {
        c.push((corta(chave, 3) + "ar", true));
    }
    if e("ido") || e("ida") {
        c.push((corta(chave, 3) + "er", false));
        c.push((corta(chave, 3) + "ir", false));
    }
    if pt {
        if e("aram") {
            c.push((corta(chave, 4) + "ar", false));
        } else if e("am") {
            c.push((corta(chave, 2) + "ar", false));
        }
        if e("ou") {
            c.push((corta(chave, 2) + "ar", false));
        }
        if e("eu") || e("iu") {
            c.push((corta(chave, 2) + "er", false));
            c.push((corta(chave, 2) + "ir", false));
        }
        if e("em") && !e("gem") {
            c.push((corta(chave, 2) + "er", false));
            c.push((corta(chave, 2) + "ir", false));
        }
    } else {
        if e("aron") {
            c.push((corta(chave, 4) + "ar", false));
        } else if e("an") {
            c.push((corta(chave, 2) + "ar", false));
        }
        if e("ieron") {
            c.push((corta(chave, 5) + "er", false));
            c.push((corta(chave, 5) + "ir", false));
        } else if e("en") && !(e("gen") || e("men")) {
            c.push((corta(chave, 2) + "er", false));
            c.push((corta(chave, 2) + "ir", false));
        }
    }
    c
}

fn verbos_en(chave: &str) -> Cand {
    let n = nc(chave);
    let mut c: Cand = vec![];
    if chave.ends_with("ing") && n > 5 {
        let stem = corta(chave, 3);
        c.push((stem.clone(), false));
        c.push((stem.clone() + "e", false));
        if nc(&stem) > 2 && do_fim(&stem, 1) == do_fim(&stem, 2) {
            c.push((corta(&stem, 1), false));
        }
    }
    if chave.ends_with("ied") && n > 5 {
        c.push((corta(chave, 3) + "y", false));
    }
    if chave.ends_with("ed") && n > 4 {
        let stem = corta(chave, 2);
        c.push((stem.clone(), false));
        c.push((corta(chave, 1), false));
        if nc(&stem) > 2 && do_fim(&stem, 1) == do_fim(&stem, 2) {
            c.push((corta(&stem, 1), false));
        }
    }
    if termina(chave, &["ization", "isation"]) && n > 8 {
        c.push((corta(chave, 7) + "e", false));
    }
    c
}

fn adverbios(chave: &str, idioma: &str) -> Cand {
    let mut c: Cand = vec![];
    let n = nc(chave);
    if idioma == "en" {
        if chave.ends_with("ally") && n > 7 {
            c.push((corta(chave, 2), false));
            c.push((corta(chave, 4), false));
        } else if chave.ends_with("ily") && n > 6 {
            c.push((corta(chave, 3) + "y", false));
        } else if chave.ends_with("ly") && n > 5 {
            c.push((corta(chave, 2), false));
        }
        return c;
    }
    if chave.ends_with("mente") && n > 8 {
        let base = corta(chave, 5);
        if base.ends_with('a') {
            c.push((corta(&base, 1) + "o", false));
        }
        c.push((base, false));
    }
    c
}

const PARES_GENERO: [(&str, &str); 10] = [
    ("osa", "oso"), ("iva", "ivo"), ("ana", "ano"), ("una", "uno"), ("eira", "eiro"), ("uda", "udo"),
    ("ora", "or"), ("ada", "ado"), ("ida", "ido"), ("mna", "mno"),
];

fn genero(chave: &str) -> Cand {
    if nc(chave) < 5 {
        return vec![];
    }
    PARES_GENERO
        .iter()
        .filter(|(f, _)| chave.ends_with(f))
        .map(|(f, m)| (corta(chave, nc(f)) + m, false))
        .collect()
}

fn etapa(contagem: &IndexMap<String, i64>, gera: &dyn Fn(&str) -> Cand, razao: f64) -> IndexMap<String, String> {
    let mut propostas: HashMap<&str, Cand> = HashMap::new();
    for k in contagem.keys() {
        propostas.insert(k.as_str(), gera(k));
    }
    let mut suporte: HashMap<String, HashSet<&str>> = HashMap::new();
    for (k, lista) in &propostas {
        for (ck, forte) in lista {
            if *forte {
                suporte.entry(ck.clone()).or_default().insert(*k);
            }
        }
    }
    let mut chaves: Vec<&String> = contagem.keys().collect();
    chaves.sort();
    let mut destino = IndexMap::new();
    for k in chaves {
        let mut escolha: Option<String> = None;
        for (ck, _) in &propostas[k.as_str()] {
            if ck != k && nc(ck) >= 4 {
                if let Some(&cc) = contagem.get(ck) {
                    if cc as f64 >= razao * contagem[k] as f64 {
                        escolha = Some(ck.clone());
                        break;
                    }
                }
            }
        }
        if escolha.is_none() {
            for (ck, forte) in &propostas[k.as_str()] {
                if *forte
                    && ck != k
                    && nc(ck) >= 5
                    && !contagem.contains_key(ck)
                    && suporte.get(ck).map_or(0, |s| s.len()) >= 2
                {
                    escolha = Some(ck.clone());
                    break;
                }
            }
        }
        if let Some(e) = escolha {
            destino.insert(k.clone(), e);
        }
    }
    destino
}

fn irreg_ou(idioma: &str, c: Cand) -> Cand {
    c.into_iter()
        .map(|(ck, f)| (irregular(idioma, &ck).map(normaliza).unwrap_or(ck), f))
        .collect()
}

/// chave da palavra -> (chave do lema, grafia do lema) para um idioma.
fn lemas_do_idioma(
    idioma: &str,
    vocab: &IndexMap<String, i64>,
    rep: &HashMap<String, String>,
    nivel: u8,
) -> HashMap<String, (String, String)> {
    let mut k1: HashMap<String, String> = HashMap::new();
    let mut exib: HashMap<String, String> = HashMap::new();
    for k in vocab.keys() {
        let s = if nivel >= 1 { singulariza(&rep[k], idioma) } else { rep[k].clone() };
        let ks = normaliza(&s);
        k1.insert(k.clone(), ks.clone());
        exib.entry(ks).or_insert(s);
    }
    let mut c1: IndexMap<String, i64> = IndexMap::new();
    for (k, n) in vocab {
        *c1.entry(k1[k].clone()).or_insert(0) += n;
    }
    let mut atual: HashMap<String, String> = vocab.keys().map(|k| (k.clone(), k1[k].clone())).collect();
    if nivel >= 2 {
        let id = idioma.to_string();
        let etapas: Vec<(Box<dyn Fn(&str) -> Cand>, f64)> = if idioma == "en" {
            let a = id.clone();
            let b = id.clone();
            vec![
                (Box::new(move |k: &str| irreg_ou(&a, verbos_en(k))), 0.3),
                (Box::new(move |k: &str| irreg_ou(&b, adverbios(k, &b))), 0.0),
            ]
        } else {
            let a = id.clone();
            let b = id.clone();
            vec![
                (Box::new(move |k: &str| verbos_romance(k, &a)), 0.0),
                (Box::new(move |k: &str| irreg_ou(&b, adverbios(k, &b))), 0.0),
                (Box::new(|k: &str| genero(k)), 0.0),
            ]
        };
        for (gera, razao) in etapas {
            let destino = etapa(&c1, gera.as_ref(), razao);
            if destino.is_empty() {
                continue;
            }
            let mut novo: IndexMap<String, i64> = IndexMap::new();
            for (k, n) in &c1 {
                *novo.entry(destino.get(k).cloned().unwrap_or_else(|| k.clone())).or_insert(0) += n;
            }
            for v in atual.values_mut() {
                if let Some(d) = destino.get(v) {
                    *v = d.clone();
                }
            }
            for ck in destino.values() {
                exib.entry(ck.clone()).or_insert_with(|| ck.clone());
            }
            c1 = novo;
        }
    }
    let mut saida = HashMap::new();
    for k in vocab.keys() {
        let lema = atual[k].clone();
        let grafia = if vocab.contains_key(&lema) {
            rep[&lema].clone()
        } else {
            exib.get(&lema).cloned().unwrap_or_else(|| lema.clone())
        };
        saida.insert(k.clone(), (lema, grafia));
    }
    saida
}

/// Lema (grafia) de cada palavra de uma lista, tratada como o vocabulário de um corpus.
pub fn lematiza(palavras: &[&str], idioma: &str, nivel: u8) -> Vec<(String, String)> {
    let mut vocab: IndexMap<String, i64> = IndexMap::new();
    let mut rep: HashMap<String, String> = HashMap::new();
    for p in palavras {
        let k = normaliza(p);
        *vocab.entry(k.clone()).or_insert(0) += 1;
        rep.entry(k).or_insert_with(|| p.to_lowercase());
    }
    let mapa = lemas_do_idioma(idioma, &vocab, &rep, nivel);
    palavras.iter().map(|p| (p.to_string(), mapa[&normaliza(p)].1.clone())).collect()
}

// ===================================================================== leitura e prepara

fn limpa_resumo(texto: &str) -> String {
    static C: OnceLock<Regex> = OnceLock::new();
    static P: OnceLock<Regex> = OnceLock::new();
    let c = C.get_or_init(|| {
        Regex::new(r"(?is)(©|\(c\)|copyright|all rights reserved|published by).*$").unwrap()
    });
    let p = P.get_or_init(|| {
        Regex::new(r"(?i)\[?\s*(no abstract available|resumo n[aã]o dispon[ií]vel|sin resumen|abstract not available)\s*\]?")
            .unwrap()
    });
    let sem = c.replace_all(texto, "");
    p.replace_all(&sem, " ").trim().to_string()
}

/// `(id, título, resumo)` dos documentos com resumo (do período, se pedido).
pub fn le_resumos(c: &Connection, periodo_id: Option<i64>) -> Result<Vec<(i64, String, String)>, Erro> {
    let mut linhas: Vec<(i64, Option<String>, Option<String>)> = Vec::new();
    let mut coleta = |sql: &str, params: &[&dyn rusqlite::ToSql]| -> Result<(), Erro> {
        let mut st = c.prepare(sql).map_err(|e| e.to_string())?;
        let it = st
            .query_map(params, |r| Ok((r.get::<_, i64>(0)?, r.get::<_, Option<String>>(1)?, r.get::<_, Option<String>>(2)?)))
            .map_err(|e| e.to_string())?;
        for l in it {
            linhas.push(l.map_err(|e| e.to_string())?);
        }
        Ok(())
    };
    match periodo_id {
        None => coleta("SELECT idDocument, title, docAbstract FROM Document ORDER BY idDocument", &[])?,
        Some(p) => coleta(
            "SELECT d.idDocument, d.title, d.docAbstract FROM Document d \
             JOIN PublishDate_Period pp ON pp.PublishDate_idPublishDate = d.PublishDate_idPublishDate \
             WHERE pp.Period_idPeriod = ? ORDER BY d.idDocument",
            &[&p],
        )?,
    }
    let mut saida = vec![];
    for (id, titulo, resumo) in linhas {
        let r = limpa_resumo(&resumo.unwrap_or_default());
        if r.split_whitespace().count() >= MINIMO_PALAVRAS {
            saida.push((id, titulo.unwrap_or_default(), r));
        }
    }
    Ok(saida)
}

/// Há ao menos um resumo utilizável?
pub fn aplicavel(c: &Connection) -> bool {
    le_resumos(c, None).map(|v| !v.is_empty()).unwrap_or(false)
}

fn ignorados(ignorar: &[String]) -> HashSet<String> {
    let mut itens: Vec<String> = vec![];
    for i in ignorar {
        for p in i.split(|c| c == ',' || c == ';' || c == '\n') {
            itens.push(p.to_string());
        }
    }
    itens
        .iter()
        .take(LIMITE_IGNORAR)
        .filter(|p| !p.trim().is_empty())
        .map(|p| normaliza(&p.trim().replace('’', "'")))
        .collect()
}

/// `re.split(r"(?<=[.?!;:])\s+", texto)`.
fn divide_frases(texto: &str) -> Vec<String> {
    let cs: Vec<char> = texto.chars().collect();
    let mut saida = vec![];
    let mut atual = String::new();
    let mut i = 0;
    while i < cs.len() {
        if cs[i].is_whitespace() && i > 0 && ".?!;:".contains(cs[i - 1]) {
            saida.push(std::mem::take(&mut atual));
            while i < cs.len() && cs[i].is_whitespace() {
                i += 1;
            }
        } else {
            atual.push(cs[i]);
            i += 1;
        }
    }
    saida.push(atual);
    saida
}

type FrasePal = (Option<&'static str>, Vec<String>);

fn analisa_idiomas(texto: &str) -> (&'static str, Vec<FrasePal>) {
    let frases_txt: Vec<String> = divide_frases(texto).into_iter().filter(|f| !f.trim().is_empty()).collect();
    let palavras_frase: Vec<Vec<String>> = frases_txt
        .iter()
        .map(|f| palavras_do_texto(f).iter().map(|p| p.to_lowercase().replace('’', "'")).collect())
        .collect();
    let todas: Vec<String> = palavras_frase.iter().flatten().cloned().collect();
    let principal = detecta_idioma_palavras(&todas);
    let frases = palavras_frase
        .into_iter()
        .map(|p| {
            let idi = if p.len() >= 6 { decide(&pontua_idiomas(&p), 3.0, 1.6) } else { None };
            (idi, p)
        })
        .collect();
    (principal, frases)
}

fn idioma_do_resumo(principal: &'static str, frases: &[FrasePal], preferido: &'static str) -> &'static str {
    if preferido != principal && frases.iter().filter(|(i, _)| *i == Some(preferido)).count() >= 2 {
        preferido
    } else {
        principal
    }
}

fn tira_s_posse(p: &str) -> &str {
    p.strip_suffix("'s").unwrap_or(p)
}

fn tokeniza_frases(frases: &[FrasePal], idioma: &str, ign: &HashSet<String>) -> (Vec<Vec<(String, String)>>, usize) {
    let v = vazias();
    let vaz = &v.por_idioma[idx(idioma)];
    let mut saida = vec![];
    let mut descartadas = 0;
    for (idi, palavras) in frases {
        if let Some(i) = idi {
            if *i != idioma {
                descartadas += 1;
                continue;
            }
        }
        let mut s = vec![];
        for p in palavras {
            let p = tira_s_posse(p);
            let k = normaliza(p);
            if nc(&k) < 3 || vaz.contains(&k) || ign.contains(&k) || v.gerais.contains(&k) {
                continue;
            }
            s.push((k, p.to_string()));
        }
        saida.push(s);
    }
    (saida, descartadas)
}

struct Prep {
    segmentos: Vec<Vec<String>>,
    meta: Vec<(i64, &'static str)>,
    rotulo: HashMap<String, String>,
    docs_por_idioma: IndexMap<&'static str, i64>,
    frases_descartadas: usize,
    docs_usados: usize,
    docs_lidos: usize,
}

fn mais_comum(c: &IndexMap<String, i64>) -> String {
    let mut v: Vec<(&String, &i64)> = c.iter().collect();
    v.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
    v[0].0.clone()
}

fn prepara(documentos: &[(i64, String, String)], segmento: &str, idioma: &str, ign: &HashSet<String>, nivel: u8) -> Prep {
    let analisados: Vec<(i64, &'static str, Vec<FrasePal>)> = documentos
        .iter()
        .map(|(id, _, r)| {
            let (p, f) = analisa_idiomas(r);
            (*id, p, f)
        })
        .collect();
    let preferido: &'static str = if idioma == "todos" {
        let mut cont = [0i64; 3];
        for (_, p, _) in &analisados {
            cont[idx(p)] += 1;
        }
        let mut ordem = [0usize, 1, 2];
        ordem.sort_by(|&a, &b| cont[b].cmp(&cont[a]).then(a.cmp(&b)));
        IDIOMAS[ordem[0]]
    } else {
        IDIOMAS[idx(idioma)]
    };
    let mut lidos: Vec<(i64, &'static str, Vec<Vec<(String, String)>>)> = vec![];
    let mut por_idioma_docs: IndexMap<&'static str, i64> = IndexMap::new();
    let mut descartadas = 0;
    for (id, principal, frases) in &analisados {
        let idi = idioma_do_resumo(principal, frases, preferido);
        *por_idioma_docs.entry(idi).or_insert(0) += 1;
        if idioma != "todos" && idi != idioma {
            continue;
        }
        let (toks, desc) = tokeniza_frases(frases, idi, ign);
        descartadas += desc;
        lidos.push((*id, idi, toks));
    }
    let mut vocab: [IndexMap<String, i64>; 3] = Default::default();
    let mut grafias: [IndexMap<String, IndexMap<String, i64>>; 3] = Default::default();
    for (_, idi, frases) in &lidos {
        let l = idx(idi);
        for fr in frases {
            for (k, p) in fr {
                *vocab[l].entry(k.clone()).or_insert(0) += 1;
                *grafias[l].entry(k.clone()).or_default().entry(p.clone()).or_insert(0) += 1;
            }
        }
    }
    let rep: Vec<HashMap<String, String>> =
        (0..3).map(|l| grafias[l].iter().map(|(k, g)| (k.clone(), mais_comum(g))).collect()).collect();
    let mapa: Vec<Option<HashMap<String, (String, String)>>> = (0..3)
        .map(|l| if vocab[l].is_empty() { None } else { Some(lemas_do_idioma(IDIOMAS[l], &vocab[l], &rep[l], nivel)) })
        .collect();
    let mut segmentos: Vec<Vec<String>> = vec![];
    let mut meta = vec![];
    let mut exib: IndexMap<String, IndexMap<String, i64>> = IndexMap::new();
    for (doc_id, idi, frases) in &lidos {
        let l = idx(idi);
        let mut por_frase: Vec<Vec<String>> = vec![];
        for fr in frases {
            let mut lemas = vec![];
            for (k, _) in fr {
                let (lema, graf) = &mapa[l].as_ref().unwrap()[k];
                if ign.contains(lema) || ign.contains(&normaliza(graf)) {
                    continue;
                }
                let no = format!("{idi}:{lema}");
                *exib.entry(no.clone()).or_default().entry(graf.clone()).or_insert(0) += 1;
                lemas.push(no);
            }
            if !lemas.is_empty() {
                por_frase.push(lemas);
            }
        }
        if por_frase.is_empty() {
            continue;
        }
        let segs: Vec<Vec<String>> = if segmento == "resumo" {
            vec![por_frase.into_iter().flatten().collect()]
        } else {
            let mut segs: Vec<Vec<String>> = vec![];
            let mut atual: Vec<String> = vec![];
            for fr in por_frase {
                atual.extend(fr);
                if atual.len() >= FORMAS_POR_SEGMENTO {
                    segs.push(std::mem::take(&mut atual));
                }
            }
            if !atual.is_empty() {
                if !segs.is_empty() && atual.len() < 6 {
                    segs.last_mut().unwrap().extend(atual);
                } else {
                    segs.push(atual);
                }
            }
            segs
        };
        for s in segs {
            segmentos.push(s);
            meta.push((*doc_id, *idi));
        }
    }
    let rotulo: HashMap<String, String> = exib.iter().map(|(no, c)| (no.clone(), mais_comum(c))).collect();
    let docs_usados = meta.iter().map(|m| m.0).collect::<HashSet<_>>().len();
    Prep {
        segmentos,
        meta,
        rotulo,
        docs_por_idioma: por_idioma_docs,
        frases_descartadas: descartadas,
        docs_usados,
        docs_lidos: documentos.len(),
    }
}

// ===================================================================== formas

fn cotas(cand: &[Vec<String>; 3], docs: &IndexMap<&'static str, i64>, n: usize) -> [usize; 3] {
    let idiomas: Vec<usize> = (0..3).filter(|&l| !cand[l].is_empty()).collect();
    let mut cota = [0usize; 3];
    if idiomas.len() == 1 {
        cota[idiomas[0]] = n.min(cand[idiomas[0]].len());
        return cota;
    }
    for &l in &idiomas {
        cota[l] = COTA_MINIMA_IDIOMA.min(cand[l].len());
    }
    let docs_de = |l: usize| docs.get(IDIOMAS[l]).copied().unwrap_or(0);
    while idiomas.iter().map(|&l| cota[l]).sum::<usize>() > n {
        let l = *idiomas.iter().max_by_key(|&&l| (cota[l], l)).unwrap();
        cota[l] -= 1;
    }
    let mut sobra = n - idiomas.iter().map(|&l| cota[l]).sum::<usize>();
    while sobra > 0 {
        let livres: Vec<usize> = idiomas.iter().copied().filter(|&l| cota[l] < cand[l].len()).collect();
        if livres.is_empty() {
            break;
        }
        let total = (livres.iter().map(|&l| docs_de(l)).sum::<i64>()).max(1) as f64;
        let mut ideal = [0.0f64; 3];
        for &l in &livres {
            ideal[l] = sobra as f64 * docs_de(l) as f64 / total;
        }
        let mut dado = 0;
        for &l in &livres {
            let q = (ideal[l] as usize).min(cand[l].len() - cota[l]);
            cota[l] += q;
            dado += q;
        }
        if dado == 0 {
            let l = *livres
                .iter()
                .max_by(|&&a, &&b| {
                    let ka = (ideal[a] - ideal[a].trunc(), docs_de(a), -(a as i64));
                    let kb = (ideal[b] - ideal[b].trunc(), docs_de(b), -(b as i64));
                    ka.partial_cmp(&kb).unwrap()
                })
                .unwrap();
            cota[l] += 1;
            dado = 1;
        }
        sobra -= dado;
    }
    cota
}

fn formas_ativas(prep: &Prep, n_formas: usize) -> (Vec<String>, IndexMap<String, i64>, IndexMap<String, i64>) {
    let mut df: IndexMap<String, i64> = IndexMap::new();
    let mut freq: IndexMap<String, i64> = IndexMap::new();
    for s in &prep.segmentos {
        let mut vistos = HashSet::new();
        for f in s {
            *freq.entry(f.clone()).or_insert(0) += 1;
            if vistos.insert(f) {
                *df.entry(f.clone()).or_insert(0) += 1;
            }
        }
    }
    let mut segs_idioma = [0i64; 3];
    for (_, i) in &prep.meta {
        segs_idioma[idx(i)] += 1;
    }
    let mut cand: [Vec<String>; 3] = Default::default();
    for (no, d) in &df {
        let l = idx(no.split(':').next().unwrap());
        let minimo = if segs_idioma[l] >= 12 { MINIMO_DF } else { MINIMO_DF_POUCOS };
        if *d >= minimo {
            cand[l].push(no.clone());
        }
    }
    let ordena = |v: &mut Vec<String>| {
        v.sort_by(|a, b| df[b].cmp(&df[a]).then(freq[b].cmp(&freq[a])).then(a.cmp(b)));
    };
    for l in 0..3 {
        ordena(&mut cand[l]);
    }
    let c = cotas(&cand, &prep.docs_por_idioma, n_formas);
    let mut escolhidas: Vec<String> = vec![];
    for l in 0..3 {
        escolhidas.extend(cand[l].iter().take(c[l]).cloned());
    }
    ordena(&mut escolhidas);
    (escolhidas, df, freq)
}

// ===================================================================== índices

fn log_comb(n: u64, k: u64) -> f64 {
    ln_fatorial(n) - ln_fatorial(k) - ln_fatorial(n - k)
}

fn peso_binomial(c: u64, di: u64, dj: u64, n: u64) -> f64 {
    let kmax = di.min(dj);
    if c == 0 || c > kmax || n < di.max(dj) {
        return 0.0;
    }
    let base = log_comb(n, dj);
    let mut termos = vec![];
    for k in c..=kmax {
        if k > dj || dj - k > n - di {
            continue;
        }
        termos.push(log_comb(di, k) + log_comb(n - di, dj - k) - base);
    }
    if termos.is_empty() {
        return 0.0;
    }
    let m = termos.iter().cloned().fold(f64::MIN, f64::max);
    let lp = m + crate::util::soma_py(termos.iter().map(|t| (t - m).exp())).ln();
    (-lp / 10f64.ln()).max(0.0)
}

fn matriz_indice(c: &[Vec<i64>], d: &[i64], n_por_forma: &[i64], nome: &str) -> Vec<Vec<f64>> {
    let m = d.len();
    let mut w = vec![vec![0.0f64; m]; m];
    for i in 0..m {
        for j in 0..m {
            if i == j {
                continue;
            }
            let off = c[i][j] as f64;
            let (di, dj) = (d[i] as f64, d[j] as f64);
            w[i][j] = match nome {
                "cooc" => off,
                "jaccard" => off / (di + dj - off).max(1.0),
                "cosseno" => off / (di * dj).max(1.0).sqrt(),
                _ => 0.0,
            };
        }
    }
    if nome == "binomial" {
        for i in 0..m {
            for j in (i + 1)..m {
                if c[i][j] > 0 {
                    let v = peso_binomial(c[i][j] as u64, d[i] as u64, d[j] as u64, n_por_forma[i] as u64);
                    w[i][j] = v;
                    w[j][i] = v;
                }
            }
        }
    }
    w
}

// ===================================================================== grafo e blocos

fn rotulos_legiveis(nos: &[String], rotulo: &HashMap<String, String>, varios: bool) -> HashMap<String, String> {
    let base: HashMap<String, String> = nos
        .iter()
        .map(|n| (n.clone(), rotulo.get(n).cloned().unwrap_or_else(|| n.split_once(':').unwrap().1.to_string())))
        .collect();
    if !varios {
        return base;
    }
    let mut por_texto: HashMap<String, HashSet<&str>> = HashMap::new();
    for (n, t) in &base {
        por_texto.entry(normaliza(t)).or_default().insert(n.split(':').next().unwrap());
    }
    base.iter()
        .map(|(n, t)| {
            let l = n.split(':').next().unwrap();
            let v = if por_texto[&normaliza(t)].len() > 1 { format!("{t} ({l})") } else { t.clone() };
            (n.clone(), v)
        })
        .collect()
}

fn idioma_da_forma(f: &str) -> &str {
    f.split(':').next().unwrap()
}

/// Análise completa a partir de `(id, título, resumo)`.
pub fn analisa_documentos(documentos: &[(i64, String, String)], p: &ParametrosSimilitude) -> Result<Similitude, Erro> {
    if p.idioma != "todos" && !IDIOMAS.contains(&p.idioma.as_str()) {
        return Err("idioma precisa ser todos, en, pt ou es".into());
    }
    if !["jaccard", "cosseno", "binomial", "cooc"].contains(&p.indice.as_str()) {
        return Err("indice precisa ser um de: jaccard, cosseno, binomial, cooc".into());
    }
    if !["resumo", "frase"].contains(&p.segmento.as_str()) {
        return Err("segmento precisa ser um de: resumo, frase".into());
    }
    if documentos.is_empty() {
        return Err(MENSAGEM_SEM_RESUMOS.into());
    }
    let ign = ignorados(&p.ignorar);
    let mut prep = prepara(documentos, &p.segmento, &p.idioma, &ign, p.nivel_lema);
    let mut avisos: Vec<String> = vec![];
    let docs_idioma = prep.docs_por_idioma.clone();
    let docs_de = |l: &str| docs_idioma.get(l).copied().unwrap_or(0);
    if p.idioma != "todos" {
        if docs_de(&p.idioma) < MINIMO_RESUMOS_IDIOMA {
            return Err(format!(
                "Há só {} resumo(s) em {}: poucos para a análise (mínimo {}). Escolha \"todos\" ou outro idioma.",
                docs_de(&p.idioma),
                nome_idioma(&p.idioma),
                MINIMO_RESUMOS_IDIOMA
            ));
        }
    } else {
        let pequenos: Vec<&str> =
            IDIOMAS.iter().copied().filter(|l| docs_de(l) > 0 && docs_de(l) < MINIMO_RESUMOS_IDIOMA).collect();
        if !pequenos.is_empty() {
            let ig: Vec<String> =
                pequenos.iter().map(|l| format!("{} em {}", docs_de(l), nome_idioma(l))).collect();
            avisos.push(format!(
                "Idiomas com menos de {MINIMO_RESUMOS_IDIOMA} resumos não formam blocos próprios; esses resumos ficaram de fora ({}).",
                ig.join("; ")
            ));
            let manter: Vec<usize> =
                (0..prep.meta.len()).filter(|&k| !pequenos.contains(&prep.meta[k].1)).collect();
            prep.segmentos = manter.iter().map(|&k| prep.segmentos[k].clone()).collect();
            prep.meta = manter.iter().map(|&k| prep.meta[k]).collect();
            prep.docs_usados = prep.meta.iter().map(|m| m.0).collect::<HashSet<_>>().len();
        }
    }
    if prep.segmentos.is_empty() {
        return Err(MENSAGEM_SEM_RESUMOS.into());
    }
    let (formas, df, freq) = formas_ativas(&prep, p.n_formas);
    if formas.len() < 3 {
        return Err("O vocabulário dos resumos é pequeno demais para o grafo (menos de 3 palavras repetidas). Use mais resumos, ou reduza a lista de palavras ignoradas.".into());
    }
    let nf = formas.len();
    let pos: HashMap<&str, usize> = formas.iter().enumerate().map(|(k, f)| (f.as_str(), k)).collect();
    let mut c = vec![vec![0i64; nf]; nf];
    for s in &prep.segmentos {
        let mut ids: Vec<usize> = s.iter().filter_map(|f| pos.get(f.as_str()).copied()).collect();
        ids.sort();
        ids.dedup();
        for &a in &ids {
            for &b in &ids {
                c[a][b] += 1;
            }
        }
    }
    let d: Vec<i64> = formas.iter().map(|f| df[f]).collect();
    let mut segs_idioma = [0i64; 3];
    for (_, i) in &prep.meta {
        segs_idioma[idx(i)] += 1;
    }
    let n_forma: Vec<i64> = formas.iter().map(|f| segs_idioma[idx(idioma_da_forma(f))]).collect();
    let w = matriz_indice(&c, &d, &n_forma, &p.indice);
    // grafo completo (arestas i<j com peso > 0)
    let mut g_arestas: Vec<(usize, usize, f64)> = vec![];
    for i in 0..nf {
        for j in (i + 1)..nf {
            if w[i][j] > 0.0 {
                g_arestas.push((i, j, w[i][j]));
            }
        }
    }
    // árvore máxima (Kruskal; empate pelo nome)
    let nome = |i: usize| formas[i].as_str();
    let mut ordenadas = g_arestas.clone();
    ordenadas.sort_by(|a, b| {
        b.2.partial_cmp(&a.2)
            .unwrap()
            .then(nome(a.0).min(nome(a.1)).cmp(nome(b.0).min(nome(b.1))))
            .then(nome(a.0).max(nome(a.1)).cmp(nome(b.0).max(nome(b.1))))
    });
    // nós da árvore em ordem de nome
    let mut ordem_nos: Vec<usize> = (0..nf).collect();
    ordem_nos.sort_by(|&a, &b| nome(a).cmp(nome(b)));
    let mut no_de: Vec<usize> = vec![0; nf]; // forma -> índice na ordem dos nomes
    for (k, &f) in ordem_nos.iter().enumerate() {
        no_de[f] = k;
    }
    let mut pai: Vec<usize> = (0..nf).collect();
    fn raiz(pai: &mut Vec<usize>, mut x: usize) -> usize {
        while pai[x] != x {
            pai[x] = pai[pai[x]];
            x = pai[x];
        }
        x
    }
    let mut arvore = Grafo::com_nos(nf);
    let mut arv_pares: HashSet<(usize, usize)> = HashSet::new();
    let mut arv_lista: Vec<(usize, usize, f64)> = vec![];
    for &(u, v, wt) in &ordenadas {
        // a união usa a raiz de menor nome
        let (ru, rv) = (raiz(&mut pai, no_de[u]), raiz(&mut pai, no_de[v]));
        if ru != rv {
            pai[ru.max(rv)] = ru.min(rv);
            arvore.add_aresta(no_de[u], no_de[v], wt);
            arv_pares.insert((u.min(v), u.max(v)));
            arv_lista.push((u, v, wt));
        }
    }
    // extras
    let k_extras = py_round_int(p.extras as f64 / 100.0 * arv_lista.len() as f64).max(0) as usize;
    let mut extras: Vec<(usize, usize, f64)> = vec![];
    if k_extras > 0 {
        let mut fora: Vec<(usize, usize, f64)> = g_arestas
            .iter()
            .filter(|(u, v, _)| !arv_pares.contains(&(*u, *v)))
            .map(|&(u, v, wt)| if nome(u) <= nome(v) { (u, v, wt) } else { (v, u, wt) })
            .collect();
        fora.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap().then(nome(a.0).cmp(nome(b.0))).then(nome(a.1).cmp(nome(b.1))));
        extras = fora.into_iter().take(k_extras).collect();
    }
    // comunidades (Louvain sobre a árvore; nós na ordem dos nomes)
    let mut blocos_nos: Vec<Vec<usize>> = if arv_lista.is_empty() {
        (0..nf).map(|k| vec![k]).collect()
    } else {
        louvain(&arvore, RESOLUCAO, 1e-7, SEMENTE)
    };
    // índice na ordem dos nomes -> forma
    for b in blocos_nos.iter_mut() {
        for x in b.iter_mut() {
            *x = ordem_nos[*x];
        }
    }
    let soma_df = |b: &Vec<usize>| b.iter().map(|&f| df[&formas[f]]).sum::<i64>();
    let min_nome = |b: &Vec<usize>| b.iter().map(|&f| formas[f].clone()).min().unwrap();
    blocos_nos.sort_by(|a, b| {
        b.len().cmp(&a.len()).then(soma_df(b).cmp(&soma_df(a))).then(min_nome(a).cmp(&min_nome(b)))
    });
    let mut com = vec![0usize; nf];
    for (k, b) in blocos_nos.iter().enumerate() {
        for &f in b {
            com[f] = k + 1;
        }
    }
    let usados: Vec<&str> =
        IDIOMAS.iter().copied().filter(|l| formas.iter().any(|f| f.starts_with(&format!("{l}:")))).collect();
    let rot = rotulos_legiveis(&formas, &prep.rotulo, usados.len() > 1);
    let mut grau = vec![0i64; nf];
    for &(u, v, _) in arv_lista.iter().chain(extras.iter()) {
        grau[u] += 1;
        grau[v] += 1;
    }
    let mut docs_forma: Vec<HashSet<i64>> = vec![HashSet::new(); nf];
    for (s, (doc_id, _)) in prep.segmentos.iter().zip(prep.meta.iter()) {
        for f in s {
            if let Some(&k) = pos.get(f.as_str()) {
                docs_forma[k].insert(*doc_id);
            }
        }
    }
    let linhas: Vec<Forma> = (0..nf)
        .map(|k| Forma {
            id: formas[k].clone(),
            forma: rot[&formas[k]].clone(),
            idioma: idioma_da_forma(&formas[k]).to_string(),
            frequencia: df[&formas[k]],
            resumos: docs_forma[k].len(),
            ocorrencias: freq[&formas[k]],
            comunidade: com[k],
            grau: grau[k],
        })
        .collect();
    let mut arv_ord: Vec<(usize, usize, f64)> =
        arv_lista.iter().map(|&(u, v, wt)| if nome(u) <= nome(v) { (u, v, wt) } else { (v, u, wt) }).collect();
    arv_ord.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap().then(nome(a.0).cmp(nome(b.0))).then(nome(a.1).cmp(nome(b.1))));
    let mut arestas: Vec<ArestaSim> = arv_ord
        .iter()
        .map(|&(u, v, wt)| ArestaSim { origem: formas[u].clone(), destino: formas[v].clone(), peso: wt, tipo: "arvore".into() })
        .collect();
    arestas.extend(
        extras.iter().map(|&(u, v, wt)| ArestaSim { origem: formas[u].clone(), destino: formas[v].clone(), peso: wt, tipo: "extra".into() }),
    );
    let mut comunidades: Vec<ComunidadeInfo> = vec![];
    let n_com = blocos_nos.len();
    for k in 1..=n_com {
        let mut mem: Vec<usize> = (0..nf).filter(|&f| com[f] == k).collect();
        mem.sort_by(|&a, &b| df[&formas[b]].cmp(&df[&formas[a]]).then(formas[a].cmp(&formas[b])));
        let nomes: Vec<String> = mem.iter().take(3).map(|&f| rot[&formas[f]].clone()).collect();
        let mut idiomas: Vec<String> = mem.iter().map(|&f| idioma_da_forma(&formas[f]).to_string()).collect();
        idiomas.sort();
        idiomas.dedup();
        comunidades.push(ComunidadeInfo { id: k, n: mem.len(), nome: nomes.join(", "), idiomas });
    }
    let componentes = arvore.componentes().len();
    if componentes > 1 && usados.len() <= 1 {
        avisos.push(format!(
            "As palavras escolhidas formam {componentes} grupos desconexos: algumas não aparecem junto das demais em nenhum resumo."
        ));
    }
    if prep.frases_descartadas > 0 {
        avisos.push(format!(
            "{} frase(s) de resumos bilíngues, em idioma diferente do do resumo, foram desconsideradas.",
            prep.frases_descartadas
        ));
    }
    let mut ign_v: Vec<String> = ign.iter().cloned().collect();
    ign_v.sort();
    let mut dpi: IndexMap<String, i64> = IndexMap::new();
    for l in IDIOMAS {
        if docs_de(l) > 0 {
            dpi.insert(l.to_string(), docs_de(l));
        }
    }
    Ok(Similitude {
        parametros: ParametrosUsados {
            n_formas: p.n_formas,
            indice: p.indice.clone(),
            segmento: p.segmento.clone(),
            extras: p.extras,
            idioma: p.idioma.clone(),
            periodo: p.periodo.clone(),
            ignorar: ign_v,
            semente: SEMENTE,
        },
        n_resumos: prep.docs_usados,
        n_lidos: prep.docs_lidos,
        n_segmentos: prep.segmentos.len(),
        docs_por_idioma: dpi,
        idiomas_nas_formas: usados.iter().map(|s| s.to_string()).collect(),
        formas: linhas,
        arestas,
        comunidades,
        n_arvore: arv_lista.len(),
        n_extras: extras.len(),
        componentes,
        avisos,
    })
}

/// Lê os resumos do projeto e roda a análise.
pub fn analisa(c: &Connection, periodo_id: Option<i64>, p: &ParametrosSimilitude) -> Result<Similitude, Erro> {
    analisa_documentos(&le_resumos(c, periodo_id)?, p)
}

// ===================================================================== exportações

pub fn descreve_parametros(res: &Similitude) -> Vec<(String, String)> {
    let p = &res.parametros;
    let idioma = if p.idioma == "todos" {
        let v: Vec<String> = res.docs_por_idioma.iter().map(|(l, n)| format!("{} {}", nome_idioma(l), n)).collect();
        format!("todos ({})", v.join(", "))
    } else {
        nome_idioma(&p.idioma).to_string()
    };
    let mut itens = vec![
        (
            "Resumos usados".to_string(),
            format!("{} de {} com resumo; {} segmento(s)", res.n_resumos, res.n_lidos, res.n_segmentos),
        ),
        ("Idioma".into(), idioma),
        ("Período".into(), p.periodo.clone()),
        ("Formas ativas".into(), res.formas.len().to_string()),
        ("Índice".into(), nome_indice(&p.indice).into()),
        ("Segmento".into(), nome_segmento(&p.segmento).into()),
        (
            "Arestas".into(),
            format!("árvore máxima ({})", res.n_arvore)
                + &if res.n_extras > 0 { format!(" + {} extras ({}%)", res.n_extras, p.extras) } else { String::new() },
        ),
        ("Blocos".into(), format!("{} (Louvain, semente {})", res.comunidades.len(), p.semente)),
    ];
    if !p.ignorar.is_empty() {
        itens.push(("Palavras ignoradas".into(), p.ignorar.join(", ")));
    }
    itens
}

/// Uma linha para o rodapé da figura.
pub fn texto_parametros(res: &Similitude) -> String {
    let p = &res.parametros;
    let idi = if p.idioma == "todos" { "todos os idiomas".to_string() } else { nome_idioma(&p.idioma).to_string() };
    format!(
        "{} resumos · {} · {} palavras · índice: {} · segmento: {} · árvore máxima{} · blocos: Louvain ({})",
        res.n_resumos,
        idi,
        res.formas.len(),
        nome_indice(&p.indice),
        nome_segmento(&p.segmento),
        if res.n_extras > 0 { format!(" + {}% de arestas extras", p.extras) } else { String::new() },
        res.comunidades.len()
    )
}

fn xml_esc(t: &str) -> String {
    t.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;")
}

/// GraphML como o `nx.generate_graphml(named_key_ids=True)`.
pub fn graphml(res: &Similitude) -> String {
    let mut o = String::new();
    o.push_str("<graphml xmlns=\"http://graphml.graphdrawing.org/xmlns\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd\">\n");
    for (nome, tipo) in [("tipo", "string"), ("peso", "double")] {
        o.push_str(&format!("  <key id=\"{nome}\" for=\"edge\" attr.name=\"{nome}\" attr.type=\"{tipo}\" />\n"));
    }
    for (nome, tipo) in [
        ("grau", "long"), ("comunidade", "long"), ("ocorrencias", "long"), ("resumos", "long"),
        ("frequencia", "long"), ("idioma", "string"), ("forma", "string"),
    ] {
        o.push_str(&format!("  <key id=\"{nome}\" for=\"node\" attr.name=\"{nome}\" attr.type=\"{tipo}\" />\n"));
    }
    o.push_str("  <graph edgedefault=\"undirected\">\n");
    let pos: HashMap<&str, usize> = res.formas.iter().enumerate().map(|(k, f)| (f.id.as_str(), k)).collect();
    for f in &res.formas {
        o.push_str(&format!("    <node id=\"{}\">\n", xml_esc(&f.id)));
        o.push_str(&format!("      <data key=\"forma\">{}</data>\n", xml_esc(&f.forma)));
        o.push_str(&format!("      <data key=\"idioma\">{}</data>\n", xml_esc(&f.idioma)));
        o.push_str(&format!("      <data key=\"frequencia\">{}</data>\n", f.frequencia));
        o.push_str(&format!("      <data key=\"resumos\">{}</data>\n", f.resumos));
        o.push_str(&format!("      <data key=\"ocorrencias\">{}</data>\n", f.ocorrencias));
        o.push_str(&format!("      <data key=\"comunidade\">{}</data>\n", f.comunidade));
        o.push_str(&format!("      <data key=\"grau\">{}</data>\n", f.grau));
        o.push_str("    </node>\n");
    }
    // ordem de `G.edges()`: por nó, vizinhos na ordem de inserção
    let mut g = Grafo::com_nos(res.formas.len());
    let mut dados: HashMap<(usize, usize), (f64, &str)> = HashMap::new();
    for a in &res.arestas {
        let (u, v) = (pos[a.origem.as_str()], pos[a.destino.as_str()]);
        g.add_aresta(u, v, a.peso);
        dados.insert((u, v), (a.peso, a.tipo.as_str()));
        dados.insert((v, u), (a.peso, a.tipo.as_str()));
    }
    for (u, v, _) in g.arestas() {
        let (peso, tipo) = dados[&(u, v)];
        o.push_str(&format!(
            "    <edge source=\"{}\" target=\"{}\">\n      <data key=\"peso\">{}</data>\n      <data key=\"tipo\">{}</data>\n    </edge>\n",
            xml_esc(&res.formas[u].id),
            xml_esc(&res.formas[v].id),
            pyf(peso),
            tipo
        ));
    }
    o.push_str("  </graph>\n</graphml>\n");
    o
}

fn campo_csv(c: &str) -> String {
    if c.contains(',') || c.contains('"') || c.contains('\n') || c.contains('\r') {
        format!("\"{}\"", c.replace('"', "\"\""))
    } else {
        c.to_string()
    }
}

fn linha_csv(v: &[String]) -> String {
    v.iter().map(|c| campo_csv(c)).collect::<Vec<_>>().join(",") + "\n"
}

pub fn csv_formas(res: &Similitude) -> String {
    let mut o = String::from("\u{feff}");
    o += &linha_csv(&["forma", "idioma", "frequencia_segmentos", "resumos", "ocorrencias", "bloco", "grau"].map(String::from));
    let mut fs: Vec<&Forma> = res.formas.iter().collect();
    fs.sort_by(|a, b| a.comunidade.cmp(&b.comunidade).then(b.frequencia.cmp(&a.frequencia)).then(a.forma.cmp(&b.forma)));
    for f in fs {
        o += &linha_csv(&[
            f.forma.clone(),
            f.idioma.clone(),
            f.frequencia.to_string(),
            f.resumos.to_string(),
            f.ocorrencias.to_string(),
            f.comunidade.to_string(),
            f.grau.to_string(),
        ]);
    }
    o
}

pub fn csv_arestas(res: &Similitude) -> String {
    let nome: HashMap<&str, &str> = res.formas.iter().map(|f| (f.id.as_str(), f.forma.as_str())).collect();
    let mut o = String::from("\u{feff}");
    o += &linha_csv(&["origem", "destino", "peso", "tipo"].map(String::from));
    for a in &res.arestas {
        o += &linha_csv(&[
            nome[a.origem.as_str()].to_string(),
            nome[a.destino.as_str()].to_string(),
            format!("{:.6}", a.peso),
            if a.tipo == "arvore" { "árvore".into() } else { "extra".into() },
        ]);
    }
    o
}
