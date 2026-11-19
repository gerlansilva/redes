//! Áreas de conhecimento das revistas, inferidas por palavras do NOME (duplo mapa).
//! A classificação é aproximada: a revista fica na primeira área da lista cujo termo aparece no nome.
//!
//! Sintaxe dos termos (nome sem acento, minúsculas, só letras e números): `educ*` (palavra que
//! começa com `educ`), `math` (palavra inteira), `early childhood` (palavras seguidas) e `=nature`
//! (o nome inteiro). Porta `redes/areas.py`; o arquivo JSON de configuração (`REDES_AREAS`) é
//! aceito por `Regras::de_json`.

use std::collections::HashMap;

use serde::{Deserialize, Serialize};

use crate::tabelas::AREAS;
use crate::util::sem_acentos;

pub const NAO_CLASSIFICADO: &str = "Não classificado";
pub const COR_NAO_CLASSIFICADO: &str = "#8A94A6";
pub const PALETA_EXTRA: [&str; 7] = ["#DB2777", "#65A30D", "#0284C7", "#A16207", "#0F766E", "#BE185D", "#4D7C0F"];

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Area {
    pub nome: String,
    pub cor: String,
    pub termos: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Regras {
    pub areas: Vec<Area>,
    /// Fixações por nome exato (chave já normalizada).
    pub revistas: HashMap<String, String>,
}

/// Nome sem acento, em minúsculas, só letras e números separados por um espaço.
pub fn normaliza(texto: &str) -> String {
    let base = sem_acentos(texto).to_lowercase();
    let mut saida = String::new();
    let mut separa = false;
    for c in base.chars() {
        if c.is_ascii_lowercase() || c.is_ascii_digit() {
            if separa && !saida.is_empty() {
                saida.push(' ');
            }
            separa = false;
            saida.push(c);
        } else {
            separa = true;
        }
    }
    saida
}

fn casa(termo: &str, nome: &str, palavras: &[&str]) -> bool {
    let termo = termo.trim().to_lowercase();
    if termo.is_empty() {
        return false;
    }
    if let Some(resto) = termo.strip_prefix('=') {
        return nome == normaliza(resto);
    }
    if let Some(pre) = termo.strip_suffix('*') {
        let prefixo = normaliza(pre);
        return !prefixo.is_empty() && palavras.iter().any(|p| p.starts_with(&prefixo));
    }
    let t = normaliza(&termo);
    !t.is_empty() && format!(" {nome} ").contains(&format!(" {t} "))
}

fn cor_valida(cor: &str, indice: usize) -> String {
    let c = cor.trim();
    let ok = c.len() == 7 && c.starts_with('#') && c[1..].chars().all(|x| x.is_ascii_hexdigit());
    if ok {
        c.to_string()
    } else {
        PALETA_EXTRA[indice % PALETA_EXTRA.len()].to_string()
    }
}

impl Regras {
    pub fn padrao() -> Regras {
        Regras {
            areas: AREAS
                .iter()
                .map(|(n, c, t)| Area { nome: n.to_string(), cor: c.to_string(), termos: t.iter().map(|s| s.to_string()).collect() })
                .collect(),
            revistas: HashMap::new(),
        }
    }

    /// Regras do arquivo JSON (`{"areas": [...], "revistas": {...}, "substitui": false}`).
    pub fn de_json(texto: &str) -> Result<Regras, String> {
        let v: serde_json::Value = serde_json::from_str(texto).map_err(|e| e.to_string())?;
        let mut novas = vec![];
        if let Some(lista) = v.get("areas").and_then(|a| a.as_array()) {
            for (i, item) in lista.iter().enumerate() {
                let nome = item.get("nome").and_then(|x| x.as_str()).unwrap_or("").split_whitespace().collect::<Vec<_>>().join(" ");
                let termos: Vec<String> = item
                    .get("termos")
                    .and_then(|x| x.as_array())
                    .map(|a| a.iter().filter_map(|t| t.as_str()).map(String::from).filter(|t| !t.trim().is_empty()).collect())
                    .unwrap_or_default();
                if !nome.is_empty() && nome != NAO_CLASSIFICADO && !termos.is_empty() {
                    let cor = cor_valida(item.get("cor").and_then(|x| x.as_str()).unwrap_or(""), i);
                    novas.push(Area { nome, cor, termos });
                }
            }
        }
        let substitui = v.get("substitui").and_then(|x| x.as_bool()).unwrap_or(false);
        let mut areas = novas;
        if !substitui {
            areas.extend(Regras::padrao().areas);
        }
        let mut revistas = HashMap::new();
        if let Some(o) = v.get("revistas").and_then(|x| x.as_object()) {
            for (k, val) in o {
                let chave = normaliza(k);
                let valor = val.as_str().unwrap_or("").split_whitespace().collect::<Vec<_>>().join(" ");
                if !chave.is_empty() && !valor.is_empty() {
                    revistas.insert(chave, valor);
                }
            }
        }
        Ok(Regras { areas, revistas })
    }

    /// Cores por área (as áreas em ordem, depois "Não classificado").
    pub fn cores(&self) -> indexmap::IndexMap<String, String> {
        let mut m = indexmap::IndexMap::new();
        for a in &self.areas {
            m.insert(a.nome.clone(), a.cor.clone());
        }
        m.insert(NAO_CLASSIFICADO.to_string(), COR_NAO_CLASSIFICADO.to_string());
        m
    }

    /// `(área, termo que casou)`; `("Não classificado", "")` se nenhum casa; `"(fixada)"` para nome exato.
    pub fn classifica(&self, nome: &str) -> (String, String) {
        let chave = normaliza(nome);
        if let Some(a) = self.revistas.get(&chave) {
            return (a.clone(), "(fixada)".into());
        }
        let palavras: Vec<&str> = chave.split(' ').filter(|p| !p.is_empty()).collect();
        for area in &self.areas {
            for termo in &area.termos {
                if casa(termo, &chave, &palavras) {
                    return (area.nome.clone(), termo.clone());
                }
            }
        }
        (NAO_CLASSIFICADO.to_string(), String::new())
    }
}

impl Default for Regras {
    fn default() -> Self {
        Regras::padrao()
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn classifica_como_o_python() {
        let r = Regras::padrao();
        assert_eq!(r.classifica("Educational Studies in Mathematics"), ("Educação".into(), "educ*".into()));
        assert_eq!(r.classifica("Nature"), ("Multidisciplinar".into(), "=nature".into()));
        assert_eq!(r.classifica("Cognition"), ("Psicologia".into(), "cognit*".into()));
        assert_eq!(r.classifica("Xyz"), (NAO_CLASSIFICADO.into(), String::new()));
        assert_eq!(normaliza("  Revista—Brasileira (ÉTICA) "), "revista brasileira etica");
    }
}
