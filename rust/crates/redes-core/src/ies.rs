//! Rede de instituições (IES): nomes unificados (porta de `ies.py` e das partes
//! de `sugestoes.py` que ela usa). As variantes do mesmo nome são unidas só
//! quando a normalização é inequívoca (caixa, acento, pontuação, ligações,
//! Univ./University, sigla entre parênteses, país depois de hífen ou barra);
//! o mesmo nome em países diferentes não se une entre países.

use std::collections::{BTreeMap, BTreeSet, HashMap};

use indexmap::IndexMap;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};

use crate::paises::{pais, pais_da_afiliacao};
use crate::texto::{chave, sem_acentos};

pub const COMPONENTE_MINIMO_PADRAO: usize = 3;

const LIGACOES: &[&str] = &[
    "of", "the", "and", "for", "in", "on", "a", "an", "to", "with", "from", "by", "at", "as", "de", "da", "do", "das", "dos", "e", "y",
    "del", "di", "la", "le", "los", "las", "du", "des", "van", "von",
];

fn equivalente(p: &str) -> &str {
    match p {
        "universidade" | "universidad" | "universite" | "universita" | "universitat" | "university" | "univ" | "universitaet" => "univ",
        "instituto" | "institute" | "institut" | "instituition" => "inst",
        "faculdade" | "facultad" | "faculty" => "fac",
        "college" => "college",
        _ => p,
    }
}

