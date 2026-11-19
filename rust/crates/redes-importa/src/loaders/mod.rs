//! Carregadores de corpus (porta de `redes/loaders`).

use std::path::Path;

use indexmap::IndexMap;

use crate::erro::{Erro, Resultado};
use crate::fonte::DocumentoFonte;
use crate::rx;
use crate::util::*;

pub mod bibtex;
pub mod csv_tab;
pub mod openalex;
pub mod openalex_json;
pub mod ris;
pub mod scopus;
pub mod wos;
pub mod zotero;

/// Formatos reconhecidos.
#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Formato {
    Csv,
    Bibtex,
    Ris,
    Openalex,
    #[serde(rename = "openalex-json")]
    OpenalexJson,
    Wos,
    Scopus,
    Zotero,
}

impl Formato {
    pub const TODOS: [Formato; 8] = [
        Formato::Csv,
        Formato::Bibtex,
        Formato::Ris,
        Formato::Openalex,
        Formato::OpenalexJson,
        Formato::Wos,
        Formato::Scopus,
        Formato::Zotero,
    ];

    pub fn nome(self) -> &'static str {
        match self {
            Formato::Csv => "csv",
            Formato::Bibtex => "bibtex",
            Formato::Ris => "ris",
            Formato::Openalex => "openalex",
            Formato::OpenalexJson => "openalex-json",
            Formato::Wos => "wos",
            Formato::Scopus => "scopus",
            Formato::Zotero => "zotero",
        }
    }

    pub fn de_nome(n: &str) -> Option<Formato> {
        let n = n.trim().to_lowercase();
        match n.as_str() {
            "bib" => return Some(Formato::Bibtex),
            "json" | "openalex_json" => return Some(Formato::OpenalexJson),
            "txt" | "tab" => return Some(Formato::Wos),
            _ => {}
        }
        Formato::TODOS.into_iter().find(|f| f.nome() == n)
    }

    fn tabular(self) -> bool {
        matches!(self, Formato::Csv | Formato::Scopus | Formato::Openalex | Formato::Zotero)
    }
}

pub fn le_texto(caminho: &Path) -> Resultado<String> {
    let dados = std::fs::read(caminho).map_err(|e| Erro::Io(format!("{}: {e}", caminho.display())))?;
    Ok(decodifica(&dados))
}

fn colunas(linha: &str) -> Vec<String> {
    linha.split([',', ';', '\t']).map(|c| strip(c).trim_matches('"').to_lowercase()).collect()
}

/// Reconhece o formato pelo conteúdo; a extensão é só o último recurso.
pub fn detecta_formato(caminho: &Path) -> Resultado<Formato> {
    let texto = le_texto(caminho)?;
    Ok(detecta_formato_texto(&texto, caminho.extension().and_then(|e| e.to_str()).unwrap_or("")))
}

pub fn detecta_formato_texto(texto: &str, extensao: &str) -> Formato {
    let amostra: String = texto.chars().take(65536).collect();
    let extensao = extensao.trim_start_matches('.').to_lowercase();

    let t = amostra.trim_start();
    if (t.starts_with('{') || t.starts_with('[')) && (extensao == "json" || t.starts_with("{\"") || t.starts_with("[{") || t.starts_with("{\n") || t.starts_with("[\n")) {
        return Formato::OpenalexJson;
    }
    if rx!(r"(?m)^TY\s{2}-").is_match(&amostra).unwrap_or(false) {
        return Formato::Ris;
    }
    if rx!(r"(?m)^@\w+\s*\{").is_match(&amostra).unwrap_or(false) {
        return Formato::Bibtex;
    }
    if rx!(r"(?m)^PT\s+[A-Z]").is_match(&amostra).unwrap_or(false) {
        return Formato::Wos;
    }
    let primeira = splitlines(&amostra).first().copied().unwrap_or("");
    let cols: std::collections::HashSet<String> = colunas(primeira).into_iter().collect();
    let tem = |n: &str| cols.contains(n);
    if tem("item type") && (tem("publication year") || tem("manual tags") || tem("publication title")) {
        return Formato::Zotero;
    }
    if tem("openalex id") || tem("source keywords") || (tem("citation count") && tem("author ids")) {
        return Formato::Openalex;
    }
    if tem("index keywords") || tem("document type") || tem("author(s) id") || tem("eid") {
        return Formato::Scopus;
    }
    if tem("author full names") {
        return Formato::Openalex;
    }
    if tem("authorkeywords") || tem("sourcekeywords") || tem("citations") {
        return Formato::Csv;
    }
    if tem("title") && (tem("authors") || tem("year")) {
        return Formato::Csv;
    }
    match extensao.as_str() {
        "bib" | "bibtex" => Formato::Bibtex,
        "ris" => Formato::Ris,
        "txt" => Formato::Wos,
        _ => Formato::Csv,
    }
}

/// Lê um corpus; devolve `(documentos, formato efetivo)`.
pub fn le_corpus(caminho: &Path, formato: Option<Formato>) -> Resultado<(Vec<DocumentoFonte>, Formato)> {
    let detectado = detecta_formato(caminho)?;
    let formato = match formato {
        None => detectado,
        Some(f) if f.tabular() && detectado.tabular() => detectado,
        Some(f) => f,
    };
    let texto = le_texto(caminho)?;
    let docs = match formato {
        Formato::Csv => csv_tab::le(&texto)?,
        Formato::Bibtex => bibtex::le(&texto),
        Formato::Ris => ris::le(&texto),
        Formato::Wos => wos::le(&texto),
        Formato::Scopus => scopus::le(&texto)?,
        Formato::Zotero => zotero::le(&texto)?,
        Formato::Openalex => openalex::le(&texto)?,
        Formato::OpenalexJson => openalex_json::le(&texto)?,
    };
    Ok((docs, formato))
}

/// Leitor CSV no estilo `csv.DictReader`: todas as colunas do cabeçalho existem em
/// cada linha (vazias quando faltam); colunas repetidas ficam com o último valor.
pub fn dict_reader(texto: &str, delimitador: u8) -> Resultado<Vec<IndexMap<String, String>>> {
    let mut leitor = csv::ReaderBuilder::new().has_headers(false).flexible(true).delimiter(delimitador).from_reader(texto.as_bytes());
    let mut registros = leitor.records();
    let cabecalho: Vec<String> = match registros.next() {
        Some(r) => r.map_err(|e| Erro::Formato(e.to_string()))?.iter().map(String::from).collect(),
        None => return Ok(vec![]),
    };
    let mut saida = vec![];
    for r in registros {
        let r = r.map_err(|e| Erro::Formato(e.to_string()))?;
        if r.is_empty() || (r.len() == 1 && r.get(0) == Some("") && cabecalho.len() > 1) {
            continue;
        }
        let mut linha: IndexMap<String, String> = IndexMap::new();
        for (i, nome) in cabecalho.iter().enumerate() {
            linha.insert(nome.clone(), r.get(i).unwrap_or("").to_string());
        }
        saida.push(linha);
    }
    Ok(saida)
}

pub fn campo<'a>(linha: &'a IndexMap<String, String>, nome: &str) -> &'a str {
    linha.get(nome).map(|s| s.as_str()).unwrap_or("")
}
