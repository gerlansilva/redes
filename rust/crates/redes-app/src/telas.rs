//! Telas em egui: boas-vindas, importar, análise.

use crate::app::{Aba, Estado, Tela};
use crate::cena::{Ancora, Cena, Prim};
use crate::exportar;
use crate::modelo::*;
use crate::tema::{self, *};
use eframe::egui::{
    self, Align, Align2, Color32, CornerRadius, FontId, Layout, Margin, RichText, Sense, Stroke, Vec2,
};

pub const EMAIL: &str = "gerlanmatfis@gmail.com";
pub const ORCID: &str = "0000-0002-9996-9983";

pub struct RedesApp {
    pub estado: Estado,
    logo: Option<egui::TextureHandle>,
}

impl RedesApp {
    pub fn novo(cc: &eframe::CreationContext<'_>, backend: Box<dyn crate::backend::Backend>) -> Self {
        tema::aplicar(&cc.egui_ctx);
        let mut estado = Estado::novo(backend);
        // Atalho de desenvolvimento: REDES_DEMO=1 abre direto a análise de demonstração
        // (REDES_ABA=rede|estrategico escolhe a aba; REDES_TELA=importar abre a tela de importar).
        match std::env::var("REDES_TELA").as_deref() {
            Ok("importar") => estado.tela = Tela::Importar,
            _ => {}
        }
        if let Some(arq) = std::env::var_os("REDES_ARQUIVO") {
            estado.abrir_caminho(std::path::Path::new(&arq));
            match std::env::var("REDES_ABA").as_deref() {
                Ok("rede") => estado.aba = Aba::Rede,
                Ok("estrategico") => estado.aba = Aba::Estrategico,
                _ => {}
            }
        } else if std::env::var_os("REDES_DEMO").is_some() {
            estado.abrir_demonstracao();
            match std::env::var("REDES_ABA").as_deref() {
                Ok("rede") => estado.aba = Aba::Rede,
                Ok("estrategico") => estado.aba = Aba::Estrategico,
                _ => {}
            }
        }
        RedesApp { estado, logo: None }
    }

    fn logo(&mut self, ctx: &egui::Context) -> egui::TextureId {
        if self.logo.is_none() {
            let px = 256;
            let rgba = exportar::svg_para_rgba(include_str!("../assets/logo-mark.svg"), px, px).unwrap_or_else(|_| vec![0; (px * px * 4) as usize]);
            let img = egui::ColorImage::from_rgba_unmultiplied([px as usize, px as usize], &rgba);
            self.logo = Some(ctx.load_texture("logo", img, egui::TextureOptions::LINEAR));
        }
        self.logo.as_ref().unwrap().id()
    }
}

impl eframe::App for RedesApp {
    fn clear_color(&self, _visuals: &egui::Visuals) -> [f32; 4] {
        [0xF7 as f32 / 255.0, 0xF8 as f32 / 255.0, 0xFB as f32 / 255.0, 1.0]
    }

    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        let logo = self.logo(ctx);
        // Arrastar e soltar um .redes abre o projeto.
        let soltos: Vec<_> = ctx.input(|i| i.raw.dropped_files.iter().filter_map(|f| f.path.clone()).collect());
        if let Some(p) = soltos.first() {
            self.estado.abrir_caminho(p);
        }
        match self.estado.tela {
            Tela::BoasVindas => boas_vindas(ctx, &mut self.estado, logo),
            Tela::Importar => importar(ctx, &mut self.estado, logo),
            Tela::Analise => analise(ctx, &mut self.estado, logo),
        }
    }
}

fn centro<R>(ui: &mut egui::Ui, largura: f32, f: impl FnOnce(&mut egui::Ui) -> R) -> R {
    let disp = ui.available_rect_before_wrap();
    let x = disp.center().x - largura / 2.0;
    let r = egui::Rect::from_min_size(egui::pos2(x.max(disp.left()), disp.top()), Vec2::new(largura.min(disp.width()), disp.height()));
    ui.scope_builder(egui::UiBuilder::new().max_rect(r), f).inner
}

