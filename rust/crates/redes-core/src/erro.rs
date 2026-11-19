use thiserror::Error;

#[derive(Debug, Error)]
pub enum Erro {
    #[error("projeto não encontrado: {0}")]
    NaoEncontrado(String),
    #[error("{0} não é um projeto do Redes (.redes) válido")]
    ProjetoInvalido(String),
    #[error("período não encontrado: {0}")]
    PeriodoInexistente(String),
    #[error("parâmetro inválido: {0}")]
    Parametro(String),
    #[error("ainda não suportado no núcleo Rust: {0}")]
    NaoSuportado(String),
    #[error("erro no banco: {0}")]
    Banco(#[from] rusqlite::Error),
    #[error("erro de JSON: {0}")]
    Json(#[from] serde_json::Error),
}

pub type Resultado<T> = std::result::Result<T, Erro>;
