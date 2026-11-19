//! Medidas de Callon (centralidade e densidade), faixas normalizadas e índices
//! de desempenho h, g, hg, q2 (porta de `measures.py`) e mapeadores de
//! documentos (`mappers.py`).

use std::collections::{BTreeMap, BTreeSet, HashMap};

use crate::pycompat::py_sum;
use crate::rede::Rede;

// ------------------------------------------------------------ diagrama estratégico

/// Centralidade de Callon: 10 x soma dos vínculos externos do grupo.
pub fn centralidade_callon(rede: &Rede, nos: &[i64]) -> f64 {
    10.0 * py_sum(rede.pares_externos(nos).into_iter().map(|p| p.2))
}

/// Densidade de Callon: 100 x soma interna dividida pelo número de nós.
pub fn densidade_callon(rede: &Rede, nos: &[i64]) -> f64 {
    if nos.is_empty() {
        return 0.0;
    }
    100.0 * py_sum(rede.pares_internos(nos).into_iter().map(|p| p.2)) / nos.len() as f64
}

/// Posição relativa de cada grupo na medida, (1..n)/n, com empates estáveis.
pub fn faixa_normalizada(valores: &[f64]) -> Vec<f64> {
    let mut ordem: Vec<usize> = (0..valores.len()).collect();
    ordem.sort_by(|&a, &b| valores[a].partial_cmp(&valores[b]).unwrap_or(std::cmp::Ordering::Equal));
    let mut faixas = vec![0.0; valores.len()];
    for (pos, &i) in ordem.iter().enumerate() {
        faixas[i] = (1.0 + pos as f64) / valores.len() as f64;
    }
    faixas
}

/// Quadrante pelo cruzamento das faixas com 0,5 (como `viz/strategic.py`).
pub fn quadrante(centralidade_faixa: f64, densidade_faixa: f64) -> &'static str {
    let (x, y) = (centralidade_faixa, densidade_faixa);
    if x >= 0.5 && y >= 0.5 {
        "motor"
    } else if x < 0.5 && y >= 0.5 {
        "nicho"
    } else if x < 0.5 {
        "emergente"
    } else {
        "basico"
    }
}

// ------------------------------------------------------------------ desempenho

fn positivas_decrescentes(c: &[i64]) -> Vec<i64> {
    let mut v: Vec<i64> = c.iter().copied().filter(|&x| x > 0).collect();
    v.sort_unstable_by(|a, b| b.cmp(a));
    v
}

pub fn indice_h(citacoes: &[i64]) -> i64 {
    let v = positivas_decrescentes(citacoes);
    let mut h = 0;
    for (pos, &x) in v.iter().enumerate() {
        if x < pos as i64 + 1 {
            return pos as i64;
        }
        h = pos as i64 + 1;
    }
    h
}

pub fn indice_g(citacoes: &[i64]) -> i64 {
    let v = positivas_decrescentes(citacoes);
    let (mut soma, mut g) = (0i64, 0i64);
    for (pos, &x) in v.iter().enumerate() {
        soma += x;
        if soma >= (pos as i64 + 1).pow(2) {
            g += 1;
        } else {
            break;
        }
    }
    g
}

pub fn indice_hg(citacoes: &[i64]) -> f64 {
    ((indice_h(citacoes) * indice_g(citacoes)) as f64).sqrt()
}

pub fn indice_q2(citacoes: &[i64]) -> f64 {
    let v = positivas_decrescentes(citacoes);
    if v.is_empty() {
        return 0.0;
    }
    let h = indice_h(&v);
    if h == 0 {
        return 0.0;
    }
    let mediana = if h % 2 == 1 { v[((h + 1) / 2 - 1) as usize] } else { v[(h / 2 - 1) as usize] };
    ((h * mediana) as f64).sqrt()
}

// ----------------------------------------------------------------- mapeadores

/// Documentos de cada item (ou item de alto nível): fonte dos mapeadores.
pub type Fonte<'a> = &'a BTreeMap<i64, Vec<i64>>;

fn docs(fonte: Fonte, item: i64) -> BTreeSet<i64> {
    fonte.get(&item).map(|v| v.iter().copied().collect()).unwrap_or_default()
}

/// Documentos presentes em pelo menos um par interno do agrupamento.
pub fn nucleo(rede: &Rede, fonte: Fonte, nos: &[i64]) -> BTreeSet<i64> {
    let mut r = BTreeSet::new();
    for (a, b, _) in rede.pares_internos(nos) {
        let da = docs(fonte, a);
        let db = docs(fonte, b);
        r.extend(da.intersection(&db).copied());
    }
    r
}

/// Diferença simétrica acumulada dos documentos dos nós.
pub fn secundarios(fonte: Fonte, nos: &[i64]) -> BTreeSet<i64> {
    if nos.is_empty() {
        return BTreeSet::new();
    }
    let mut acumulado = docs(fonte, nos[0]);
    for &item in &nos[1..] {
        let anterior = acumulado.clone();
        let d = docs(fonte, item);
        acumulado.extend(d.iter().copied());
        for x in anterior.intersection(&d) {
            acumulado.remove(x);
        }
    }
    acumulado
}

/// Documentos que aparecem em pelo menos k nós do agrupamento.
pub fn k_core(fonte: Fonte, nos: &[i64], k: usize) -> BTreeSet<i64> {
    let mut c: HashMap<i64, usize> = HashMap::new();
    for &item in nos {
        for d in docs(fonte, item) {
            *c.entry(d).or_insert(0) += 1;
        }
    }
    c.into_iter().filter(|&(_, q)| q >= k).map(|(d, _)| d).collect()
}

pub fn interseccao(fonte: Fonte, nos: &[i64]) -> BTreeSet<i64> {
    if nos.is_empty() {
        return BTreeSet::new();
    }
    let mut r = docs(fonte, nos[0]);
    for &item in &nos[1..] {
        let d = docs(fonte, item);
        r = r.intersection(&d).copied().collect();
    }
    r
}

pub fn uniao(fonte: Fonte, nos: &[i64]) -> BTreeSet<i64> {
    let mut r = BTreeSet::new();
    for &item in nos {
        r.extend(docs(fonte, item));
    }
    r
}

/// Acoplamento básico: os nós já são documentos.
pub fn acoplamento(nos: &[i64]) -> BTreeSet<i64> {
    nos.iter().copied().collect()
}
