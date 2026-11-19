//! Estado e fluxo do aplicativo (independente de janela, testável).

use crate::backend::Backend;
use crate::cena::Cena;
use crate::desenho;
use crate::modelo::*;
use crate::servicos::{Desfecho, FormatoCorpus, FormatoRelatorio, PedidoRelatorio, OpcoesImportacao, Progresso, Servicos, Tarefa, TipoAnalise};
use crate::vista::Vista;
use std::collections::HashMap;
use std::sync::Arc;
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tela {
    BoasVindas,
    Importar,
    Analise,
}

/// Abas da tela de análise. Para somar uma aba: nova variante aqui, entrada em
/// `TODAS`, `rotulo`, `slug` e, se for gráfica, no `match` de `Estado::construir_cena`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Aba {
    Resumo,
    Rede,
    Estrategico,
    /// Análise fornecida pelo serviço `Analises`.
    Analise(TipoAnalise),
    Relatorio,
}

impl Aba {
    pub const TODAS: [Aba; 10] = [
        Aba::Resumo,
        Aba::Rede,
        Aba::Estrategico,
        Aba::Analise(TipoAnalise::Dendrograma),
        Aba::Analise(TipoAnalise::LinhaDoTempo),
        Aba::Analise(TipoAnalise::Densidade),
        Aba::Analise(TipoAnalise::Similitude),
        Aba::Analise(TipoAnalise::DuploMapa),
        Aba::Analise(TipoAnalise::Sankey),
        Aba::Relatorio,
    ];

    pub fn rotulo(self) -> &'static str {
        match self {
            Aba::Resumo => "Resumo",
            Aba::Rede => "Rede",
            Aba::Estrategico => "Diagrama estratégico",
            Aba::Analise(t) => t.rotulo(),
            Aba::Relatorio => "Relatório",
        }
    }

    /// Nome curto para arquivos e para REDES_ABA.
    pub fn slug(self) -> &'static str {
        match self {
            Aba::Resumo => "resumo",
            Aba::Rede => "rede",
            Aba::Estrategico => "estrategico",
            Aba::Analise(TipoAnalise::Dendrograma) => "dendrograma",
            Aba::Analise(TipoAnalise::LinhaDoTempo) => "linha-do-tempo",
            Aba::Analise(TipoAnalise::Densidade) => "densidade",
            Aba::Analise(TipoAnalise::Similitude) => "similitude",
            Aba::Analise(TipoAnalise::DuploMapa) => "duplo-mapa",
            Aba::Analise(TipoAnalise::Sankey) => "sankey",
            Aba::Relatorio => "relatorio",
        }
    }

    pub fn de_slug(t: &str) -> Option<Aba> {
        Aba::TODAS.into_iter().find(|a| a.slug() == t)
    }

    /// A aba mostra uma cena com zoom e pan?
    pub fn tem_cena(self) -> bool {
        !matches!(self, Aba::Resumo | Aba::Relatorio)
    }
}

/// Vista (zoom e deslocamento) de uma aba gráfica.
#[derive(Clone, Copy, Debug)]
pub struct VistaAba {
    pub vista: Vista,
    /// Enquanto o usuário não mexe, a vista continua enquadrando a cena ao redimensionar.
    pub auto: bool,
    pub geracao: u64,
    /// Tamanho do gráfico no último quadro.
    pub tela: (f32, f32),
}

/// Formulário e andamento da importação de corpus.
pub struct ImportacaoUi {
    pub arquivo: Option<PathBuf>,
    pub nome: String,
    pub formato: FormatoCorpus,
    pub periodos: String,
    pub tarefa: Option<Box<dyn Tarefa>>,
    pub progresso: Option<Progresso>,
    pub erro: Option<String>,
    pub aviso: Option<String>,
}

impl Default for ImportacaoUi {
    fn default() -> Self {
        ImportacaoUi {
            arquivo: None,
            nome: String::new(),
            formato: FormatoCorpus::Automatico,
            periodos: String::new(),
            tarefa: None,
            progresso: None,
            erro: None,
            aviso: None,
        }
    }
}

impl ImportacaoUi {
    pub fn em_andamento(&self) -> bool {
        self.tarefa.is_some()
    }
}

