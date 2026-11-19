//! Paridade com o Python: roda o núcleo Rust nas mesmas configurações que
//! `tests/gera_referencia.py` rodou no Python e compara grupos, nós, arestas e
//! medidas. Os projetos `.redes` (MBs) não vão ao repositório: o teste procura
//! em `$REDES_DADOS`, `<repo>/tests/dados` e `/home/claude/t`, e é pulado se não
//! os achar.

use std::collections::BTreeMap;
use std::io::Read;
use std::path::PathBuf;

use redes_core::{executar_periodo, Parametros, Projeto};
use serde_json::Value;

fn procura_projeto(nome: &str) -> Option<PathBuf> {
    let mut candidatos: Vec<PathBuf> = Vec::new();
    if let Ok(d) = std::env::var("REDES_DADOS") {
        candidatos.push(PathBuf::from(d));
    }
    let raiz = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
    candidatos.push(raiz.join("tests/dados"));
    candidatos.push(PathBuf::from("/home/claude/t"));
    candidatos.into_iter().map(|d| d.join(format!("{nome}.redes"))).find(|p| p.is_file())
}

fn referencia(nome: &str) -> Vec<Value> {
    let caminho = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(format!("tests/referencia/{nome}.json.gz"));
    let mut txt = String::new();
    flate2::read::GzDecoder::new(std::fs::File::open(caminho).unwrap()).read_to_string(&mut txt).unwrap();
    serde_json::from_str(&txt).unwrap()
}

fn proximo(a: f64, b: f64) -> bool {
    a == b || (a - b).abs() <= 1e-9 * a.abs().max(b.abs()).max(1.0)
}

fn digest(v: &[i64]) -> Vec<i64> {
    let mut v = v.to_vec();
    v.sort_unstable();
    vec![v.len() as i64, v.iter().sum(), v.iter().map(|x| x * x).sum()]
}

fn ints(v: &Value) -> Vec<i64> {
    v.as_array().unwrap().iter().map(|x| x.as_i64().unwrap()).collect()
}

fn titulo(p: &Parametros) -> String {
    format!(
        "{:?}/{:?}/{:?}/{:?} minf={} rede={}..{} corte={} map={:?} pal={:?}",
        p.unidade, p.matriz, p.algoritmo, p.similaridade, p.min_freq, p.rede_min, p.rede_max, p.corte, p.mapeadores, p.palavras
    )
}

