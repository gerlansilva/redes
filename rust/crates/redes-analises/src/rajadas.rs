//! Rajadas (bursts) de palavras-chave e de referências pelo algoritmo de Kleinberg (2002)
//! (porta de `rajadas.py`).
//!
//! Para cada termo, a série é a fração dos documentos de cada ano que o contêm. O autômato de
//! dois estados compara a taxa de base com uma taxa `s` vezes maior e escolhe, por programação
//! dinâmica, os anos em que vale a pena "ficar" em rajada. A força é o ganho de verossimilhança.

use std::collections::{BTreeMap, BTreeSet};

use redes_core::texto::termo_legivel;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};

use crate::db::{self, Erro};
use crate::util::py_round;

pub const S_PADRAO: f64 = 2.0;
pub const GAMA_PADRAO: f64 = 1.0;
pub const MINIMO_DOCUMENTOS: usize = 3;

/// `math.lgamma(n + 1)` para inteiros: ln(n!).
pub fn ln_fatorial(n: u64) -> f64 {
    if n <= 20 {
        let mut p: u64 = 1;
        for k in 2..=n {
            p *= k;
        }
        return (p as f64).ln();
    }
    let x = n as f64;
    let inv = 1.0 / x;
    let inv2 = inv * inv;
    x * x.ln() - x + 0.5 * (2.0 * std::f64::consts::PI * x).ln()
        + inv * (1.0 / 12.0 - inv2 * (1.0 / 360.0 - inv2 * (1.0 / 1260.0 - inv2 * (1.0 / 1680.0 - inv2 / 1188.0))))
}

fn log_binomial(n: u64, k: u64) -> f64 {
    ln_fatorial(n) - ln_fatorial(k) - ln_fatorial(n - k)
}

/// -log da verossimilhança binomial de k de n documentos com taxa p.
fn custo(n: u64, k: u64, p: f64) -> f64 {
    let p = p.max(1e-9).min(1.0 - 1e-9);
    -(log_binomial(n, k) + k as f64 * p.ln() + (n - k) as f64 * (1.0 - p).ln())
}