pub struct Estado {
    pub backend: Box<dyn Backend>,
    pub servicos: Servicos,
    pub tela: Tela,
    pub aba: Aba,
    pub info: Option<InfoProjeto>,
    pub params: Parametros,
    pub resultado: Option<Resultado>,
    pub erro: Option<String>,
    pub aviso: Option<String>,
    pub importacao: ImportacaoUi,
    /// Agrupamento aberto no painel lateral.
    pub selecao: Option<usize>,
    /// Títulos dos documentos do agrupamento selecionado.
    pub titulos: HashMap<i64, String>,
    pub vistas: HashMap<Aba, VistaAba>,
    /// Zoom a aplicar, uma vez, depois do próximo enquadramento (REDES_ZOOM).
    pub zoom_inicial: Option<f32>,
    /// Agrupamento a enquadrar no gráfico (botão "Mostrar no gráfico").
    pub foco: Option<usize>,
    pub formato_relatorio: FormatoRelatorio,
    geracao: u64,
    cache: Option<(Aba, u64, Result<Arc<Cena>, String>)>,
}

impl Estado {
    pub fn novo(backend: Box<dyn Backend>) -> Self {
        Estado::com_servicos(backend, Servicos::padrao())
    }

    pub fn com_servicos(backend: Box<dyn Backend>, servicos: Servicos) -> Self {
        Estado {
            backend,
            servicos,
            tela: Tela::BoasVindas,
            aba: Aba::Resumo,
            info: None,
            params: Parametros::default(),
            resultado: None,
            erro: None,
            aviso: None,
            importacao: ImportacaoUi::default(),
            selecao: None,
            titulos: HashMap::new(),
            vistas: HashMap::new(),
            zoom_inicial: None,
            foco: None,
            formato_relatorio: FormatoRelatorio::Html,
            geracao: 0,
            cache: None,
        }
    }

    /// A aba pode ser aberta? Abas de serviço só abrem quando o serviço está ligado.
    pub fn aba_disponivel(&self, a: Aba) -> bool {
        match a {
            Aba::Analise(t) => self.servicos.analises.disponivel(t),
            Aba::Relatorio => self.servicos.relatorio.disponivel(),
            _ => true,
        }
    }

    pub fn ir_para_aba(&mut self, a: Aba) {
        if self.aba_disponivel(a) {
            self.aba = a;
        }
    }

    /// Escolhe o agrupamento do painel lateral (ou fecha o painel) e carrega os títulos.
    pub fn selecionar_grupo(&mut self, g: Option<usize>) {
        let g = g.filter(|&i| self.resultado.as_ref().is_some_and(|r| i < r.grupos.len()));
        self.selecao = g;
        self.titulos.clear();
        if let (Some(i), Some(r)) = (g, &self.resultado) {
            let ids: Vec<i64> = r.grupos[i].doc_ids.iter().copied().take(500).collect();
            self.titulos = self.backend.titulos(&ids);
        }
    }

    /// Pede que a vista da aba volte a enquadrar a cena.
    pub fn ajustar_vista(&mut self, aba: Aba) {
        self.vistas.remove(&aba);
    }

    // ---- Importação ----

    /// Arquivo escolhido na tela de importar: `.redes` abre direto; o resto preenche o formulário.
    pub fn importar_escolher(&mut self, caminho: &Path) {
        if caminho.extension().is_some_and(|e| e.eq_ignore_ascii_case("redes")) {
            self.abrir_caminho(caminho);
            return;
        }
        self.importacao.erro = None;
        self.importacao.aviso = None;
        if self.importacao.nome.trim().is_empty() {
            self.importacao.nome = caminho.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
        }
        self.importacao.arquivo = Some(caminho.to_path_buf());
        self.tela = Tela::Importar;
    }

    pub fn importar_iniciar(&mut self) {
        let imp = &mut self.importacao;
        imp.erro = None;
        imp.aviso = None;
        let Some(arquivo) = imp.arquivo.clone() else {
            imp.erro = Some("Escolha o arquivo do corpus.".into());
            return;
        };
        let periodos = match crate::servicos::parse_periodos(&imp.periodos) {
            Ok(p) => p,
            Err(e) => {
                imp.erro = Some(e);
                return;
            }
        };
        let opcoes = OpcoesImportacao { arquivo, nome: imp.nome.trim().to_string(), formato: imp.formato, periodos };
        match self.servicos.importador.iniciar(opcoes) {
            Ok(t) => {
                self.importacao.progresso = Some(t.progresso());
                self.importacao.tarefa = Some(t);
            }
            Err(e) => self.importacao.erro = Some(e),
        }
    }

    pub fn importar_cancelar(&mut self) {
        if let Some(t) = &self.importacao.tarefa {
            t.cancelar();
        }
    }

