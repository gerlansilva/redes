// Evita abrir o terminal no Windows; não afeta macOS.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use redes_app::{backend, telas::RedesApp};

fn main() -> eframe::Result<()> {
    let opcoes = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_title("Redes")
            .with_app_id("br.ufscar.gerlan.redes")
            .with_icon(icone())
            .with_inner_size([1280.0, 800.0])
            .with_min_inner_size([900.0, 600.0]),
        ..Default::default()
    };
    eframe::run_native(
        "Redes",
        opcoes,
        Box::new(|cc| Ok(Box::new(RedesApp::novo(cc, backend_inicial())))),
    )
}

/// REDES_DEMO_GRUPOS=<n> usa dados de demonstração com n agrupamentos (teste de escala).
fn backend_inicial() -> Box<dyn backend::Backend> {
    if let Some(n) = std::env::var("REDES_DEMO_GRUPOS").ok().and_then(|t| t.parse::<usize>().ok()) {
        return Box::new(backend::mock::Demonstracao::com_grupos(n));
    }
    backend::padrao()
}

/// Ícone da janela (Linux e Windows; no macOS vale o Redes.icns do pacote).
fn icone() -> eframe::egui::IconData {
    let px = 256;
    let rgba = redes_app::exportar::svg_para_rgba(include_str!("../assets/logo-mark.svg"), px, px).unwrap_or_else(|_| vec![0; (px * px * 4) as usize]);
    eframe::egui::IconData { rgba, width: px, height: px }
}
