//! Qualidade dos agrupamentos e pontos de virada de um período, calculados da
//! rede e dos grupos de [`PeriodoRel`] (portas de `qualidade.py` e `pivos.py`).
//!
//! Usado pelo adaptador do redes-core, que ainda não traz esses indicadores. A
//! silhueta, o Q e o Q do Louvain seguem o Python; a intermediação é o Brandes de
//! custo 1/peso de `measures.intermediacao`. O sigma (força de rajada) não é
//! calculado aqui: sem rajada, a coluna Sigma não aparece.

use std::cmp::Reverse;
use std::collections::{BinaryHeap, HashMap};

use redes_core::rede::Rede;

use crate::dados::*;
use crate::metodo::{PIVOS_MINIMO_NOS, PIVOS_PERCENTIL, PIVOS_PROPORCAO_DESCRITOR, Q_GRUPO_GRANDE, Q_LIMITE_NOS, Q_MINIMO_NOS, Q_MINIMO_NOS_SILHUETA};

const AVISO_COAUTORIA: &str = "Em redes de coautoria, um Q alto costuma ser artefato: a rede é feita de pequenos grupos de coautores, que a \
modularidade premia mesmo sem estrutura temática. Leia o Q junto com o número de itens por agrupamento.";

const NOTA_NITIDEZ: &str = "Os avisos de nitidez acima descrevem o quanto a divisão se destaca na rede; eles não mudam o selo. Em redes densas \
(acoplamento, referências) ficam baixos mesmo quando os grupos são grandes e coesos.";

/// Número em pt-BR, com vírgula e o sinal "−" nos negativos; perto de um limiar do selo mostra
/// casas a mais, para o texto nunca contradizer o selo.
pub fn num(x: f64, casas: usize, limiares: &[f64]) -> String {
    let meia = 0.5 * 10f64.powi(-(casas as i32));
    let perto: Vec<f64> = limiares.iter().copied().filter(|t| (x - t).abs() < meia).collect();
    let mut extra = 0;
    if !perto.is_empty() {
        extra = 1;
        while extra < 5 && perto.iter().any(|&t| x != t && arredonda(x, casas + extra) == t) {
            extra += 1;
        }
    }
    let mut t = format!("{:.*}", casas + extra, x);
    if t.parse::<f64>().map(|v| v == 0.0).unwrap_or(false) {
        t = t.trim_start_matches('-').to_string();
    }
    t.replace('.', ",").replace('-', "\u{2212}")
}

fn arredonda(x: f64, casas: usize) -> f64 {
    format!("{:.*}", casas, x).parse().unwrap_or(x)
}

fn particao(p: &PeriodoRel) -> HashMap<i64, usize> {
    let mut m = HashMap::new();
    for (i, g) in p.grupos.iter().enumerate() {
        for &n in &g.nos {
            m.entry(n).or_insert(i);
        }
    }
    m
}

fn arestas(p: &PeriodoRel) -> &[ArestaRel] {
    p.rede.as_ref().map(|r| r.arestas.as_slice()).unwrap_or(&[])
}

fn ids(p: &PeriodoRel) -> Vec<i64> {
    p.rede.as_ref().map(|r| r.nos.iter().map(|n| n.id).collect()).unwrap_or_default()
}

/// Q de Newman ponderado; nó fora da partição é um grupo de um nó. `None` sem ligação positiva.
pub fn modularidade(nos: &[i64], arestas: &[ArestaRel], part: &HashMap<i64, usize>) -> Option<f64> {
    let rotulo = |n: i64| -> (u8, i64) {
        match part.get(&n) {
            Some(&g) => (0, g as i64),
            None => (1, n),
        }
    };
    let mut grau: HashMap<i64, f64> = nos.iter().map(|&n| (n, 0.0)).collect();
    let mut dois_m = 0.0;
    let mut dentro: HashMap<(u8, i64), f64> = HashMap::new();
    for a in arestas {
        if !(a.peso > 0.0) {
            continue;
        }
        *grau.entry(a.a).or_insert(0.0) += a.peso;
        *grau.entry(a.b).or_insert(0.0) += a.peso;
        dois_m += 2.0 * a.peso;
        let (ga, gb) = (rotulo(a.a), rotulo(a.b));
        if ga == gb {
            *dentro.entry(ga).or_insert(0.0) += 2.0 * a.peso;
        }
    }
    if dois_m <= 0.0 {
        return None;
    }
    let mut total: HashMap<(u8, i64), f64> = HashMap::new();
    for (&n, &g) in &grau {
        *total.entry(rotulo(n)).or_insert(0.0) += g;
    }
    let mut chaves: Vec<_> = total.keys().copied().collect();
    chaves.sort();
    Some(chaves.iter().map(|c| dentro.get(c).copied().unwrap_or(0.0) / dois_m - (total[c] / dois_m).powi(2)).sum())
}

