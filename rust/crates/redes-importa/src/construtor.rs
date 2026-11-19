//! Constrói o projeto `.redes` a partir dos documentos importados (porta de `build.py`).
//!
//! A ordem de criação dos agrupamentos importa: ela define os identificadores dos itens
//! e, com isso, o desempate dos algoritmos de agrupamento.

use std::collections::{HashMap, HashSet};
use std::path::Path;

use indexmap::IndexMap;
use rusqlite::{params, Connection};

use crate::erro::{Erro, Resultado};
use crate::fonte::DocumentoFonte;
use crate::referencias::{converte_referencia, nome_do_grupo};
use crate::util::*;

pub const SCHEMA: &str = include_str!("schema.sql");
pub const VERSAO: &str = "v1_03";

pub struct Referencia {
    pub id: i64,
    pub completa: String,
    pub bruta: String,
    pub autor: String,
    pub ano: String,
    pub fonte: String,
    pub volume: String,
    pub paginas: String,
}

impl Referencia {
    fn nova(id: i64, completa: &str, bruta: &str) -> Self {
        let campos: Vec<&str> = completa.split(',').collect();
        let g = |i: usize| campos.get(i).map(|s| strip(s).to_string()).unwrap_or_default();
        Referencia {
            id,
            completa: completa.to_string(),
            bruta: if bruta.is_empty() { completa.to_string() } else { bruta.to_string() },
            autor: g(0),
            ano: g(1),
            fonte: g(2),
            volume: g(3),
            paginas: g(4),
        }
    }
}

/// Palavra, autor, referência ou fonte com sua contagem de documentos.
pub struct Item {
    pub id: i64,
    pub nome: String,
    pub documentos: Vec<i64>,
    pub usos: i64,
}

