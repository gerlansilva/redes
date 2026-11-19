//! BibTeX. Porta de `loaders/bibtex.py`.

use std::collections::HashMap;

use crate::fonte::{abrevia_autor, acha_doi, citacoes_em_texto, decodifica_latex, DocumentoFonte};
use crate::rx;
use crate::util::*;

/// Valor de um campo a partir de `inicio` (índices em bytes; os delimitadores são ASCII).
fn valor(texto: &str, inicio: usize) -> (String, usize) {
    let b = texto.as_bytes();
    let mut i = inicio;
    while i < b.len() && matches!(b[i], b' ' | b'\t' | b'\r' | b'\n') {
        i += 1;
    }
    if i >= b.len() {
        return (String::new(), i);
    }
    if b[i] == b'{' {
        let mut prof = 0;
        let mut j = i;
        while j < b.len() {
            if b[j] == b'{' {
                prof += 1;
            } else if b[j] == b'}' {
                prof -= 1;
                if prof == 0 {
                    return (texto[i + 1..j].to_string(), j + 1);
                }
            }
            j += 1;
        }
        return (texto[i + 1..].to_string(), j);
    }
    if b[i] == b'"' {
        let mut j = i + 1;
        while j < b.len() && b[j] != b'"' {
            j += 1;
        }
        return (texto[i + 1..j.min(b.len())].to_string(), j + 1);
    }
    let mut j = i;
    while j < b.len() && !matches!(b[j], b',' | b'\n' | b'}') {
        j += 1;
    }
    (strip(&texto[i..j]).to_string(), j)
}

fn entradas(texto: &str) -> Vec<(String, &str)> {
    let re = rx!(r"(?i)@(\w+)\s*\{([^,]*),");
    let b = texto.as_bytes();
    let mut saida = vec![];
    let mut pos = 0;
    while pos <= texto.len() {
        let Ok(Some(m)) = re.captures_from_pos(texto, pos) else { break };
        let tipo = m.get(1).unwrap().as_str().to_lowercase();
        let corpo_ini = m.get(0).unwrap().end();
        let mut prof = 1;
        let mut i = corpo_ini;
        while i < b.len() && prof > 0 {
            if b[i] == b'{' {
                prof += 1;
            } else if b[i] == b'}' {
                prof -= 1;
            }
            i += 1;
        }
        // Python: texto[corpo_inicio:i - 1]
        let fim = if i == 0 { 0 } else { i - 1 };
        saida.push((tipo, &texto[corpo_ini..fim.max(corpo_ini)]));
        pos = i;
    }
    saida
}

fn campos(corpo: &str) -> HashMap<String, String> {
    let re = rx!(r"(?i)(\w+)\s*=\s*");
    let mut c = HashMap::new();
    let mut pos = 0;
    while pos <= corpo.len() {
        let Ok(Some(m)) = re.captures_from_pos(corpo, pos) else { break };
        let nome = m.get(1).unwrap().as_str().to_lowercase();
        let (v, p) = valor(corpo, m.get(0).unwrap().end());
        pos = p;
        c.entry(nome).or_insert_with(|| strip(&v).to_string());
    }
    c
}

fn autores(v: &str) -> Vec<String> {
    let re = rx!(r"\s+and\s+");
    let mut nomes = vec![];
    let mut ini = 0;
    for m in re.find_iter(v).flatten() {
        nomes.push(&v[ini..m.start()]);
        ini = m.end();
    }
    nomes.push(&v[ini..]);
    nomes.into_iter().map(strip).filter(|n| !n.is_empty()).map(|n| abrevia_autor(&decodifica_latex(n))).collect()
}

fn palavras_chave(v: &str) -> Vec<String> {
    v.split([';', ',']).filter(|p| !strip(p).is_empty()).map(|p| strip(&decodifica_latex(p)).to_string()).collect()
}

pub fn le(texto: &str) -> Vec<DocumentoFonte> {
    let mut docs = vec![];
    for (tipo, corpo) in entradas(texto) {
        let c = campos(corpo);
        let g = |n: &str| c.get(n).map(|s| s.as_str()).unwrap_or("");
        let titulo = palavras(g("title")).join(" ");
        if titulo.is_empty() {
            continue;
        }
        let mut ano = strip(g("year")).to_string();
        if ano.is_empty() {
            ano = rx!(r"\d{4}").find(g("date")).ok().flatten().map(|m| m.as_str().to_string()).unwrap_or_default();
        }
        let primeiro_nao_vazio = |ns: &[&str]| -> String {
            for n in ns {
                if !g(n).is_empty() {
                    return g(n).to_string();
                }
            }
            String::new()
        };
        docs.push(DocumentoFonte {
            titulo: decodifica_latex(&titulo),
            autores: autores(g("author")),
            ano,
            citacoes: Some(citacoes_em_texto(&[g("note"), g("annote")])),
            periodico: decodifica_latex(&primeiro_nao_vazio(&["journal", "journaltitle", "booktitle", "publisher"])),
            doi: {
                let d = strip(g("doi")).to_string();
                if d.is_empty() { acha_doi(&[g("url")]) } else { d }
            },
            tipo,
            resumo: decodifica_latex(&palavras(g("abstract")).join(" ")),
            palavras_autor: palavras_chave(g("keywords")),
            ..Default::default()
        });
    }
    docs
}