fn botao_primario(ui: &mut egui::Ui, texto: &str) -> egui::Response {
    ui.add(
        egui::Button::new(RichText::new(texto).color(BRANCO).family(tema::negrito()))
            .fill(AZUL)
            .stroke(Stroke::NONE)
            .min_size(Vec2::new(120.0, 38.0))
            .corner_radius(CornerRadius::same(10)),
    )
}

fn botao_secundario(ui: &mut egui::Ui, texto: &str) -> egui::Response {
    ui.add(
        egui::Button::new(RichText::new(texto).color(AZUL_ESCURO))
            .fill(BRANCO)
            .stroke(Stroke::new(1.0f32, LINHA_FORTE))
            .min_size(Vec2::new(0.0, 34.0))
            .corner_radius(CornerRadius::same(10)),
    )
}

fn boas_vindas(ctx: &egui::Context, s: &mut Estado, logo: egui::TextureId) {
    egui::CentralPanel::default().frame(egui::Frame::new().fill(BRANCO)).show(ctx, |ui| {
        let alto = ui.available_height();
        ui.add_space((alto - 440.0).max(24.0) / 2.0);
        centro(ui, 560.0, |ui| {
            ui.vertical_centered(|ui| {
                ui.add(egui::Image::new((logo, Vec2::splat(128.0))));
                ui.add_space(8.0);
                ui.label(RichText::new("Redes").size(42.0).family(tema::negrito()).color(AZUL_ESCURO));
                ui.add_space(4.0);
                ui.label(
                    RichText::new("Mapeie a produção científica de um campo: temas, autores, países e referências, a partir do arquivo exportado da sua base.")
                        .size(15.0)
                        .color(Color32::from_rgb(0x47, 0x55, 0x69)),
                );
                ui.add_space(14.0);
                if botao_primario(ui, "Começar").clicked() {
                    s.tela = Tela::Importar;
                }
                ui.add_space(6.0);
                ui.label(RichText::new("Versão local · nenhum dado sai desta máquina").size(12.0).color(TINTA_FRACA));
                ui.add_space(28.0);
                let larg = |ui: &egui::Ui, t: &str, f: FontId| ui.fonts(|fo| fo.layout_no_wrap(t.to_string(), f, Color32::BLACK).size().x);
                let f12 = FontId::proportional(12.0);
                let fneg = FontId::new(12.0, tema::negrito());
                let (a, b, c) = ("Criada por ", "Gerlan Silva da Silva", " · Doutorando em Educação, UFSCar");
                let total = larg(ui, a, f12.clone()) + larg(ui, b, fneg) + larg(ui, c, f12.clone());
                ui.horizontal(|ui| {
                    ui.spacing_mut().item_spacing.x = 0.0;
                    ui.add_space(((560.0 - total) / 2.0).max(0.0));
                    ui.label(RichText::new(a).size(12.0).color(TINTA_FRACA));
                    ui.label(RichText::new(b).size(12.0).family(tema::negrito()).color(TINTA_FRACA));
                    ui.label(RichText::new(c).size(12.0).color(TINTA_FRACA));
                });
                let l1 = EMAIL.to_string();
                let l2 = format!("ORCID {ORCID}");
                let total = larg(ui, &l1, f12.clone()) + larg(ui, &l2, f12.clone()) + larg(ui, " · ", f12) + 8.0;
                ui.horizontal(|ui| {
                    ui.spacing_mut().item_spacing.x = 0.0;
                    ui.add_space(((560.0 - total) / 2.0).max(0.0));
                    ui.hyperlink_to(RichText::new(l1).size(12.0).color(AZUL), format!("mailto:{EMAIL}"));
                    ui.label(RichText::new(" · ").size(12.0).color(TINTA_FRACA));
                    ui.hyperlink_to(RichText::new(l2).size(12.0).color(AZUL), format!("https://orcid.org/{ORCID}"));
                });
            });
        });
    });
}