impl Item {
    fn novo(id: i64, nome: &str) -> Self {
        Item { id, nome: nome.to_string(), documentos: vec![], usos: 0 }
    }
    fn frequencia(&self) -> usize {
        self.documentos.len()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AutoresReferencia {
    #[default]
    Primeiro,
    Todos,
    Lista,
}

pub type Periodo = (String, i64, i64);

fn converte_referencias(documentos: &mut [DocumentoFonte]) {
    for d in documentos {
        if d.referencias_convertidas {
            continue;
        }
        let mut convertidas: Vec<String> = vec![];
        for bruta in &d.referencias {
            if let Some(item) = converte_referencia(bruta) {
                if !convertidas.contains(&item) {
                    convertidas.push(item);
                }
            }
        }
        d.referencias = convertidas;
        d.referencias_convertidas = true;
    }
}

pub struct Construtor {
    pub documentos: Vec<DocumentoFonte>,
    autores_referencia: AutoresReferencia,
    pub autores: IndexMap<String, Item>,
    pub palavras: IndexMap<String, Item>,
    pub referencias: IndexMap<String, Referencia>,
    pub autores_ref: IndexMap<String, Item>,
    pub fontes: IndexMap<String, Item>,
    pub paises: IndexMap<String, i64>,
    pub afiliacoes: IndexMap<String, i64>,
    nomes_completos: HashMap<String, String>,
    jornais: IndexMap<String, i64>,
    datas: IndexMap<(String, String), i64>,
    vinculos_autor: IndexMap<i64, Vec<(i64, i64)>>,
    vinculos_pais: IndexMap<i64, Vec<i64>>,
    vinculos_afiliacao: IndexMap<i64, Vec<i64>>,
    vinculos_palavra: IndexMap<(i64, i64), [i64; 3]>,
    vinculos_referencia: IndexMap<i64, Vec<i64>>,
    refs_por_autor_ref: IndexMap<i64, Vec<(i64, i64)>>,
    refs_por_fonte: IndexMap<i64, Vec<i64>>,
}

type GrupoSimples = (i64, String, Vec<i64>);
type GrupoParada = (i64, String, bool, Vec<i64>);

impl Construtor {
    pub fn novo(documentos: Vec<DocumentoFonte>, autores_referencia: AutoresReferencia) -> Self {
        Construtor {
            documentos,
            autores_referencia,
            autores: Default::default(),
            palavras: Default::default(),
            referencias: Default::default(),
            autores_ref: Default::default(),
            fontes: Default::default(),
            paises: Default::default(),
            afiliacoes: Default::default(),
            nomes_completos: Default::default(),
            jornais: Default::default(),
            datas: Default::default(),
            vinculos_autor: Default::default(),
            vinculos_pais: Default::default(),
            vinculos_afiliacao: Default::default(),
            vinculos_palavra: Default::default(),
            vinculos_referencia: Default::default(),
            refs_por_autor_ref: Default::default(),
            refs_por_fonte: Default::default(),
        }
    }

    pub fn importa(&mut self, progresso: &mut dyn FnMut(&str, f32)) {
        converte_referencias(&mut self.documentos);
        let docs = std::mem::take(&mut self.documentos);
        let total = docs.len().max(1);
        for (i, d) in docs.iter().enumerate() {
            self.documento((i + 1) as i64, d);
            if i % 200 == 0 {
                progresso("Organizando documentos", i as f32 / total as f32);
            }
        }
        self.documentos = docs;
    }

    fn autores_citados(&self, autor: &str) -> Vec<String> {
        if self.autores_referencia == AutoresReferencia::Lista || !autor.contains(';') {
            return vec![autor.to_string()];
        }
        let mut autores: Vec<String> = vec![];
        for a in autor.split(';') {
            let a = strip(a);
            if !a.is_empty() && !autores.iter().any(|x| x == a) {
                autores.push(a.to_string());
            }
        }
        if autores.is_empty() {
            return vec![autor.to_string()];
        }
        if self.autores_referencia == AutoresReferencia::Primeiro {
            autores.truncate(1);
        }
        autores
    }

    fn documento(&mut self, doc_id: i64, d: &DocumentoFonte) {
        let n = self.jornais.len() as i64 + 1;
        self.jornais.entry(d.periodico.clone()).or_insert(n);
        let n = self.datas.len() as i64 + 1;
        self.datas.entry((d.ano.clone(), String::new())).or_insert(n);

        let mut va = vec![];
        let mut vistos: HashSet<i64> = HashSet::new();
        for (i, nome) in d.autores.iter().enumerate() {
            let posicao = i as i64 + 1;
            let nome = strip(nome);
            if nome.is_empty() {
                continue;
            }
            let novo_id = self.autores.len() as i64 + 1;
            let item = self.autores.entry(nome.to_string()).or_insert_with(|| Item::novo(novo_id, nome));
            if item.documentos.last() != Some(&doc_id) {
                item.documentos.push(doc_id);
            }
            if !vistos.insert(item.id) {
                continue;
            }
            va.push((item.id, posicao));
        }
        self.vinculos_autor.insert(doc_id, va);

        for (i, nome) in d.autores.iter().enumerate() {
            let nome = strip(nome);
            if nome.is_empty() || self.nomes_completos.contains_key(nome) {
                continue;
            }
            let completo = d.autores_completos.get(i).map(|s| strip(s)).unwrap_or("");
            self.nomes_completos.insert(nome.to_string(), if completo.is_empty() { nome.to_string() } else { completo.to_string() });
        }

        let mut vaf: Vec<i64> = vec![];
        for nome in &d.afiliacoes {
            let nome = strip(nome);
            if nome.is_empty() {
                continue;
            }
            let novo = self.afiliacoes.len() as i64 + 1;
            let id = *self.afiliacoes.entry(nome.to_string()).or_insert(novo);
            if !vaf.contains(&id) {
                vaf.push(id);
            }
        }
        self.vinculos_afiliacao.insert(doc_id, vaf);

        let mut vp: Vec<i64> = vec![];
        for nome in &d.paises {
            let nome = strip(nome);
            if nome.is_empty() {
                continue;
            }
            let novo = self.paises.len() as i64 + 1;
            let id = *self.paises.entry(nome.to_string()).or_insert(novo);
            if !vp.contains(&id) {
                vp.push(id);
            }
        }
        self.vinculos_pais.insert(doc_id, vp);

        let mut vr: Vec<i64> = vec![];
        for (posicao, completa) in d.referencias.iter().enumerate() {
            let bruta = d.referencias_brutas.get(posicao).map(|s| strip(s)).unwrap_or("");
            let ref_id = match self.referencias.get(completa) {
                Some(r) => r.id,
                None => {
                    let id = self.referencias.len() as i64 + 1;
                    let referencia = Referencia::nova(id, completa, bruta);
                    let autor_ref = referencia.autor.clone();
                    let fonte_ref = referencia.fonte.clone();
                    self.referencias.insert(completa.clone(), referencia);

                    for (pa, nome_autor) in self.autores_citados(&autor_ref).into_iter().enumerate() {
                        let novo = self.autores_ref.len() as i64 + 1;
                        let autor = self.autores_ref.entry(nome_autor.clone()).or_insert_with(|| Item::novo(novo, &nome_autor));
                        autor.usos += 1;
                        let aid = autor.id;
                        self.refs_por_autor_ref.entry(aid).or_default().push((id, pa as i64 + 1));
                    }
                    let novo = self.fontes.len() as i64 + 1;
                    let fonte = self.fontes.entry(fonte_ref.clone()).or_insert_with(|| Item::novo(novo, &fonte_ref));
                    fonte.usos += 1;
                    let fid = fonte.id;
                    self.refs_por_fonte.entry(fid).or_default().push(id);
                    id
                }
            };
            if !vr.contains(&ref_id) {
                vr.push(ref_id);
            }
        }
        self.vinculos_referencia.insert(doc_id, vr);

        for (tipo, termos) in [(0usize, &d.palavras_autor), (1usize, &d.palavras_fonte)] {
            for termo in termos {
                let nome = normaliza_palavra(termo);
                if nome.is_empty() {
                    continue;
                }
                let novo = self.palavras.len() as i64 + 1;
                let item = self.palavras.entry(nome.clone()).or_insert_with(|| Item::novo(novo, &nome));
                if item.documentos.last() != Some(&doc_id) {
                    item.documentos.push(doc_id);
                }
                let iid = item.id;
                self.vinculos_palavra.entry((doc_id, iid)).or_insert([0, 0, 0])[tipo] = 1;
            }
        }
    }

    // ------------------------------------------------------------- agrupamento

    pub fn agrupa_palavras(&self) -> Vec<GrupoSimples> {
        let mut ordenadas: Vec<&Item> = self.palavras.values().collect();
        ordenadas.sort_by(|a, b| a.nome.cmp(&b.nome));
        let mut blocos: HashMap<String, Vec<usize>> = HashMap::new();
        for (pos, item) in ordenadas.iter().enumerate() {
            blocos.entry(chave_de_bloco(&item.nome)).or_default().push(pos);
        }
        let mut usadas = vec![false; ordenadas.len()];
        let mut grupos: Vec<GrupoSimples> = vec![];
        for (pos, base) in ordenadas.iter().enumerate() {
            if usadas[pos] {
                continue;
            }
            usadas[pos] = true;
            let mut membros: Vec<&Item> = vec![base];
            for &outra in &blocos[&chave_de_bloco(&base.nome)] {
                if outra > pos && !usadas[outra] && mesmo_termo(&base.nome, &ordenadas[outra].nome) {
                    usadas[outra] = true;
                    membros.push(ordenadas[outra]);
                }
            }
            let mut nome = base.nome.clone();
            let mut maximo = base.frequencia();
            for m in &membros {
                if m.frequencia() > maximo {
                    maximo = m.frequencia();
                    nome = m.nome.clone();
                } else if m.frequencia() == maximo
                    && nome == sem_acentos(&nome)
                    && m.nome != sem_acentos(&m.nome)
                    && sem_acentos(&m.nome) == sem_acentos(&nome)
                {
                    nome = m.nome.clone();
                }
            }
            grupos.push((grupos.len() as i64 + 1, nome, membros.iter().map(|m| m.id).collect()));
        }
        grupos
    }

    pub fn agrupa_autores(&self) -> Vec<GrupoSimples> {
        let mut por_chave: IndexMap<String, Vec<&Item>> = IndexMap::new();
        for a in self.autores.values() {
            por_chave.entry(chave(&a.nome)).or_default().push(a);
        }
        let mut grupos = vec![];
        for membros in por_chave.values() {
            let mut rep = membros[0];
            for m in membros {
                if m.frequencia() > rep.frequencia() {
                    rep = m;
                }
            }
            grupos.push((grupos.len() as i64 + 1, rep.nome.clone(), membros.iter().map(|m| m.id).collect()));
        }
        grupos
    }

    pub fn agrupa_referencias(&self) -> Vec<(i64, String, i64)> {
        let mut usados: HashSet<String> = HashSet::new();
        let mut grupos = vec![];
        for r in self.referencias.values() {
            let nome = nome_do_grupo(&r.completa, &usados);
            usados.insert(nome.clone());
            grupos.push((grupos.len() as i64 + 1, nome, r.id));
        }
        grupos
    }

    pub fn agrupa_autores_de_referencia(&self) -> Vec<GrupoParada> {
        let mut por_chave: IndexMap<String, Vec<&Item>> = IndexMap::new();
        for a in self.autores_ref.values() {
            por_chave.entry(chave(&a.nome)).or_default().push(a);
        }
        let mut grupos = vec![];
        for membros in por_chave.values() {
            let mut rep = membros[0];
            for m in membros {
                if m.usos > rep.usos || (m.usos == rep.usos && n_chars(&m.nome) < n_chars(&rep.nome)) {
                    rep = m;
                }
            }
            grupos.push((grupos.len() as i64 + 1, rep.nome.clone(), rep.nome.to_lowercase() == "sem autor", membros.iter().map(|m| m.id).collect()));
        }
        grupos
    }

    pub fn agrupa_fontes(&self) -> Vec<GrupoParada> {
        let mut por_chave: IndexMap<String, Vec<&Item>> = IndexMap::new();
        for f in self.fontes.values() {
            por_chave.entry(chave(&f.nome)).or_default().push(f);
        }
        let nome_por_chave: HashMap<&String, String> = por_chave.iter().map(|(k, v)| (k, representante_fonte(v).nome.clone())).collect();
        let chaves: Vec<&String> = por_chave.keys().collect();
        let alvo = abreviacoes_sem_ambiguidade(&chaves, &nome_por_chave);

        let mut grupos: IndexMap<String, Vec<&Item>> = IndexMap::new();
        for (k, membros) in &por_chave {
            let destino = alvo.get(k).cloned().unwrap_or_else(|| k.clone());
            grupos.entry(destino).or_default().extend(membros.iter().copied());
        }
        let mut resultado = vec![];
        for membros in grupos.values() {
            let rep = representante_fonte(membros);
            resultado.push((resultado.len() as i64 + 1, rep.nome.clone(), rep.nome.to_lowercase() == "sem fonte", membros.iter().map(|m| m.id).collect()));
        }
        resultado
    }

    // ------------------------------------------------------------- gravação

    pub fn grava(&self, destino: &Path, periodos: &[Periodo], progresso: &mut dyn FnMut(&str, f32)) -> Resultado<()> {
        if destino.exists() {
            std::fs::remove_file(destino).map_err(|e| Erro::Io(format!("{}: {e}", destino.display())))?;
        }
        if let Some(pai) = destino.parent() {
            if !pai.as_os_str().is_empty() {
                std::fs::create_dir_all(pai).map_err(|e| Erro::Io(format!("{}: {e}", pai.display())))?;
            }
        }
        let mut conexao = Connection::open(destino)?;
        conexao.execute_batch("PRAGMA foreign_keys = OFF; PRAGMA synchronous = OFF; PRAGMA journal_mode = MEMORY;")?;
        conexao.execute_batch(SCHEMA)?;
        conexao.execute_batch("PRAGMA foreign_keys = ON;")?;

        progresso("Agrupando termos", 0.0);
        let g_palavra = self.agrupa_palavras();
        let g_autor = self.agrupa_autores();
        progresso("Agrupando referências", 0.0);
        let g_ref = self.agrupa_referencias();
        let g_autor_ref = self.agrupa_autores_de_referencia();
        let g_fonte = self.agrupa_fontes();

        let tx = conexao.transaction()?;
        progresso("Gravando o projeto", 0.0);
        self.grava_nucleo(&tx)?;
        grava_grupos(&tx, "WordGroup", "idWordGroup", "Word", "idWord", "WordGroup_idWordGroup", &g_palavra)?;
        grava_grupos(&tx, "AuthorGroup", "idAuthorGroup", "Author", "idAuthor", "AuthorGroup_idAuthorGroup", &g_autor)?;
        grava_referencias(&tx, &g_ref, &g_autor_ref, &g_fonte)?;
        self.grava_periodos(&tx, periodos)?;
        ex(&tx, "INSERT OR REPLACE INTO KnowledgeBaseVersion(knowledgeBaseVersion) VALUES (?);", [VERSAO])?;
        tx.commit()?;
        Ok(())
    }

    fn grava_nucleo(&self, c: &Connection) -> Resultado<()> {
        for ((ano, data), id) in &self.datas {
            ex(c, "INSERT INTO PublishDate(idPublishDate, year, date) VALUES (?, ?, ?)", params![id, ano, data])?;
        }
        for (fonte, id) in &self.jornais {
            ex(c, "INSERT INTO Journal(idJournal, source) VALUES (?, ?)", params![id, fonte])?;
        }
        {
            let mut ins = c.prepare(
                "INSERT INTO Document(idDocument, title, type, docAbstract, doi, citationsCount, authors, \
                 PublishDate_idPublishDate, Journal_idJournal) VALUES (?,?,?,?,?,?,?,NULL,NULL)",
            )?;
            let mut upd = c.prepare("UPDATE Document SET PublishDate_idPublishDate = ?, Journal_idJournal = ? WHERE idDocument = ?")?;
            for (i, d) in self.documentos.iter().enumerate() {
                let id = i as i64 + 1;
                ins.execute(params![id, d.titulo, d.tipo, d.resumo, d.doi, d.citacoes, d.autores.join(", ")])?;
                upd.execute(params![self.datas[&(d.ano.clone(), String::new())], self.jornais[&d.periodico], id])?;
            }
        }
        for (nome, a) in &self.autores {
            ex(c, 
                "INSERT INTO Author(idAuthor, authorName, fullAuthorName, AuthorGroup_idAuthorGroup) VALUES (?, ?, ?, NULL)",
                params![a.id, nome, self.nomes_completos.get(nome).unwrap_or(nome)],
            )?;
        }
        {
            let mut ins = c.prepare("INSERT INTO Document_Author(Author_idAuthor, Document_idDocument, position) VALUES (?, ?, ?)")?;
            for (doc, vs) in &self.vinculos_autor {
                for (a, p) in vs {
                    ins.execute(params![a, doc, p])?;
                }
            }
        }
        for (nome, id) in &self.afiliacoes {
            ex(c, 
                "INSERT INTO Affiliation(idAffiliation, fullAffiliation, affiliation_documentsCount, affiliation_authorsCount) VALUES (?, ?, 0, 0)",
                params![id, nome],
            )?;
        }
        {
            let mut ins = c.prepare("INSERT INTO Document_Affiliation(Affiliation_idAffiliation, Document_idDocument) VALUES (?, ?)")?;
            for (doc, vs) in &self.vinculos_afiliacao {
                for a in vs {
                    ins.execute(params![a, doc])?;
                }
            }
        }
        for (nome, id) in &self.paises {
            ex(c, "INSERT INTO CountryGroup(idCountryGroup, groupName, stopGroup) VALUES (?, ?, 0)", params![id, nome])?;
            ex(c, "INSERT INTO Country(idCountry, countryName, CountryGroup_idCountryGroup) VALUES (?, ?, ?)", params![id, nome, id])?;
        }
        {
            let mut ins = c.prepare("INSERT INTO Document_Country(Country_idCountry, Document_idDocument) VALUES (?, ?)")?;
            for (doc, vs) in &self.vinculos_pais {
                for p in vs {
                    ins.execute(params![p, doc])?;
                }
            }
        }
        for (nome, p) in &self.palavras {
            ex(c, "INSERT INTO Word(idWord, wordName, WordGroup_idWordGroup) VALUES (?, ?, NULL)", params![p.id, nome])?;
        }
        {
            let mut ins = c.prepare(
                "INSERT INTO Document_Word(Document_idDocument, Word_idWord, isAuthorWord, isSourceWord, isAddedWord) VALUES (?, ?, ?, ?, ?)",
            )?;
            for ((doc, pid), f) in &self.vinculos_palavra {
                ins.execute(params![doc, pid, f[0], f[1], 0])?;
            }
        }
        {
            let mut ins = c.prepare(
                "INSERT INTO Reference(idReference, fullReference, volume, page, year, doi, ReferenceGroup_idReferenceGroup, \
                 ReferenceSource_idReferenceSource) VALUES (?,?,?,?,?,?,NULL,NULL)",
            )?;
            for r in self.referencias.values() {
                ins.execute(params![r.id, r.completa, r.volume, r.paginas, r.ano, ""])?;
            }
            let mut raw = c.prepare("INSERT INTO ReferenceRaw(Reference_idReference, rawReference) VALUES (?, ?)")?;
            for r in self.referencias.values() {
                raw.execute(params![r.id, r.bruta])?;
            }
            let mut dr = c.prepare("INSERT INTO Document_Reference(Document_idDocument, Reference_idReference) VALUES (?, ?)")?;
            for (doc, rs) in &self.vinculos_referencia {
                for r in rs {
                    dr.execute(params![doc, r])?;
                }
            }
        }
        {
            let mut ins = c.prepare("INSERT INTO DocumentMetadata(Document_idDocument, metaKey, metaValue) VALUES (?, ?, ?)")?;
            for (i, d) in self.documentos.iter().enumerate() {
                for (k, v) in &d.metadados {
                    ins.execute(params![i as i64 + 1, k, v])?;
                }
            }
        }
        for (nome, a) in &self.autores_ref {
            ex(c, 
                "INSERT INTO AuthorReference(idAuthorReference, authorName, AuthorReferenceGroup_idAuthorReferenceGroup) VALUES (?, ?, NULL)",
                params![a.id, nome],
            )?;
        }
        {
            let mut ins = c.prepare(
                "INSERT INTO AuthorReference_Reference(AuthorReference_idAuthorReference, Reference_idReference, position) VALUES (?, ?, ?)",
            )?;
            for (aid, refs) in &self.refs_por_autor_ref {
                for (r, p) in refs {
                    ins.execute(params![aid, r, p])?;
                }
            }
        }
        for (nome, f) in &self.fontes {
            ex(c, 
                "INSERT INTO ReferenceSource(idReferenceSource, source, ReferenceSourceGroup_idReferenceSourceGroup) VALUES (?, ?, NULL)",
                params![f.id, nome],
            )?;
        }
        {
            let mut upd = c.prepare("UPDATE Reference SET ReferenceSource_idReferenceSource = ? WHERE idReference = ?")?;
            for (fid, refs) in &self.refs_por_fonte {
                for r in refs {
                    upd.execute(params![fid, r])?;
                }
            }
        }
        Ok(())
    }

    fn grava_periodos(&self, c: &Connection, periodos: &[Periodo]) -> Resultado<()> {
        for (i, (nome, inicio, fim)) in periodos.iter().enumerate() {
            let pos = i as i64 + 1;
            ex(c, "INSERT INTO Period(idPeriod, name, position) VALUES (?, ?, ?)", params![pos, nome, pos])?;
            for ((ano, _), data_id) in &self.datas {
                let Some(valor) = ano_inteiro(ano) else { continue };
                if *inicio <= valor && valor <= *fim {
                    ex(c, "INSERT INTO PublishDate_Period(PublishDate_idPublishDate, Period_idPeriod) VALUES (?, ?)", params![data_id, pos])?;
                }
            }
        }
        Ok(())
    }
}

/// Executa com statement em cache (preparar um INSERT numa tabela com gatilhos é caro).
fn ex(c: &Connection, sql: &str, p: impl rusqlite::Params) -> Resultado<usize> {
    Ok(c.prepare_cached(sql)?.execute(p)?)
}

/// `int(str(ano).strip()[:4])`.
fn ano_inteiro(ano: &str) -> Option<i64> {
    let t: String = strip(ano).chars().take(4).collect();
    t.parse::<i64>().ok()
}

fn grava_grupos(c: &Connection, tabela_grupo: &str, coluna_grupo: &str, tabela_item: &str, coluna_item: &str, coluna_fk: &str, grupos: &[GrupoSimples]) -> Resultado<()> {
    let mut ins = c.prepare(&format!("INSERT INTO {tabela_grupo}({coluna_grupo}, groupName, stopGroup) VALUES (?, ?, 0)"))?;
    let mut upd = c.prepare(&format!("UPDATE {tabela_item} SET {coluna_fk} = ? WHERE {coluna_item} = ?"))?;
    for (id, nome, membros) in grupos {
        ins.execute(params![id, nome])?;
        for m in membros {
            upd.execute(params![id, m])?;
        }
    }
    Ok(())
}

fn grava_referencias(c: &Connection, g_ref: &[(i64, String, i64)], g_autor_ref: &[GrupoParada], g_fonte: &[GrupoParada]) -> Resultado<()> {
    for (id, nome, rid) in g_ref {
        ex(c, "INSERT INTO ReferenceGroup(idReferenceGroup, groupName, stopGroup) VALUES (?, ?, 0)", params![id, nome])?;
        ex(c, "UPDATE Reference SET ReferenceGroup_idReferenceGroup = ? WHERE idReference = ?", params![id, rid])?;
    }
    for (id, nome, parada, membros) in g_autor_ref {
        ex(c, "INSERT INTO AuthorReferenceGroup(idAuthorReferenceGroup, groupName, stopGroup) VALUES (?, ?, ?)", params![id, nome, *parada as i64])?;
        for m in membros {
            ex(c, "UPDATE AuthorReference SET AuthorReferenceGroup_idAuthorReferenceGroup = ? WHERE idAuthorReference = ?", params![id, m])?;
        }
    }
    for (id, nome, parada, membros) in g_fonte {
        ex(c, "INSERT INTO ReferenceSourceGroup(idReferenceSourceGroup, groupName, stopGroup) VALUES (?, ?, ?)", params![id, nome, *parada as i64])?;
        for m in membros {
            ex(c, "UPDATE ReferenceSource SET ReferenceSourceGroup_idReferenceSourceGroup = ? WHERE idReferenceSource = ?", params![id, m])?;
        }
    }
    Ok(())
}

fn representante_fonte<'a>(membros: &[&'a Item]) -> &'a Item {
    let mut escolhido = membros[0];
    for &m in membros {
        let ab_esc = parece_abreviacao(&escolhido.nome);
        let ab_m = parece_abreviacao(&m.nome);
        if m.usos > escolhido.usos
            || (m.usos == escolhido.usos && ab_esc && !ab_m)
            || (m.usos == escolhido.usos && ab_esc == ab_m && n_chars(&m.nome) < n_chars(&escolhido.nome))
        {
            escolhido = m;
        }
    }
    escolhido
}

