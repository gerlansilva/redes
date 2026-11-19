//! Interpretação de referências citadas em texto livre (porta de `references.py`).
//!
//! A referência vira `AUTOR, ANO, FONTE, Vvolume, Ppáginas, Título`.

use std::collections::HashSet;

use unicode_normalization::UnicodeNormalization;

use crate::rx;
use crate::util::*;

pub const SEM_AUTOR: &str = "Sem autor";
pub const SEM_FONTE: &str = "Sem fonte";

const PAGINA: &str = r"(?=[^\s,]*\d|[ivxlc]+\s*[-–—])[^\s,]+(?:\s*[-–—]\s*[^\s,]+)?";

const PALAVRAS_DE_TITULO: &[&str] = &["of", "the", "and", "for", "in", "on", "a", "an", "to", "with", "from", "by", "at", "as"];

const PALAVRAS_DE_FONTE: &[&str] = &[
    "journal", "proceedings", "conference", "congress", "symposium", "workshop", "transaction", "review", "quarterly", "bulletin",
    "annals", "letters", "magazine", "press", "publishing", "springer", "elsevier", "wiley", "routledge", "sage", "acm", "ieee",
    "association", "society", "education", "educational", "science", "sciences", "computing", "computer", "psychology", "learning",
    "technology", "research", "studies", "international", "university", "handbook", "books", "educ",
];
const INICIO_DE_FONTE: &[&str] = &["proceedings", "conference", "journal", "transaction", "transactions", "symposium", "workshop", "annals", "bulletin"];
const INICIO_DE_FONTE_ABREVIADO: &[&str] = &[
    "univ", "univ.", "universidad", "universidade", "university", "editorial", "publisher", "psychol", "psychol.", "monogr", "monogr.",
    "rev", "rev.", "revista",
];
const PARTICULAS: &[&str] = &[
    "van", "von", "der", "den", "ter", "ten", "te", "del", "della", "di", "du", "la", "le", "al", "el", "bin", "ibn", "af", "av", "zu",
];
const CONECTORES: &[&str] = &["and", "of", "for", "in", "on", "with", "by", "at", "as", "to", "from", "de", "da", "do", "das", "dos", "e", "y", "und", "et"];
const NAO_SOBRENOME: &[&str] = &[
    "statistics", "mathematics", "probability", "data", "learning", "teaching", "children", "report", "annual", "introduction", "education",
    "science", "research", "handbook", "proceedings", "journal", "review", "studies", "mathematik", "matematica", "estatistica",
    "probabilidad", "estadistica",
];
const RUIDO_DE_DUPLICATA: &[&str] = &["p", "pp", "v", "vol", "volume", "n", "no", "issue", "numero"];

macro_rules! cheio {
    ($p:expr, $s:expr) => {{
        static R: std::sync::OnceLock<fancy_regex::Regex> = std::sync::OnceLock::new();
        R.get_or_init(|| fancy_regex::Regex::new(concat!(r"^(?:", $p, r")$")).expect("regex")).is_match($s).unwrap_or(false)
    }};
}

pub fn limpa_texto(valor: &str) -> String {
    let t = html_unescape(valor);
    let t = rx!(r"<[^>]+>").replace_all(&t, "").replace(['\r', '\n'], " ");
    let mut out = String::with_capacity(t.len());
    let mut espaco = false;
    for c in strip(&t).chars() {
        if e_espaco(c) {
            espaco = true;
        } else {
            if espaco {
                out.push(' ');
                espaco = false;
            }
            out.push(c);
        }
    }
    out
}

fn palavras_de(s: &str) -> Vec<&str> {
    s.split(' ').collect()
}

