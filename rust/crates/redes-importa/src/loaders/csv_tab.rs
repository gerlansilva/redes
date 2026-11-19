//! CSV tabulado do Redes (listas separadas por `//`). Porta de `loaders/csv.py`.

use crate::erro::Resultado;
use crate::fonte::DocumentoFonte;
use crate::loaders::{campo, dict_reader};
use crate::paises::paises_de;
use crate::util::*;

fn lista(valor: &str) -> Vec<String> {
    valor.split("//").map(strip).filter(|i| !i.is_empty()).map(String::from).collect()
}

pub fn citacoes(valor: &str) -> Option<i64> {
    let v = strip(valor);
    if v.is_empty() {
        return None;
    }
    // int(float(valor.replace(",", ".")))
    py_float(&v.replace(',', ".")).map(|f| f as i64)
}

/// `float()` do Python para o que aparece em colunas de contagem.
pub fn py_float(s: &str) -> Option<f64> {
    let s = strip(s);
    if s.is_empty() || s.chars().any(|c| c.is_alphabetic() && !matches!(c, 'e' | 'E')) {
        return None;
    }
    s.parse::<f64>().ok().filter(|f| f.is_finite())
}

pub fn le(texto: &str) -> Resultado<Vec<DocumentoFonte>> {
    let mut docs = vec![];
    for linha in dict_reader(texto, b',')? {
        let titulo = strip(campo(&linha, "Title")).replace('\n', " ");
        if titulo.is_empty() {
            continue;
        }
        let afiliacoes = lista(strip(campo(&linha, "Affiliations")));
        docs.push(DocumentoFonte {
            titulo,
            autores: lista(strip(campo(&linha, "Authors"))),
            ano: strip(campo(&linha, "Year")).to_string(),
            citacoes: citacoes(strip(campo(&linha, "Citations"))),
            periodico: strip(campo(&linha, "Journal")).to_string(),
            doi: strip(campo(&linha, "Doi")).to_string(),
            tipo: strip(campo(&linha, "Type")).to_string(),
            resumo: strip(campo(&linha, "Abstract")).replace('\n', " "),
            paises: paises_de(&afiliacoes, ""),
            afiliacoes,
            palavras_autor: lista(strip(campo(&linha, "AuthorKeywords"))),
            palavras_fonte: lista(strip(campo(&linha, "SourceKeywords"))),
            referencias: lista(strip(campo(&linha, "References"))),
            referencias_convertidas: true,
            ..Default::default()
        });
    }
    Ok(docs)
}