/// Devolve as divergências de um caso (vazio = paridade total).
fn compara(projeto: &Projeto, caso: &Value) -> (usize, Vec<String>) {
    let mut p: Parametros = serde_json::from_value(caso["params"].clone()).unwrap();
    let mut dif = Vec::new();
    let mut comparados = 0;
    let periodos = projeto.periodos().unwrap();
    let ref_periodos = caso["periodos"].as_array().unwrap();
    for (per, r) in periodos.iter().zip(ref_periodos) {
        p.periodo = Some(per.nome.clone());
        let res = match executar_periodo(projeto, per.id, &per.nome, &p) {
            Ok(x) => x,
            Err(e) => {
                dif.push(format!("[{} | {}] erro: {e}", titulo(&p), per.nome));
                continue;
            }
        };
        comparados += 1;
        let s = &res.resumo;
        let mut d = |campo: &str, ok: bool, rust: String, py: String| {
            if !ok {
                dif.push(format!("[{} | {}] {campo}: rust={rust} python={py}", titulo(&p), per.nome));
            }
        };
        for (campo, rust) in [
            ("documentos", s.documentos),
            ("itens", s.itens),
            ("itens_reduzidos", s.itens_reduzidos),
            ("grupos", s.grupos),
            ("maior_grupo", s.maior_grupo),
            ("grupos_unitarios", s.grupos_unitarios),
            ("nos_rede", s.nos_rede),
            ("arestas_rede", s.arestas_rede),
        ] {
            let py = r[campo].as_u64().unwrap() as usize;
            d(campo, rust == py, rust.to_string(), py.to_string());
        }
        for (campo, rust) in [("centralidade_media", s.centralidade_media), ("densidade_media", s.densidade_media)] {
            let py = r[campo].as_f64().unwrap();
            d(campo, proximo(rust, py), rust.to_string(), py.to_string());
        }
        let soma: f64 = res.arestas.iter().map(|a| a.peso).sum();
        let pond: f64 = res.arestas.iter().map(|a| a.peso * ((a.a % 97 + 3 * (a.b % 89)) as f64)).sum();
        d("arestas_soma", proximo(soma, r["arestas_soma"].as_f64().unwrap()), soma.to_string(), r["arestas_soma"].to_string());
        d(
            "arestas_soma_ponderada",
            proximo(pond, r["arestas_soma_ponderada"].as_f64().unwrap()),
            pond.to_string(),
            r["arestas_soma_ponderada"].to_string(),
        );
        let freq = digest(&res.nos.iter().map(|n| n.frequencia as i64).collect::<Vec<_>>());
        d("frequencias", freq == ints(&r["frequencias"]), format!("{freq:?}"), r["frequencias"].to_string());

        let gl = r["grupos_lista"].as_array().unwrap();
        if gl.len() != res.grupos.len() {
            continue;
        }
        for (i, (g, rg)) in res.grupos.iter().zip(gl).enumerate() {
            let nos_py = ints(&rg["nos"]);
            d(&format!("grupo {i} nós"), g.nos == nos_py, format!("{:?}", g.nos), format!("{nos_py:?}"));
            d(
                &format!("grupo {i} principal"),
                g.principal == rg["principal"].as_i64(),
                format!("{:?}", g.principal),
                rg["principal"].to_string(),
            );
            d(&format!("grupo {i} exibição"), g.exibicao == rg["exibicao"].as_str().unwrap(), g.exibicao.clone(), rg["exibicao"].to_string());
            for (campo, rust, chave) in [
                ("centralidade", g.centralidade, "c"),
                ("densidade", g.densidade, "d"),
                ("faixa c", g.centralidade_faixa, "cf"),
                ("faixa d", g.densidade_faixa, "df"),
            ] {
                let py = rg[chave].as_f64().unwrap();
                d(&format!("grupo {i} {campo}"), proximo(rust, py), rust.to_string(), py.to_string());
            }
            for (m, docs) in &g.documentos {
                let dg = digest(docs);
                d(&format!("grupo {i} docs {m}"), dg == ints(&rg["docs"][m]), format!("{dg:?}"), rg["docs"][m].to_string());
            }
            let py_med: BTreeMap<String, f64> =
                rg["medidas"].as_object().unwrap().iter().map(|(k, v)| (k.clone(), v.as_f64().unwrap())).collect();
            for (k, v) in &py_med {
                let rust = g.medidas.get(k).copied();
                d(
                    &format!("grupo {i} medida {k}"),
                    rust.map(|x| proximo(x, *v)).unwrap_or(false),
                    format!("{rust:?}"),
                    v.to_string(),
                );
            }
        }
    }
    (comparados, dif)
}

fn roda(nome: &str) {
    let Some(caminho) = procura_projeto(nome) else {
        eprintln!("projeto {nome}.redes não encontrado: teste de paridade pulado");
        return;
    };
    let projeto = Projeto::abrir(&caminho).unwrap();
    let casos = referencia(nome);
    let (mut total, mut divergentes) = (0, Vec::new());
    let mut casos_ruins = 0;
    for caso in &casos {
        if caso.get("erro").is_some() {
            continue; // o Python também falhou: nada a comparar
        }
        let (n, dif) = compara(&projeto, caso);
        total += n;
        if !dif.is_empty() {
            casos_ruins += 1;
            divergentes.extend(dif);
        }
    }
    eprintln!("{nome}: {total} análises comparadas, {casos_ruins} casos com divergência, {} divergências", divergentes.len());
    for l in divergentes.iter().take(40) {
        eprintln!("  {l}");
    }
    assert!(divergentes.is_empty(), "{} divergências em {nome}", divergentes.len());
}

#[test]
fn paridade_serj_auto() {
    roda("serj_auto");
}

#[test]
fn paridade_novo142() {
    roda("novo142");
}

#[test]
fn paridade_eecera59_auto() {
    roda("eecera59_auto");
}

#[test]
fn paridade_zotero() {
    roda("zotero");
}

#[test]
fn paridade_segat() {
    roda("segat");
}
