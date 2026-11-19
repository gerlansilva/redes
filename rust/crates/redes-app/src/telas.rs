//! Telas em egui: boas-vindas, importar, análise.

use crate::app::{Aba, Estado, Tela};
use crate::exportar;
use crate::grafico;
use crate::painel;
use crate::tela_importar;
use crate::modelo::*;
use crate::tema::{self, *};
use eframe::egui::{
    self, Align, Color32, CornerRadius, FontId, Layout, Margin, RichText, Sense, Stroke, Vec2,
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
        // Atalhos de desenvolvimento (capturas e testes): REDES_DEMO=1 abre a análise de
        // demonstração; REDES_ARQUIVO=<.redes> abre um projeto; REDES_TELA=importar;
        // REDES_ABA=<slug da aba>; REDES_SELECIONAR=<n> abre o tema n; REDES_ZOOM=<fator>.
        if matches!(std::env::var("REDES_TELA").as_deref(), Ok("importar")) {
            estado.tela = Tela::Importar;
        }
        if let Some(arq) = std::env::var_os("REDES_ARQUIVO") {
            estado.abrir_caminho(std::path::Path::new(&arq));
        } else if std::env::var_os("REDES_DEMO").is_some() {
            estado.abrir_demonstracao();
        }
        // REDES_IMPORTAR=<arquivo> preenche o formulário de importação; com REDES_IMPORTAR_INICIAR=1 já inicia.
        if let Some(ms) = std::env::var("REDES_PASSO_MS").ok().and_then(|t| t.parse::<u64>().ok()) {
            estado.servicos.importador = Box::new(crate::servicos::ImportadorEmBreve { passo: std::time::Duration::from_millis(ms) });
        }
        if let Some(arq) = std::env::var_os("REDES_IMPORTAR") {
            estado.importar_escolher(std::path::Path::new(&arq));
            estado.importacao.periodos = std::env::var("REDES_PERIODOS").unwrap_or_default();
            if std::env::var_os("REDES_IMPORTAR_INICIAR").is_some() {
                estado.importar_iniciar();
            }
        }
        if estado.tela == Tela::Analise {
            if let Some(a) = std::env::var("REDES_ABA").ok().and_then(|t| Aba::de_slug(&t)) {
                estado.ir_para_aba(a);
            }
            if let Some(n) = std::env::var("REDES_SELECIONAR").ok().and_then(|t| t.parse::<usize>().ok()) {
                estado.selecionar_grupo(Some(n));
            }
            estado.zoom_inicial = std::env::var("REDES_ZOOM").ok().and_then(|t| t.parse().ok());
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
            self.estado.importar_escolher(p);
        }
        if self.estado.importar_atualizar() {
            ctx.request_repaint_after(std::time::Duration::from_millis(50));
        }
        match self.estado.tela {
            Tela::BoasVindas => boas_vindas(ctx, &mut self.estado, logo),
            Tela::Importar => tela_importar::importar(ctx, &mut self.estado, logo),
            Tela::Analise => analise(ctx, &mut self.estado, logo),
        }
    }
}

pub(crate) fn centro<R>(ui: &mut egui::Ui, largura: f32, f: impl FnOnce(&mut egui::Ui) -> R) -> R {
    let disp = ui.available_rect_before_wrap();
    let x = disp.center().x - largura / 2.0;
    let r = egui::Rect::from_min_size(egui::pos2(x.max(disp.left()), disp.top()), Vec2::new(largura.min(disp.width()), disp.height()));
    ui.scope_builder(egui::UiBuilder::new().max_rect(r), f).inner
}

pub(crate) fn botao_primario(ui: &mut egui::Ui, texto: &str) -> egui::Response {
    ui.add(
        egui::Button::new(RichText::new(texto).color(BRANCO).family(tema::negrito()))
            .fill(AZUL)
            .stroke(Stroke::NONE)
            .min_size(Vec2::new(120.0, 38.0))
            .corner_radius(CornerRadius::same(10)),
    )
}

