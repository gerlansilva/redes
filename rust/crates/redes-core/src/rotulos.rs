//! Rótulos de agrupamentos por termos distintivos (porta de `rotulos.py`):
//! razão de verossimilhança de Dunning (LLR) entre os documentos do núcleo do
//! agrupamento e os demais do período. Só para Words e References; nas demais
//! unidades o rótulo é o nome do líder do agrupamento.

use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};

use serde::{Deserialize, Serialize};

use crate::erro::Resultado;
use crate::projeto::Projeto;
use crate::pycompat::py_sum;
use crate::tabelas::{ACADEMICAS, PALAVRAS_DE_RESUMO, VAZIAS};
use crate::texto::{mesmo_termo, sem_acentos, NOMES_PROPRIOS, SIGLAS};

pub const MINIMO_DOCUMENTOS: usize = 5;
pub const LIMITE_INDICATIVO: usize = 10;
pub const COBERTURA_MAXIMA: f64 = 0.70;
pub const MINIMO_NO_GRUPO: usize = 2;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct RotuloTema {
    pub termos: Vec<String>,
    /// Termos unidos por " · ".
    pub rotulo: String,
    /// Rótulo com inicial maiúscula e siglas restauradas.
    pub exibicao: String,
    /// Menos de 10 documentos: o rótulo é só indicativo.
    pub indicativo: bool,
    pub documentos: usize,
}

fn normaliza(p: &str) -> String {
    sem_acentos(p).to_lowercase()
}

fn e_letra(c: char) -> bool {
    c.is_alphabetic()
}

/// Palavras do título; `None` marca onde havia uma palavra descartada.
pub fn quebra_titulo(titulo: &str, tirar_academicas: bool, ocultar: &HashSet<String>) -> Vec<Option<String>> {
    let cs: Vec<char> = titulo.chars().collect();
    let mut saida = Vec::new();
    let mut i = 0;
    while i < cs.len() {
        if !e_letra(cs[i]) {
            i += 1;
            continue;
        }
        let ini = i;
        while i < cs.len() && e_letra(cs[i]) {
            i += 1;
        }
        // (?:['’\-][^\W\d_]+)*
        loop {
            if i + 1 < cs.len() && matches!(cs[i], '\'' | '\u{2019}' | '-') && e_letra(cs[i + 1]) {
                i += 1;
                while i < cs.len() && e_letra(cs[i]) {
                    i += 1;
                }
            } else {
                break;
            }
        }
        let mut palavra: String = cs[ini..i].iter().collect();
        // re.sub(r"['’]s$", "", palavra)
        for suf in ["'s", "\u{2019}s"] {
            if let Some(r) = palavra.strip_suffix(suf) {
                palavra = r.to_string();
                break;
            }
        }
        let base = normaliza(&palavra.replace('\u{2019}', "'"));
        if base.chars().count() < 3
            || VAZIAS.binary_search(&base.as_str()).is_ok()
            || ocultar.contains(&base)
            || (tirar_academicas && ACADEMICAS.binary_search(&base.as_str()).is_ok())
        {
            saida.push(None);
        } else {
            saida.push(Some(palavra.to_lowercase()));
        }
    }
    saida
}

fn igual_sem_caixa(c: char, p: char) -> bool {
    c == p || c.to_lowercase().eq(p.to_lowercase())
}

/// `_COPYRIGHT.sub("", texto)`: corta do primeiro marcador de direitos autorais ao fim.
fn sem_copyright(texto: &str) -> String {
    const MARCAS: [&str; 5] = ["©", "(c)", "copyright", "all rights reserved", "published by"];
    let cs: Vec<char> = texto.chars().collect();
    for i in 0..cs.len() {
        for m in MARCAS {
            let mc: Vec<char> = m.chars().collect();
            if i + mc.len() <= cs.len() && cs[i..i + mc.len()].iter().zip(&mc).all(|(&c, &p)| igual_sem_caixa(c, p)) {
                return cs[..i].iter().collect();
            }
        }
    }
    texto.to_string()
}

fn canonico(uni: &HashMap<String, usize>) -> HashMap<String, String> {
    let mut baldes: HashMap<String, Vec<&String>> = HashMap::new();
    for t in uni.keys() {
        let k: String = normaliza(t).chars().take(4).collect();
        baldes.entry(k).or_default().push(t);
    }
    let mut destino = HashMap::new();
    for (_, mut ts) in baldes {
        ts.sort_by(|a, b| uni[*b].cmp(&uni[*a]).then_with(|| a.cmp(b)));
        let mut reps: Vec<&String> = Vec::new();
        for t in ts {
            let achou = reps.iter().find(|r| mesmo_termo(&t.to_uppercase(), &r.to_uppercase()));
            match achou {
                Some(r) => {
                    destino.insert(t.clone(), (*r).clone());
                }
                None => {
                    reps.push(t);
                    destino.insert(t.clone(), t.clone());
                }
            }
        }
    }
    destino
}

