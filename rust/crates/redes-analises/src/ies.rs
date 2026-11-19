//! Instituições (IES): nome da afiliação, aliases e unificação de variantes inequívocas
//! (porta de `ies.py` e dos trechos de `sugestoes.py` que ele usa).

use std::collections::{BTreeMap, BTreeSet};
use std::sync::OnceLock;

use indexmap::IndexMap;
use regex::Regex;
use rusqlite::Connection;
use serde::Serialize;

use crate::db::{existe_tabela, Erro};
use crate::paises::{pais as nome_de_pais, pais_da_afiliacao};
use crate::util::sem_acentos;

const LIGACOES: &[&str] = &["of", "the", "and", "for", "in", "on", "a", "an", "to", "with", "from", "by", "at", "as", "de", "da", "do", "das", "dos", "e", "y"];
const LIGACOES_IES_EXTRA: &[&str] = &["del", "di", "la", "le", "los", "las", "du", "des", "van", "von"];

fn equivalente(p: &str) -> &str {
    match p {
        "universidade" | "universidad" | "universite" | "universita" | "universitat" | "university" | "univ"
        | "universitaet" => "univ",
        "instituto" | "institute" | "institut" | "instituition" => "inst",
        "faculdade" | "facultad" | "faculty" => "fac",
        "college" => "college",
        _ => p,
    }
}

fn re_universidade() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"(?i)\b(univ\w*|college|hochschule|polit[eé]cnic\w*|polytechni\w*)\b").unwrap())
}

fn re_outras() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(
            r"(?i)\b(instit\w*|school|escola|faculd\w*|facult\w*|centro|center|centre|academ\w*|laborat\w*|hospital|ministr\w*|secretaria|foundation|funda[cç][aã]o|ecole|école|council|agency|association|embrapa|fiocruz|cnpq|capes|ufscar)\b",
        )
        .unwrap()
    })
}

/// Trecho da afiliação que nomeia a instituição ("Depto, Universidade X, Cidade, País").
pub fn instituicao_da_afiliacao(afiliacao: &str) -> String {
    let partes: Vec<&str> = afiliacao.split(',').map(|p| p.trim()).filter(|p| !p.is_empty()).collect();
    if partes.is_empty() {
        return String::new();
    }
    for padrao in [re_universidade(), re_outras()] {
        for p in &partes {
            if padrao.is_match(p) {
                return p.to_string();
            }
        }
    }
    partes[0].to_string()
}

fn re_parenteses() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"\([^)]*\)").unwrap())
}

pub fn tokens_ies(nome: &str) -> Vec<String> {
    let t = sem_acentos(nome).to_lowercase();
    let t = re_parenteses().replace_all(&t, " ").into_owned();
    let mut saida = Vec::new();
    for p in t.split(|c: char| !(c.is_ascii_lowercase() || c.is_ascii_digit())).filter(|p| !p.is_empty()) {
        let p = equivalente(p);
        if LIGACOES.contains(&p) || LIGACOES_IES_EXTRA.contains(&p) {
            continue;
        }
        saida.push(p.to_string());
    }
    saida
}

fn re_sufixo_pais() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"\s+[-–—/|]\s+([^-–—/|]+)$").unwrap())
}

/// Tira " - Brazil" do fim; devolve (nome, houve_sufixo).
fn sem_sufixo_de_pais(nome: &str) -> (String, bool) {
    if let Some(c) = re_sufixo_pais().captures(nome) {
        if !nome_de_pais(c.get(1).unwrap().as_str()).is_empty() {
            return (nome[..c.get(0).unwrap().start()].to_string(), true);
        }
    }
    (nome.to_string(), false)
}

/// Chave de comparação do nome de uma instituição (vazia = não comparável).
pub fn chave_ies(nome: &str) -> Vec<String> {
    let (limpo, _) = sem_sufixo_de_pais(nome.trim());
    tokens_ies(&limpo)
}

fn chave_texto(nome: &str) -> String {
    sem_acentos(nome).to_lowercase().replace('&', "and").chars().filter(|c| c.is_ascii_lowercase() || c.is_ascii_digit()).collect()
}

