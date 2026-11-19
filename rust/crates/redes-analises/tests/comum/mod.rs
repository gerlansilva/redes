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

/// Troca os identificadores derivados de hash (`dg1a2b3c4d`, `lt...`) por um valor fixo: o
/// Rust usa outro hash que o Python (só estes ids mudam).
pub fn sem_hash(svg: &str, prefixos: &[&str]) -> String {
    let mut s = svg.to_string();
    for p in prefixos {
        let re = regex::Regex::new(&format!(r"{p}[0-9a-f]{{8}}")).unwrap();
        s = re.replace_all(&s, format!("{p}XXXXXXXX")).into_owned();
    }
    s
}

/// Igualdade de textos; em caso de diferença, mostra o primeiro ponto divergente.
pub fn igual_texto(a: &str, b: &str, ctx: &str) {
    if a == b {
        return;
    }
    let ca: Vec<char> = a.chars().collect();
    let cb: Vec<char> = b.chars().collect();
    let i = ca.iter().zip(cb.iter()).position(|(x, y)| x != y).unwrap_or(ca.len().min(cb.len()));
    let trecho = |c: &Vec<char>| c[i.saturating_sub(100)..(i + 100).min(c.len())].iter().collect::<String>();
    panic!("{ctx}: textos diferentes na posição {i} (rust {} chars, python {})\n rust:   ...{}\n python: ...{}", ca.len(), cb.len(), trecho(&ca), trecho(&cb));
}
