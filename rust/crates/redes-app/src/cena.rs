//! Cena 2D independente de janela: uma lista de primitivas que pode ser
//! pintada no egui, serializada em SVG ou rasterizada em PNG. Assim o que se
//! vê na tela é exatamente o que se exporta.

pub type Cor = [u8; 4];

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Ancora {
    Esquerda,
    Centro,
    Direita,
}

/// O que um círculo representa (para clique e destaque na tela).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Alvo {
    Grupo(usize),
    No(usize),
}

/// Onde o rótulo fica em relação ao círculo dono dele.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Lugar {
    Dentro,
    Acima,
    Direita,
}

/// Rótulo gerenciado por nível de detalhe: só aparece na tela quando o elemento
/// de origem fica grande o bastante e o espaço está livre (veja `grafico`).
/// Não entra na exportação, que usa os `Prim::Texto` da cena estática.
#[derive(Clone, Debug, PartialEq)]
pub struct Rotulo {
    pub pos: (f32, f32),
    pub texto: String,
    pub tam: f32,
    pub cor: Cor,
    pub negrito: bool,
    pub lugar: Lugar,
    /// Quanto maior, mais cedo ganha espaço.
    pub prioridade: f32,
    /// Raio, em unidades da cena, do elemento dono do rótulo.
    pub raio: f32,
    /// Raio mínimo em pixels de tela para o rótulo aparecer.
    pub min_px: f32,
    pub alvo: Option<Alvo>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Prim {
    Circulo {
        c: (f32, f32),
        r: f32,
        preench: Option<Cor>,
        borda: Option<(Cor, f32)>,
        dica: Option<String>,
        alvo: Option<Alvo>,
    },
    Linha {
        a: (f32, f32),
        b: (f32, f32),
        cor: Cor,
        larg: f32,
        tracejada: bool,
    },
    Retangulo {
        min: (f32, f32),
        max: (f32, f32),
        preench: Option<Cor>,
        borda: Option<(Cor, f32)>,
    },
    Texto {
        pos: (f32, f32),
        texto: String,
        tam: f32,
        cor: Cor,
        ancora: Ancora,
        negrito: bool,
        /// Rotação de 90 graus anti-horária (rótulo do eixo vertical).
        vertical: bool,
    },
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct Cena {
    pub largura: f32,
    pub altura: f32,
    pub prims: Vec<Prim>,
    /// Rótulos por nível de detalhe (só na tela interativa).
    pub rotulos: Vec<Rotulo>,
}

/// Círculo encontrado sob um ponto.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Acerto<'a> {
    pub dica: &'a str,
    pub alvo: Option<Alvo>,
    pub centro: (f32, f32),
    pub raio: f32,
}

fn esc(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;").replace('"', "&quot;")
}

fn rgb(c: Cor) -> String {
    format!("#{:02X}{:02X}{:02X}", c[0], c[1], c[2])
}

fn op(c: Cor) -> String {
    format!("{:.3}", c[3] as f32 / 255.0)
}

pub const FAMILIA_SVG: &str = "Helvetica Neue, Helvetica, Arial, Inter, sans-serif";

impl Cena {
    pub fn nova(largura: f32, altura: f32) -> Self {
        Cena { largura, altura, prims: Vec::new(), rotulos: Vec::new() }
    }

    pub fn push(&mut self, p: Prim) {
        self.prims.push(p);
    }

    /// Círculo sob o ponto (o de cima vence), com `tol` de folga em unidades da cena.
    pub fn acertar(&self, p: (f32, f32), tol: f32) -> Option<Acerto<'_>> {
        self.prims.iter().rev().find_map(|prim| match prim {
            Prim::Circulo { c, r, dica: Some(d), alvo, .. } => {
                let (dx, dy) = (p.0 - c.0, p.1 - c.1);
                let rr = r + tol;
                if dx * dx + dy * dy <= rr * rr {
                    Some(Acerto { dica: d.as_str(), alvo: *alvo, centro: *c, raio: *r })
                } else {
                    None
                }
            }
            _ => None,
        })
    }

    /// Texto da dica do círculo sob o ponto, se houver.
    pub fn dica_em(&self, p: (f32, f32)) -> Option<&str> {
        self.acertar(p, 0.0).map(|a| a.dica)
    }