fn motivo(nome: &str, adotado: &str) -> String {
    if chave_texto(nome) == chave_texto(adotado) {
        return "caixa, acentos ou pontuação".into();
    }
    let mut motivos: Vec<&str> = Vec::new();
    let (sem, houve) = sem_sufixo_de_pais(nome);
    let (sem_ad, houve_ad) = sem_sufixo_de_pais(adotado);
    if houve != houve_ad {
        motivos.push("país no fim do nome");
    }
    let base = |s: &str| re_parenteses().replace_all(&sem_acentos(s).to_lowercase(), " ").into_owned();
    let (ba, bb) = (base(&sem), base(&sem_ad));
    if chave_texto(&ba) == chave_texto(&bb) {
        if motivos.is_empty() {
            motivos.push("sigla entre parênteses");
        }
    } else {
        let toks = |b: &str| -> Vec<String> {
            b.split(|c: char| !(c.is_ascii_lowercase() || c.is_ascii_digit()))
                .filter(|p| !p.is_empty())
                .filter(|p| !["de", "of", "the", "da", "do", "del"].contains(p))
                .map(String::from)
                .collect()
        };
        if toks(&ba) != toks(&bb) {
            motivos.push("Univ./University e termos equivalentes");
        } else {
            motivos.push("ligações (de/of/the)");
        }
    }
    motivos.join("; ")
}

#[derive(Clone, Debug, Serialize)]
pub struct Variante {
    pub nome: String,
    pub documentos: usize,
    pub motivo: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct Uniao {
    pub id: i64,
    pub adotado: String,
    pub documentos: usize,
    pub variantes: Vec<Variante>,
}

/// Instituições do projeto, já unificadas.
#[derive(Clone, Debug, Default, Serialize)]
pub struct IndiceIes {
    pub nomes: BTreeMap<i64, String>,
    pub por_documento: IndexMap<i64, Vec<i64>>,
    pub unioes: Vec<Uniao>,
}

impl IndiceIes {
    pub fn quantidade_variantes_unidas(&self) -> usize {
        self.unioes.iter().map(|u| u.variantes.len() - 1).sum()
    }
}

pub fn aliases_de_ies(c: &Connection) -> BTreeMap<String, String> {
    let mut m = BTreeMap::new();
    if !existe_tabela(c, "InstitutionAlias") {
        return m;
    }
    if let Ok(mut st) = c.prepare("SELECT instituicao, canonico FROM InstitutionAlias") {
        if let Ok(linhas) = st.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))) {
            for l in linhas.flatten() {
                m.insert(l.0, l.1);
            }
        }
    }
    m
}

/// (documento, nome da instituição, país) de cada afiliação de documento.
pub fn ocorrencias(c: &Connection) -> Result<Vec<(i64, String, String)>, Erro> {
    if !existe_tabela(c, "Affiliation") || !existe_tabela(c, "Document_Affiliation") {
        return Ok(vec![]);
    }
    let aliases = aliases_de_ies(c);
    let mut st = c
        .prepare(
            "SELECT da.Document_idDocument, a.fullAffiliation FROM Document_Affiliation da \
             JOIN Affiliation a ON a.idAffiliation = da.Affiliation_idAffiliation \
             ORDER BY da.Document_idDocument, a.idAffiliation",
        )
        .map_err(|e| e.to_string())?;
    let mut saida = Vec::new();
    let linhas = st
        .query_map([], |r| Ok((r.get::<_, i64>(0)?, r.get::<_, Option<String>>(1)?.unwrap_or_default())))
        .map_err(|e| e.to_string())?;
    for l in linhas {
        let (doc, afil) = l.map_err(|e| e.to_string())?;
        let nome = instituicao_da_afiliacao(&afil);
        if nome.is_empty() {
            continue;
        }
        let nome = aliases.get(&nome).cloned().unwrap_or(nome);
        saida.push((doc, nome.trim().to_string(), pais_da_afiliacao(&afil)));
    }
    Ok(saida)
}

fn adotado(variantes: &IndexMap<String, BTreeSet<i64>>) -> String {
    let mut v: Vec<(&String, &BTreeSet<i64>)> = variantes.iter().collect();
    v.sort_by(|a, b| {
        let pref = |n: &String, d: &BTreeSet<i64>| {
            (
                -(d.len() as i64),
                -(n.chars().filter(|c| (*c as u32) > 127).count() as i64),
                n.chars().filter(|c| c.is_uppercase()).count() as i64,
                -(n.chars().count() as i64),
                n.clone(),
            )
        };
        pref(a.0, a.1).cmp(&pref(b.0, b.1))
    });
    v[0].0.clone()
}

type Ocorrencia = (i64, String, String);

