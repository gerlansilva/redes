//! Adaptador do redes-core: monta [`DadosRelatorio`] a partir de `Resultado`/`Analise`.
//!
//! Lacunas conhecidas do core atual (aparecem como "—" ou ficam de fora): ano médio dos
//! grupos, sigma/rajada dos pontos de virada, linha do tempo, densidade, similitude,
//! duplo mapa, evolução e dendrograma (vêm do redes-analises, como [`ExtraRel`]).

use std::collections::{BTreeMap, BTreeSet};

use redes_core::parametros::{Parametros, Unidade};
use redes_core::pipeline::{executar_analise, Analise, Resultado};
use redes_core::pivos::PontosDeVirada;
use redes_core::projeto::Projeto;

use crate::dados::*;

fn config_de(p: &Parametros, frequencia: usize) -> ConfigRel {
    ConfigRel {
        unidade: p.unidade.nome().into(),
        matriz: p.matriz.nome().into(),
        similaridade: p.similaridade.nome().into(),
        algoritmo: p.algoritmo.nome().into(),
        minimo_frequencia: frequencia,
        minimo_coocorrencia: p.min_cooc,
        tamanho_minimo: p.rede_min,
        tamanho_maximo: p.rede_max,
        corte: p.corte,
        mapeadores: p.mapeadores.iter().map(|m| m.nome().to_string()).collect(),
        k_core: p.k_core,
        palavras: p.palavras.clone(),
        ignorar: p.ignorar.clone(),
        agrupamento_minimo: p.componente_minimo.unwrap_or(if p.unidade == Unidade::Institutions { 3 } else { 1 }),
        ..Default::default()
    }
}

fn qualidade_de(q: &redes_core::qualidade::Qualidade) -> Qualidade {
    Qualidade {
        nivel: q.nivel.clone(),
        n_nos: q.n_nos,
        q: q.q,
        q_louvain: q.q_louvain,
        razao: q.razao,
        silhueta_media: q.silhueta_media,
        pct_agrupados: q.pct_agrupados,
        pct_em_grupos_grandes: Some(q.pct_em_grupos_grandes),
        pct_silhueta_negativa: q.pct_silhueta_negativa,
        avisos: q.avisos.clone(),
    }
}

fn pivos_de(p: &PontosDeVirada) -> Pivos {
    Pivos {
        n_nos: p.n_nos,
        suficiente: p.suficiente,
        itens: p
            .pivos
            .iter()
            .map(|x| PivoItem {
                no: x.no,
                rotulo: x.rotulo.clone(),
                intermediacao: x.intermediacao,
                grupos_vizinhos: x.grupos_vizinhos,
                grupo: x.grupo,
                frequencia: x.frequencia,
                sigma: x.sigma,
            })
            .collect(),
        termos_descritores: p
            .termos_descritores
            .iter()
            .map(|x| TermoDescritor { rotulo: x.rotulo.clone(), proporcao_documentos: x.proporcao_documentos.unwrap_or(0.0) })
            .collect(),
        avisos: p.avisos.clone(),
        nao_calculado: p.nao_calculado.clone(),
    }
}

/// Conversão só do `Resultado` (sem consultar o projeto): estatísticas de documentos com
/// itens ficam no padrão (`documentos`).
pub fn de_redes_core(r: &Resultado) -> PeriodoRel {
    periodo_de(r, None, &BTreeMap::new())
}

