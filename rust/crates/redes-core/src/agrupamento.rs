//! Algoritmos de agrupamento (porta de `clustering.py`): centros simples,
//! quatro ligações hierárquicas e Louvain. O critério de desempate é a ordem
//! da lista de pares, como no Python.

use std::cmp::Ordering;
use std::collections::{BinaryHeap, BTreeMap, BTreeSet, HashMap};

use indexmap::IndexMap;

use crate::erro::{Erro, Resultado};
use crate::parametros::Algoritmo;
use crate::pycompat::{ordem_set_py, py_sum};
use crate::rede::Rede;

#[derive(Clone, Debug)]
pub struct Agrupamento {
    pub nos: Vec<i64>,
    pub principal: Option<i64>,
}

#[derive(Clone, Debug, Default)]
pub struct Conjunto {
    pub agrupamentos: Vec<Agrupamento>,
    pub grupo_do_no: HashMap<i64, usize>,
}

impl Conjunto {
    pub fn adiciona(&mut self, rede: &Rede, nos: &[i64], principal: Option<i64>) -> bool {
        if nos.iter().any(|n| !rede.contem_no(*n)) || nos.iter().any(|n| self.grupo_do_no.contains_key(n)) {
            return false;
        }
        let mut v: Vec<i64> = nos.to_vec();
        v.sort_unstable();
        v.dedup();
        let pos = self.agrupamentos.len();
        for n in &v {
            self.grupo_do_no.insert(*n, pos);
        }
        self.agrupamentos.push(Agrupamento { nos: v, principal });
        true
    }
}

pub fn agrupa(
    algoritmo: Algoritmo,
    rede: &Rede,
    minimo: usize,
    maximo: usize,
    corte: f64,
) -> Resultado<Conjunto> {
    match algoritmo {
        Algoritmo::CentersSimples => Ok(centros_simples(rede, minimo, maximo)),
        Algoritmo::AverageLink => Ok(ligacao(rede, minimo, maximo, Criterio::Media, corte)),
        Algoritmo::CompleteLink => Ok(ligacao(rede, minimo, maximo, Criterio::Completa, corte)),
        Algoritmo::SingleLink => Ok(ligacao(rede, minimo, maximo, Criterio::Simples, corte)),
        Algoritmo::SumLink => Ok(ligacao(rede, minimo, maximo, Criterio::Soma, corte)),
        Algoritmo::Louvain => louvain(rede, minimo, maximo),
    }
}

// ------------------------------------------------------------- centros simples

pub fn centros_simples(rede: &Rede, tamanho_minimo: usize, tamanho_maximo: usize) -> Conjunto {
    let mut resultado = Conjunto::default();
    let mut pares = rede.arestas();
    // ordem decrescente de valor, estável (como sort(key=-valor))
    pares.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap_or(Ordering::Equal));

    let total = pares.len();
    let origem: Vec<usize> = pares.iter().map(|p| rede.idx[&p.0]).collect();
    let destino: Vec<usize> = pares.iter().map(|p| rede.idx[&p.1]).collect();
    let mut vivo = vec![true; total];
    let mut pares_do_no: Vec<Vec<usize>> = vec![Vec::new(); rede.nos.len()];
    for i in 0..total {
        pares_do_no[origem[i]].push(i);
        pares_do_no[destino[i]].push(i);
    }

    let mut contagem = vec![0i64; rede.nos.len()];
    let grau_maximo = pares_do_no.iter().map(|v| v.len()).max().unwrap_or(0);
    let minimo_menos_1 = tamanho_minimo as i64 - 1;
    let mut tamanho_atual: i64 = (tamanho_maximo as i64 - 1).min((grau_maximo as i64).max(minimo_menos_1));
    let mut restantes = total;
    let mut i = 0usize;

    while restantes > 0 && tamanho_atual >= 1 {
        let mut semente: Option<usize> = None;
        let mut posicao = 0usize;
        while i < total {
            if vivo[i] {
                let (a, b) = (origem[i], destino[i]);
                contagem[a] += 1;
                contagem[b] += 1;
                if contagem[a] == tamanho_atual {
                    semente = Some(a);
                    posicao = i;
                    break;
                }
                if contagem[b] == tamanho_atual {
                    semente = Some(b);
                    posicao = i;
                    break;
                }
            }
            i += 1;
        }

        let Some(semente) = semente else {
            if tamanho_atual > minimo_menos_1 {
                contagem.iter_mut().for_each(|c| *c = 0);
                i = 0;
                tamanho_atual -= 1;
                continue;
            }
            break;
        };

        let mut tema = vec![semente];
        for &indice in pares_do_no[semente].iter().rev() {
            if indice > posicao || !vivo[indice] {
                continue;
            }
            tema.push(if origem[indice] == semente { destino[indice] } else { origem[indice] });
        }
        let ids: Vec<i64> = tema.iter().map(|&n| rede.nos[n]).collect();
        resultado.adiciona(rede, &ids, Some(rede.nos[semente]));

        for &no in &tema {
            for &indice in &pares_do_no[no] {
                if !vivo[indice] {
                    continue;
                }
                vivo[indice] = false;
                restantes -= 1;
                if indice <= posicao {
                    contagem[origem[indice]] -= 1;
                    contagem[destino[indice]] -= 1;
                }
            }
        }
        i = posicao + 1;
    }
    resultado
}

