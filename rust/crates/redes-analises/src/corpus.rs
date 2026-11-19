//! Corpus completo: o conjunto documento x item de **todos** os documentos do projeto (sem criar
//! período) e o fluxo de análise de co-ocorrência sobre ele (rede, normalização e
//! agrupamento). Base da linha do tempo e do mapa de densidade (porta de
//! `linha_do_tempo._TodosOsDocumentos` e do trecho relevante de `pipeline.executa_periodo`).

use std::collections::{BTreeMap, HashMap};

use redes_core::dataset::Dataset;
use redes_core::parametros::{Matriz, Parametros, Unidade};
use redes_core::rede::{normaliza, rede_coocorrencia, Rede};
use redes_core::texto::{chave, exibe_termo, termo_legivel};
use rusqlite::Connection;

use crate::db::{existe_tabela, Erro};
use crate::ies;

const SQL_PALAVRAS: &str = "SELECT w.WordGroup_idWordGroup, dw.isAuthorWord, dw.isSourceWord, dw.isAddedWord \
     FROM Document_Word dw, Word w WHERE dw.Document_idDocument = ? AND dw.Word_idWord = w.idWord;";
const SQL_AUTORES: &str = "SELECT a.AuthorGroup_idAuthorGroup FROM Document_Author da, Author a \
     WHERE da.Document_idDocument = ? AND da.Author_idAuthor = a.idAuthor ORDER BY da.position ASC;";
const SQL_REFERENCIAS: &str = "SELECT r.idReference, r.ReferenceGroup_idReferenceGroup, r.ReferenceSource_idReferenceSource \
     FROM Document_Reference dr, Reference r \
     WHERE dr.Document_idDocument = ? AND dr.Reference_idReference = r.idReference;";
const SQL_AUTORES_REFERENCIA: &str = "SELECT ar.AuthorReferenceGroup_idAuthorReferenceGroup \
     FROM AuthorReference_Reference arr, AuthorReference ar, Reference r \
     WHERE r.idReference = ? AND r.idReference = arr.Reference_idReference \
     AND arr.AuthorReference_idAuthorReference = ar.idAuthorReference;";
const SQL_PAISES: &str = "SELECT c.CountryGroup_idCountryGroup FROM Document_Country dc, Country c \
     WHERE dc.Document_idDocument = ? AND dc.Country_idCountry = c.idCountry;";

struct Grupos<'a> {
    c: &'a Connection,
    cache: HashMap<&'static str, HashMap<i64, (String, bool)>>,
}

impl<'a> Grupos<'a> {
    fn get(&mut self, tabela: &'static str, coluna: &str, id: i64) -> Result<Option<(String, bool)>, Erro> {
        if !self.cache.contains_key(tabela) {
            let mut m = HashMap::new();
            let mut st = self
                .c
                .prepare(&format!("SELECT {coluna}, groupName, stopGroup FROM {tabela};"))
                .map_err(|e| e.to_string())?;
            let linhas = st
                .query_map([], |r| {
                    Ok((
                        r.get::<_, i64>(0)?,
                        r.get::<_, Option<String>>(1)?.unwrap_or_default(),
                        r.get::<_, Option<i64>>(2)?.unwrap_or(0) != 0,
                    ))
                })
                .map_err(|e| e.to_string())?;
            for l in linhas {
                let (i, n, s) = l.map_err(|e| e.to_string())?;
                m.insert(i, (n, s));
            }
            self.cache.insert(tabela, m);
        }
        Ok(self.cache[tabela].get(&id).cloned())
    }

    fn adiciona(&mut self, ds: &mut Dataset, doc: i64, tabela: &'static str, coluna: &str, g: Option<i64>) -> Result<(), Erro> {
        let Some(g) = g else { return Ok(()) };
        if let Some((nome, parada)) = self.get(tabela, coluna, g)? {
            if !parada {
                ds.adiciona_item_ao_documento(doc, g, &nome);
            }
        }
        Ok(())
    }
}

fn col_i64(c: &Connection, sql: &str, doc: i64) -> Result<Vec<Option<i64>>, Erro> {
    let mut st = c.prepare_cached(sql).map_err(|e| e.to_string())?;
    let v = st.query_map([doc], |r| r.get::<_, Option<i64>>(0)).map_err(|e| e.to_string())?.collect::<Result<Vec<_>, _>>();
    v.map_err(|e| e.to_string())
}

