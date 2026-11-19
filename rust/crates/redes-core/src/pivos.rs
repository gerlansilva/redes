//! Pontos de virada (porta de `pivos.py`): nós de intermediação alta (decil
//! superior) com vizinhos em pelo menos dois agrupamentos. Sem rajadas, não há
//! medida sigma (os campos `rajada` e `sigma` ficam `None`).

use std::collections::{BTreeSet, HashMap};

use serde::{Deserialize, Serialize};

use crate::rede::Rede;

pub const MINIMO_NOS: usize = 40;
pub const LIMITE_NOS: usize = 800;
pub const PROPORCAO_DESCRITOR: f64 = 0.5;
pub const PERCENTIL: f64 = 90.0;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Pivo {
    pub no: i64,
    pub rotulo: String,
    /// Intermediação normalizada por (n-1)(n-2)/2.
    pub intermediacao: f64,
    pub grau: usize,
    pub grupos_vizinhos: usize,
    /// Índice (0-based) do grupo do nó.
    pub grupo: Option<usize>,
    pub frequencia: usize,
    pub rajada: Option<f64>,
    pub sigma: Option<f64>,
    /// Só nos termos-descritor: proporção dos documentos do período.
    #[serde(default)]
    pub proporcao_documentos: Option<f64>,
    #[serde(default)]
    pub motivo: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct PontosDeVirada {
    pub n_nos: usize,
    pub suficiente: bool,
    pub pivos: Vec<Pivo>,
    pub termos_descritores: Vec<Pivo>,
    pub avisos: Vec<String>,
    pub nao_calculado: Option<String>,
}

fn nos_txt(n: usize) -> String {
    format!("{n} {}", if n == 1 { "nó" } else { "nós" })
}

fn vazio(n: usize, avisos: Vec<String>, nao_calculado: Option<String>) -> PontosDeVirada {
    PontosDeVirada { n_nos: n, suficiente: n >= MINIMO_NOS, pivos: vec![], termos_descritores: vec![], avisos, nao_calculado }
}

/// Resultado de uma rede cujos pontos de virada não puderam ser calculados.
pub fn nao_calculado(n: usize, motivo: &str) -> PontosDeVirada {
    let texto = format!("Não calculado: {motivo}");
    vazio(n, vec![texto.clone()], Some(texto))
}

/// Percentil com interpolação linear (igual ao padrão do numpy).
pub fn percentil(valores: &[f64], p: f64) -> f64 {
    let mut o = valores.to_vec();
    o.sort_by(|a, b| a.total_cmp(b));
    let posicao = (o.len() as f64 - 1.0) * p / 100.0;
    let baixo = posicao as usize;
    let alto = (baixo + 1).min(o.len() - 1);
    o[baixo] + (o[alto] - o[baixo]) * (posicao - baixo as f64)
}

pub struct Entrada<'a> {
    pub rede: &'a Rede,
    pub grupo_do_no: &'a HashMap<i64, usize>,
    pub tem_grupos: bool,
    pub frequencia: &'a dyn Fn(i64) -> usize,
    pub rotulo: &'a dyn Fn(i64) -> String,
    /// Documentos do período (só em co-ocorrência, para os termos-descritor).
    pub total_documentos: Option<usize>,
    /// Intermediação (bruta) por posição, se já calculada.
    pub intermediacao: Option<Vec<f64>>,
    pub topo: usize,
}

