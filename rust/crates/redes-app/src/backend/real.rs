//! Adaptador para `redes-core` (feature `redes-core`, ligada por padrão).

use super::Backend;
use crate::modelo::*;
use redes_core as core;
use std::collections::HashMap;
use std::path::Path;

#[derive(Default)]
pub struct Nucleo {
    projeto: Option<core::Projeto>,
    periodos: Vec<String>,
}

/// Mesmas análises da interface web (redes/ui/app.js, ANALISES).
pub fn parametros_core(par: &Parametros, nome_periodo: Option<String>) -> core::Parametros {
    let (unidade, matriz) = match par.estrutura {
        Estrutura::Fontes => (core::Unidade::ReferenceSources, core::Matriz::CoOccurrence),
        Estrutura::Conceitual => (core::Unidade::Words, core::Matriz::CoOccurrence),
        Estrutura::Intelectual => (core::Unidade::AuthorsReference, core::Matriz::CoOccurrence),
        Estrutura::Social => (core::Unidade::Authors, core::Matriz::CoOccurrence),
    };
    core::Parametros {
        unidade,
        matriz,
        min_freq: par.frequencia_minima.max(1) as usize,
        min_cooc: par.coocorrencia_minima.max(1) as f64,
        periodo: nome_periodo,
        ..Default::default()
    }
}

pub fn converter(r: &core::Resultado) -> Resultado {
    let grupos: Vec<Grupo> = r
        .grupos
        .iter()
        .enumerate()
        .map(|(i, g)| Grupo {
            id: i,
            nome: if g.exibicao.is_empty() { g.rotulo.clone() } else { g.exibicao.clone() },
            centralidade: g.centralidade,
            densidade: g.densidade,
            faixa_c: g.centralidade_faixa,
            faixa_d: g.densidade_faixa,
            tamanho: g.nos.len() as u32,
            documentos: g.documentos.get("nucleo").or_else(|| g.documentos.values().next()).map(|v| v.len() as u32).unwrap_or(0),
            citacoes: None,
            quadrante: Quadrante::de_texto(&g.quadrante).unwrap_or(Quadrante::Emergente),
            doc_ids: g.documentos.get("nucleo").or_else(|| g.documentos.values().next()).cloned().unwrap_or_default(),
        })
        .collect();
    // Só entram no grafo os nós que pertencem a algum grupo.
    let mut idx: HashMap<i64, usize> = HashMap::new();
    let mut nos = Vec::new();
    for n in &r.nos {
        if let Some(g) = n.grupo.filter(|g| *g < grupos.len()) {
            idx.insert(n.id, nos.len());
            nos.push(No { id: nos.len(), rotulo: n.rotulo.clone(), grupo: g, peso: n.frequencia.max(1) as f64 });
        }
    }
    let arestas: Vec<Aresta> = r
        .arestas
        .iter()
        .filter_map(|a| Some(Aresta { a: *idx.get(&a.a)?, b: *idx.get(&a.b)?, peso: a.peso }))
        .collect();
    let resumo = Resumo {
        documentos: r.resumo.documentos as u32,
        nos: nos.len() as u32,
        arestas: arestas.len() as u32,
        grupos: grupos.len() as u32,
    };
    Resultado { grupos, nos, arestas, resumo }
}

impl Backend for Nucleo {
    fn abrir(&mut self, caminho: &Path) -> Result<InfoProjeto, String> {
        let p = core::Projeto::abrir(caminho).map_err(|e| e.to_string())?;
        let periodos: Vec<String> = p.periodos().map_err(|e| e.to_string())?.into_iter().map(|x| x.nome).collect();
        let nome = caminho.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_else(|| "projeto".into());
        let info = InfoProjeto {
            nome,
            caminho: caminho.display().to_string(),
            // O núcleo ainda não expõe a contagem total; a interface mostra a do resumo.
            documentos: 0,
            periodos: periodos.clone(),
        };
        self.periodos = periodos;
        self.projeto = Some(p);
        Ok(info)
    }

    fn abrir_demonstracao(&mut self) -> Result<InfoProjeto, String> {
        Err("Com o núcleo real, abra um arquivo .redes.".into())
    }

    fn executar(&self, par: &Parametros) -> Result<Resultado, String> {
        let p = self.projeto.as_ref().ok_or("Nenhum projeto aberto.")?;
        let nome = par.periodo.and_then(|i| self.periodos.get(i).cloned());
        let r = core::executar(p, &parametros_core(par, nome)).map_err(|e| e.to_string())?;
        Ok(converter(&r))
    }

    fn permite_todos_periodos(&self) -> bool {
        false
    }

    fn titulos(&self, ids: &[i64]) -> HashMap<i64, String> {
        self.projeto.as_ref().and_then(|p| p.titulos(ids).ok()).unwrap_or_default()
    }

    fn origem(&self) -> &'static str {
        "núcleo Rust"
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    /// Teste de fumaça com um projeto real, se existir nesta máquina.
    #[test]
    fn abre_e_executa_projeto_real_se_houver() {
        let Some(c) = ["/home/claude/t/peq/dados.redes", "/home/claude/t/segat.redes"].into_iter().map(Path::new).find(|p| p.is_file()) else { return };
        let mut b = Nucleo::default();
        let info = b.abrir(c).unwrap();
        assert!(!info.periodos.is_empty());
        for e in Estrutura::TODAS {
            let r = b.executar(&Parametros { estrutura: e, periodo: Some(0), ..Default::default() });
            // Algumas estruturas podem não ter dados nesse projeto; quando há, o resultado é coerente.
            if let Ok(r) = r {
                for a in &r.arestas {
                    assert!(a.a < r.nos.len() && a.b < r.nos.len());
                }
                for n in &r.nos {
                    assert!(n.grupo < r.grupos.len());
                }
            }
        }
    }

    #[test]
    fn mapeia_estruturas() {
        let p = Parametros { estrutura: Estrutura::Social, ..Default::default() };
        assert_eq!(parametros_core(&p, Some("a".into())).unidade, core::Unidade::Authors);
        let p = Parametros { estrutura: Estrutura::Fontes, ..Default::default() };
        assert_eq!(parametros_core(&p, None).unidade, core::Unidade::ReferenceSources);
    }
}