fn componentes(nos: &[i64], arestas: &[ArestaRel]) -> usize {
    let mut adj: HashMap<i64, Vec<i64>> = HashMap::new();
    for a in arestas {
        if a.peso > 0.0 {
            adj.entry(a.a).or_default().push(a.b);
            adj.entry(a.b).or_default().push(a.a);
        }
    }
    let mut visto = std::collections::HashSet::new();
    let mut q = 0;
    for &i in nos {
        if visto.contains(&i) {
            continue;
        }
        q += 1;
        let mut pilha = vec![i];
        visto.insert(i);
        while let Some(n) = pilha.pop() {
            for &v in adj.get(&n).map(|v| v.as_slice()).unwrap_or(&[]) {
                if visto.insert(v) {
                    pilha.push(v);
                }
            }
        }
    }
    q
}

/// Silhueta por nó agrupado: (nós, grupo de cada um, valor) ou `None`.
fn silhuetas(p: &PeriodoRel, part: &HashMap<i64, usize>) -> Option<(Vec<i64>, Vec<usize>, Vec<f64>)> {
    let todos = ids(p);
    let nos: Vec<i64> = todos.into_iter().filter(|n| part.contains_key(n)).collect();
    let n = nos.len();
    if n < 2 {
        return None;
    }
    let mut gids: Vec<usize> = nos.iter().map(|x| part[x]).collect();
    gids.sort_unstable();
    gids.dedup();
    if gids.len() < 2 {
        return None;
    }
    let col: HashMap<i64, usize> = nos.iter().enumerate().map(|(i, &x)| (x, i)).collect();
    let maximo = arestas(p).iter().map(|a| a.peso).fold(0.0, f64::max);
    let escala = if maximo > 1.0 { maximo } else { 1.0 };
    let mut dist = vec![1.0f64; n * n];
    for i in 0..n {
        dist[i * n + i] = 0.0;
    }
    for a in arestas(p) {
        if let (Some(&i), Some(&j)) = (col.get(&a.a), col.get(&a.b)) {
            let s = (a.peso.max(0.0) / escala).min(1.0);
            dist[i * n + j] = 1.0 - s;
            dist[j * n + i] = 1.0 - s;
        }
    }
    let pos_g: HashMap<usize, usize> = gids.iter().enumerate().map(|(i, &g)| (g, i)).collect();
    let k = gids.len();
    let rot: Vec<usize> = nos.iter().map(|x| pos_g[&part[x]]).collect();
    let mut tam = vec![0.0f64; k];
    for &r in &rot {
        tam[r] += 1.0;
    }
    let mut soma = vec![0.0f64; n * k];
    for i in 0..n {
        for j in 0..n {
            soma[i * k + rot[j]] += dist[i * n + j];
        }
    }
    let mut s = vec![0.0; n];
    for i in 0..n {
        let proprio = tam[rot[i]];
        let a_ = soma[i * k + rot[i]] / (proprio - 1.0);
        let mut b_ = f64::INFINITY;
        for g in 0..k {
            if g != rot[i] {
                b_ = b_.min(soma[i * k + g] / tam[g]);
            }
        }
        let m = a_.max(b_);
        s[i] = if proprio > 1.0 && m > 0.0 && m.is_finite() { (b_ - a_) / m } else { 0.0 };
    }
    Some((nos, rot.iter().map(|&r| gids[r]).collect(), s))
}

/// Silhueta média por agrupamento (só os de pelo menos 3 itens); `None` quando a avaliação é indefinida.
pub fn silhueta_por_grupo(p: &PeriodoRel) -> Vec<Option<f64>> {
    let mut out = vec![None; p.grupos.len()];
    let part = particao(p);
    let nos = ids(p);
    if nos.len() < Q_MINIMO_NOS || p.grupos.len() < 2 || modularidade(&nos, arestas(p), &part).is_none() {
        return out;
    }
    let agrupados = nos.iter().filter(|n| part.contains_key(n)).count();
    if agrupados > Q_LIMITE_NOS {
        return out;
    }
    if let Some((_, rot, val)) = silhuetas(p, &part) {
        for (i, g) in p.grupos.iter().enumerate() {
            if g.itens() >= Q_MINIMO_NOS_SILHUETA {
                let v: Vec<f64> = rot.iter().zip(val.iter()).filter(|(r, _)| **r == i).map(|(_, v)| *v).collect();
                if !v.is_empty() {
                    out[i] = Some(v.iter().sum::<f64>() / v.len() as f64);
                }
            }
        }
    }
    out
}