fn importar(ctx: &egui::Context, s: &mut Estado, logo: egui::TextureId) {
    egui::CentralPanel::default().frame(egui::Frame::new().fill(FUNDO)).show(ctx, |ui| {
        let alto = ui.available_height();
        ui.add_space((alto - 380.0).max(24.0) / 2.0);
        centro(ui, 520.0, |ui| {
            egui::Frame::new()
                .fill(BRANCO)
                .stroke(Stroke::new(1.0f32, LINHA))
                .corner_radius(CornerRadius::same(14))
                .inner_margin(Margin::same(28))
                .show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.add(egui::Image::new((logo, Vec2::splat(32.0))));
                        ui.label(RichText::new("Abrir projeto").size(22.0).family(tema::negrito()).color(AZUL_ESCURO));
                    });
                    ui.add_space(6.0);
                    ui.label(RichText::new("Escolha um arquivo .redes, ou arraste-o para esta janela. O arquivo é lido nesta máquina.").color(TINTA_FRACA));
                    ui.add_space(14.0);
                    let (area, _) = ui.allocate_exact_size(Vec2::new(ui.available_width(), 110.0), Sense::hover());
                    ui.painter().rect(area, CornerRadius::same(12), apoio_lavanda(), Stroke::new(1.0f32, LINHA_FORTE), egui::StrokeKind::Inside);
                    ui.painter().text(area.center() - Vec2::new(0.0, 12.0), Align2::CENTER_CENTER, "Solte o arquivo .redes aqui", FontId::proportional(14.0), AZUL_ESCURO);
                    ui.painter().text(area.center() + Vec2::new(0.0, 12.0), Align2::CENTER_CENTER, "ou use o botão abaixo", FontId::proportional(12.0), TINTA_FRACA);
                    ui.add_space(12.0);
                    ui.horizontal(|ui| {
                        if botao_primario(ui, "Escolher arquivo…").clicked() {
                            if let Some(p) = rfd::FileDialog::new()
                                .set_title("Abrir projeto Redes")
                                .add_filter("Projeto Redes", &["redes"])
                                .pick_file()
                            {
                                s.abrir_caminho(&p);
                            }
                        }
                        if botao_secundario(ui, "Usar dados de demonstração").clicked() {
                            s.abrir_demonstracao();
                        }
                    });
                    if let Some(e) = &s.erro {
                        ui.add_space(10.0);
                        ui.label(RichText::new(e).color(Color32::from_rgb(0xB4, 0x23, 0x18)));
                    }
                    ui.add_space(8.0);
                    ui.label(RichText::new(format!("Cálculo: {}", s.backend.origem())).size(11.0).color(TINTA_SUAVE));
                });
            ui.add_space(10.0);
            if ui.link(RichText::new("Voltar").color(AZUL)).clicked() {
                s.tela = Tela::BoasVindas;
            }
        });
    });
}

fn apoio_lavanda() -> Color32 {
    Color32::from_rgb(0xF4, 0xF2, 0xFF)
}

fn secao(ui: &mut egui::Ui, texto: &str) {
    ui.add_space(8.0);
    ui.label(RichText::new(texto.to_uppercase()).size(10.5).family(tema::negrito()).color(TINTA_SUAVE));
}

fn item_menu(ui: &mut egui::Ui, texto: &str, ativo: bool) -> bool {
    let (fundo, cor) = if ativo { (LAVANDA, AZUL) } else { (Color32::TRANSPARENT, TINTA) };
    ui.add(
        egui::Button::new(RichText::new(texto).color(cor).family(tema::negrito()))
            .fill(fundo)
            .stroke(Stroke::NONE)
            .min_size(Vec2::new(ui.available_width(), 34.0))
            .corner_radius(CornerRadius::same(8)),
    )
    .clicked()
}