fn e_palavra(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// Palavras (`\w+`) de um texto, em minúsculas.
fn palavras_minusculas(texto: &str) -> Vec<String> {
    let mut v = Vec::new();
    let mut atual = String::new();
    for c in texto.chars() {
        if e_palavra(c) {
            atual.extend(c.to_lowercase());
        } else if !atual.is_empty() {
            v.push(std::mem::take(&mut atual));
        }
    }
    if !atual.is_empty() {
        v.push(atual);
    }
    v
}

fn casa_universidade(p: &str) -> bool {
    p.starts_with("univ")
        || p == "college"
        || p == "hochschule"
        || p.starts_with("politecnic")
        || p.starts_with("polit\u{e9}cnic")
        || p.starts_with("polytechni")
}

fn casa_outras(p: &str) -> bool {
    p.starts_with("instit")
        || p == "school"
        || p == "escola"
        || p.starts_with("faculd")
        || p.starts_with("facult")
        || matches!(p, "centro" | "center" | "centre")
        || p.starts_with("academ")
        || p.starts_with("laborat")
        || p == "hospital"
        || p.starts_with("ministr")
        || matches!(p, "secretaria" | "foundation" | "fundacao" | "funda\u{e7}\u{e3}o" | "funda\u{e7}ao" | "fundac\u{e3}o")
        || matches!(p, "ecole" | "\u{e9}cole" | "council" | "agency" | "association" | "embrapa" | "fiocruz" | "cnpq" | "capes" | "ufscar")
}

/// Trecho da afiliação que nomeia a instituição ("Depto, Universidade X, Cidade, País").
pub fn instituicao_da_afiliacao(afiliacao: &str) -> String {
    let partes: Vec<&str> = afiliacao.split(',').map(|p| p.trim()).filter(|p| !p.is_empty()).collect();
    if partes.is_empty() {
        return String::new();
    }
    for padrao in [casa_universidade as fn(&str) -> bool, casa_outras] {
        for parte in &partes {
            if palavras_minusculas(parte).iter().any(|p| padrao(p)) {
                return parte.to_string();
            }
        }
    }
    partes[0].to_string()
}

/// `re.sub(r"\([^)]*\)", " ", texto)`.
fn sem_parenteses(texto: &str) -> String {
    let cs: Vec<char> = texto.chars().collect();
    let mut s = String::new();
    let mut i = 0;
    while i < cs.len() {
        if cs[i] == '(' {
            if let Some(f) = cs[i + 1..].iter().position(|&c| c == ')') {
                s.push(' ');
                i += f + 2;
                continue;
            }
        }
        s.push(cs[i]);
        i += 1;
    }
    s
}

fn palavras_az09(texto: &str) -> Vec<String> {
    texto.split(|c: char| !(c.is_ascii_lowercase() || c.is_ascii_digit())).filter(|p| !p.is_empty()).map(|p| p.to_string()).collect()
}

pub fn tokens_ies(nome: &str) -> Vec<String> {
    let texto = sem_parenteses(&sem_acentos(nome).to_lowercase());
    palavras_az09(&texto)
        .into_iter()
        .map(|p| equivalente(&p).to_string())
        .filter(|p| !LIGACOES.contains(&p.as_str()))
        .collect()
}

const SEPS_PAIS: &[char] = &['-', '\u{2013}', '\u{2014}', '/', '|'];

/// Tira " - Brazil" do fim; devolve (nome, houve_sufixo).
fn sem_sufixo_de_pais(nome: &str) -> (&str, bool) {
    if let Some(idx) = nome.rfind(SEPS_PAIS) {
        let sep = nome[idx..].chars().next().unwrap();
        let antes = &nome[..idx];
        let depois = &nome[idx + sep.len_utf8()..];
        if antes.chars().next_back().is_some_and(|c| c.is_whitespace())
            && depois.chars().next().is_some_and(|c| c.is_whitespace())
            && !pais(depois).is_empty()
        {
            return (antes.trim_end(), true);
        }
    }
    (nome, false)
}

/// Chave de comparação do nome de uma instituição (vazia = não comparável).
pub fn chave_ies(nome: &str) -> Vec<String> {
    let (limpo, _) = sem_sufixo_de_pais(nome.trim());
    tokens_ies(limpo)
}

fn motivo(nome: &str, adotado: &str) -> String {
    if chave(nome) == chave(adotado) {
        return "caixa, acentos ou pontuação".into();
    }
    let mut motivos: Vec<&str> = Vec::new();
    let (sem, houve) = sem_sufixo_de_pais(nome);
    let (sem_ad, houve_ad) = sem_sufixo_de_pais(adotado);
    if houve != houve_ad {
        motivos.push("país no fim do nome");
    }
    let base_a = sem_parenteses(&sem_acentos(sem).to_lowercase());
    let base_b = sem_parenteses(&sem_acentos(sem_ad).to_lowercase());
    if chave(&base_a) == chave(&base_b) {
        if motivos.is_empty() {
            motivos.push("sigla entre parênteses");
        }
    } else {
        let lig = |v: Vec<String>| -> Vec<String> {
            v.into_iter().filter(|p| !matches!(p.as_str(), "de" | "of" | "the" | "da" | "do" | "del")).collect()
        };
        if lig(palavras_az09(&base_a)) != lig(palavras_az09(&base_b)) {
            motivos.push("Univ./University e termos equivalentes");
        } else {
            motivos.push("ligações (de/of/the)");
        }
    }
    motivos.join("; ")
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Variante {
    pub nome: String,
    pub documentos: usize,
    pub motivo: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Uniao {
    pub id: i64,
    pub adotado: String,
    pub documentos: usize,
    pub variantes: Vec<Variante>,
}

/// Instituições do projeto, já unificadas.
#[derive(Clone, Debug, Default)]
pub struct IndiceIes {
    pub nomes: BTreeMap<i64, String>,
    pub por_documento: HashMap<i64, Vec<i64>>,
    pub unioes: Vec<Uniao>,
}

impl IndiceIes {
    /// Quantas grafias deixaram de existir por causa das uniões.
    pub fn quantidade_variantes_unidas(&self) -> usize {
        self.unioes.iter().map(|u| u.variantes.len() - 1).sum()
    }
}

type Ocorrencia = (i64, String, String);

fn aliases(conexao: &Connection) -> HashMap<String, String> {
    let mut m = HashMap::new();
    let existe: bool = conexao
        .query_row("SELECT 1 FROM sqlite_master WHERE type='table' AND name='InstitutionAlias'", [], |_| Ok(()))
        .is_ok();
    if !existe {
        return m;
    }
    if let Ok(mut st) = conexao.prepare("SELECT instituicao, canonico FROM InstitutionAlias") {
        if let Ok(linhas) = st.query_map([], |r| Ok((r.get::<_, String>(0)?, r.get::<_, String>(1)?))) {
            for l in linhas.flatten() {
                m.insert(l.0, l.1);
            }
        }
    }
    m
}

/// (documento, nome da instituição, país) de cada afiliação de documento.
fn ocorrencias(conexao: &Connection) -> rusqlite::Result<Vec<Ocorrencia>> {
    let al = aliases(conexao);
    let tabelas: BTreeSet<String> = {
        let mut st = conexao.prepare("SELECT name FROM sqlite_master WHERE type='table'")?;
        let v = st.query_map([], |r| r.get::<_, String>(0))?.collect::<Result<_, _>>()?;
        v
    };
    if !(tabelas.contains("Affiliation") && tabelas.contains("Document_Affiliation")) {
        return Ok(Vec::new());
    }
    let mut st = conexao.prepare(
        "SELECT da.Document_idDocument, a.fullAffiliation FROM Document_Affiliation da \
         JOIN Affiliation a ON a.idAffiliation = da.Affiliation_idAffiliation \
         ORDER BY da.Document_idDocument, a.idAffiliation",
    )?;
    let linhas = st.query_map([], |r| Ok((r.get::<_, i64>(0)?, r.get::<_, Option<String>>(1)?.unwrap_or_default())))?;
    let mut saida = Vec::new();
    for l in linhas {
        let (doc, afiliacao) = l?;
        let nome = instituicao_da_afiliacao(&afiliacao);
        if nome.is_empty() {
            continue;
        }
        let nome = al.get(&nome).cloned().unwrap_or(nome);
        saida.push((doc, nome.trim().to_string(), pais_da_afiliacao(&afiliacao).to_string()));
    }
    Ok(saida)
}

/// Grafia adotada: a mais usada; no empate, a com acentos, com menos maiúsculas e a mais completa.
fn adotado(variantes: &IndexMap<String, BTreeSet<i64>>) -> String {
    let mut v: Vec<(&String, &BTreeSet<i64>)> = variantes.iter().collect();
    v.sort_by_key(|(nome, docs)| {
        let acentuados = nome.chars().filter(|&c| c as u32 > 127).count() as i64;
        let maiusculas = nome.chars().filter(|c| c.is_uppercase()).count() as i64;
        (-(docs.len() as i64), -acentuados, maiusculas, -(nome.chars().count() as i64), (*nome).clone())
    });
    v[0].0.clone()
}

fn base_da_chave(chave_grupo: &[String]) -> Vec<String> {
    match chave_grupo.last() {
        Some(u) if u.starts_with('@') => chave_grupo[..chave_grupo.len() - 1].to_vec(),
        _ => chave_grupo.to_vec(),
    }
}

/// Une variantes inequívocas e devolve o índice (ids estáveis por nome).
pub fn unifica(ocs: Vec<Ocorrencia>) -> IndiceIes {
    let mut grupos: IndexMap<Vec<String>, Vec<Ocorrencia>> = IndexMap::new();
    for o in ocs {
        let mut k = chave_ies(&o.1);
        if k.is_empty() {
            k = vec![format!("#{}", o.1)];
        }
        grupos.entry(k).or_default().push(o);
    }

    let mut clusters: IndexMap<(Vec<String>, String), Vec<Ocorrencia>> = IndexMap::new();
    for (chave_grupo, itens) in grupos {
        let paises: BTreeSet<&String> = itens.iter().map(|i| &i.2).filter(|p| !p.is_empty()).collect();
        if paises.len() <= 1 {
            let p = paises.iter().next().map(|s| (*s).clone()).unwrap_or_default();
            clusters.insert((chave_grupo, p), itens);
            continue;
        }
        for item in itens {
            let destino = if !item.2.is_empty() {
                (chave_grupo.clone(), item.2.clone())
            } else {
                let mut k = chave_grupo.clone();
                k.push(format!("@{}", item.1));
                (k, String::new())
            };
            clusters.entry(destino).or_default().push(item);
        }
    }

    let mut partilhados: HashMap<Vec<String>, usize> = HashMap::new();
    for (chave_grupo, _) in clusters.keys() {
        *partilhados.entry(base_da_chave(chave_grupo)).or_insert(0) += 1;
    }

    struct Final {
        rotulo: String,
        itens: Vec<Ocorrencia>,
        variantes: IndexMap<String, BTreeSet<i64>>,
        adotado: String,
    }
    let mut finais: Vec<Final> = Vec::new();
    for ((chave_grupo, pais_c), itens) in clusters {
        let mut variantes: IndexMap<String, BTreeSet<i64>> = IndexMap::new();
        for (doc, nome, _) in &itens {
            variantes.entry(nome.clone()).or_default().insert(*doc);
        }
        let ad = adotado(&variantes);
        let base = base_da_chave(&chave_grupo);
        let rotulo = if !pais_c.is_empty() && partilhados.get(&base).copied().unwrap_or(1) > 1 {
            format!("{ad} ({pais_c})")
        } else {
            ad.clone()
        };
        finais.push(Final { rotulo, itens, variantes, adotado: ad });
    }
    finais.sort_by(|a, b| {
        (sem_acentos(&a.rotulo).to_lowercase(), &a.rotulo).cmp(&(sem_acentos(&b.rotulo).to_lowercase(), &b.rotulo))
    });

    let mut indice = IndiceIes::default();
    for (i, f) in finais.into_iter().enumerate() {
        let numero = i as i64 + 1;
        indice.nomes.insert(numero, f.rotulo.clone());
        for (doc, _, _) in &f.itens {
            let lista = indice.por_documento.entry(*doc).or_default();
            if !lista.contains(&numero) {
                lista.push(numero);
            }
        }
        if f.variantes.len() > 1 {
            let docs: BTreeSet<i64> = f.itens.iter().map(|o| o.0).collect();
            let mut vs: Vec<(&String, &BTreeSet<i64>)> = f.variantes.iter().collect();
            vs.sort_by(|a, b| {
                ((a.0 != &f.adotado), -(a.1.len() as i64), a.0).cmp(&((b.0 != &f.adotado), -(b.1.len() as i64), b.0))
            });
            indice.unioes.push(Uniao {
                id: numero,
                adotado: f.rotulo.clone(),
                documentos: docs.len(),
                variantes: vs
                    .into_iter()
                    .map(|(nome, docs)| Variante {
                        nome: nome.clone(),
                        documentos: docs.len(),
                        motivo: if nome == &f.adotado { "nome adotado".into() } else { motivo(nome, &f.adotado) },
                    })
                    .collect(),
            });
        }
    }
    indice
        .unioes
        .sort_by(|a, b| (-(a.variantes.len() as i64), sem_acentos(&a.adotado).to_lowercase()).cmp(&(-(b.variantes.len() as i64), sem_acentos(&b.adotado).to_lowercase())));
    indice
}

pub fn indice_de_ies(conexao: &Connection) -> rusqlite::Result<IndiceIes> {
    Ok(unifica(ocorrencias(conexao)?))
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn tokens() {
        assert_eq!(tokens_ies("Universidade de São Paulo (USP)"), vec!["univ", "sao", "paulo"]);
        assert_eq!(chave_ies("Univ. de Sao Paulo - Brazil"), vec!["univ", "sao", "paulo"]);
    }

    #[test]
    fn instituicao() {
        assert_eq!(
            instituicao_da_afiliacao("Depto de Estatistica, Universidade Federal de X, Cidade, Brasil"),
            "Universidade Federal de X"
        );
        assert_eq!(instituicao_da_afiliacao("Embrapa Solos, Rio, Brasil"), "Embrapa Solos");
    }
}
