//! Conjunto documento x item de uma unidade e de um período (porta de `dataset.py`).
//!
//! A ordem de inserção dos itens de cada documento é preservada: ela define a
//! ordem de inserção das arestas e, com isso, a ordem das somas em ponto
//! flutuante do Louvain.

use std::collections::BTreeMap;

#[derive(Clone, Debug, Default)]
pub struct Documento {
    pub citacoes: i64,
    pub itens: Vec<i64>,
}

#[derive(Clone, Debug, Default)]
pub struct Dataset {
    pub documentos: BTreeMap<i64, Documento>,
    pub itens: BTreeMap<i64, String>,
    pub docs_por_item: BTreeMap<i64, Vec<i64>>,
}

impl Dataset {
    pub fn adiciona_documento(&mut self, id: i64, citacoes: i64) -> bool {
        if self.documentos.contains_key(&id) {
            return false;
        }
        self.documentos.insert(id, Documento { citacoes, itens: Vec::new() });
        true
    }

    pub fn adiciona_item_ao_documento(&mut self, doc: i64, item: i64, rotulo: &str) -> bool {
        let Some(d) = self.documentos.get_mut(&doc) else { return false };
        if !self.itens.contains_key(&item) {
            self.itens.insert(item, rotulo.to_string());
            self.docs_por_item.insert(item, Vec::new());
        }
        if d.itens.contains(&item) {
            return false;
        }
        d.itens.push(item);
        self.docs_por_item.get_mut(&item).unwrap().push(doc);
        true
    }

    pub fn remove_item(&mut self, item: i64) {
        if let Some(docs) = self.docs_por_item.remove(&item) {
            for d in docs {
                if let Some(doc) = self.documentos.get_mut(&d) {
                    if let Some(p) = doc.itens.iter().position(|&x| x == item) {
                        doc.itens.remove(p);
                    }
                }
            }
        }
        self.itens.remove(&item);
    }

    pub fn lista_documentos(&self) -> Vec<i64> {
        self.documentos.keys().copied().collect()
    }

    pub fn lista_itens(&self) -> Vec<i64> {
        self.itens.keys().copied().collect()
    }

    pub fn quantidade_documentos(&self) -> usize {
        self.documentos.len()
    }

    pub fn quantidade_itens(&self) -> usize {
        self.itens.len()
    }

    pub fn citacoes(&self, doc: i64) -> i64 {
        self.documentos.get(&doc).map(|d| d.citacoes).unwrap_or(0)
    }

    pub fn itens_do_documento(&self, doc: i64) -> &[i64] {
        self.documentos.get(&doc).map(|d| d.itens.as_slice()).unwrap_or(&[])
    }

    pub fn documentos_do_item(&self, item: i64) -> &[i64] {
        self.docs_por_item.get(&item).map(|v| v.as_slice()).unwrap_or(&[])
    }

    pub fn frequencia_item(&self, item: i64) -> usize {
        self.docs_por_item.get(&item).map(|v| v.len()).unwrap_or(0)
    }

    /// Número de itens do documento (frequência documental do acoplamento).
    pub fn frequencia_documento_item(&self, doc: i64) -> usize {
        self.documentos.get(&doc).map(|d| d.itens.len()).unwrap_or(0)
    }

    pub fn filtra_itens_por_frequencia(&mut self, minimo: usize) {
        for item in self.lista_itens() {
            if self.frequencia_item(item) < minimo {
                self.remove_item(item);
            }
        }
    }
}

/// Itens de alto nível (autor ou periódico) com seus documentos (`aggregate.py`).
#[derive(Clone, Debug, Default)]
pub struct Agregado {
    pub altos: BTreeMap<i64, String>,
    pub documentos: BTreeMap<i64, Vec<i64>>,
}

impl Agregado {
    pub fn adiciona(&mut self, alto: i64, rotulo: &str, doc: i64) {
        if !self.altos.contains_key(&alto) {
            self.altos.insert(alto, rotulo.to_string());
            self.documentos.insert(alto, Vec::new());
        }
        let v = self.documentos.get_mut(&alto).unwrap();
        if !v.contains(&doc) {
            v.push(doc);
        }
    }

    pub fn lista_alto_nivel(&self) -> Vec<i64> {
        self.altos.keys().copied().collect()
    }

    pub fn frequencia_documento_item(&self, alto: i64) -> usize {
        self.documentos.get(&alto).map(|v| v.len()).unwrap_or(0)
    }
}
