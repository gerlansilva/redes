//! Tipos de dados que a interface consome. O adaptador do núcleo real
//! (`backend::real`) converte o `Resultado` de `redes-core` para estes tipos.

use std::fmt;

/// As quatro análises da barra lateral.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Estrutura {
    Fontes,
    Conceitual,
    Intelectual,
    Social,
}

impl Estrutura {
    pub const TODAS: [Estrutura; 4] = [
        Estrutura::Fontes,
        Estrutura::Conceitual,
        Estrutura::Intelectual,
        Estrutura::Social,
    ];

    pub fn rotulo(self) -> &'static str {
        match self {
            Estrutura::Fontes => "Fontes",
            Estrutura::Conceitual => "Conceitual",
            Estrutura::Intelectual => "Intelectual",
            Estrutura::Social => "Social",
        }
    }

    pub fn descricao(self) -> &'static str {
        match self {
            Estrutura::Fontes => "Periódicos do corpus e como se agrupam",
            Estrutura::Conceitual => "Temas, a partir das palavras-chave",
            Estrutura::Intelectual => "Referências e autores citados",
            Estrutura::Social => "Coautoria entre autores, instituições e países",
        }
    }

    pub fn nome_no(self) -> &'static str {
        match self {
            Estrutura::Fontes => "periódicos",
            Estrutura::Conceitual => "palavras-chave",
            Estrutura::Intelectual => "referências",
            Estrutura::Social => "autores",
        }
    }
}

/// Quadrantes do diagrama estratégico de Callon.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Quadrante {
    /// Alta centralidade, alta densidade.
    Motor,
    /// Alta centralidade, baixa densidade.
    Basico,
    /// Baixa centralidade, alta densidade.
    Nicho,
    /// Baixa centralidade, baixa densidade.
    Emergente,
}

impl Quadrante {
    pub const TODOS: [Quadrante; 4] = [
        Quadrante::Motor,
        Quadrante::Basico,
        Quadrante::Nicho,
        Quadrante::Emergente,
    ];

    pub fn rotulo(self) -> &'static str {
        match self {
            Quadrante::Motor => "Temas motores",
            Quadrante::Basico => "Temas básicos e transversais",
            Quadrante::Nicho => "Temas de nicho",
            Quadrante::Emergente => "Temas emergentes ou em declínio",
        }
    }

    pub fn curto(self) -> &'static str {
        match self {
            Quadrante::Motor => "Motor",
            Quadrante::Basico => "Básico",
            Quadrante::Nicho => "Nicho",
            Quadrante::Emergente => "Emergente",
        }
    }

    /// Classifica pelo cruzamento com os limiares (medianas) dos eixos.
    /// Interpreta o texto de quadrante do núcleo ("motor", "nicho", "emergente", "basico").
    pub fn de_texto(t: &str) -> Option<Quadrante> {
        match t.trim().to_lowercase().as_str() {
            "motor" => Some(Quadrante::Motor),
            "nicho" => Some(Quadrante::Nicho),
            "emergente" => Some(Quadrante::Emergente),
            "basico" | "básico" => Some(Quadrante::Basico),
            _ => None,
        }
    }

    pub fn classificar(centralidade: f64, densidade: f64, lim_c: f64, lim_d: f64) -> Quadrante {
        match (centralidade >= lim_c, densidade >= lim_d) {
            (true, true) => Quadrante::Motor,
            (true, false) => Quadrante::Basico,
            (false, true) => Quadrante::Nicho,
            (false, false) => Quadrante::Emergente,
        }
    }
}

impl fmt::Display for Quadrante {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.rotulo())
    }
}

/// Posição relativa de cada valor, (1..n)/n, com empates estáveis (como o núcleo).
pub fn faixas(v: &[f64]) -> Vec<f64> {
    let mut ordem: Vec<usize> = (0..v.len()).collect();
    ordem.sort_by(|&a, &b| v[a].partial_cmp(&v[b]).unwrap_or(std::cmp::Ordering::Equal));
    let mut f = vec![0.0; v.len()];
    for (pos, &i) in ordem.iter().enumerate() {
        f[i] = (pos as f64 + 1.0) / v.len() as f64;
    }
    f
}