// --------------------------------------------------------- ligação hierárquica

#[derive(Clone, Copy)]
pub enum Criterio {
    Media,
    Completa,
    Simples,
    Soma,
}

fn medida_ligacao(valores: &[f64], c: Criterio) -> f64 {
    match c {
        Criterio::Soma => py_sum(valores.iter().copied()),
        Criterio::Media => py_sum(valores.iter().copied()) / valores.len() as f64,
        Criterio::Completa => valores.iter().copied().fold(f64::INFINITY, |m, v| if v < m { v } else { m }),
        Criterio::Simples => valores.iter().copied().fold(f64::NEG_INFINITY, |m, v| if v > m { v } else { m }),
    }
}

#[derive(Clone, Copy, PartialEq)]
struct Entrada {
    neg: f64,
    i: usize,
    j: usize,
}
impl Eq for Entrada {}
impl Ord for Entrada {
    // BinaryHeap é monte máximo; invertemos para obter o mínimo de (neg, i, j).
    fn cmp(&self, o: &Self) -> Ordering {
        o.neg
            .partial_cmp(&self.neg)
            .unwrap_or(Ordering::Equal)
            .then(o.i.cmp(&self.i))
            .then(o.j.cmp(&self.j))
    }
}
impl PartialOrd for Entrada {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}

pub fn ligacao(rede: &Rede, minimo: usize, maximo: usize, criterio: Criterio, corte: f64) -> Conjunto {
    let mut resultado = Conjunto::default();

    let mut grupo_de: HashMap<i64, usize> = rede.nos.iter().enumerate().map(|(i, &n)| (n, i)).collect();
    let mut posicao: HashMap<i64, usize> = rede.nos.iter().map(|&n| (n, 0)).collect();
    let mut membros: BTreeMap<usize, Vec<i64>> = rede.nos.iter().enumerate().map(|(i, &n)| (i, vec![n])).collect();
    let mut vizinhos: HashMap<usize, BTreeSet<usize>> = membros.keys().map(|&k| (k, BTreeSet::new())).collect();
    let mut pares: HashMap<(usize, usize), f64> = HashMap::new();
    let mut monte: BinaryHeap<Entrada> = BinaryHeap::new();

    let refaz = |g: usize,
                 grupo_de: &HashMap<i64, usize>,
                 posicao: &HashMap<i64, usize>,
                 membros: &BTreeMap<usize, Vec<i64>>,
                 vizinhos: &mut HashMap<usize, BTreeSet<usize>>,
                 pares: &mut HashMap<(usize, usize), f64>,
                 monte: &mut BinaryHeap<Entrada>| {
        let mut por_grupo: IndexMap<usize, Vec<(usize, usize, f64)>> = IndexMap::new();
        for (pa, &a) in membros[&g].iter().enumerate() {
            for (&b, &valor) in &rede.adj[rede.idx[&a]] {
                let k = grupo_de[&b];
                if k != g {
                    por_grupo.entry(k).or_default().push((pa, posicao[&b], valor));
                }
            }
        }
        for (k, mut lista) in por_grupo {
            let chave;
            if g < k {
                lista.sort_by(|x, y| (x.0, x.1).cmp(&(y.0, y.1)));
                chave = (g, k);
            } else {
                lista.sort_by(|x, y| (x.1, x.0).cmp(&(y.1, y.0)));
                chave = (k, g);
            }
            let vals: Vec<f64> = lista.iter().map(|t| t.2).collect();
            let valor = medida_ligacao(&vals, criterio);
            vizinhos.get_mut(&g).unwrap().insert(k);
            vizinhos.get_mut(&k).unwrap().insert(g);
            if valor > -1.0 {
                pares.insert(chave, valor);
                monte.push(Entrada { neg: -valor, i: chave.0, j: chave.1 });
            }
        }
    };

    let todos: Vec<usize> = membros.keys().copied().collect();
    for g in todos {
        refaz(g, &grupo_de, &posicao, &membros, &mut vizinhos, &mut pares, &mut monte);
    }

    loop {
        let mut melhor: Option<(usize, usize, f64)> = None;
        while let Some(&e) = monte.peek() {
            if pares.get(&(e.i, e.j)).copied() == Some(-e.neg) {
                melhor = Some((e.i, e.j, -e.neg));
                break;
            }
            monte.pop();
        }
        let Some((i, j, valor)) = melhor else { break };
        if valor < corte {
            break;
        }
        if membros[&i].len() + membros[&j].len() > maximo {
            break;
        }

        for g in [i, j] {
            if let Some(vs) = vizinhos.remove(&g) {
                for k in vs {
                    if let Some(s) = vizinhos.get_mut(&k) {
                        s.remove(&g);
                    }
                    pares.remove(&if g < k { (g, k) } else { (k, g) });
                }
            }
        }
        let deslocamento = membros[&i].len();
        let mj = membros.remove(&j).unwrap();
        for &no in &mj {
            grupo_de.insert(no, i);
            *posicao.get_mut(&no).unwrap() += deslocamento;
        }
        membros.get_mut(&i).unwrap().extend(mj);
        vizinhos.insert(i, BTreeSet::new());
        refaz(i, &grupo_de, &posicao, &membros, &mut vizinhos, &mut pares, &mut monte);
    }

    for (_, grupo) in &membros {
        if grupo.len() >= minimo {
            let p = no_principal(rede, grupo);
            resultado.adiciona(rede, grupo, Some(p));
        }
    }
    resultado
}

