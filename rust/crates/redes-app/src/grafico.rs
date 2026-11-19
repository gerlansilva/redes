//! Gráfico interativo (rede e diagrama estratégico): zoom, pan, dicas, clique e
//! rótulos por nível de detalhe. A matemática da câmera fica em `vista`; aqui
//! ficam a entrada do egui e a pintura.

use crate::app::{Aba, Estado, VistaAba};
use crate::cena::{Acerto, Alvo, Ancora, Cena, Lugar, Prim, Rotulo};
use crate::painel;
use crate::tema::{self, *};
use crate::telas::{botao_secundario, cartao};
use crate::vista::{fator_roda, Vista};
use eframe::egui::{self, Align, Align2, Color32, CursorIcon, FontId, Layout, Margin, Pos2, Rect, RichText, Sense, Stroke, Vec2};

const MARGEM_AJUSTE: f32 = 16.0;
const PASSO_BOTAO: f32 = 1.25;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Colocado {
    pub indice: usize,
    pub rect: Rect,
}

/// Decide quais rótulos aparecem: os de maior prioridade primeiro, só se o
/// elemento ficou grande o bastante na tela e se não cobrem outro já colocado.
/// `tela` é o tamanho do gráfico; `medir` devolve (largura, altura) do texto.
pub fn colocar_rotulos(cena: &Cena, vista: &Vista, tela: (f32, f32), medir: &mut dyn FnMut(&Rotulo, f32) -> (f32, f32)) -> Vec<Colocado> {
    let area = Rect::from_min_size(Pos2::ZERO, Vec2::new(tela.0, tela.1));
    let mut ordem: Vec<usize> = (0..cena.rotulos.len()).collect();
    ordem.sort_by(|&a, &b| cena.rotulos[b].prioridade.partial_cmp(&cena.rotulos[a].prioridade).unwrap_or(std::cmp::Ordering::Equal));
    let esc = vista.escala_texto();
    let mut postos: Vec<Colocado> = Vec::new();
    for i in ordem {
        let l = &cena.rotulos[i];
        let raio_px = l.raio * vista.zoom;
        if raio_px < l.min_px {
            continue;
        }
        let a = vista.para_tela(l.pos);
        let a = Pos2::new(a.0, a.1);
        if !area.expand(raio_px + 4.0).contains(a) {
            continue;
        }
        let tam = l.tam * esc;
        let (w, h) = medir(l, tam);
        let rect = match l.lugar {
            Lugar::Dentro => {
                if w > raio_px * 1.7 {
                    continue;
                }
                Rect::from_center_size(a, Vec2::new(w, h))
            }
            Lugar::Acima => Rect::from_min_size(Pos2::new(a.x - w / 2.0, a.y - h - 3.0), Vec2::new(w, h)),
            Lugar::Direita => Rect::from_min_size(Pos2::new(a.x + raio_px + 3.0, a.y - h / 2.0), Vec2::new(w, h)),
        };
        if rect.min.x < area.min.x || rect.min.y < area.min.y || rect.max.x > area.max.x || rect.max.y > area.max.y {
            continue;
        }
        let folga = rect.expand(2.0);
        if postos.iter().any(|p| p.rect.intersects(folga)) {
            continue;
        }
        postos.push(Colocado { indice: i, rect });
    }
    postos
}

fn cor32(c: [u8; 4]) -> Color32 {
    // Pré-multiplicação simples em sRGB, o mesmo resultado do SVG (o egui, por padrão,
    // pré-multiplica de forma "gama-correta" e clareia cores translúcidas).
    let a = c[3] as u32;
    let m = |v: u8| ((v as u32 * a + 127) / 255) as u8;
    Color32::from_rgba_premultiplied(m(c[0]), m(c[1]), m(c[2]), c[3])
}

fn fonte(tam: f32, negrito: bool) -> FontId {
    if negrito { FontId::new(tam, tema::negrito()) } else { FontId::proportional(tam) }
}