/// Rajadas de uma série: `(início, fim, força)`, com índices inclusivos.
pub fn kleinberg(contagens: &[u64], totais: &[u64], s: f64, gama: f64) -> Vec<(usize, usize, f64)> {
    let n = contagens.len();
    let total_termo: u64 = contagens.iter().sum();
    let total_docs: u64 = totais.iter().sum();
    if n == 0 || total_docs == 0 || total_termo == 0 {
        return Vec::new();
    }
    let p0 = total_termo as f64 / total_docs as f64;
    let p1 = (s * p0).min(0.95);
    if p1 <= p0 {
        return Vec::new();
    }
    let custo0: Vec<f64> = (0..n).map(|t| custo(totais[t], contagens[t], p0)).collect();
    let custo1: Vec<f64> = (0..n).map(|t| custo(totais[t], contagens[t], p1)).collect();
    let subida = gama * (n.max(2) as f64).ln();
    let mut melhor: Vec<(f64, f64)> = vec![(custo0[0], custo1[0] + subida)];
    let mut origem: Vec<(usize, usize)> = vec![(0, 0)];
    for t in 1..n {
        let (a0, a1) = *melhor.last().unwrap();
        let (para0, de0) = if a0 <= a1 { (a0, 0) } else { (a1, 1) };
        let subir = a0 + subida;
        let (para1, de1) = if a1 <= subir { (a1, 1) } else { (subir, 0) };
        melhor.push((para0 + custo0[t], para1 + custo1[t]));
        origem.push((de0, de1));
    }
    let ult = melhor[n - 1];
    let mut estado = if ult.0 <= ult.1 { 0 } else { 1 };
    let mut estados = vec![0usize; n];
    for t in (0..n).rev() {
        estados[t] = estado;
        estado = if estado == 0 { origem[t].0 } else { origem[t].1 };
    }
    let mut rajadas = Vec::new();
    let mut t = 0;
    while t < n {
        if estados[t] == 1 {
            let inicio = t;
            while t + 1 < n && estados[t + 1] == 1 {
                t += 1;
            }
            let forca = crate::util::soma_py((inicio..=t).map(|i| custo0[i] - custo1[i]));
            if forca > 0.0 {
                rajadas.push((inicio, t, forca));
            }
        }
        t += 1;
    }
    rajadas
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Tipo {
    Palavras,
    Referencias,
}

impl Tipo {
    pub fn nome(self) -> &'static str {
        match self {
            Tipo::Palavras => "palavras",
            Tipo::Referencias => "referencias",
        }
    }
    fn sql(self) -> &'static str {
        match self {
            Tipo::Palavras => {
                "SELECT dw.Document_idDocument, COALESCE(g.groupName, w.wordName) \
                 FROM Document_Word dw JOIN Word w ON w.idWord = dw.Word_idWord \
                 LEFT JOIN WordGroup g ON g.idWordGroup = w.WordGroup_idWordGroup \
                 WHERE dw.isAuthorWord = 1 AND COALESCE(g.stopGroup, 0) = 0"
            }
            Tipo::Referencias => {
                "SELECT dr.Document_idDocument, COALESCE(g.groupName, r.fullReference) \
                 FROM Document_Reference dr JOIN Reference r ON r.idReference = dr.Reference_idReference \
                 LEFT JOIN ReferenceGroup g ON g.idReferenceGroup = r.ReferenceGroup_idReferenceGroup \
                 WHERE COALESCE(g.stopGroup, 0) = 0"
            }
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Rajada {
    pub termo: String,
    pub termo_exibicao: String,
    pub primeiro_ano: i64,
    pub forca: f64,
    pub inicio: i64,
    pub fim: i64,
    pub documentos: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ParametrosRajadas {
    pub s: f64,
    pub gama: f64,
    pub minimo_documentos: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Rajadas {
    pub tipo: Tipo,
    pub anos: Vec<i64>,
    pub rajadas: Vec<Rajada>,
    pub documentos_na_base: usize,
    pub avisos: Vec<String>,
    pub parametros: Option<ParametrosRajadas>,
}

pub fn calcula(c: &Connection, tipo: Tipo, limite: usize, minimo_documentos: usize, s: f64, gama: f64) -> Result<Rajadas, Erro> {
    let anos_doc = db::anos_dos_documentos(c)?;
    let mut termos: BTreeMap<String, BTreeMap<i64, BTreeSet<i64>>> = BTreeMap::new();
    let mut com_termo: BTreeMap<i64, BTreeSet<i64>> = BTreeMap::new();
    for (doc, nome) in db::pares_doc_nome(c, tipo.sql())? {
        let Some(&ano) = anos_doc.get(&doc) else { continue };
        if nome.is_empty() {
            continue;
        }
        termos.entry(nome).or_default().entry(ano).or_default().insert(doc);
        com_termo.entry(ano).or_default().insert(doc);
    }
    if com_termo.is_empty() {
        return Ok(Rajadas {
            tipo,
            anos: vec![],
            rajadas: vec![],
            documentos_na_base: 0,
            avisos: vec!["Não há dados suficientes para esta análise.".into()],
            parametros: None,
        });
    }
    let primeiro = *com_termo.keys().next().unwrap();
    let ultimo = *com_termo.keys().next_back().unwrap();
    let anos: Vec<i64> = (primeiro..=ultimo).collect();
    let totais: Vec<u64> = anos.iter().map(|a| com_termo.get(a).map_or(0, |s| s.len() as u64)).collect();
    let base: u64 = totais.iter().sum();
    let mut resultado: Vec<Rajada> = Vec::new();
    for (nome, por_ano) in &termos {
        let contagens: Vec<u64> = anos.iter().map(|a| por_ano.get(a).map_or(0, |s| s.len() as u64)).collect();
        let total: u64 = contagens.iter().sum();
        if (total as usize) < minimo_documentos {
            continue;
        }
        let primeiro_idx = contagens.iter().position(|&c| c > 0).unwrap();
        for (ini, fim, forca) in kleinberg(&contagens, &totais, s, gama) {
            resultado.push(Rajada {
                termo: nome.clone(),
                termo_exibicao: if tipo == Tipo::Palavras { termo_legivel(nome) } else { nome.clone() },
                primeiro_ano: anos[primeiro_idx],
                forca: py_round(forca, 2),
                inicio: anos[ini],
                fim: anos[fim],
                documentos: total as usize,
            });
        }
    }
    resultado.sort_by(|a, b| b.forca.partial_cmp(&a.forca).unwrap().then_with(|| a.termo.cmp(&b.termo)));
    let mut vistos = BTreeSet::new();
    let mut unicos = Vec::new();
    for l in resultado {
        if vistos.insert(l.termo.clone()) {
            unicos.push(l);
        }
    }
    let mut avisos = Vec::new();
    if anos.len() < 8 {
        avisos.push(format!("O corpus cobre só {} anos; rajadas pedem séries mais longas.", anos.len()));
    }
    if base < 100 {
        avisos.push(format!(
            "Só {} documentos entram nesta análise; com tão poucos, as rajadas são instáveis e devem ser lidas com cautela.",
            base
        ));
    }
    if unicos.is_empty() {
        avisos.push(format!(
            "Nenhum termo com pelo menos {} documentos formou uma rajada. Reduza o mínimo de documentos para procurar termos \
             mais raros.",
            minimo_documentos
        ));
    }
    unicos.truncate(limite);
    Ok(Rajadas {
        tipo,
        anos: vec![anos[0], *anos.last().unwrap()],
        rajadas: unicos,
        documentos_na_base: base as usize,
        avisos,
        parametros: Some(ParametrosRajadas { s, gama, minimo_documentos }),
    })
}
