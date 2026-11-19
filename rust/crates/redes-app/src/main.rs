// Evita abrir o terminal no Windows; não afeta macOS.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use redes_app::{backend, telas::RedesApp};

fn main() -> eframe::Result<()> {
    let opcoes = eframe::NativeOptions {
        viewport: eframe::egui::ViewportBuilder::default()
            .with_title("Redes")
            .with_inner_size([1280.0, 800.0])
            .with_min_inner_size([900.0, 600.0]),
        ..Default::default()
    };
    eframe::run_native(
        "Redes",
        opcoes,
        Box::new(|cc| Ok(Box::new(RedesApp::novo(cc, backend::padrao())))),
    )
}
