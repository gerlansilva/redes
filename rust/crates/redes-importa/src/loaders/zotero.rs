//! CSV do Zotero. Porta de `loaders/zotero.py`.

use indexmap::IndexMap;

use crate::erro::Resultado;
use crate::fonte::{abrevia_autor, acha_doi, citacoes_em_texto, divide_termos, DocumentoFonte};
use crate::loaders::dict_reader;
use crate::rx;
use crate::util::*;

fn campo_de(linha: &IndexMap<String, String>, nomes: &[&str]) -> String {
    for nome in nomes {
        // chaves em minúsculas; a última coluna repetida vence
        let mut achado: Option<&String> = None;
        for (k, v) in linha {
            if strip(k).to_lowercase() == nome.to_lowercase() {
                achado = Some(v);
            }
        }
        if let Some(v) = achado {
            let v = strip(v);
            if !v.is_empty() {
                return v.to_string();
            }
        }
    }
    String::new()
}

pub fn le(texto: &str) -> Resultado<Vec<DocumentoFonte>> {
    let mut docs = vec![];
    for linha in dict_reader(texto, b',')? {
        let titulo = palavras(&campo_de(&linha, &["Title"])).join(" ");
        if titulo.is_empty() {
            continue;
        }
        let mut ano = campo_de(&linha, &["Publication Year", "Year"]);
        if !rx!(r"^\d{4}$").is_match(&ano).unwrap_or(false) {
            let d = campo_de(&linha, &["Date"]);
            let fonte = if d.is_empty() { ano.clone() } else { d };
            ano = rx!(r"\d{4}").find(&fonte).ok().flatten().map(|m| m.as_str().to_string()).unwrap_or_default();
        }
        let completos: Vec<String> = campo_de(&linha, &["Author"]).split(';').map(strip).filter(|n| !n.is_empty()).map(String::from).collect();
        let extra = campo_de(&linha, &["Extra"]);
        let mut tags = divide_termos(&campo_de(&linha, &["Manual Tags"]));
        tags.extend(divide_termos(&campo_de(&linha, &["Automatic Tags"])));
        let mut vistos = std::collections::HashSet::new();
        let mut palavras_autor = vec![];
        for t in tags {
            if vistos.insert(t.to_lowercase()) {
                palavras_autor.push(t);
            }
        }
        let url = campo_de(&linha, &["Url"]);
        let doi = {
            let d = campo_de(&linha, &["DOI"]);
            if d.is_empty() { acha_doi(&[&url, &extra]) } else { d }
        };
        docs.push(DocumentoFonte {
            titulo,
            autores: completos.iter().map(|n| abrevia_autor(n)).collect(),
            ano,
            citacoes: Some(citacoes_em_texto(&[&extra, &campo_de(&linha, &["Notes"])])),
            periodico: campo_de(&linha, &["Publication Title", "Proceedings Title", "Conference Name", "Publisher"]),
            doi,
            tipo: campo_de(&linha, &["Item Type"]).to_lowercase(),
            resumo: palavras(&campo_de(&linha, &["Abstract Note"])).join(" "),
            autores_completos: completos,
            palavras_autor,
            ..Default::default()
        });
    }
    Ok(docs)
}