/// Pinta as primitivas da cena com a vista dada; `rect` é a área do gráfico na janela.
pub fn pintar_cena(p: &egui::Painter, rect: Rect, vista: &Vista, cena: &Cena) {
    let o = rect.min;
    let pt = |q: (f32, f32)| {
        let t = vista.para_tela(q);
        Pos2::new(o.x + t.0, o.y + t.1)
    };
    let esc_linha = vista.zoom.powf(0.6).clamp(0.5, 3.0);
    let esc_texto = vista.escala_texto();
    let vis = rect.expand(40.0);
    for prim in &cena.prims {
        match prim {
            Prim::Circulo { c, r, preench, borda, .. } => {
                let (ce, rr) = (pt(*c), r * vista.zoom);
                if !vis.intersects(Rect::from_center_size(ce, Vec2::splat(rr * 2.0))) {
                    continue;
                }
                if let Some(f) = preench {
                    p.circle_filled(ce, rr, cor32(*f));
                }
                if let Some((cb, w)) = borda {
                    p.circle_stroke(ce, rr, Stroke::new(w * esc_linha, cor32(*cb)));
                }
            }
            Prim::Linha { a, b, cor, larg, tracejada } => {
                let (pa, pb) = (pt(*a), pt(*b));
                if !vis.intersects(Rect::from_two_pos(pa, pb)) {
                    continue;
                }
                let st = Stroke::new(larg * esc_linha, cor32(*cor));
                if *tracejada {
                    p.extend(egui::Shape::dashed_line(&[pa, pb], st, 6.0, 4.0));
                } else {
                    p.line_segment([pa, pb], st);
                }
            }
            Prim::Retangulo { min, max, preench, borda } => {
                let r = Rect::from_two_pos(pt(*min), pt(*max));
                if !vis.intersects(r) {
                    continue;
                }
                if let Some(f) = preench {
                    p.rect_filled(r, 0.0, cor32(*f));
                }
                if let Some((cb, w)) = borda {
                    p.rect_stroke(r, 0.0, Stroke::new(w * esc_linha, cor32(*cb)), egui::StrokeKind::Inside);
                }
            }
            Prim::Texto { pos, texto, tam, cor, ancora, negrito, vertical } => {
                let c = cor32(*cor);
                let f = fonte(tam * esc_texto, *negrito);
                let q = pt(*pos);
                if !vis.expand(200.0).contains(q) {
                    continue;
                }
                if *vertical {
                    let galley = p.layout_no_wrap(texto.clone(), f, c);
                    let (w, h) = (galley.size().x, galley.size().y);
                    p.add(egui::epaint::TextShape::new(Pos2::new(q.x - h / 2.0, q.y + w / 2.0), galley, c).with_angle(-std::f32::consts::FRAC_PI_2));
                } else {
                    let al = match ancora {
                        Ancora::Esquerda => Align2::LEFT_CENTER,
                        Ancora::Centro => Align2::CENTER_CENTER,
                        Ancora::Direita => Align2::RIGHT_CENTER,
                    };
                    p.text(q, al, texto, f, c);
                }
            }
        }
    }
}

fn pintar_rotulos(p: &egui::Painter, rect: Rect, cena: &Cena, vista: &Vista, postos: &[Colocado]) {
    let esc = vista.escala_texto();
    for c in postos {
        let l = &cena.rotulos[c.indice];
        let r = c.rect.translate(rect.min.to_vec2());
        if l.lugar != Lugar::Dentro {
            p.rect_filled(r.expand(2.0), 3.0, Color32::from_rgba_unmultiplied(255, 255, 255, 215));
        }
        p.text(r.center(), Align2::CENTER_CENTER, &l.texto, fonte(l.tam * esc, l.negrito), cor32(l.cor));
    }
}

fn anel(p: &egui::Painter, rect: Rect, vista: &Vista, cena: &Cena, alvo: Alvo, cor: Color32, largura: f32) {
    for prim in &cena.prims {
        if let Prim::Circulo { c, r, alvo: Some(a), .. } = prim {
            if *a == alvo {
                let t = vista.para_tela(*c);
                p.circle_stroke(Pos2::new(rect.min.x + t.0, rect.min.y + t.1), r * vista.zoom + 2.5, Stroke::new(largura, cor));
            }
        }
    }
}