pub fn parece_autor(segmento: &str) -> bool {
    let segmento = strip(segmento);
    if segmento.is_empty() || (n_chars(segmento) > 160 && !segmento.contains(';')) {
        return false;
    }
    if segmento.contains(';') {
        let partes: Vec<&str> = segmento.split(';').map(strip).filter(|p| !p.is_empty()).collect();
        if partes.is_empty() || partes.len() > 200 {
            return false;
        }
        return partes.iter().all(|p| palavras(p).len() <= 5);
    }
    if rx!(r"^[^\W\d_][^,;]*\s(?:[A-Z]\.?-?)+$").is_match(segmento).unwrap_or(false) {
        let ps = palavras(segmento);
        if ps.len() > 6 {
            return false;
        }
        if ps.iter().any(|p| {
            let m = p.to_lowercase();
            primeira_minuscula(p) && !CONECTORES.contains(&m.as_str()) && !PARTICULAS.contains(&m.as_str()) && !rx!(r"^[a-z]{2,4}[A-Z]").is_match(p).unwrap_or(false)
        }) {
            return false;
        }
        return true;
    }
    let ps = palavras(segmento);
    if !(2..=4).contains(&ps.len()) || n_chars(segmento) > 45 {
        return false;
    }
    if ps.iter().any(|p| PALAVRAS_DE_TITULO.contains(&p.to_lowercase().as_str())) {
        return false;
    }
    ps.iter().all(|p| primeira_maiuscula(p))
}

fn autor_com_iniciais(segmento: &str) -> bool {
    if !parece_autor(segmento) || segmento.contains(':') {
        return false;
    }
    if rx!(r"\b[A-Z]\.(?:[A-Z]\.){2,}").is_match(segmento).unwrap_or(false) {
        return false;
    }
    let ultimo = palavras(segmento).last().copied().unwrap_or("");
    cheio!(r"[A-Z]\.?(?:[A-Z]\.?)?", ultimo)
}

fn sobrenome_solto(segmentos: &[String]) -> bool {
    if segmentos.len() < 3 {
        return false;
    }
    let primeiro = &segmentos[0];
    if !cheio!(r"[^\W\d_][^\W\d_'’-]{1,24}(?:[-'’][^\W\d_]{1,24})?", primeiro) {
        return false;
    }
    if !primeira_maiuscula(primeiro) || (eh_maiuscula(primeiro) && n_chars(primeiro) > 5) {
        return false;
    }
    if NAO_SOBRENOME.contains(&primeiro.to_lowercase().as_str()) || parece_fonte(primeiro) {
        return false;
    }
    let segundo = &segmentos[1];
    palavras(segundo).len() >= 2 && primeira_maiuscula(segundo)
}

pub fn parece_fonte(texto: &str) -> bool {
    let m = texto.to_lowercase();
    PALAVRAS_DE_FONTE.iter().any(|p| m.contains(p))
}

fn limpa_campo(valor: &str) -> String {
    let t = valor.replace("//", "/").replace(',', " ");
    palavras(&t).join(" ")
}

fn limpa_titulo(valor: &str) -> String {
    strip(&palavras(valor).join(" ").replace("//", "/")).to_string()
}

fn tokens(texto: &str) -> Vec<String> {
    let t: String = texto.nfkd().filter(|c| !combina(*c)).collect::<String>().to_lowercase();
    rx!(r"[a-z0-9]+").find_iter(&t).flatten().map(|m| m.as_str().to_string()).collect()
}

fn ruido(t: &str) -> bool {
    (!t.is_empty() && t.chars().all(eh_digito)) || RUIDO_DE_DUPLICATA.contains(&t)
}

fn encontra_repeticao(segmentos: &[String]) -> Option<(usize, usize)> {
    let toks: Vec<Vec<String>> = segmentos.iter().map(|s| tokens(s)).collect();
    for j in 1..segmentos.len() {
        let cauda: Vec<&String> = toks[j..].iter().flatten().collect();
        if cauda.is_empty() {
            continue;
        }
        for k in 0..j {
            let janela: Vec<&String> = toks[k..j].iter().flatten().collect();
            if janela.is_empty() {
                continue;
            }
            if janela.len() == 1 {
                if cauda.len() == 1 && janela == cauda && n_chars(janela[0]) >= 3 {
                    return Some((k, j));
                }
                continue;
            }
            if cauda.len() < janela.len() || cauda[..janela.len()] != janela[..] {
                continue;
            }
            if cauda[janela.len()..].iter().all(|t| ruido(t)) {
                return Some((k, j));
            }
        }
    }
    None
}