/// Une variantes inequívocas e devolve o índice (ids estáveis por nome).
pub fn unifica(ocs: &[Ocorrencia]) -> IndiceIes {
    let mut grupos: IndexMap<Vec<String>, Vec<Ocorrencia>> = IndexMap::new();
    for o in ocs {
        let mut ch = chave_ies(&o.1);
        if ch.is_empty() {
            ch = vec![format!("#{}", o.1)];
        }
        grupos.entry(ch).or_default().push(o.clone());
    }
    let mut clusters: IndexMap<(Vec<String>, String), Vec<Ocorrencia>> = IndexMap::new();
    for (ch, itens) in &grupos {
        let paises: Vec<&String> = {
            let mut s: Vec<&String> = Vec::new();
            for (_, _, p) in itens {
                if !p.is_empty() && !s.contains(&p) {
                    s.push(p);
                }
            }
            s
        };
        if paises.len() <= 1 {
            let p = paises.first().map(|s| (*s).clone()).unwrap_or_default();
            clusters.insert((ch.clone(), p), itens.clone());
            continue;
        }
        for item in itens {
            let destino = if !item.2.is_empty() {
                (ch.clone(), item.2.clone())
            } else {
                let mut c2 = ch.clone();
                c2.push(format!("@{}", item.1));
                (c2, String::new())
            };
            clusters.entry(destino).or_default().push(item.clone());
        }
    }
    let base_de = |ch: &Vec<String>| -> Vec<String> {
        if ch.last().map_or(false, |u| u.starts_with('@')) {
            ch[..ch.len() - 1].to_vec()
        } else {
            ch.clone()
        }
    };
    let mut partilhados: BTreeMap<Vec<String>, usize> = BTreeMap::new();
    for (ch, _) in clusters.keys() {
        *partilhados.entry(base_de(ch)).or_default() += 1;
    }
    struct Final {
        rotulo: String,
        itens: Vec<Ocorrencia>,
        variantes: IndexMap<String, BTreeSet<i64>>,
        adotado: String,
    }
    let mut finais: Vec<Final> = Vec::new();
    for ((ch, pais), itens) in &clusters {
        let mut variantes: IndexMap<String, BTreeSet<i64>> = IndexMap::new();
        for (doc, nome, _) in itens {
            variantes.entry(nome.clone()).or_default().insert(*doc);
        }
        let ad = adotado(&variantes);
        let rotulo = if !pais.is_empty() && partilhados.get(&base_de(ch)).copied().unwrap_or(1) > 1 {
            format!("{ad} ({pais})")
        } else {
            ad.clone()
        };
        finais.push(Final { rotulo, itens: itens.clone(), variantes, adotado: ad });
    }
    finais.sort_by(|a, b| {
        (sem_acentos(&a.rotulo).to_lowercase(), &a.rotulo).cmp(&(sem_acentos(&b.rotulo).to_lowercase(), &b.rotulo))
    });
    let mut indice = IndiceIes::default();
    for (k, f) in finais.iter().enumerate() {
        let numero = k as i64 + 1;
        indice.nomes.insert(numero, f.rotulo.clone());
        for (doc, _, _) in &f.itens {
            let l = indice.por_documento.entry(*doc).or_default();
            if !l.contains(&numero) {
                l.push(numero);
            }
        }
        if f.variantes.len() > 1 {
            let mut vs: Vec<(&String, &BTreeSet<i64>)> = f.variantes.iter().collect();
            vs.sort_by(|a, b| {
                ((a.0 != &f.adotado), -(a.1.len() as i64), a.0).cmp(&((b.0 != &f.adotado), -(b.1.len() as i64), b.0))
            });
            let docs: BTreeSet<i64> = f.itens.iter().map(|i| i.0).collect();
            indice.unioes.push(Uniao {
                id: numero,
                adotado: f.rotulo.clone(),
                documentos: docs.len(),
                variantes: vs
                    .into_iter()
                    .map(|(n, d)| Variante {
                        nome: n.clone(),
                        documentos: d.len(),
                        motivo: if n == &f.adotado { "nome adotado".into() } else { motivo(n, &f.adotado) },
                    })
                    .collect(),
            });
        }
    }
    indice.unioes.sort_by(|a, b| {
        (-(a.variantes.len() as i64), sem_acentos(&a.adotado).to_lowercase())
            .cmp(&(-(b.variantes.len() as i64), sem_acentos(&b.adotado).to_lowercase()))
    });
    indice
}

pub fn indice_de_ies(c: &Connection) -> Result<IndiceIes, Erro> {
    Ok(unifica(&ocorrencias(c)?))
}