/// Nó principal pelo critério do Python: compara com a média do primeiro nó e
/// fica com o último nó cuja média seja menor que a dele (não com o mínimo).
fn no_principal(rede: &Rede, nos: &[i64]) -> i64 {
    let sims: Vec<f64> = nos
        .iter()
        .map(|&no| {
            let viz = rede.vizinhos(no);
            if viz.is_empty() {
                f64::NAN
            } else {
                py_sum(viz.iter().map(|&v| rede.valor(no, v))) / viz.len() as f64
            }
        })
        .collect();
    let mut principal = nos[0];
    let primeira = sims[0];
    for p in 1..nos.len() {
        if primeira > sims[p] {
            principal = nos[p];
        }
    }
    principal
}

// -------------------------------------------------------------------- Louvain

type Grafo = IndexMap<i64, IndexMap<i64, f64>>;

pub fn louvain(rede: &Rede, tamanho_minimo: usize, tamanho_maximo: usize) -> Resultado<Conjunto> {
    let grafo: Grafo = rede
        .nos
        .iter()
        .enumerate()
        .map(|(i, &n)| (n, rede.adj[i].clone()))
        .collect();
    let particao = detecta_comunidades(&grafo)?;
    let grupos = agrupa_particao(&particao);

    let grupos = junta_grupos_pequenos(grupos, &grafo, tamanho_minimo);
    let mut grupos = divide_grupos_grandes(grupos, &grafo, tamanho_maximo);
    grupos.sort_by_key(|g| (std::cmp::Reverse(g.len()), *g.iter().min().unwrap()));

    let mut resultado = Conjunto::default();
    for g in &grupos {
        if g.len() >= tamanho_minimo.max(2) {
            resultado.adiciona(rede, g, Some(principal_por_grau(g, &grafo)));
        }
    }
    Ok(resultado)
}

fn detecta_comunidades(original: &Grafo) -> Resultado<IndexMap<i64, i64>> {
    let mut grafo: Grafo = original.clone();
    let mut pertence: IndexMap<i64, i64> = original.keys().map(|&n| (n, n)).collect();
    loop {
        let particao = move_nos(&grafo);
        let distintas: std::collections::HashSet<i64> = particao.values().copied().collect();
        if distintas.len() == grafo.len() {
            break;
        }
        for (_, v) in pertence.iter_mut() {
            *v = *particao.get(v).ok_or_else(|| {
                Erro::Parametro("Louvain: rótulo de comunidade ausente (KeyError também no Python)".into())
            })?;
        }
        grafo = agrega(&grafo, &particao);
    }
    Ok(pertence)
}

fn graus(grafo: &Grafo) -> HashMap<i64, f64> {
    let mut g = HashMap::new();
    for (&no, viz) in grafo {
        let mut grau = 0.0;
        for (&destino, &peso) in viz {
            grau += if destino == no { 2.0 * peso } else { peso };
        }
        g.insert(no, grau);
    }
    g
}

