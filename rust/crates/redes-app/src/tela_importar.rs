//! Tela de importar: abrir um projeto `.redes` ou importar um corpus (arquivo,
//! nome, formato, períodos), com barra de progresso e cancelamento.

use crate::app::{Estado, Tela};
use crate::servicos::{parse_periodos, FormatoCorpus};
use crate::telas::{botao_primario, botao_secundario, centro};
use crate::tema::{self, *};
use eframe::egui::{self, Align, Color32, CornerRadius, Layout, Margin, RichText, Stroke, Vec2};

const VERMELHO: Color32 = Color32::from_rgb(0xB4, 0x23, 0x18);
const VERDE_TEXTO: Color32 = Color32::from_rgb(0x06, 0x76, 0x47);

fn rotulo_campo(ui: &mut egui::Ui, t: &str) {
    ui.label(RichText::new(t.to_uppercase()).size(10.5).family(tema::negrito()).color(TINTA_SUAVE));
}

fn nome_do_arquivo(p: &std::path::Path) -> String {
    p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| p.display().to_string())
}

pub fn importar(ctx: &egui::Context, s: &mut Estado, logo: egui::TextureId) {
    egui::CentralPanel::default().frame(egui::Frame::new().fill(FUNDO).inner_margin(Margin::symmetric(0, 16))).show(ctx, |ui| {
        egui::ScrollArea::vertical().auto_shrink([false, false]).drag_to_scroll(false).show(ui, |ui| {
            centro(ui, 600.0, |ui| {
                egui::Frame::new()
                    .fill(BRANCO)
                    .stroke(Stroke::new(1.0f32, LINHA))
                    .corner_radius(CornerRadius::same(14))
                    .inner_margin(Margin::same(24))
                    .show(ui, |ui| {
                        ui.horizontal(|ui| {
                            ui.add(egui::Image::new((logo, Vec2::splat(32.0))));
                            ui.label(RichText::new("Importar corpus").size(22.0).family(tema::negrito()).color(AZUL_ESCURO));
                        });
                        ui.add_space(4.0);
                        ui.label(RichText::new("Escolha o arquivo exportado da base, ou arraste-o para esta janela. Tudo é lido nesta máquina.").color(TINTA_FRACA));
                        ui.add_space(12.0);
                        formulario(ui, s);
                    });
                ui.add_space(12.0);
                projeto_existente(ui, s);
                ui.add_space(10.0);
                if ui.link(RichText::new("Voltar").color(AZUL)).clicked() {
                    s.tela = Tela::BoasVindas;
                }
                ui.add_space(8.0);
                ui.label(RichText::new(format!("Cálculo: {}", s.backend.origem())).size(11.0).color(TINTA_SUAVE));
            });
        });
    });
}

fn formulario(ui: &mut egui::Ui, s: &mut Estado) {
    let ocupado = s.importacao.em_andamento();
    // Durante a importação o formulário dá lugar a um resumo (sem widgets desabilitados).
    if ocupado {
        resumo_em_andamento(ui, s);
    } else {
        campos(ui, s);
    }
    ui.add_space(12.0);
    let disponivel = s.servicos.importador.disponivel();
    if !disponivel {
        egui::Frame::new().fill(Color32::from_rgb(0xFF, 0xF8, 0xE1)).corner_radius(CornerRadius::same(8)).inner_margin(Margin::same(10)).show(ui, |ui| {
            ui.label(
                RichText::new("O importador de corpus será ligado na próxima versão. Por enquanto, o botão abaixo só simula o andamento para conferir a tela; nada é lido nem gravado.")
                    .size(12.0)
                    .color(Color32::from_rgb(0x7A, 0x4B, 0x00)),
            );
        });
        ui.add_space(8.0);
    }
    if let Some(p) = s.importacao.progresso.clone().filter(|_| ocupado) {
        ui.label(RichText::new(format!("{} · {:.0}%", p.etapa, p.fracao * 100.0)).size(12.5).color(TINTA));
        // A faixa da barra usa a cor de fundo dos campos, que aqui é branca: troca por lavanda.
        ui.scope(|ui| {
            ui.visuals_mut().extreme_bg_color = LAVANDA;
            let largura = ui.available_width();
            ui.add(egui::ProgressBar::new(p.fracao).desired_width(largura).desired_height(10.0).fill(AZUL));
        });
        ui.add_space(6.0);
        if botao_secundario(ui, "Cancelar importação").clicked() {
            s.importar_cancelar();
        }
    } else {
        ui.horizontal(|ui| {
            let texto = if disponivel { "Importar" } else { "Simular importação" };
            if botao_primario(ui, texto).clicked() {
                s.importar_iniciar();
            }
        });
    }
    if let Some(e) = &s.importacao.erro {
        ui.add_space(8.0);
        ui.label(RichText::new(e).color(VERMELHO));
    }
    if let Some(a) = &s.importacao.aviso {
        ui.add_space(8.0);
        ui.label(RichText::new(a).color(VERDE_TEXTO));
    }
}

