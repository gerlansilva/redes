//! Duplo mapa simplificado (Chen e Leydesdorff, 2014): de que áreas para que áreas.
//! À esquerda, as revistas que publicam o corpus (as N que mais citam); à direita, as revistas
//! citadas por elas (as M mais citadas por esse conjunto). Porta `redes/duplo_mapa.py` e
//! `redes/viz/duplo_mapa.py`.

use std::collections::{BTreeMap, HashMap, HashSet};

use indexmap::IndexMap;
use rusqlite::Connection;
use serde::Serialize;

use crate::areas::{Regras, COR_NAO_CLASSIFICADO, NAO_CLASSIFICADO, PALETA_EXTRA};
use crate::util::{esc_limpo, hash8, largura, limpa, textwrap, FONTE_INTER, TINTA, TINTA_FRACA};
use redes_core::texto::termo_legivel;

pub const MAX_ESQ: usize = 10;
pub const MAX_DIR: usize = 16;
pub const LIMITE_ESQ: (usize, usize) = (3, 30);
pub const LIMITE_DIR: (usize, usize) = (5, 40);
pub const EXTRAS_NAO_CLASSIFICADAS: usize = 15;
pub const SEM_FONTE: &str = "Sem fonte";
pub const AVISO_APROXIMADA: &str = "A área de cada revista é inferida por palavras do nome da revista; é uma classificação aproximada, que pode errar ou deixar revistas sem área. Confira a tabela revista → área.";
pub const COLUNAS: [&str; 2] = ["Revistas que publicam o corpus", "Revistas citadas"];
pub const TITULO: &str = "Duplo mapa — áreas das revistas que publicam e das revistas citadas (corpus completo)";
pub const NOTA: &str = "Como ler: à esquerda estão as revistas que publicam os documentos do corpus completo (as que mais citam) e à direita as revistas que elas citam (as mais citadas por esse conjunto), agrupadas e coloridas por área. Cada faixa liga uma área da esquerda a uma área da direita, e a largura é o número de citações (referências) entre revistas desenhadas; uma faixa larga mostra de onde o corpus tira o seu conhecimento. A área de cada revista é inferida por palavras do NOME da revista, não por uma base de categorias: a classificação é aproximada, pode errar e deixa revistas em \"Não classificado\". A tabela revista → área, com o termo que decidiu cada caso, serve para conferir; referências sem periódico identificado não entram.";

/// Contagens lidas do projeto.
#[derive(Clone, Debug, Default)]
pub struct Citacoes {
    /// `(revista do documento, revista citada) -> n`
    pub citacoes: BTreeMap<(String, String), i64>,
    pub documentos: i64,
    pub documentos_com_revista: i64,
    pub referencias_sem_fonte: i64,
}

pub fn le_citacoes(c: &Connection) -> Citacoes {
    let base = "FROM Document d JOIN Journal j ON j.idJournal = d.Journal_idJournal \
                JOIN Document_Reference dr ON dr.Document_idDocument = d.idDocument \
                JOIN Reference r ON r.idReference = dr.Reference_idReference \
                JOIN ReferenceSource rs ON rs.idReferenceSource = r.ReferenceSource_idReferenceSource \
                LEFT JOIN ReferenceSourceGroup g ON g.idReferenceSourceGroup = rs.ReferenceSourceGroup_idReferencesourceGroup \
                WHERE COALESCE(j.source, '') <> '' ";
    let oculta = "(COALESCE(g.stopGroup, 0) <> 0 OR rs.source = ? OR COALESCE(rs.source, '') = '')";
    let tenta = || -> Result<Citacoes, rusqlite::Error> {
        let mut r = Citacoes::default();
        let sql = format!("SELECT j.source, COALESCE(g.groupName, rs.source), COUNT(*) {base}AND NOT {oculta} GROUP BY 1, 2");
        let mut st = c.prepare(&sql)?;
        let linhas = st.query_map([SEM_FONTE], |l| {
            Ok((l.get::<_, Option<String>>(0)?, l.get::<_, Option<String>>(1)?, l.get::<_, i64>(2)?))
        })?;
        for l in linhas {
            let (a, b, n) = l?;
            if let (Some(a), Some(b)) = (a, b) {
                if !a.is_empty() && !b.is_empty() {
                    *r.citacoes.entry((a, b)).or_insert(0) += n;
                }
            }
        }
        r.referencias_sem_fonte = c.query_row(&format!("SELECT COUNT(*) {base}AND {oculta}"), [SEM_FONTE], |l| l.get(0))?;
        r.documentos = c.query_row("SELECT COUNT(*) FROM Document", [], |l| l.get(0))?;
        r.documentos_com_revista = c.query_row(
            "SELECT COUNT(*) FROM Document d JOIN Journal j ON j.idJournal = d.Journal_idJournal WHERE COALESCE(j.source, '') <> ''",
            [],
            |l| l.get(0),
        )?;
        Ok(r)
    };
    tenta().unwrap_or_default()
}