fn separa_paginas(segmentos: Vec<String>, mut paginas: String) -> (Vec<String>, String) {
    static RE: std::sync::OnceLock<fancy_regex::Regex> = std::sync::OnceLock::new();
    let re = RE.get_or_init(|| fancy_regex::Regex::new(&format!(r"(?i)(?:^|\s)p{{1,2}}\.\s*({PAGINA})\s*$")).unwrap());
    let mut restantes = vec![];
    for mut segmento in segmentos {
        if let Ok(Some(c)) = re.captures(&segmento) {
            if paginas.is_empty() {
                paginas = c.get(1).unwrap().as_str().to_string();
            }
            let ini = c.get(0).unwrap().start();
            segmento = strip_chars(&segmento[..ini], " ,").to_string();
        }
        if !segmento.is_empty() {
            restantes.push(segmento);
        }
    }
    (restantes, paginas)
}

fn segmentos_de(texto: &str) -> Vec<String> {
    let mut partes = vec![];
    let mut atual = String::new();
    let mut prof: i32 = 0;
    for c in texto.chars() {
        if c == '(' || c == '[' {
            prof += 1;
        } else if c == ')' || c == ']' {
            prof = (prof - 1).max(0);
        }
        if c == ',' && prof == 0 {
            let p = strip(&atual);
            if !p.is_empty() {
                partes.push(p.to_string());
            }
            atual.clear();
        } else {
            atual.push(c);
        }
    }
    let p = strip(&atual);
    if !p.is_empty() {
        partes.push(p.to_string());
    }
    partes
}

fn numero_curto(s: &str) -> bool {
    cheio!(r"\d{1,6}", s)
}

