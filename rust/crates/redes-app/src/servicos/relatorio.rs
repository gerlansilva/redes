//! Geração de relatório (documento com as análises do projeto).

use super::EM_BREVE;
use crate::modelo::{InfoProjeto, Parametros, Resultado};
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FormatoRelatorio {
    Html,
    Pdf,
    Docx,
}

impl FormatoRelatorio {
    pub fn rotulo(self) -> &'static str {
        match self {
            FormatoRelatorio::Html => "HTML",
            FormatoRelatorio::Pdf => "PDF",
            FormatoRelatorio::Docx => "Word (.docx)",
        }
    }

    pub fn extensao(self) -> &'static str {
        match self {
            FormatoRelatorio::Html => "html",
            FormatoRelatorio::Pdf => "pdf",
            FormatoRelatorio::Docx => "docx",
        }
    }
}

pub struct PedidoRelatorio<'a> {
    pub info: &'a InfoProjeto,
    pub parametros: &'a Parametros,
    pub resultado: &'a Resultado,
    pub formato: FormatoRelatorio,
}

pub trait Relatorio: Send {
    fn disponivel(&self) -> bool;
    fn formatos(&self) -> Vec<FormatoRelatorio>;
    /// Grava o relatório em `destino` e devolve o caminho final.
    fn gerar(&self, pedido: &PedidoRelatorio<'_>, destino: &Path) -> Result<PathBuf, String>;
}

/// Stub da fase 1.
pub struct RelatorioEmBreve;

impl Relatorio for RelatorioEmBreve {
    fn disponivel(&self) -> bool {
        false
    }

    fn formatos(&self) -> Vec<FormatoRelatorio> {
        vec![FormatoRelatorio::Html, FormatoRelatorio::Pdf, FormatoRelatorio::Docx]
    }

    fn gerar(&self, _p: &PedidoRelatorio<'_>, _d: &Path) -> Result<PathBuf, String> {
        Err(format!("Relatório: {}.", EM_BREVE.to_lowercase()))
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn stub_indisponivel() {
        let s = RelatorioEmBreve;
        assert!(!s.disponivel());
        let info = InfoProjeto { nome: "x".into(), caminho: String::new(), documentos: 0, periodos: vec![] };
        let (par, r) = (Parametros::default(), Resultado::default());
        let pedido = PedidoRelatorio { info: &info, parametros: &par, resultado: &r, formato: FormatoRelatorio::Html };
        assert!(s.gerar(&pedido, Path::new("/tmp/x.html")).is_err());
        assert_eq!(FormatoRelatorio::Docx.extensao(), "docx");
    }
}
