//! `redes-core`: núcleo de análise bibliométrica do Redes (porta do Python).
//!
//! ```no_run
//! use redes_core::{Projeto, Parametros, executar};
//! let projeto = Projeto::abrir("exemplo.redes").unwrap();
//! let res = executar(&projeto, &Parametros::default()).unwrap();
//! println!("{}", serde_json::to_string(&res).unwrap());
//! ```

pub mod agrupamento;
pub mod centralidade;
pub mod dataset;
pub mod erro;
pub mod ies;
pub mod longitudinal;
pub mod medidas;
pub mod paises;
pub mod parametros;
pub mod pipeline;
pub mod pivos;
pub mod projeto;
pub mod pycompat;
pub mod qualidade;
pub mod rede;
pub mod rotulos;
mod tabelas;
pub mod texto;

pub use erro::{Erro, Resultado as ResultadoErro};
pub use parametros::{Algoritmo, Extras, Mapeador, Matriz, Parametros, Similaridade, Unidade};
pub use pipeline::{executar, executar_analise, executar_periodo, executar_periodos, Analise, Resultado};
pub use projeto::{Periodo, Projeto};
