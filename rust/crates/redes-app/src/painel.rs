//! Dica ao passar o mouse e painel lateral com os itens e documentos de um tema.

use crate::app::Estado;
use crate::cena::Alvo;
use crate::desenho::fmt_num;
use crate::modelo::*;
use crate::tema::{self, *};
use eframe::egui::{self, Align, Color32, CornerRadius, Layout, Margin, RichText, Stroke, Vec2};

/// Linhas (rótulo, valor) de um agrupamento.
pub fn metricas(g: &Grupo) -> Vec<(&'static str, String)> {
    let mut v = vec![
        ("Quadrante", g.quadrante.rotulo().to_string()),
        ("Centralidade", format!("{} (posição {})", fmt_num(g.centralidade), fmt_num(g.faixa_c))),
        ("Densidade", format!("{} (posição {})", fmt_num(g.densidade), fmt_num(g.faixa_d))),
        ("Itens", g.tamanho.to_string()),
        ("Documentos", g.documentos.to_string()),
    ];
    if let Some(c) = g.citacoes {
        v.push(("Citações", c.to_string()));
    }
    v
}

/// Conteúdo da dica: tema (nome, quadrante, medidas) ou item (peso e tema).
pub fn dica(ui: &mut egui::Ui, r: &Resultado, alvo: Option<Alvo>, texto: &str) {
    ui.set_max_width(320.0);
    match alvo {
        Some(Alvo::Grupo(i)) if i < r.grupos.len() => {
            let g = &r.grupos[i];
            ui.label(RichText::new(&g.nome).family(tema::negrito()).size(14.0).color(AZUL_ESCURO));
            for (k, v) in metricas(g) {
                ui.label(RichText::new(format!("{k}: {v}")).size(12.0).color(TINTA_FRACA));
            }
            ui.label(RichText::new("Clique para ver itens e documentos").size(11.0).color(TINTA_SUAVE));
        }
        Some(Alvo::No(i)) if i < r.nos.len() => {
            let n = &r.nos[i];
            ui.label(RichText::new(&n.rotulo).family(tema::negrito()).size(14.0).color(AZUL_ESCURO));
            ui.label(RichText::new(format!("Frequência: {:.0}", n.peso)).size(12.0).color(TINTA_FRACA));
            if let Some(g) = r.grupos.get(n.grupo) {
                ui.label(RichText::new(format!("Tema: {}", g.nome)).size(12.0).color(TINTA_FRACA));
            }
            ui.label(RichText::new("Clique para abrir o tema").size(11.0).color(TINTA_SUAVE));
        }
        _ => {
            ui.label(texto);
        }
    }
}

fn lista(ui: &mut egui::Ui, id: &str, altura: f32, n: usize, mut linha: impl FnMut(&mut egui::Ui, usize)) {
    let h = 22.0;
    egui::ScrollArea::vertical().id_salt(id).max_height(altura).auto_shrink([false, true]).drag_to_scroll(false).show_rows(ui, h, n, |ui, faixa| {
        for i in faixa {
            ui.allocate_ui_with_layout(Vec2::new(ui.available_width(), h), Layout::left_to_right(Align::Center), |ui| linha(ui, i));
        }
    });
}

/// Painel à direita com o tema selecionado. Mostra-se só se há seleção.
pub fn lateral(ctx: &egui::Context, s: &mut Estado) {
    let Some(sel) = s.selecao else { return };
    let Some(r) = s.resultado.as_ref() else { return };
    let Some(g) = r.grupos.get(sel) else { return };
    let mut fechar = false;
    let mut focar = false;
    egui::SidePanel::right("detalhe")
        .exact_width(340.0)
        .resizable(false)
        .show_separator_line(false)
        .frame(egui::Frame::new().fill(BRANCO).stroke(Stroke::new(1.0f32, LINHA)).inner_margin(Margin::symmetric(16, 16)))
        .show(ctx, |ui| {
            ui.horizontal(|ui| {
                let (pt, _) = ui.allocate_exact_size(Vec2::splat(12.0), egui::Sense::hover());
                let c = crate::tema::cor_grupo(g.id, 255);
                ui.painter().circle_filled(pt.center(), 6.0, Color32::from_rgb(c[0], c[1], c[2]));
                ui.add(egui::Label::new(RichText::new(&g.nome).family(tema::negrito()).size(17.0).color(AZUL_ESCURO)).wrap());
                ui.with_layout(Layout::right_to_left(Align::Min), |ui| {
                    if ui.add(egui::Button::new("×").frame(false)).on_hover_text("Fechar").clicked() {
                        fechar = true;
                    }
                });
            });
            ui.add_space(4.0);
            egui::Grid::new("metricas").num_columns(2).spacing([12.0, 4.0]).show(ui, |ui| {
                for (k, v) in metricas(g) {
                    ui.label(RichText::new(k).size(12.0).color(TINTA_SUAVE));
                    ui.label(RichText::new(v).size(12.5).color(TINTA));
                    ui.end_row();
                }
            });
            ui.add_space(6.0);
            if ui.add(egui::Button::new(RichText::new("Mostrar no gráfico").color(AZUL)).fill(LAVANDA).stroke(Stroke::NONE).corner_radius(CornerRadius::same(8))).clicked() {
                focar = true;
            }
            ui.add_space(8.0);
            let nos = r.nos_do_grupo(g.id);
            let total = ui.available_height();
            ui.label(RichText::new(format!("ITENS ({})", nos.len())).size(10.5).family(tema::negrito()).color(TINTA_SUAVE));
            lista(ui, "itens", (total * 0.38).max(90.0), nos.len(), |ui, i| {
                let n = nos[i];
                ui.add(egui::Label::new(RichText::new(&n.rotulo).size(12.5)).truncate());
                ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                    ui.label(RichText::new(format!("{:.0}", n.peso)).size(12.0).color(TINTA_FRACA));
                });
            });
            ui.add_space(8.0);
            ui.label(RichText::new(format!("DOCUMENTOS ({})", g.doc_ids.len())).size(10.5).family(tema::negrito()).color(TINTA_SUAVE));
            if g.doc_ids.is_empty() {
                ui.label(RichText::new("Este resultado não traz a lista de documentos.").size(12.0).color(TINTA_FRACA));
            } else {
                let altura = ui.available_height().max(90.0);
                let titulos = &s.titulos;
                lista(ui, "docs", altura, g.doc_ids.len(), |ui, i| {
                    let id = g.doc_ids[i];
                    let t = titulos.get(&id).cloned().unwrap_or_else(|| format!("Documento {id}"));
                    ui.add(egui::Label::new(RichText::new(&t).size(12.5)).truncate()).on_hover_text(t);
                });
            }
        });
    if fechar {
        s.selecionar_grupo(None);
    }
    if focar {
        s.foco = Some(sel);
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use crate::backend::{mock::Demonstracao, Backend};

    #[test]
    fn metricas_incluem_citacoes_so_quando_ha() {
        let mut d = Demonstracao::default();
        d.abrir_demonstracao().unwrap();
        let mut g = d.executar(&Parametros::default()).unwrap().grupos[0].clone();
        assert_eq!(metricas(&g).len(), 6);
        g.citacoes = None;
        let m = metricas(&g);
        assert_eq!(m.len(), 5);
        assert!(m.iter().any(|(k, v)| *k == "Documentos" && *v == g.documentos.to_string()));
    }
}
