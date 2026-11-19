//! `redes-relatorio`: gerador do relatório HTML do Redes, em português.
//!
//! Dois formatos, ambos autocontidos e sem JavaScript:
//! - **arquivo único** ([`unico::gera_arquivo_unico`]): capa, sumário, seções 1..N
//!   numeradas ("Figura 6 — …", "Tabela 3 — …"), CSS e SVG embutidos;
//! - **pasta de páginas** ([`pasta::gera_pasta`]): índice, visão geral, uma pasta por
//!   análise com páginas de período e de agrupamento.
//!
//! A entrada é [`dados::DadosRelatorio`] (serde); o adaptador [`adaptador`] a monta
//! a partir do `Resultado` do redes-core.
//!
//! ```no_run
//! use redes_relatorio::{dados::DadosRelatorio, unico};
//! let dados: DadosRelatorio = serde_json::from_str("{}").unwrap();
//! let html = unico::gera_html_unico(&dados);
//! ```

pub mod abnt;
pub mod adaptador;
pub mod css;
pub mod dados;
pub mod metodo;
pub mod pasta;
pub mod qualidade;
pub mod svg;
pub mod texto;
pub mod unico;

pub use dados::DadosRelatorio;

pub const TITULO_DUPLO: &str = "Duplo mapa de áreas das revistas (corpus completo)";
pub const TITULO_SIMILITUDE: &str = "Similitude dos resumos (palavras que aparecem juntas)";
pub const LOGO_SVG: &str = include_str!("../assets/logo.svg");
