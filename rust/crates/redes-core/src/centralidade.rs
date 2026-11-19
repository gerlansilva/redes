//! Centralidades dos nós (porta de `measures.py`): grau ponderado, intermediação
//! de Brandes com custo 1/peso, proximidade, autovetor e PageRank. A ordem das
//! somas e o desempate do heap seguem o Python.

use std::cmp::{Ordering, Reverse};
use std::collections::BinaryHeap;

use serde::{Deserialize, Serialize};

use crate::pycompat::py_sum;
use crate::rede::Rede;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct CentralidadeNo {
    pub id: i64,
    pub grau: f64,
    pub intermediacao: f64,
    pub proximidade: f64,
    pub autovetor: f64,
    pub pagerank: f64,
}

#[derive(Clone, Copy, PartialEq)]
struct Dist(f64);
impl Eq for Dist {}
impl PartialOrd for Dist {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}
impl Ord for Dist {
    fn cmp(&self, o: &Self) -> Ordering {
        self.0.total_cmp(&o.0)
    }
}

fn custo(peso: f64) -> f64 {
    if peso > 0.0 {
        1.0 / peso
    } else {
        1e308 / 4.0
    }
}

/// Lista de adjacência por posição: (posição do vizinho, id do vizinho, valor), na ordem de inserção.
fn adjacentes(rede: &Rede) -> Vec<Vec<(usize, i64, f64)>> {
    rede.adj.iter().map(|m| m.iter().map(|(&v, &p)| (rede.idx[&v], v, p)).collect()).collect()
}

/// Grau ponderado (soma dos pesos) por posição do nó em `rede.nos`.
pub fn grau_ponderado(rede: &Rede) -> Vec<f64> {
    rede.adj.iter().map(|m| py_sum(m.values().copied())).collect()
}

/// Betweenness de Brandes com custo 1/peso (idêntico ao Python, mesma ordem de somas).
pub fn intermediacao(rede: &Rede) -> Vec<f64> {
    let nos = &rede.nos;
    let n = nos.len();
    let adj: Vec<Vec<(usize, i64, f64)>> =
        adjacentes(rede).into_iter().map(|l| l.into_iter().map(|(j, v, p)| (j, v, custo(p))).collect()).collect();
    let mut centralidade = vec![0.0f64; n];
    let mut preds: Vec<Vec<usize>> = vec![Vec::new(); n];
    for s in 0..n {
        for p in preds.iter_mut() {
            p.clear();
        }
        let mut distancia = vec![f64::INFINITY; n];
        let mut caminhos = vec![0.0f64; n];
        let mut pilha: Vec<usize> = Vec::new();
        distancia[s] = 0.0;
        caminhos[s] = 1.0;
        let mut fila: BinaryHeap<Reverse<(Dist, i64)>> = BinaryHeap::new();
        fila.push(Reverse((Dist(0.0), nos[s])));
        while let Some(Reverse((Dist(atual), no))) = fila.pop() {
            let i = rede.idx[&no];
            if atual > distancia[i] {
                continue;
            }
            pilha.push(i);
            let base = distancia[i];
            for &(j, vizinho, c) in &adj[i] {
                let nova = base + c;
                let alvo = distancia[j];
                if nova < alvo - 1e-10 {
                    distancia[j] = nova;
                    fila.push(Reverse((Dist(nova), vizinho)));
                    caminhos[j] = caminhos[i];
                    preds[j].clear();
                    preds[j].push(i);
                } else if (nova - alvo).abs() <= 1e-10 {
                    caminhos[j] += caminhos[i];
                    preds[j].push(i);
                }
            }
        }
        let mut dependencia = vec![0.0f64; n];
        while let Some(w) = pilha.pop() {
            if !preds[w].is_empty() {
                let caminhos_w = caminhos[w];
                if caminhos_w > 0.0 {
                    for k in 0..preds[w].len() {
                        let v = preds[w][k];
                        dependencia[v] += caminhos[v] / caminhos_w * (1.0 + dependencia[w]);
                    }
                }
            }
            if w != s {
                centralidade[w] += dependencia[w];
            }
        }
    }
    centralidade.into_iter().map(|c| c / 2.0).collect()
}