fn analise(ctx: &egui::Context, s: &mut Estado, logo: egui::TextureId) {
    egui::SidePanel::left("menu")
        .exact_width(240.0)
        .resizable(false)
        .show_separator_line(false)
        .frame(egui::Frame::new().fill(BRANCO).stroke(Stroke::new(1.0f32, LINHA)).inner_margin(Margin::symmetric(16, 20)))
        .show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.add(egui::Image::new((logo, Vec2::splat(30.0))));
                ui.label(RichText::new("Redes").size(20.0).family(tema::negrito()).color(AZUL_ESCURO));
            });
            ui.add_space(12.0);
            secao(ui, "Análises");
            for e in Estrutura::TODAS {
                let ativo = s.params.estrutura == e;
                let r = ui.scope(|ui| item_menu(ui, e.rotulo(), ativo)).inner;
                if r {
                    s.escolher_estrutura(e);
                }
            }
            ui.add_space(8.0);
            ui.label(RichText::new(s.params.estrutura.descricao()).size(11.5).color(TINTA_FRACA));
            ui.with_layout(Layout::bottom_up(Align::LEFT), |ui| {
                ui.label(RichText::new(format!("Cálculo: {}", s.backend.origem())).size(11.0).color(TINTA_SUAVE));
                if botao_secundario(ui, "Abrir outro projeto").clicked() {
                    s.fechar_projeto();
                }
            });
        });

    egui::TopBottomPanel::top("topo")
        .exact_height(64.0)
        .show_separator_line(false)
        .frame(egui::Frame::new().fill(BRANCO).stroke(Stroke::new(1.0f32, LINHA)).inner_margin(Margin::symmetric(24, 10)))
        .show(ctx, |ui| {
            ui.horizontal_centered(|ui| {
                if let Some(info) = &s.info {
                    ui.vertical(|ui| {
                        ui.spacing_mut().item_spacing.y = 0.0;
                        ui.label(RichText::new(&info.nome).family(tema::negrito()).size(15.0).color(AZUL_ESCURO));
                        let docs = if info.documentos > 0 { format!("{} documentos · ", info.documentos) } else { String::new() };
                        ui.label(RichText::new(format!("{docs}{} períodos", info.periodos.len())).size(11.5).color(TINTA_FRACA));
                    });
                }
                ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                    let atual = s.rotulo_periodo();
                    let opcoes: Vec<String> = s.info.as_ref().map(|i| i.periodos.clone()).unwrap_or_default();
                    let mut escolha = s.params.periodo;
                    let todos = s.backend.permite_todos_periodos();
                    egui::ComboBox::from_id_salt("periodo").selected_text(atual).width(170.0).show_ui(ui, |ui| {
                        if todos {
                            ui.selectable_value(&mut escolha, None, "Todos os períodos");
                        }
                        for (i, p) in opcoes.iter().enumerate() {
                            ui.selectable_value(&mut escolha, Some(i), p);
                        }
                    });
                    ui.label(RichText::new("Período").size(12.0).color(TINTA_FRACA));
                    s.escolher_periodo(escolha);
                });
            });
        });

    egui::CentralPanel::default().frame(egui::Frame::new().fill(FUNDO).inner_margin(Margin::symmetric(28, 20))).show(ctx, |ui| {
        ui.label(RichText::new(format!("Estrutura {}", s.params.estrutura.rotulo().to_lowercase())).size(22.0).family(tema::negrito()).color(AZUL_ESCURO));
        ui.add_space(6.0);
        ui.horizontal(|ui| {
            for a in Aba::TODAS {
                let ativo = s.aba == a;
                let t = RichText::new(a.rotulo()).color(if ativo { AZUL } else { TINTA }).family(tema::negrito());
                let b = egui::Button::new(t)
                    .fill(if ativo { LAVANDA } else { Color32::TRANSPARENT })
                    .stroke(Stroke::NONE)
                    .corner_radius(CornerRadius::same(8))
                    .min_size(Vec2::new(0.0, 32.0));
                if ui.add(b).clicked() {
                    s.aba = a;
                }
            }
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                if s.aba != Aba::Resumo {
                    if botao_secundario(ui, "Exportar PNG").clicked() {
                        exportar_cena(s, "png");
                    }
                    if botao_secundario(ui, "Exportar SVG").clicked() {
                        exportar_cena(s, "svg");
                    }
                }
            });
        });
        ui.add_space(8.0);
        if let Some(e) = s.erro.clone() {
            ui.label(RichText::new(e).color(Color32::from_rgb(0xB4, 0x23, 0x18)));
        }
        if let Some(a) = s.aviso.clone() {
            ui.label(RichText::new(a).color(Color32::from_rgb(0x06, 0x76, 0x47)));
        }
        if s.resultado.is_none() {
            return;
        }
        match s.aba {
            Aba::Resumo => resumo(ui, s),
            Aba::Rede | Aba::Estrategico => painel_cena(ui, s),
        }
    });
}

