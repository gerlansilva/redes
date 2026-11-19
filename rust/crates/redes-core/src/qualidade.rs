//! Qualidade dos agrupamentos de um período (porta de `qualidade.py`):
//! modularidade Q ponderada, Q do Louvain como régua, silhueta e o selo
//! (ok/atencao/ruim) que depende só da cobertura útil, da fragmentação da rede
//! e, em coautoria, de um teto em "atencao".

use std::collections::HashMap;

use indexmap::IndexMap;
use serde::{Deserialize, Serialize};

use crate::agrupamento::{louvain, Agrupamento};
use crate::pycompat::py_sum;
use crate::rede::Rede;

pub const MINIMO_NOS: usize = 15;
pub const MINIMO_NOS_SILHUETA: usize = 3;
pub const LIMITE_NOS: usize = 2000;
pub const GRUPO_GRANDE: usize = 5;

const AVISO_COAUTORIA: &str = "Em redes de coautoria, um Q alto costuma ser artefato: a rede é feita de pequenos grupos de coautores, que a modularidade premia mesmo sem estrutura temática. Leia o Q junto com o número de itens por agrupamento.";
const NOTA_NITIDEZ: &str = "Os avisos de nitidez acima descrevem o quanto a divisão se destaca na rede; eles não mudam o selo. Em redes densas (acoplamento, referências) ficam baixos mesmo quando os grupos são grandes e coesos.";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Qualidade {
    pub n_nos: usize,
    pub n_grupos: usize,
    pub pct_agrupados: f64,
    pub pct_em_grupos_grandes: f64,
    /// Modularidade de Newman ponderada.
    pub q: Option<f64>,
    pub q_louvain: Option<f64>,
    pub razao: Option<f64>,
    pub silhueta_media: Option<f64>,
    /// Um valor por grupo (índice em `Resultado::grupos`).
    pub silhueta_por_grupo: Vec<Option<f64>>,
    pub pct_silhueta_negativa: Option<f64>,
    pub componentes: usize,
    /// "ok", "atencao", "ruim" ou "indefinido".
    pub nivel: String,
    pub avisos: Vec<String>,
}

/// Número em pt-BR, com vírgula e o sinal "−" (U+2212) nos negativos; perto de um
/// limiar do selo mostra casas a mais para o texto não contradizer o selo.
pub fn num(x: f64, casas: usize, limiares: &[f64]) -> String {
    let meia = 0.5 * 10f64.powi(-(casas as i32));
    let perto: Vec<f64> = limiares.iter().copied().filter(|t| (x - t).abs() < meia).collect();
    let mut extra = 0usize;
    if !perto.is_empty() {
        extra = 1;
        let arred = |c: usize| format!("{:.*}", c, x).parse::<f64>().unwrap_or(x);
        while extra < 5 && perto.iter().any(|&t| x != t && arred(casas + extra) == t) {
            extra += 1;
        }
    }
    let mut texto = format!("{:.*}", casas + extra, x);
    if texto.parse::<f64>().map(|v| v == 0.0).unwrap_or(false) {
        texto = texto.trim_start_matches('-').to_string();
    }
    texto.replace('.', ",").replace('-', "\u{2212}")
}

/// Partição nó -> grupo; em empate de pertinência vale o primeiro grupo.
pub fn particao_dos_grupos(grupos: &[Vec<i64>]) -> HashMap<i64, usize> {
    let mut d = HashMap::new();
    for (i, g) in grupos.iter().enumerate() {
        for &no in g {
            d.entry(no).or_insert(i);
        }
    }
    d
}

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
enum Chave {
    Grupo(usize),
    Solto(i64),
}