/// Indicadores de qualidade dos agrupamentos de um período.
pub fn avalia(p: &PeriodoRel, unidade: &str) -> Qualidade {
    let nos = ids(p);
    let n_nos = nos.len();
    let part = particao(p);
    let n_agrupados = nos.iter().filter(|n| part.contains_key(n)).count();
    let n_grupos = p.grupos.len();
    let comp = if n_nos > 0 { componentes(&nos, arestas(p)) } else { 0 };
    let n_em_grandes = nos.iter().filter(|n| part.get(n).map(|&g| p.grupos[g].itens() >= Q_GRUPO_GRANDE).unwrap_or(false)).count();
    let pct = |x: usize| if n_nos > 0 { 100.0 * x as f64 / n_nos as f64 } else { 0.0 };
    let mut out = Qualidade {
        nivel: "indefinido".into(),
        n_nos,
        pct_agrupados: pct(n_agrupados),
        pct_em_grupos_grandes: Some(pct(n_em_grandes)),
        ..Default::default()
    };
    if n_nos < Q_MINIMO_NOS {
        out.avisos.push(if n_nos == 0 {
            format!("A rede não tem itens; não dá para avaliar a qualidade dos agrupamentos (mínimo de {Q_MINIMO_NOS} itens).")
        } else {
            format!(
                "A rede tem só {n_nos} {}; com tão poucos itens não dá para avaliar a qualidade dos agrupamentos (mínimo de {Q_MINIMO_NOS}).",
                if n_nos == 1 { "item" } else { "itens" }
            )
        });
        return out;
    }
    if n_grupos < 2 {
        out.avisos.push("Há menos de dois agrupamentos; não dá para avaliar se a divisão em grupos faz sentido.".into());
        return out;
    }
    let Some(q) = modularidade(&nos, arestas(p), &part) else {
        out.avisos.push("A rede não tem ligações com valor positivo; não dá para avaliar os agrupamentos.".into());
        return out;
    };
    out.q = Some(q);

    // Q do Louvain, como régua de comparação
    let ql = (|| {
        let mut rede = Rede::nova(nos.iter().copied());
        for a in arestas(p) {
            rede.adiciona_aresta(a.a, a.b, a.peso);
        }
        let conj = redes_core::agrupamento::louvain(&rede, 1, n_nos + 1).ok()?;
        let mut pl: HashMap<i64, usize> = HashMap::new();
        for (i, g) in conj.agrupamentos.iter().enumerate() {
            for &n in &g.nos {
                pl.insert(n, i);
            }
        }
        modularidade(&nos, arestas(p), &pl)
    })();
    out.q_louvain = ql;
    if let Some(ql) = ql {
        if ql > 0.0 {
            out.razao = Some(q / ql);
        }
    }

    // Silhueta
    if n_agrupados > Q_LIMITE_NOS {
        out.avisos.push(format!(
            "A rede é grande ({n_agrupados} itens agrupados); a medida de coesão por item foi dispensada para não deixar a análise lenta."
        ));
    } else if let Some((_, rot, val)) = silhuetas(p, &part) {
        let validos: Vec<f64> = rot.iter().zip(val.iter()).filter(|(r, _)| p.grupos[**r].itens() >= Q_MINIMO_NOS_SILHUETA).map(|(_, v)| *v).collect();
        if !validos.is_empty() {
            out.silhueta_media = Some(validos.iter().sum::<f64>() / validos.len() as f64);
            out.pct_silhueta_negativa = Some(100.0 * validos.iter().filter(|v| **v < 0.0).count() as f64 / validos.len() as f64);
        }
    }

    // Selo
    let ordem = |s: &str| match s {
        "ok" => 0,
        "atencao" => 1,
        _ => 2,
    };
    let mut nivel = "ok";
    let sobe = |novo: &'static str, nivel: &mut &'static str| {
        if ordem(novo) > ordem(nivel) {
            *nivel = novo;
        }
    };
    let pu = out.pct_em_grupos_grandes.unwrap_or(0.0);
    if pu < 50.0 {
        sobe("ruim", &mut nivel);
        out.avisos.push(format!(
            "Só {}% dos itens estão em agrupamentos de {Q_GRUPO_GRANDE} ou mais itens; o resto está solto ou em grupos pequenos (pares, \
             trios), e o mapa tem pouco o que ler.",
            num(pu, 0, &[50.0, 80.0])
        ));
    } else if pu < 80.0 {
        sobe("atencao", &mut nivel);
        out.avisos.push(format!(
            "{}% dos itens estão em agrupamentos de {Q_GRUPO_GRANDE} ou mais itens; o resto está solto ou em grupos pequenos (pares, trios).",
            num(pu, 0, &[50.0, 80.0])
        ));
    }
    if comp as f64 > n_nos as f64 / 2.0 {
        sobe("atencao", &mut nivel);
        out.avisos.push("A rede é fragmentada (quase só pares e itens isolados); um valor de força alto não indica qualidade.".into());
    }
    if unidade == "Authors" {
        sobe("atencao", &mut nivel);
        out.avisos.push(AVISO_COAUTORIA.into());
    }
    let mut notas: Vec<String> = Vec::new();
    if q < 0.15 {
        notas.push(format!(
            "A divisão em grupos é muito fraca (força {}): os itens de um grupo quase não se ligam mais entre si do que com os outros grupos.",
            num(q, 2, &[0.15, 0.30])
        ));
    } else if q < 0.30 {
        notas.push(format!("A divisão em grupos é moderada (força {}); os limites entre alguns grupos podem ser pouco nítidos.", num(q, 2, &[0.15, 0.30])));
    }
    if let Some(r) = out.razao {
        if r < 0.6 {
            notas.push(format!(
                "Outro método de agrupamento acha uma divisão bem mais nítida nesta rede (a atual alcança só {}% dela); vale comparar.",
                num(100.0 * r, 0, &[60.0])
            ));
        }
    }
    if let Some(sm) = out.silhueta_media {
        if sm < 0.0 {
            notas.push(format!("Em média, os itens estão mais perto de outros grupos do que do próprio (coesão {}).", num(sm, 2, &[0.0, 0.05])));
        } else if sm < 0.05 {
            notas.push(format!(
                "Os grupos são pouco coesos (coesão média {}): os itens ficam quase tão perto de outros grupos quanto do seu.",
                num(sm, 2, &[0.0, 0.05])
            ));
        }
    }
    if let Some(pn) = out.pct_silhueta_negativa {
        if pn > 30.0 {
            notas.push(format!("{}% dos itens estão mais perto de outro grupo do que do seu; talvez estejam mal alocados.", num(pn, 0, &[30.0])));
        }
    }
    if !notas.is_empty() {
        out.avisos.extend(notas);
        out.avisos.push(NOTA_NITIDEZ.into());
    }
    out.nivel = nivel.to_string();
    out
}

