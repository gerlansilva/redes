//! Mapas longitudinais (porta de `longitudinal.py`): evolução temática entre
//! períodos consecutivos e matriz de sobreposição entre todos os períodos, com
//! as medidas de equivalência, associação, inclusão, Jaccard e Salton aplicadas
//! a conjuntos de itens. Exporta o mapa de evolução no formato Pajek.

use std::collections::{BTreeMap, BTreeSet, HashMap};

use serde::{Deserialize, Serialize};

use crate::erro::{Erro, Resultado as Res};
use crate::parametros::{Parametros, Similaridade};
use crate::pipeline::{executar_periodo, Resultado};
use crate::projeto::Projeto;
use crate::rede::similaridade;

/// Nome da medida de sobreposição, para legendas.
pub fn nome_medida(m: Similaridade) -> &'static str {
    match m {
        Similaridade::AssociationStrength => "força de associação",
        Similaridade::EquivalenceIndex => "índice de equivalência",
        Similaridade::InclusionIndex => "índice de inclusão",
        Similaridade::JaccardIndex => "índice de Jaccard",
        Similaridade::SaltonCosine => "cosseno de Salton",
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct NoEvolucao {
    /// Posição do período (0..n-1).
    pub periodo: usize,
    /// Posição (1-based) do agrupamento no período, por tamanho decrescente.
    pub selo: usize,
    pub rotulo: String,
    pub itens: BTreeSet<i64>,
    pub principal: Option<i64>,
    pub tamanho: usize,
    /// Rótulo de cada item.
    pub nomes: BTreeMap<i64, String>,
}

impl NoEvolucao {
    pub fn contem_principal(&self, outro: &NoEvolucao) -> bool {
        self.principal.is_some_and(|p| outro.itens.contains(&p)) || outro.principal.is_some_and(|p| self.itens.contains(&p))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Elo {
    /// Índices em `Evolucao::nos`.
    pub origem: usize,
    pub destino: usize,
    pub peso: f64,
    pub principal_comum: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Continua {
    pub de: String,
    pub para: String,
    pub sobreposicao: f64,
    pub itens_comuns: usize,
    pub exemplos: Vec<String>,
    pub mesmo_no_principal: bool,
    pub fraca: bool,
    pub itens_de: usize,
    pub itens_para: usize,
}

/// Temas que continuam, somem ou surgem entre dois períodos consecutivos.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Transicao {
    pub de: String,
    pub para: String,
    pub continuam: Vec<Continua>,
    pub somem: Vec<String>,
    pub surgem: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Evolucao {
    pub periodos: Vec<String>,
    pub nos: Vec<NoEvolucao>,
    pub elos: Vec<Elo>,
    /// Sobreposição entre todos os pares de períodos.
    pub sobreposicao: Vec<Vec<f64>>,
    pub transicoes: Vec<Transicao>,
    pub medida: Similaridade,
    /// Parâmetros da análise de cada período, em texto (legenda da figura).
    pub parametros: String,
}

impl Evolucao {
    pub fn nos_do_periodo(&self, periodo: usize) -> Vec<usize> {
        (0..self.nos.len()).filter(|&i| self.nos[i].periodo == periodo).collect()
    }

    /// Mapa de evolução no formato Pajek (`.net`).
    pub fn pajek(&self) -> String {
        let mut s = format!("*Vertices {}\n", self.nos.len());
        for (i, no) in self.nos.iter().enumerate() {
            s.push_str(&format!("{} \"{}\"\n", i + 1, no.rotulo.replace('"', "'")));
        }
        s.push_str("*Edges\n");
        for e in &self.elos {
            s.push_str(&format!("{} {} {}\n", e.origem + 1, e.destino + 1, formata_g(e.peso, 6)));
        }
        s
    }
}

/// `format(x, ".{precisao}g")` do Python.
pub fn formata_g(x: f64, precisao: usize) -> String {
    if x == 0.0 {
        return "0".into();
    }
    if !x.is_finite() {
        return if x.is_nan() { "nan".into() } else if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let p = precisao.max(1);
    let e = format!("{:.*e}", p - 1, x);
    let (mant, exp) = e.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    let corta = |s: &str| -> String {
        if s.contains('.') {
            s.trim_end_matches('0').trim_end_matches('.').to_string()
        } else {
            s.to_string()
        }
    };
    if exp < -4 || exp >= p as i32 {
        format!("{}e{}{:02}", corta(mant), if exp < 0 { '-' } else { '+' }, exp.abs())
    } else {
        corta(&format!("{:.*}", (p as i32 - 1 - exp) as usize, x))
    }
}

/// `round(x, n)` do Python (arredondamento exato, empate para o par).
pub fn arredonda(x: f64, n: usize) -> f64 {
    format!("{:.*}", n, x).parse().unwrap_or(x)
}

/// Parâmetros que definem os temas, em uma linha (legenda da figura).
pub fn descreve_parametros(p: &Parametros) -> String {
    let mut t = format!(
        "frequência mínima {} · coocorrência mínima {} · rede de {} a {} itens",
        p.min_freq, p.min_cooc, p.rede_min, p.rede_max
    );
    if p.corte != 0.0 {
        t.push_str(&format!(" · corte {}", formata_g(p.corte, 6)));
    }
    t
}

/// Aplica a medida de similaridade a dois conjuntos de itens.
pub fn mede_conjuntos(medida: Similaridade, origem: &BTreeSet<i64>, destino: &BTreeSet<i64>) -> f64 {
    let comum = origem.intersection(destino).count();
    if comum == 0 {
        return 0.0;
    }
    let v = similaridade(medida, origem.len(), destino.len(), comum as f64);
    if v.is_finite() {
        v
    } else {
        0.0
    }
}

/// Executa a análise de cada período (todos) e monta evolução e sobreposição.
pub fn evolucao(projeto: &Projeto, p: &Parametros, medida: Similaridade, limite_elos: usize) -> Res<Evolucao> {
    let periodos = projeto.periodos()?;
    if periodos.is_empty() {
        return Err(Erro::PeriodoInexistente("(nenhum)".into()));
    }
    let mut resultados = Vec::new();
    for per in &periodos {
        resultados.push(executar_periodo(projeto, per.id, &per.nome, p)?);
    }
    Ok(constroi(&periodos.iter().map(|x| x.nome.clone()).collect::<Vec<_>>(), &resultados, p, medida, limite_elos))
}

/// Monta o mapa a partir de resultados já calculados (um por período, em ordem).
pub fn constroi(nomes: &[String], resultados: &[Resultado], p: &Parametros, medida: Similaridade, limite_elos: usize) -> Evolucao {
    let mut mapa = Evolucao {
        periodos: nomes.to_vec(),
        nos: Vec::new(),
        elos: Vec::new(),
        sobreposicao: Vec::new(),
        transicoes: Vec::new(),
        medida,
        parametros: descreve_parametros(p),
    };
    for (indice, r) in resultados.iter().enumerate() {
        let rotulo_do_no: HashMap<i64, &String> = r.nos.iter().map(|n| (n.id, &n.rotulo)).collect();
        let mut grupos: Vec<&crate::pipeline::Grupo> = r.grupos.iter().collect();
        grupos.sort_by(|a, b| b.nos.len().cmp(&a.nos.len()).then_with(|| a.rotulo.cmp(&b.rotulo)));
        for (selo, g) in grupos.into_iter().enumerate() {
            mapa.nos.push(NoEvolucao {
                periodo: indice,
                selo: selo + 1,
                rotulo: g.exibicao.clone(),
                itens: g.nos.iter().copied().collect(),
                principal: g.principal,
                tamanho: g.nos.len(),
                nomes: g
                    .nos
                    .iter()
                    .map(|n| (*n, rotulo_do_no.get(n).map(|s| (*s).clone()).unwrap_or_else(|| n.to_string())))
                    .collect(),
            });
        }
    }

    for indice in 0..nomes.len().saturating_sub(1) {
        let origem = mapa.nos_do_periodo(indice);
        let destino = mapa.nos_do_periodo(indice + 1);
        let mut candidatos: Vec<Elo> = Vec::new();
        for &a in &origem {
            for &b in &destino {
                let peso = mede_conjuntos(medida, &mapa.nos[a].itens, &mapa.nos[b].itens);
                if peso > 0.0 {
                    candidatos.push(Elo { origem: a, destino: b, peso, principal_comum: mapa.nos[a].contem_principal(&mapa.nos[b]) });
                }
            }
        }
        candidatos.sort_by(|x, y| y.peso.total_cmp(&x.peso));
        let transicao = transicao(&mapa, indice, &origem, &destino, &candidatos);
        mapa.transicoes.push(transicao);
        let mut usados: HashMap<usize, usize> = HashMap::new();
        for elo in candidatos {
            let chave = mapa.nos[elo.origem].selo;
            if usados.get(&chave).copied().unwrap_or(0) >= limite_elos {
                continue;
            }
            *usados.entry(chave).or_insert(0) += 1;
            mapa.elos.push(elo);
        }
    }

    let conjuntos: Vec<BTreeSet<i64>> = (0..nomes.len())
        .map(|i| mapa.nos_do_periodo(i).iter().flat_map(|&n| mapa.nos[n].itens.iter().copied()).collect())
        .collect();
    mapa.sobreposicao = (0..nomes.len())
        .map(|i| (0..nomes.len()).map(|j| mede_conjuntos(medida, &conjuntos[i], &conjuntos[j])).collect())
        .collect();
    mapa
}

fn transicao(mapa: &Evolucao, indice: usize, origem: &[usize], destino: &[usize], candidatos: &[Elo]) -> Transicao {
    let mut melhor: HashMap<usize, &Elo> = HashMap::new();
    for elo in candidatos {
        melhor.entry(mapa.nos[elo.origem].selo).or_insert(elo);
    }
    let recebem: BTreeSet<usize> = candidatos.iter().map(|e| mapa.nos[e.destino].selo).collect();
    let mut continuam = Vec::new();
    for &i in origem {
        let no = &mapa.nos[i];
        let Some(elo) = melhor.get(&no.selo) else { continue };
        let dest = &mapa.nos[elo.destino];
        let mut comuns: Vec<&String> = no.itens.intersection(&dest.itens).filter_map(|i| no.nomes.get(i)).collect();
        comuns.sort();
        let n_comuns = no.itens.intersection(&dest.itens).count();
        continuam.push(Continua {
            de: no.rotulo.clone(),
            para: dest.rotulo.clone(),
            sobreposicao: arredonda(elo.peso, 4),
            itens_comuns: n_comuns,
            exemplos: comuns.into_iter().take(5).cloned().collect(),
            mesmo_no_principal: elo.principal_comum,
            fraca: n_comuns < 2 && !elo.principal_comum,
            itens_de: no.tamanho,
            itens_para: dest.tamanho,
        });
    }
    Transicao {
        de: mapa.periodos[indice].clone(),
        para: mapa.periodos[indice + 1].clone(),
        continuam,
        somem: origem.iter().filter(|&&i| !melhor.contains_key(&mapa.nos[i].selo)).map(|&i| mapa.nos[i].rotulo.clone()).collect(),
        surgem: destino.iter().filter(|&&i| !recebem.contains(&mapa.nos[i].selo)).map(|&i| mapa.nos[i].rotulo.clone()).collect(),
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn g6() {
        assert_eq!(formata_g(0.5, 6), "0.5");
        assert_eq!(formata_g(1.0, 6), "1");
        assert_eq!(formata_g(0.123456789, 6), "0.123457");
        assert_eq!(formata_g(1234567.0, 6), "1.23457e+06");
        assert_eq!(formata_g(0.00001234, 6), "1.234e-05");
        assert_eq!(formata_g(100000.0, 6), "100000");
    }

    #[test]
    fn conjuntos() {
        let a: BTreeSet<i64> = [1, 2, 3].into();
        let b: BTreeSet<i64> = [2, 3, 4, 5].into();
        assert!((mede_conjuntos(Similaridade::JaccardIndex, &a, &b) - 2.0 / 5.0).abs() < 1e-12);
    }
}
