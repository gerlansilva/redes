//! Reconhecimento de países nas afiliações (porta de `paises.py`).

use std::collections::HashMap;
use std::sync::OnceLock;

use crate::tabelas::{INDICE_PAISES, SIGLAS_EUA};

const SEPARADORES_CHAVE: &[char] = &[' ', '.', ',', ';', ':', '(', ')', '[', ']'];

/// `_chave` do Python: NFKD sem marcas, espaços colapsados, sem pontuação nas pontas, minúsculas.
fn chave_pais(texto: &str) -> String {
    use unicode_normalization::UnicodeNormalization;
    let sem: String = texto.nfkd().filter(|c| !crate::texto::e_marca(*c)).collect();
    let colapsado = sem.split_whitespace().collect::<Vec<_>>().join(" ");
    colapsado.trim_matches(SEPARADORES_CHAVE).to_lowercase()
}

fn indice() -> &'static HashMap<&'static str, &'static str> {
    static I: OnceLock<HashMap<&'static str, &'static str>> = OnceLock::new();
    I.get_or_init(|| INDICE_PAISES.iter().copied().collect())
}

/// Nome canônico do país, ou vazio quando o texto não é um país.
pub fn pais(texto: &str) -> &'static str {
    indice().get(chave_pais(texto).as_str()).copied().unwrap_or("")
}

fn partes(afiliacao: &str) -> Vec<String> {
    let texto = afiliacao.replace('\n', " ");
    // `\bemail:.*$` (sem caixa): corta no primeiro "email:" que começa uma palavra
    let cs: Vec<char> = texto.chars().collect();
    let mut corte = cs.len();
    for i in 0..cs.len() {
        if i + 6 <= cs.len()
            && cs[i..i + 6].iter().collect::<String>().to_lowercase() == "email:"
            && (i == 0 || !(cs[i - 1].is_alphanumeric() || cs[i - 1] == '_'))
        {
            corte = i;
            break;
        }
    }
    let texto: String = cs[..corte].iter().collect();
    texto
        .split(',')
        .filter(|p| !p.trim().is_empty())
        .map(|p| p.trim().trim_matches(SEPARADORES_CHAVE).to_string())
        .collect()
}

fn estado_eua(parte: &str) -> bool {
    // ^[A-Z]{2}\s+\d{5}(?:-\d{4})?$
    let cs: Vec<char> = parte.chars().collect();
    if cs.len() < 2 || !cs[0].is_ascii_uppercase() || !cs[1].is_ascii_uppercase() {
        return false;
    }
    let mut i = 2;
    let ini = i;
    while i < cs.len() && cs[i].is_whitespace() {
        i += 1;
    }
    if i == ini {
        return false;
    }
    let resto: String = cs[i..].iter().collect();
    let d = |s: &str| s.chars().all(|c| c.is_ascii_digit());
    match resto.len() {
        5 => d(&resto),
        10 => d(&resto[..5]) && resto.as_bytes()[5] == b'-' && d(&resto[6..]),
        _ => false,
    }
}

/// País no fim de uma afiliação do tipo `Instituição, Cidade, País`.
pub fn pais_da_afiliacao(afiliacao: &str) -> &'static str {
    let p = partes(afiliacao);
    let n = p.len();
    for parte in p[n.saturating_sub(3)..].iter().rev() {
        let a = pais(parte);
        if !a.is_empty() {
            return a;
        }
    }
    for parte in p[n.saturating_sub(2)..].iter().rev() {
        if estado_eua(parte) {
            let sigla: String = parte.chars().take(2).collect();
            if SIGLAS_EUA.contains(&sigla.as_str()) {
                return "Estados Unidos";
            }
        }
    }
    ""
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn reconhece() {
        assert_eq!(pais("Brazil"), "Brasil");
        assert_eq!(pais(" España. "), "Espanha");
        assert_eq!(pais("Foo"), "");
        assert_eq!(pais_da_afiliacao("Univ de São Paulo, São Paulo, Brazil"), "Brasil");
        assert_eq!(pais_da_afiliacao("Univ California, Davis, CA 95616"), "Estados Unidos");
        assert_eq!(pais_da_afiliacao("Univ X, Rua, Brasil email: a@b.c"), "Brasil");
    }
}