enum PedidoZoom {
    Mais,
    Menos,
    Ajustar,
}

fn barra(ui: &mut egui::Ui, percentual: f32) -> Option<PedidoZoom> {
    let mut pedido = None;
    ui.horizontal(|ui| {
        let b = |ui: &mut egui::Ui, t: &str| ui.add(egui::Button::new(RichText::new(t).size(16.0)).min_size(Vec2::new(32.0, 28.0)));
        if b(ui, "−").on_hover_text("Reduzir (tecla -)").clicked() {
            pedido = Some(PedidoZoom::Menos);
        }
        if b(ui, "+").on_hover_text("Ampliar (tecla +)").clicked() {
            pedido = Some(PedidoZoom::Mais);
        }
        if botao_secundario(ui, "Ajustar").on_hover_text("Enquadrar tudo (tecla 0)").clicked() {
            pedido = Some(PedidoZoom::Ajustar);
        }
        ui.label(RichText::new(format!("{:.0}%", percentual)).size(12.0).color(TINTA_FRACA));
        ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
            ui.label(RichText::new("Roda ou pinça: zoom · arrastar: mover · clique num tema: detalhes").size(11.5).color(TINTA_SUAVE));
        });
    });
    pedido
}

/// Desenha o gráfico da aba atual (rede, diagrama estratégico ou análise de serviço).
pub fn painel_grafico(ui: &mut egui::Ui, s: &mut Estado) {
    let aba: Aba = s.aba;
    let cena = match s.cena(aba) {
        Ok(c) => c,
        Err(e) => {
            cartao().show(ui, |ui| {
                ui.set_min_size(ui.available_size() - Vec2::new(2.0, 2.0));
                ui.label(RichText::new(e).color(TINTA_FRACA));
            });
            return;
        }
    };
    let mundo = (cena.largura, cena.altura);
    cartao().inner_margin(Margin::same(8)).show(ui, |ui| {
        ui.style_mut().interaction.tooltip_delay = 0.0;
        let atual = s.vistas.get(&aba).map(|v| v.vista.zoom);
        let ref_zoom = atual.map(|z| z / Vista::ajustada(mundo, s.vistas[&aba].tela, MARGEM_AJUSTE).zoom.max(1e-6)).unwrap_or(1.0);
        let pedido = barra(ui, ref_zoom * 100.0);
        let disp = ui.available_size();
        let (rect, resp) = ui.allocate_exact_size(Vec2::new(disp.x, (disp.y - 4.0).max(200.0)), Sense::click_and_drag());
        let tela = (rect.width(), rect.height());
        let ajustada = Vista::ajustada(mundo, tela, MARGEM_AJUSTE);
        let geracao = 0;
        let va = s.vistas.entry(aba).or_insert(VistaAba { vista: ajustada, auto: true, geracao, tela });
        if va.auto && va.tela != tela {
            va.vista = ajustada;
        }
        va.tela = tela;
        let centro = (tela.0 / 2.0, tela.1 / 2.0);

        // Entrada: botões, teclado, roda, pinça, arrastar.
        match pedido {
            Some(PedidoZoom::Mais) => {
                va.vista.zoom_em(centro, PASSO_BOTAO);
                va.auto = false;
            }
            Some(PedidoZoom::Menos) => {
                va.vista.zoom_em(centro, 1.0 / PASSO_BOTAO);
                va.auto = false;
            }
            Some(PedidoZoom::Ajustar) => {
                va.vista = ajustada;
                va.auto = true;
            }
            None => {}
        }
        if let Some(z) = s.zoom_inicial.take() {
            va.vista.zoom_em(centro, z);
            va.auto = false;
        }
        let local = |p: Pos2| (p.x - rect.min.x, p.y - rect.min.y);
        if resp.hovered() {
            let (zoom_gesto, eventos, teclas) = ui.input(|i| {
                let mais = i.key_pressed(egui::Key::Plus) || i.key_pressed(egui::Key::Equals);
                let menos = i.key_pressed(egui::Key::Minus);
                let zero = i.key_pressed(egui::Key::Num0);
                (i.zoom_delta(), i.raw.events.clone(), (mais, menos, zero))
            });
            let ancora = ui.input(|i| i.pointer.hover_pos()).map(local).unwrap_or(centro);
            if (zoom_gesto - 1.0).abs() > 1e-4 {
                va.vista.zoom_em(ancora, zoom_gesto);
                va.auto = false;
            }
            for e in eventos {
                if let egui::Event::MouseWheel { unit, delta, modifiers } = e {
                    if modifiers.ctrl || modifiers.command {
                        continue; // já contado em zoom_delta
                    }
                    match unit {
                        egui::MouseWheelUnit::Line => va.vista.zoom_em(ancora, fator_roda(delta.y, true)),
                        egui::MouseWheelUnit::Page => va.vista.zoom_em(ancora, fator_roda(delta.y * 10.0, true)),
                        // Gesto de dois dedos no trackpad: desloca.
                        egui::MouseWheelUnit::Point => va.vista.deslocar((delta.x, delta.y)),
                    }
                    va.auto = false;
                }
            }
            match teclas {
                (true, _, _) => {
                    va.vista.zoom_em(centro, PASSO_BOTAO);
                    va.auto = false;
                }
                (_, true, _) => {
                    va.vista.zoom_em(centro, 1.0 / PASSO_BOTAO);
                    va.auto = false;
                }
                (_, _, true) => {
                    va.vista = ajustada;
                    va.auto = true;
                }
                _ => {}
            }
        }
        if resp.dragged_by(egui::PointerButton::Primary) || resp.dragged_by(egui::PointerButton::Middle) {
            let d = resp.drag_delta();
            va.vista.deslocar((d.x, d.y));
            va.auto = false;
            ui.ctx().set_cursor_icon(CursorIcon::Grabbing);
        } else if resp.hovered() {
            ui.ctx().set_cursor_icon(CursorIcon::Grab);
        }
        if let Some(g) = s.foco.take() {
            if let Some(Prim::Circulo { c, r, .. }) =
                cena.prims.iter().find(|p| matches!(p, Prim::Circulo { alvo: Some(Alvo::Grupo(i)), .. } if *i == g))
            {
                let z = (tela.0.min(tela.1) * 0.2 / r.max(1.0)).clamp(va.vista.zoom, 20.0);
                va.vista.centralizar(*c, tela, Some(z));
                va.auto = false;
            }
        }
        va.vista.limitar(mundo, tela, 80.0);
        let vista = va.vista;

        // Alvo sob o ponteiro e clique.
        let tol = 3.0 / vista.zoom;
        let sob: Option<Acerto<'_>> = resp
            .hover_pos()
            .filter(|_| !resp.dragged())
            .and_then(|p| cena.acertar(vista.para_mundo(local(p)), tol));
        if resp.clicked() {
            let alvo = resp.interact_pointer_pos().and_then(|p| cena.acertar(vista.para_mundo(local(p)), tol)).and_then(|a| a.alvo);
            let grupo = alvo.and_then(|a| match a {
                Alvo::Grupo(g) => Some(g),
                Alvo::No(n) => s.resultado.as_ref().and_then(|r| r.nos.get(n)).map(|n| n.grupo),
            });
            s.selecionar_grupo(grupo);
        }
        if resp.double_clicked() {
            if let Some(Alvo::Grupo(g)) = resp.interact_pointer_pos().and_then(|p| cena.acertar(vista.para_mundo(local(p)), tol)).and_then(|a| a.alvo) {
                s.foco = Some(g);
                s.selecionar_grupo(Some(g));
            }
        }

        // Pintura.
        let p = ui.painter_at(rect);
        p.rect_filled(rect, 6.0, BRANCO);
        pintar_cena(&p, rect, &vista, &cena);
        if let Some(g) = s.selecao {
            anel(&p, rect, &vista, &cena, Alvo::Grupo(g), AZUL, 3.0);
        }
        if let Some(a) = sob.as_ref().and_then(|a| a.alvo) {
            anel(&p, rect, &vista, &cena, a, ROXO, 2.0);
        }
        let postos = {
            let ctx = ui.ctx().clone();
            let mut medir = |l: &Rotulo, tam: f32| {
                let g = ctx.fonts(|f| f.layout_no_wrap(l.texto.clone(), fonte(tam, l.negrito), Color32::BLACK));
                (g.size().x, g.size().y)
            };
            colocar_rotulos(&cena, &vista, tela, &mut medir)
        };
        pintar_rotulos(&p, rect, &cena, &vista, &postos);

        if let (Some(a), Some(r)) = (sob, s.resultado.as_ref()) {
            let (dica, alvo) = (a.dica.to_string(), a.alvo);
            resp.on_hover_ui_at_pointer(|ui| painel::dica(ui, r, alvo, &dica));
        }
    });
}

