//! Texto do ISI Web of Science (plain text "PT…ER" e a variante tabulada).
//! Porta de `loaders/wos.py`; a variante com cabeçalho `PT<TAB>AU<TAB>…` é extra.

use std::collections::HashMap;

use crate::fonte::DocumentoFonte;
use crate::loaders::csv_tab::py_float;
use crate::paises::paises_de;
use crate::rx;
use crate::util::*;

const REPETIDOS: &[&str] = &["AU", "AF", "CR", "C1", "DE", "ID", "EM", "OI", "FU", "SU"];

fn divide(p: &str) -> Vec<String> {
    p.split([';', '|']).map(strip).filter(|i| !i.is_empty()).map(String::from).collect()
}

fn citacoes(v: &str) -> i64 {
    let v = strip(v);
    if v.is_empty() {
        return 0;
    }
    py_float(v).map(|f| f as i64).unwrap_or(0)
}

type Registro = HashMap<String, Vec<String>>;

fn monta(registro: &Registro) -> Option<DocumentoFonte> {
    let primeiro = |n: &str| registro.get(n).and_then(|v| v.first()).map(|s| strip(s).to_string()).unwrap_or_default();
    let lista = |n: &str| -> Vec<String> { registro.get(n).cloned().unwrap_or_default() };
    let titulo = primeiro("TI").replace('\n', " ");
    if titulo.is_empty() {
        return None;
    }
    let autores: Vec<String> = lista("AU").iter().map(|n| strip(n).to_string()).filter(|n| !n.is_empty()).collect();
    let referencias: Vec<String> = lista("CR").iter().map(|n| strip(n).to_string()).filter(|n| !n.is_empty()).collect();
    let afiliacoes: Vec<String> = lista("C1").iter().map(|n| strip(n).to_string()).filter(|n| !n.is_empty()).collect();
    let ano = {
        let py = primeiro("PY");
        if py.is_empty() { primeiro("PD").chars().take(4).collect() } else { py }
    };
    Some(DocumentoFonte {
        titulo,
        autores,
        ano,
        citacoes: Some(citacoes(&primeiro("TC"))),
        periodico: primeiro("SO"),
        doi: primeiro("DI"),
        tipo: primeiro("DT"),
        resumo: primeiro("AB").replace('\n', " "),
        paises: paises_de(&afiliacoes, ""),
        afiliacoes,
        palavras_autor: divide(&lista("DE").join("; ")),
        palavras_fonte: divide(&lista("ID").join("; ")),
        referencias,
        ..Default::default()
    })
}

/// Variante tabulada ("Save as tab-delimited"): primeira linha `PT\tAU\tAF\t…`.
fn le_tabulado(linhas: &[&str]) -> Vec<DocumentoFonte> {
    let cab: Vec<String> = linhas[0].split('\t').map(|c| strip(c).to_string()).collect();
    let mut docs = vec![];
    for l in &linhas[1..] {
        if strip(l).is_empty() {
            continue;
        }
        let campos: Vec<&str> = l.split('\t').collect();
        let mut r: Registro = HashMap::new();
        for (i, nome) in cab.iter().enumerate() {
            let v = strip(campos.get(i).copied().unwrap_or(""));
            if v.is_empty() {
                continue;
            }
            let itens: Vec<String> = if REPETIDOS.contains(&nome.as_str()) { v.split("; ").map(|s| s.to_string()).collect() } else { vec![v.to_string()] };
            r.insert(nome.clone(), itens);
        }
        if let Some(d) = monta(&r) {
            docs.push(d);
        }
    }
    docs
}

pub fn le(texto: &str) -> Vec<DocumentoFonte> {
    let linhas = splitlines(texto);
    if let Some(p) = linhas.first() {
        if p.starts_with("PT\t") {
            return le_tabulado(&linhas);
        }
    }
    let mut registros: Vec<Registro> = vec![];
    let mut atual: Option<Registro> = None;
    let mut campo: Option<String> = None;
    for linha in linhas {
        if linha.starts_with("PT ") {
            atual = Some(HashMap::new());
            campo = None;
        }
        let Some(reg) = atual.as_mut() else { continue };
        if let Ok(Some(c)) = rx!(r"^([A-Z][A-Z0-9]) (.*)$").captures(linha) {
            let nome = c.get(1).unwrap().as_str().to_string();
            reg.entry(nome.clone()).or_default().push(strip(c.get(2).unwrap().as_str()).to_string());
            campo = Some(nome);
        } else if linha.starts_with("   ") {
            if let Some(nome) = &campo {
                if REPETIDOS.contains(&nome.as_str()) {
                    reg.get_mut(nome).unwrap().push(strip(linha).to_string());
                } else {
                    let v = reg.get_mut(nome).unwrap();
                    let u = v.last_mut().unwrap();
                    u.push(' ');
                    u.push_str(strip(linha));
                }
            }
        }
        if linha.starts_with("ER") {
            registros.push(atual.take().unwrap());
            campo = None;
        }
    }
    registros.iter().filter_map(monta).collect()
}
