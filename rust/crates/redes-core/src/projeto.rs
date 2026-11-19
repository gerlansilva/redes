//! Leitura de um projeto `.redes` (SQLite, somente leitura): porta de `kb.py`.

use std::cell::RefCell;
use std::collections::{BTreeMap, HashMap};
use std::path::Path;
use std::rc::Rc;

use rusqlite::{Connection, OpenFlags, Row};

use crate::dataset::{Agregado, Dataset};
use crate::erro::{Erro, Resultado};
use crate::ies::{indice_de_ies, IndiceIes};
use crate::parametros::Unidade;

#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize)]
pub struct Periodo {
    pub id: i64,
    pub nome: String,
    pub posicao: i64,
}

pub struct Projeto {
    pub caminho: String,
    conexao: Connection,
    grupos: RefCell<HashMap<&'static str, HashMap<i64, (String, bool)>>>,
    ies: RefCell<Option<Rc<IndiceIes>>>,
}

const SQL_PUBLISHDATES: &str = "SELECT pu.idPublishDate FROM PublishDate_Period pdp, PublishDate pu \
     WHERE pdp.Period_idPeriod = ? AND pdp.PublishDate_idPublishDate = pu.idPublishDate;";
const SQL_DOCUMENTOS: &str = "SELECT d.idDocument, d.citationsCount FROM Document d, PublishDate p \
     WHERE p.idPublishDate = ? AND p.idPublishDate = d.PublishDate_idPublishDate;";
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

impl Projeto {
    pub fn abrir(caminho: impl AsRef<Path>) -> Resultado<Projeto> {
        let caminho = caminho.as_ref();
        let texto = caminho.display().to_string();
        if !caminho.is_file() {
            return Err(Erro::NaoEncontrado(texto));
        }
        let conexao = Connection::open_with_flags(
            caminho,
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )
        .map_err(|_| Erro::ProjetoInvalido(texto.clone()))?;
        if conexao.query_row("SELECT 1 FROM Period LIMIT 1;", [], |_| Ok(())).is_err() {
            return Err(Erro::ProjetoInvalido(texto));
        }
        Ok(Projeto { caminho: texto, conexao, grupos: RefCell::new(HashMap::new()), ies: RefCell::new(None) })
    }

