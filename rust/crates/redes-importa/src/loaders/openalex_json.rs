//! JSON da API do OpenAlex (`{"results": [...]}`, lista de works ou um work).
//!
//! Sem equivalente no Python. As referências (`referenced_works`) são só IDs e não
//! viram referências do projeto.

use indexmap::IndexMap;
use serde_json::Value;

use crate::erro::{Erro, Resultado};
use crate::fonte::DocumentoFonte;
use crate::loaders::openalex::abrevia_nome_do_site;
use crate::paises::pais_por_sigla;
use crate::referencias::limpa_texto;

fn s<'a>(v: &'a Value, chave: &str) -> &'a str {
    v.get(chave).and_then(|x| x.as_str()).unwrap_or("")
}

fn resumo(v: &Value) -> String {
    let Some(ix) = v.get("abstract_inverted_index").and_then(|x| x.as_object()) else { return String::new() };
    let mut pos: Vec<(usize, &str)> = vec![];
    for (palavra, ps) in ix {
        for p in ps.as_array().into_iter().flatten().filter_map(|p| p.as_u64()) {
            pos.push((p as usize, palavra.as_str()));
        }
    }
    pos.sort();
    pos.into_iter().map(|p| p.1).collect::<Vec<_>>().join(" ")
}

fn nomes(v: &Value, chave: &str, campo: &str) -> Vec<String> {
    let mut saida: Vec<String> = vec![];
    for it in v.get(chave).and_then(|x| x.as_array()).into_iter().flatten() {
        let n = limpa_texto(s(it, campo));
        if !n.is_empty() && !saida.contains(&n) {
            saida.push(n);
        }
    }
    saida
}

pub fn le(texto: &str) -> Resultado<Vec<DocumentoFonte>> {
    let json: Value = serde_json::from_str(texto).map_err(|e| Erro::Formato(format!("JSON inválido: {e}")))?;
    let obras: Vec<&Value> = match &json {
        Value::Array(a) => a.iter().collect(),
        Value::Object(o) if o.get("results").map_or(false, |r| r.is_array()) => o["results"].as_array().unwrap().iter().collect(),
        Value::Object(_) => vec![&json],
        _ => vec![],
    };
    let mut docs = vec![];
    for w in obras {
        let titulo = {
            let t = limpa_texto(s(w, "title"));
            if t.is_empty() { limpa_texto(s(w, "display_name")) } else { t }
        };
        if titulo.is_empty() {
            continue;
        }
        let mut completos = vec![];
        let mut afiliacoes: Vec<String> = vec![];
        let mut paises: Vec<String> = vec![];
        for a in w.get("authorships").and_then(|x| x.as_array()).into_iter().flatten() {
            let n = limpa_texto(a.get("author").map_or("", |x| s(x, "display_name")));
            if !n.is_empty() {
                completos.push(n);
            }
            for i in a.get("institutions").and_then(|x| x.as_array()).into_iter().flatten() {
                let n = limpa_texto(s(i, "display_name"));
                if !n.is_empty() && !afiliacoes.contains(&n) {
                    afiliacoes.push(n);
                }
                if let Some(p) = pais_por_sigla(s(i, "country_code")) {
                    if !paises.iter().any(|x| x == p) {
                        paises.push(p.to_string());
                    }
                }
            }
            for c in a.get("countries").and_then(|x| x.as_array()).into_iter().flatten().filter_map(|c| c.as_str()) {
                if let Some(p) = pais_por_sigla(c) {
                    if !paises.iter().any(|x| x == p) {
                        paises.push(p.to_string());
                    }
                }
            }
        }
        let fonte = w
            .pointer("/primary_location/source/display_name")
            .or_else(|| w.pointer("/host_venue/display_name"))
            .and_then(|x| x.as_str())
            .unwrap_or("");
        let doi = s(w, "doi");
        let doi = doi.strip_prefix("https://doi.org/").unwrap_or(doi).to_string();
        let mut palavras_autor = nomes(w, "keywords", "display_name");
        if palavras_autor.is_empty() {
            palavras_autor = nomes(w, "keywords", "keyword");
        }
        let mut meta = IndexMap::new();
        for (k, rot) in [("id", "OpenAlex ID"), ("language", "Language")] {
            if !s(w, k).is_empty() {
                meta.insert(rot.to_string(), s(w, k).to_string());
            }
        }
        let tipo = s(w, "type");
        docs.push(DocumentoFonte {
            titulo,
            autores: completos.iter().map(|n| abrevia_nome_do_site(n)).collect(),
            autores_completos: completos,
            ano: w.get("publication_year").and_then(|x| x.as_i64()).map(|a| a.to_string()).unwrap_or_default(),
            citacoes: w.get("cited_by_count").and_then(|x| x.as_i64()),
            periodico: limpa_texto(fonte),
            doi,
            tipo: if tipo.is_empty() { "article".into() } else { tipo.to_string() },
            resumo: resumo(w),
            afiliacoes,
            paises,
            palavras_autor,
            palavras_fonte: nomes(w, "concepts", "display_name"),
            referencias_convertidas: true,
            metadados: meta,
            ..Default::default()
        });
    }
    Ok(docs)
}