    pub fn para_svg(&self) -> String {
        let mut s = String::new();
        s.push_str(&format!(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{w}\" height=\"{h}\" viewBox=\"0 0 {w} {h}\" font-family=\"{f}\">\n",
            w = self.largura, h = self.altura, f = FAMILIA_SVG
        ));
        s.push_str(&format!("<rect width=\"{}\" height=\"{}\" fill=\"#FFFFFF\"/>\n", self.largura, self.altura));
        for p in &self.prims {
            match p {
                Prim::Circulo { c, r, preench, borda, .. } => {
                    let mut a = format!("<circle cx=\"{:.2}\" cy=\"{:.2}\" r=\"{:.2}\"", c.0, c.1, r);
                    match preench {
                        Some(f) => a.push_str(&format!(" fill=\"{}\" fill-opacity=\"{}\"", rgb(*f), op(*f))),
                        None => a.push_str(" fill=\"none\""),
                    }
                    if let Some((cb, w)) = borda {
                        a.push_str(&format!(" stroke=\"{}\" stroke-opacity=\"{}\" stroke-width=\"{:.2}\"", rgb(*cb), op(*cb), w));
                    }
                    a.push_str("/>\n");
                    s.push_str(&a);
                }
                Prim::Linha { a, b, cor, larg, tracejada } => {
                    s.push_str(&format!(
                        "<line x1=\"{:.2}\" y1=\"{:.2}\" x2=\"{:.2}\" y2=\"{:.2}\" stroke=\"{}\" stroke-opacity=\"{}\" stroke-width=\"{:.2}\" stroke-linecap=\"round\"{}/>\n",
                        a.0, a.1, b.0, b.1, rgb(*cor), op(*cor), larg,
                        if *tracejada { " stroke-dasharray=\"6 4\"" } else { "" }
                    ));
                }
                Prim::Retangulo { min, max, preench, borda } => {
                    let mut a = format!(
                        "<rect x=\"{:.2}\" y=\"{:.2}\" width=\"{:.2}\" height=\"{:.2}\"",
                        min.0, min.1, max.0 - min.0, max.1 - min.1
                    );
                    match preench {
                        Some(f) => a.push_str(&format!(" fill=\"{}\" fill-opacity=\"{}\"", rgb(*f), op(*f))),
                        None => a.push_str(" fill=\"none\""),
                    }
                    if let Some((cb, w)) = borda {
                        a.push_str(&format!(" stroke=\"{}\" stroke-opacity=\"{}\" stroke-width=\"{:.2}\"", rgb(*cb), op(*cb), w));
                    }
                    a.push_str("/>\n");
                    s.push_str(&a);
                }
                Prim::Texto { pos, texto, tam, cor, ancora, negrito, vertical } => {
                    let anchor = match ancora {
                        Ancora::Esquerda => "start",
                        Ancora::Centro => "middle",
                        Ancora::Direita => "end",
                    };
                    let y = pos.1 + tam * 0.35;
                    let rot = if *vertical { format!(" transform=\"rotate(-90 {:.2} {:.2})\"", pos.0, pos.1) } else { String::new() };
                    s.push_str(&format!(
                        "<text x=\"{:.2}\" y=\"{:.2}\" font-size=\"{:.1}\" fill=\"{}\" fill-opacity=\"{}\" text-anchor=\"{}\"{}{}>{}</text>\n",
                        pos.0, y, tam, rgb(*cor), op(*cor), anchor,
                        if *negrito { " font-weight=\"700\"" } else { "" },
                        rot, esc(texto)
                    ));
                }
            }
        }
        s.push_str("</svg>\n");
        s
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    fn exemplo() -> Cena {
        let mut c = Cena::nova(100.0, 80.0);
        c.push(Prim::Circulo { c: (10.0, 10.0), r: 5.0, preench: Some([1, 2, 3, 255]), borda: None, dica: Some("a & b".into()), alvo: None });
        c.push(Prim::Texto { pos: (5.0, 5.0), texto: "<x> & \"y\"".into(), tam: 10.0, cor: [0, 0, 0, 255], ancora: Ancora::Centro, negrito: true, vertical: false });
        c
    }

    #[test]
    fn svg_escapa_e_e_xml_valido() {
        let s = exemplo().para_svg();
        assert!(s.contains("&lt;x&gt; &amp; &quot;y&quot;"));
        assert!(s.starts_with("<svg") && s.trim_end().ends_with("</svg>"));
        assert!(s.contains("fill=\"#010203\""));
    }

    #[test]
    fn dica_por_ponto() {
        let c = exemplo();
        assert_eq!(c.dica_em((11.0, 10.0)), Some("a & b"));
        assert_eq!(c.dica_em((50.0, 50.0)), None);
    }
}