fn periodo_de(r: &Resultado, docs_com_itens: Option<usize>, titulos: &BTreeMap<i64, DocumentoRel>) -> PeriodoRel {
    let sil: Vec<Option<f64>> = r.qualidade.as_ref().map(|q| q.silhueta_por_grupo.clone()).unwrap_or_default();
    let grupos: Vec<GrupoRel> = r
        .grupos
        .iter()
        .enumerate()
        .map(|(i, g)| {
            let mut documentos: BTreeMap<String, Vec<DocumentoRel>> = BTreeMap::new();
            if !titulos.is_empty() {
                for (m, ids) in &g.documentos {
                    documentos.insert(m.clone(), ids.iter().filter_map(|d| titulos.get(d).cloned()).collect());
                }
            }
            GrupoRel {
                id: g.id,
                rotulo: g.rotulo.clone(),
                exibicao: g.exibicao.clone(),
                rotulo_novo: g.tema.as_ref().filter(|t| !t.exibicao.is_empty()).map(|t| t.exibicao.clone()),
                indicativo: g.tema.as_ref().map(|t| t.indicativo).unwrap_or(false),
                nos: g.nos.clone(),
                tamanho: g.nos.len(),
                silhueta: sil.get(i).copied().flatten(),
                ano_medio: None,
                documentos_nucleo: g.documentos.get("nucleo").map(|d| d.len()),
                centralidade: g.centralidade,
                densidade: g.densidade,
                centralidade_faixa: g.centralidade_faixa,
                densidade_faixa: g.densidade_faixa,
                medidas: g.medidas.clone(),
                documentos,
            }
        })
        .collect();
    let rede = RedeRel {
        nos: r.nos.iter().map(|n| NoRel { id: n.id, rotulo: n.rotulo.clone(), frequencia: n.frequencia, grupo: n.grupo }).collect(),
        arestas: r.arestas.iter().map(|a| ArestaRel { a: a.a, b: a.b, peso: a.peso }).collect(),
    };
    PeriodoRel {
        nome: r.resumo.periodo.clone(),
        documentos: r.resumo.documentos,
        documentos_com_itens: docs_com_itens,
        itens: r.resumo.itens,
        grafias: None,
        itens_reduzidos: r.resumo.itens_reduzidos,
        rede_nos: r.resumo.nos_rede,
        rede_arestas: r.resumo.arestas_rede,
        itens_agrupados: None,
        itens_sem_agrupamento: None,
        grupos,
        rede: Some(rede),
        qualidade: r.qualidade.as_ref().map(qualidade_de),
        pivos: r.pontos_de_virada.as_ref().map(pivos_de),
        ies: r.ies.as_ref().map(|i| IesInfo {
            unioes: i
                .unioes
                .iter()
                .map(|u| UniaoIes {
                    adotado: u.adotado.clone(),
                    variantes: u.variantes.iter().map(|v| VarianteIes { nome: v.nome.clone(), documentos: v.documentos, motivo: v.motivo.clone() }).collect(),
                })
                .collect(),
            componentes_pequenos: i.componentes_pequenos.len(),
            componente_minimo: i.componente_minimo,
            isolados: i.isolados,
        }),
        filtro_agrupamento: r.filtro_agrupamento.as_ref().map(|f| FiltroAgrupamento {
            minimo: f.minimo,
            grupos_antes: f.grupos_antes,
            grupos_depois: f.grupos_depois,
            nos_sem_agrupamento: f.nos_sem_agrupamento,
            isolados: f.isolados,
        }),
        ..Default::default()
    }
}

/// Período a partir de uma `Analise` (traz documentos com itens e, se `estendido`, os títulos).
pub fn periodo_de_analise(a: &Analise, projeto: Option<&Projeto>, estendido: bool) -> PeriodoRel {
    let com_itens = a.original.lista_documentos().into_iter().filter(|d| !a.original.itens_do_documento(*d).is_empty()).count();
    let mut titulos: BTreeMap<i64, DocumentoRel> = BTreeMap::new();
    if estendido {
        if let Some(pr) = projeto {
            let ids: BTreeSet<i64> = a.resultado.grupos.iter().flat_map(|g| g.documentos.values().flatten().copied()).collect();
            let ids: Vec<i64> = ids.into_iter().collect();
            if let Ok(t) = pr.titulos(&ids) {
                for (id, titulo) in t {
                    titulos.insert(id, DocumentoRel { titulo, ..Default::default() });
                }
            }
        }
    }
    periodo_de(&a.resultado, Some(com_itens), &titulos)
}

/// Uma análise (todos os períodos) como seção do relatório. `None` quando a base não dá agrupamento.
pub fn secao_do_projeto(
    projeto: &Projeto,
    chave: &str,
    rotulo: &str,
    descricao: &str,
    base: &Parametros,
    estendido: bool,
    frequencia_fixa: Option<usize>,
) -> anyhow::Result<Option<SecaoAnalise>> {
    let periodos = projeto.periodos()?;
    let candidatas: Vec<usize> = match frequencia_fixa {
        Some(f) => vec![f],
        None => vec![3, 2, 1],
    };
    let mut melhor: Option<(usize, usize, Vec<Analise>)> = None;
    for f in candidatas {
        let mut p = base.clone();
        p.min_freq = f;
        p.extras.pivos = true;
        p.extras.qualidade = true;
        p.extras.rotulos = true;
        let mut analises = Vec::new();
        for per in &periodos {
            analises.push(executar_analise(projeto, per.id, &per.nome, &p)?);
        }
        let gr: Vec<usize> = analises.iter().map(|a| a.resultado.grupos.len()).collect();
        let soma: usize = gr.iter().sum();
        if soma == 0 {
            continue;
        }
        let com_itens: Vec<usize> =
            gr.iter().zip(&analises).filter(|(_, a)| a.original.quantidade_itens() > 0).map(|(n, _)| *n).collect();
        if !com_itens.is_empty() && com_itens.iter().all(|n| *n >= 1) && soma >= 3 {
            melhor = Some((soma, f, analises));
            break;
        }
        if melhor.as_ref().map(|m| soma > m.0).unwrap_or(true) {
            melhor = Some((soma, f, analises));
        }
    }
    let Some((_, f, analises)) = melhor else { return Ok(None) };
    let mut p = base.clone();
    p.min_freq = f;

    let mut docs: BTreeSet<i64> = BTreeSet::new();
    let mut docs_itens: BTreeSet<i64> = BTreeSet::new();
    let mut itens: BTreeSet<i64> = BTreeSet::new();
    for a in &analises {
        for d in a.original.lista_documentos() {
            docs.insert(d);
            if !a.original.itens_do_documento(d).is_empty() {
                docs_itens.insert(d);
            }
        }
        itens.extend(a.original.lista_itens());
    }
    Ok(Some(SecaoAnalise {
        chave: chave.into(),
        rotulo: rotulo.into(),
        descricao: descricao.into(),
        config: config_de(&p, f),
        frequencia: Some(f),
        medida_temporal: None,
        periodos: analises.iter().map(|a| periodo_de_analise(a, Some(projeto), estendido)).collect(),
        total: Some(TotalRel {
            documentos: Some(docs.len()),
            documentos_com_itens: Some(docs_itens.len()),
            itens: Some(itens.len()),
            ..Default::default()
        }),
        extras: Vec::new(),
    }))
}

