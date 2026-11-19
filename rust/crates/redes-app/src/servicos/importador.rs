//! Importação de corpus: do arquivo exportado da base a um projeto `.redes`.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FormatoCorpus {
    /// Detecta pelo conteúdo e pela extensão.
    Automatico,
    Scopus,
    WebOfScience,
    OpenAlex,
    BibtexRis,
}

impl FormatoCorpus {
    pub const TODOS: [FormatoCorpus; 5] = [
        FormatoCorpus::Automatico,
        FormatoCorpus::Scopus,
        FormatoCorpus::WebOfScience,
        FormatoCorpus::OpenAlex,
        FormatoCorpus::BibtexRis,
    ];

    pub fn rotulo(self) -> &'static str {
        match self {
            FormatoCorpus::Automatico => "Detectar automaticamente",
            FormatoCorpus::Scopus => "Scopus (CSV)",
            FormatoCorpus::WebOfScience => "Web of Science (texto)",
            FormatoCorpus::OpenAlex => "OpenAlex (CSV ou JSON)",
            FormatoCorpus::BibtexRis => "BibTeX ou RIS",
        }
    }

    /// Extensões aceitas no seletor de arquivo.
    pub fn extensoes(self) -> &'static [&'static str] {
        match self {
            FormatoCorpus::Automatico => &["csv", "txt", "bib", "ris", "json"],
            FormatoCorpus::Scopus => &["csv"],
            FormatoCorpus::WebOfScience => &["txt"],
            FormatoCorpus::OpenAlex => &["csv", "json"],
            FormatoCorpus::BibtexRis => &["bib", "ris"],
        }
    }
}

/// Intervalo de anos, inclusive nas duas pontas.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PeriodoSpec {
    pub inicio: i32,
    pub fim: i32,
}

impl PeriodoSpec {
    pub fn rotulo(&self) -> String {
        if self.inicio == self.fim { self.inicio.to_string() } else { format!("{}–{}", self.inicio, self.fim) }
    }
}

/// Lê "2011-2016, 2017–2019; 2020" (vírgula, ponto e vírgula ou quebra de linha
/// separam; hífen, meia-risca ou "a" ligam os anos). Texto vazio = sem divisão.
pub fn parse_periodos(texto: &str) -> Result<Vec<PeriodoSpec>, String> {
    let mut v: Vec<PeriodoSpec> = Vec::new();
    for parte in texto.split([',', ';', '\n']).map(str::trim).filter(|p| !p.is_empty()) {
        let norm = parte.replace(['–', '—'], "-").replace(" a ", "-");
        let anos: Vec<&str> = norm.split('-').map(str::trim).collect();
        let ano = |t: &str| -> Result<i32, String> {
            let n: i32 = t.parse().map_err(|_| format!("Período inválido: \"{parte}\"."))?;
            if (1000..=2200).contains(&n) { Ok(n) } else { Err(format!("Ano fora do intervalo em \"{parte}\".")) }
        };
        let p = match anos.as_slice() {
            [a] => PeriodoSpec { inicio: ano(a)?, fim: ano(a)? },
            [a, b] => PeriodoSpec { inicio: ano(a)?, fim: ano(b)? },
            _ => return Err(format!("Período inválido: \"{parte}\".")),
        };
        if p.inicio > p.fim {
            return Err(format!("O início é depois do fim em \"{parte}\"."));
        }
        v.push(p);
    }
    v.sort_by_key(|p| p.inicio);
    for w in v.windows(2) {
        if w[1].inicio <= w[0].fim {
            return Err(format!("Os períodos {} e {} se sobrepõem.", w[0].rotulo(), w[1].rotulo()));
        }
    }
    Ok(v)
}

#[derive(Clone, Debug, PartialEq)]
pub struct OpcoesImportacao {
    pub arquivo: PathBuf,
    pub nome: String,
    pub formato: FormatoCorpus,
    /// Vazio = um único período com todos os anos.
    pub periodos: Vec<PeriodoSpec>,
}