/// Q de Newman ponderado. Nó fora da partição é um grupo de um nó. `None` quando
/// a rede não tem ligação com peso positivo.
pub fn modularidade(rede: &Rede, particao: &HashMap<i64, usize>) -> Option<f64> {
    let n = rede.nos.len();
    let mut grau = vec![0.0f64; n];
    let mut dois_m = 0.0f64;
    let mut dentro: HashMap<Chave, f64> = HashMap::new();
    let chave = |no: i64| particao.get(&no).map(|&g| Chave::Grupo(g)).unwrap_or(Chave::Solto(no));
    for (a, b, w) in rede.arestas() {
        if !(w > 0.0) {
            continue;
        }
        grau[rede.idx[&a]] += w;
        grau[rede.idx[&b]] += w;
        dois_m += 2.0 * w;
        let (ga, gb) = (chave(a), chave(b));
        if ga == gb {
            *dentro.entry(ga).or_insert(0.0) += 2.0 * w;
        }
    }
    if dois_m <= 0.0 {
        return None;
    }
    let mut total: IndexMap<Chave, f64> = IndexMap::new();
    for (i, &no) in rede.nos.iter().enumerate() {
        *total.entry(chave(no)).or_insert(0.0) += grau[i];
    }
    Some(py_sum(total.iter().map(|(c, t)| dentro.get(c).copied().unwrap_or(0.0) / dois_m - (t / dois_m).powi(2))))
}

/// Componentes conexas por ligações de peso positivo (item isolado conta como uma).
pub fn componentes(rede: &Rede) -> usize {
    let n = rede.nos.len();
    let mut visto = vec![false; n];
    let mut q = 0;
    for ini in 0..n {
        if visto[ini] {
            continue;
        }
        q += 1;
        visto[ini] = true;
        let mut pilha = vec![ini];
        while let Some(i) = pilha.pop() {
            for (v, &w) in &rede.adj[i] {
                let j = rede.idx[v];
                if w > 0.0 && !visto[j] {
                    visto[j] = true;
                    pilha.push(j);
                }
            }
        }
    }
    q
}

/// Silhueta por nó agrupado: (nós, grupo de cada nó, valor). `None` se não há dois grupos.
pub fn silhuetas(rede: &Rede, grupos: &[Vec<i64>]) -> Option<(Vec<i64>, Vec<usize>, Vec<f64>)> {
    let particao = particao_dos_grupos(grupos);
    let nos: Vec<i64> = rede.nos.iter().copied().filter(|n| particao.contains_key(n)).collect();
    let n = nos.len();
    if n < 2 {
        return None;
    }
    let mut ids: Vec<usize> = nos.iter().map(|no| particao[no]).collect();
    ids.sort_unstable();
    ids.dedup();
    if ids.len() < 2 {
        return None;
    }
    let coluna: HashMap<i64, usize> = nos.iter().enumerate().map(|(i, &no)| (no, i)).collect();
    let maximo = rede.arestas().iter().map(|a| a.2).fold(0.0f64, f64::max);
    let escala = if maximo > 1.0 { maximo } else { 1.0 };
    let pos_grupo: HashMap<usize, usize> = ids.iter().enumerate().map(|(i, &g)| (g, i)).collect();
    let rotulo: Vec<usize> = nos.iter().map(|no| pos_grupo[&particao[no]]).collect();
    let k = ids.len();
    let mut tamanho = vec![0.0f64; k];
    for &r in &rotulo {
        tamanho[r] += 1.0;
    }
    // soma[i][g] = soma das distâncias do nó i aos nós do grupo g (distância 1 sem ligação, 0 em si
    // mesmo), somada em ordem de coluna como o produto de matrizes do numpy: a ordem importa só no
    // último dígito, mas decide o sinal de uma silhueta que é zero em teoria.
    let mut soma = vec![vec![0.0f64; k]; n];
    let mut linha = vec![1.0f64; n];
    for i in 0..n {
        for x in linha.iter_mut() {
            *x = 1.0;
        }
        linha[i] = 0.0;
        for (v, &w) in &rede.adj[rede.idx[&nos[i]]] {
            if let Some(&j) = coluna.get(v) {
                if j != i {
                    linha[j] = 1.0 - (w.max(0.0) / escala).min(1.0);
                }
            }
        }
        for j in 0..n {
            soma[i][rotulo[j]] += linha[j];
        }
    }
    let valores: Vec<f64> = (0..n)
        .map(|i| {
            let proprio = tamanho[rotulo[i]];
            let a = soma[i][rotulo[i]] / (proprio - 1.0);
            let mut b = f64::INFINITY;
            for g in 0..k {
                if g != rotulo[i] {
                    b = b.min(soma[i][g] / tamanho[g]);
                }
            }
            let m = if a.is_nan() { f64::NAN } else { a.max(b) };
            if proprio > 1.0 && m > 0.0 {
                (b - a) / m
            } else {
                0.0
            }
        })
        .collect();
    Some((nos, rotulo.iter().map(|&r| ids[r]).collect(), valores))
}