/// Termos por documento e frequência de documentos de cada termo.
pub struct Corpus {
    pub canonico: HashMap<String, String>,
    pub termos: HashMap<i64, BTreeSet<String>>,
    pub df: HashMap<String, usize>,
    pub n: usize,
}

impl Corpus {
    pub fn novo(projeto: &Projeto, ids: &[i64]) -> Resultado<Corpus> {
        let mut vistos = HashSet::new();
        let ids: Vec<i64> = ids.iter().copied().filter(|i| vistos.insert(*i)).collect();
        let textos = projeto.textos_documentos(&ids)?;
        let kws_brutos = projeto.palavras_chave_autor().unwrap_or_default();
        let mut kws: HashMap<i64, BTreeSet<String>> = HashMap::new();
        for (doc, nome) in kws_brutos {
            if textos.contains_key(&doc) && !nome.is_empty() {
                let legivel = nome.replace('-', " ").to_lowercase().split_whitespace().collect::<Vec<_>>().join(" ");
                if !legivel.is_empty() {
                    kws.entry(doc).or_default().insert(legivel);
                }
            }
        }
        let ocultar: HashSet<String> = PALAVRAS_DE_RESUMO.iter().map(|s| s.to_string()).collect();
        let mut pedacos: BTreeMap<i64, (Vec<Option<String>>, Vec<Option<String>>)> = BTreeMap::new();
        let mut uni: HashMap<String, usize> = HashMap::new();
        for (doc, (titulo, resumo)) in &textos {
            let resumo = sem_copyright(resumo);
            let pt = quebra_titulo(titulo, true, &ocultar);
            let pa = if resumo.trim().is_empty() { vec![] } else { quebra_titulo(&resumo, true, &ocultar) };
            let distintos: HashSet<&String> = pt.iter().chain(pa.iter()).flatten().collect();
            for p in distintos {
                *uni.entry(p.clone()).or_insert(0) += 1;
            }
            pedacos.insert(*doc, (pt, pa));
        }
        let canon = canonico(&uni);
        let mut termos: HashMap<i64, BTreeSet<String>> = HashMap::new();
        for (doc, (pt, pa)) in &pedacos {
            let mut conjunto: BTreeSet<String> = BTreeSet::new();
            for (k, lista) in [pt, pa].into_iter().enumerate() {
                let ped: Vec<Option<&String>> =
                    lista.iter().map(|p| p.as_ref().map(|p| canon.get(p).unwrap_or(p))).collect();
                if k == 0 {
                    conjunto.extend(ped.iter().flatten().map(|s| s.to_string()));
                }
                for par in ped.windows(2) {
                    if let (Some(a), Some(b)) = (par[0], par[1]) {
                        conjunto.insert(format!("{a} {b}"));
                    }
                }
            }
            if let Some(k) = kws.get(doc) {
                conjunto.extend(k.iter().cloned());
            }
            if !conjunto.is_empty() {
                termos.insert(*doc, conjunto);
            }
        }
        let mut df: HashMap<String, usize> = HashMap::new();
        for c in termos.values() {
            for t in c {
                *df.entry(t.clone()).or_insert(0) += 1;
            }
        }
        let n = termos.len();
        Ok(Corpus { canonico: canon, termos, df, n })
    }

    fn chave(&self, termo: &str) -> BTreeSet<String> {
        termo.split_whitespace().map(|w| normaliza(self.canonico.get(w).map(|s| s.as_str()).unwrap_or(w))).collect()
    }
}

fn xlx(x: f64) -> f64 {
    if x > 0.0 {
        x * x.ln()
    } else {
        0.0
    }
}

/// Razão de verossimilhança de Dunning (G²) da tabela 2x2.
pub fn llr(a: usize, n_grupo: usize, b: usize, n_resto: usize) -> f64 {
    let k = [a, n_grupo - a, b, n_resto - b];
    let n: usize = k.iter().sum();
    let (lin1, lin2, col1, col2) = (n_grupo, n_resto, a + b, n - a - b);
    2.0 * (py_sum(k.iter().map(|&x| xlx(x as f64))) + xlx(n as f64)
        - xlx(lin1 as f64)
        - xlx(lin2 as f64)
        - xlx(col1 as f64)
        - xlx(col2 as f64))
}

fn ranking(corpus: &Corpus, docs: &BTreeSet<i64>) -> Vec<(String, f64)> {
    let mut cont: HashMap<&String, usize> = HashMap::new();
    for d in docs {
        for t in &corpus.termos[d] {
            *cont.entry(t).or_insert(0) += 1;
        }
    }
    let nc = docs.len();
    let nr = corpus.n.saturating_sub(nc);
    if nc == 0 || nr == 0 {
        return vec![];
    }
    let mut pontos = Vec::new();
    for (t, a) in cont {
        if a < MINIMO_NO_GRUPO {
            continue;
        }
        let b = corpus.df[t] - a;
        if a as f64 / nc as f64 <= b as f64 / nr as f64 {
            continue;
        }
        pontos.push((t.clone(), llr(a, nc, b, nr)));
    }
    pontos.sort_by(|x, y| y.1.total_cmp(&x.1).then_with(|| x.0.cmp(&y.0)));
    pontos
}