impl OpcoesImportacao {
    /// Onde o projeto será gravado: ao lado do arquivo de origem.
    pub fn saida(&self) -> PathBuf {
        let base = if self.nome.trim().is_empty() { "projeto" } else { self.nome.trim() };
        self.arquivo.with_file_name(format!("{base}.redes"))
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Progresso {
    /// De 0 a 1.
    pub fracao: f32,
    pub etapa: String,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Desfecho {
    Concluida(PathBuf),
    Cancelada,
    Falhou(String),
}

/// Importação em andamento. Quem implementa o serviço real devolve um destes.
pub trait Tarefa: Send {
    fn progresso(&self) -> Progresso;
    fn cancelar(&self);
    /// `None` enquanto roda; `Some` uma única vez, quando termina.
    fn desfecho(&mut self) -> Option<Desfecho>;
}

pub trait Importador: Send {
    /// O importador real está ligado? Se não, a interface avisa que é uma simulação.
    fn disponivel(&self) -> bool;
    fn iniciar(&self, opcoes: OpcoesImportacao) -> Result<Box<dyn Tarefa>, String>;
}

/// Entregue à função de trabalho para informar progresso e checar cancelamento.
#[derive(Clone)]
pub struct Controle {
    progresso: Arc<Mutex<Progresso>>,
    cancelado: Arc<AtomicBool>,
}

impl Controle {
    pub fn avancar(&self, fracao: f32, etapa: impl Into<String>) {
        if let Ok(mut p) = self.progresso.lock() {
            *p = Progresso { fracao: fracao.clamp(0.0, 1.0), etapa: etapa.into() };
        }
    }

    pub fn cancelado(&self) -> bool {
        self.cancelado.load(Ordering::Relaxed)
    }
}

/// `Tarefa` pronta: roda uma função em outra thread. Reaproveitável pelo importador real.
pub struct TarefaEmThread {
    ctl: Controle,
    rx: mpsc::Receiver<Result<PathBuf, String>>,
    fio: Option<JoinHandle<()>>,
    fim: bool,
}

impl TarefaEmThread {
    pub fn lancar<F>(trabalho: F) -> Self
    where
        F: FnOnce(&Controle) -> Result<PathBuf, String> + Send + 'static,
    {
        let ctl = Controle {
            progresso: Arc::new(Mutex::new(Progresso { fracao: 0.0, etapa: "Iniciando".into() })),
            cancelado: Arc::new(AtomicBool::new(false)),
        };
        let (tx, rx) = mpsc::channel();
        let c2 = ctl.clone();
        let fio = std::thread::spawn(move || {
            let _ = tx.send(trabalho(&c2));
        });
        TarefaEmThread { ctl, rx, fio: Some(fio), fim: false }
    }
}

impl Tarefa for TarefaEmThread {
    fn progresso(&self) -> Progresso {
        self.ctl.progresso.lock().map(|p| p.clone()).unwrap_or(Progresso { fracao: 0.0, etapa: String::new() })
    }

    fn cancelar(&self) {
        self.ctl.cancelado.store(true, Ordering::Relaxed);
    }

    fn desfecho(&mut self) -> Option<Desfecho> {
        if self.fim {
            return None;
        }
        let r = match self.rx.try_recv() {
            Ok(r) => r,
            Err(mpsc::TryRecvError::Empty) => return None,
            Err(mpsc::TryRecvError::Disconnected) => Err("A importação terminou de forma inesperada.".into()),
        };
        self.fim = true;
        if let Some(f) = self.fio.take() {
            let _ = f.join();
        }
        Some(match r {
            Ok(p) => Desfecho::Concluida(p),
            Err(_) if self.ctl.cancelado() => Desfecho::Cancelada,
            Err(e) => Desfecho::Falhou(e),
        })
    }
}

/// Stub da fase 1: percorre as etapas de forma simulada (para a tela ser testável
/// com barra de progresso e cancelamento) e termina avisando que o importador
/// real ainda não está ligado. Não lê nem grava nenhum arquivo.
pub struct ImportadorEmBreve {
    /// Duração de cada etapa simulada.
    pub passo: Duration,
}

impl Default for ImportadorEmBreve {
    fn default() -> Self {
        ImportadorEmBreve { passo: Duration::from_millis(350) }
    }
}

pub const ETAPAS_SIMULADAS: [&str; 6] = [
    "Lendo o arquivo",
    "Reconhecendo os campos",
    "Normalizando autores e instituições",
    "Dividindo em períodos",
    "Montando as tabelas",
    "Gravando o projeto",
];

impl Importador for ImportadorEmBreve {
    fn disponivel(&self) -> bool {
        false
    }

    fn iniciar(&self, opcoes: OpcoesImportacao) -> Result<Box<dyn Tarefa>, String> {
        if opcoes.nome.trim().is_empty() {
            return Err("Dê um nome ao projeto.".into());
        }
        let passo = self.passo;
        Ok(Box::new(TarefaEmThread::lancar(move |ctl| {
            for (i, etapa) in ETAPAS_SIMULADAS.iter().enumerate() {
                ctl.avancar(i as f32 / ETAPAS_SIMULADAS.len() as f32, *etapa);
                // Dorme em fatias curtas para responder logo ao cancelamento.
                let fatias = (passo.as_millis() / 25).max(1);
                for _ in 0..fatias {
                    if ctl.cancelado() {
                        return Err("Cancelada.".into());
                    }
                    std::thread::sleep(Duration::from_millis(25));
                }
            }
            Err("O importador de corpus ainda não está ligado nesta versão (em breve). Nada foi gravado.".into())
        })))
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    fn opcoes() -> OpcoesImportacao {
        OpcoesImportacao { arquivo: PathBuf::from("/tmp/scopus.csv"), nome: "meu corpus".into(), formato: FormatoCorpus::Automatico, periodos: vec![] }
    }

    fn esperar(t: &mut dyn Tarefa) -> Desfecho {
        for _ in 0..400 {
            if let Some(d) = t.desfecho() {
                return d;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        panic!("tarefa não terminou");
    }

    #[test]
    fn periodos_validos() {
        let v = parse_periodos("2011-2016, 2017–2019; 2020\n2021 a 2023").unwrap();
        assert_eq!(v.len(), 4);
        assert_eq!(v[0], PeriodoSpec { inicio: 2011, fim: 2016 });
        assert_eq!(v[2].rotulo(), "2020");
        assert_eq!(v[3].rotulo(), "2021–2023");
        assert!(parse_periodos("  ").unwrap().is_empty());
        // Ordena.
        assert_eq!(parse_periodos("2020-2022, 2010-2012").unwrap()[0].inicio, 2010);
    }

    #[test]
    fn periodos_invalidos() {
        assert!(parse_periodos("abc").unwrap_err().contains("inválido"));
        assert!(parse_periodos("2020-2010").unwrap_err().contains("depois do fim"));
        assert!(parse_periodos("2010-2015, 2015-2020").unwrap_err().contains("sobrepõem"));
        assert!(parse_periodos("20-30").unwrap_err().contains("fora do intervalo"));
        assert!(parse_periodos("2010-2012-2014").is_err());
    }

    #[test]
    fn saida_ao_lado_do_arquivo() {
        assert_eq!(opcoes().saida(), PathBuf::from("/tmp/meu corpus.redes"));
        let mut o = opcoes();
        o.nome = "  ".into();
        assert_eq!(o.saida(), PathBuf::from("/tmp/projeto.redes"));
    }

    #[test]
    fn stub_exige_nome() {
        let mut o = opcoes();
        o.nome = String::new();
        assert!(ImportadorEmBreve::default().iniciar(o).is_err());
    }

    #[test]
    fn stub_percorre_etapas_e_avisa_que_nao_esta_ligado() {
        let imp = ImportadorEmBreve { passo: Duration::from_millis(25) };
        assert!(!imp.disponivel());
        let mut t = imp.iniciar(opcoes()).unwrap();
        match esperar(t.as_mut()) {
            Desfecho::Falhou(m) => assert!(m.contains("em breve")),
            d => panic!("{d:?}"),
        }
        assert_eq!(t.desfecho(), None);
    }

    #[test]
    fn cancelamento_funciona() {
        let imp = ImportadorEmBreve { passo: Duration::from_millis(500) };
        let mut t = imp.iniciar(opcoes()).unwrap();
        std::thread::sleep(Duration::from_millis(60));
        assert!(t.progresso().fracao < 1.0 && !t.progresso().etapa.is_empty());
        t.cancelar();
        assert_eq!(esperar(t.as_mut()), Desfecho::Cancelada);
    }

    #[test]
    fn tarefa_em_thread_conclui_com_caminho() {
        let mut t = TarefaEmThread::lancar(|c| {
            c.avancar(0.5, "meio");
            Ok(PathBuf::from("/tmp/a.redes"))
        });
        assert_eq!(esperar(&mut t), Desfecho::Concluida(PathBuf::from("/tmp/a.redes")));
    }
}