pub(crate) fn botao_secundario(ui: &mut egui::Ui, texto: &str) -> egui::Response {
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

    painel::lateral(ctx, s);

    egui::CentralPanel::default().frame(egui::Frame::new().fill(FUNDO).inner_margin(Margin::symmetric(28, 20))).show(ctx, |ui| {
        ui.horizontal(|ui| {
            ui.label(RichText::new(format!("Estrutura {}", s.params.estrutura.rotulo().to_lowercase())).size(22.0).family(tema::negrito()).color(AZUL_ESCURO));
            ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
                if s.aba.tem_cena() && s.cena(s.aba).is_ok() {
                    if botao_secundario(ui, "Exportar PNG").clicked() {
                        exportar_cena(s, "png");
                    }
                    if botao_secundario(ui, "Exportar SVG").clicked() {
                        exportar_cena(s, "svg");
                    }
                }
            });
        });
        ui.add_space(4.0);
        ui.horizontal_wrapped(|ui| {
            ui.spacing_mut().item_spacing = Vec2::new(2.0, 4.0);
            ui.spacing_mut().button_padding = Vec2::new(9.0, 6.0);
            for a in Aba::TODAS {
                let ativo = s.aba == a;
                let livre = s.aba_disponivel(a);
                let cor = if !livre { TINTA_SUAVE } else if ativo { AZUL } else { TINTA };
                let t = RichText::new(a.rotulo()).color(cor).family(tema::negrito());
                let b = egui::Button::new(t)
                    .fill(if ativo { LAVANDA } else { Color32::TRANSPARENT })
                    .stroke(Stroke::NONE)
                    .corner_radius(CornerRadius::same(8))
                    .min_size(Vec2::new(0.0, 32.0));
                let r = ui.add_enabled(livre, b);
                if livre {
                    if r.clicked() {
                        s.ir_para_aba(a);
                    }
                } else {
                    r.on_disabled_hover_text(crate::servicos::EM_BREVE);
                }
            }
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
            Aba::Relatorio => relatorio(ui, s),
            Aba::Rede | Aba::Estrategico | Aba::Analise(_) => grafico::painel_grafico(ui, s),
        }
    });
}

fn relatorio(ui: &mut egui::Ui, s: &mut Estado) {
    cartao().show(ui, |ui| {
        ui.label(RichText::new("Relatório do projeto").size(16.0).family(tema::negrito()).color(AZUL_ESCURO));
        ui.label(RichText::new("Reúne as análises em um documento para anexar ou imprimir.").color(TINTA_FRACA));
        ui.add_space(8.0);
        let formatos = s.servicos.relatorio.formatos();
        ui.horizontal(|ui| {
            ui.label("Formato");
            egui::ComboBox::from_id_salt("formato_relatorio").selected_text(s.formato_relatorio.rotulo()).show_ui(ui, |ui| {
                for f in formatos {
                    ui.selectable_value(&mut s.formato_relatorio, f, f.rotulo());
                }
            });
        });
        ui.add_space(6.0);
        if botao_primario(ui, "Gerar relatório…").clicked() {
            let nome = format!("{}_relatorio.{}", s.info.as_ref().map(|i| i.nome.as_str()).unwrap_or("redes"), s.formato_relatorio.extensao());
            if let Some(p) = rfd::FileDialog::new().set_title("Salvar relatório").set_file_name(nome).save_file() {
                s.gerar_relatorio(&p);
            }
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

pub(crate) fn cartao() -> egui::Frame {
    egui::Frame::new()
        .fill(BRANCO)
        .stroke(Stroke::new(1.0f32, LINHA))
        .corner_radius(CornerRadius::same(12))
        .inner_margin(Margin::same(16))
}

fn resumo(ui: &mut egui::Ui, s: &mut Estado) {
    let mut abrir: Option<usize> = None;
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
                                let nome = ui.add(egui::Label::new(RichText::new(&g.nome).family(tema::negrito()).color(AZUL)).sense(Sense::click()));
                                if nome.on_hover_cursor(egui::CursorIcon::PointingHand).on_hover_text("Ver itens e documentos").clicked() {
                                    abrir = Some(g.id);
                                }
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
    if let Some(g) = abrir {
        s.selecionar_grupo(Some(g));
    }
}