fn abreviacoes_sem_ambiguidade(chaves: &[&String], nome_por_chave: &HashMap<&String, String>) -> HashMap<String, String> {
    let mut completas: Vec<&String> = vec![];
    let mut palavras_c: HashMap<&String, Vec<String>> = HashMap::new();
    for &k in chaves {
        let nome = &nome_por_chave[k];
        if !parece_abreviacao(nome) && nome.to_lowercase() != "sem fonte" {
            completas.push(k);
            palavras_c.insert(k, palavras_significativas(nome));
        }
    }
    let mut alvo = HashMap::new();
    for &k in chaves {
        let partes = partes_abreviadas(&nome_por_chave[k]);
        if partes.is_empty() {
            continue;
        }
        let candidatas: Vec<&&String> = completas.iter().filter(|c| abreviacao_de(&partes, &palavras_c[**c])).collect();
        if candidatas.len() == 1 {
            alvo.insert(k.clone(), (*candidatas[0]).clone());
        }
    }
    alvo
}

// ------------------------------------------------------------------ períodos

/// Divide o intervalo de anos em períodos de volume parecido (1 a 4 sem `quantidade`).
pub fn sugere_periodos(anos: &[i64], quantidade: Option<i64>, minimo_por_periodo: i64) -> Vec<Periodo> {
    let mut anos: Vec<i64> = anos.iter().copied().filter(|a| *a != 0).collect();
    anos.sort_unstable();
    if anos.is_empty() {
        return vec![("0\u{2013}9999".into(), 0, 9999)];
    }
    let primeiro = anos[0];
    let ultimo = *anos.last().unwrap();
    let extensao = ultimo - primeiro + 1;
    let n = anos.len() as i64;
    let quantidade = match quantidade {
        None => 4.min(n.div_euclid(minimo_por_periodo)).min(extensao.div_euclid(3)),
        Some(q) => q,
    };
    let quantidade = 1.max(quantidade.min(extensao));
    let mut fins: Vec<i64> = vec![];
    for i in 1..quantidade {
        let idx = 0.max(py_round(i as f64 * n as f64 / quantidade as f64) - 1) as usize;
        let corte = anos[idx];
        if primeiro <= corte && corte < ultimo && fins.last().map_or(true, |u| corte > *u) {
            fins.push(corte);
        }
    }
    fins.push(ultimo);
    let mut faixas = vec![];
    let mut inicio = primeiro;
    for fim in fins {
        faixas.push((format!("{inicio}\u{2013}{fim}"), inicio, fim));
        inicio = fim + 1;
    }
    faixas
}

