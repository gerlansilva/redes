//! `redes-core`: núcleo de análise bibliométrica do Redes (porta do Python).
//!
//! ```no_run
//! use redes_core::{Projeto, Parametros, executar};
//! let projeto = Projeto::abrir("exemplo.redes").unwrap();
//! let res = executar(&projeto, &Parametros::default()).unwrap();
//! println!("{}", serde_json::to_string(&res).unwrap());
//! ```

pub mod agrupamento;
pub mod dataset;
pub mod erro;
pub mod medidas;
pub mod parametros;
pub mod pipeline;
pub mod projeto;
pub mod pycompat;
pub mod rede;
pub mod texto;

pub use erro::{Erro, Resultado as ResultadoErro};
pub use parametros::{Algoritmo, Mapeador, Matriz, Parametros, Similaridade, Unidade};
pub use pipeline::{executar, executar_periodo, executar_periodos, Resultado};
pub use projeto::{Periodo, Projeto};