#[cfg(test)]
mod testes {
    use super::*;
    use crate::cena::Cena;

    fn rot(pos: (f32, f32), texto: &str, prio: f32, raio: f32, lugar: Lugar) -> Rotulo {
        Rotulo { pos, texto: texto.into(), tam: 10.0, cor: [0, 0, 0, 255], negrito: false, lugar, prioridade: prio, raio, min_px: 6.0, alvo: None }
    }

    fn medir(l: &Rotulo, tam: f32) -> (f32, f32) {
        (l.texto.chars().count() as f32 * tam * 0.6, tam * 1.2)
    }

    fn cena(rs: Vec<Rotulo>) -> Cena {
        let mut c = Cena::nova(1000.0, 800.0);
        c.rotulos = rs;
        c
    }

    #[test]
    fn prioridade_vence_a_colisao() {
        let c = cena(vec![
            rot((100.0, 100.0), "baixa prioridade", 1.0, 10.0, Lugar::Direita),
            rot((105.0, 100.0), "alta prioridade", 5.0, 10.0, Lugar::Direita),
        ]);
        let v = Vista::default();
        let p = colocar_rotulos(&c, &v, (1000.0, 800.0), &mut medir);
        assert_eq!(p.len(), 1);
        assert_eq!(p[0].indice, 1);
    }

