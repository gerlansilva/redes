//! Redes não orientadas (porta de `network.py`, `similarity.py`).
//!
//! `adj[no]` guarda os vizinhos na ordem de inserção, como o `dict` do Python:
//! a ordem das somas em ponto flutuante do Louvain depende dela.

use std::collections::{HashMap, HashSet};

use indexmap::IndexMap;

use crate::dataset::{Agregado, Dataset};
use crate::parametros::Similaridade;

#[derive(Clone, Debug)]
pub struct Rede {
    pub nos: Vec<i64>,
    pub idx: HashMap<i64, usize>,
    pub adj: Vec<IndexMap<i64, f64>>,
}

impl Rede {
    pub fn nova(nos: impl IntoIterator<Item = i64>) -> Rede {
        let mut nos: Vec<i64> = nos.into_iter().collect();
        nos.sort_unstable();
        nos.dedup();
        let idx = nos.iter().enumerate().map(|(i, &n)| (n, i)).collect();
        let adj = vec![IndexMap::new(); nos.len()];
        Rede { nos, idx, adj }
    }

    pub fn contem_no(&self, no: i64) -> bool {
        self.idx.contains_key(&no)
    }

    pub fn adiciona_aresta(&mut self, a: i64, b: i64, valor: f64) -> bool {
        let (Some(&ia), Some(&ib)) = (self.idx.get(&a), self.idx.get(&b)) else { return false };
        self.adj[ia].insert(b, valor);
        self.adj[ib].insert(a, valor);
        true
    }

    pub fn remove_aresta(&mut self, a: i64, b: i64) -> bool {
        let (Some(&ia), Some(&ib)) = (self.idx.get(&a), self.idx.get(&b)) else { return false };
        self.adj[ia].shift_remove(&b);
        self.adj[ib].shift_remove(&a);
        true
    }

    pub fn valor(&self, a: i64, b: i64) -> f64 {
        self.idx.get(&a).and_then(|&i| self.adj[i].get(&b)).copied().unwrap_or(0.0)
    }

    pub fn vizinhos(&self, no: i64) -> Vec<i64> {
        match self.idx.get(&no) {
            Some(&i) => {
                let mut v: Vec<i64> = self.adj[i].keys().copied().collect();
                v.sort_unstable();
                v
            }
            None => Vec::new(),
        }
    }

    /// Triângulo superior (a < b) em ordem de linha e coluna.
    pub fn arestas(&self) -> Vec<(i64, i64, f64)> {
        let mut pares = Vec::new();
        for (i, &a) in self.nos.iter().enumerate() {
            let mut viz: Vec<(i64, f64)> = self.adj[i].iter().filter(|(&b, _)| b > a).map(|(&b, &v)| (b, v)).collect();
            viz.sort_unstable_by_key(|p| p.0);
            for (b, v) in viz {
                pares.push((a, b, v));
            }
        }
        pares
    }

    pub fn quantidade_nos(&self) -> usize {
        self.nos.len()
    }

    pub fn quantidade_arestas(&self) -> usize {
        self.adj.iter().map(|m| m.len()).sum::<usize>() / 2
    }

    /// Arestas com as duas pontas no conjunto, em ordem de (a, b).
    pub fn pares_internos(&self, nos: &[i64]) -> Vec<(i64, i64, f64)> {
        let conjunto: HashSet<i64> = nos.iter().copied().collect();
        let mut ordenados: Vec<i64> = conjunto.iter().copied().collect();
        ordenados.sort_unstable();
        let mut pares = Vec::new();
        for a in ordenados {
            let Some(&ia) = self.idx.get(&a) else { continue };
            let mut viz: Vec<(i64, f64)> =
                self.adj[ia].iter().filter(|(&b, _)| b > a && conjunto.contains(&b)).map(|(&b, &v)| (b, v)).collect();
            viz.sort_unstable_by_key(|p| p.0);
            for (b, v) in viz {
                pares.push((a, b, v));
            }
        }
        pares
    }

    /// Arestas com uma ponta no conjunto e outra fora dele.
    pub fn pares_externos(&self, nos: &[i64]) -> Vec<(i64, i64, f64)> {
        let conjunto: HashSet<i64> = nos.iter().copied().collect();
        let mut ordenados: Vec<i64> = conjunto.iter().copied().collect();
        ordenados.sort_unstable();
        let mut pares = Vec::new();
        for a in ordenados {
            let Some(&ia) = self.idx.get(&a) else { continue };
            let mut viz: Vec<(i64, f64)> =
                self.adj[ia].iter().filter(|(&b, _)| !conjunto.contains(&b)).map(|(&b, &v)| (b, v)).collect();
            viz.sort_unstable_by_key(|p| p.0);
            for (b, v) in viz {
                pares.push((a, b, v));
            }
        }
        pares
    }