fn move_nos(grafo: &Grafo) -> IndexMap<i64, i64> {
    let mut comunidade: IndexMap<i64, i64> = IndexMap::new();
    let graus = graus(grafo);
    let mut total: HashMap<i64, f64> = HashMap::new();
    let mut dois_m = 0.0;
    for &no in grafo.keys() {
        comunidade.insert(no, no);
        total.insert(no, graus[&no]);
        dois_m += graus[&no];
    }
    if dois_m <= 0.0 {
        return comunidade;
    }

    let nos: Vec<i64> = grafo.keys().copied().collect();
    let mut passadas = 0;
    let mut mudou = true;
    while mudou && passadas < 100 {
        mudou = false;
        passadas += 1;
        for &no in &nos {
            let atual = comunidade[&no];
            let mut peso_para: IndexMap<i64, f64> = IndexMap::new();
            for (&viz, &peso) in &grafo[&no] {
                let destino = comunidade[&viz];
                *peso_para.entry(destino).or_insert(0.0) += peso;
            }

            *total.get_mut(&atual).unwrap() -= graus[&no];

            let mut melhor = atual;
            let mut melhor_ganho =
                peso_para.get(&atual).copied().unwrap_or(0.0) - graus[&no] * total.get(&atual).copied().unwrap_or(0.0) / dois_m;

            let mut destinos: Vec<i64> = peso_para.keys().copied().collect();
            destinos.sort_unstable();
            for destino in destinos {
                if destino == atual {
                    continue;
                }
                let ganho = peso_para[&destino] - graus[&no] * total.get(&destino).copied().unwrap_or(0.0) / dois_m;
                if ganho > melhor_ganho + 1e-9 || ((ganho - melhor_ganho).abs() <= 1e-9 && destino < melhor) {
                    melhor_ganho = ganho;
                    melhor = destino;
                }
            }

            *total.entry(melhor).or_insert(0.0) += graus[&no];
            comunidade.insert(no, melhor);
            if melhor != atual {
                mudou = true;
            }
        }
    }
    comunidade
}

fn agrega(grafo: &Grafo, particao: &IndexMap<i64, i64>) -> Grafo {
    let mut representante: HashMap<i64, i64> = HashMap::new();
    for (&no, &grupo) in particao {
        match representante.get(&grupo) {
            Some(&r) if r <= no => {}
            _ => {
                representante.insert(grupo, no);
            }
        }
    }
    // `{representante[g]: {} for g in set(particao.values())}`: a ordem é a de
    // iteração de um `set` do CPython.
    let mut agregado: Grafo = Grafo::new();
    for g in ordem_set_py(particao.values().copied()) {
        agregado.insert(representante[&g], IndexMap::new());
    }
    for (&no, viz) in grafo {
        let origem = representante[&particao[&no]];
        for (&dno, &peso) in viz {
            let destino = representante[&particao[&dno]];
            *agregado.get_mut(&origem).unwrap().entry(destino).or_insert(0.0) += peso;
        }
    }
    agregado
}

fn agrupa_particao(particao: &IndexMap<i64, i64>) -> Vec<Vec<i64>> {
    let mut nos: Vec<i64> = particao.keys().copied().collect();
    nos.sort_unstable();
    let mut grupos: IndexMap<i64, Vec<i64>> = IndexMap::new();
    for no in nos {
        grupos.entry(particao[&no]).or_default().push(no);
    }
    grupos.into_values().collect()
}

fn junta_grupos_pequenos(grupos: Vec<Vec<i64>>, grafo: &Grafo, minimo: usize) -> Vec<Vec<i64>> {
    let mut resultado: Vec<Vec<i64>> = grupos.into_iter().filter(|g| !g.is_empty()).collect();
    if resultado.is_empty() || minimo <= 1 {
        return resultado;
    }
    let mut juntou = true;
    while juntou {
        juntou = false;
        let mut grupo_do_no: HashMap<i64, usize> = HashMap::new();
        for (i, g) in resultado.iter().enumerate() {
            for &n in g {
                grupo_do_no.insert(n, i);
            }
        }
        for i in 0..resultado.len() {
            if resultado[i].len() < minimo {
                let v = vizinho_mais_forte(&resultado, i, &grupo_do_no, grafo);
                if let Some(v) = v {
                    if v < resultado.len() && v != i {
                        let g = resultado[i].clone();
                        resultado[v].extend(g);
                        resultado.remove(i);
                        juntou = true;
                        break;
                    }
                }
            }
        }
    }
    resultado
}

