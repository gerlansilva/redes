//! Acesso somente leitura ao `.redes` (SQLite) para as análises que precisam de campos
//! além dos expostos por `redes-core` (resumos, afiliações, anos, referências).

use std::collections::BTreeMap;
use std::path::Path;

use rusqlite::{Connection, OpenFlags};

pub type Erro = String;

pub fn abre(caminho: impl AsRef<Path>) -> Result<Connection, Erro> {
    let c = caminho.as_ref();
    if !c.is_file() {
        return Err(format!("projeto não encontrado: {}", c.display()));
    }
    Connection::open_with_flags(c, OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX)
        .map_err(|e| format!("projeto inválido: {e}"))
}

pub fn existe_tabela(c: &Connection, nome: &str) -> bool {
    c.query_row("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [nome], |_| Ok(())).is_ok()
}

/// Ano de 4 algarismos no começo do texto (`int(str(v)[:4])`), entre 1000 e 2999.
pub fn ano_do_texto(v: &str) -> Option<i64> {
    let p: String = v.chars().take(4).collect();
    let n: i64 = p.parse().ok()?;
    if (1000..=2999).contains(&n) {
        Some(n)
    } else {
        None
    }
}

fn texto_da_coluna(v: rusqlite::types::ValueRef) -> Option<String> {
    use rusqlite::types::ValueRef::*;
    match v {
        Null => None,
        Integer(i) => Some(i.to_string()),
        Real(f) => Some(format!("{f}")),
        Text(t) => Some(String::from_utf8_lossy(t).into_owned()),
        Blob(_) => None,
    }
}

/// Ano de cada documento (`PublishDate.year`, ou `Document.year` na falta).
pub fn anos_dos_documentos(c: &Connection) -> Result<BTreeMap<i64, i64>, Erro> {
    let mut st = c
        .prepare(
            "SELECT d.idDocument, COALESCE(p.year, d.year) FROM Document d \
             LEFT JOIN PublishDate p ON p.idPublishDate = d.PublishDate_idPublishDate",
        )
        .map_err(|e| e.to_string())?;
    let mut saida = BTreeMap::new();
    let mut linhas = st.query([]).map_err(|e| e.to_string())?;
    while let Some(l) = linhas.next().map_err(|e| e.to_string())? {
        let id: i64 = l.get(0).map_err(|e| e.to_string())?;
        if let Some(t) = texto_da_coluna(l.get_ref(1).map_err(|e| e.to_string())?) {
            if let Some(a) = ano_do_texto(&t) {
                saida.insert(id, a);
            }
        }
    }
    Ok(saida)
}

/// Mediana inferior (`statistics.median_low`) de uma lista não vazia.
pub fn mediana_baixa(v: &mut Vec<i64>) -> i64 {
    v.sort();
    v[(v.len() - 1) / 2]
}

/// Pares (documento, nome) de uma consulta de duas colunas, na ordem devolvida.
pub fn pares_doc_nome(c: &Connection, sql: &str) -> Result<Vec<(i64, String)>, Erro> {
    let mut st = c.prepare(sql).map_err(|e| e.to_string())?;
    let mut linhas = st.query([]).map_err(|e| e.to_string())?;
    let mut v = Vec::new();
    while let Some(l) = linhas.next().map_err(|e| e.to_string())? {
        let id: i64 = l.get(0).map_err(|e| e.to_string())?;
        if let Some(t) = texto_da_coluna(l.get_ref(1).map_err(|e| e.to_string())?) {
            v.push((id, t));
        }
    }
    Ok(v)
}
