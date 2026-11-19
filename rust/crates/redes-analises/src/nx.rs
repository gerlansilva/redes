//! Portes fiéis de trechos do networkx usados pela similitude: Louvain (3.7, com a mesma ordem
//! de vizinhança e o mesmo embaralhamento do `random.Random`), componentes conexos e o
//! `spring_layout` (Fruchterman-Reingold denso, semeado por `RandomState`).

use indexmap::IndexMap;

use crate::mt::Mt;
use crate::util::soma_py;

/// Grafo não dirigido com pesos; vizinhos na ordem de inserção (como o `dict` do networkx).
#[derive(Clone, Debug, Default)]
pub struct Grafo {
    pub adj: Vec<IndexMap<usize, f64>>,
}

impl Grafo {
    pub fn com_nos(n: usize) -> Grafo {
        Grafo { adj: vec![IndexMap::new(); n] }
    }
    pub fn n(&self) -> usize {
        self.adj.len()
    }
    /// `add_edge`: se existe, só troca o peso (posição preservada).
    pub fn add_aresta(&mut self, u: usize, v: usize, w: f64) {
        self.adj[u].insert(v, w);
        self.adj[v].insert(u, w);
    }
    pub fn tem_aresta(&self, u: usize, v: usize) -> bool {
        self.adj[u].contains_key(&v)
    }
    pub fn peso(&self, u: usize, v: usize) -> Option<f64> {
        self.adj[u].get(&v).copied()
    }
    /// `G.degree(weight)`: o laço conta duas vezes.
    pub fn grau(&self, u: usize) -> f64 {
        let s = soma_py(self.adj[u].values().copied());
        match self.adj[u].get(&u) {
            Some(w) => s + w,
            None => s,
        }
    }
    /// `G.edges()` na ordem do networkx.
    pub fn arestas(&self) -> Vec<(usize, usize, f64)> {
        let mut saida = Vec::new();
        let mut visto = vec![false; self.n()];
        for n in 0..self.n() {
            for (&v, &w) in &self.adj[n] {
                if !visto[v] {
                    saida.push((n, v, w));
                }
            }
            visto[n] = true;
        }
        saida
    }
    pub fn n_arestas(&self) -> usize {
        self.arestas().len()
    }
    /// `G.size(weight)`.
    pub fn tamanho(&self) -> f64 {
        let s = soma_py((0..self.n()).map(|u| self.grau(u)));
        s / 2.0
    }
    pub fn componentes(&self) -> Vec<Vec<usize>> {
        let mut visto = vec![false; self.n()];
        let mut saida = Vec::new();
        for ini in 0..self.n() {
            if visto[ini] {
                continue;
            }
            let mut comp = vec![ini];
            visto[ini] = true;
            let mut k = 0;
            while k < comp.len() {
                let u = comp[k];
                k += 1;
                for &v in self.adj[u].keys() {
                    if !visto[v] {
                        visto[v] = true;
                        comp.push(v);
                    }
                }
            }
            saida.push(comp);
        }
        saida
    }
}

fn modularidade(g: &Grafo, comunidades: &[Vec<usize>], resolucao: f64) -> f64 {
    let graus: Vec<f64> = (0..g.n()).map(|u| g.grau(u)).collect();
    let soma = soma_py(graus.iter().copied());
    let m = soma / 2.0;
    let norma = 1.0 / (soma * soma);
    let mut total = Vec::new();
    for com in comunidades {
        let conj: std::collections::HashSet<usize> = com.iter().copied().collect();
        // G.edges(comm): arestas incidentes, contadas uma vez; só as internas somam.
        let mut vistos: std::collections::HashSet<usize> = std::collections::HashSet::new();
        let mut lc = Vec::new();
        for &u in com {
            for (&v, &w) in &g.adj[u] {
                if !vistos.contains(&v) && conj.contains(&v) {
                    lc.push(w);
                }
            }
            vistos.insert(u);
        }
        let grau_soma = soma_py(com.iter().map(|&u| graus[u]));
        total.push(soma_py(lc) / m - resolucao * grau_soma * grau_soma * norma);
    }
    soma_py(total)
}

struct Nivel {
    particao: Vec<Vec<usize>>,
    interna: Vec<Vec<usize>>,
    melhorou: bool,
}

