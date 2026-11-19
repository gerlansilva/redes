//! Backend de demonstração: dados fictícios, determinísticos por
//! (estrutura, período), para a interface funcionar sem o núcleo.

use super::Backend;
use crate::modelo::*;
use std::path::Path;

#[derive(Default)]
pub struct Demonstracao {
    info: Option<InfoProjeto>,
    /// Número fixo de agrupamentos (para testar com 100 ou mais); `None` = 6 a 8.
    grupos: Option<usize>,
}

impl Demonstracao {
    /// Demonstração com `n` agrupamentos (REDES_DEMO_GRUPOS no binário).
    pub fn com_grupos(n: usize) -> Self {
        Demonstracao { info: None, grupos: Some(n.max(1)) }
    }
}

/// Gerador congruencial simples (determinístico, sem dependências).
struct Lcg(u64);
impl Lcg {
    fn prox(&mut self) -> u64 {
        self.0 = self.0.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        self.0 >> 33
    }
    fn unit(&mut self) -> f64 {
        (self.prox() % 1_000_000) as f64 / 1_000_000.0
    }
}

const PALAVRAS: &[&str] = &[
    "educação estatística", "letramento estatístico", "formação de professores",
    "raciocínio estatístico", "probabilidade", "tecnologia", "ensino fundamental",
    "currículo", "modelagem", "pensamento computacional", "dados", "variabilidade",
    "gráficos", "medidas de tendência central", "avaliação", "livros didáticos",
    "ensino superior", "inclusão", "resolução de problemas", "conhecimento docente",
    "história", "pesquisa", "cultura estatística", "formação inicial",
    "anos iniciais", "projetos", "interdisciplinaridade", "software", "BNCC",
    "inferência", "amostragem", "tabelas", "educação financeira", "mídia",
    "estudos de caso", "colaboração", "etnomatemática", "jogos", "simulação", "incerteza",
];

fn gerar(par: &Parametros, fixo: Option<usize>) -> Resultado {
    let seed = 7919u64
        .wrapping_mul(par.estrutura as u64 + 3)
        .wrapping_add(par.periodo.map(|p| p as u64 + 1).unwrap_or(0) * 104_729);
    let mut r = Lcg(seed);
    let n_grupos = fixo.unwrap_or(6 + (r.prox() % 3) as usize);
    let mut prox_doc = 1i64; // até 8 grupos x 5 termos = 40, sem repetir palavra
    let mut grupos = Vec::new();
    let mut nos = Vec::new();
    let mut arestas = Vec::new();
    let mut baralho: Vec<usize> = (0..PALAVRAS.len()).collect();
    for i in (1..baralho.len()).rev() {
        let j = (r.prox() as usize) % (i + 1);
        baralho.swap(i, j);
    }
    let mut cursor = 0usize;
    for g in 0..n_grupos {
        let tam = 3 + (r.prox() % 3) as usize;
        let inicio = nos.len();
        for k in 0..tam {
            let mut p = PALAVRAS[baralho[cursor % baralho.len()]].to_string();
            if cursor >= baralho.len() {
                p = format!("{p} {}", cursor / baralho.len() + 1);
            }
            cursor += 1;
            let peso = (1.0 + r.unit() * 12.0).round() + if k == 0 { 10.0 } else { 0.0 };
            nos.push(No { id: nos.len(), rotulo: p, grupo: g, peso });
        }
        let fim = nos.len();
        // Arestas dentro do grupo: estrela + algumas extras.
        for i in inicio + 1..fim {
            arestas.push(Aresta { a: inicio, b: i, peso: 2.0 + (r.unit() * 6.0).round() });
        }
        for i in inicio + 1..fim {
            for j in i + 1..fim {
                if r.unit() < 0.35 {
                    arestas.push(Aresta { a: i, b: j, peso: 1.0 + (r.unit() * 3.0).round() });
                }
            }
        }
        let lider = nos[inicio].rotulo.clone();
        let docs: u32 = nos[inicio..fim].iter().map(|n| n.peso as u32).sum();
        grupos.push(Grupo {
            id: g,
            nome: lider,
            centralidade: 0.1 + r.unit() * 0.9,
            densidade: 0.1 + r.unit() * 0.9,
            faixa_c: 0.0,
            faixa_d: 0.0,
            tamanho: (fim - inicio) as u32,
            documentos: docs,
            citacoes: Some(docs * (3 + (r.prox() % 9) as u32)),
            quadrante: Quadrante::Motor,
            doc_ids: (prox_doc..prox_doc + docs as i64).collect(),
        });
        prox_doc += docs as i64;
    }
    // Arestas entre grupos (ligações de centralidade).
    for g in 0..n_grupos {
        let h = (g + 1 + (r.prox() as usize % 2)) % n_grupos;
        if g == h {
            continue;
        }
        let a = nos.iter().position(|n| n.grupo == g).unwrap();
        let b = nos.iter().position(|n| n.grupo == h).unwrap();
        arestas.push(Aresta { a, b, peso: 1.0 + (r.unit() * 2.0).round() });
    }
    let fc = faixas(&grupos.iter().map(|g| g.centralidade).collect::<Vec<_>>());
    let fd = faixas(&grupos.iter().map(|g| g.densidade).collect::<Vec<_>>());
    for (i, g) in grupos.iter_mut().enumerate() {
        g.faixa_c = fc[i];
        g.faixa_d = fd[i];
        g.quadrante = Quadrante::classificar(fc[i], fd[i], 0.5, 0.5);
    }
    let resumo = Resumo {
        documentos: 280 / (1 + par.periodo.map(|_| 3).unwrap_or(0)),
        nos: nos.len() as u32,
        arestas: arestas.len() as u32,
        grupos: grupos.len() as u32,
    };
    Resultado { grupos, nos, arestas, resumo }
}