/// Referência do Scopus/OpenAlex no formato guardado pelo Redes.
pub fn converte_referencia(bruta: &str) -> Option<String> {
    let texto = palavras(bruta).join(" ");
    let texto = strip(texto.trim_end_matches(';')).to_string();
    let texto = strip(&rx!(r"^(?:\[\s*\d+\s*\]|\(\s*\d+\s*\)|\d{1,3}\.)\s*").replace(&texto, "")).to_string();
    if texto.is_empty() {
        return None;
    }
    let mut texto = texto;
    let mut ano = String::new();
    if let Ok(Some(m)) = rx!(r"(?i)[,\s]*\(\s*(\d{4}[a-z]?)\s*\)\s*$").captures(&texto) {
        ano = m.get(1).unwrap().as_str().to_string();
        let ini = m.get(0).unwrap().start();
        texto = strip(&texto[..ini]).trim_end_matches(',').to_string();
        texto = strip(&texto).to_string();
    }
    let mut paginas = String::new();
    static RE_PAG_FIM: std::sync::OnceLock<fancy_regex::Regex> = std::sync::OnceLock::new();
    let re_pag_fim = RE_PAG_FIM.get_or_init(|| fancy_regex::Regex::new(&format!(r"(?i),\s*p{{1,2}}\.\s*({PAGINA})\s*$")).unwrap());
    if let Ok(Some(m)) = re_pag_fim.captures(&texto) {
        paginas = m.get(1).unwrap().as_str().to_string();
        let ini = m.get(0).unwrap().start();
        texto = strip(&texto[..ini]).trim_end_matches(',').to_string();
        texto = strip(&texto).to_string();
    }
    let t2 = rx!(r"(?i),\s*(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+\s*$").replace(&texto, "").to_string();
    let texto = strip(strip(&t2).trim_end_matches(',')).to_string();
    if texto.is_empty() {
        return None;
    }
    let mut segmentos = segmentos_de(&texto);
    if segmentos.is_empty() {
        return None;
    }
    if segmentos.len() == 1 && ano.is_empty() {
        return None;
    }
    if ano.is_empty() && segmentos.len() >= 3 && cheio!(r"\d{4}[a-z]?", &segmentos[1]) {
        ano = segmentos[1].clone();
        segmentos.remove(1);
    }
    let (segs, pag) = separa_paginas(segmentos, paginas);
    segmentos = segs;
    paginas = pag;

    if segmentos.len() == 1
        && !ano.is_empty()
        && paginas.is_empty()
        && (autor_com_iniciais(&segmentos[0]) || (segmentos[0].contains(';') && parece_autor(&segmentos[0])))
    {
        return Some(
            [limpa_campo(&segmentos[0]), ano, SEM_FONTE.to_string(), String::new(), String::new(), String::new()].join(", "),
        );
    }

    let mut autores: Vec<String> = vec![];
    while segmentos.len() > 1 && parece_autor(&segmentos[0]) {
        if !autores.is_empty() && !(autor_com_iniciais(&segmentos[0]) || segmentos[0].contains(';')) {
            break;
        }
        autores.push(segmentos.remove(0));
    }
    if autores.is_empty()
        && segmentos.len() >= 3
        && cheio!(r"(?:[A-Z]\.?\s?-?){1,4}", &segmentos[1])
        && cheio!(r"[^\W\d_][\w'’ -]{1,40}", &segmentos[0])
    {
        let a = segmentos.remove(0);
        let b = segmentos.remove(0);
        autores.push(format!("{a} {b}"));
    } else if autores.is_empty() && sobrenome_solto(&segmentos) {
        autores.push(segmentos.remove(0));
    }
    let autor = autores.join("; ");

    let numeros: Vec<String>;
    let fonte: String;
    let titulo: String;

    if let Some((inicio, fim)) = encontra_repeticao(&segmentos) {
        let mut janela: Vec<String> = segmentos[inicio..fim].to_vec();
        let mut nums: Vec<String> = vec![];
        while janela.last().map_or(false, |u| numero_curto(u)) {
            nums.insert(0, janela.pop().unwrap());
        }
        for parte in &segmentos[fim..] {
            if numero_curto(parte) && !nums.contains(parte) {
                nums.push(parte.clone());
            }
        }
        fonte = janela.join(", ");
        titulo = segmentos[..inicio].join(", ");
        numeros = nums;
        segmentos.clear();
    } else {
        let mut nums: Vec<String> = vec![];
        while let Some(ultimo) = segmentos.last().cloned() {
            if numero_curto(&ultimo) {
                nums.insert(0, segmentos.pop().unwrap());
                continue;
            }
            let anterior = if segmentos.len() >= 2 { segmentos[segmentos.len() - 2].clone() } else { String::new() };
            let parece_numero = cheio!(r"\d{1,6}\s*[-–—]\s*\d{1,6}", &ultimo)
                || cheio!(r"[A-Z]", &ultimo)
                || rx!(r"(?i)^(?:(?:Suppl\.?|S|Pt\.?)\s*\d{1,3})$").is_match(&ultimo).unwrap_or(false);
            if parece_numero && numero_curto(&anterior) {
                nums.insert(0, segmentos.pop().unwrap());
                continue;
            }
            break;
        }
        if segmentos.is_empty() {
            return None;
        }
        let tem_ancora = !nums.is_empty() || !paginas.is_empty();
        let mut f = String::new();
        let mut t = segmentos.join(", ");

        if segmentos.len() == 1 && !tem_ancora {
            let primeira = palavras_de(&segmentos[0])[0].to_lowercase();
            let primeira = primeira.trim_matches(',');
            if INICIO_DE_FONTE.contains(&primeira) {
                f = segmentos.pop().unwrap();
                t = String::new();
            }
        } else {
            let ultimo_seg = segmentos.last().unwrap();
            let c1 = parece_fonte(ultimo_seg)
                && (primeira_maiuscula(ultimo_seg) || primeiro_digito(ultimo_seg))
                && !CONECTORES.contains(&palavras_de(ultimo_seg)[0].to_lowercase().as_str());
            let c2 = segmentos.len() >= 2 && INICIO_DE_FONTE_ABREVIADO.contains(&segmentos[segmentos.len() - 2].to_lowercase().trim_matches(',').to_string().as_str());
            if tem_ancora || c1 || c2 {
                let mut primeira = true;
                let primeira_ultimo = palavras_de(segmentos.last().unwrap())[0].to_lowercase().trim_matches(',').to_string();
                while segmentos.len() >= 2 {
                    let anterior = segmentos[segmentos.len() - 2].clone();
                    let ultimo = segmentos[segmentos.len() - 1].clone();
                    let primeira_anterior = palavras_de(&anterior)[0].to_lowercase().trim_matches(',').to_string();
                    let continua = INICIO_DE_FONTE.contains(&primeira_anterior.as_str())
                        || INICIO_DE_FONTE_ABREVIADO.contains(&primeira_anterior.as_str())
                        || (primeira && CONECTORES.contains(&primeira_ultimo.as_str()))
                        || (CONECTORES.contains(&primeira_anterior.as_str()) && parece_fonte(&anterior));
                    if continua {
                        let n = segmentos.len();
                        segmentos.truncate(n - 2);
                        segmentos.push(format!("{anterior}, {ultimo}"));
                        primeira = false;
                    } else {
                        break;
                    }
                }
                f = segmentos.pop().unwrap();
                t = segmentos.join(", ");
                if f.to_lowercase().starts_with("in ") {
                    f = strip(&f[3..]).to_string();
                }
            }
        }
        fonte = f;
        titulo = t;
        numeros = nums;
    }

    if titulo.is_empty() && fonte.is_empty() {
        return None;
    }
    let autor = if autor.is_empty() { SEM_AUTOR.to_string() } else { autor };
    let fonte = if fonte.is_empty() { SEM_FONTE.to_string() } else { fonte };
    let l_autor = limpa_campo(&autor);
    let l_fonte = limpa_campo(&fonte);
    let campos = [
        if l_autor.is_empty() { SEM_AUTOR.to_string() } else { l_autor },
        ano,
        if l_fonte.is_empty() { SEM_FONTE.to_string() } else { l_fonte },
        numeros.first().map(|n| format!("V{}", limpa_campo(n))).unwrap_or_default(),
        if paginas.is_empty() { String::new() } else { format!("P{}", limpa_campo(&paginas)) },
        limpa_titulo(&titulo),
    ];
    Some(campos.join(", "))
}

