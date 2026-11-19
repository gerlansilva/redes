//! Análises adicionais (dendrograma, linha do tempo, densidade, similitude,
//! duplo mapa, Sankey). Cada uma devolve uma `Cena`, a mesma representação do
//! grafo e do diagrama estratégico, então zoom, dicas e exportação já funcionam.

use super::EM_BREVE;
use crate::cena::Cena;
use crate::modelo::{Parametros, Resultado};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum TipoAnalise {
    Dendrograma,
    LinhaDoTempo,
    Densidade,
    Similitude,
    DuploMapa,
    Sankey,
}

impl TipoAnalise {
    pub const TODAS: [TipoAnalise; 6] = [
        TipoAnalise::Dendrograma,
        TipoAnalise::LinhaDoTempo,
        TipoAnalise::Densidade,
        TipoAnalise::Similitude,
        TipoAnalise::DuploMapa,
        TipoAnalise::Sankey,
    ];

    pub fn rotulo(self) -> &'static str {
        match self {
            TipoAnalise::Dendrograma => "Dendrograma",
            TipoAnalise::LinhaDoTempo => "Linha do tempo",
            TipoAnalise::Densidade => "Densidade",
            TipoAnalise::Similitude => "Similitude",
            TipoAnalise::DuploMapa => "Duplo mapa",
            TipoAnalise::Sankey => "Sankey",
        }
    }

    pub fn descricao(self) -> &'static str {
        match self {
            TipoAnalise::Dendrograma => "Hierarquia de agrupamento dos termos",
            TipoAnalise::LinhaDoTempo => "Evolução dos temas entre os períodos",
            TipoAnalise::Densidade => "Mapa de calor da concentração de termos",
            TipoAnalise::Similitude => "Árvore de similitude entre os termos",
            TipoAnalise::DuploMapa => "Dois mapas lado a lado (por exemplo, dois períodos)",
            TipoAnalise::Sankey => "Fluxo de temas de um período para o seguinte",
        }
    }
}

pub trait Analises: Send {
    /// A análise está ligada nesta compilação?
    fn disponivel(&self, tipo: TipoAnalise) -> bool;
    fn gerar(&self, tipo: TipoAnalise, resultado: &Resultado, parametros: &Parametros) -> Result<Cena, String>;
}

/// Stub da fase 1: nenhuma análise disponível.
pub struct AnalisesEmBreve;

impl Analises for AnalisesEmBreve {
    fn disponivel(&self, _tipo: TipoAnalise) -> bool {
        false
    }

    fn gerar(&self, tipo: TipoAnalise, _r: &Resultado, _p: &Parametros) -> Result<Cena, String> {
        Err(format!("{}: {}.", tipo.rotulo(), EM_BREVE.to_lowercase()))
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn stub_nao_oferece_nada() {
        let s = AnalisesEmBreve;
        for t in TipoAnalise::TODAS {
            assert!(!s.disponivel(t));
            assert!(s.gerar(t, &Resultado::default(), &Parametros::default()).unwrap_err().contains("em breve"));
        }
    }
}