#[derive(Clone, Debug, PartialEq)]
pub struct Grupo {
    pub id: usize,
    pub nome: String,
    pub centralidade: f64,
    pub densidade: f64,
    /// Posição relativa (1..n)/n na medida: é o que o diagrama estratégico plota.
    pub faixa_c: f64,
    pub faixa_d: f64,
    /// Número de nós do agrupamento (tamanho da esfera).
    pub tamanho: u32,
    pub documentos: u32,
    /// `None` quando o núcleo não informa citações por tema.
    pub citacoes: Option<u32>,
    pub quadrante: Quadrante,
    /// Identificadores dos documentos do agrupamento (títulos via `Backend::titulos`).
    pub doc_ids: Vec<i64>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct No {
    pub id: usize,
    pub rotulo: String,
    pub grupo: usize,
    pub peso: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Aresta {
    pub a: usize,
    pub b: usize,
    pub peso: f64,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct Resumo {
    pub documentos: u32,
    pub nos: u32,
    pub arestas: u32,
    pub grupos: u32,
}

#[derive(Clone, Debug, Default, PartialEq)]
pub struct Resultado {
    pub grupos: Vec<Grupo>,
    pub nos: Vec<No>,
    pub arestas: Vec<Aresta>,
    pub resumo: Resumo,
}

impl Resultado {
    pub fn grupos_do_quadrante(&self, q: Quadrante) -> Vec<&Grupo> {
        let mut v: Vec<&Grupo> = self.grupos.iter().filter(|g| g.quadrante == q).collect();
        v.sort_by(|a, b| b.documentos.cmp(&a.documentos).then(a.nome.cmp(&b.nome)));
        v
    }

    pub fn nos_do_grupo(&self, g: usize) -> Vec<&No> {
        let mut v: Vec<&No> = self.nos.iter().filter(|n| n.grupo == g).collect();
        v.sort_by(|a, b| b.peso.partial_cmp(&a.peso).unwrap_or(std::cmp::Ordering::Equal));
        v
    }
}

/// Parâmetros da análise, os mesmos da interface web.
#[derive(Clone, Debug, PartialEq)]
pub struct Parametros {
    pub estrutura: Estrutura,
    /// Índice em `InfoProjeto::periodos`; `None` = todos os períodos.
    pub periodo: Option<usize>,
    pub frequencia_minima: u32,
    pub coocorrencia_minima: u32,
}

impl Default for Parametros {
    fn default() -> Self {
        Parametros {
            estrutura: Estrutura::Conceitual,
            periodo: None,
            frequencia_minima: 1,
            coocorrencia_minima: 1,
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct InfoProjeto {
    pub nome: String,
    pub caminho: String,
    pub documentos: u32,
    pub periodos: Vec<String>,
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn classifica_quadrantes() {
        assert_eq!(Quadrante::classificar(2.0, 2.0, 1.0, 1.0), Quadrante::Motor);
        assert_eq!(Quadrante::classificar(2.0, 0.5, 1.0, 1.0), Quadrante::Basico);
        assert_eq!(Quadrante::classificar(0.5, 2.0, 1.0, 1.0), Quadrante::Nicho);
        assert_eq!(Quadrante::classificar(0.5, 0.5, 1.0, 1.0), Quadrante::Emergente);
        // Valor igual ao limiar fica no lado alto.
        assert_eq!(Quadrante::classificar(1.0, 1.0, 1.0, 1.0), Quadrante::Motor);
        assert_eq!(Quadrante::de_texto("basico"), Some(Quadrante::Basico));
        assert_eq!(Quadrante::de_texto("x"), None);
        assert_eq!(faixas(&[10.0, 30.0, 20.0, 40.0]), vec![0.25, 0.75, 0.5, 1.0]);
    }
}