pub fn pontos_de_virada(e: Entrada) -> PontosDeVirada {
    let rede = e.rede;
    let n = rede.quantidade_nos();
    let mut avisos: Vec<String> = Vec::new();
    if n < MINIMO_NOS {
        avisos.push(format!("Poucos dados: só {} (o mínimo confiável é {MINIMO_NOS}); leia como indício.", nos_txt(n)));
    }
    if n < 3 || rede.quantidade_arestas() == 0 {
        avisos.push("A rede tem menos de 3 nós ou nenhuma ligação; não há pontos de virada.".into());
        return vazio(n, avisos, None);
    }
    if !e.tem_grupos || e.grupo_do_no.is_empty() {
        avisos.push("Não há agrupamentos; sem eles não se identificam pontos de virada.".into());
        return vazio(n, avisos, None);
    }
    if n > LIMITE_NOS {
        let texto = format!(
            "Não calculado: rede com {n} nós (limite {LIMITE_NOS}); a intermediação foi pulada para não travar. Filtre a rede e tente de novo."
        );
        avisos.push(texto.clone());
        return vazio(n, avisos, Some(texto));
    }

    let bc = e.intermediacao.unwrap_or_else(|| crate::centralidade::intermediacao(rede));
    let norma = ((n - 1) * (n - 2)) as f64 / 2.0;
    let bcn: Vec<f64> = bc.iter().map(|b| b / norma).collect();
    let pos = |no: i64| rede.idx[&no];

    let mut descritores: HashMap<i64, f64> = HashMap::new();
    if let Some(total) = e.total_documentos.filter(|&t| t > 0) {
        for &no in &rede.nos {
            let prop = (e.frequencia)(no) as f64 / total as f64;
            if prop > PROPORCAO_DESCRITOR {
                descritores.insert(no, prop);
            }
        }
    }

    let item = |no: i64| -> Pivo {
        let mut viz: BTreeSet<usize> = rede.adj[pos(no)].keys().filter_map(|v| e.grupo_do_no.get(v).copied()).collect();
        if let Some(&g) = e.grupo_do_no.get(&no) {
            viz.insert(g);
        }
        Pivo {
            no,
            rotulo: (e.rotulo)(no),
            intermediacao: bcn[pos(no)],
            grau: rede.adj[pos(no)].len(),
            grupos_vizinhos: viz.len(),
            grupo: e.grupo_do_no.get(&no).copied(),
            frequencia: (e.frequencia)(no),
            rajada: None,
            sigma: None,
            proporcao_documentos: None,
            motivo: None,
        }
    };
    let ordem = |a: &Pivo, b: &Pivo| {
        b.intermediacao.total_cmp(&a.intermediacao).then_with(|| a.rotulo.cmp(&b.rotulo)).then_with(|| a.no.cmp(&b.no))
    };

    let candidatos: Vec<i64> = rede.nos.iter().copied().filter(|no| !descritores.contains_key(no)).collect();
    let positivos: Vec<f64> = candidatos.iter().map(|&no| bcn[pos(no)]).filter(|&b| b > 0.0).collect();
    let mut pivos: Vec<Pivo> = Vec::new();
    if !positivos.is_empty() {
        let limiar = percentil(&positivos, PERCENTIL);
        let mut itens: Vec<Pivo> = candidatos
            .iter()
            .copied()
            .filter(|&no| bcn[pos(no)] > 0.0 && bcn[pos(no)] >= limiar)
            .map(&item)
            .filter(|i| i.grupos_vizinhos >= 2)
            .collect();
        itens.sort_by(ordem);
        itens.truncate(e.topo);
        pivos = itens;
    } else {
        avisos.push("Nenhum nó tem intermediação positiva; não há pontos de virada.".into());
    }
    if pivos.is_empty() && !positivos.is_empty() {
        avisos.push("Nenhum nó de intermediação alta tem vizinhos em dois ou mais agrupamentos.".into());
    }

    let mut ds: Vec<(i64, f64)> = descritores.iter().map(|(&k, &v)| (k, v)).collect();
    ds.sort_by(|a, b| b.1.total_cmp(&a.1).then_with(|| (e.rotulo)(a.0).cmp(&(e.rotulo)(b.0))).then_with(|| a.0.cmp(&b.0)));
    let mut termos = Vec::new();
    for (no, prop) in ds {
        let mut d = item(no);
        d.proporcao_documentos = Some(prop);
        d.motivo = Some(format!(
            "Presente em {:.0}% dos documentos do período: descreve o corpus, não distingue temas; fora do ranking.",
            prop * 100.0
        ));
        termos.push(d);
    }
    if !termos.is_empty() {
        avisos.push(format!("{} termo(s) em mais de 50% dos documentos ficaram fora do ranking.", termos.len()));
    }
    PontosDeVirada { n_nos: n, suficiente: n >= MINIMO_NOS, pivos, termos_descritores: termos, avisos, nao_calculado: None }
}
