use thiserror::Error;

#[derive(Debug, Error)]
pub enum Erro {
    #[error("{0}")]
    Io(String),
    #[error("formato inválido: {0}")]
    Formato(String),
    #[error("opção inválida: {0}")]
    Opcao(String),
    #[error("nenhum documento encontrado em {0}")]
    SemDocumentos(String),
    #[error("banco de dados: {0}")]
    Banco(String),
}

impl From<rusqlite::Error> for Erro {
    fn from(e: rusqlite::Error) -> Self {
        Erro::Banco(e.to_string())
    }
}

pub type Resultado<T> = Result<T, Erro>;