/// Une grafias do mesmo periódico que só diferem por caixa, acento ou pontuação.
pub fn unifica_periodicos(documentos: &mut [DocumentoFonte]) -> IndexMap<String, Vec<String>> {
    let mut contagem: IndexMap<String, IndexMap<String, i64>> = IndexMap::new();
    for d in documentos.iter() {
        let nome = strip(&d.periodico);
        if !nome.is_empty() && !chave(nome).is_empty() {
            *contagem.entry(chave(nome)).or_default().entry(nome.to_string()).or_insert(0) += 1;
        }
    }
    let mut adotada: HashMap<String, String> = HashMap::new();
    for (k, v) in &contagem {
        let mut itens: Vec<(&String, &i64)> = v.iter().collect();
        itens.sort_by(|a, b| {
            let ka = (-*a.1, eh_maiuscula(a.0), -(a.0.chars().filter(|c| (*c as u32) > 127).count() as i64), a.0);
            let kb = (-*b.1, eh_maiuscula(b.0), -(b.0.chars().filter(|c| (*c as u32) > 127).count() as i64), b.0);
            ka.cmp(&kb)
        });
        adotada.insert(k.clone(), itens[0].0.clone());
    }
    let mut unidos = IndexMap::new();
    for (k, v) in &contagem {
        if v.len() > 1 {
            let mut vs: Vec<String> = v.keys().cloned().collect();
            vs.sort();
            unidos.insert(adotada[k].clone(), vs);
        }
    }
    for d in documentos.iter_mut() {
        let nome = strip(&d.periodico).to_string();
        if !nome.is_empty() {
            if let Some(a) = adotada.get(&chave(&nome)) {
                d.periodico = a.clone();
            }
        }
    }
    unidos
}

pub fn periodos_a_partir_dos_anos(documentos: &[DocumentoFonte]) -> Vec<Periodo> {
    let anos: Vec<i64> = documentos
        .iter()
        .filter(|d| !d.ano.is_empty() && d.ano.chars().all(|c| c.is_ascii_digit()))
        .filter_map(|d| d.ano.parse::<i64>().ok())
        .collect();
    sugere_periodos(&anos, None, 40)
}
