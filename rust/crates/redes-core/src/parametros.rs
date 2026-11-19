//! Parâmetros de uma análise (equivalem a `Configuracao` do Python).

use serde::{Deserialize, Serialize};

use crate::erro::{Erro, Resultado};

macro_rules! enum_texto {
    ($(#[$m:meta])* $nome:ident { $($var:ident),+ $(,)? }) => {
        $(#[$m])*
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
        pub enum $nome { $($var),+ }
        impl $nome {
            pub const TODOS: &'static [$nome] = &[$($nome::$var),+];
            pub fn nome(self) -> &'static str {
                match self { $($nome::$var => stringify!($var)),+ }
            }
            pub fn de_texto(s: &str) -> Resultado<$nome> {
                match s {
                    $(stringify!($var) => Ok($nome::$var),)+
                    _ => Err(Erro::Parametro(format!(concat!(stringify!($nome), " inválido: {}"), s))),
                }
            }
        }
    };
}

enum_texto!(
    /// Unidade de análise (o que são os itens).
    Unidade { Words, Authors, References, AuthorsReference, ReferenceSources, Countries, Institutions }
);
enum_texto!(
    /// Matriz: co-ocorrência de itens ou acoplamento.
    Matriz { CoOccurrence, BasicCoupling, AggregatedCouplingBasedOnAuthor, AggregatedCouplingBasedOnJournal }
);
enum_texto!(Similaridade { AssociationStrength, EquivalenceIndex, InclusionIndex, JaccardIndex, SaltonCosine });
enum_texto!(Algoritmo { CentersSimples, AverageLink, CompleteLink, SingleLink, SumLink, Louvain });

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Mapeador {
    Nucleo,
    Interseccao,
    Secundarios,
    Kcore,
    Uniao,
    Acoplamento,
}

impl Mapeador {
    pub fn nome(self) -> &'static str {
        match self {
            Mapeador::Nucleo => "nucleo",
            Mapeador::Interseccao => "interseccao",
            Mapeador::Secundarios => "secundarios",
            Mapeador::Kcore => "kcore",
            Mapeador::Uniao => "uniao",
            Mapeador::Acoplamento => "acoplamento",
        }
    }

    pub fn de_texto(s: &str) -> Resultado<Mapeador> {
        Ok(match s {
            "nucleo" => Mapeador::Nucleo,
            "interseccao" => Mapeador::Interseccao,
            "secundarios" => Mapeador::Secundarios,
            "kcore" => Mapeador::Kcore,
            "uniao" => Mapeador::Uniao,
            "acoplamento" => Mapeador::Acoplamento,
            _ => return Err(Erro::Parametro(format!("mapeador inválido: {s}"))),
        })
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Parametros {
    pub unidade: Unidade,
    pub matriz: Matriz,
    pub similaridade: Similaridade,
    pub algoritmo: Algoritmo,
    /// Frequência mínima de um item (em documentos).
    pub min_freq: usize,
    /// Valor mínimo de aresta antes da normalização (co-ocorrência bruta).
    pub min_cooc: f64,
    /// Tamanho mínimo do grupo (padrão 2).
    pub rede_min: usize,
    /// Tamanho máximo do grupo (padrão 15).
    pub rede_max: usize,
    /// Similaridade mínima para unir grupos nos algoritmos hierárquicos.
    pub corte: f64,
    pub mapeadores: Vec<Mapeador>,
    pub k_core: usize,
    /// Origens das palavras na unidade Words: "autor", "fonte", "adicionada".
    pub palavras: Vec<String>,
    /// Itens a descartar antes da rede (sem caixa, acento nem pontuação).
    pub ignorar: Vec<String>,
    /// Nome do período; `None` = o primeiro do projeto.
    pub periodo: Option<String>,
}

impl Default for Parametros {
    fn default() -> Self {
        Parametros {
            unidade: Unidade::Words,
            matriz: Matriz::CoOccurrence,
            similaridade: Similaridade::EquivalenceIndex,
            algoritmo: Algoritmo::CentersSimples,
            min_freq: 1,
            min_cooc: 1.0,
            rede_min: 2,
            rede_max: 15,
            corte: 0.0,
            mapeadores: vec![Mapeador::Nucleo],
            k_core: 2,
            palavras: vec!["autor".into(), "fonte".into()],
            ignorar: Vec::new(),
            periodo: None,
        }
    }
}

impl Parametros {
    pub fn valida(&self) -> Resultado<()> {
        if self.unidade == Unidade::Institutions {
            return Err(Erro::NaoSuportado(
                "unidade Institutions (depende da unificação de variantes de IES, ainda não portada)".into(),
            ));
        }
        if self.mapeadores.contains(&Mapeador::Acoplamento) && self.matriz != Matriz::BasicCoupling {
            return Err(Erro::Parametro(format!(
                "o mapeador \"acoplamento\" só vale com BasicCoupling (matriz atual: {})",
                self.matriz.nome()
            )));
        }
        for o in &self.palavras {
            if !matches!(o.as_str(), "autor" | "fonte" | "adicionada") {
                return Err(Erro::Parametro(format!("origem de palavra inválida: {o}")));
            }
        }
        if !self.corte.is_finite() || self.corte < 0.0 {
            return Err(Erro::Parametro(format!("corte inválido: {}", self.corte)));
        }
        if self.k_core < 1 {
            return Err(Erro::Parametro("k-core inválido".into()));
        }
        if self.rede_min < 1 || self.rede_max < self.rede_min {
            return Err(Erro::Parametro("tamanho de grupo inválido (rede_min <= rede_max, rede_min >= 1)".into()));
        }
        Ok(())
    }
}