// ------------------------------------------------------------------ pivôs

fn custo(peso: f64) -> f64 {
    if peso > 0.0 {
        1.0 / peso
    } else {
        1e308 / 4.0
    }
}

/// Intermediação de Brandes com custo 1/peso (`measures.intermediacao`).
pub fn intermediacao(nos: &[i64], arestas: &[ArestaRel]) -> HashMap<i64, f64> {
    let n = nos.len();
    let idx: HashMap<i64, usize> = nos.iter().enumerate().map(|(i, &x)| (x, i)).collect();
    let mut adj: Vec<Vec<(usize, f64)>> = vec![Vec::new(); n];
    for a in arestas {
        if let (Some(&i), Some(&j)) = (idx.get(&a.a), idx.get(&a.b)) {
            adj[i].push((j, custo(a.peso)));
            adj[j].push((i, custo(a.peso)));
        }
    }
    let mut c = vec![0.0f64; n];
    for s in 0..n {
        let mut pred: Vec<Vec<usize>> = vec![Vec::new(); n];
        let mut dist = vec![f64::INFINITY; n];
        let mut caminhos = vec![0.0f64; n];
        let mut pilha: Vec<usize> = Vec::new();
        dist[s] = 0.0;
        caminhos[s] = 1.0;
        let mut fila: BinaryHeap<Reverse<(u64, i64)>> = BinaryHeap::new();
        fila.push(Reverse((0f64.to_bits(), nos[s])));
        while let Some(Reverse((d, no))) = fila.pop() {
            let atual = f64::from_bits(d);
            let i = idx[&no];
            if atual > dist[i] {
                continue;
            }
            pilha.push(i);
            let base = dist[i];
            for &(j, cu) in &adj[i] {
                let nova = base + cu;
                let alvo = dist[j];
                if nova < alvo - 1e-10 {
                    dist[j] = nova;
                    fila.push(Reverse((nova.to_bits(), nos[j])));
                    caminhos[j] = caminhos[i];
                    pred[j] = vec![i];
                } else if (nova - alvo).abs() <= 1e-10 {
                    caminhos[j] += caminhos[i];
                    pred[j].push(i);
                }
            }
        }
        let mut dep = vec![0.0f64; n];
        while let Some(w) = pilha.pop() {
            if !pred[w].is_empty() && caminhos[w] > 0.0 {
                for &v in &pred[w] {
                    dep[v] += caminhos[v] / caminhos[w] * (1.0 + dep[w]);
                }
            }
            if w != s {
                c[w] += dep[w];
            }
        }
    }
    nos.iter().enumerate().map(|(i, &x)| (x, c[i] / 2.0)).collect()
}

