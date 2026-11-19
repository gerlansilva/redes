//! Utilidades dos testes de paridade com o Python.
#![allow(dead_code)]

use std::collections::BTreeMap;
use std::io::Read;
use std::path::PathBuf;

use serde_json::Value;

pub fn pasta_projetos() -> PathBuf {
    std::env::var("REDES_PROJETOS").map(PathBuf::from).unwrap_or_else(|_| PathBuf::from("/home/claude/t"))
}

/// Caminho do projeto, ou `None` (o teste é pulado) quando o arquivo não existe.
pub fn projeto(nome: &str) -> Option<PathBuf> {
    let p = pasta_projetos().join(format!("{nome}.redes"));
    if p.is_file() {
        Some(p)
    } else {
        eprintln!("projeto {} ausente: teste pulado", p.display());
        None
    }
}

pub fn referencia(nome: &str) -> Value {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/ref").join(format!("{nome}.json.gz"));
    let f = std::fs::File::open(&p).unwrap_or_else(|e| panic!("{}: {e}", p.display()));
    let mut d = flate2::read::GzDecoder::new(f);
    let mut s = String::new();
    d.read_to_string(&mut s).unwrap();
    serde_json::from_str(&s).unwrap()
}

/// Conta os elementos `<tag ...>` de um SVG (mesma regra do gerador Python).
pub fn contagem_svg(svg: &str) -> BTreeMap<String, i64> {
    let re = regex::Regex::new(r"<([a-zA-Z]+)[\s>/]").unwrap();
    let mut m = BTreeMap::new();
    for c in re.captures_iter(svg) {
        *m.entry(c[1].to_string()).or_insert(0) += 1;
    }
    m
}

pub fn contagem_json(v: &Value) -> BTreeMap<String, i64> {
    v.as_object().unwrap().iter().map(|(k, v)| (k.clone(), v.as_i64().unwrap())).collect()
}

pub fn perto(a: f64, b: f64, tol: f64) -> bool {
    (a - b).abs() <= tol * (1.0 + b.abs())
}