    /// Atualiza o andamento; chamar a cada quadro. Devolve `true` se há tarefa em curso.
    pub fn importar_atualizar(&mut self) -> bool {
        let Some(t) = self.importacao.tarefa.as_mut() else { return false };
        self.importacao.progresso = Some(t.progresso());
        match t.desfecho() {
            None => true,
            Some(d) => {
                self.importacao.tarefa = None;
                self.importacao.progresso = None;
                match d {
                    Desfecho::Concluida(p) => self.abrir_caminho(&p),
                    Desfecho::Cancelada => self.importacao.aviso = Some("Importação cancelada.".into()),
                    Desfecho::Falhou(e) => self.importacao.erro = Some(e),
                }
                false
            }
        }
    }

    pub fn abrir_caminho(&mut self, caminho: &Path) {
        match self.backend.abrir(caminho) {
            Ok(info) => self.projeto_aberto(info),
            Err(e) => self.erro = Some(e),
        }
    }

    pub fn abrir_demonstracao(&mut self) {
        match self.backend.abrir_demonstracao() {
            Ok(info) => self.projeto_aberto(info),
            Err(e) => self.erro = Some(e),
        }
    }

    fn projeto_aberto(&mut self, info: InfoProjeto) {
        self.info = Some(info);
        self.params = Parametros::default();
        if !self.backend.permite_todos_periodos() && !self.info.as_ref().map(|i| i.periodos.is_empty()).unwrap_or(true) {
            self.params.periodo = Some(0);
        }
        self.erro = None;
        self.aviso = None;
        self.vistas.clear();
        self.selecao = None;
        self.titulos.clear();
        self.aba = Aba::Resumo;
        self.tela = Tela::Analise;
        self.recalcular();
    }

    pub fn recalcular(&mut self) {
        match self.backend.executar(&self.params) {
            Ok(r) => {
                self.resultado = Some(r);
                self.erro = None;
            }
            Err(e) => {
                self.resultado = None;
                self.erro = Some(e);
            }
        }
        self.geracao += 1;
        self.cache = None;
        self.vistas.clear();
        self.selecionar_grupo(None);
    }

    pub fn escolher_estrutura(&mut self, e: Estrutura) {
        if self.params.estrutura != e {
            self.params.estrutura = e;
            self.recalcular();
        }
    }

    pub fn escolher_periodo(&mut self, p: Option<usize>) {
        if self.params.periodo != p {
            self.params.periodo = p;
            self.recalcular();
        }
    }

    pub fn gerar_relatorio(&mut self, destino: &Path) {
        let (Some(info), Some(resultado)) = (&self.info, &self.resultado) else { return };
        let pedido = PedidoRelatorio { info, parametros: &self.params, resultado, formato: self.formato_relatorio };
        match self.servicos.relatorio.gerar(&pedido, destino) {
            Ok(p) => {
                self.erro = None;
                self.aviso = Some(format!("Relatório gravado: {}", p.display()));
            }
            Err(e) => {
                self.aviso = None;
                self.erro = Some(e);
            }
        }
    }

    pub fn fechar_projeto(&mut self) {
        self.info = None;
        self.resultado = None;
        self.erro = None;
        self.selecao = None;
        self.titulos.clear();
        self.vistas.clear();
        self.tela = Tela::Importar;
    }

    /// Cena interativa da aba (em cache enquanto o resultado não muda).
    pub fn cena(&mut self, aba: Aba) -> Result<Arc<Cena>, String> {
        if self.resultado.is_none() {
            return Err("Sem resultado.".into());
        }
        let valido = matches!(&self.cache, Some((a, g, _)) if *a == aba && *g == self.geracao);
        if !valido {
            let c = self.construir_cena(aba).map(Arc::new);
            self.cache = Some((aba, self.geracao, c));
        }
        match &self.cache {
            Some((_, _, Ok(c))) => Ok(c.clone()),
            Some((_, _, Err(e))) => Err(e.clone()),
            None => Err("Sem cena.".into()),
        }
    }

    fn construir_cena(&self, aba: Aba) -> Result<Cena, String> {
        let r = self.resultado.as_ref().ok_or("Sem resultado.")?;
        match aba {
            Aba::Rede => Ok(desenho::rede_interativa(r)),
            Aba::Estrategico => Ok(desenho::estrategico_interativo(r)),
            Aba::Analise(t) => self.servicos.analises.gerar(t, r, &self.params),
            Aba::Resumo | Aba::Relatorio => Err("Esta aba não tem gráfico.".into()),
        }
    }

    /// Cena em tamanho fixo para exportação.
    pub fn cena_para_exportar(&self, aba: Aba) -> Option<Cena> {
        let r = self.resultado.as_ref()?;
        match aba {
            Aba::Rede => Some(desenho::rede(r, 1400.0, 1000.0)),
            Aba::Estrategico => Some(desenho::estrategico(r, 1400.0, 1000.0)),
            Aba::Analise(t) => self.servicos.analises.gerar(t, r, &self.params).ok(),
            Aba::Resumo | Aba::Relatorio => None,
        }
    }

