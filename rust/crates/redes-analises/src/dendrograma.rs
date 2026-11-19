//! Dendrograma: agrupamento hierárquico aglomerativo sobre uma rede (porta de
//! `dendrograma.py`, `dendro_helper.py` e `viz/dendrograma.py`).
//!
//! A distância entre dois nós é `1 - s`, com `s` a similaridade da rede normalizada para
//! [0, 1] (se o maior valor passa de 1, divide-se por ele). Par sem aresta tem distância 1.
//! As folhas são numeradas por posição em `nos` (ordenados por identificador, como a
//! `Rede` do Python) e as fusões criam os rótulos n, n+1, ... como no `linkage` do scipy.

use std::collections::BTreeMap;

use indexmap::IndexMap;
use redes_core::pycompat::py_sum;
use redes_core::Resultado;
use serde::{Deserialize, Serialize};

use crate::util::*;

pub const LIMITE_COPH: f64 = 0.6;
pub const POUCOS_NOS: usize = 6;
pub const LIMITE_NOS: usize = 60;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Ligacao {
    Media,
    Completa,
    Simples,
}

impl Ligacao {
    pub fn nome(self) -> &'static str {
        match self {
            Ligacao::Media => "media",
            Ligacao::Completa => "completa",
            Ligacao::Simples => "simples",
        }
    }
    pub fn de_texto(s: &str) -> Result<Ligacao, String> {
        match s {
            "media" => Ok(Ligacao::Media),
            "completa" => Ok(Ligacao::Completa),
            "simples" => Ok(Ligacao::Simples),
            _ => Err(format!("ligação inválida: {s:?}; use media, completa, simples")),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Fusao {
    pub a: usize,
    pub b: usize,
    pub altura: f64,
    pub tamanho: usize,
}

/// Entrada: sub-rede (nós ordenados) com nomes, pesos e agrupamentos da rede.
#[derive(Clone, Debug, Default)]
pub struct Entrada {
    pub nos: Vec<i64>,
    pub arestas: Vec<(i64, i64, f64)>,
    pub nomes: BTreeMap<i64, String>,
    pub pesos: Option<BTreeMap<i64, f64>>,
    pub grupos_rede: Option<BTreeMap<i64, usize>>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Dendrograma {
    pub ligacao: Ligacao,
    pub nos: Vec<i64>,
    pub nomes: BTreeMap<i64, String>,
    pub pesos: Option<BTreeMap<i64, f64>>,
    pub grupos_rede: Option<BTreeMap<i64, usize>>,
    pub ordem: Vec<i64>,
    pub fusoes: Vec<Fusao>,
    pub alturas: Vec<f64>,
    pub coph: f64,
    pub n_grupos_sugerido: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Comparacao {
    pub ari: Option<f64>,
    pub nmi: Option<f64>,
    pub n_comparados: usize,
    pub n_grupos_corte: usize,
    pub n_grupos_rede: usize,
}

fn distancias(entrada: &Entrada) -> Vec<Vec<f64>> {
    let nos = &entrada.nos;
    let n = nos.len();
    let pos: BTreeMap<i64, usize> = nos.iter().enumerate().map(|(i, &x)| (x, i)).collect();
    let mut sim = vec![vec![0.0f64; n]; n];
    let mut maximo = 0.0f64;
    let mut tem = false;
    for &(a, b, v) in &entrada.arestas {
        if let (Some(&i), Some(&j)) = (pos.get(&a), pos.get(&b)) {
            if a != b {
                sim[i][j] = v;
                sim[j][i] = v;
                if !tem || v > maximo {
                    maximo = v;
                    tem = true;
                }
            }
        }
    }
    let maximo = if tem { maximo } else { 0.0 };
    let escala = if maximo > 1.0 { maximo } else { 1.0 };
    let mut dist = vec![vec![0.0f64; n]; n];
    for i in 0..n {
        for j in (i + 1)..n {
            let s = sim[i][j].max(0.0) / escala;
            let d = 1.0 - s.min(1.0);
            dist[i][j] = d;
            dist[j][i] = d;
        }
    }
    dist
}

fn liga(lig: Ligacao, d_ik: f64, d_jk: f64, ni: usize, nj: usize) -> f64 {
    match lig {
        Ligacao::Simples => d_ik.min(d_jk),
        Ligacao::Completa => d_ik.max(d_jk),
        Ligacao::Media => (ni as f64 * d_ik + nj as f64 * d_jk) / (ni + nj) as f64,
    }
}

fn aglomera(dist: &[Vec<f64>], lig: Ligacao) -> Vec<Fusao> {
    let n = dist.len();
    let mut d: Vec<Vec<f64>> = dist.to_vec();
    let mut rotulo: Vec<usize> = (0..n).collect();
    let mut tamanho = vec![1usize; n];
    let mut ativos: Vec<usize> = (0..n).collect();
    let mut fusoes = Vec::new();
    for passo in 0..n.saturating_sub(1) {
        let mut melhor: Option<(f64, usize, usize)> = None;
        for (x, &i) in ativos.iter().enumerate() {
            for &j in &ativos[x + 1..] {
                if melhor.map_or(true, |m| d[i][j] < m.0) {
                    melhor = Some((d[i][j], i, j));
                }
            }
        }
        let (altura, i, j) = melhor.unwrap();
        let (a, b) = if rotulo[i] <= rotulo[j] { (rotulo[i], rotulo[j]) } else { (rotulo[j], rotulo[i]) };
        let novo = tamanho[i] + tamanho[j];
        for &k in &ativos {
            if k == i || k == j {
                continue;
            }
            let v = liga(lig, d[i][k], d[j][k], tamanho[i], tamanho[j]);
            d[i][k] = v;
            d[k][i] = v;
        }
        ativos.retain(|&x| x != j);
        rotulo[i] = n + passo;
        tamanho[i] = novo;
        fusoes.push(Fusao { a, b, altura, tamanho: novo });
    }
    fusoes
}

fn ordem_folhas(fusoes: &[Fusao], n: usize) -> Vec<usize> {
    if n == 1 {
        return vec![0];
    }
    let mut tam: Vec<usize> = vec![1; n + fusoes.len()];
    let mut menor: Vec<usize> = (0..n + fusoes.len()).collect();
    for (k, f) in fusoes.iter().enumerate() {
        tam[n + k] = f.tamanho;
        menor[n + k] = menor[f.a].min(menor[f.b]);
    }
    let mut ordem = Vec::new();
    let mut pilha = vec![n + fusoes.len() - 1];
    while let Some(no) = pilha.pop() {
        if no < n {
            ordem.push(no);
            continue;
        }
        let f = &fusoes[no - n];
        let (mut a, mut b) = (f.a, f.b);
        // (-tam[a], menor[a]) > (-tam[b], menor[b])
        let ka = (-(tam[a] as i64), menor[a]);
        let kb = (-(tam[b] as i64), menor[b]);
        if ka > kb {
            std::mem::swap(&mut a, &mut b);
        }
        pilha.push(b);
        pilha.push(a);
    }
    ordem
}

fn pearson(xs: &[f64], ys: &[f64]) -> f64 {
    let m = xs.len();
    if m < 2 {
        return 0.0;
    }
    let mx = py_sum(xs.iter().copied()) / m as f64;
    let my = py_sum(ys.iter().copied()) / m as f64;
    let sxx = py_sum(xs.iter().map(|x| (x - mx) * (x - mx)));
    let syy = py_sum(ys.iter().map(|y| (y - my) * (y - my)));
    if sxx <= 1e-15 || syy <= 1e-15 {
        return 0.0;
    }
    let sxy = py_sum(xs.iter().zip(ys).map(|(x, y)| (x - mx) * (y - my)));
    sxy / (sxx * syy).sqrt()
}

fn cofenetica(fusoes: &[Fusao], n: usize, dist: &[Vec<f64>]) -> f64 {
    let mut membros: BTreeMap<usize, Vec<usize>> = (0..n).map(|i| (i, vec![i])).collect();
    let mut xs = Vec::new();
    let mut ys = Vec::new();
    for (k, f) in fusoes.iter().enumerate() {
        let ma = membros.remove(&f.a).unwrap();
        let mb = membros.remove(&f.b).unwrap();
        for &x in &ma {
            for &y in &mb {
                xs.push(dist[x.min(y)][x.max(y)]);
                ys.push(f.altura);
            }
        }
        let mut m = ma;
        m.extend(mb);
        membros.insert(n + k, m);
    }
    pearson(&xs, &ys)
}

fn sugere(alturas: &[f64], n: usize) -> usize {
    if n < 3 {
        return n;
    }
    let (mut melhor_k, mut melhor_salto) = (2usize, -1.0f64);
    for k in 2..n.min(11) {
        let salto = alturas[n - k] - alturas[n - k - 1];
        if salto > melhor_salto + 1e-12 {
            melhor_k = k;
            melhor_salto = salto;
        }
    }
    melhor_k
}

/// Dendrograma aglomerativo da rede de `entrada`.
pub fn constroi(entrada: &Entrada, ligacao: Ligacao) -> Result<Dendrograma, String> {
    let mut nos = entrada.nos.clone();
    nos.sort();
    let n = nos.len();
    if n == 0 {
        return Err("a rede não tem nós".into());
    }
    let ent = Entrada { nos: nos.clone(), ..entrada.clone() };
    let dist = distancias(&ent);
    let fusoes = if n > 1 { aglomera(&dist, ligacao) } else { Vec::new() };
    let ordem_pos = ordem_folhas(&fusoes, n);
    let alturas: Vec<f64> = fusoes.iter().map(|f| f.altura).collect();
    let nomes = nos
        .iter()
        .map(|&no| (no, entrada.nomes.get(&no).cloned().unwrap_or_else(|| no.to_string())))
        .collect();
    let pesos = entrada.pesos.as_ref().map(|p| nos.iter().filter_map(|no| p.get(no).map(|v| (*no, *v))).collect::<BTreeMap<_, _>>());
    let pesos = pesos.filter(|p| !p.is_empty());
    let grupos_rede = entrada.grupos_rede.clone().filter(|g| !g.is_empty());
    let coph = if n > 2 { cofenetica(&fusoes, n, &dist) } else { 0.0 };
    let sug = if n > 1 { sugere(&alturas, n) } else { 1 };
    Ok(Dendrograma {
        ligacao,
        ordem: ordem_pos.iter().map(|&p| nos[p]).collect(),
        nos,
        nomes,
        pesos,
        grupos_rede,
        fusoes,
        alturas,
        coph,
        n_grupos_sugerido: sug,
    })
}

impl Dendrograma {
    /// Partição `{no: grupo}` por número de grupos (grupos numerados de 0 na ordem de desenho).
    pub fn corte(&self, n_grupos: usize) -> IndexMap<i64, usize> {
        let n = self.nos.len();
        let aplicar = n - n_grupos.clamp(1, n);
        self.particao_aplicando(aplicar)
    }

    pub fn corte_por_altura(&self, altura: f64) -> IndexMap<i64, usize> {
        let aplicar = self.fusoes.iter().filter(|f| f.altura <= altura + 1e-12).count();
        self.particao_aplicando(aplicar)
    }

    fn particao_aplicando(&self, aplicar: usize) -> IndexMap<i64, usize> {
        let n = self.nos.len();
        let mut pai: Vec<usize> = (0..n + self.fusoes.len()).collect();
        fn raiz(pai: &mut [usize], mut x: usize) -> usize {
            while pai[x] != x {
                pai[x] = pai[pai[x]];
                x = pai[x];
            }
            x
        }
        for k in 0..aplicar {
            let (a, b) = (self.fusoes[k].a, self.fusoes[k].b);
            let ra = raiz(&mut pai, a);
            pai[ra] = n + k;
            let rb = raiz(&mut pai, b);
            pai[rb] = n + k;
        }
        let posicao: BTreeMap<i64, usize> = self.nos.iter().enumerate().map(|(i, &x)| (x, i)).collect();
        let mut numero: IndexMap<usize, usize> = IndexMap::new();
        let mut particao = IndexMap::new();
        for &no in &self.ordem {
            let r = raiz(&mut pai, posicao[&no]);
            let k = numero.len();
            let g = *numero.entry(r).or_insert(k);
            particao.insert(no, g);
        }
        particao
    }

    /// Altura que separa exatamente `n_grupos` grupos (ponto médio do salto).
    pub fn altura_do_corte(&self, n_grupos: usize) -> f64 {
        let n = self.nos.len();
        let a = &self.alturas;
        if n_grupos >= n {
            return if a.is_empty() { 0.0 } else { a[0] / 2.0 };
        }
        if n_grupos <= 1 {
            return a.last().copied().unwrap_or(0.0);
        }
        (a[n - n_grupos - 1] + a[n - n_grupos]) / 2.0
    }

    pub fn comparacao(&self, particao: &IndexMap<i64, usize>) -> Option<Comparacao> {
        self.grupos_rede.as_ref().map(|g| comparacao(particao, g))
    }
}

fn comb2(x: usize) -> f64 {
    (x * x.wrapping_sub(1)) as f64 / 2.0
}

/// ARI e informação mútua normalizada (média aritmética das entropias).
pub fn comparacao(particao: &IndexMap<i64, usize>, grupos_rede: &BTreeMap<i64, usize>) -> Comparacao {
    let comuns: Vec<i64> = particao.keys().copied().filter(|n| grupos_rede.contains_key(n)).collect();
    let n = comuns.len();
    let n_corte = comuns.iter().map(|x| particao[x]).collect::<std::collections::BTreeSet<_>>().len();
    let n_rede = comuns.iter().map(|x| grupos_rede[x]).collect::<std::collections::BTreeSet<_>>().len();
    if n == 0 {
        return Comparacao { ari: None, nmi: None, n_comparados: 0, n_grupos_corte: n_corte, n_grupos_rede: n_rede };
    }
    let mut ca: IndexMap<usize, usize> = IndexMap::new();
    let mut cb: IndexMap<usize, usize> = IndexMap::new();
    let mut cab: IndexMap<(usize, usize), usize> = IndexMap::new();
    for no in &comuns {
        *ca.entry(particao[no]).or_default() += 1;
        *cb.entry(grupos_rede[no]).or_default() += 1;
        *cab.entry((particao[no], grupos_rede[no])).or_default() += 1;
    }
    let soma_ab = py_sum(cab.values().map(|&v| comb2(v)));
    let soma_a = py_sum(ca.values().map(|&v| comb2(v)));
    let soma_b = py_sum(cb.values().map(|&v| comb2(v)));
    let total = comb2(n);
    let esperado = if total != 0.0 { soma_a * soma_b / total } else { 0.0 };
    let maximo = (soma_a + soma_b) / 2.0;
    let ari = if (maximo - esperado).abs() < 1e-12 { 1.0 } else { (soma_ab - esperado) / (maximo - esperado) };
    let nf = n as f64;
    let ha = -py_sum(ca.values().map(|&v| v as f64 / nf * (v as f64 / nf).ln()));
    let hb = -py_sum(cb.values().map(|&v| v as f64 / nf * (v as f64 / nf).ln()));
    let info = py_sum(cab.iter().map(|(&(i, j), &v)| {
        v as f64 / nf * (((v * n) as f64) / ((ca[&i] * cb[&j]) as f64)).ln()
    }));
    let nmi = if ha + hb < 1e-12 { 1.0 } else { (2.0 * info / (ha + hb)).min(1.0).max(0.0) };
    Comparacao {
        ari: Some(py_round(ari, 6)),
        nmi: Some(py_round(nmi, 6)),
        n_comparados: n,
        n_grupos_corte: n_corte,
        n_grupos_rede: n_rede,
    }
}

fn fmt2(x: f64) -> String {
    format!("{:.2}", x).replace('.', ",")
}

fn primeiras_alturas(d: &Dendrograma) -> IndexMap<i64, f64> {
    let n = d.nos.len();
    let mut primeira: IndexMap<usize, f64> = IndexMap::new();
    for f in &d.fusoes {
        for x in [f.a, f.b] {
            if x < n && !primeira.contains_key(&x) {
                primeira.insert(x, f.altura);
            }
        }
    }
    primeira.into_iter().map(|(i, h)| (d.nos[i], h)).collect()
}

/// Frases em português sobre o que o dendrograma mostra no corte dado.
pub fn interpreta(d: &Dendrograma, n_grupos: Option<usize>) -> Vec<String> {
    let n = d.nos.len();
    let nome = |no: i64| d.nomes.get(&no).cloned().unwrap_or_else(|| no.to_string());
    let mut frases = Vec::new();
    if n < 2 {
        return vec!["A rede tem um único nó; não há hierarquia a interpretar.".into()];
    }
    let n_grupos = n_grupos.unwrap_or(if d.n_grupos_sugerido > 0 { d.n_grupos_sugerido } else { 2 }).clamp(1, n);
    let particao = d.corte(n_grupos);
    let h_corte = d.altura_do_corte(n_grupos);
    let mut contagem: BTreeMap<usize, usize> = BTreeMap::new();
    for g in particao.values() {
        *contagem.entry(*g).or_default() += 1;
    }
    frases.push(format!(
        "O corte em {} grupo{} (altura ≈ {}, distância = 1 − similaridade) divide {} nós; quanto mais baixo o corte, \
         mais temas específicos, e quanto mais alto, menos temas e mais amplos.",
        n_grupos,
        if n_grupos != 1 { "s" } else { "" },
        fmt2(h_corte),
        n
    ));
    let sem_arestas = d.alturas.is_empty()
        || d.alturas.iter().cloned().fold(f64::MIN, f64::max) - d.alturas.iter().cloned().fold(f64::MAX, f64::min) < 1e-9;
    if sem_arestas {
        frases.push(
            "Os itens quase não têm ligações entre si: todas as fusões ocorrem na mesma distância e não há estrutura \
             hierárquica a interpretar."
                .into(),
        );
    } else if n_grupos == d.n_grupos_sugerido {
        frases.push("Esse número coincide com o maior salto entre fusões, indício de uma separação natural em temas.".into());
    } else if d.n_grupos_sugerido > 0 {
        frases.push(format!(
            "O maior salto entre fusões sugere {} grupos como separação mais natural.",
            d.n_grupos_sugerido
        ));
    }
    // `Counter.most_common(1)`: o primeiro máximo na ordem de inserção (grupos crescentes)
    let (mut grande, mut tam) = (0usize, 0usize);
    for (g, c) in &contagem {
        if *c > tam {
            grande = *g;
            tam = *c;
        }
    }
    let mut membros: Vec<i64> = d.ordem.iter().copied().filter(|no| particao[no] == grande).collect();
    if let Some(p) = &d.pesos {
        membros.sort_by(|a, b| {
            let (pa, pb) = (p.get(a).copied().unwrap_or(0.0), p.get(b).copied().unwrap_or(0.0));
            (-pa).partial_cmp(&-pb).unwrap_or(std::cmp::Ordering::Equal)
        });
    }
    let exemplo = membros.iter().take(4).map(|&no| nome(no)).collect::<Vec<_>>().join(", ");
    frases.push(format!(
        "O maior ramo tem {} {} ({}% da rede), por exemplo: {}{}.",
        tam,
        if tam == 1 { "nó" } else { "nós" },
        tam * 100 / n,
        exemplo,
        if tam > 4 { "…" } else { "" }
    ));
    let pares: Vec<(i64, i64, f64)> =
        d.fusoes.iter().filter(|f| f.a < n && f.b < n).map(|f| (d.nos[f.a], d.nos[f.b], f.altura)).take(3).collect();
    if !pares.is_empty() {
        let txt = pares
            .iter()
            .map(|&(a, b, h)| format!("{} e {} (distância {})", nome(a), nome(b), fmt2(h)))
            .collect::<Vec<_>>()
            .join("; ");
        frases.push(format!("Os pares mais próximos são {}.", txt));
    }
    let primeira = primeiras_alturas(d);
    let mut valores: Vec<f64> = primeira.values().copied().collect();
    valores.sort_by(|a, b| a.partial_cmp(b).unwrap());
    if valores.len() >= 4 {
        let q1 = valores[valores.len() / 4];
        let q3 = valores[(3 * valores.len()) / 4];
        let limite = q3 + 1.5 * (q3 - q1);
        let mut tardios: Vec<i64> = primeira.iter().filter(|(_, &h)| h > limite + 1e-12).map(|(&no, _)| no).collect();
        tardios.sort_by(|a, b| (-primeira[a]).partial_cmp(&-primeira[b]).unwrap());
        let isolados: Vec<i64> = d.nos.iter().copied().filter(|no| contagem[&particao[no]] == 1).collect();
        if !tardios.is_empty() || !isolados.is_empty() {
            let mut lista: Vec<i64> = Vec::new();
            for no in tardios.into_iter().chain(isolados) {
                if !lista.contains(&no) {
                    lista.push(no);
                }
            }
            lista.truncate(5);
            frases.push(format!(
                "Nós que se juntam tarde ou ficam isolados no corte (possíveis outliers ou temas periféricos): {}.",
                lista.iter().map(|&no| nome(no)).collect::<Vec<_>>().join(", ")
            ));
        }
    }
    if let Some(gr) = &d.grupos_rede {
        let comp = comparacao(&particao, gr);
        if let (Some(ari), Some(nmi)) = (comp.ari, comp.nmi) {
            if comp.n_grupos_rede >= 2 {
                let nivel = if ari >= 0.7 {
                    "alta"
                } else if ari >= 0.4 {
                    "moderada"
                } else {
                    "baixa"
                };
                frases.push(format!(
                    "Concordância {} com os agrupamentos da rede: índice de Rand ajustado {} e informação mútua \
                     normalizada {} ({} grupos na rede contra {} no corte).",
                    nivel,
                    fmt2(ari),
                    fmt2(nmi),
                    comp.n_grupos_rede,
                    comp.n_grupos_corte
                ));
                if ari < 0.4 {
                    frases.push(
                        "Divergência grande indica partição pouco robusta: os temas dependem do método de agrupamento."
                            .into(),
                    );
                }
            }
        }
    }
    if n < POUCOS_NOS {
        frases.push(format!("Aviso: apenas {} nós; a hierarquia tem pouco poder de interpretação.", n));
    }
    if n > 2 && d.coph < LIMITE_COPH {
        frases.push(format!(
            "Aviso: correlação cofenética {} (abaixo de 0,6); o dendrograma distorce as distâncias originais e deve ser \
             lido com cautela. Tente outra ligação.",
            fmt2(d.coph)
        ));
    } else if n > 2 {
        frases.push(format!("Correlação cofenética {}: o dendrograma representa bem as distâncias originais.", fmt2(d.coph)));
    }
    frases
}

// ------------------------------------------------------------ período

/// Resultado completo para um período: dados + SVG.
#[derive(Clone, Debug, Serialize)]
pub struct DendrogramaPeriodo {
    pub dendrograma: Dendrograma,
    pub n_grupos: usize,
    pub n_grupos_sugerido: usize,
    pub n_nos: usize,
    pub ligacao: Ligacao,
    pub coph: f64,
    pub comparacao: Option<Comparacao>,
    pub particao: BTreeMap<i64, usize>,
    pub frases: Vec<String>,
    pub omitidos: usize,
    pub limite: usize,
    pub periodo: String,
    pub svg: String,
}

/// Sub-rede dos `limite` itens mais frequentes (`dendrograma_do_periodo`).
pub fn entrada_do_resultado(r: &Resultado, limite: usize) -> Option<(Entrada, usize)> {
    if r.nos.len() < 3 {
        return None;
    }
    let mut escolhidos: Vec<(i64, usize, String)> = r.nos.iter().map(|n| (n.id, n.frequencia, n.rotulo.clone())).collect();
    escolhidos.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    escolhidos.truncate(limite);
    let ids: std::collections::BTreeSet<i64> = escolhidos.iter().map(|e| e.0).collect();
    let mut nos: Vec<i64> = ids.iter().copied().collect();
    nos.sort();
    let arestas: Vec<(i64, i64, f64)> =
        r.arestas.iter().filter(|a| ids.contains(&a.a) && ids.contains(&a.b)).map(|a| (a.a, a.b, a.peso)).collect();
    let mut grupos_rede = BTreeMap::new();
    for (i, g) in r.grupos.iter().enumerate() {
        for no in &g.nos {
            if ids.contains(no) {
                grupos_rede.insert(*no, i);
            }
        }
    }
    let nomes = escolhidos.iter().map(|e| (e.0, e.2.clone())).collect();
    let pesos = escolhidos.iter().map(|e| (e.0, e.1.max(0) as f64)).collect();
    let omitidos = r.nos.len() - escolhidos.len();
    Some((Entrada { nos, arestas, nomes, pesos: Some(pesos), grupos_rede: Some(grupos_rede) }, omitidos))
}

/// Dendrograma de um período de `redes-core`: dados e SVG (`n_grupos` vazio usa o sugerido).
pub fn do_periodo(
    r: &Resultado,
    ligacao: Ligacao,
    limite: usize,
    n_grupos: Option<usize>,
    titulo: &str,
) -> Result<DendrogramaPeriodo, String> {
    let (entrada, omitidos) =
        entrada_do_resultado(r, limite).ok_or_else(|| "Poucos itens neste período para um dendrograma (mínimo de 3).".to_string())?;
    let d = constroi(&entrada, ligacao)?;
    let n_total = d.nos.len();
    let ng = n_grupos.map(|g| g.min(n_total)).unwrap_or(d.n_grupos_sugerido).max(1);
    let particao = d.corte(ng);
    let comparacao = d.comparacao(&particao);
    Ok(DendrogramaPeriodo {
        n_grupos: ng,
        n_grupos_sugerido: d.n_grupos_sugerido,
        n_nos: n_total,
        ligacao,
        coph: py_round(d.coph, 4),
        comparacao,
        frases: interpreta(&d, Some(ng)),
        omitidos,
        limite,
        periodo: r.resumo.periodo.clone(),
        svg: svg(&d, Some(ng), titulo),
        particao: particao.iter().map(|(a, b)| (*a, *b)).collect(),
        dendrograma: d,
    })
}

// ---------------------------------------------------------------- SVG

pub const LARGURA: f64 = 900.0;
const CINZA: &str = "#94A3B8";
const PALETA: [&str; 10] =
    ["#1F77B4", "#D95F02", "#2CA02C", "#9467BD", "#C0392B", "#0F9D9A", "#B8860B", "#E7298A", "#555555", "#6B8E23"];

fn escala_ticks(maximo: f64) -> Vec<f64> {
    if maximo <= 0.0 {
        return vec![0.0];
    }
    let mut passo = 1.0;
    for p in [0.05, 0.1, 0.2, 0.25, 0.5, 1.0] {
        passo = p;
        if maximo / p <= 6.0 {
            break;
        }
    }
    let mut ticks = Vec::new();
    let mut v = 0.0;
    while v <= maximo + 1e-9 {
        ticks.push(py_round(v, 4));
        v += passo;
    }
    ticks
}

/// SVG horizontal autocontido: raiz à esquerda, folhas à direita, ramos coloridos abaixo do corte.
pub fn svg(d: &Dendrograma, n_grupos: Option<usize>, titulo: &str) -> String {
    let n = d.nos.len();
    let rotulos: BTreeMap<i64, String> =
        d.nos.iter().map(|&no| (no, d.nomes.get(&no).cloned().unwrap_or_else(|| no.to_string()))).collect();
    let pref = format!("dg{}", hash8(&format!("{:?}{:?}{:?}{}", d.nos, d.fusoes, n_grupos, titulo)));
    let titulo_txt = if titulo.is_empty() { "Dendrograma" } else { titulo };
    if n < 2 {
        return format!(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{l}\" height=\"120\" viewBox=\"0 0 {l} 120\" role=\"img\" \
             aria-labelledby=\"{p}-t\"><title id=\"{p}-t\">{t}</title><rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\
             <text x=\"{h}\" y=\"64\" text-anchor=\"middle\" font-family=\"{f}\" font-size=\"14\" fill=\"{tf}\">Dendrograma \
             indisponível: a rede tem menos de 2 nós.</text></svg>",
            l = pyf(LARGURA).trim_end_matches(".0"),
            p = pref,
            t = esc(titulo_txt),
            h = pyf(LARGURA / 2.0),
            f = FONTE_INTER,
            tf = TINTA_FRACA
        );
    }
    let ng = n_grupos.unwrap_or(if d.n_grupos_sugerido > 0 { d.n_grupos_sugerido } else { 2 }).clamp(1, n);
    let particao = d.corte(ng);
    let h_corte = d.altura_do_corte(ng);
    let mut h_max = d.alturas.iter().cloned().fold(f64::MIN, f64::max);
    if h_max == 0.0 {
        h_max = 1.0;
    }
    let h_max = h_max.max(h_corte);

    let linha = if n > 40 { 20.0 } else { 22.0 };
    let (topo, base) = (58.0f64, 52.0f64);
    let maior = rotulos.values().map(|r| curto(r, 30).chars().count()).max().unwrap_or(0) as f64;
    let esq = 24.0;
    let dir_ = 24.0 + maior * 7.8 + 16.0;
    let (x0, x1) = (esq, LARGURA - dir_);
    let altura_svg = (topo + base + linha * n as f64) as i64;
    let fonte = if linha >= 20.0 { 12 } else { 11 };
    let x_de = |h: f64| x1 - (h / h_max) * (x1 - x0);

    let posicao: BTreeMap<i64, usize> = d.nos.iter().enumerate().map(|(i, &x)| (x, i)).collect();
    let mut y_folha: BTreeMap<i64, f64> = BTreeMap::new();
    for (i, &no) in d.ordem.iter().enumerate() {
        y_folha.insert(no, topo + linha * (i as f64 + 0.5));
    }
    let mut y: Vec<f64> = vec![0.0; n + d.fusoes.len()];
    for (&no, &yy) in &y_folha {
        y[posicao[&no]] = yy;
    }
    let mut h_no = vec![0.0f64; n + d.fusoes.len()];
    let mut grupo_no: Vec<Option<usize>> = vec![None; n + d.fusoes.len()];
    for i in 0..n {
        grupo_no[i] = Some(particao[&d.nos[i]]);
    }
    for (k, f) in d.fusoes.iter().enumerate() {
        y[n + k] = (y[f.a] + y[f.b]) / 2.0;
        h_no[n + k] = f.altura;
        let (ga, gb) = (grupo_no[f.a], grupo_no[f.b]);
        grupo_no[n + k] = if ga == gb && ga.is_some() { ga } else { None };
        if f.altura > h_corte {
            grupo_no[n + k] = None;
        }
    }
    let cor = |g: Option<usize>| g.map_or(CINZA, |g| PALETA[g % PALETA.len()]);
    let mut contagem: BTreeMap<usize, usize> = BTreeMap::new();
    for g in particao.values() {
        *contagem.entry(*g).or_default() += 1;
    }
    let desc = format!(
        "Dendrograma horizontal de {} nós, ligação {}, cortado em {} grupos (tamanhos: {}). Correlação cofenética {:.2}.",
        n,
        d.ligacao.nome(),
        ng,
        contagem.values().map(|c| c.to_string()).collect::<Vec<_>>().join(", "),
        d.coph
    );
    let mut p: Vec<String> = Vec::new();
    p.push(format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{w}\" height=\"{h}\" viewBox=\"0 0 {w} {h}\" role=\"img\" \
         aria-labelledby=\"{pr}-t {pr}-d\">",
        w = LARGURA as i64,
        h = altura_svg,
        pr = pref
    ));
    p.push(format!("<title id=\"{}-t\">{}</title>", pref, esc(titulo_txt)));
    p.push(format!("<desc id=\"{}-d\">{}</desc>", pref, esc(&desc)));
    p.push("<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>".into());
    p.push(format!(
        "<text x=\"{}\" y=\"22\" text-anchor=\"middle\" font-family=\"{}\" font-size=\"15\" font-weight=\"600\" \
         fill=\"{}\">{}</text>",
        pyf(LARGURA / 2.0),
        FONTE_INTER,
        TINTA,
        esc(&curto(titulo_txt, 110))
    ));
    p.push(format!(
        "<text x=\"{}\" y=\"40\" text-anchor=\"middle\" font-family=\"{}\" font-size=\"12\" fill=\"{}\">{} grupo{} · \
         ligação {} · cofenética {:.2}</text>",
        pyf(LARGURA / 2.0),
        FONTE_INTER,
        TINTA_FRACA,
        ng,
        if ng != 1 { "s" } else { "" },
        esc(d.ligacao.nome()),
        d.coph
    ));
    let eixo_y = (topo + linha * n as f64 + 6.0) as i64;
    p.push(format!("<g id=\"{}-escala\" font-family=\"{}\" font-size=\"11\" fill=\"{}\">", pref, FONTE_INTER, TINTA_FRACA));
    for t in escala_ticks(h_max) {
        let xt = x_de(t);
        p.push(format!(
            "<line x1=\"{:.1}\" y1=\"{}\" x2=\"{:.1}\" y2=\"{}\" stroke=\"#E2E8F0\" stroke-width=\"1\"/>",
            xt,
            topo as i64,
            xt,
            eixo_y
        ));
        p.push(format!("<text x=\"{:.1}\" y=\"{}\" text-anchor=\"middle\">{:.2}</text>", xt, eixo_y + 14, t));
    }
    p.push(format!(
        "<text x=\"{:.1}\" y=\"{}\" text-anchor=\"middle\">altura de fusão (distância = 1 − similaridade)</text></g>",
        (x0 + x1) / 2.0,
        eixo_y + 32
    ));
    p.push(format!(
        "<g id=\"{}-ramos\" fill=\"none\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\">",
        pref
    ));
    for (k, f) in d.fusoes.iter().enumerate() {
        let xm = x_de(f.altura);
        for filho in [f.a, f.b] {
            let g = if f.altura <= h_corte { grupo_no[filho] } else { None };
            let xf = x_de(h_no[filho]);
            p.push(format!(
                "<path d=\"M{:.1} {:.1}V{:.1}H{:.1}\" stroke=\"{}\"/>",
                xm,
                y[n + k],
                y[filho],
                xf,
                cor(g)
            ));
        }
    }
    p.push("</g>".into());
    let xc = x_de(h_corte);
    p.push(format!(
        "<g id=\"{}-corte\"><line x1=\"{:.1}\" y1=\"{}\" x2=\"{:.1}\" y2=\"{}\" stroke=\"{}\" stroke-width=\"1.4\" \
         stroke-dasharray=\"6 4\"/><text x=\"{:.1}\" y=\"{}\" text-anchor=\"{}\" font-family=\"{}\" font-size=\"11\" \
         fill=\"{}\">corte {:.2}</text></g>",
        pref,
        xc,
        (topo - 6.0) as i64,
        xc,
        eixo_y,
        TINTA,
        xc,
        (topo - 10.0) as i64,
        if xc < 45.0 { "start" } else { "middle" },
        FONTE_INTER,
        TINTA,
        h_corte
    ));
    let vazio = BTreeMap::new();
    let pesos = d.pesos.as_ref().unwrap_or(&vazio);
    let pmax = pesos.values().cloned().fold(0.0f64, f64::max);
    p.push(format!("<g id=\"{}-folhas\" font-family=\"{}\" font-size=\"{}\" fill=\"{}\">", pref, FONTE_INTER, fonte, TINTA));
    for &no in &d.ordem {
        let yy = y_folha[&no];
        let g = particao[&no];
        let raio = 3.0 + if pmax > 0.0 { 3.0 * pesos.get(&no).copied().unwrap_or(0.0) / pmax } else { 0.0 };
        p.push(format!("<circle cx=\"{:.1}\" cy=\"{:.1}\" r=\"{:.1}\" fill=\"{}\"/>", x1, yy, raio, cor(Some(g))));
        p.push(format!(
            "<text x=\"{:.1}\" y=\"{:.1}\"><title>{} (grupo {})</title>{}</text>",
            x1 + 11.0,
            yy + 4.0,
            esc(&rotulos[&no]),
            g + 1,
            esc(&curto(&rotulos[&no], 30))
        ));
    }
    p.push("</g></svg>".into());
    p.concat()
}
