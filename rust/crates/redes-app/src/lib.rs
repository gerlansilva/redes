//! Redes: aplicativo gráfico nativo (egui) para mapeamento científico.
//!
//! A lógica (modelo, layout do grafo, desenho em cena, exportação) fica em
//! módulos independentes da janela para poder ser testada sem abrir nada.

pub mod app;
pub mod backend;
pub mod cena;
pub mod desenho;
pub mod exportar;
pub mod layout;
pub mod modelo;
pub mod tema;
pub mod telas;
