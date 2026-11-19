//! Paridade com o Python: rajadas, dendrograma, linha do tempo e densidade.
mod comum;
use std::collections::BTreeMap;

use comum::*;
use redes_analises::{corpus, db, densidade, dendrograma, linha_do_tempo, rajadas};
use redes_core::{pipeline::executar_periodo, projeto::Projeto, Parametros};
use serde_json::Value;

fn parametros(v: &Value) -> Parametros {
    serde_json::from_value(v.clone()).unwrap()
}

fn rajadas_conf(nome: &str) {
    let Some(caminho) = projeto(nome) else { return };
    let r = referencia(nome);
    let c = db::abre(&caminho).unwrap();
    for (tipo, py) in r["rajadas"].as_object().unwrap() {
        let t = if tipo == "palavras" { rajadas::Tipo::Palavras } else { rajadas::Tipo::Referencias };
        let rs = rajadas::calcula(&c, t, 20, 3, 2.0, 1.0).unwrap();
        let pr = py["rajadas"].as_array().unwrap();
        assert_eq!(rs.rajadas.len(), pr.len(), "{nome}/{tipo} rajadas");
        for (a, b) in rs.rajadas.iter().zip(pr) {
            assert_eq!(a.termo, b["termo"].as_str().unwrap(), "{nome}/{tipo} termo");
            assert_eq!(a.termo_exibicao, b["termo_exibicao"].as_str().unwrap());
            assert_eq!((a.inicio, a.fim, a.primeiro_ano), (b["inicio"].as_i64().unwrap(), b["fim"].as_i64().unwrap(), b["primeiro_ano"].as_i64().unwrap()));
            assert_eq!(a.documentos as i64, b["documentos"].as_i64().unwrap());
            assert!(perto(a.forca, b["forca"].as_f64().unwrap(), 1e-9), "{nome}/{tipo} forca {} vs {}", a.forca, b["forca"]);
        }
        assert_eq!(rs.documentos_na_base as i64, py["documentos_na_base"].as_i64().unwrap());
        assert_eq!(rs.anos, py["anos"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap()).collect::<Vec<_>>());
    }
}