/// Os k melhores sem repetir ideia (um termo contido em outro é descartado).
fn escolhe(corpus: &Corpus, ranking: &[(String, f64)], k: usize) -> Vec<String> {
    let mut escolhidos = Vec::new();
    let mut chaves: Vec<BTreeSet<String>> = Vec::new();
    for (t, pontos) in ranking {
        if *pontos <= 0.0 {
            break;
        }
        let c = corpus.chave(t);
        if chaves.iter().any(|x| c.is_subset(x) || x.is_subset(&c)) {
            continue;
        }
        escolhidos.push(t.clone());
        chaves.push(c);
        if escolhidos.len() == k {
            break;
        }
    }
    escolhidos
}

const SIGLAS_AMBIGUAS: &[&str] = &["STEM", "STEAM", "TIC", "TICS", "EJA"];

/// `termo_de_rotulo`: inicial maiúscula e siglas conhecidas restauradas.
pub fn termo_de_rotulo(termo: &str) -> String {
    let texto = termo.split_whitespace().collect::<Vec<_>>().join(" ");
    if texto.is_empty() {
        return String::new();
    }
    let cs: Vec<char> = texto.chars().collect();
    let mut saida = String::new();
    let mut i = 0;
    while i < cs.len() {
        if e_letra(cs[i]) {
            let ini = i;
            while i < cs.len() && e_letra(cs[i]) {
                i += 1;
            }
            let p: String = cs[ini..i].iter().collect();
            let maiuscula = p.to_uppercase();
            if let Some((_, v)) = NOMES_PROPRIOS.iter().find(|(k, _)| *k == maiuscula) {
                saida.push_str(v);
            } else if SIGLAS.contains(&maiuscula.as_str()) && !SIGLAS_AMBIGUAS.contains(&maiuscula.as_str()) {
                saida.push_str(&maiuscula);
            } else {
                saida.push_str(&p);
            }
        } else {
            saida.push(cs[i]);
            i += 1;
        }
    }
    let cs: Vec<char> = saida.chars().collect();
    for (i, &c) in cs.iter().enumerate() {
        if c.is_alphabetic() {
            let mut s: String = cs[..i].iter().collect();
            s.extend(c.to_uppercase());
            s.extend(cs[i + 1..].iter());
            return s;
        }
        if !c.is_numeric() && !"-'\"(".contains(c) {
            break;
        }
    }
    saida
}

/// `termo_de_rotulo` em cada termo de um rótulo "termo · termo · termo".
pub fn rotulo_legivel(texto: &str) -> String {
    texto.split(" · ").map(termo_de_rotulo).collect::<Vec<_>>().join(" · ")
}

/// Rótulo por termos distintivos: `docs_por_grupo[i]` são os documentos do núcleo do grupo `i`;
/// `universo` são os documentos do período. Chave do resultado = índice do grupo; grupos sem
/// base suficiente ficam de fora.
pub fn rotula_grupos(
    projeto: &Projeto,
    universo: &[i64],
    docs_por_grupo: &[BTreeSet<i64>],
    n_termos: usize,
    minimo_documentos: usize,
) -> Resultado<BTreeMap<usize, RotuloTema>> {
    let mut saida = BTreeMap::new();
    if universo.is_empty() || docs_por_grupo.is_empty() || n_termos < 1 {
        return Ok(saida);
    }
    let corpus = Corpus::novo(projeto, universo)?;
    if corpus.n == 0 {
        return Ok(saida);
    }
    for (indice, docs) in docs_por_grupo.iter().enumerate() {
        let docs: BTreeSet<i64> = docs.iter().copied().filter(|d| corpus.termos.contains_key(d)).collect();
        let n = docs.len();
        if n < minimo_documentos || n < 1 {
            continue;
        }
        if n as f64 / corpus.n as f64 > COBERTURA_MAXIMA {
            continue;
        }
        let escolhidos = escolhe(&corpus, &ranking(&corpus, &docs), n_termos);
        if escolhidos.is_empty() {
            continue;
        }
        let rotulo = escolhidos.join(" · ");
        saida.insert(
            indice,
            RotuloTema { exibicao: rotulo_legivel(&rotulo), termos: escolhidos, rotulo, indicativo: n < LIMITE_INDICATIVO, documentos: n },
        );
    }
    Ok(saida)
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn titulo() {
        let o = HashSet::new();
        let v = quebra_titulo("Teaching of statistics in children's schools", true, &o);
        assert_eq!(
            v,
            vec![Some("teaching".into()), None, Some("statistics".into()), None, Some("children".into()), Some("schools".into())]
        );
    }

    #[test]
    fn rotulo() {
        assert_eq!(rotulo_legivel("pisa results · statistical thinking"), "PISA results · Statistical thinking");
    }

    #[test]
    fn g2() {
        assert!(llr(10, 20, 5, 100) > 0.0);
    }
}
