//! Apresentação dos termos (porta de `texto.py` e do essencial de `text_utils.py`).

use unicode_normalization::UnicodeNormalization;

use crate::parametros::Unidade;

const SIGLAS: &[&str] = &[
    "SPSS", "PISA", "ICME", "TIMSS", "PIRLS", "TALIS", "ENEM", "SAEB", "SAEP", "BNCC", "TIC", "TICS", "ICT", "NCTM",
    "GAISE", "STEM", "STEAM", "PCK", "TPACK", "IASE", "ICOTS", "ANOVA", "IRT", "RME", "PNAIC", "PNLD", "PCN", "LDB",
    "EJA", "IDEB", "MOOC", "MOOCS", "COVID", "CAQDAS", "SIPEM", "IRAMUTEQ", "SBEM",
];

const NOMES_PROPRIOS: &[(&str, &str)] = &[
    ("GEOGEBRA", "GeoGebra"),
    ("WHATSAPP", "WhatsApp"),
    ("YOUTUBE", "YouTube"),
    ("RSTUDIO", "RStudio"),
    ("NVIVO", "NVivo"),
    ("MAXQDA", "MAXQDA"),
    ("POWERPOINT", "PowerPoint"),
    ("GITHUB", "GitHub"),
    ("SCRATCH", "Scratch"),
];

fn eh_maiuscula(s: &str) -> bool {
    let mut tem = false;
    for c in s.chars().filter(|c| c.is_alphabetic()) {
        tem = true;
        if c.is_lowercase() {
            return false;
        }
    }
    tem
}

fn tudo_maiusculo(s: &str) -> bool {
    // str.isupper(): ao menos uma letra e nenhuma minúscula
    eh_maiuscula(s)
}

fn capitalizado(s: &str) -> bool {
    // pedaco == pedaco.capitalize()
    let mut cs = s.chars();
    match cs.next() {
        None => false,
        Some(p) => {
            let cap: String = p.to_uppercase().chain(cs.flat_map(|c| c.to_lowercase())).collect();
            cap == s
        }
    }
}

/// Numeral romano de I a XXXIX (só I, V, X), em maiúsculas ou caixa de título.
pub fn e_romano(pedaco: &str) -> bool {
    if pedaco.chars().count() <= 1 {
        return false;
    }
    let up = pedaco.to_uppercase();
    let b = up.as_bytes();
    if !matches!(b.first(), Some(b'I' | b'V' | b'X')) {
        return false;
    }
    let mut i = 0;
    while i < b.len() && b[i] == b'X' && i < 3 {
        i += 1;
    }
    let resto = &up[i..];
    let casa = resto.is_empty()
        || resto == "IX"
        || resto == "IV"
        || {
            let r = resto.strip_prefix('V').unwrap_or(resto);
            r.len() <= 3 && r.bytes().all(|c| c == b'I')
        };
    casa && (tudo_maiusculo(pedaco) || capitalizado(pedaco))
}

fn letras(p: &str) -> usize {
    p.chars().filter(|c| c.is_alphabetic()).count()
}

fn palavra(p: &str, varias: bool) -> String {
    if SIGLAS.contains(&p) {
        return p.to_string();
    }
    if let Some((_, v)) = NOMES_PROPRIOS.iter().find(|(k, _)| *k == p) {
        return v.to_string();
    }
    if p.chars().any(|c| c.is_ascii_digit() || c.is_numeric()) && p.chars().any(|c| c.is_alphabetic()) {
        return p.to_string();
    }
    if varias && e_romano(p) && tudo_maiusculo(p) {
        return p.to_string();
    }
    p.to_lowercase()
}

fn converte(texto: &str) -> String {
    let varias = texto.trim().contains(' ');
    let mut saida: Vec<String> = Vec::new();
    for pal in texto.split(' ') {
        let pedacos: Vec<&str> = pal.split('-').collect();
        let partes: Vec<String> = pedacos.iter().map(|p| palavra(p, varias)).collect();
        let mut r = partes[0].clone();
        for i in 1..partes.len() {
            let lig = if letras(pedacos[i - 1]) >= 2 && letras(pedacos[i]) >= 2 { " " } else { "-" };
            r.push_str(lig);
            r.push_str(&partes[i]);
        }
        saida.push(r);
    }
    let frase = saida.join(" ");
    let cs: Vec<char> = frase.chars().collect();
    for (i, &c) in cs.iter().enumerate() {
        if c.is_alphabetic() {
            let mut s: String = cs[..i].iter().collect();
            s.extend(c.to_uppercase());
            s.extend(cs[i + 1..].iter());
            return s;
        }
        if !c.is_numeric() && !"-'\"(“¿¡".contains(c) {
            break;
        }
    }
    frase
}

/// Forma de exibição de um termo guardado em caixa alta.
pub fn termo_legivel(texto: &str) -> String {
    let base = texto.split_whitespace().collect::<Vec<_>>().join(" ");
    if base.is_empty() || !eh_maiuscula(&base) {
        return texto.to_string();
    }
    converte(&base)
}

fn e_palavra(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// Numerais romanos em maiúsculas num título em caixa de título (`Iv` -> `IV`).
pub fn restaura_romanos(texto: &str) -> String {
    let cs: Vec<char> = texto.chars().collect();
    let mut saida = String::new();
    let mut i = 0;
    while i < cs.len() {
        if "IiVvXx".contains(cs[i]) && (i == 0 || !e_palavra(cs[i - 1])) {
            let mut j = i;
            while j < cs.len() && "IiVvXx".contains(cs[j]) {
                j += 1;
            }
            let tok: String = cs[i..j].iter().collect();
            if j - i >= 2 && (j == cs.len() || !e_palavra(cs[j])) {
                if e_romano(&tok) {
                    saida.push_str(&tok.to_uppercase());
                } else {
                    saida.push_str(&tok);
                }
                i = j;
                continue;
            }
        }
        saida.push(cs[i]);
        i += 1;
    }
    saida
}

/// Forma de exibição de um item conforme a unidade (`exibe_termo`).
pub fn exibe_termo(unidade: Unidade, texto: &str) -> String {
    match unidade {
        Unidade::Words => termo_legivel(texto),
        Unidade::ReferenceSources | Unidade::References | Unidade::Institutions => restaura_romanos(texto),
        _ => texto.to_string(),
    }
}

/// Chave de comparação: caixa, acento, pontuação e espaço não contam.
pub fn chave(nome: &str) -> String {
    let sem: String = nome.nfd().filter(|c| !is_marca(*c)).collect();
    sem.to_lowercase().replace('&', "and").chars().filter(|c| c.is_ascii_lowercase() || c.is_ascii_digit()).collect()
}

fn is_marca(c: char) -> bool {
    // categoria Mn (marcas combinantes), faixas principais
    matches!(c as u32, 0x0300..=0x036F | 0x1AB0..=0x1AFF | 0x1DC0..=0x1DFF | 0x20D0..=0x20FF | 0xFE20..=0xFE2F)
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn legivel() {
        assert_eq!(termo_legivel("STATISTICAL-REASONING"), "Statistical reasoning");
        assert_eq!(termo_legivel("E-LEARNING"), "E-learning");
        assert_eq!(termo_legivel("COVID-19"), "COVID-19");
        assert_eq!(termo_legivel("WORLD WAR II"), "World war II");
        assert_eq!(termo_legivel("GEOGEBRA"), "GeoGebra");
        assert_eq!(termo_legivel("Já legível"), "Já legível");
    }

    #[test]
    fn romanos() {
        assert_eq!(restaura_romanos("Anais do Iv Seminario"), "Anais do IV Seminario");
    }
}