    pub fn periodos(&self) -> Resultado<Vec<Periodo>> {
        let mut st = self.conexao.prepare("SELECT idPeriod, name, position FROM Period ORDER BY position ASC;")?;
        let v = st
            .query_map([], |r| {
                Ok(Periodo { id: r.get(0)?, nome: r.get::<_, Option<String>>(1)?.unwrap_or_default(), posicao: r.get(2)? })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(v)
    }

    /// Total de documentos do projeto (todos os períodos).
    pub fn total_documentos(&self) -> Resultado<usize> {
        let n: i64 = self.conexao.query_row("SELECT COUNT(*) FROM Document", [], |r| r.get(0))?;
        Ok(n as usize)
    }

    /// Instituições do projeto com as variantes unidas (calculado uma vez).
    pub fn indice_ies(&self) -> Resultado<Rc<IndiceIes>> {
        if let Some(i) = self.ies.borrow().as_ref() {
            return Ok(i.clone());
        }
        let i = Rc::new(indice_de_ies(&self.conexao)?);
        *self.ies.borrow_mut() = Some(i.clone());
        Ok(i)
    }

    /// Título e resumo dos documentos pedidos (para os rótulos por tema).
    pub fn textos_documentos(&self, ids: &[i64]) -> Resultado<BTreeMap<i64, (String, String)>> {
        use rusqlite::types::Value;
        let texto = |v: Value| match v {
            Value::Null => String::new(),
            Value::Text(t) => t,
            Value::Integer(i) => i.to_string(),
            Value::Real(f) => f.to_string(),
            Value::Blob(_) => String::new(),
        };
        let mut saida = BTreeMap::new();
        for lote in ids.chunks(500) {
            let marcas = vec!["?"; lote.len()].join(",");
            let sql = format!("SELECT idDocument, title, docAbstract FROM Document WHERE idDocument IN ({marcas})");
            let Ok(mut st) = self.conexao.prepare(&sql) else { return Ok(saida) };
            let linhas = st.query_map(rusqlite::params_from_iter(lote.iter()), |r| {
                Ok((r.get::<_, i64>(0)?, r.get::<_, Value>(1)?, r.get::<_, Value>(2)?))
            })?;
            for l in linhas {
                let (d, t, a) = l?;
                saida.insert(d, (texto(t), texto(a)));
            }
        }
        Ok(saida)
    }

    /// (documento, nome) das palavras-chave dos autores, com o grupo quando existe.
    pub fn palavras_chave_autor(&self) -> Resultado<Vec<(i64, String)>> {
        let mut st = self.conexao.prepare(
            "SELECT dw.Document_idDocument, COALESCE(g.groupName, w.wordName) \
             FROM Document_Word dw JOIN Word w ON w.idWord = dw.Word_idWord \
             LEFT JOIN WordGroup g ON g.idWordGroup = w.WordGroup_idWordGroup \
             WHERE dw.isAuthorWord = 1 AND COALESCE(g.stopGroup, 0) = 0",
        )?;
        let v = st
            .query_map([], |r| Ok((r.get::<_, i64>(0)?, r.get::<_, Option<String>>(1)?.unwrap_or_default())))?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(v)
    }

    /// Títulos dos documentos (rótulos das redes de acoplamento).
    pub fn titulos(&self, ids: &[i64]) -> Resultado<HashMap<i64, String>> {
        let mut saida = HashMap::new();
        let mut st = self.conexao.prepare("SELECT title FROM Document WHERE idDocument = ?;")?;
        for &id in ids {
            let t: Option<Option<String>> = st
                .query_row([id], |r| r.get::<_, Option<String>>(0))
                .map(Some)
                .or_else(|e| if matches!(e, rusqlite::Error::QueryReturnedNoRows) { Ok(None) } else { Err(e) })?;
            if let Some(t) = t {
                let t = t.filter(|s| !s.is_empty()).unwrap_or_else(|| format!("Documento {id}"));
                saida.insert(id, t);
            }
        }
        Ok(saida)
    }

    fn grupo(&self, tabela: &'static str, coluna: &str, id: i64) -> Resultado<Option<(String, bool)>> {
        let mut cache = self.grupos.borrow_mut();
        if !cache.contains_key(tabela) {
            let mut mapa = HashMap::new();
            let mut st = self
                .conexao
                .prepare(&format!("SELECT {coluna}, groupName, stopGroup FROM {tabela};"))?;
            let linhas = st.query_map([], |r| {
                Ok((
                    r.get::<_, i64>(0)?,
                    r.get::<_, Option<String>>(1)?.unwrap_or_default(),
                    r.get::<_, Option<i64>>(2)?.unwrap_or(0) != 0,
                ))
            })?;
            for l in linhas {
                let (i, n, s) = l?;
                mapa.insert(i, (n, s));
            }
            cache.insert(tabela, mapa);
        }
        Ok(cache[tabela].get(&id).cloned())
    }

    fn adiciona_grupo(
        &self,
        ds: &mut Dataset,
        doc: i64,
        tabela: &'static str,
        coluna: &str,
        grupo: Option<i64>,
    ) -> Resultado<()> {
        let Some(g) = grupo else { return Ok(()) };
        if let Some((nome, parada)) = self.grupo(tabela, coluna, g)? {
            if !parada {
                ds.adiciona_item_ao_documento(doc, g, &nome);
            }
        }
        Ok(())
    }

    /// Conjunto documento x item de uma unidade e de um período.
    pub fn dataset(&self, unidade: Unidade, periodo_id: i64, palavras: &[String]) -> Resultado<Dataset> {
        let mut ds = Dataset::default();
        let mut pst = self.conexao.prepare_cached(SQL_PUBLISHDATES)?;
        let pds: Vec<i64> = pst.query_map([periodo_id], |r| r.get(0))?.collect::<Result<_, _>>()?;
        for pd in pds {
            let mut dst = self.conexao.prepare_cached(SQL_DOCUMENTOS)?;
            let docs: Vec<(i64, i64)> = dst
                .query_map([pd], |r| Ok((r.get(0)?, r.get::<_, Option<i64>>(1)?.unwrap_or(0))))?
                .collect::<Result<_, _>>()?;
            for (doc, cit) in docs {
                ds.adiciona_documento(doc, cit);
                self.itens_do_documento(&mut ds, unidade, doc, palavras)?;
            }
        }
        Ok(ds)
    }

    fn itens_do_documento(&self, ds: &mut Dataset, unidade: Unidade, doc: i64, palavras: &[String]) -> Resultado<()> {
        match unidade {
            Unidade::Words => {
                let colunas = |o: &str| match o {
                    "autor" => Some(1usize),
                    "fonte" => Some(2),
                    "adicionada" => Some(3),
                    _ => None,
                };
                let ativas: Vec<usize> = palavras.iter().filter_map(|o| colunas(o)).collect();
                let mut st = self.conexao.prepare_cached(SQL_PALAVRAS)?;
                let linhas: Vec<(Option<i64>, [bool; 4])> = st
                    .query_map([doc], |r| {
                        let f = |r: &Row, i: usize| -> rusqlite::Result<bool> {
                            Ok(r.get::<_, Option<i64>>(i)?.unwrap_or(0) != 0)
                        };
                        Ok((r.get(0)?, [false, f(r, 1)?, f(r, 2)?, f(r, 3)?]))
                    })?
                    .collect::<Result<_, _>>()?;
                for (g, flags) in linhas {
                    if !ativas.is_empty() && !ativas.iter().any(|&c| flags[c]) {
                        continue;
                    }
                    self.adiciona_grupo(ds, doc, "WordGroup", "idWordGroup", g)?;
                }
            }
            Unidade::Authors => {
                let mut st = self.conexao.prepare_cached(SQL_AUTORES)?;
                let gs: Vec<Option<i64>> = st.query_map([doc], |r| r.get(0))?.collect::<Result<_, _>>()?;
                for g in gs {
                    self.adiciona_grupo(ds, doc, "AuthorGroup", "idAuthorGroup", g)?;
                }
            }
            Unidade::Countries => {
                // Projetos antigos não têm as tabelas Country/Document_Country.
                let Ok(mut st) = self.conexao.prepare_cached(SQL_PAISES) else { return Ok(()) };
                let gs: Vec<Option<i64>> = st.query_map([doc], |r| r.get(0))?.collect::<Result<_, _>>()?;
                for g in gs {
                    self.adiciona_grupo(ds, doc, "CountryGroup", "idCountryGroup", g)?;
                }
            }
            Unidade::References => {
                for (_, grupo, _) in self.referencias(doc)? {
                    self.adiciona_grupo(ds, doc, "ReferenceGroup", "idReferenceGroup", grupo)?;
                }
            }
            Unidade::AuthorsReference => {
                for (rid, _, _) in self.referencias(doc)? {
                    let mut st = self.conexao.prepare_cached(SQL_AUTORES_REFERENCIA)?;
                    let gs: Vec<Option<i64>> = st.query_map([rid], |r| r.get(0))?.collect::<Result<_, _>>()?;
                    for g in gs {
                        self.adiciona_grupo(ds, doc, "AuthorReferenceGroup", "idAuthorReferenceGroup", g)?;
                    }
                }
            }
            Unidade::ReferenceSources => {
                for (_, _, fonte) in self.referencias(doc)? {
                    let Some(f) = fonte else { continue };
                    let g: Option<Option<i64>> = self
                        .conexao
                        .query_row(
                            "SELECT ReferenceSourceGroup_idReferenceSourceGroup FROM ReferenceSource \
                             WHERE idReferenceSource = ?;",
                            [f],
                            |r| r.get(0),
                        )
                        .map(Some)
                        .or_else(|e| if matches!(e, rusqlite::Error::QueryReturnedNoRows) { Ok(None) } else { Err(e) })?;
                    self.adiciona_grupo(ds, doc, "ReferenceSourceGroup", "idReferenceSourceGroup", g.flatten())?;
                }
            }
            Unidade::Institutions => {
                let indice = self.indice_ies()?;
                if let Some(lista) = indice.por_documento.get(&doc) {
                    for ies in lista {
                        ds.adiciona_item_ao_documento(doc, *ies, &indice.nomes[ies]);
                    }
                }
            }
        }
        Ok(())
    }

    fn referencias(&self, doc: i64) -> Resultado<Vec<(i64, Option<i64>, Option<i64>)>> {
        let mut st = self.conexao.prepare_cached(SQL_REFERENCIAS)?;
        let v = st
            .query_map([doc], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)))?
            .collect::<Result<_, _>>()?;
        Ok(v)
    }