    pub fn nome_arquivo_exportacao(&self, aba: Aba, ext: &str) -> String {
        let base = self.info.as_ref().map(|i| i.nome.as_str()).unwrap_or("redes");
        let parte = match aba {
            Aba::Estrategico => "diagrama-estrategico",
            outra => outra.slug(),
        };
        let est = match self.params.estrutura {
            Estrutura::Fontes => "fontes",
            Estrutura::Conceitual => "conceitual",
            Estrutura::Intelectual => "intelectual",
            Estrutura::Social => "social",
        };
        format!("{base}_{est}_{parte}.{ext}")
    }

    pub fn rotulo_periodo(&self) -> String {
        match (self.params.periodo, &self.info) {
            (Some(i), Some(info)) => info.periodos.get(i).cloned().unwrap_or_default(),
            _ => "Todos os períodos".into(),
        }
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use crate::backend::mock::Demonstracao;

    fn estado() -> Estado {
        Estado::novo(Box::new(Demonstracao::default()))
    }

    #[test]
    fn fluxo_basico() {
        let mut s = estado();
        assert_eq!(s.tela, Tela::BoasVindas);
        s.abrir_demonstracao();
        assert_eq!(s.tela, Tela::Analise);
        assert!(s.resultado.is_some());
        let antes = s.resultado.clone();
        s.escolher_estrutura(Estrutura::Social);
        assert_ne!(s.resultado, antes);
        s.escolher_periodo(Some(2));
        assert_eq!(s.rotulo_periodo(), "2020–2022");
        s.escolher_periodo(None);
        assert_eq!(s.rotulo_periodo(), "Todos os períodos");
    }

    #[test]
    fn arquivo_inexistente_mostra_erro_e_nao_muda_de_tela() {
        let mut s = estado();
        s.tela = Tela::Importar;
        s.abrir_caminho(Path::new("/nao/existe.redes"));
        assert!(s.erro.is_some());
        assert_eq!(s.tela, Tela::Importar);
    }

    #[test]
    fn arquivo_existente_abre() {
        let mut s = estado();
        let f = std::env::temp_dir().join(format!("redes_t_{}.redes", std::process::id()));
        std::fs::write(&f, b"x").unwrap();
        s.abrir_caminho(&f);
        assert_eq!(s.tela, Tela::Analise);
        assert!(s.info.as_ref().unwrap().nome.starts_with("redes_t_"));
        let _ = std::fs::remove_file(f);
    }

    #[test]
    fn cache_de_cena_e_invalidado() {
        let mut s = estado();
        s.abrir_demonstracao();
        let a = s.cena(Aba::Rede).unwrap();
        assert!(Arc::ptr_eq(&a, &s.cena(Aba::Rede).unwrap()));
        s.escolher_estrutura(Estrutura::Fontes);
        assert_ne!(s.cena(Aba::Rede).unwrap(), a);
        assert!(s.cena(Aba::Resumo).is_err());
    }

    #[test]
    fn nomes_de_exportacao() {
        let mut s = estado();
        s.abrir_demonstracao();
        assert_eq!(s.nome_arquivo_exportacao(Aba::Estrategico, "svg"), "demonstracao_conceitual_diagrama-estrategico.svg");
        assert!(s.cena_para_exportar(Aba::Resumo).is_none());
        assert!(s.cena_para_exportar(Aba::Rede).is_some());
    }

    #[test]
    fn fechar_volta_para_importar() {
        let mut s = estado();
        s.abrir_demonstracao();
        s.fechar_projeto();
        assert_eq!(s.tela, Tela::Importar);
        assert!(s.resultado.is_none());
    }

    #[test]
    fn abas_de_servico_ficam_desabilitadas_no_stub() {
        let mut s = estado();
        s.abrir_demonstracao();
        for a in Aba::TODAS {
            let esperado = !matches!(a, Aba::Analise(_) | Aba::Relatorio);
            assert_eq!(s.aba_disponivel(a), esperado, "{a:?}");
        }
        s.ir_para_aba(Aba::Analise(TipoAnalise::Sankey));
        assert_eq!(s.aba, Aba::Resumo);
        s.ir_para_aba(Aba::Estrategico);
        assert_eq!(s.aba, Aba::Estrategico);
        assert!(s.cena(Aba::Analise(TipoAnalise::Sankey)).is_err());
    }

    #[test]
    fn slugs_unicos_e_reversiveis() {
        let mut v: Vec<&str> = Aba::TODAS.iter().map(|a| a.slug()).collect();
        v.sort();
        v.dedup();
        assert_eq!(v.len(), Aba::TODAS.len());
        for a in Aba::TODAS {
            assert_eq!(Aba::de_slug(a.slug()), Some(a));
        }
        assert!(Aba::Rede.tem_cena() && !Aba::Resumo.tem_cena() && !Aba::Relatorio.tem_cena());
    }

    #[test]
    fn selecao_carrega_titulos_e_limpa_ao_recalcular() {
        let mut s = estado();
        s.abrir_demonstracao();
        s.selecionar_grupo(Some(0));
        let n = s.resultado.as_ref().unwrap().grupos[0].doc_ids.len();
        assert!(n > 0);
        assert_eq!(s.titulos.len(), n);
        s.selecionar_grupo(Some(999));
        assert_eq!(s.selecao, None);
        s.selecionar_grupo(Some(1));
        s.escolher_estrutura(Estrutura::Social);
        assert_eq!(s.selecao, None);
        assert!(s.titulos.is_empty());
    }

    fn esperar_importacao(s: &mut Estado) {
        for _ in 0..600 {
            if !s.importar_atualizar() {
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        panic!("importação não terminou");
    }

    fn estado_rapido() -> Estado {
        use crate::servicos::{ImportadorEmBreve, Servicos};
        let mut sv = Servicos::em_breve();
        sv.importador = Box::new(ImportadorEmBreve { passo: std::time::Duration::from_millis(25) });
        Estado::com_servicos(Box::new(Demonstracao::default()), sv)
    }

    #[test]
    fn importar_valida_formulario() {
        let mut s = estado_rapido();
        s.importar_iniciar();
        assert!(s.importacao.erro.as_deref().unwrap().contains("arquivo"));
        s.importar_escolher(Path::new("/tmp/corpus scopus.csv"));
        assert_eq!(s.importacao.nome, "corpus scopus");
        s.importacao.periodos = "2020-2010".into();
        s.importar_iniciar();
        assert!(s.importacao.erro.as_deref().unwrap().contains("depois do fim"));
        assert!(!s.importacao.em_andamento());
    }

    #[test]
    fn importar_progride_e_termina_com_aviso_do_stub() {
        let mut s = estado_rapido();
        s.importar_escolher(Path::new("/tmp/c.csv"));
        s.importacao.periodos = "2010-2015, 2016-2020".into();
        s.importar_iniciar();
        assert!(s.importacao.em_andamento() && s.importacao.progresso.is_some());
        esperar_importacao(&mut s);
        assert!(s.importacao.erro.as_deref().unwrap().contains("em breve"));
        assert_eq!(s.tela, Tela::Importar);
    }

    #[test]
    fn importar_cancela() {
        use crate::servicos::{ImportadorEmBreve, Servicos};
        let mut sv = Servicos::em_breve();
        sv.importador = Box::new(ImportadorEmBreve { passo: std::time::Duration::from_millis(800) });
        let mut s = Estado::com_servicos(Box::new(Demonstracao::default()), sv);
        s.importar_escolher(Path::new("/tmp/c.csv"));
        s.importar_iniciar();
        s.importar_cancelar();
        esperar_importacao(&mut s);
        assert_eq!(s.importacao.aviso.as_deref(), Some("Importação cancelada."));
        assert!(s.importacao.erro.is_none());
    }

    #[test]
    fn escolher_redes_abre_direto() {
        let mut s = estado();
        let f = std::env::temp_dir().join(format!("redes_i_{}.REDES", std::process::id()));
        std::fs::write(&f, b"x").unwrap();
        s.importar_escolher(&f);
        assert_eq!(s.tela, Tela::Analise);
        let _ = std::fs::remove_file(f);
    }

    #[test]
    fn pacote_macos_declara_nome_e_versao() {
        let plist = include_str!("../../../packaging/Info.plist");
        assert!(plist.contains("<key>CFBundleName</key><string>Redes</string>"));
        assert!(plist.contains("<key>CFBundleShortVersionString</key><string>@VERSAO@</string>"));
        assert!(plist.contains("<key>CFBundleIconFile</key><string>Redes</string>"));
        // O script de empacotamento troca @VERSAO@ pela versão do Cargo (ou de VERSAO).
        let script = include_str!("../../../scripts/empacotar_mac.sh");
        assert!(script.contains("s/@VERSAO@/$VERSAO/g"));
        assert!(!env!("CARGO_PKG_VERSION").is_empty());
    }
}
