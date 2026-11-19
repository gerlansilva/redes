//! Reconhecimento de países nas afiliações (porta de `paises.py`).

use std::collections::HashMap;
use std::sync::OnceLock;

use regex::Regex;
use unicode_normalization::char::is_combining_mark;
use unicode_normalization::UnicodeNormalization;

use crate::tabelas::{ALIAS_PAISES, PAISES, SIGLAS_EUA};

fn chave(texto: &str) -> String {
    let t: String = texto.nfkd().filter(|c| !is_combining_mark(*c)).collect();
    let t = t.split_whitespace().collect::<Vec<_>>().join(" ");
    t.trim_matches(|c| " .,;:()[]".contains(c)).to_lowercase()
}

fn indice() -> &'static HashMap<String, &'static str> {
    static I: OnceLock<HashMap<String, &'static str>> = OnceLock::new();
    I.get_or_init(|| {
        let mut m: HashMap<String, &'static str> = HashMap::new();
        for (nome, canonico) in PAISES {
            m.insert(chave(nome), canonico);
        }
        for (nome, canonico) in ALIAS_PAISES {
            m.entry(chave(nome)).or_insert(canonico);
        }
        for (_, canonico) in PAISES {
            m.entry(chave(canonico)).or_insert(canonico);
        }
        m
    })
}

/// Nome canônico do país, ou vazio quando o texto não é um país.
pub fn pais(texto: &str) -> String {
    indice().get(&chave(texto)).map(|s| s.to_string()).unwrap_or_default()
}

fn partes(afiliacao: &str) -> Vec<String> {
    static E: OnceLock<Regex> = OnceLock::new();
    let e = E.get_or_init(|| Regex::new(r"(?i)\bemail:.*$").unwrap());
    let texto = afiliacao.replace('\n', " ");
    let texto = e.replace(&texto, "").into_owned();
    texto
        .split(',')
        .filter(|p| !p.trim().is_empty())
        .map(|p| p.trim().trim_matches(|c| " .,;:()[]".contains(c)).to_string())
        .collect()
}

/// País no fim de uma afiliação do tipo `Instituição, Cidade, País`.
pub fn pais_da_afiliacao(afiliacao: &str) -> String {
    let ps = partes(afiliacao);
    let ini = ps.len().saturating_sub(3);
    for p in ps[ini..].iter().rev() {
        let a = pais(p);
        if !a.is_empty() {
            return a;
        }
    }
    static EU: OnceLock<Regex> = OnceLock::new();
    let eu = EU.get_or_init(|| Regex::new(r"^[A-Z]{2}\s+\d{5}(?:-\d{4})?$").unwrap());
    let ini = ps.len().saturating_sub(2);
    for p in ps[ini..].iter().rev() {
        if eu.is_match(p) && SIGLAS_EUA.contains(&&p[..2]) {
            return "Estados Unidos".into();
        }
    }
    String::new()
}