    /// Agregado por autor (`idAuthor`, `authorName`) sobre os documentos do conjunto.
    pub fn agregado_por_autor(&self, docs: &[i64]) -> Resultado<Agregado> {
        let mut ag = Agregado::default();
        let mut st = self.conexao.prepare(
            "SELECT a.idAuthor, a.authorName FROM Document_Author da, Author a \
             WHERE da.Document_idDocument = ? AND da.Author_idAuthor = a.idAuthor;",
        )?;
        for &doc in docs {
            let linhas: Vec<(i64, String)> = st
                .query_map([doc], |r| Ok((r.get(0)?, r.get::<_, Option<String>>(1)?.unwrap_or_default())))?
                .collect::<Result<_, _>>()?;
            for (id, nome) in linhas {
                ag.adiciona(id, &nome, doc);
            }
        }
        Ok(ag)
    }

    /// Agregado por periódico (`idJournal`, `source`).
    pub fn agregado_por_periodico(&self, docs: &[i64]) -> Resultado<Agregado> {
        let mut ag = Agregado::default();
        let mut st = self.conexao.prepare(
            "SELECT j.idJournal, j.source FROM Document d, Journal j \
             WHERE d.idDocument = ? AND d.Journal_idJournal = j.idJournal;",
        )?;
        for &doc in docs {
            let l: Option<(i64, String)> = st
                .query_row([doc], |r| Ok((r.get(0)?, r.get::<_, Option<String>>(1)?.unwrap_or_default())))
                .map(Some)
                .or_else(|e| if matches!(e, rusqlite::Error::QueryReturnedNoRows) { Ok(None) } else { Err(e) })?;
            if let Some((id, nome)) = l {
                ag.adiciona(id, &nome, doc);
            }
        }
        Ok(ag)
    }
}