    #[test]
    fn elemento_pequeno_na_tela_nao_ganha_rotulo_e_o_zoom_revela() {
        let c = cena(vec![rot((100.0, 100.0), "tema", 1.0, 4.0, Lugar::Direita)]);
        let mut v = Vista::default();
        v.zoom = 1.0;
        assert!(colocar_rotulos(&c, &v, (1000.0, 800.0), &mut medir).is_empty());
        v.zoom_em((0.0, 0.0), 2.0);
        assert_eq!(colocar_rotulos(&c, &v, (1000.0, 800.0), &mut medir).len(), 1);
    }

    #[test]
    fn fora_da_tela_nao_entra() {
        let c = cena(vec![rot((5000.0, 100.0), "longe", 1.0, 10.0, Lugar::Acima)]);
        assert!(colocar_rotulos(&c, &Vista::default(), (800.0, 600.0), &mut medir).is_empty());
    }

    #[test]
    fn numero_dentro_so_se_couber() {
        let c = cena(vec![rot((100.0, 100.0), "123456", 1.0, 10.0, Lugar::Dentro)]);
        let mut v = Vista::default();
        assert!(colocar_rotulos(&c, &v, (800.0, 600.0), &mut medir).is_empty());
        v.zoom_em((0.0, 0.0), 6.0);
        assert_eq!(colocar_rotulos(&c, &v, (2000.0, 2000.0), &mut medir).len(), 1);
    }

    #[test]
    fn centenas_de_rotulos_ficam_sem_sobreposicao() {
        let rs: Vec<Rotulo> = (0..600)
            .map(|i| rot(((i % 30) as f32 * 30.0 + 20.0, (i / 30) as f32 * 35.0 + 20.0), &format!("tema numero {i}"), (i % 17) as f32, 8.0, Lugar::Direita))
            .collect();
        let c = cena(rs);
        let v = Vista::default();
        let p = colocar_rotulos(&c, &v, (1000.0, 800.0), &mut medir);
        assert!(!p.is_empty() && p.len() < 600);
        for i in 0..p.len() {
            for j in i + 1..p.len() {
                assert!(!p[i].rect.intersects(p[j].rect), "{i} x {j}");
            }
        }
    }
}