/// As análises do relatório completo (como `api.ANALISES_COMPLETO`), nesta ordem.
pub fn analises_completo() -> Vec<(&'static str, &'static str, &'static str, Parametros)> {
    use redes_core::parametros::{Mapeador, Matriz};
    let mk = |u: Unidade, m: Matriz, map: Option<Mapeador>| {
        let mut p = Parametros { unidade: u, matriz: m, ..Default::default() };
        if let Some(x) = map {
            p.mapeadores = vec![x];
        }
        p
    };
    vec![
        ("conceitual", "Estrutura conceitual (palavras-chave)", "Palavras-chave em co-ocorrência: os temas que estruturam o campo.", mk(Unidade::Words, Matriz::CoOccurrence, None)),
        ("autores", "Colaboração entre autores", "Quem publica com quem, pela co-ocorrência de autores nos documentos.", mk(Unidade::Authors, Matriz::CoOccurrence, None)),
        ("paises", "Colaboração entre países", "Cooperação internacional: países que assinam os mesmos documentos.", mk(Unidade::Countries, Matriz::CoOccurrence, None)),
        (
            "instituicoes",
            "Colaboração entre instituições (IES)",
            "Instituições que assinam os mesmos documentos, com os nomes unidos quando a variante é inequívoca; componentes com menos de 3 instituições ficam sem agrupamento.",
            mk(Unidade::Institutions, Matriz::CoOccurrence, None),
        ),
        ("referencias", "Cocitação de referências", "Obras citadas em conjunto pelos documentos do corpus.", mk(Unidade::References, Matriz::CoOccurrence, None)),
        ("citados", "Cocitação de autores", "Autores citados em conjunto, formando a base intelectual do campo.", mk(Unidade::AuthorsReference, Matriz::CoOccurrence, None)),
        ("frentes", "Frentes de pesquisa (acoplamento bibliográfico)", "Documentos ligados por referências compartilhadas.", mk(Unidade::References, Matriz::BasicCoupling, Some(Mapeador::Acoplamento))),
        ("veiculos", "Periódicos citados", "Periódicos citados em conjunto nas referências do corpus.", mk(Unidade::ReferenceSources, Matriz::CoOccurrence, None)),
    ]
}

/// Dados do relatório completo de um projeto `.redes`, só com o que o redes-core calcula.
/// `nome_arquivo` aparece na capa.
pub fn dados_do_projeto(projeto: &Projeto, nome_arquivo: &str, estendido: bool, frequencia_fixa: Option<usize>) -> anyhow::Result<DadosRelatorio> {
    let periodos = projeto.periodos()?;
    let mut dados = DadosRelatorio {
        projeto: InfoProjeto {
            nome: nome_arquivo.into(),
            documentos: projeto.total_documentos()?,
            periodos: periodos.iter().map(|p| p.nome.clone()).collect(),
            data: None,
        },
        medida_temporal: "EquivalenceIndex".into(),
        estendido,
        ..Default::default()
    };
    for (chave, rotulo, descricao, p) in analises_completo() {
        match secao_do_projeto(projeto, chave, rotulo, descricao, &p, estendido, frequencia_fixa) {
            Ok(Some(s)) => dados.secoes.push(s),
            Ok(None) => dados.ignoradas.push(Ignorada { rotulo: rotulo.into(), motivo: "a base não tem dados suficientes para esta análise".into() }),
            Err(e) => dados.ignoradas.push(Ignorada { rotulo: rotulo.into(), motivo: e.to_string() }),
        }
    }
    Ok(dados)
}