fn percentil(valores: &[f64], p: f64) -> f64 {
    let mut o = valores.to_vec();
    o.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let pos = (o.len() - 1) as f64 * p / 100.0;
    let baixo = pos as usize;
    let alto = (baixo + 1).min(o.len() - 1);
    o[baixo] + (o[alto] - o[baixo]) * (pos - baixo as f64)
}

fn vazio(n: usize, avisos: Vec<String>, nao_calculado: Option<String>) -> Pivos {
    Pivos { n_nos: n, suficiente: n >= PIVOS_MINIMO_NOS, itens: vec![], termos_descritores: vec![], avisos, nao_calculado }
}

/// Pontos de virada do período (sem sigma: não há rajada aqui).
pub fn pontos_de_virada(p: &PeriodoRel, matriz: &str, topo: usize) -> Pivos {
    let Some(rede) = &p.rede else { return vazio(0, vec![], None) };
    let nos = ids(p);
    let n = nos.len();
    let mut avisos: Vec<String> = Vec::new();
    if n < PIVOS_MINIMO_NOS {
        avisos.push(format!("Poucos dados: só {n} {} (o mínimo confiável é {PIVOS_MINIMO_NOS}); leia como indício.", if n == 1 { "nó" } else { "nós" }));
    }
    if n < 3 || rede.arestas.is_empty() {
        avisos.push("A rede tem menos de 3 nós ou nenhuma ligação; não há pontos de virada.".into());
        return vazio(n, avisos, None);
    }
    let gdn = particao(p);
    if p.grupos.is_empty() || gdn.is_empty() {
        avisos.push("Não há agrupamentos; sem eles não se identificam pontos de virada.".into());
        return vazio(n, avisos, None);
    }
    if n > 800 {
        let t = format!("Não calculado: rede com {n} nós (limite 800); a intermediação foi pulada para não travar. Filtre a rede e tente de novo.");
        avisos.push(t.clone());
        return vazio(n, avisos, Some(t));
    }
    let bc = intermediacao(&nos, &rede.arestas);
    let norma = (n as f64 - 1.0) * (n as f64 - 2.0) / 2.0;
    let bcn: HashMap<i64, f64> = nos.iter().map(|&x| (x, bc[&x] / norma)).collect();
    let info: HashMap<i64, &NoRel> = rede.nos.iter().map(|x| (x.id, x)).collect();
    let mut adj: HashMap<i64, Vec<i64>> = HashMap::new();
    for a in &rede.arestas {
        adj.entry(a.a).or_default().push(a.b);
        adj.entry(a.b).or_default().push(a.a);
    }
    let mut descritores: Vec<(i64, f64)> = Vec::new();
    if matriz == "CoOccurrence" && p.documentos > 0 {
        for &x in &nos {
            let prop = info[&x].frequencia as f64 / p.documentos as f64;
            if prop > PIVOS_PROPORCAO_DESCRITOR {
                descritores.push((x, prop));
            }
        }
    }
    let eh_desc = |x: i64| descritores.iter().any(|d| d.0 == x);
    let item = |x: i64| -> PivoItem {
        let mut viz: Vec<usize> = adj.get(&x).map(|v| v.iter().filter_map(|y| gdn.get(y).copied()).collect()).unwrap_or_default();
        if let Some(&g) = gdn.get(&x) {
            viz.push(g);
        }
        viz.sort_unstable();
        viz.dedup();
        PivoItem { no: x, rotulo: info[&x].rotulo.clone(), intermediacao: bcn[&x], grupos_vizinhos: viz.len(), grupo: gdn.get(&x).copied(), frequencia: info[&x].frequencia, sigma: None }
    };
    let candidatos: Vec<i64> = nos.iter().copied().filter(|&x| !eh_desc(x)).collect();
    let positivos: Vec<f64> = candidatos.iter().map(|x| bcn[x]).filter(|&v| v > 0.0).collect();
    let mut pivos: Vec<PivoItem> = Vec::new();
    if !positivos.is_empty() {
        let limiar = percentil(&positivos, PIVOS_PERCENTIL);
        let mut itens: Vec<PivoItem> = candidatos.iter().filter(|x| bcn[x] > 0.0 && bcn[x] >= limiar).map(|&x| item(x)).filter(|i| i.grupos_vizinhos >= 2).collect();
        itens.sort_by(|a, b| b.intermediacao.partial_cmp(&a.intermediacao).unwrap().then_with(|| a.rotulo.cmp(&b.rotulo)).then_with(|| a.no.cmp(&b.no)));
        itens.truncate(topo);
        pivos = itens;
    } else {
        avisos.push("Nenhum nó tem intermediação positiva; não há pontos de virada.".into());
    }
    if pivos.is_empty() && !positivos.is_empty() {
        avisos.push("Nenhum nó de intermediação alta tem vizinhos em dois ou mais agrupamentos.".into());
    }
    let mut termos: Vec<TermoDescritor> = descritores.iter().map(|&(x, prop)| TermoDescritor { rotulo: info[&x].rotulo.clone(), proporcao_documentos: prop }).collect();
    termos.sort_by(|a, b| b.proporcao_documentos.partial_cmp(&a.proporcao_documentos).unwrap().then_with(|| a.rotulo.cmp(&b.rotulo)));
    if !termos.is_empty() {
        avisos.push(format!("{} termo(s) em mais de 50% dos documentos ficaram fora do ranking.", termos.len()));
    }
    Pivos { n_nos: n, suficiente: n >= PIVOS_MINIMO_NOS, itens: pivos, termos_descritores: termos, avisos, nao_calculado: None }
}