fn campos(ui: &mut egui::Ui, s: &mut Estado) {
    rotulo_campo(ui, "Arquivo do corpus");
    ui.with_layout(Layout::right_to_left(Align::Center), |ui| {
        if botao_secundario(ui, "Escolher arquivo…").clicked() {
            let ext = s.importacao.formato.extensoes();
            if let Some(p) = rfd::FileDialog::new().set_title("Arquivo do corpus").add_filter("Arquivos de corpus", ext).pick_file() {
                s.importar_escolher(&p);
            }
        }
        let t = match &s.importacao.arquivo {
            Some(p) => nome_do_arquivo(p),
            None => "Nenhum arquivo escolhido".into(),
        };
        let cor = if s.importacao.arquivo.is_some() { TINTA } else { TINTA_FRACA };
        let r = ui.add(egui::Label::new(RichText::new(t).color(cor)).truncate());
        if let Some(p) = &s.importacao.arquivo {
            r.on_hover_text(p.display().to_string());
        }
    });
    ui.add_space(6.0);
    rotulo_campo(ui, "Nome do projeto");
    ui.add(egui::TextEdit::singleline(&mut s.importacao.nome).margin(Margin::symmetric(8, 6)).hint_text("ex.: educação estatística").desired_width(ui.available_width()));
    ui.add_space(6.0);
    rotulo_campo(ui, "Formato");
    egui::ComboBox::from_id_salt("formato_corpus").selected_text(s.importacao.formato.rotulo()).width(260.0).show_ui(ui, |ui| {
        for f in FormatoCorpus::TODOS {
            ui.selectable_value(&mut s.importacao.formato, f, f.rotulo());
        }
    });
    ui.add_space(6.0);
    rotulo_campo(ui, "Períodos");
    ui.add(
        egui::TextEdit::singleline(&mut s.importacao.periodos)
            .margin(Margin::symmetric(8, 6))
            .hint_text("ex.: 2011-2016, 2017-2019, 2020-2025 (vazio = todos os anos)")
            .desired_width(ui.available_width()),
    );
    match parse_periodos(&s.importacao.periodos) {
        Ok(v) if !v.is_empty() => {
            let txt: Vec<String> = v.iter().map(|p| p.rotulo()).collect();
            ui.label(RichText::new(format!("{} períodos: {}", v.len(), txt.join(" · "))).size(11.5).color(TINTA_FRACA));
        }
        Ok(_) => {
            ui.label(RichText::new("Sem divisão: um único período com todos os anos.").size(11.5).color(TINTA_FRACA));
        }
        Err(e) => {
            ui.label(RichText::new(e).size(11.5).color(VERMELHO));
        }
    }
    if let Some(p) = &s.importacao.arquivo {
        let saida = crate::servicos::OpcoesImportacao {
            arquivo: p.clone(),
            nome: s.importacao.nome.clone(),
            formato: s.importacao.formato,
            periodos: vec![],
        }
        .saida();
        ui.label(RichText::new(format!("Será gravado em {}", saida.display())).size(11.5).color(TINTA_SUAVE));
    }
}

fn resumo_em_andamento(ui: &mut egui::Ui, s: &Estado) {
    let imp = &s.importacao;
    rotulo_campo(ui, "Importando");
    if let Some(p) = &imp.arquivo {
        ui.label(RichText::new(nome_do_arquivo(p)).color(TINTA));
    }
    ui.label(RichText::new(format!("Projeto: {} · formato: {}", imp.nome.trim(), imp.formato.rotulo())).size(12.0).color(TINTA_FRACA));
    if !imp.periodos.trim().is_empty() {
        ui.label(RichText::new(format!("Períodos: {}", imp.periodos.trim())).size(12.0).color(TINTA_FRACA));
    }
}

fn projeto_existente(ui: &mut egui::Ui, s: &mut Estado) {
    egui::Frame::new()
        .fill(BRANCO)
        .stroke(Stroke::new(1.0f32, LINHA))
        .corner_radius(CornerRadius::same(14))
        .inner_margin(Margin::same(20))
        .show(ui, |ui| {
            ui.set_width(ui.available_width());
            ui.label(RichText::new("Abrir projeto existente").size(16.0).family(tema::negrito()).color(AZUL_ESCURO));
            ui.label(RichText::new("Arquivo .redes já importado (também vale arrastá-lo para a janela).").color(TINTA_FRACA));
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                if botao_secundario(ui, "Abrir .redes…").clicked() {
                    if let Some(p) = rfd::FileDialog::new().set_title("Abrir projeto Redes").add_filter("Projeto Redes", &["redes"]).pick_file() {
                        s.abrir_caminho(&p);
                    }
                }
                if botao_secundario(ui, "Usar dados de demonstração").clicked() {
                    s.abrir_demonstracao();
                }
            });
            if let Some(e) = &s.erro {
                ui.add_space(8.0);
                ui.label(RichText::new(e).color(VERMELHO));
            }
        });
}
