//! Importação de exportações bibliográficas para um projeto `.redes` (SQLite).
//!
//! Formatos: Scopus (CSV), Web of Science (texto e tabulado), OpenAlex (CSV e JSON), RIS,
//! BibTeX, CSV genérico e Zotero (CSV e RIS). O esquema e o conteúdo gravados são os mesmos
//! do importador Python (`redes/build.py`), de modo que `redes-core` abre o resultado.
//!
//! ```no_run
//! use redes_importa::{importar, Opcoes};
//! let g = importar("scopus.csv", &Opcoes::default()).unwrap();
//! println!("{} documentos em {}", g.resumo.documentos, g.caminho.display());
//! ```

pub mod construtor;
mod dados_paises;
pub mod erro;
pub mod fonte;
pub mod loaders;
pub mod paises;
pub mod referencias;
pub mod util;

use std::path::{Path, PathBuf};

pub use construtor::AutoresReferencia;
pub use erro::{Erro, Resultado};
pub use fonte::DocumentoFonte;
pub use loaders::{detecta_formato, le_corpus, Formato};

use construtor::{periodos_a_partir_dos_anos, sugere_periodos, unifica_periodicos, Construtor, Periodo};
use indexmap::IndexMap;
use util::*;

/// Opções da importação.
#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
#[serde(default)]
pub struct Opcoes {
    /// `None` = detectar pelo conteúdo.
    pub formato: Option<Formato>,
    /// Nome do projeto (arquivo `<nome>.redes`). Padrão: nome do arquivo de origem.
    pub nome: Option<String>,
    /// Faixas `2008-2014,2015-2020` (cada uma pode ter nome: `Antes=1990-2000`); um número
    /// (`3`) pede essa quantidade de períodos automáticos; `unico` pede um só. `None` = 1 a 4
    /// períodos automáticos.
    pub periodos: Option<String>,
    /// Pasta de destino. Padrão: a pasta do arquivo de origem.
    pub pasta: Option<PathBuf>,
    /// Junta registros com o mesmo DOI ou título e ano (padrão: sim).
    pub remove_repetidos: bool,
    /// Quem conta como autor citado (padrão: o primeiro autor da obra).
    pub autores_referencia: AutoresReferencia,
    /// Junta periódicos que só diferem por caixa, acento ou pontuação (padrão: sim).
    pub unir_periodicos: bool,
}

impl Default for Opcoes {
    fn default() -> Self {
        Opcoes {
            formato: None,
            nome: None,
            periodos: None,
            pasta: None,
            remove_repetidos: true,
            autores_referencia: AutoresReferencia::Primeiro,
            unir_periodicos: true,
        }
    }
}

/// Resumo da importação (campos de `build.constroi`).
#[derive(Clone, Debug, Default, serde::Serialize)]
pub struct Resumo {
    pub formato: String,
    pub documentos: usize,
    pub documentos_lidos: usize,
    pub duplicatas_removidas: usize,
    /// Até 50 pares (título, motivo).
    pub duplicatas: Vec<(String, String)>,
    pub sem_palavras: usize,
    pub sem_pais: usize,
    pub sem_citacoes: usize,
    pub sem_referencias: usize,
    pub palavras: usize,
    pub grupos_palavra: i64,
    pub autores: usize,
    pub grupos_autor: i64,
    pub referencias: usize,
    pub grupos_referencia: i64,
    pub autores_referencia: usize,
    pub grupos_autor_referencia: i64,
    pub fontes: usize,
    pub grupos_fonte: i64,
    pub paises: usize,
    pub afiliacoes: usize,
    pub periodos: Vec<String>,
    pub periodicos_unidos: IndexMap<String, Vec<String>>,
}

#[derive(Clone, Debug, serde::Serialize)]
pub struct ProjetoGravado {
    pub caminho: PathBuf,
    pub resumo: Resumo,
}

/// Importa sem acompanhar o progresso.
pub fn importar(arquivo: impl AsRef<Path>, opcoes: &Opcoes) -> Resultado<ProjetoGravado> {
    importar_com_progresso(arquivo, opcoes, &mut |_, _| {})
}

/// Importa chamando `progresso(fase, fração entre 0 e 1 da fase)`.
pub fn importar_com_progresso(arquivo: impl AsRef<Path>, opcoes: &Opcoes, progresso: &mut dyn FnMut(&str, f32)) -> Resultado<ProjetoGravado> {
    let arquivo = arquivo.as_ref();
    progresso("Lendo o arquivo", 0.0);
    let (documentos, formato) = le_corpus(arquivo, opcoes.formato)?;
    if documentos.is_empty() {
        return Err(Erro::SemDocumentos(format!("{} (formato {}); confira o formato do arquivo", arquivo.display(), formato.nome())));
    }
    let faixas = interpreta_periodos(opcoes.periodos.as_deref().unwrap_or(""))?;

    let nome = match &opcoes.nome {
        Some(n) if !n.trim().is_empty() => nome_seguro(n),
        _ => nome_seguro(arquivo.file_stem().and_then(|s| s.to_str()).unwrap_or("projeto")),
    };
    let pasta = match &opcoes.pasta {
        Some(p) => p.clone(),
        None => arquivo.parent().map(|p| p.to_path_buf()).filter(|p| !p.as_os_str().is_empty()).unwrap_or_else(|| PathBuf::from(".")),
    };
    let destino = pasta.join(format!("{nome}.redes"));

    let mut resumo = constroi(documentos, &destino, faixas, opcoes, progresso)?;
    resumo.formato = formato.nome().to_string();
    progresso("Concluído", 1.0);
    Ok(ProjetoGravado { caminho: destino, resumo })
}