fn um_nivel(
    g: &Grafo,
    mut particao: Vec<Vec<usize>>,
    membros: &[Vec<usize>],
    m: f64,
    resolucao: f64,
    rng: &mut Mt,
) -> Nivel {
    let n = g.n();
    let mut no_com: Vec<usize> = (0..n).collect();
    let mut interna: Vec<Vec<usize>> = (0..n).map(|u| vec![u]).collect();
    let gama = resolucao / 2.0;
    let graus: Vec<f64> = (0..n).map(|u| g.grau(u)).collect();
    let mut stot = graus.clone();
    let vizinhos: Vec<Vec<(usize, f64)>> = (0..n)
        .map(|u| g.adj[u].iter().filter(|(&v, _)| v != u).map(|(&v, &w)| (v, w)).collect())
        .collect();
    let mut aleatorios: Vec<usize> = (0..n).collect();
    rng.shuffle(&mut aleatorios);
    let mut movimentos = 1;
    let mut melhorou = false;
    while movimentos > 0 {
        movimentos = 0;
        for &u in &aleatorios {
            let u_com = no_com[u];
            let mut por_com: IndexMap<usize, f64> = IndexMap::new();
            for &(v, w) in &vizinhos[u] {
                *por_com.entry(no_com[v]).or_insert(0.0) += w;
            }
            let grau = graus[u];
            stot[u_com] -= grau;
            let x = stot[u_com] * grau;
            let remove = por_com.get(&u_com).copied().unwrap_or(0.0) * m - gama * x;
            let mut melhor_ganho = remove;
            let mut melhor_com = u_com;
            for (&c, &w) in &por_com {
                let x = stot[c] * grau;
                let ganho = w * m - gama * x;
                if ganho > melhor_ganho {
                    melhor_ganho = ganho;
                    melhor_com = c;
                }
            }
            stot[melhor_com] += grau;
            if melhor_com != u_com {
                let originais = &membros[u];
                particao[u_com].retain(|x| !originais.contains(x));
                particao[melhor_com].extend(originais.iter().copied());
                interna[u_com].retain(|&x| x != u);
                interna[melhor_com].push(u);
                melhorou = true;
                movimentos += 1;
                no_com[u] = melhor_com;
            }
        }
    }
    particao.retain(|p| !p.is_empty());
    interna.retain(|p| !p.is_empty());
    Nivel { particao, interna, melhorou }
}

fn agrega(g: &Grafo, interna: &[Vec<usize>], membros: &[Vec<usize>]) -> (Grafo, Vec<Vec<usize>>) {
    let mut h = Grafo::com_nos(interna.len());
    let mut no_com = vec![0usize; g.n()];
    let mut novos = Vec::new();
    for (i, parte) in interna.iter().enumerate() {
        let mut todos = Vec::new();
        for &nd in parte {
            no_com[nd] = i;
            todos.extend(membros[nd].iter().copied());
        }
        novos.push(todos);
    }
    for (a, b, w) in g.arestas() {
        let (c1, c2) = (no_com[a], no_com[b]);
        match h.peso(c1, c2) {
            Some(atual) => h.add_aresta(c1, c2, w + atual),
            None => h.add_aresta(c1, c2, w),
        }
    }
    (h, novos)
}

/// `nx.community.louvain_communities(G, weight, resolution, seed)` com semente inteira.
/// Nós 0..n na ordem do grafo; devolve os blocos (listas de nós).
pub fn louvain(g_orig: &Grafo, resolucao: f64, limiar: f64, semente: u32) -> Vec<Vec<usize>> {
    let n = g_orig.n();
    let mut p: Vec<Vec<usize>> = (0..n).map(|u| vec![u]).collect();
    if g_orig.n_arestas() == 0 {
        return p;
    }
    let mut rng = Mt::python(semente);
    let mut mod_ = modularidade(g_orig, &p, resolucao);
    // cópia ordenada pelo `edges()` do original
    let mut g = Grafo::com_nos(n);
    for (u, v, w) in g_orig.arestas() {
        match g.peso(u, v) {
            Some(a) => g.add_aresta(u, v, a + w),
            None => g.add_aresta(u, v, w),
        }
    }
    let m = g_orig.tamanho();
    let mut membros: Vec<Vec<usize>> = (0..n).map(|u| vec![u]).collect();
    let nivel = um_nivel(&g, p.clone(), &membros, m, resolucao, &mut rng);
    p = nivel.particao;
    let mut interna = nivel.interna;
    let mut melhorou = true;
    let mut ultimo = p.clone();
    while melhorou {
        ultimo = p.clone();
        let novo = modularidade(&g, &interna, resolucao);
        if novo - mod_ <= limiar {
            return ultimo;
        }
        mod_ = novo;
        let (h, novos) = agrega(&g, &interna, &membros);
        g = h;
        membros = novos;
        let nivel = um_nivel(&g, p.clone(), &membros, m, resolucao, &mut rng);
        p = nivel.particao;
        interna = nivel.interna;
        melhorou = nivel.melhorou;
    }
    ultimo
}