impl Backend for Demonstracao {
    fn abrir(&mut self, caminho: &Path) -> Result<InfoProjeto, String> {
        if !caminho.exists() {
            return Err(format!("Arquivo não encontrado: {}", caminho.display()));
        }
        let nome = caminho
            .file_stem()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_else(|| "projeto".into());
        let info = InfoProjeto {
            nome,
            caminho: caminho.display().to_string(),
            documentos: 280,
            periodos: vec!["2011–2016".into(), "2017–2019".into(), "2020–2022".into(), "2023–2025".into()],
        };
        self.info = Some(info.clone());
        Ok(info)
    }

    fn abrir_demonstracao(&mut self) -> Result<InfoProjeto, String> {
        let info = InfoProjeto {
            nome: "demonstracao".into(),
            caminho: "(dados fictícios)".into(),
            documentos: 280,
            periodos: vec!["2011–2016".into(), "2017–2019".into(), "2020–2022".into(), "2023–2025".into()],
        };
        self.info = Some(info.clone());
        Ok(info)
    }

    fn executar(&self, parametros: &Parametros) -> Result<Resultado, String> {
        if self.info.is_none() {
            return Err("Nenhum projeto aberto.".into());
        }
        Ok(gerar(parametros, self.grupos))
    }

    fn titulos(&self, ids: &[i64]) -> std::collections::HashMap<i64, String> {
        ids.iter()
            .map(|&i| {
                let a = PALAVRAS[(i as usize * 7) % PALAVRAS.len()];
                let b = PALAVRAS[(i as usize * 13 + 5) % PALAVRAS.len()];
                (i, format!("Estudo {i} sobre {a} e {b}"))
            })
            .collect()
    }

    fn origem(&self) -> &'static str {
        "dados de demonstração"
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    fn aberto() -> Demonstracao {
        let mut d = Demonstracao::default();
        d.abrir_demonstracao().unwrap();
        d
    }

    #[test]
    fn determinista() {
        let d = aberto();
        let p = Parametros::default();
        assert_eq!(d.executar(&p).unwrap(), d.executar(&p).unwrap());
    }

    #[test]
    fn varia_com_estrutura_e_periodo() {
        let d = aberto();
        let a = d.executar(&Parametros::default()).unwrap();
        let b = d.executar(&Parametros { periodo: Some(1), ..Default::default() }).unwrap();
        let c = d.executar(&Parametros { estrutura: Estrutura::Social, ..Default::default() }).unwrap();
        assert_ne!(a, b);
        assert_ne!(a, c);
    }

    #[test]
    fn consistencia() {
        let d = aberto();
        for e in Estrutura::TODAS {
            for per in [None, Some(0), Some(3)] {
                let r = d.executar(&Parametros { estrutura: e, periodo: per, ..Default::default() }).unwrap();
                assert!(r.grupos.len() >= 6);
                let mut rot: Vec<&str> = r.nos.iter().map(|n| n.rotulo.as_str()).collect();
                rot.sort();
                rot.dedup();
                assert_eq!(rot.len(), r.nos.len());
                for ar in &r.arestas {
                    assert!(ar.a < r.nos.len() && ar.b < r.nos.len() && ar.a != ar.b);
                }
                for n in &r.nos {
                    assert!(n.grupo < r.grupos.len());
                }
                // Há ao menos um tema em cada lado dos limiares.
                assert!(r.grupos.iter().any(|g| g.quadrante == Quadrante::Motor || g.quadrante == Quadrante::Nicho));
            }
        }
    }

    #[test]
    fn sem_projeto_e_erro() {
        assert!(Demonstracao::default().executar(&Parametros::default()).is_err());
    }

    #[test]
    fn abrir_inexistente_falha() {
        let mut d = Demonstracao::default();
        assert!(d.abrir(Path::new("/nao/existe.redes")).is_err());
    }
}