fn dendrogramas(nome: &str) {
    let Some(caminho) = projeto(nome) else { return };
    let r = referencia(nome);
    let projeto = Projeto::abrir(&caminho).unwrap();
    let per = projeto.periodos().unwrap().into_iter().next().unwrap();
    let mut cache: BTreeMap<String, redes_core::Resultado> = BTreeMap::new();
    for (chave, py) in r["dendrograma"].as_object().unwrap() {
        if py.get("vazio").is_some() {
            continue;
        }
        let params = parametros(&py["params"]);
        let ident = py["params"].to_string();
        if !cache.contains_key(&ident) {
            cache.insert(ident.clone(), executar_periodo(&projeto, per.id, &per.nome, &params).unwrap());
        }
        let res = &cache[&ident];
        let lig = dendrograma::Ligacao::de_texto(py["ligacao"].as_str().unwrap()).unwrap();
        let d = dendrograma::do_periodo(res, lig, 60, None, "Dendrograma").unwrap();
        let ctx = format!("{nome}/{chave}");
        let nos: Vec<i64> = py["nos"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap()).collect();
        assert_eq!(d.dendrograma.nos, nos, "{ctx} nos");
        let ordem: Vec<i64> = py["ordem"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap()).collect();
        assert_eq!(d.dendrograma.ordem, ordem, "{ctx} ordem");
        let fus = py["fusoes"].as_array().unwrap();
        assert_eq!(d.dendrograma.fusoes.len(), fus.len(), "{ctx} fusoes");
        for (a, b) in d.dendrograma.fusoes.iter().zip(fus) {
            assert_eq!((a.a as i64, a.b as i64, a.tamanho as i64), (b[0].as_i64().unwrap(), b[1].as_i64().unwrap(), b[3].as_i64().unwrap()), "{ctx} fusao");
            assert!(perto(a.altura, b[2].as_f64().unwrap(), 1e-9), "{ctx} altura {} vs {}", a.altura, b[2]);
        }
        assert!(perto(d.dendrograma.coph, py["coph"].as_f64().unwrap(), 1e-9), "{ctx} coph");
        assert_eq!(d.n_grupos_sugerido as i64, py["sugerido"].as_i64().unwrap(), "{ctx} sugerido");
        assert_eq!(d.omitidos as i64, py["omitidos"].as_i64().unwrap(), "{ctx} omitidos");
        let part: BTreeMap<i64, usize> = py["particao"].as_object().unwrap().iter().map(|(k, v)| (k.parse().unwrap(), v.as_u64().unwrap() as usize)).collect();
        assert_eq!(d.particao, part, "{ctx} particao");
        if let (Some(a), Some(b)) = (&d.comparacao, py["comparacao"].as_object()) {
            assert_eq!(a.n_comparados as i64, b["n_comparados"].as_i64().unwrap(), "{ctx} comparados");
            assert_eq!(a.n_grupos_corte as i64, b["n_grupos_corte"].as_i64().unwrap());
            assert_eq!(a.n_grupos_rede as i64, b["n_grupos_rede"].as_i64().unwrap());
            for (x, y) in [(a.ari, &b["ari"]), (a.nmi, &b["nmi"])] {
                match (x, y.as_f64()) {
                    (Some(x), Some(y)) => assert!(perto(x, y, 1e-6), "{ctx} ari/nmi {x} vs {y}"),
                    (None, None) => {}
                    o => panic!("{ctx} ari/nmi {o:?}"),
                }
            }
        } else {
            assert!(d.comparacao.is_none() && py["comparacao"].is_null(), "{ctx} comparacao");
        }
        let frases: Vec<&str> = py["frases"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
        assert_eq!(d.frases.iter().map(|s| s.as_str()).collect::<Vec<_>>(), frases, "{ctx} frases");
        assert_eq!(contagem_svg(&d.svg), contagem_svg(py["svg_texto"].as_str().unwrap()), "{ctx} elementos do SVG");
        igual_texto(&sem_hash(&d.svg, &["dg"]), &sem_hash(py["svg_texto"].as_str().unwrap(), &["dg"]), &format!("{ctx} SVG"));
    }
}

fn linhas(nome: &str) {
    let Some(caminho) = projeto(nome) else { return };
    let r = referencia(nome);
    let c = db::abre(&caminho).unwrap();
    for (chave, py) in r["linha"].as_object().unwrap() {
        let p = parametros(&py["params"]);
        let l = linha_do_tempo::constroi(&c, &p, 40, 8).unwrap();
        let ctx = format!("{nome}/{chave}");
        let pd = &py["dados"];
        assert_eq!(l.faixas.len(), pd["faixas"].as_array().unwrap().len(), "{ctx} faixas");
        for (f, pf) in l.faixas.iter().zip(pd["faixas"].as_array().unwrap()) {
            assert_eq!(f.rotulo, pf["rotulo"].as_str().unwrap(), "{ctx} rotulo da faixa");
            assert_eq!(f.indice as i64, pf["indice"].as_i64().unwrap());
            assert_eq!(f.frequencia_total, pf["frequencia_total"].as_i64().unwrap());
            assert_eq!(f.itens_total as i64, pf["itens_total"].as_i64().unwrap());
            assert_eq!(f.nos.len(), pf["nos"].as_array().unwrap().len(), "{ctx} nos da faixa {}", f.rotulo);
            for (n, pn) in f.nos.iter().zip(pf["nos"].as_array().unwrap()) {
                assert_eq!(n.id, pn["id"].as_i64().unwrap(), "{ctx} id");
                assert_eq!(n.rotulo, pn["rotulo"].as_str().unwrap());
                assert_eq!(n.ano, pn["ano"].as_i64().unwrap(), "{ctx} ano de {}", n.rotulo);
                assert_eq!(n.frequencia, pn["frequencia"].as_i64().unwrap());
                assert_eq!(n.rajada, pn["rajada"].as_bool().unwrap(), "{ctx} rajada de {}", n.rotulo);
                assert_eq!(n.rajada_inicio, pn["rajada_inicio"].as_i64());
                assert_eq!(n.rajada_fim, pn["rajada_fim"].as_i64());
                assert_eq!((n.primeiro, n.ultimo), (pn["primeiro"].as_i64().unwrap(), pn["ultimo"].as_i64().unwrap()));
            }
        }
        let pl = pd["ligacoes"].as_array().unwrap();
        assert_eq!(l.ligacoes.len(), pl.len(), "{ctx} ligacoes");
        for (a, b) in l.ligacoes.iter().zip(pl) {
            assert_eq!((a.origem, a.destino, a.cruzada), (b["origem"].as_i64().unwrap(), b["destino"].as_i64().unwrap(), b["cruzada"].as_bool().unwrap()), "{ctx} ligacao");
            assert!(perto(a.valor, b["valor"].as_f64().unwrap(), 1e-9));
        }
        assert_eq!(l.omitidos.itens as i64, pd["omitidos"]["itens"].as_i64().unwrap(), "{ctx} omitidos");
        assert_eq!(l.omitidos.agrupamentos as i64, pd["omitidos"]["agrupamentos"].as_i64().unwrap());
        assert_eq!(l.omitidos.sem_ano as i64, pd["omitidos"]["sem_ano"].as_i64().unwrap());
        assert_eq!(l.omitidos.descritores as i64, pd["omitidos"]["descritores"].as_i64().unwrap());
        assert_eq!(l.total_itens as i64, pd["total_itens"].as_i64().unwrap());
        assert_eq!(l.total_agrupamentos as i64, pd["total_agrupamentos"].as_i64().unwrap());
        assert_eq!(l.atividade, pd["atividade"].as_bool().unwrap());
        let avisos: Vec<&str> = pd["avisos"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
        assert_eq!(l.avisos.iter().map(|s| s.as_str()).collect::<Vec<_>>(), avisos, "{ctx} avisos");
        let svg = linha_do_tempo::svg(&l, "Linha do tempo", &BTreeMap::new());
        let svg_py = py["svg_texto"].as_str().unwrap();
        assert_eq!(contagem_svg(&svg), contagem_svg(svg_py), "{ctx} elementos do SVG");
        igual_texto(&sem_hash(&svg, &["lt"]), &sem_hash(svg_py, &["lt"]), &format!("{ctx} SVG"));
    }
}

fn densidades(nome: &str) {
    let Some(caminho) = projeto(nome) else { return };
    let r = referencia(nome);
    let c = db::abre(&caminho).unwrap();
    for (chave, py) in r["densidade"].as_object().unwrap() {
        let p = parametros(&py["params"]);
        let co = corpus::corpus_completo(&c, &p).unwrap();
        let (d, svg) = densidade::do_corpus(&co, "Mapa", 150, 4);
        let ctx = format!("{nome}/{chave}");
        assert_eq!(d.nos.len() as i64, py["n_nos"].as_i64().unwrap(), "{ctx} itens");
        let nos: Vec<i64> = py["nos"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap()).collect();
        assert_eq!(d.nos, nos, "{ctx} ordem dos itens");
        for (a, b) in d.pesos.iter().zip(py["pesos"].as_array().unwrap()) {
            assert!(perto(*a, b.as_f64().unwrap(), 1e-9), "{ctx} pesos");
        }
        if !d.nos.is_empty() {
            let (cr, cp) = (contagem_svg(&svg), contagem_json(&py["svg"]));
            // os rótulos dependem das posições (RNG próprio, ver README): o resto é estrutural
            for k in ["svg", "image", "rect", "desc", "defs", "linearGradient", "circle"] {
                assert_eq!(cr.get(k), cp.get(k), "{ctx} <{k}> no SVG");
            }
        }
    }
}

#[test]
fn rajadas_serj_auto() {
    rajadas_conf("serj_auto");
}
#[test]
fn rajadas_novo142() {
    rajadas_conf("novo142");
}
#[test]
fn dendrograma_serj_auto() {
    dendrogramas("serj_auto");
}
#[test]
fn dendrograma_novo142() {
    dendrogramas("novo142");
}
#[test]
fn linha_serj_auto() {
    linhas("serj_auto");
}
#[test]
fn linha_novo142() {
    linhas("novo142");
}
#[test]
fn densidade_serj_auto() {
    densidades("serj_auto");
}
#[test]
fn densidade_novo142() {
    densidades("novo142");
}
