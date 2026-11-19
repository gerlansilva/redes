//! Exportação de cenas para SVG e PNG.

use crate::cena::Cena;
use std::path::Path;
use std::sync::Arc;

pub fn salvar_svg(cena: &Cena, caminho: &Path) -> Result<(), String> {
    std::fs::write(caminho, cena.para_svg()).map_err(|e| format!("Não foi possível gravar o SVG: {e}"))
}

/// Rasteriza o SVG da cena (escala 2x, nítido em telas Retina).
pub fn png_bytes(cena: &Cena, escala: f32) -> Result<Vec<u8>, String> {
    let svg = cena.para_svg();
    let mut opt = resvg::usvg::Options::default();
    Arc::make_mut(&mut opt.fontdb).load_system_fonts();
    let arvore = resvg::usvg::Tree::from_str(&svg, &opt).map_err(|e| format!("SVG inválido: {e}"))?;
    let w = (cena.largura * escala).ceil().max(1.0) as u32;
    let h = (cena.altura * escala).ceil().max(1.0) as u32;
    let mut pix = resvg::tiny_skia::Pixmap::new(w, h).ok_or("Tamanho de imagem inválido")?;
    resvg::render(&arvore, resvg::tiny_skia::Transform::from_scale(escala, escala), &mut pix.as_mut());
    pix.encode_png().map_err(|e| format!("Falha ao codificar PNG: {e}"))
}

pub fn salvar_png(cena: &Cena, caminho: &Path) -> Result<(), String> {
    let b = png_bytes(cena, 2.0)?;
    std::fs::write(caminho, b).map_err(|e| format!("Não foi possível gravar o PNG: {e}"))
}

#[cfg(test)]
mod testes {
    use super::*;
    use crate::backend::{mock::Demonstracao, Backend};
    use crate::desenho;
    use crate::modelo::Parametros;

    #[test]
    fn png_valido_com_dimensoes() {
        let mut d = Demonstracao::default();
        d.abrir_demonstracao().unwrap();
        let r = d.executar(&Parametros::default()).unwrap();
        let cena = desenho::estrategico(&r, 400.0, 300.0);
        let b = png_bytes(&cena, 1.0).unwrap();
        assert_eq!(&b[..8], &[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A]);
        // Largura e altura no cabeçalho IHDR.
        assert_eq!(u32::from_be_bytes(b[16..20].try_into().unwrap()), 400);
        assert_eq!(u32::from_be_bytes(b[20..24].try_into().unwrap()), 300);
    }

    #[test]
    fn grava_arquivos() {
        let dir = std::env::temp_dir().join(format!("redes_app_teste_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let mut d = Demonstracao::default();
        d.abrir_demonstracao().unwrap();
        let r = d.executar(&Parametros::default()).unwrap();
        let cena = desenho::rede(&r, 400.0, 300.0);
        salvar_svg(&cena, &dir.join("a.svg")).unwrap();
        salvar_png(&cena, &dir.join("a.png")).unwrap();
        assert!(std::fs::metadata(dir.join("a.svg")).unwrap().len() > 100);
        assert!(std::fs::metadata(dir.join("a.png")).unwrap().len() > 100);
        let _ = std::fs::remove_dir_all(dir);
    }
}

/// Rasteriza um SVG qualquer para RGBA (usado para o logotipo na interface).
pub fn svg_para_rgba(svg: &str, largura: u32, altura: u32) -> Result<Vec<u8>, String> {
    let opt = resvg::usvg::Options::default();
    let arvore = resvg::usvg::Tree::from_str(svg, &opt).map_err(|e| e.to_string())?;
    let mut pix = resvg::tiny_skia::Pixmap::new(largura, altura).ok_or("tamanho inválido")?;
    let t = arvore.size();
    let tr = resvg::tiny_skia::Transform::from_scale(largura as f32 / t.width(), altura as f32 / t.height());
    resvg::render(&arvore, tr, &mut pix.as_mut());
    // Converte de alfa pré-multiplicado para direto, como o egui espera.
    let mut v = pix.take();
    for p in v.chunks_exact_mut(4) {
        let a = p[3] as u32;
        if a > 0 && a < 255 {
            for c in &mut p[..3] {
                *c = ((*c as u32 * 255 + a / 2) / a).min(255) as u8;
            }
        }
    }
    Ok(v)
}

#[cfg(test)]
mod testes_logo {
    use super::*;

    #[test]
    fn logo_rasteriza() {
        let v = svg_para_rgba(include_str!("../assets/logo-mark.svg"), 64, 64).unwrap();
        assert_eq!(v.len(), 64 * 64 * 4);
        assert!(v.chunks_exact(4).any(|p| p[3] > 0));
    }
}