/// Há ao menos um documento com revista que cita alguma referência com periódico?
pub fn aplicavel(c: &Connection) -> bool {
    c.query_row(
        "SELECT 1 FROM Document d JOIN Journal j ON j.idJournal = d.Journal_idJournal \
         JOIN Document_Reference dr ON dr.Document_idDocument = d.idDocument \
         JOIN Reference r ON r.idReference = dr.Reference_idReference \
         JOIN ReferenceSource rs ON rs.idReferenceSource = r.ReferenceSource_idReferenceSource \
         WHERE COALESCE(j.source, '') <> '' AND COALESCE(rs.source, '') NOT IN ('', ?) LIMIT 1",
        [SEM_FONTE],
        |_| Ok(()),
    )
    .is_ok()
}

#[derive(Clone, Debug, Serialize)]
pub struct Item {
    pub nome: String,
    pub original: String,
    pub area: String,
    pub termo: String,
    pub valor: i64,
    pub no_desenho: Option<i64>,
    pub total: Option<i64>,
    #[serde(skip)]
    pub y_centro: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct AreaInfo {
    pub nome: String,
    pub cor: String,
    pub esquerda: usize,
    pub direita: usize,
    pub saida: i64,
    pub entrada: i64,
}

#[derive(Clone, Debug, Serialize)]
pub struct Fluxo {
    pub origem: String,
    pub destino: String,
    pub valor: i64,
    pub pct: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct LinhaTabela {
    pub revista: String,
    pub area: String,
    pub termo: String,
    pub publica: i64,
    pub citada: i64,
    pub no_desenho: bool,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct Cobertura {
    pub referencias: i64,
    pub desenhadas: i64,
    pub sem_fonte: i64,
    pub revistas: usize,
    pub revistas_nao_classificadas: usize,
    pub pct_revistas_nao_classificadas: f64,
    pub pct_citadas_nao_classificadas: f64,
    pub pct_citantes_nao_classificadas: f64,
    pub pct_desenho_nao_classificadas: f64,
    pub documentos: i64,
    pub documentos_com_revista: i64,
}

#[derive(Clone, Debug, Serialize)]
pub struct LigacaoRevista {
    pub origem: String,
    pub destino: String,
    pub valor: i64,
}

#[derive(Clone, Debug, Serialize)]
pub struct DuploMapa {
    pub aplicavel: bool,
    pub aviso: String,
    pub colunas: Vec<String>,
    pub esquerda: Vec<Item>,
    pub direita: Vec<Item>,
    pub areas: Vec<AreaInfo>,
    pub fluxos: Vec<Fluxo>,
    pub tabela: Vec<LinhaTabela>,
    pub cobertura: Cobertura,
    pub avisos: Vec<String>,
    pub cores: IndexMap<String, String>,
    pub max_esq: usize,
    pub max_dir: usize,
    pub total_esquerda: usize,
    pub total_direita: usize,
    pub ligacoes: Vec<LigacaoRevista>,
}

fn vazio(aviso: &str, regras: &Regras) -> DuploMapa {
    DuploMapa {
        aplicavel: false,
        aviso: aviso.into(),
        colunas: COLUNAS.iter().map(|s| s.to_string()).collect(),
        esquerda: vec![],
        direita: vec![],
        areas: vec![],
        fluxos: vec![],
        tabela: vec![],
        cobertura: Cobertura::default(),
        avisos: vec![],
        cores: regras.cores(),
        max_esq: 0,
        max_dir: 0,
        total_esquerda: 0,
        total_direita: 0,
        ligacoes: vec![],
    }
}

fn mais_citadas(c: &HashMap<String, i64>, n: usize) -> Vec<String> {
    let mut v: Vec<(&String, &i64)> = c.iter().collect();
    v.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
    v.into_iter().take(n).map(|(k, _)| k.clone()).collect()
}

/// Dados do duplo mapa a partir de `le_citacoes`.
pub fn calcula(ctx: &Citacoes, max_esq: usize, max_dir: usize, regras: &Regras) -> DuploMapa {
    if ctx.documentos > 0 && ctx.documentos_com_revista == 0 {
        return vazio("A base não traz o periódico dos documentos; o duplo mapa precisa saber em que revista cada documento foi publicado.", regras);
    }
    if ctx.citacoes.is_empty() {
        return vazio("A base não traz referências com periódico identificado; o duplo mapa precisa do periódico de cada referência citada.", regras);
    }
    let mut emitidas: HashMap<String, i64> = HashMap::new();
    let mut recebidas: HashMap<String, i64> = HashMap::new();
    for ((citante, citada), n) in &ctx.citacoes {
        *emitidas.entry(citante.clone()).or_insert(0) += n;
        *recebidas.entry(citada.clone()).or_insert(0) += n;
    }
    let mut cache: HashMap<String, (String, String)> = HashMap::new();
    let mut classe = |nome: &str| -> (String, String) {
        cache.entry(nome.to_string()).or_insert_with(|| regras.classifica(nome)).clone()
    };
    let esq = mais_citadas(&emitidas, max_esq);
    let conj_esq: HashSet<&String> = esq.iter().collect();
    let mut das_esq: HashMap<String, i64> = HashMap::new();
    for ((citante, citada), n) in &ctx.citacoes {
        if conj_esq.contains(citante) {
            *das_esq.entry(citada.clone()).or_insert(0) += n;
        }
    }
    let dir = mais_citadas(&das_esq, max_dir);
    let conj_dir: HashSet<&String> = dir.iter().collect();
    let mut pares: BTreeMap<(String, String), i64> = BTreeMap::new();
    let mut fluxo_area: BTreeMap<(String, String), i64> = BTreeMap::new();
    let mut saida_revista: HashMap<String, i64> = HashMap::new();
    for ((citante, citada), n) in &ctx.citacoes {
        if conj_esq.contains(citante) && conj_dir.contains(citada) {
            *fluxo_area.entry((classe(citante).0, classe(citada).0)).or_insert(0) += n;
            *saida_revista.entry(citante.clone()).or_insert(0) += n;
            *pares.entry((citante.clone(), citada.clone())).or_insert(0) += n;
        }
    }
    let desenhadas: i64 = fluxo_area.values().sum();
    if desenhadas == 0 {
        return vazio("Nenhuma das revistas que publicam o corpus cita as revistas mais citadas.", regras);
    }
    let mut ordem_areas: Vec<String> = regras.areas.iter().map(|a| a.nome.clone()).collect();
    ordem_areas.push(NAO_CLASSIFICADO.into());
    let posicao = |a: &str| ordem_areas.iter().position(|x| x == a).unwrap_or(99);
    let mut item = |nome: &str, valor: i64, no_desenho: Option<i64>, total: Option<i64>| -> Item {
        let (area, termo) = classe(nome);
        Item { nome: termo_legivel(nome), original: nome.to_string(), area, termo, valor, no_desenho, total, y_centro: 0.0 }
    };
    let mut esquerda: Vec<Item> =
        esq.iter().map(|r| item(r, emitidas[r], Some(saida_revista.get(r).copied().unwrap_or(0)), None)).collect();
    let mut direita: Vec<Item> = dir.iter().map(|r| item(r, das_esq[r], None, Some(recebidas[r]))).collect();
    let mut por_saida: HashMap<String, i64> = HashMap::new();
    let mut por_entrada: HashMap<String, i64> = HashMap::new();
    for ((a, b), n) in &fluxo_area {
        *por_saida.entry(a.clone()).or_insert(0) += n;
        *por_entrada.entry(b.clone()).or_insert(0) += n;
    }
    let g = |m: &HashMap<String, i64>, a: &str| m.get(a).copied().unwrap_or(0);
    let mut nomes_areas: Vec<String> = esquerda.iter().chain(direita.iter()).map(|i| i.area.clone()).collect();
    nomes_areas.sort();
    nomes_areas.dedup();
    nomes_areas.sort_by(|a, b| {
        let ka = (a == NAO_CLASSIFICADO, -(g(&por_saida, a) + g(&por_entrada, a)), posicao(a), a.clone());
        let kb = (b == NAO_CLASSIFICADO, -(g(&por_saida, b) + g(&por_entrada, b)), posicao(b), b.clone());
        ka.cmp(&kb)
    });
    let mut cor_de = regras.cores();
    let mut extras_cor = PALETA_EXTRA.iter();
    for a in &nomes_areas {
        if !cor_de.contains_key(a) {
            cor_de.insert(a.clone(), extras_cor.next().map(|s| s.to_string()).unwrap_or_else(|| COR_NAO_CLASSIFICADO.into()));
        }
    }
    let idx_area = |a: &str| nomes_areas.iter().position(|x| x == a).unwrap();
    let ordena = |v: &mut Vec<Item>| {
        v.sort_by(|a, b| idx_area(&a.area).cmp(&idx_area(&b.area)).then(b.valor.cmp(&a.valor)).then(a.nome.cmp(&b.nome)));
    };
    ordena(&mut esquerda);
    ordena(&mut direita);
    let lista_areas: Vec<AreaInfo> = nomes_areas
        .iter()
        .map(|a| AreaInfo {
            nome: a.clone(),
            cor: cor_de[a].clone(),
            esquerda: esquerda.iter().filter(|i| &i.area == a).count(),
            direita: direita.iter().filter(|i| &i.area == a).count(),
            saida: g(&por_saida, a),
            entrada: g(&por_entrada, a),
        })
        .collect();
    let mut fl: Vec<(&(String, String), &i64)> = fluxo_area.iter().collect();
    fl.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
    let fluxos: Vec<Fluxo> = fl
        .into_iter()
        .map(|((a, b), n)| Fluxo { origem: a.clone(), destino: b.clone(), valor: *n, pct: *n as f64 / desenhadas as f64 })
        .collect();

    // tabela auditável
    let mut linhas: IndexMap<String, LinhaTabela> = IndexMap::new();
    for i in &esquerda {
        linhas.insert(
            i.original.clone(),
            LinhaTabela {
                revista: i.nome.clone(),
                area: i.area.clone(),
                termo: i.termo.clone(),
                publica: i.valor,
                citada: recebidas.get(&i.original).copied().unwrap_or(0),
                no_desenho: true,
            },
        );
    }
    for i in &direita {
        let l = linhas.entry(i.original.clone()).or_insert_with(|| LinhaTabela {
            revista: i.nome.clone(),
            area: i.area.clone(),
            termo: i.termo.clone(),
            publica: 0,
            citada: 0,
            no_desenho: true,
        });
        l.publica = emitidas.get(&i.original).copied().unwrap_or(0);
        l.citada = recebidas[&i.original];
    }
    let mut todas: HashMap<String, i64> = HashMap::new();
    for (n, v) in emitidas.iter().chain(recebidas.iter()) {
        *todas.entry(n.clone()).or_insert(0) += v;
    }
    let mut ordem_todas: Vec<(&String, &i64)> = todas.iter().collect();
    ordem_todas.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
    let mut extras = 0;
    for (nome, _) in ordem_todas {
        if extras >= EXTRAS_NAO_CLASSIFICADAS {
            break;
        }
        if linhas.contains_key(nome) || classe(nome).0 != NAO_CLASSIFICADO {
            continue;
        }
        linhas.insert(
            nome.clone(),
            LinhaTabela {
                revista: termo_legivel(nome),
                area: NAO_CLASSIFICADO.into(),
                termo: String::new(),
                publica: emitidas.get(nome).copied().unwrap_or(0),
                citada: recebidas.get(nome).copied().unwrap_or(0),
                no_desenho: false,
            },
        );
        extras += 1;
    }
    let mut tabela: Vec<LinhaTabela> = linhas.into_values().collect();
    tabela.sort_by(|a, b| {
        (!a.no_desenho, posicao(&a.area), -(a.publica + a.citada), a.revista.clone())
            .cmp(&(!b.no_desenho, posicao(&b.area), -(b.publica + b.citada), b.revista.clone()))
    });
    let total_refs: i64 = ctx.citacoes.values().sum();
    let refs_nc_citadas: i64 = recebidas.iter().filter(|(r, _)| classe(r).0 == NAO_CLASSIFICADO).map(|(_, n)| n).sum();
    let refs_nc_citantes: i64 = emitidas.iter().filter(|(r, _)| classe(r).0 == NAO_CLASSIFICADO).map(|(_, n)| n).sum();
    let revistas: HashSet<&String> = emitidas.keys().chain(recebidas.keys()).collect();
    let n_nc = revistas.iter().filter(|r| classe(r).0 == NAO_CLASSIFICADO).count();
    let desenho_nc: i64 = esquerda.iter().chain(direita.iter()).filter(|i| i.area == NAO_CLASSIFICADO).map(|i| i.valor).sum();
    let desenho_total: i64 = esquerda.iter().chain(direita.iter()).map(|i| i.valor).sum();
    let cobertura = Cobertura {
        referencias: total_refs,
        desenhadas,
        sem_fonte: ctx.referencias_sem_fonte,
        revistas: revistas.len(),
        revistas_nao_classificadas: n_nc,
        pct_revistas_nao_classificadas: n_nc as f64 / revistas.len() as f64,
        pct_citadas_nao_classificadas: refs_nc_citadas as f64 / total_refs as f64,
        pct_citantes_nao_classificadas: refs_nc_citantes as f64 / total_refs as f64,
        pct_desenho_nao_classificadas: desenho_nc as f64 / desenho_total.max(1) as f64,
        documentos: ctx.documentos,
        documentos_com_revista: ctx.documentos_com_revista,
    };
    let mut avisos = vec![AVISO_APROXIMADA.to_string()];
    if emitidas.len() == 1 {
        avisos.push("O corpus tem uma única revista de publicação; o lado esquerdo mostra apenas ela.".into());
    }
    let total_esquerda = emitidas.len();
    let total_direita = recebidas.len();
    DuploMapa {
        aplicavel: true,
        aviso: String::new(),
        colunas: COLUNAS.iter().map(|s| s.to_string()).collect(),
        esquerda,
        direita,
        areas: lista_areas,
        fluxos,
        tabela,
        cobertura,
        avisos,
        cores: cor_de,
        max_esq,
        max_dir,
        total_esquerda,
        total_direita,
        ligacoes: pares.into_iter().map(|((o, d), n)| LigacaoRevista { origem: o, destino: d, valor: n }).collect(),
    }
}

pub fn calcula_do_banco(c: &Connection, max_esq: usize, max_dir: usize, regras: &Regras) -> DuploMapa {
    calcula(&le_citacoes(c), max_esq, max_dir, regras)
}

/// Fração como porcentagem com vírgula (`0,184` → `18%`; abaixo de 10%, uma casa).
pub fn porcentagem(valor: f64) -> String {
    let p = valor * 100.0;
    let texto = if p > 0.0 && p < 10.0 { format!("{:.1}", p) } else { format!("{:.0}", p) };
    texto.replace('.', ",") + "%"
}

// ====================================================================== SVG

pub const LARGURA: i64 = 1100;
const MARGEM: f64 = 16.0;
const TOPO_TITULO: f64 = 46.0;
const TOPO_CABECALHO: f64 = 30.0;
const LARGURA_BARRA: f64 = 14.0;
const LINHA: f64 = 18.0;
const CABECA_AREA: f64 = 20.0;
const ENTRE_BLOCOS: f64 = 12.0;
const ALTURA_FLUXO: f64 = 360.0;
const ESCALA_MAX: f64 = 40.0;
const ROTULO_MAX: f64 = 235.0;
const QUEBRA_RODAPE: usize = 160;

fn l12(t: &str) -> f64 {
    largura(t, 12.0, false)
}
fn l12b(t: &str) -> f64 {
    largura(t, 12.0, true)
}

fn cabe(texto: &str, px: f64, tamanho: f64, negrito: bool) -> String {
    let texto = limpa(texto);
    if largura(&texto, tamanho, negrito) <= px {
        return texto;
    }
    let mut cs: Vec<char> = texto.chars().collect();
    while cs.len() > 1 {
        let s: String = cs.iter().collect();
        if largura(&format!("{}…", s.trim_end()), tamanho, negrito) <= px {
            break;
        }
        cs.pop();
    }
    let s: String = cs.iter().collect();
    format!("{}…", s.trim_end())
}

fn citacoes(n: i64) -> String {
    format!("{n} citaç{}", if n == 1 { "ão" } else { "ões" })
}

fn revistas(n: usize) -> String {
    format!("{n} revista{}", if n == 1 { "" } else { "s" })
}

fn permutacoes(n: usize) -> Vec<Vec<usize>> {
    fn rec(atual: &mut Vec<usize>, usado: &mut Vec<bool>, n: usize, saida: &mut Vec<Vec<usize>>) {
        if atual.len() == n {
            saida.push(atual.clone());
            return;
        }
        for i in 0..n {
            if !usado[i] {
                usado[i] = true;
                atual.push(i);
                rec(atual, usado, n, saida);
                atual.pop();
                usado[i] = false;
            }
        }
    }
    let mut s = vec![];
    rec(&mut vec![], &mut vec![false; n], n, &mut s);
    s
}

/// Ordem das áreas da direita com menos cruzamentos de faixas (exaustivo até 6 áreas).
fn ordem_direita(esq: &[String], dir: &[String], fluxo: &BTreeMap<(String, String), i64>) -> Vec<String> {
    let pos_esq: HashMap<&String, usize> = esq.iter().enumerate().map(|(i, a)| (a, i)).collect();
    let custo = |ordem: &[&String]| -> i64 {
        let pos: HashMap<&String, usize> = ordem.iter().enumerate().map(|(i, a)| (*a, i)).collect();
        let itens: Vec<(i64, i64, i64)> = fluxo
            .iter()
            .filter(|((a, b), _)| pos_esq.contains_key(a) && pos.contains_key(b))
            .map(|((a, b), n)| (pos_esq[a] as i64, pos[b] as i64, *n))
            .collect();
        let mut total = 0;
        for (i, (a1, b1, n1)) in itens.iter().enumerate() {
            for (a2, b2, n2) in &itens[i + 1..] {
                if (a1 - a2) * (b1 - b2) < 0 {
                    total += n1 * n2;
                }
            }
        }
        total
    };
    if dir.len() <= 6 {
        let mut melhor: Option<(i64, Vec<usize>)> = None;
        for p in permutacoes(dir.len()) {
            let ordem: Vec<&String> = p.iter().map(|&i| &dir[i]).collect();
            let c = custo(&ordem);
            if melhor.as_ref().map_or(true, |(mc, _)| c < *mc) {
                melhor = Some((c, p));
            }
        }
        return melhor.map(|(_, p)| p.into_iter().map(|i| dir[i].clone()).collect()).unwrap_or_default();
    }
    let baricentro = |a: &String| -> f64 {
        let pesos: Vec<(usize, i64)> =
            fluxo.iter().filter(|((o, d), _)| d == a && pos_esq.contains_key(o)).map(|((o, _), n)| (pos_esq[o], *n)).collect();
        let soma: i64 = pesos.iter().map(|(_, n)| n).sum();
        if soma > 0 {
            pesos.iter().map(|(p, n)| *p as f64 * *n as f64).sum::<f64>() / soma as f64
        } else {
            dir.iter().position(|x| x == a).unwrap() as f64
        }
    };
    let mut v: Vec<(f64, usize, String)> =
        dir.iter().enumerate().map(|(i, a)| (baricentro(a), i, a.clone())).collect();
    v.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap().then(a.1.cmp(&b.1)));
    v.into_iter().map(|t| t.2).collect()
}

#[derive(Clone, Debug)]
pub struct Bloco {
    pub area: String,
    pub membros: Vec<Item>,
    pub y: f64,
    pub h: f64,
}

#[derive(Clone, Debug)]
pub struct Faixa {
    pub origem: String,
    pub destino: String,
    pub valor: i64,
    pub espessura: f64,
    pub y0: f64,
    pub y1: f64,
}

#[derive(Clone, Debug)]
pub struct Layout {
    pub blocos_e: Vec<Bloco>,
    pub blocos_d: Vec<Bloco>,
    pub x_barra_e: f64,
    pub x_barra_d: f64,
    pub altura: f64,
    pub faixas: Vec<Faixa>,
    pub escala: f64,
    pub larg_e: f64,
    pub larg_d: f64,
}

pub fn layout(dados: &DuploMapa, largura_svg: i64, topo: f64) -> Layout {
    let fluxos: BTreeMap<(String, String), i64> =
        dados.fluxos.iter().map(|f| ((f.origem.clone(), f.destino.clone()), f.valor)).collect();
    let ordem_esq: Vec<String> =
        dados.areas.iter().filter(|a| dados.esquerda.iter().any(|i| i.area == a.nome)).map(|a| a.nome.clone()).collect();
    let ordem_dir0: Vec<String> =
        dados.areas.iter().filter(|a| dados.direita.iter().any(|i| i.area == a.nome)).map(|a| a.nome.clone()).collect();
    let ordem_dir = ordem_direita(&ordem_esq, &ordem_dir0, &fluxos);
    let total = {
        let t: i64 = fluxos.values().sum();
        if t == 0 {
            1
        } else {
            t
        }
    };
    let escala = ESCALA_MAX.min(ALTURA_FLUXO / total as f64);
    let saida: HashMap<&String, i64> =
        ordem_esq.iter().map(|a| (a, fluxos.iter().filter(|((o, _), _)| o == a).map(|(_, n)| *n).sum())).collect();
    let entrada: HashMap<&String, i64> =
        ordem_dir.iter().map(|a| (a, fluxos.iter().filter(|((_, d), _)| d == a).map(|(_, n)| *n).sum())).collect();
    let cab: Vec<String> = dados.colunas.iter().map(|c| limpa(c)).collect();
    let maior = |itens: &[Item], ordem: &[String]| -> f64 {
        itens
            .iter()
            .map(|i| l12(&i.nome))
            .chain(ordem.iter().map(|a| l12b(a)))
            .fold(0.0, f64::max)
    };
    let larg_e = ROTULO_MAX.min(maior(&dados.esquerda, &ordem_esq).max(l12b(&cab[0])));
    let larg_d = ROTULO_MAX.min(maior(&dados.direita, &ordem_dir).max(l12b(&cab[1])));
    let x_barra_e = MARGEM + larg_e + 14.0;
    let x_barra_d = largura_svg as f64 - MARGEM - larg_d - 14.0 - LARGURA_BARRA;

    let coluna = |ordem: &[String], itens: &[Item], peso: &HashMap<&String, i64>| -> (Vec<Bloco>, f64) {
        let mut blocos = vec![];
        let mut y = 0.0;
        for area in ordem {
            let membros: Vec<Item> = itens.iter().filter(|i| &i.area == area).cloned().collect();
            let corpo = (membros.len() as f64 * LINHA).max(peso[area] as f64 * escala).max(LINHA);
            blocos.push(Bloco { area: area.clone(), membros, y: y + CABECA_AREA, h: corpo });
            y += CABECA_AREA + corpo + ENTRE_BLOCOS;
        }
        (blocos, (y - ENTRE_BLOCOS).max(0.0))
    };
    let (mut blocos_e, altura_e) = coluna(&ordem_esq, &dados.esquerda, &saida);
    let (mut blocos_d, altura_d) = coluna(&ordem_dir, &dados.direita, &entrada);
    let altura = altura_e.max(altura_d);
    for (blocos, h) in [(&mut blocos_e, altura_e), (&mut blocos_d, altura_d)] {
        let desl = topo + (altura - h) / 2.0;
        for b in blocos.iter_mut() {
            b.y += desl;
            let n = b.membros.len().max(1) as f64;
            let (by, bh) = (b.y, b.h);
            for (k, m) in b.membros.iter_mut().enumerate() {
                m.y_centro = by + (k as f64 + 0.5) * bh / n;
            }
        }
    }
    let por_e: HashMap<&String, &Bloco> = blocos_e.iter().map(|b| (&b.area, b)).collect();
    let por_d: HashMap<&String, &Bloco> = blocos_d.iter().map(|b| (&b.area, b)).collect();
    let mut cursor_e: HashMap<&String, f64> =
        ordem_esq.iter().map(|a| (a, por_e[a].y + (por_e[a].h - saida[a] as f64 * escala) / 2.0)).collect();
    let mut cursor_d: HashMap<&String, f64> =
        ordem_dir.iter().map(|a| (a, por_d[a].y + (por_d[a].h - entrada[a] as f64 * escala) / 2.0)).collect();
    let pos_e = |a: &String| ordem_esq.iter().position(|x| x == a).unwrap();
    let pos_d = |a: &String| ordem_dir.iter().position(|x| x == a).unwrap();
    let mut pares: Vec<(&(String, String), &i64)> = fluxos.iter().collect();
    pares.sort_by(|a, b| (pos_d(&a.0 .1), pos_e(&a.0 .0)).cmp(&(pos_d(&b.0 .1), pos_e(&b.0 .0))));
    let mut topo_e: HashMap<(String, String), f64> = HashMap::new();
    for o in &ordem_esq {
        let mut ds: Vec<(&String, i64)> = pares.iter().filter(|(k, _)| &k.0 == o).map(|(k, n)| (&k.1, **n)).collect();
        ds.sort_by_key(|(d, _)| pos_d(d));
        for (d, n) in ds {
            topo_e.insert((o.clone(), d.clone()), cursor_e[o]);
            *cursor_e.get_mut(o).unwrap() += n as f64 * escala;
        }
    }
    let mut topo_d: HashMap<(String, String), f64> = HashMap::new();
    for d in &ordem_dir {
        let mut os: Vec<(&String, i64)> = fluxos.iter().filter(|(k, _)| &k.1 == d).map(|(k, n)| (&k.0, *n)).collect();
        os.sort_by_key(|(o, _)| pos_e(o));
        for (o, n) in os {
            topo_d.insert((o.clone(), d.clone()), cursor_d[d]);
            *cursor_d.get_mut(d).unwrap() += n as f64 * escala;
        }
    }
    let faixas = pares
        .iter()
        .map(|((o, d), n)| Faixa {
            origem: o.clone(),
            destino: d.clone(),
            valor: **n,
            espessura: (**n as f64 * escala).max(1.0),
            y0: topo_e[&(o.clone(), d.clone())],
            y1: topo_d[&(o.clone(), d.clone())],
        })
        .collect();
    Layout { blocos_e, blocos_d, x_barra_e, x_barra_d, altura, faixas, escala, larg_e, larg_d }
}

fn linhas_rodape(d: &DuploMapa) -> Vec<String> {
    let c = &d.cobertura;
    let t = format!(
        "Desenhadas {} de {} citações com periódico ({} de {} que publicam o corpus; {} de {} citadas). Largura da faixa = citações da área da esquerda para a da direita. Sem área: {} das citações recebidas e {} das revistas.",
        c.desenhadas,
        c.referencias,
        d.esquerda.len(),
        revistas(d.total_esquerda),
        d.direita.len(),
        revistas(d.total_direita),
        porcentagem(c.pct_citadas_nao_classificadas),
        porcentagem(c.pct_revistas_nao_classificadas)
    );
    let a = "Classificação aproximada: a área de cada revista é inferida por palavras do NOME da revista (sem base de categorias) e pode errar ou faltar; confira a tabela revista → área.";
    let mut saida = textwrap(a, QUEBRA_RODAPE);
    saida.extend(textwrap(&t, QUEBRA_RODAPE));
    saida
}

fn f1(x: f64) -> String {
    format!("{:.1}", x)
}

/// SVG do duplo mapa, ou "" quando não há o que desenhar.
pub fn svg(dados: &DuploMapa, titulo: &str, largura_svg: i64, prefixo_id: Option<&str>) -> String {
    if !dados.aplicavel || dados.fluxos.is_empty() {
        return String::new();
    }
    let topo_t = if titulo.is_empty() { 12.0 } else { TOPO_TITULO };
    let cabeca_y = topo_t + 14.0;
    let d = layout(dados, largura_svg, topo_t + TOPO_CABECALHO);
    let rodape = linhas_rodape(dados);
    let altura = (topo_t + TOPO_CABECALHO + d.altura + 22.0 + 15.0 * rodape.len() as f64 + 8.0) as i64;
    let p = match prefixo_id {
        Some(s) => s.to_string(),
        None => {
            let base = format!(
                "{:?}{:?}{:?}",
                titulo,
                dados.esquerda.iter().map(|i| (&i.original, i.valor, &i.area)).collect::<Vec<_>>(),
                dados.direita.iter().map(|i| (&i.original, i.valor, &i.area)).collect::<Vec<_>>()
            );
            format!("dm{}", &hash8(&base)[..6])
        }
    };
    let cores = &dados.cores;
    let cor = |a: &str| cores.get(a).cloned().unwrap_or_else(|| "#8A94A6".into());
    let (x_e, x_d) = (d.x_barra_e, d.x_barra_d);
    let mut maiores: Vec<&Fluxo> = dados.fluxos.iter().collect();
    maiores.sort_by(|a, b| b.valor.cmp(&a.valor));
    let desc = format!(
        "Duplo mapa: áreas das revistas que publicam o corpus (esquerda) e das revistas citadas (direita), com classificação aproximada por palavras do nome. Maiores fluxos: {}.",
        maiores.iter().take(3).map(|f| format!("{} para {}, {}", f.origem, f.destino, citacoes(f.valor))).collect::<Vec<_>>().join("; ")
    );
    let mut o: Vec<String> = vec![];
    o.push(format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {largura_svg} {altura}\" width=\"{largura_svg}\" height=\"{altura}\" font-family=\"{FONTE_INTER}\" role=\"img\" aria-labelledby=\"{p}-t {p}-d\">"
    ));
    o.push(format!(
        "<title id=\"{p}-t\">{}</title><desc id=\"{p}-d\">{}</desc>",
        esc_limpo(if titulo.is_empty() { "Duplo mapa de áreas das revistas" } else { titulo }),
        esc_limpo(&desc)
    ));
    o.push("<style>.dm-fx{fill-opacity:.4;transition:fill-opacity .12s}.dm-fx:hover{fill-opacity:.75}</style>".into());
    o.push(format!("<rect width=\"{largura_svg}\" height=\"{altura}\" fill=\"#fff\"/>"));
    if !titulo.is_empty() {
        o.push(format!(
            "<text x=\"{:.0}\" y=\"28\" text-anchor=\"middle\" font-size=\"16\" font-weight=\"700\" fill=\"{TINTA}\">{}</text>",
            largura_svg as f64 / 2.0,
            esc_limpo(&cabe(titulo, largura_svg as f64 - 2.0 * MARGEM, 16.0, true))
        ));
    }
    o.push(format!(
        "<text x=\"{}\" y=\"{}\" text-anchor=\"end\" font-size=\"12\" font-weight=\"700\" fill=\"{TINTA_FRACA}\">{}</text>",
        f1(x_e + LARGURA_BARRA),
        cabeca_y + 4.0,
        esc_limpo(&dados.colunas[0])
    ));
    o.push(format!(
        "<text x=\"{}\" y=\"{}\" text-anchor=\"start\" font-size=\"12\" font-weight=\"700\" fill=\"{TINTA_FRACA}\">{}</text>",
        f1(x_d),
        cabeca_y + 4.0,
        esc_limpo(&dados.colunas[1])
    ));
    o.push("<g class=\"dm-faixas\">".into());
    for (k, f) in d.faixas.iter().enumerate() {
        let (x0, x1) = (x_e + LARGURA_BARRA, x_d);
        let xm = (x0 + x1) / 2.0;
        let (a0, a1) = (f.y0, f.y0 + f.espessura);
        let (b0, b1) = (f.y1, f.y1 + f.espessura);
        let pct = dados.fluxos.iter().find(|g| g.origem == f.origem && g.destino == f.destino).unwrap().pct;
        o.push(format!(
            "<path id=\"{p}-f{k}\" class=\"dm-fx\" fill=\"{}\" d=\"M{},{} C{},{} {},{} {},{} L{},{} C{},{} {},{} {},{} Z\"><title>{} → {}: {} ({} das desenhadas)</title></path>",
            cor(&f.origem),
            f1(x0), f1(a0), f1(xm), f1(a0), f1(xm), f1(b0), f1(x1), f1(b0),
            f1(x1), f1(b1), f1(xm), f1(b1), f1(xm), f1(a1), f1(x0), f1(a1),
            esc_limpo(&f.origem), esc_limpo(&f.destino), citacoes(f.valor), porcentagem(pct)
        ));
    }
    o.push("</g>".into());
    let areas: HashMap<&String, &AreaInfo> = dados.areas.iter().map(|a| (&a.nome, a)).collect();
    for (lado, blocos, x_barra) in [("e", &d.blocos_e, x_e), ("d", &d.blocos_d, x_d)] {
        o.push(format!("<g class=\"dm-col-{lado}\">"));
        let esq = lado == "e";
        let larg = if esq { d.larg_e } else { d.larg_d };
        let x_texto = if esq { x_barra - 12.0 } else { x_barra + LARGURA_BARRA + 12.0 };
        let ancora = if esq { "end" } else { "start" };
        for b in blocos.iter() {
            let c = cor(&b.area);
            let a = areas[&b.area];
            let n_rev = b.membros.len();
            let fluxo = if esq { a.saida } else { a.entrada };
            let dica = format!(
                "{}: {} revista{} desenhada{} · {} nas faixas · área inferida pelo nome",
                b.area,
                n_rev,
                if n_rev == 1 { "" } else { "s" },
                if n_rev == 1 { "" } else { "s" },
                citacoes(fluxo)
            );
            o.push(format!(
                "<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" rx=\"2\" fill=\"{c}\"><title>{}</title></rect>",
                f1(x_barra), f1(b.y), LARGURA_BARRA, f1(b.h), esc_limpo(&dica)
            ));
            let x_cab = if esq { x_barra + LARGURA_BARRA } else { x_barra };
            o.push(format!(
                "<text x=\"{}\" y=\"{}\" text-anchor=\"{ancora}\" font-size=\"12\" font-weight=\"700\" fill=\"{TINTA}\"><title>{}</title>{}</text>",
                f1(x_cab), f1(b.y - 6.0), esc_limpo(&dica),
                esc_limpo(&cabe(&b.area, larg + 12.0 + LARGURA_BARRA, 12.0, true))
            ));
            for m in &b.membros {
                let y = m.y_centro;
                let rot = cabe(&m.nome, larg, 12.0, false);
                if esq {
                    o.push(format!(
                        "<line x1=\"{}\" x2=\"{}\" y1=\"{}\" y2=\"{}\" stroke=\"{c}\" stroke-width=\"2\"/>",
                        f1(x_barra - 6.0), f1(x_barra), f1(y), f1(y)
                    ));
                } else {
                    o.push(format!(
                        "<line x1=\"{}\" x2=\"{}\" y1=\"{}\" y2=\"{}\" stroke=\"{c}\" stroke-width=\"2\"/>",
                        f1(x_barra + LARGURA_BARRA), f1(x_barra + LARGURA_BARRA + 6.0), f1(y), f1(y)
                    ));
                }
                let extra = if esq {
                    format!("{} citaç{}", m.valor, if m.valor == 1 { "ão feita" } else { "ões feitas" })
                } else {
                    format!(
                        "{} das revistas desenhadas à esquerda{}",
                        citacoes(m.valor),
                        if m.total != Some(m.valor) { format!(" ({} no corpus)", m.total.unwrap_or(0)) } else { String::new() }
                    )
                };
                let termo = if m.termo.is_empty() { " · sem termo que case".to_string() } else { format!(" · termo: {}", m.termo) };
                o.push(format!(
                    "<text x=\"{}\" y=\"{}\" text-anchor=\"{ancora}\" font-size=\"12\" fill=\"{TINTA}\"><title>{} — {}{} · {}</title>{}</text>",
                    f1(x_texto), f1(y + 4.0), esc_limpo(&m.nome), esc_limpo(&m.area), esc_limpo(&termo), esc_limpo(&extra), esc_limpo(&rot)
                ));
            }
        }
        o.push("</g>".into());
    }
    let y_rod = topo_t + TOPO_CABECALHO + d.altura + 24.0;
    for (n, linha) in rodape.iter().enumerate() {
        o.push(format!(
            "<text x=\"{}\" y=\"{:.0}\" font-size=\"11\" fill=\"{TINTA_FRACA}\">{}</text>",
            MARGEM, y_rod + 15.0 * n as f64, esc_limpo(linha)
        ));
    }
    o.push("</svg>".into());
    o.join("\n")
}