fn distancias(adj: &[Vec<(usize, i64, f64)>], nos: &[i64], origem: usize) -> Vec<f64> {
    let n = nos.len();
    let mut d = vec![f64::INFINITY; n];
    d[origem] = 0.0;
    let mut fila: BinaryHeap<Reverse<(Dist, usize)>> = BinaryHeap::new();
    fila.push(Reverse((Dist(0.0), origem)));
    while let Some(Reverse((Dist(atual), i))) = fila.pop() {
        if atual > d[i] {
            continue;
        }
        for &(j, _, c) in &adj[i] {
            let nova = d[i] + c;
            if nova < d[j] - 1e-10 {
                d[j] = nova;
                fila.push(Reverse((Dist(nova), j)));
            }
        }
    }
    d
}

pub fn proximidade(rede: &Rede) -> Vec<f64> {
    let adj: Vec<Vec<(usize, i64, f64)>> =
        adjacentes(rede).into_iter().map(|l| l.into_iter().map(|(j, v, p)| (j, v, custo(p))).collect()).collect();
    (0..rede.nos.len())
        .map(|o| {
            let d = distancias(&adj, &rede.nos, o);
            let alc: Vec<f64> = d.iter().enumerate().filter(|(i, x)| *i != o && x.is_finite()).map(|(_, &x)| x).collect();
            let soma = py_sum(alc.iter().copied());
            if !alc.is_empty() && soma > 0.0 {
                alc.len() as f64 / soma
            } else {
                0.0
            }
        })
        .collect()
}

pub fn autovetor(rede: &Rede) -> Vec<f64> {
    let n = rede.nos.len();
    let adj = adjacentes(rede);
    let total = n.max(1);
    let mut atual = vec![1.0 / total as f64; n];
    for _ in 0..500 {
        let mut proximo = vec![0.0f64; n];
        let mut norma = 0.0f64;
        for i in 0..n {
            let mut soma = atual[i];
            for &(j, _, peso) in &adj[i] {
                soma += peso * atual[j];
            }
            proximo[i] = soma;
            norma += soma * soma;
        }
        let norma = norma.sqrt();
        if norma < 1e-10 {
            return vec![0.0; n];
        }
        let mut diferenca = 0.0f64;
        for i in 0..n {
            proximo[i] /= norma;
            diferenca += (proximo[i] - atual[i]).abs();
        }
        atual = proximo;
        if diferenca < 1e-10 {
            break;
        }
    }
    atual
}

pub fn pagerank(rede: &Rede) -> Vec<f64> {
    let n = rede.nos.len();
    if n == 0 {
        return Vec::new();
    }
    let adj = adjacentes(rede);
    let graus = grau_ponderado(rede);
    let total = n as f64;
    let mut atual = vec![1.0 / total; n];
    for _ in 0..500 {
        let mut proximo = vec![0.0f64; n];
        for i in 0..n {
            let mut soma = 0.0f64;
            for &(j, _, peso) in &adj[i] {
                if graus[j] > 0.0 {
                    soma += peso / graus[j] * atual[j];
                }
            }
            proximo[i] = 0.15 / total + 0.85 * soma;
        }
        let diferenca = py_sum((0..n).map(|i| (proximo[i] - atual[i]).abs()));
        atual = proximo;
        if diferenca < 1e-10 {
            break;
        }
    }
    atual
}

/// As cinco centralidades de todos os nós, na ordem de `rede.nos`.
pub fn todas(rede: &Rede) -> Vec<CentralidadeNo> {
    let (g, b, p, a, r) = (grau_ponderado(rede), intermediacao(rede), proximidade(rede), autovetor(rede), pagerank(rede));
    rede.nos
        .iter()
        .enumerate()
        .map(|(i, &id)| CentralidadeNo { id, grau: g[i], intermediacao: b[i], proximidade: p[i], autovetor: a[i], pagerank: r[i] })
        .collect()
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn caminho_de_tres() {
        let mut r = Rede::nova([1, 2, 3]);
        r.adiciona_aresta(1, 2, 1.0);
        r.adiciona_aresta(2, 3, 1.0);
        let b = intermediacao(&r);
        assert_eq!(b, vec![0.0, 1.0, 0.0]);
        assert_eq!(grau_ponderado(&r), vec![1.0, 2.0, 1.0]);
    }
}
