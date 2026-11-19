//! Camada entre a interface e o cálculo.
//!
//! A interface só conhece o trait [`Backend`]. Há duas implementações:
//!
//! * `real::Nucleo` (feature `nucleo`, padrão): chama `redes-core`
//!   (`Projeto::abrir`, `executar`) e converte o resultado;
//! * [`mock::Demonstracao`]: dados fictícios determinísticos, usados nos
//!   testes e quando se compila com `--no-default-features`.
//!
//! O núcleo analisa um período por vez, por isso a interface só oferece
//! "Todos os períodos" quando [`Backend::permite_todos_periodos`] é verdadeiro.

use crate::modelo::{InfoProjeto, Parametros, Resultado};
use std::path::Path;

pub mod mock;
#[cfg(feature = "nucleo")]
pub mod real;

pub trait Backend {
    /// Abre um projeto `.redes` e devolve seus metadados.
    fn abrir(&mut self, caminho: &Path) -> Result<InfoProjeto, String>;
    /// Projeto de demonstração, sem arquivo.
    fn abrir_demonstracao(&mut self) -> Result<InfoProjeto, String>;
    /// Executa a análise com os parâmetros dados.
    fn executar(&self, parametros: &Parametros) -> Result<Resultado, String>;
    /// O núcleo real analisa um período por vez; o mock aceita "todos".
    fn permite_todos_periodos(&self) -> bool {
        true
    }
    /// Rótulo curto para a interface ("dados de demonstração", "núcleo Rust").
    fn origem(&self) -> &'static str;
}

/// Backend padrão do binário.
pub fn padrao() -> Box<dyn Backend> {
    #[cfg(feature = "nucleo")]
    {
        Box::new(real::Nucleo::default())
    }
    #[cfg(not(feature = "nucleo"))]
    {
        Box::new(mock::Demonstracao::default())
    }
}