fn media(v: &[f64]) -> f64 {
    v.iter().sum::<f64>() / v.len() as f64
}

/// Indicadores de qualidade dos agrupamentos de um período.
/// `grupos` são as listas de nós de cada grupo; `coautoria` liga o teto de "Atenção" (unidade Authors).
pub fn avalia(rede: &Rede, grupos: &[Agrupamento], coautoria: bool, limite_nos: usize) -> Qualidade {
    let listas: Vec<Vec<i64>> = grupos.iter().map(|g| g.nos.clone()).collect();
    let n_nos = rede.nos.len();
    let particao = particao_dos_grupos(&listas);
    let n_agrupados = rede.nos.iter().filter(|n| particao.contains_key(n)).count();
    let n_grupos = grupos.len();
    let comp = if n_nos > 0 { componentes(rede) } else { 0 };
    let tamanhos: Vec<usize> = listas
        .iter()
        .map(|g| {
            let mut v = g.clone();
            v.sort_unstable();
            v.dedup();
            v.len()
        })
        .collect();
    let n_em_grandes = rede.nos.iter().filter(|n| particao.get(n).is_some_and(|&g| tamanhos[g] >= GRUPO_GRANDE)).count();
    let pct = |x: usize| if n_nos > 0 { 100.0 * x as f64 / n_nos as f64 } else { 0.0 };
    let mut out = Qualidade {
        n_nos,
        n_grupos,
        pct_agrupados: pct(n_agrupados),
        pct_em_grupos_grandes: pct(n_em_grandes),
        q: None,
        q_louvain: None,
        razao: None,
        silhueta_media: None,
        silhueta_por_grupo: vec![None; n_grupos],
        pct_silhueta_negativa: None,
        componentes: comp,
        nivel: "indefinido".into(),
        avisos: Vec::new(),
    };

    if n_nos < MINIMO_NOS {
        out.avisos.push(if n_nos == 0 {
            format!("A rede não tem itens; não dá para avaliar a qualidade dos agrupamentos (mínimo de {MINIMO_NOS} itens).")
        } else {
            format!(
                "A rede tem só {n_nos} {}; com tão poucos itens não dá para avaliar a qualidade dos agrupamentos (mínimo de {MINIMO_NOS}).",
                if n_nos == 1 { "item" } else { "itens" }
            )
        });
        return out;
    }
    if n_grupos < 2 {
        out.avisos.push("Há menos de dois agrupamentos; não dá para avaliar se a divisão em grupos faz sentido.".into());
        return out;
    }
    let Some(q) = modularidade(rede, &particao) else {
        out.avisos.push("A rede não tem ligações com valor positivo; não dá para avaliar os agrupamentos.".into());
        return out;
    };
    out.q = Some(q);

    let ql = louvain(rede, 1, n_nos + 1).ok().and_then(|c| {
        let p: HashMap<i64, usize> = c.agrupamentos.iter().enumerate().flat_map(|(i, g)| g.nos.iter().map(move |&n| (n, i))).collect();
        modularidade(rede, &p)
    });
    out.q_louvain = ql;
    if let Some(ql) = ql.filter(|&x| x > 0.0) {
        out.razao = Some(q / ql);
    }

    let sil = if n_agrupados > limite_nos { None } else { silhuetas(rede, &listas) };
    if sil.is_none() && n_agrupados > limite_nos {
        out.avisos.push(format!(
            "A rede é grande ({n_agrupados} itens agrupados); a medida de coesão por item foi dispensada para não deixar a análise lenta."
        ));
    } else if let Some((_, rotulos, valores)) = sil {
        for i in 0..n_grupos {
            if tamanhos[i] >= MINIMO_NOS_SILHUETA {
                let sel: Vec<f64> = rotulos.iter().zip(&valores).filter(|(r, _)| **r == i).map(|(_, v)| *v).collect();
                if !sel.is_empty() {
                    out.silhueta_por_grupo[i] = Some(media(&sel));
                }
            }
        }
        let validos: Vec<f64> = rotulos.iter().zip(&valores).filter(|(r, _)| tamanhos[**r] >= MINIMO_NOS_SILHUETA).map(|(_, v)| *v).collect();
        if !validos.is_empty() {
            out.silhueta_media = Some(media(&validos));
            out.pct_silhueta_negativa = Some(100.0 * validos.iter().filter(|&&v| v < 0.0).count() as f64 / validos.len() as f64);
        }
    }

    // Selo: estrutura do mapa (cobertura útil, fragmentação, coautoria).
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
    let pu = out.pct_em_grupos_grandes;
    if pu < 50.0 {
        sobe("ruim", &mut nivel);
        out.avisos.push(format!(
            "Só {}% dos itens estão em agrupamentos de {GRUPO_GRANDE} ou mais itens; o resto está solto ou em grupos pequenos (pares, trios), e o mapa tem pouco o que ler.",
            num(pu, 0, &[50.0, 80.0])
        ));
    } else if pu < 80.0 {
        sobe("atencao", &mut nivel);
        out.avisos.push(format!(
            "{}% dos itens estão em agrupamentos de {GRUPO_GRANDE} ou mais itens; o resto está solto ou em grupos pequenos (pares, trios).",
            num(pu, 0, &[50.0, 80.0])
        ));
    }
    if comp as f64 > n_nos as f64 / 2.0 {
        sobe("atencao", &mut nivel);
        out.avisos.push("A rede é fragmentada (quase só pares e itens isolados); um valor de força alto não indica qualidade.".into());
    }
    if coautoria {
        sobe("atencao", &mut nivel);
        out.avisos.push(AVISO_COAUTORIA.into());
    }

    // Notas sobre a nitidez da divisão: não mudam o selo.
    let mut notas: Vec<String> = Vec::new();
    if q < 0.15 {
        notas.push(format!(
            "A divisão em grupos é muito fraca (força {}): os itens de um grupo quase não se ligam mais entre si do que com os outros grupos.",
            num(q, 2, &[0.15, 0.30])
        ));
    } else if q < 0.30 {
        notas.push(format!(
            "A divisão em grupos é moderada (força {}); os limites entre alguns grupos podem ser pouco nítidos.",
            num(q, 2, &[0.15, 0.30])
        ));
    }
    if let Some(r) = out.razao.filter(|&r| r < 0.6) {
        notas.push(format!(
            "Outro método de agrupamento acha uma divisão bem mais nítida nesta rede (a atual alcança só {}% dela); vale comparar.",
            num(100.0 * r, 0, &[60.0])
        ));
    }
    if let Some(sm) = out.silhueta_media {
        if sm < 0.0 {
            notas.push(format!(
                "Em média, os itens estão mais perto de outros grupos do que do próprio (coesão {}).",
                num(sm, 2, &[0.0, 0.05])
            ));
        } else if sm < 0.05 {
            notas.push(format!(
                "Os grupos são pouco coesos (coesão média {}): os itens ficam quase tão perto de outros grupos quanto do seu.",
                num(sm, 2, &[0.0, 0.05])
            ));
        }
    }
    if let Some(pn) = out.pct_silhueta_negativa.filter(|&p| p > 30.0) {
        notas.push(format!("{}% dos itens estão mais perto de outro grupo do que do seu; talvez estejam mal alocados.", num(pn, 0, &[30.0])));
    }
    if !notas.is_empty() {
        out.avisos.extend(notas);
        out.avisos.push(NOTA_NITIDEZ.into());
    }
    out.nivel = nivel.into();
    out
}