/// Nome curto e único do grupo de referências (autor, ano e fonte).
pub fn nome_do_grupo(completa: &str, usados: &HashSet<String>) -> String {
    let campos: Vec<&str> = completa.splitn(7, ',').collect();
    let g = |i: usize| campos.get(i).map(|s| strip(s)).unwrap_or("");
    let (mut autor, ano, fonte, volume, paginas, titulo) = (g(0).to_string(), g(1), g(2), g(3), g(4), g(5));
    if let Some(p) = autor.find(';') {
        autor = format!("{} et al.", strip(&autor[..p]));
    }
    let mut base = autor;
    if !ano.is_empty() {
        base = format!("{base}, {ano}");
    }
    let fonte_ok = !fonte.is_empty() && fonte.to_lowercase() != SEM_FONTE.to_lowercase();
    if fonte_ok && n_chars(fonte) <= 30 {
        base = format!("{base}, {fonte}");
    } else if ano.is_empty() && fonte_ok {
        base = format!("{base}, {fonte}");
    } else if ano.is_empty() && !titulo.is_empty() {
        base = format!("{base}, {titulo}");
    }
    let mut tentativas = vec![base.clone()];
    if !volume.is_empty() {
        tentativas.push(format!("{base}, {volume}"));
        if !paginas.is_empty() {
            tentativas.push(format!("{base}, {volume}, {paginas}"));
        }
    }
    tentativas.push(completa.to_string());
    for t in tentativas {
        if !usados.contains(&t) {
            return t;
        }
    }
    let mut n = 2;
    loop {
        let nome = format!("{base} ({n})");
        if !usados.contains(&nome) {
            return nome;
        }
        n += 1;
    }
}

/// Divide por `;` que segue `)`: `(?<=\));\s*`.
pub fn separa_referencias(valor: &str) -> Vec<&str> {
    let mut partes = vec![];
    let mut ini = 0;
    for m in rx!(r"(?<=\));\s*").find_iter(valor).flatten() {
        partes.push(&valor[ini..m.start()]);
        ini = m.end();
    }
    partes.push(&valor[ini..]);
    partes
}

