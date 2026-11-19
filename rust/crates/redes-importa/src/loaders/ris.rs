//! RIS (inclusive o do Zotero e do EndNote). Porta de `loaders/ris.py`.

use std::collections::HashMap;

use crate::fonte::{abrevia_autor, acha_doi, citacoes_em_texto, divide_termos, DocumentoFonte};
use crate::paises::paises_de;
use crate::rx;
use crate::util::*;

type Registro = HashMap<String, Vec<String>>;

fn registros(texto: &str) -> Vec<Registro> {
    let mut regs = vec![];
    let mut atual: Registro = HashMap::new();
    let mut ultima: Option<String> = None;
    for linha in splitlines(&texto.replace('\0', "")) {
        let l = linha.trim_end_matches(e_espaco);
        let (tag, valor) = if let Ok(Some(c)) = rx!(r"^([A-Z][A-Z0-9])\s{2}-\s?(.*)$").captures(l) {
            (c.get(1).unwrap().as_str().to_string(), strip(c.get(2).unwrap().as_str()).to_string())
        } else {
            if let Some(u) = &ultima {
                if !strip(linha).is_empty() {
                    if let Some(v) = atual.get_mut(u).and_then(|v| v.last_mut()) {
                        v.push(' ');
                        v.push_str(strip(linha));
                    }
                }
            }
            continue;
        };
        if tag == "TY" {
            if !atual.is_empty() {
                regs.push(std::mem::take(&mut atual));
            }
        } else if tag == "ER" {
            if !atual.is_empty() {
                regs.push(std::mem::take(&mut atual));
            }
            ultima = None;
            continue;
        }
        atual.entry(tag.clone()).or_default().push(valor);
        ultima = Some(tag);
    }
    if !atual.is_empty() {
        regs.push(atual);
    }
    regs
}

fn ano(r: &Registro) -> String {
    for tag in ["PY", "Y1", "DA", "Y2"] {
        let junto = r.get(tag).map(|v| v.join(" ")).unwrap_or_default();
        if let Ok(Some(m)) = rx!(r"\d{4}").find(&junto) {
            return m.as_str().to_string();
        }
    }
    String::new()
}

pub fn le(texto: &str) -> Vec<DocumentoFonte> {
    let mut docs = vec![];
    for r in registros(texto) {
        let g = |t: &str| -> Vec<String> { r.get(t).cloned().unwrap_or_default() };
        let ou = |tags: &[&str]| -> Vec<String> {
            for t in tags {
                let v = g(t);
                if !v.is_empty() {
                    return v;
                }
            }
            vec![]
        };
        let titulo = strip(&ou(&["TI", "T1"]).join(" ")).to_string();
        if titulo.is_empty() {
            continue;
        }
        let mut nomes = g("AU");
        nomes.extend(g("A1"));
        nomes.retain(|n| !strip(n).is_empty());
        let periodico = strip(&ou(&["JO", "JF", "T2", "JA", "J2"]).join(" ")).to_string();
        let mut palavras_autor = vec![];
        for v in g("KW") {
            palavras_autor.extend(divide_termos(&v));
        }
        let mut afiliacoes = g("C1");
        afiliacoes.extend(g("AD"));
        let notas = g("N1").join(" ");
        let doi = {
            let d = strip(&g("DO").join(" ")).to_string();
            if d.is_empty() { acha_doi(&[&g("UR").join(" "), &g("L3").join(" "), &notas]) } else { d }
        };
        docs.push(DocumentoFonte {
            titulo: palavras(&titulo).join(" "),
            autores: nomes.iter().map(|n| abrevia_autor(n)).collect(),
            autores_completos: nomes.iter().map(|n| strip(n).to_string()).collect(),
            ano: ano(&r),
            citacoes: Some(citacoes_em_texto(&[&notas])),
            periodico,
            doi,
            tipo: strip(&g("TY").join(" ")).to_lowercase(),
            resumo: strip(&ou(&["AB", "N2"]).join(" ")).to_string(),
            paises: paises_de(&afiliacoes, ""),
            afiliacoes,
            palavras_autor,
            ..Default::default()
        });
    }
    docs
}