#[cfg(test)]
mod testes {
    use super::*;

    fn periodo(n: i64) -> PeriodoRel {
        // duas cliques de n nós unidas por uma ponte
        let mut nos = Vec::new();
        let mut arestas = Vec::new();
        for g in 0..2i64 {
            for i in 0..n {
                nos.push(NoRel { id: g * 100 + i, rotulo: format!("n{}", g * 100 + i), frequencia: 2, grupo: Some(g as usize) });
                for j in 0..i {
                    arestas.push(ArestaRel { a: g * 100 + i, b: g * 100 + j, peso: 0.8 });
                }
            }
        }
        arestas.push(ArestaRel { a: 0, b: 100, peso: 0.2 });
        let grupos = (0..2usize)
            .map(|g| GrupoRel { id: g + 1, rotulo: format!("g{g}"), nos: (0..n).map(|i| g as i64 * 100 + i).collect(), ..Default::default() })
            .collect();
        PeriodoRel { nome: "t".into(), documentos: 10, rede_nos: nos.len(), rede_arestas: arestas.len(), grupos, rede: Some(RedeRel { nos, arestas }), ..Default::default() }
    }

    #[test]
    fn qualidade_boa() {
        let p = periodo(8);
        let q = avalia(&p, "Words");
        assert_eq!(q.nivel, "ok");
        assert!(q.q.unwrap() > 0.4, "{:?}", q.q);
        assert!(q.silhueta_media.unwrap() > 0.0);
        assert_eq!(silhueta_por_grupo(&p).iter().flatten().count(), 2);
    }

    #[test]
    fn poucos_itens_indefinido() {
        let q = avalia(&periodo(3), "Words");
        assert_eq!(q.nivel, "indefinido");
        assert!(q.avisos[0].contains("mínimo de 15"));
    }

    #[test]
    fn pivo_e_a_ponte() {
        let p = periodo(25);
        let pv = pontos_de_virada(&p, "CoOccurrence", 10);
        assert!(pv.suficiente);
        let nos: Vec<i64> = pv.itens.iter().map(|i| i.no).collect();
        assert!(nos.contains(&0) && nos.contains(&100), "{nos:?}");
    }

    #[test]
    fn formato_num() {
        assert_eq!(num(0.1496, 2, &[0.15, 0.30]), "0,1496");
        assert_eq!(num(-0.5, 2, &[]), "\u{2212}0,50");
    }
}