fn exportar_cena(s: &mut Estado, ext: &str) {
    let Some(cena) = s.cena_para_exportar(s.aba) else { return };
    let nome = s.nome_arquivo_exportacao(s.aba, ext);
    let filtro = if ext == "svg" { "Imagem SVG" } else { "Imagem PNG" };
    if let Some(p) = rfd::FileDialog::new().set_title("Exportar").set_file_name(nome).add_filter(filtro, &[ext]).save_file() {
        let r = if ext == "svg" { exportar::salvar_svg(&cena, &p) } else { exportar::salvar_png(&cena, &p) };
        match r {
            Ok(()) => {
                s.erro = None;
                s.aviso = Some(format!("Exportado: {}", p.display()));
            }
            Err(e) => {
                s.aviso = None;
                s.erro = Some(e);
            }
        }
    }
}

fn cartao() -> egui::Frame {
    egui::Frame::new()
        .fill(BRANCO)
        .stroke(Stroke::new(1.0f32, LINHA))
        .corner_radius(CornerRadius::same(12))
        .inner_margin(Margin::same(16))
}

fn resumo(ui: &mut egui::Ui, s: &Estado) {
    let r = s.resultado.as_ref().unwrap();
    egui::ScrollArea::vertical().auto_shrink([false, false]).show(ui, |ui| {
        ui.horizontal_wrapped(|ui| {
            let nome = s.params.estrutura.nome_no();
            for (rot, val) in [
                ("Documentos", r.resumo.documentos),
                (&nome[..1].to_uppercase().chars().chain(nome[1..].chars()).collect::<String>(), r.resumo.nos),
                ("Ligações", r.resumo.arestas),
                ("Temas", r.resumo.grupos),
            ] {
                cartao().show(ui, |ui| {
                    ui.set_min_width(130.0);
                    ui.label(RichText::new(rot.to_uppercase()).size(10.5).family(tema::negrito()).color(TINTA_SUAVE));
                    ui.label(RichText::new(val.to_string()).size(24.0).family(tema::negrito()).color(AZUL_ESCURO));
                });
            }
        });
        ui.add_space(12.0);
        let largura = (ui.available_width() - 12.0) / 2.0;
        for linha in [[Quadrante::Motor, Quadrante::Nicho], [Quadrante::Basico, Quadrante::Emergente]] {
            ui.horizontal_top(|ui| {
                for q in linha {
                    ui.allocate_ui_with_layout(Vec2::new(largura, 0.0), Layout::top_down(Align::Min), |ui| {
                        cartao().show(ui, |ui| {
                            ui.set_width(largura - 34.0);
                            ui.horizontal(|ui| {
                                let (pt, _) = ui.allocate_exact_size(Vec2::splat(10.0), Sense::hover());
                                ui.painter().circle_filled(pt.center(), 5.0, cor_quadrante(q));
                                ui.label(RichText::new(q.rotulo()).family(tema::negrito()).size(15.0).color(AZUL_ESCURO));
                            });
                            let grupos = r.grupos_do_quadrante(q);
                            if grupos.is_empty() {
                                ui.label(RichText::new("Nenhum tema neste quadrante.").color(TINTA_FRACA));
                            }
                            for g in grupos {
                                ui.add_space(2.0);
                                ui.label(RichText::new(&g.nome).family(tema::negrito()));
                                let termos: Vec<String> = r.nos_do_grupo(g.id).iter().take(5).map(|n| n.rotulo.clone()).collect();
                                ui.label(
                                    RichText::new(match g.citacoes {
                                        Some(c) => format!("{} documentos · {} citações · {}", g.documentos, c, termos.join(", ")),
                                        None => format!("{} documentos · {}", g.documentos, termos.join(", ")),
                                    })
                                        .size(11.5)
                                        .color(TINTA_FRACA),
                                );
                            }
                        });
                    });
                }
            });
            ui.add_space(12.0);
        }
    });
}