fn vizinho_mais_forte(grupos: &[Vec<i64>], indice: usize, grupo_do_no: &HashMap<i64, usize>, grafo: &Grafo) -> Option<usize> {
    let mut pesos: IndexMap<usize, f64> = IndexMap::new();
    for &no in &grupos[indice] {
        if let Some(viz) = grafo.get(&no) {
            for (&v, &peso) in viz {
                if let Some(&d) = grupo_do_no.get(&v) {
                    if d != indice {
                        *pesos.entry(d).or_insert(0.0) += peso;
                    }
                }
            }
        }
    }
    let mut melhor: Option<usize> = None;
    let mut melhor_peso = -1.0f64;
    for (&d, &peso) in &pesos {
        let troca = match melhor {
            None => peso > melhor_peso,
            Some(m) => peso > melhor_peso || (peso == melhor_peso && d < m),
        };
        if troca {
            melhor_peso = peso;
            melhor = Some(d);
        }
    }
    melhor
}

fn divide_grupos_grandes(grupos: Vec<Vec<i64>>, grafo: &Grafo, maximo: usize) -> Vec<Vec<i64>> {
    let mut resultado = Vec::new();
    for g in grupos {
        if g.len() <= maximo {
            resultado.push(g);
        } else {
            resultado.extend(divide(&g, grafo, maximo));
        }
    }
    resultado
}

fn divide(grupo: &[i64], grafo: &Grafo, maximo: usize) -> Vec<Vec<i64>> {
    if grupo.len() <= 1 {
        return grupo.iter().map(|&n| vec![n]).collect();
    }
    let arestas = arestas_internas(grupo, grafo);
    let mut pai: HashMap<i64, i64> = grupo.iter().map(|&n| (n, n)).collect();
    fn raiz(pai: &mut HashMap<i64, i64>, mut no: i64) -> i64 {
        while pai[&no] != no {
            let avo = pai[&pai[&no]];
            pai.insert(no, avo);
            no = pai[&no];
        }
        no
    }
    let mut comp = grupo.len();
    let mut k = 0usize;
    for indice in (0..arestas.len()).rev() {
        let (a, b, _) = arestas[indice];
        let (ra, rb) = (raiz(&mut pai, a), raiz(&mut pai, b));
        if ra != rb {
            pai.insert(ra, rb);
            comp -= 1;
            if comp == 1 {
                k = indice + 1;
                break;
            }
        }
    }
    let mut resultado = Vec::new();
    for componente in componentes(grupo, &arestas, k) {
        if componente.len() > maximo {
            resultado.extend(divide(&componente, grafo, maximo));
        } else {
            resultado.push(componente);
        }
    }
    resultado
}

fn arestas_internas(grupo: &[i64], grafo: &Grafo) -> Vec<(i64, i64, i64)> {
    let dentro: std::collections::HashSet<i64> = grupo.iter().copied().collect();
    let mut arestas = Vec::new();
    for &no in grupo {
        for (&v, &peso) in &grafo[&no] {
            if v > no && dentro.contains(&v) {
                arestas.push((no, v, (peso * 1_000_000.0).round_ties_even() as i64));
            }
        }
    }
    arestas.sort_by_key(|a| (a.2, a.0, a.1));
    arestas
}

fn componentes(grupo: &[i64], arestas: &[(i64, i64, i64)], retiradas: usize) -> Vec<Vec<i64>> {
    let mut pai: HashMap<i64, i64> = grupo.iter().map(|&n| (n, n)).collect();
    fn raiz(pai: &HashMap<i64, i64>, mut no: i64) -> i64 {
        while pai[&no] != no {
            no = pai[&no];
        }
        no
    }
    for &(a, b, _) in &arestas[retiradas..] {
        let (ra, rb) = (raiz(&pai, a), raiz(&pai, b));
        if ra != rb {
            pai.insert(ra.max(rb), ra.min(rb));
        }
    }
    let mut por_raiz: IndexMap<i64, Vec<i64>> = IndexMap::new();
    for &no in grupo {
        let r = raiz(&pai, no);
        por_raiz.entry(r).or_default().push(no);
    }
    por_raiz.into_values().collect()
}

fn principal_por_grau(grupo: &[i64], grafo: &Grafo) -> i64 {
    let mut principal = grupo[0];
    for &no in grupo {
        if grau_no(no, grupo, grafo) > grau_no(principal, grupo, grafo) {
            principal = no;
        }
    }
    principal
}

fn grau_no(no: i64, grupo: &[i64], grafo: &Grafo) -> f64 {
    let dentro: std::collections::HashSet<i64> = grupo.iter().copied().collect();
    py_sum(grafo[&no].iter().filter(|(v, _)| dentro.contains(*v)).map(|(_, &p)| p))
}
