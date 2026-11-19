//! Reconhecimento de países nas afiliações (porta de `paises.py`).

use std::collections::HashMap;
use std::sync::OnceLock;

use unicode_normalization::UnicodeNormalization;

use crate::dados_paises::{ALIAS, PAISES, SIGLAS_EUA, SIGLAS_PAISES};
use crate::rx;
use crate::util::*;

fn chave_pais(texto: &str) -> String {
    let t: String = texto.nfkd().filter(|c| !combina(*c)).collect();
    let t = palavras(&t).join(" ");
    // `re.sub(r"\s+", " ")` e depois `.strip(" .,;:()[]")`
    strip_chars(&t, " .,;:()[]").to_lowercase()
}

fn indice() -> &'static HashMap<String, &'static str> {
    static I: OnceLock<HashMap<String, &'static str>> = OnceLock::new();
    I.get_or_init(|| {
        let mut m: HashMap<String, &'static str> = HashMap::new();
        for (nome, canonico) in PAISES {
            m.insert(chave_pais(nome), canonico);
        }
        for (nome, canonico) in ALIAS {
            m.entry(chave_pais(nome)).or_insert(canonico);
        }
        for (_, canonico) in PAISES {
            m.entry(chave_pais(canonico)).or_insert(canonico);
        }
        m
    })
}

/// Nome canônico do país, ou vazio.
pub fn pais(texto: &str) -> &'static str {
    indice().get(&chave_pais(texto)).copied().unwrap_or("")
}

fn partes(afiliacao: &str) -> Vec<String> {
    let t = afiliacao.replace('\n', " ");
    let t = rx!(r"(?i)\bemail:.*$").replace(&t, "").to_string();
    t.split(',').filter(|p| !strip(p).is_empty()).map(|p| strip_chars(p, " .,;:()[]").to_string()).collect()
}

pub fn pais_da_afiliacao(afiliacao: &str) -> &'static str {
    let ps = partes(afiliacao);
    let n = ps.len();
    for parte in ps[n.saturating_sub(3)..].iter().rev() {
        let a = pais(parte);
        if !a.is_empty() {
            return a;
        }
    }
    for parte in ps[n.saturating_sub(2)..].iter().rev() {
        if rx!(r"^[A-Z]{2}\s+\d{5}(?:-\d{4})?$").is_match(parte).unwrap_or(false) {
            let sigla: String = parte.chars().take(2).collect();
            if SIGLAS_EUA.contains(&sigla.as_str()) {
                return "Estados Unidos";
            }
        }
    }
    ""
}

pub fn paises_de(afiliacoes: &[String], alternativa: &str) -> Vec<String> {
    let mut achados: Vec<String> = vec![];
    for a in afiliacoes {
        let p = pais_da_afiliacao(a);
        if !p.is_empty() && !achados.iter().any(|x| x == p) {
            achados.push(p.to_string());
        }
    }
    if achados.is_empty() && !alternativa.is_empty() {
        for parte in alternativa.split([';', ',', '|']) {
            let p = pais(parte);
            if !p.is_empty() && !achados.iter().any(|x| x == p) {
                achados.push(p.to_string());
            }
        }
    }
    achados
}

pub fn pais_por_sigla(sigla: &str) -> Option<&'static str> {
    let s = strip(sigla).to_uppercase();
    SIGLAS_PAISES.iter().find(|(k, _)| *k == s).map(|(_, v)| *v)
}