fn nome_seguro(n: &str) -> String {
    let n: String = n.trim().chars().map(|c| if matches!(c, '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|') || c.is_control() { '-' } else { c }).collect();
    let n = n.trim_matches(|c: char| c == '.' || c.is_whitespace()).to_string();
    let n = n.strip_suffix(".redes").map(String::from).unwrap_or(n);
    if n.is_empty() { "projeto".to_string() } else { n }
}

/// Faixas pedidas pelo usuário.
#[derive(Clone, Debug, PartialEq)]
pub enum PeriodosPedidos {
    Automatico,
    Quantidade(i64),
    Unico,
    Faixas(Vec<Periodo>),
}

pub fn interpreta_periodos(texto: &str) -> Resultado<PeriodosPedidos> {
    let t = strip(texto);
    if t.is_empty() {
        return Ok(PeriodosPedidos::Automatico);
    }
    let minusculo = t.to_lowercase();
    if minusculo == "unico" || minusculo == "único" {
        return Ok(PeriodosPedidos::Unico);
    }
    if t.chars().all(|c| c.is_ascii_digit()) && t.len() <= 2 {
        let q: i64 = t.parse().unwrap();
        if q >= 1 {
            return Ok(PeriodosPedidos::Quantidade(q));
        }
    }
    let mut faixas = vec![];
    for parte in t.split([',', ';']) {
        let parte = strip(parte);
        if parte.is_empty() {
            continue;
        }
        let (rotulo, intervalo) = match parte.split_once('=') {
            Some((r, i)) => (Some(strip(r).to_string()), strip(i)),
            None => (None, parte),
        };
        let c = rx!(r"^(\d{4})\s*(?:[-\u{2013}\u{2014}]|\.\.)\s*(\d{4})$").captures(intervalo).ok().flatten().ok_or_else(|| {
            Erro::Opcao(format!("faixa de período inválida: {parte:?}; use 2008-2014, separando as faixas por vírgula"))
        })?;
        let inicio: i64 = c[1].parse().unwrap();
        let fim: i64 = c[2].parse().unwrap();
        if inicio > fim {
            return Err(Erro::Opcao(format!("faixa invertida: {parte}")));
        }
        faixas.push((rotulo.filter(|r| !r.is_empty()).unwrap_or_else(|| format!("{inicio}\u{2013}{fim}")), inicio, fim));
    }
    if faixas.is_empty() {
        return Ok(PeriodosPedidos::Automatico);
    }
    Ok(PeriodosPedidos::Faixas(faixas))
}

fn constroi(documentos: Vec<DocumentoFonte>, destino: &Path, pedidos: PeriodosPedidos, opcoes: &Opcoes, progresso: &mut dyn FnMut(&str, f32)) -> Resultado<Resumo> {
    let total_original = documentos.len();
    progresso("Juntando duplicatas", 0.0);
    let (mut documentos, repetidos) = if opcoes.remove_repetidos { fonte::remove_duplicatas(documentos) } else { (documentos, vec![]) };

    let anos: Vec<i64> = documentos.iter().filter(|d| !d.ano.is_empty() && d.ano.chars().all(|c| c.is_ascii_digit())).filter_map(|d| d.ano.parse().ok()).collect();
    let periodos: Vec<Periodo> = match pedidos {
        PeriodosPedidos::Faixas(f) => f,
        PeriodosPedidos::Automatico => periodos_a_partir_dos_anos(&documentos),
        PeriodosPedidos::Quantidade(q) => sugere_periodos(&anos, Some(q), 40),
        PeriodosPedidos::Unico => match (anos.iter().min(), anos.iter().max()) {
            (Some(a), Some(b)) => vec![(format!("{a}\u{2013}{b}"), *a, *b)],
            _ => vec![("0\u{2013}9999".into(), 0, 9999)],
        },
    };

    let periodicos_unidos = if opcoes.unir_periodicos { unifica_periodicos(&mut documentos) } else { IndexMap::new() };
    let sem_palavras = documentos.iter().filter(|d| d.palavras_autor.is_empty() && d.palavras_fonte.is_empty()).count();
    let sem_pais = documentos.iter().filter(|d| d.paises.is_empty()).count();
    let sem_citacoes = documentos.iter().filter(|d| d.citacoes.is_none()).count();
    let n_docs = documentos.len();

    let mut c = Construtor::novo(documentos, opcoes.autores_referencia);
    c.importa(progresso);
    c.grava(destino, &periodos, progresso)?;
    let sem_referencias = c.documentos.iter().filter(|d| d.referencias.is_empty()).count();

    let conexao = rusqlite::Connection::open(destino)?;
    let conta = |t: &str| -> Resultado<i64> { Ok(conexao.query_row(&format!("SELECT COUNT(*) FROM {t}"), [], |r| r.get(0))?) };
    Ok(Resumo {
        formato: String::new(),
        documentos: n_docs,
        documentos_lidos: total_original,
        duplicatas_removidas: repetidos.len(),
        duplicatas: repetidos.into_iter().take(50).collect(),
        sem_palavras,
        sem_pais,
        sem_citacoes,
        sem_referencias,
        palavras: c.palavras.len(),
        grupos_palavra: conta("WordGroup")?,
        autores: c.autores.len(),
        grupos_autor: conta("AuthorGroup")?,
        referencias: c.referencias.len(),
        grupos_referencia: conta("ReferenceGroup")?,
        autores_referencia: c.autores_ref.len(),
        grupos_autor_referencia: conta("AuthorReferenceGroup")?,
        fontes: c.fontes.len(),
        grupos_fonte: conta("ReferenceSourceGroup")?,
        paises: c.paises.len(),
        afiliacoes: c.afiliacoes.len(),
        periodos: periodos.iter().map(|p| p.0.clone()).collect(),
        periodicos_unidos,
    })
}