/// Conjunto documento x item de todos os documentos do projeto.
pub fn dataset_corpus(c: &Connection, unidade: Unidade, palavras: &[String]) -> Result<Dataset, Erro> {
    let mut ds = Dataset::default();
    let mut grupos = Grupos { c, cache: HashMap::new() };
    let ies_ix = if unidade == Unidade::Institutions { Some(ies::indice_de_ies(c)?) } else { None };
    // documentos: por PublishDate (em ordem) e, no fim, os sem data
    let mut docs: Vec<(i64, i64)> = Vec::new();
    let mut vistos = std::collections::HashSet::new();
    {
        let mut st = c.prepare("SELECT idPublishDate FROM PublishDate ORDER BY idPublishDate").map_err(|e| e.to_string())?;
        let datas: Vec<i64> = st.query_map([], |r| r.get(0)).map_err(|e| e.to_string())?.collect::<Result<_, _>>().map_err(|e: rusqlite::Error| e.to_string())?;
        let mut sd = c
            .prepare(
                "SELECT d.idDocument, d.citationsCount FROM Document d, PublishDate p \
                 WHERE p.idPublishDate = ? AND p.idPublishDate = d.PublishDate_idPublishDate;",
            )
            .map_err(|e| e.to_string())?;
        for d in datas {
            let linhas: Vec<(i64, i64)> = sd
                .query_map([d], |r| Ok((r.get(0)?, r.get::<_, Option<i64>>(1)?.unwrap_or(0))))
                .map_err(|e| e.to_string())?
                .collect::<Result<_, _>>()
                .map_err(|e: rusqlite::Error| e.to_string())?;
            for l in linhas {
                if vistos.insert(l.0) {
                    docs.push(l);
                }
            }
        }
        let mut sn = c
            .prepare("SELECT idDocument, citationsCount FROM Document WHERE PublishDate_idPublishDate IS NULL ORDER BY idDocument")
            .map_err(|e| e.to_string())?;
        let linhas: Vec<(i64, i64)> = sn
            .query_map([], |r| Ok((r.get(0)?, r.get::<_, Option<i64>>(1)?.unwrap_or(0))))
            .map_err(|e| e.to_string())?
            .collect::<Result<_, _>>()
            .map_err(|e: rusqlite::Error| e.to_string())?;
        for l in linhas {
            if vistos.insert(l.0) {
                docs.push(l);
            }
        }
    }
    let tem_paises = existe_tabela(c, "Country") && existe_tabela(c, "Document_Country");
    for (doc, cit) in docs {
        ds.adiciona_documento(doc, cit);
        match unidade {
            Unidade::Words => {
                let idx = |o: &str| match o {
                    "autor" => Some(1usize),
                    "fonte" => Some(2),
                    "adicionada" => Some(3),
                    _ => None,
                };
                let ativas: Vec<usize> = palavras.iter().filter_map(|o| idx(o)).collect();
                let mut st = c.prepare_cached(SQL_PALAVRAS).map_err(|e| e.to_string())?;
                let linhas: Vec<(Option<i64>, [bool; 4])> = st
                    .query_map([doc], |r| {
                        let f = |i: usize| -> rusqlite::Result<bool> { Ok(r.get::<_, Option<i64>>(i)?.unwrap_or(0) != 0) };
                        Ok((r.get(0)?, [false, f(1)?, f(2)?, f(3)?]))
                    })
                    .map_err(|e| e.to_string())?
                    .collect::<Result<_, _>>()
                    .map_err(|e: rusqlite::Error| e.to_string())?;
                for (g, fl) in linhas {
                    if !ativas.is_empty() && !ativas.iter().any(|&k| fl[k]) {
                        continue;
                    }
                    grupos.adiciona(&mut ds, doc, "WordGroup", "idWordGroup", g)?;
                }
            }
            Unidade::Authors => {
                for g in col_i64(c, SQL_AUTORES, doc)? {
                    grupos.adiciona(&mut ds, doc, "AuthorGroup", "idAuthorGroup", g)?;
                }
            }
            Unidade::Countries => {
                if tem_paises {
                    for g in col_i64(c, SQL_PAISES, doc)? {
                        grupos.adiciona(&mut ds, doc, "CountryGroup", "idCountryGroup", g)?;
                    }
                }
            }
            Unidade::References | Unidade::AuthorsReference | Unidade::ReferenceSources => {
                let mut st = c.prepare_cached(SQL_REFERENCIAS).map_err(|e| e.to_string())?;
                let refs: Vec<(i64, Option<i64>, Option<i64>)> = st
                    .query_map([doc], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)))
                    .map_err(|e| e.to_string())?
                    .collect::<Result<_, _>>()
                    .map_err(|e: rusqlite::Error| e.to_string())?;
                for (rid, g, fonte) in refs {
                    match unidade {
                        Unidade::References => grupos.adiciona(&mut ds, doc, "ReferenceGroup", "idReferenceGroup", g)?,
                        Unidade::AuthorsReference => {
                            for ga in col_i64(c, SQL_AUTORES_REFERENCIA, rid)? {
                                grupos.adiciona(&mut ds, doc, "AuthorReferenceGroup", "idAuthorReferenceGroup", ga)?;
                            }
                        }
                        _ => {
                            let Some(f) = fonte else { continue };
                            let gs: Option<Option<i64>> = c
                                .query_row(
                                    "SELECT ReferenceSourceGroup_idReferenceSourceGroup FROM ReferenceSource WHERE idReferenceSource = ?;",
                                    [f],
                                    |r| r.get(0),
                                )
                                .ok();
                            grupos.adiciona(&mut ds, doc, "ReferenceSourceGroup", "idReferenceSourceGroup", gs.flatten())?;
                        }
                    }
                }
            }
            Unidade::Institutions => {
                let ix = ies_ix.as_ref().unwrap();
                if let Some(l) = ix.por_documento.get(&doc) {
                    for &i in l {
                        ds.adiciona_item_ao_documento(doc, i, &ix.nomes[&i]);
                    }
                }
            }
        }
    }
    Ok(ds)
}

