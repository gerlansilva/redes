//! Camada de serviços: o que a interface pede ao restante do sistema.
//!
//! A interface só conhece os traits [`Importador`], [`Analises`] e [`Relatorio`].
//! Hoje todos têm implementação "em breve" (`disponivel() == false`); a fase 2
//! liga `redes-importa`, `redes-analises` e `redes-relatorio` trocando só a
//! construção em [`Servicos::padrao`], sem mexer nas telas.

pub mod analises;
pub mod importador;
pub mod relatorio;

pub use analises::{Analises, AnalisesEmBreve, TipoAnalise};
pub use importador::{
    parse_periodos, Controle, Desfecho, FormatoCorpus, Importador, ImportadorEmBreve, OpcoesImportacao, PeriodoSpec,
    Progresso, Tarefa, TarefaEmThread,
};
pub use relatorio::{FormatoRelatorio, PedidoRelatorio, Relatorio, RelatorioEmBreve};

pub const EM_BREVE: &str = "Em breve";

pub struct Servicos {
    pub importador: Box<dyn Importador>,
    pub analises: Box<dyn Analises>,
    pub relatorio: Box<dyn Relatorio>,
}

impl Servicos {
    /// Serviços ligados no binário. Na fase 2, troque os stubs pelos crates novos aqui.
    pub fn padrao() -> Self {
        Servicos::em_breve()
    }

    pub fn em_breve() -> Self {
        Servicos {
            importador: Box::new(ImportadorEmBreve::default()),
            analises: Box::new(AnalisesEmBreve),
            relatorio: Box::new(RelatorioEmBreve),
        }
    }
}

impl Default for Servicos {
    fn default() -> Self {
        Servicos::padrao()
    }
}