    pub fn filtra_por_valor(&mut self, minimo: f64) {
        for (a, b, v) in self.arestas() {
            if v < minimo {
                self.remove_aresta(a, b);
            }
        }
    }
}

// ------------------------------------------------------------------ construtores

/// Co-ocorrência de itens por documento.
pub fn rede_coocorrencia(ds: &Dataset) -> Rede {
    let mut rede = Rede::nova(ds.lista_itens());
    for doc in ds.lista_documentos() {
        let itens = ds.itens_do_documento(doc);
        for i in 0..itens.len() {
            for j in (i + 1)..itens.len() {
                let (a, b) = (itens[i], itens[j]);
                let v = rede.valor(a, b) + 1.0;
                rede.adiciona_aresta(a, b, v);
            }
        }
    }
    rede
}

fn interseccao(a: &[i64], b: &[i64]) -> usize {
    let (mut i, mut j, mut n) = (0, 0, 0);
    while i < a.len() && j < b.len() {
        match a[i].cmp(&b[j]) {
            std::cmp::Ordering::Less => i += 1,
            std::cmp::Ordering::Greater => j += 1,
            std::cmp::Ordering::Equal => {
                n += 1;
                i += 1;
                j += 1;
            }
        }
    }
    n
}

/// Acoplamento básico: nós são documentos, peso = itens em comum.
/// Arestas de peso zero só são criadas quando `min_cooc <= 0` (caso contrário o
/// Python as cria e as remove em seguida; o resultado é o mesmo).
pub fn rede_acoplamento(ds: &Dataset, min_cooc: f64) -> Rede {
    let docs = ds.lista_documentos();
    let mut rede = Rede::nova(docs.iter().copied());
    let ordenados: Vec<Vec<i64>> = docs
        .iter()
        .map(|&d| {
            let mut v = ds.itens_do_documento(d).to_vec();
            v.sort_unstable();
            v
        })
        .collect();
    for i in 0..docs.len() {
        for j in (i + 1)..docs.len() {
            let n = interseccao(&ordenados[i], &ordenados[j]);
            if n > 0 || min_cooc <= 0.0 {
                rede.adiciona_aresta(docs[i], docs[j], n as f64);
            }
        }
    }
    rede
}

/// Acoplamento agregado: peso = itens de baixo nível em comum entre os
/// documentos de cada item de alto nível.
pub fn rede_acoplamento_agregado(ag: &Agregado, ds: &Dataset, min_cooc: f64) -> Rede {
    let altos = ag.lista_alto_nivel();
    let mut rede = Rede::nova(altos.iter().copied());
    let itens: Vec<Vec<i64>> = altos
        .iter()
        .map(|a| {
            let mut s: Vec<i64> = ag.documentos[a].iter().flat_map(|&d| ds.itens_do_documento(d).iter().copied()).collect();
            s.sort_unstable();
            s.dedup();
            s
        })
        .collect();
    for i in 0..altos.len() {
        for j in (i + 1)..altos.len() {
            let n = interseccao(&itens[i], &itens[j]);
            if n > 0 || min_cooc <= 0.0 {
                rede.adiciona_aresta(altos[i], altos[j], n as f64);
            }
        }
    }
    rede
}

// ---------------------------------------------------------------- similaridades

pub fn similaridade(medida: Similaridade, fi: usize, fj: usize, cooc: f64) -> f64 {
    let produto = (fi * fj) as f64;
    match medida {
        Similaridade::AssociationStrength => cooc / produto,
        Similaridade::EquivalenceIndex => (cooc * cooc) / produto,
        Similaridade::InclusionIndex => cooc / (fi.min(fj) as f64),
        Similaridade::JaccardIndex => cooc / ((fi + fj) as f64 - cooc),
        Similaridade::SaltonCosine => (cooc * cooc) / produto.sqrt(),
    }
}

/// Substitui cada aresta pelo índice de similaridade (mutação in place).
pub fn normaliza(rede: &mut Rede, medida: Similaridade, freq: impl Fn(i64) -> usize) {
    for (a, b, v) in rede.arestas() {
        let s = similaridade(medida, freq(a), freq(b), v);
        rede.adiciona_aresta(a, b, s);
    }
}
