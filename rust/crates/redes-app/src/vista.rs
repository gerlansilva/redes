//! Câmera 2D do gráfico: zoom e deslocamento (pan), sem depender do egui.
//!
//! Coordenadas de tela são locais ao retângulo do gráfico (origem no canto
//! superior esquerdo dele); coordenadas de mundo são as da `Cena`.

pub type P = (f32, f32);

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Vista {
    pub zoom: f32,
    /// Posição na tela da origem do mundo.
    pub desloc: P,
}

pub const ZOOM_MIN: f32 = 0.05;
pub const ZOOM_MAX: f32 = 80.0;

impl Default for Vista {
    fn default() -> Self {
        Vista { zoom: 1.0, desloc: (0.0, 0.0) }
    }
}

impl Vista {
    /// Enquadra a cena inteira, centralizada, com uma margem em pixels.
    pub fn ajustada(mundo: P, tela: P, margem: f32) -> Vista {
        let dw = (tela.0 - 2.0 * margem).max(10.0);
        let dh = (tela.1 - 2.0 * margem).max(10.0);
        let z = (dw / mundo.0.max(1.0)).min(dh / mundo.1.max(1.0)).clamp(ZOOM_MIN, ZOOM_MAX);
        Vista { zoom: z, desloc: ((tela.0 - mundo.0 * z) / 2.0, (tela.1 - mundo.1 * z) / 2.0) }
    }

    pub fn para_tela(&self, p: P) -> P {
        (self.desloc.0 + p.0 * self.zoom, self.desloc.1 + p.1 * self.zoom)
    }

    pub fn para_mundo(&self, p: P) -> P {
        ((p.0 - self.desloc.0) / self.zoom, (p.1 - self.desloc.1) / self.zoom)
    }

    /// Multiplica o zoom mantendo fixo o ponto de tela `ancora`.
    pub fn zoom_em(&mut self, ancora: P, fator: f32) {
        if !fator.is_finite() || fator <= 0.0 {
            return;
        }
        let mundo = self.para_mundo(ancora);
        self.zoom = (self.zoom * fator).clamp(ZOOM_MIN, ZOOM_MAX);
        self.desloc = (ancora.0 - mundo.0 * self.zoom, ancora.1 - mundo.1 * self.zoom);
    }

    pub fn deslocar(&mut self, d: P) {
        self.desloc.0 += d.0;
        self.desloc.1 += d.1;
    }

    /// Leva o ponto de mundo para o centro da tela, com o zoom pedido (se houver).
    pub fn centralizar(&mut self, mundo: P, tela: P, zoom: Option<f32>) {
        if let Some(z) = zoom {
            self.zoom = z.clamp(ZOOM_MIN, ZOOM_MAX);
        }
        self.desloc = (tela.0 / 2.0 - mundo.0 * self.zoom, tela.1 / 2.0 - mundo.1 * self.zoom);
    }

    /// Impede de perder a cena de vista: pelo menos `minimo` pixels dela ficam visíveis.
    pub fn limitar(&mut self, mundo: P, tela: P, minimo: f32) {
        let (w, h) = (mundo.0 * self.zoom, mundo.1 * self.zoom);
        let m = minimo.min(w).min(h).min(tela.0).min(tela.1);
        self.desloc.0 = self.desloc.0.clamp(m - w, tela.0 - m);
        self.desloc.1 = self.desloc.1.clamp(m - h, tela.1 - m);
    }

    /// Escala de texto na tela: cresce devagar com o zoom, para os rótulos ficarem legíveis.
    pub fn escala_texto(&self) -> f32 {
        self.zoom.sqrt().clamp(0.8, 1.5)
    }
}

/// Fator de zoom de um passo da roda do mouse (linhas ou pixels).
pub fn fator_roda(delta_y: f32, em_linhas: bool) -> f32 {
    let passo = if em_linhas { delta_y * 0.12 } else { delta_y * 0.0025 };
    passo.clamp(-1.0, 1.0).exp()
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn ajusta_centralizado() {
        let v = Vista::ajustada((1000.0, 500.0), (800.0, 800.0), 20.0);
        assert!((v.zoom - 0.76).abs() < 1e-5);
        let c = v.para_tela((500.0, 250.0));
        assert!((c.0 - 400.0).abs() < 1e-3 && (c.1 - 400.0).abs() < 1e-3);
    }

    #[test]
    fn zoom_mantem_ponto_fixo() {
        let mut v = Vista { zoom: 0.8, desloc: (30.0, 10.0) };
        let alvo = (300.0, 200.0);
        let antes = v.para_mundo(alvo);
        v.zoom_em(alvo, 2.5);
        let depois = v.para_mundo(alvo);
        assert!((antes.0 - depois.0).abs() < 1e-3 && (antes.1 - depois.1).abs() < 1e-3);
        assert!((v.zoom - 2.0).abs() < 1e-5);
    }

    #[test]
    fn zoom_tem_limites() {
        let mut v = Vista::default();
        for _ in 0..50 {
            v.zoom_em((0.0, 0.0), 2.0);
        }
        assert_eq!(v.zoom, ZOOM_MAX);
        for _ in 0..80 {
            v.zoom_em((0.0, 0.0), 0.5);
        }
        assert_eq!(v.zoom, ZOOM_MIN);
        v.zoom_em((0.0, 0.0), f32::NAN);
        assert_eq!(v.zoom, ZOOM_MIN);
    }

    #[test]
    fn ida_e_volta() {
        let v = Vista { zoom: 3.0, desloc: (-40.0, 25.0) };
        let p = (12.5, 77.0);
        let q = v.para_mundo(v.para_tela(p));
        assert!((p.0 - q.0).abs() < 1e-4 && (p.1 - q.1).abs() < 1e-4);
    }

    #[test]
    fn limitar_nao_deixa_perder_a_cena() {
        let mut v = Vista { zoom: 1.0, desloc: (5000.0, -5000.0) };
        v.limitar((1000.0, 700.0), (800.0, 600.0), 80.0);
        assert_eq!(v.desloc, (720.0, -620.0));
    }

    #[test]
    fn centraliza_ponto() {
        let mut v = Vista::default();
        v.centralizar((100.0, 100.0), (400.0, 300.0), Some(4.0));
        assert_eq!(v.para_tela((100.0, 100.0)), (200.0, 150.0));
    }

    #[test]
    fn roda_simetrica() {
        assert!((fator_roda(1.0, true) * fator_roda(-1.0, true) - 1.0).abs() < 1e-6);
        assert!(fator_roda(40.0, false) > 1.0);
    }
}
