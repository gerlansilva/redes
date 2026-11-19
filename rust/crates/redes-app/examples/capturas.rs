//! Grava PNGs das cenas com dados de demonstração: cargo run --example capturas -- <pasta>
use redes_app::{backend::{mock::Demonstracao, Backend}, desenho, exportar, modelo::Parametros};

fn main() {
    let dir = std::env::args().nth(1).unwrap_or_else(|| ".".into());
    let mut d = Demonstracao::default();
    d.abrir_demonstracao().unwrap();
    let r = d.executar(&Parametros::default()).unwrap();
    exportar::salvar_png(&desenho::rede(&r, 1000.0, 700.0), format!("{dir}/rede.png").as_ref()).unwrap();
    exportar::salvar_png(&desenho::estrategico(&r, 1000.0, 700.0), format!("{dir}/estrategico.png").as_ref()).unwrap();
}