fn painel_cena(ui: &mut egui::Ui, s: &mut Estado) {
    let aba = s.aba;
    cartao().inner_margin(Margin::same(8)).show(ui, |ui| {
        let disp = ui.available_size();
        let (rect, resp) = ui.allocate_exact_size(Vec2::new(disp.x, (disp.y - 4.0).max(200.0)), Sense::hover());
        let Some(cena) = s.cena(aba, rect.width(), rect.height()) else { return };
        pintar(ui.painter_at(rect), rect.min, cena);
        if let Some(p) = resp.hover_pos() {
            if let Some(d) = cena.dica_em((p.x - rect.min.x, p.y - rect.min.y)) {
                resp.on_hover_text_at_pointer(d.to_string());
            }
        }
    });
}

fn cor32(c: [u8; 4]) -> Color32 {
    // Pré-multiplicação simples em sRGB, o mesmo resultado do SVG (o egui, por padrão,
    // pré-multiplica de forma "gama-correta" e clareia cores translúcidas).
    let a = c[3] as u32;
    let m = |v: u8| ((v as u32 * a + 127) / 255) as u8;
    Color32::from_rgba_premultiplied(m(c[0]), m(c[1]), m(c[2]), c[3])
}

/// Pinta uma cena no egui, com a origem da cena em `o`.
pub fn pintar(p: egui::Painter, o: egui::Pos2, cena: &Cena) {
    let pt = |q: (f32, f32)| egui::pos2(o.x + q.0, o.y + q.1);
    for prim in &cena.prims {
        match prim {
            Prim::Circulo { c, r, preench, borda, .. } => {
                if let Some(f) = preench {
                    p.circle_filled(pt(*c), *r, cor32(*f));
                }
                if let Some((cb, w)) = borda {
                    p.circle_stroke(pt(*c), *r, Stroke::new(*w, cor32(*cb)));
                }
            }
            Prim::Linha { a, b, cor, larg, tracejada } => {
                let st = Stroke::new(*larg, cor32(*cor));
                if *tracejada {
                    p.extend(egui::Shape::dashed_line(&[pt(*a), pt(*b)], st, 6.0, 4.0));
                } else {
                    p.line_segment([pt(*a), pt(*b)], st);
                }
            }
            Prim::Retangulo { min, max, preench, borda } => {
                let rect = egui::Rect::from_min_max(pt(*min), pt(*max));
                if let Some(f) = preench {
                    p.rect_filled(rect, 0.0, cor32(*f));
                }
                if let Some((cb, w)) = borda {
                    p.rect_stroke(rect, 0.0, Stroke::new(*w, cor32(*cb)), egui::StrokeKind::Inside);
                }
            }
            Prim::Texto { pos, texto, tam, cor, ancora, negrito, vertical } => {
                let fonte = if *negrito { FontId::new(*tam, tema::negrito()) } else { FontId::proportional(*tam) };
                let c = cor32(*cor);
                if *vertical {
                    let galley = p.layout_no_wrap(texto.clone(), fonte, c);
                    let (w, h) = (galley.size().x, galley.size().y);
                    let topo_esq = egui::pos2(o.x + pos.0 - h / 2.0, o.y + pos.1 + w / 2.0);
                    p.add(egui::epaint::TextShape::new(topo_esq, galley, c).with_angle(-std::f32::consts::FRAC_PI_2));
                } else {
                    let al = match ancora {
                        Ancora::Esquerda => Align2::LEFT_CENTER,
                        Ancora::Centro => Align2::CENTER_CENTER,
                        Ancora::Direita => Align2::RIGHT_CENTER,
                    };
                    p.text(pt(*pos), al, texto, fonte.clone(), c);
                }
            }
        }
    }
}
