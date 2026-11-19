//! Identidade visual do Redes (espelha redes/ui/style.css). Só tema claro.

use crate::cena::Cor;
use eframe::egui::{self, Color32, FontFamily, FontId, Stroke, TextStyle};

pub const AZUL: Color32 = Color32::from_rgb(0x2F, 0x2B, 0xFF);
pub const AZUL_ESCURO: Color32 = Color32::from_rgb(0x0B, 0x1F, 0x66);
pub const ROXO: Color32 = Color32::from_rgb(0x6A, 0x3B, 0xFF);
pub const AMARELO: Color32 = Color32::from_rgb(0xFF, 0xC4, 0x00);
pub const VERDE: Color32 = Color32::from_rgb(0x00, 0xC8, 0x53);
pub const LAVANDA: Color32 = Color32::from_rgb(0xED, 0xEB, 0xFF);
pub const BRANCO: Color32 = Color32::WHITE;
pub const FUNDO: Color32 = Color32::from_rgb(0xF7, 0xF8, 0xFB);
pub const LINHA: Color32 = Color32::from_rgb(0xE9, 0xEC, 0xF2);
pub const LINHA_FORTE: Color32 = Color32::from_rgb(0xDC, 0xE3, 0xF0);
pub const TINTA: Color32 = Color32::from_rgb(0x14, 0x20, 0x4A);
pub const TINTA_FRACA: Color32 = Color32::from_rgb(0x64, 0x74, 0x8B);
pub const TINTA_SUAVE: Color32 = Color32::from_rgb(0x8A, 0x94, 0xA6);

/// Cores dos grupos no grafo e no diagrama (RGB).
pub const PALETA: [[u8; 3]; 8] = [
    [0x2F, 0x2B, 0xFF],
    [0x00, 0xC8, 0x53],
    [0x6A, 0x3B, 0xFF],
    [0xFF, 0xC4, 0x00],
    [0x0B, 0x1F, 0x66],
    [0x00, 0x9E, 0xB8],
    [0xE0, 0x5A, 0x8C],
    [0x8A, 0x94, 0xA6],
];

pub fn cor_grupo(i: usize, alfa: u8) -> Cor {
    let c = PALETA[i % PALETA.len()];
    [c[0], c[1], c[2], alfa]
}

pub fn cor_quadrante(q: crate::modelo::Quadrante) -> Color32 {
    use crate::modelo::Quadrante::*;
    match q {
        Motor => AZUL,
        Nicho => Color32::from_rgb(0x06, 0x76, 0x47),
        Basico => AZUL_ESCURO,
        Emergente => Color32::from_rgb(0xA1, 0x62, 0x07),
    }
}

/// Família em negrito (Inter SemiBold); o egui não tem negrito sintético.
pub fn negrito() -> FontFamily {
    FontFamily::Name("negrito".into())
}

fn instalar_fontes(ctx: &egui::Context) {
    let mut f = egui::FontDefinitions::default();
    f.font_data.insert("inter".into(), std::sync::Arc::new(egui::FontData::from_static(include_bytes!("../assets/fonts/Inter-Regular.otf"))));
    f.font_data.insert("inter-sb".into(), std::sync::Arc::new(egui::FontData::from_static(include_bytes!("../assets/fonts/Inter-SemiBold.otf"))));
    f.families.entry(FontFamily::Proportional).or_default().insert(0, "inter".into());
    f.families.insert(negrito(), vec!["inter-sb".into(), "inter".into()]);
    ctx.set_fonts(f);
}

pub fn aplicar(ctx: &egui::Context) {
    instalar_fontes(ctx);
    let mut v = egui::Visuals::light();
    v.panel_fill = FUNDO;
    v.window_fill = BRANCO;
    v.extreme_bg_color = BRANCO;
    v.override_text_color = Some(TINTA);
    v.hyperlink_color = AZUL;
    v.selection.bg_fill = Color32::from_rgb(0xDD, 0xE4, 0xFF);
    v.selection.stroke = Stroke::new(1.0f32, AZUL);
    let raio = egui::CornerRadius::same(8);
    for w in [
        &mut v.widgets.noninteractive,
        &mut v.widgets.inactive,
        &mut v.widgets.hovered,
        &mut v.widgets.active,
        &mut v.widgets.open,
    ] {
        w.corner_radius = raio;
    }
    v.widgets.noninteractive.bg_stroke = Stroke::new(1.0f32, LINHA);
    v.widgets.inactive.bg_fill = BRANCO;
    v.widgets.inactive.weak_bg_fill = BRANCO;
    v.widgets.inactive.bg_stroke = Stroke::new(1.0f32, LINHA_FORTE);
    v.widgets.hovered.weak_bg_fill = LAVANDA;
    v.widgets.hovered.bg_fill = LAVANDA;
    v.widgets.hovered.bg_stroke = Stroke::new(1.0f32, AZUL);
    v.widgets.active.weak_bg_fill = Color32::from_rgb(0xDD, 0xE4, 0xFF);
    v.widgets.active.bg_stroke = Stroke::new(1.0f32, AZUL);
    ctx.set_visuals(v);

    let mut st = (*ctx.style()).clone();
    st.spacing.item_spacing = egui::vec2(8.0, 8.0);
    st.spacing.button_padding = egui::vec2(12.0, 6.0);
    st.text_styles = [
        (TextStyle::Heading, FontId::new(22.0, FontFamily::Proportional)),
        (TextStyle::Body, FontId::new(13.5, FontFamily::Proportional)),
        (TextStyle::Button, FontId::new(13.5, FontFamily::Proportional)),
        (TextStyle::Small, FontId::new(11.0, FontFamily::Proportional)),
        (TextStyle::Monospace, FontId::new(12.5, FontFamily::Monospace)),
    ]
    .into();
    ctx.set_style(st);
}
