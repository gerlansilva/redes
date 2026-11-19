//! CSV exportado pela Scopus. Porta de `loaders/scopus.py`.

use indexmap::IndexMap;

use crate::erro::Resultado;
use crate::fonte::DocumentoFonte;
use crate::loaders::csv_tab::py_float;
use crate::loaders::dict_reader;
use crate::paises::paises_de;
use crate::referencias::{converte_referencia, limpa_texto, separa_referencias};
use crate::rx;
use crate::util::*;

fn campo_de(linha: &IndexMap<String, String>, nomes: &[&str]) -> String {
    for nome in nomes {
        for (k, v) in linha {
            if !k.is_empty() && strip(k).to_lowercase() == nome.to_lowercase() {
                return strip(v).to_string();
            }
        }
    }
    String::new()
}

fn campo_prefixo(linha: &IndexMap<String, String>, prefixo: &str) -> String {
    let p = prefixo.to_lowercase();
    for (k, v) in linha {
        if !k.is_empty() && strip(k).to_lowercase().starts_with(&p) {
            return strip(v).to_string();
        }
    }
    String::new()
}

fn lista(valor: &str) -> Vec<String> {
    valor.replace('\n', " ").split(';').map(strip).filter(|i| !i.is_empty()).map(String::from).collect()
}

fn sem_id(nome: &str) -> String {
    strip(&rx!(r"\s*\(\d+\)\s*$").replace(nome, "")).to_string()
}

fn autores(linha: &IndexMap<String, String>) -> (Vec<String>, Vec<String>) {
    let completos: Vec<String> = lista(&campo_de(linha, &["Author full names"])).iter().map(|n| sem_id(n)).collect();
    let abreviados: Vec<String> = lista(&campo_de(linha, &["Authors"])).iter().map(|n| sem_id(n)).collect();
    let a = if abreviados.is_empty() { completos.clone() } else { abreviados.clone() };
    let c = if completos.is_empty() { abreviados } else { completos };
    (a, c)
}

const ESTRUTURADAS: &[&str] = &[
    "authors", "author full names", "title", "year", "source title", "source", "doi", "affiliations", "abstract", "author keywords",
    "index keywords", "references", "document type", "type",
];

fn metadados(linha: &IndexMap<String, String>) -> IndexMap<String, String> {
    let mut dados = IndexMap::new();
    for (k, v) in linha {
        if k.is_empty() {
            continue;
        }
        let nome = strip(k);
        let minusculo = nome.to_lowercase();
        if ESTRUTURADAS.contains(&minusculo.as_str()) || minusculo.starts_with("cited by") {
            continue;
        }
        let l = limpa_texto(v);
        if !l.is_empty() {
            dados.insert(nome.to_string(), l);
        }
    }
    dados
}

pub fn referencias(valor: &str) -> (Vec<String>, Vec<String>) {
    let mut convertidas: Vec<String> = vec![];
    let mut brutas = vec![];
    for bruta in separa_referencias(&valor.replace('\n', " ")) {
        let lb = limpa_texto(bruta);
        if let Some(item) = converte_referencia(&lb) {
            if !convertidas.contains(&item) {
                convertidas.push(item);
                brutas.push(lb);
            }
        }
    }
    (convertidas, brutas)
}

fn citacoes(valor: &str) -> Option<i64> {
    let v = strip(valor);
    if v.is_empty() {
        return None;
    }
    // Python: int(float(valor.strip())); texto não numérico vira None.
    py_float(v).map(|f| f as i64)
}

fn delimitador(cabecalho: &str) -> u8 {
    // max() devolve o primeiro empate na ordem , ; \t
    let cont = [(b',', cabecalho.matches(',').count()), (b';', cabecalho.matches(';').count()), (b'\t', cabecalho.matches('\t').count())];
    let max = cont.iter().map(|c| c.1).max().unwrap_or(0);
    if max == 0 {
        return b',';
    }
    cont.iter().find(|c| c.1 == max).unwrap().0
}

pub fn le(texto: &str) -> Resultado<Vec<DocumentoFonte>> {
    let cabecalho = splitlines(texto).first().copied().unwrap_or("");
    let mut docs = vec![];
    for linha in dict_reader(texto, delimitador(cabecalho))? {
        let titulo = campo_de(&linha, &["Title"]).replace('\n', " ");
        if titulo.is_empty() {
            continue;
        }
        let (aut, comp) = autores(&linha);
        let afiliacoes = lista(&campo_de(&linha, &["Affiliations"]));
        let (refs, brutas) = referencias(&campo_de(&linha, &["References"]));
        docs.push(DocumentoFonte {
            titulo,
            autores: aut,
            autores_completos: comp,
            ano: campo_de(&linha, &["Year"]),
            citacoes: citacoes(&campo_prefixo(&linha, "Cited by")),
            periodico: campo_de(&linha, &["Source title", "Source"]),
            doi: campo_de(&linha, &["DOI"]),
            tipo: campo_de(&linha, &["Document Type"]),
            resumo: campo_de(&linha, &["Abstract"]).replace('\n', " "),
            paises: paises_de(&afiliacoes, ""),
            afiliacoes,
            palavras_autor: lista(&campo_de(&linha, &["Author Keywords"])),
            palavras_fonte: lista(&campo_de(&linha, &["Index Keywords"])),
            referencias: refs,
            referencias_brutas: brutas,
            referencias_convertidas: true,
            metadados: metadados(&linha),
        });
    }
    Ok(docs)
}
