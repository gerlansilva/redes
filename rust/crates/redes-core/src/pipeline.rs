//! Fluxo de análise de um período (porta de `pipeline.py`): conjunto documental,
//! redução por frequência, rede, normalização, agrupamento, medidas de Callon,
//! mapeamento de documentos e índices de desempenho.

use std::collections::{BTreeMap, BTreeSet};

use serde::{Deserialize, Serialize};

use crate::agrupamento::agrupa;
use crate::dataset::{Agregado, Dataset};
use crate::erro::{Erro, Resultado as Res};
use crate::medidas::*;
use crate::parametros::{Mapeador, Matriz, Parametros, Unidade};
use crate::projeto::Projeto;
use crate::pycompat::py_sum;
use crate::rede::{normaliza, rede_acoplamento, rede_acoplamento_agregado, rede_coocorrencia};
use crate::texto::{chave, exibe_termo, termo_legivel};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Grupo {
    /// Posição (1-based) do grupo na lista.
    pub id: usize,
    /// Nós (identificadores) em ordem crescente.
    pub nos: Vec<i64>,
    pub principal: Option<i64>,
    pub rotulo: String,
    /// Rótulo legível (palavras-chave em co-ocorrência saem em forma de frase).
    pub exibicao: String,
    pub centralidade: f64,
    pub densidade: f64,
    pub centralidade_faixa: f64,
    pub densidade_faixa: f64,
    pub quadrante: String,
    /// Documentos por mapeador (nome do mapeador -> ids ordenados).
    pub documentos: BTreeMap<String, Vec<i64>>,
    /// Índices de desempenho por mapeador ("nucleo:h", "nucleo:g", ...).
    pub medidas: BTreeMap<String, f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct No {
    pub id: i64,
    pub rotulo: String,
    /// Nome do item como o projeto guarda, quando existe (itens, não documentos).
    pub frequencia: usize,
    /// Índice (0-based) em `grupos`; `None` = sem grupo.
    pub grupo: Option<usize>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Aresta {
    pub a: i64,
    pub b: i64,
    pub peso: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Ponto {
    pub grupo: usize,
    pub rotulo: String,
    pub centralidade: f64,
    pub densidade: f64,
    pub centralidade_faixa: f64,
    pub densidade_faixa: f64,
    pub quadrante: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Resumo {
    pub periodo: String,
    pub documentos: usize,
    pub itens: usize,
    pub itens_reduzidos: usize,
    pub grupos: usize,
    pub maior_grupo: usize,
    pub grupos_unitarios: usize,
    pub nos_rede: usize,
    pub arestas_rede: usize,
    pub centralidade_media: f64,
    pub densidade_media: f64,
    /// Média por grupo de cada medida ("nucleo:h" etc.).
    pub medidas_medias: BTreeMap<String, f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Resultado {
    pub parametros: Parametros,
    pub grupos: Vec<Grupo>,
    pub nos: Vec<No>,
    pub arestas: Vec<Aresta>,
    /// Pontos do diagrama estratégico de Callon (um por grupo).
    pub estrategico: Vec<Ponto>,
    pub resumo: Resumo,
}

/// Executa a análise do período indicado em `p.periodo` (ou o primeiro).
pub fn executar(projeto: &Projeto, p: &Parametros) -> Res<Resultado> {
    let periodos = projeto.periodos()?;
    let periodo = match &p.periodo {
        Some(nome) => periodos
            .iter()
            .find(|x| &x.nome == nome)
            .ok_or_else(|| Erro::PeriodoInexistente(nome.clone()))?,
        None => periodos.first().ok_or_else(|| Erro::PeriodoInexistente("(nenhum)".into()))?,
    };
    executar_periodo(projeto, periodo.id, &periodo.nome, p)
}

/// Executa um período por nome (em `nomes`) ou todos, quando `nomes` é vazio.
pub fn executar_periodos(projeto: &Projeto, p: &Parametros, nomes: &[String]) -> Res<Vec<Resultado>> {
    let periodos = projeto.periodos()?;
    let mut saida = Vec::new();
    for per in periodos.iter().filter(|x| nomes.is_empty() || nomes.contains(&x.nome)) {
        saida.push(executar_periodo(projeto, per.id, &per.nome, p)?);
    }
    if saida.is_empty() {
        return Err(Erro::PeriodoInexistente(nomes.join(", ")));
    }
    Ok(saida)
}

pub fn executar_periodo(projeto: &Projeto, periodo_id: i64, periodo_nome: &str, p: &Parametros) -> Res<Resultado> {
    p.valida()?;

    let original = projeto.dataset(p.unidade, periodo_id, &p.palavras)?;
    let mut dataset = original.clone();
    let documentos_originais = original.quantidade_documentos();
    let itens_originais = original.quantidade_itens();

    let agregado: Option<Agregado> = match p.matriz {
        Matriz::AggregatedCouplingBasedOnAuthor => Some(projeto.agregado_por_autor(&dataset.lista_documentos())?),
        Matriz::AggregatedCouplingBasedOnJournal => Some(projeto.agregado_por_periodico(&dataset.lista_documentos())?),
        _ => None,
    };

    if !p.ignorar.is_empty() {
        remove_ignorados(&mut dataset, &p.ignorar);
    }
    dataset.filtra_itens_por_frequencia(p.min_freq);

    let mut rede = match (&p.matriz, &agregado) {
        (Matriz::CoOccurrence, _) => rede_coocorrencia(&dataset),
        (Matriz::BasicCoupling, _) => rede_acoplamento(&dataset, p.min_cooc),
        (_, Some(ag)) => rede_acoplamento_agregado(ag, &dataset, p.min_cooc),
        _ => unreachable!(),
    };
    rede.filtra_por_valor(p.min_cooc);

    match (&p.matriz, &agregado) {
        (Matriz::CoOccurrence, _) => normaliza(&mut rede, p.similaridade, |i| dataset.frequencia_item(i)),
        (_, Some(ag)) => normaliza(&mut rede, p.similaridade, |i| ag.frequencia_documento_item(i)),
        _ => normaliza(&mut rede, p.similaridade, |i| dataset.frequencia_documento_item(i)),
    }

    let conjunto = agrupa(p.algoritmo, &rede, p.rede_min, p.rede_max, p.corte)?;

    // No acoplamento os nós são documentos; o rótulo vem do título.
    let titulos = if p.matriz != Matriz::CoOccurrence { projeto.titulos(&rede.nos)? } else { Default::default() };
    let rotulo_de_item = |id: i64| -> String {
        if let Some(t) = titulos.get(&id) {
            return t.clone();
        }
        dataset.itens.get(&id).cloned().unwrap_or_else(|| id.to_string())
    };
    let legivel = p.unidade == Unidade::Words && p.matriz == Matriz::CoOccurrence;

    let mut grupos: Vec<Grupo> = conjunto
        .agrupamentos
        .iter()
        .enumerate()
        .map(|(i, a)| {
            let rotulo = a.principal.map(&rotulo_de_item).unwrap_or_default();
            let exibicao = if legivel { termo_legivel(&rotulo) } else { rotulo.clone() };
            Grupo {
                id: i + 1,
                nos: a.nos.clone(),
                principal: a.principal,
                rotulo,
                exibicao,
                centralidade: 0.0,
                densidade: 0.0,
                centralidade_faixa: 0.0,
                densidade_faixa: 0.0,
                quadrante: String::new(),
                documentos: BTreeMap::new(),
                medidas: BTreeMap::new(),
            }
        })
        .collect();

    for g in &mut grupos {
        g.centralidade = centralidade_callon(&rede, &g.nos);
        g.densidade = densidade_callon(&rede, &g.nos);
    }
    let fc = faixa_normalizada(&grupos.iter().map(|g| g.centralidade).collect::<Vec<_>>());
    let fd = faixa_normalizada(&grupos.iter().map(|g| g.densidade).collect::<Vec<_>>());
    for (i, g) in grupos.iter_mut().enumerate() {
        g.centralidade_faixa = fc[i];
        g.densidade_faixa = fd[i];
        g.quadrante = quadrante(fc[i], fd[i]).to_string();
    }

    // fonte dos mapeadores: documentos de cada item (ou de cada item de alto nível)
    let fonte: BTreeMap<i64, Vec<i64>> = match &agregado {
        Some(ag) => ag.documentos.clone(),
        None => dataset.docs_por_item.clone(),
    };
    for g in &mut grupos {
        for &m in &p.mapeadores {
            let docs: BTreeSet<i64> = match m {
                Mapeador::Nucleo => nucleo(&rede, &fonte, &g.nos),
                Mapeador::Interseccao => interseccao(&fonte, &g.nos),
                Mapeador::Secundarios => secundarios(&fonte, &g.nos),
                Mapeador::Kcore => k_core(&fonte, &g.nos, p.k_core),
                Mapeador::Uniao => uniao(&fonte, &g.nos),
                Mapeador::Acoplamento => acoplamento(&g.nos),
            };
            let ordenados: Vec<i64> = docs.into_iter().collect();
            calcula_indices(&dataset, m.nome(), &ordenados, &mut g.medidas);
            g.documentos.insert(m.nome().to_string(), ordenados);
        }
    }

    let frequencia = |no: i64| -> usize {
        match (&agregado, &p.matriz) {
            (Some(ag), _) => ag.frequencia_documento_item(no),
            (None, Matriz::CoOccurrence) => dataset.frequencia_item(no),
            _ => dataset.frequencia_documento_item(no),
        }
    };
    let rotulo_no = |id: i64| -> String {
        match titulos.get(&id) {
            Some(t) => t.clone(),
            None => exibe_termo(p.unidade, dataset.itens.get(&id).map(|s| s.as_str()).unwrap_or(&id.to_string())),
        }
    };
    let nos: Vec<No> = rede
        .nos
        .iter()
        .map(|&id| No { id, rotulo: rotulo_no(id), frequencia: frequencia(id), grupo: conjunto.grupo_do_no.get(&id).copied() })
        .collect();
    let arestas: Vec<Aresta> = rede.arestas().into_iter().map(|(a, b, peso)| Aresta { a, b, peso }).collect();
    let estrategico: Vec<Ponto> = grupos
        .iter()
        .enumerate()
        .map(|(i, g)| Ponto {
            grupo: i,
            rotulo: g.exibicao.clone(),
            centralidade: g.centralidade,
            densidade: g.densidade,
            centralidade_faixa: g.centralidade_faixa,
            densidade_faixa: g.densidade_faixa,
            quadrante: g.quadrante.clone(),
        })
        .collect();

    let n = grupos.len();
    let media = |f: &dyn Fn(&Grupo) -> f64| if n == 0 { 0.0 } else { py_sum(grupos.iter().map(|g| f(g))) / n as f64 };
    let mut medidas_medias = BTreeMap::new();
    if n > 0 {
        let chaves: BTreeSet<&String> = grupos.iter().flat_map(|g| g.medidas.keys()).collect();
        for c in chaves {
            let vals: Vec<f64> = grupos.iter().filter_map(|g| g.medidas.get(c).copied()).collect();
            medidas_medias.insert(c.clone(), py_sum(vals.iter().copied()) / vals.len() as f64);
        }
    }
    let resumo = Resumo {
        periodo: periodo_nome.to_string(),
        documentos: documentos_originais,
        itens: itens_originais,
        itens_reduzidos: dataset.quantidade_itens(),
        grupos: n,
        maior_grupo: grupos.iter().map(|g| g.nos.len()).max().unwrap_or(0),
        grupos_unitarios: grupos.iter().filter(|g| g.nos.len() == 1).count(),
        nos_rede: rede.quantidade_nos(),
        arestas_rede: rede.quantidade_arestas(),
        centralidade_media: media(&|g| g.centralidade),
        densidade_media: media(&|g| g.densidade),
        medidas_medias,
    };

    Ok(Resultado { parametros: p.clone(), grupos, nos, arestas, estrategico, resumo })
}

fn remove_ignorados(ds: &mut Dataset, ignorar: &[String]) {
    let alvos: BTreeSet<String> = ignorar.iter().map(|n| chave(n)).filter(|c| !c.is_empty()).collect();
    for id in ds.lista_itens() {
        if alvos.contains(&chave(&ds.itens[&id])) {
            ds.remove_item(id);
        }
    }
}

/// Índices de desempenho dos documentos mapeados ("<mapeador>:<medida>").
fn calcula_indices(ds: &Dataset, nome: &str, docs: &[i64], saida: &mut BTreeMap<String, f64>) {
    let cit: Vec<i64> = docs.iter().map(|&d| ds.citacoes(d)).collect();
    let k = |m: &str| format!("{nome}:{m}");
    saida.insert(k("documentos"), docs.len() as f64);
    saida.insert(k("h"), indice_h(&cit) as f64);
    saida.insert(k("g"), indice_g(&cit) as f64);
    saida.insert(k("hg"), indice_hg(&cit));
    saida.insert(k("q2"), indice_q2(&cit));
    saida.insert(k("media"), if cit.is_empty() { 0.0 } else { cit.iter().sum::<i64>() as f64 / cit.len() as f64 });
    saida.insert(k("soma"), cit.iter().sum::<i64>() as f64);
    saida.insert(k("minimo"), cit.iter().copied().min().unwrap_or(0) as f64);
    saida.insert(k("maximo"), cit.iter().copied().max().unwrap_or(0) as f64);
}

/// Linha TSV equivalente a `python3 -m redes analisa` (mesmas colunas).
pub const CABECALHO_TSV: &[&str] = &[
    "periodo", "eixo", "unidade", "matriz", "algoritmo", "similaridade", "mapeador", "medida", "palavras", "min_freq",
    "min_cooc", "rede_min", "rede_max", "corte", "documentos", "itens", "itens_reduzidos", "grupos", "maior_grupo",
    "grupos_unitarios", "nos_rede", "arestas_rede", "centralidade_media", "densidade_media", "valor_medida",
];

pub fn linha_tsv(r: &Resultado) -> Vec<String> {
    let p = &r.parametros;
    let s = &r.resumo;
    let mapeador = p.mapeadores.first().map(|m| m.nome()).unwrap_or("");
    let palavras = if p.palavras.is_empty() { "todas".to_string() } else { p.palavras.join("+") };
    let f = |x: f64| format!("{x:.4}");
    vec![
        s.periodo.clone(),
        String::new(),
        p.unidade.nome().into(),
        p.matriz.nome().into(),
        p.algoritmo.nome().into(),
        p.similaridade.nome().into(),
        mapeador.into(),
        String::new(),
        palavras,
        p.min_freq.to_string(),
        p.min_cooc.to_string(),
        p.rede_min.to_string(),
        p.rede_max.to_string(),
        p.corte.to_string(),
        s.documentos.to_string(),
        s.itens.to_string(),
        s.itens_reduzidos.to_string(),
        s.grupos.to_string(),
        s.maior_grupo.to_string(),
        s.grupos_unitarios.to_string(),
        s.nos_rede.to_string(),
        s.arestas_rede.to_string(),
        f(s.centralidade_media),
        f(s.densidade_media),
        String::new(),
    ]
}