#[derive(Clone, Debug)]
pub struct GrupoCorpus {
    pub nos: Vec<i64>,
    pub principal: Option<i64>,
    pub rotulo: String,
    pub exibicao: String,
}

/// Análise de co-ocorrência do corpus completo.
pub struct Corpus {
    pub parametros: Parametros,
    pub documentos_originais: usize,
    pub dataset: Dataset,
    pub rede: Rede,
    pub grupos: Vec<GrupoCorpus>,
    pub grupo_do_no: HashMap<i64, usize>,
    pub frequencia: BTreeMap<i64, usize>,
}

impl Corpus {
    /// Rótulo de exibição do nó (o nome do item, em forma legível quando palavra-chave).
    pub fn rotulo(&self, no: i64) -> String {
        let nome = self.dataset.itens.get(&no).cloned().unwrap_or_else(|| no.to_string());
        exibe_termo(self.parametros.unidade, &nome)
    }
}

/// Roda a co-ocorrência (rede, normalização e agrupamento) sobre todos os documentos.
pub fn corpus_completo(c: &Connection, p: &Parametros) -> Result<Corpus, Erro> {
    if p.matriz != Matriz::CoOccurrence {
        return Err("a análise do corpus completo existe só para co-ocorrência (os nós de acoplamento são documentos)".into());
    }
    p.valida().ok();
    let original = dataset_corpus(c, p.unidade, &p.palavras)?;
    let mut dataset = original.clone();
    if !p.ignorar.is_empty() {
        let alvos: std::collections::BTreeSet<String> = p.ignorar.iter().map(|n| chave(n)).filter(|k| !k.is_empty()).collect();
        for id in dataset.lista_itens() {
            if alvos.contains(&chave(&dataset.itens[&id])) {
                dataset.remove_item(id);
            }
        }
    }
    dataset.filtra_itens_por_frequencia(p.min_freq);
    let mut rede = rede_coocorrencia(&dataset);
    rede.filtra_por_valor(p.min_cooc);
    normaliza(&mut rede, p.similaridade, |i| dataset.frequencia_item(i));
    let conjunto = redes_core::agrupamento::agrupa(p.algoritmo, &rede, p.rede_min, p.rede_max, p.corte).map_err(|e| e.to_string())?;
    let legivel = p.unidade == Unidade::Words;
    let grupos = conjunto
        .agrupamentos
        .iter()
        .map(|a| {
            let rotulo = a.principal.map(|n| dataset.itens.get(&n).cloned().unwrap_or_else(|| n.to_string())).unwrap_or_default();
            let exibicao = if legivel { termo_legivel(&rotulo) } else { rotulo.clone() };
            GrupoCorpus { nos: a.nos.clone(), principal: a.principal, rotulo, exibicao }
        })
        .collect();
    let frequencia = rede.nos.iter().map(|&no| (no, dataset.frequencia_item(no))).collect();
    Ok(Corpus {
        parametros: p.clone(),
        documentos_originais: original.quantidade_documentos(),
        grupo_do_no: conjunto.grupo_do_no.clone(),
        dataset,
        rede,
        grupos,
        frequencia,
    })
}