/// `nx.spring_layout(G, weight, k, iterations, seed)` para n < 500 (Fruchterman-Reingold denso),
/// com `scale=1`, `center=0`. `a` é a matriz de pesos (n x n).
pub fn spring_layout(a: &[Vec<f64>], k: Option<f64>, iteracoes: usize, semente: u32) -> Vec<[f64; 2]> {
    let n = a.len();
    if n == 0 {
        return vec![];
    }
    if n == 1 {
        return vec![[0.0, 0.0]];
    }
    let mut rng = Mt::numpy(semente);
    let mut pos: Vec<[f64; 2]> = (0..n).map(|_| [rng.res53(), rng.res53()]).collect();
    let k = k.unwrap_or_else(|| (1.0 / n as f64).sqrt());
    let max_x = pos.iter().map(|p| p[0]).fold(f64::MIN, f64::max);
    let min_x = pos.iter().map(|p| p[0]).fold(f64::MAX, f64::min);
    let max_y = pos.iter().map(|p| p[1]).fold(f64::MIN, f64::max);
    let min_y = pos.iter().map(|p| p[1]).fold(f64::MAX, f64::min);
    let mut t = (max_x - min_x).max(max_y - min_y) * 0.1;
    let dt = t / (iteracoes as f64 + 1.0);
    for _ in 0..iteracoes {
        let mut desloc = vec![[0.0f64; 2]; n];
        for i in 0..n {
            let (mut dx, mut dy) = (0.0, 0.0);
            for j in 0..n {
                let ex = pos[i][0] - pos[j][0];
                let ey = pos[i][1] - pos[j][1];
                let mut d = (ex * ex + ey * ey).sqrt();
                if d < 0.01 {
                    d = 0.01;
                }
                let f = k * k / (d * d) - a[i][j] * d / k;
                dx += ex * f;
                dy += ey * f;
            }
            desloc[i] = [dx, dy];
        }
        let mut soma_q = 0.0;
        for i in 0..n {
            let mut comp = (desloc[i][0] * desloc[i][0] + desloc[i][1] * desloc[i][1]).sqrt();
            if comp < 0.01 {
                comp = 0.01;
            }
            let dp = [desloc[i][0] * (t / comp), desloc[i][1] * (t / comp)];
            pos[i][0] += dp[0];
            pos[i][1] += dp[1];
            soma_q += dp[0] * dp[0] + dp[1] * dp[1];
        }
        t -= dt;
        if soma_q.sqrt() / (n as f64) < 1e-4 {
            break;
        }
    }
    // rescale_layout(scale=1)
    let mut lim: f64 = 0.0;
    for d in 0..2 {
        let media = pos.iter().map(|p| p[d]).sum::<f64>() / n as f64;
        for p in pos.iter_mut() {
            p[d] -= media;
        }
        lim = lim.max(pos.iter().map(|p| p[d].abs()).fold(0.0, f64::max));
    }
    if lim > 0.0 {
        for p in pos.iter_mut() {
            p[0] *= 1.0 / lim;
            p[1] *= 1.0 / lim;
        }
    }
    pos
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn embaralha_como_python() {
        let mut m = Mt::python(7);
        let mut x: Vec<usize> = (0..10).collect();
        m.shuffle(&mut x);
        assert_eq!(x, vec![8, 3, 1, 4, 7, 0, 9, 6, 2, 5]);
    }

    #[test]
    fn louvain_dois_triangulos() {
        let mut g = Grafo::com_nos(6);
        for &(a, b) in &[(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5), (2, 3)] {
            g.add_aresta(a, b, 1.0);
        }
        let mut c = louvain(&g, 1.0, 1e-7, 7);
        for b in c.iter_mut() {
            b.sort();
        }
        c.sort();
        assert_eq!(c, vec![vec![0, 1, 2], vec![3, 4, 5]]);
    }

    #[test]
    fn spring_como_networkx() {
        let mut a = vec![vec![0.0; 4]; 4];
        for &(i, j, w) in &[(0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0), (0, 3, 0.3)] {
            a[i][j] = w;
            a[j][i] = w;
        }
        let p = spring_layout(&a, Some(0.75), 300, 3);
        let esperado = [[0.20851663718837252, 0.9999999999999999], [-0.6978135139673566, 0.370491000914633],
            [-0.30547756458731923, -0.7286497574255602], [0.7947744413663033, -0.6418412434890726]];
        for i in 0..4 {
            for d in 0..2 {
                assert!((p[i][d] - esperado[i][d]).abs() < 1e-9, "{:?} vs {:?}", p, esperado);
            }
        }
    }
}
