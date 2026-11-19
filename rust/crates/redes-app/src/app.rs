//! Estado e fluxo do aplicativo (independente de janela, testável).

use crate::backend::Backend;
use crate::cena::Cena;
use crate::desenho;
use crate::modelo::*;
use std::path::Path;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tela {
    BoasVindas,
    Importar,
    Analise,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Aba {
    Resumo,
    Rede,
    Estrategico,
}

impl Aba {
    pub const TODAS: [Aba; 3] = [Aba::Resumo, Aba::Rede, Aba::Estrategico];
    pub fn rotulo(self) -> &'static str {
        match self {
            Aba::Resumo => "Resumo",
            Aba::Rede => "Rede",
            Aba::Estrategico => "Diagrama estratégico",
        }
    }
}

pub struct Estado {
    pub backend: Box<dyn Backend>,
    pub tela: Tela,
    pub aba: Aba,
    pub info: Option<InfoProjeto>,
    pub params: Parametros,
    pub resultado: Option<Resultado>,
    pub erro: Option<String>,
    pub aviso: Option<String>,
    geracao: u64,
    cache: Option<(Aba, i32, i32, u64, Cena)>,
}

impl Estado {
    pub fn novo(backend: Box<dyn Backend>) -> Self {
        Estado {
            backend,
            tela: Tela::BoasVindas,
            aba: Aba::Resumo,
            info: None,
            params: Parametros::default(),
            resultado: None,
            erro: None,
            aviso: None,
            geracao: 0,
            cache: None,
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

    pub fn fechar_projeto(&mut self) {
        self.info = None;
        self.resultado = None;
        self.erro = None;
        self.tela = Tela::Importar;
    }

    /// Cena da aba atual para o tamanho dado (em cache enquanto nada muda).
    pub fn cena(&mut self, aba: Aba, largura: f32, altura: f32) -> Option<&Cena> {
        let r = self.resultado.as_ref()?;
        let (w, h) = (largura.round() as i32, altura.round() as i32);
        let valido = matches!(&self.cache, Some((a, cw, ch, g, _)) if *a == aba && *cw == w && *ch == h && *g == self.geracao);
        if !valido {
            let cena = match aba {
                Aba::Rede => desenho::rede(r, w as f32, h as f32),
                Aba::Estrategico => desenho::estrategico(r, w as f32, h as f32),
                Aba::Resumo => return None,
            };
            self.cache = Some((aba, w, h, self.geracao, cena));
        }
        self.cache.as_ref().map(|c| &c.4)
    }

    /// Cena em tamanho fixo para exportação.
    pub fn cena_para_exportar(&self, aba: Aba) -> Option<Cena> {
        let r = self.resultado.as_ref()?;
        match aba {
            Aba::Rede => Some(desenho::rede(r, 1400.0, 1000.0)),
            Aba::Estrategico => Some(desenho::estrategico(r, 1400.0, 1000.0)),
            Aba::Resumo => None,
        }
    }

    pub fn nome_arquivo_exportacao(&self, aba: Aba, ext: &str) -> String {
        let base = self.info.as_ref().map(|i| i.nome.as_str()).unwrap_or("redes");
        let parte = match aba {
            Aba::Rede => "rede",
            Aba::Estrategico => "diagrama-estrategico",
            Aba::Resumo => "resumo",
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
        let a = s.cena(Aba::Rede, 800.0, 600.0).unwrap().clone();
        assert_eq!(s.cena(Aba::Rede, 800.0, 600.0).unwrap(), &a);
        s.escolher_estrutura(Estrutura::Fontes);
        assert_ne!(s.cena(Aba::Rede, 800.0, 600.0).unwrap(), &a);
        assert!(s.cena(Aba::Resumo, 800.0, 600.0).is_none());
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
}
