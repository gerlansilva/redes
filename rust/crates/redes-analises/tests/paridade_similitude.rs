mod comum;
use comum::*;
use redes_analises::similitude::{self, ParametrosSimilitude};
use redes_analises::similitude_viz;
use serde_json::Value;

fn parametros(p: &Value) -> ParametrosSimilitude {
    let mut o = ParametrosSimilitude::default();
    if let Some(v) = p.get("indice_nome").and_then(|v| v.as_str()) {
        o.indice = v.into();
    }
    if let Some(v) = p.get("segmento").and_then(|v| v.as_str()) {
        o.segmento = v.into();
    }
    if let Some(v) = p.get("idioma").and_then(|v| v.as_str()) {
        o.idioma = v.into();
    }
    if let Some(v) = p.get("n_formas").and_then(|v| v.as_u64()) {
        o.n_formas = v as usize;
    }
    if let Some(v) = p.get("extras").and_then(|v| v.as_u64()) {
        o.extras = v as usize;
    }
    o
}

fn confere(nome: &str) {
    let Some(caminho) = projeto(nome) else { return };
    let r = referencia(nome);
    let c = redes_analises::db::abre(&caminho).unwrap();
    for (rotulo, ref_caso) in r["similitude"].as_object().unwrap() {
        let p = parametros(&ref_caso["params"]);
        let res = similitude::analisa(&c, None, &p).unwrap_or_else(|e| panic!("{nome}/{rotulo}: {e}"));
        let py = &ref_caso["res"];
        let ctx = format!("{nome}/{rotulo}");
        assert_eq!(res.n_resumos as u64, py["n_resumos"].as_u64().unwrap(), "{ctx} n_resumos");
        assert_eq!(res.n_lidos as u64, py["n_lidos"].as_u64().unwrap(), "{ctx} n_lidos");
        assert_eq!(res.n_segmentos as u64, py["n_segmentos"].as_u64().unwrap(), "{ctx} n_segmentos");
        let pf = py["formas"].as_array().unwrap();
        assert_eq!(res.formas.len(), pf.len(), "{ctx} formas");
        for (a, b) in res.formas.iter().zip(pf) {
            assert_eq!(a.id, b["id"].as_str().unwrap(), "{ctx} ordem das formas");
            assert_eq!(a.forma, b["forma"].as_str().unwrap(), "{ctx} rotulo de {}", a.id);
            assert_eq!(a.frequencia, b["frequencia"].as_i64().unwrap(), "{ctx} frequencia de {}", a.id);
            assert_eq!(a.resumos as u64, b["resumos"].as_u64().unwrap(), "{ctx} resumos de {}", a.id);
            assert_eq!(a.ocorrencias, b["ocorrencias"].as_i64().unwrap(), "{ctx} ocorrencias de {}", a.id);
            assert_eq!(a.comunidade as u64, b["comunidade"].as_u64().unwrap(), "{ctx} bloco de {}", a.id);
            assert_eq!(a.grau, b["grau"].as_i64().unwrap(), "{ctx} grau de {}", a.id);
        }
        let pa = py["arestas"].as_array().unwrap();
        assert_eq!(res.arestas.len(), pa.len(), "{ctx} arestas");
        for (a, b) in res.arestas.iter().zip(pa) {
            assert_eq!(a.origem, b["origem"].as_str().unwrap(), "{ctx} origem");
            assert_eq!(a.destino, b["destino"].as_str().unwrap(), "{ctx} destino");
            assert_eq!(a.tipo, b["tipo"].as_str().unwrap(), "{ctx} tipo");
            assert!(perto(a.peso, b["peso"].as_f64().unwrap(), 1e-9), "{ctx} peso {} vs {}", a.peso, b["peso"]);
        }
        let pc = py["comunidades"].as_array().unwrap();
        assert_eq!(res.comunidades.len(), pc.len(), "{ctx} blocos");
        for (a, b) in res.comunidades.iter().zip(pc) {
            assert_eq!(a.nome, b["nome"].as_str().unwrap(), "{ctx} nome do bloco");
            assert_eq!(a.n as u64, b["n"].as_u64().unwrap(), "{ctx} tamanho do bloco");
        }
        assert_eq!(res.n_arvore as u64, py["n_arvore"].as_u64().unwrap());
        assert_eq!(res.n_extras as u64, py["n_extras"].as_u64().unwrap());
        assert_eq!(res.componentes as u64, py["componentes"].as_u64().unwrap());
        let avisos: Vec<&str> = py["avisos"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
        assert_eq!(res.avisos.iter().map(|s| s.as_str()).collect::<Vec<_>>(), avisos, "{ctx} avisos");
        assert_eq!(similitude::csv_formas(&res), ref_caso["csv_formas"].as_str().unwrap(), "{ctx} csv formas");
        assert_eq!(similitude::csv_arestas(&res), ref_caso["csv_arestas"].as_str().unwrap(), "{ctx} csv arestas");
        let gml = similitude::graphml(&res);
        let gml_py = ref_caso["graphml"].as_str().unwrap();
        if p.indice == "binomial" {
            // os pesos binomiais usam lgamma; o Rust usa Stirling (diferença ~1e-13): só a estrutura
            assert_eq!(gml.lines().count(), gml_py.lines().count(), "{ctx} graphml (linhas)");
        } else {
            assert_eq!(gml, gml_py, "{ctx} graphml");
        }
        let svg = similitude_viz::svg(&res, "Similitude", None, true, None);
        assert_eq!(contagem_svg(&svg), contagem_json(&ref_caso["svg"]), "{ctx} elementos do SVG");
        let svg_py = ref_caso["svg_texto"].as_str().unwrap();
        if svg != svg_py {
            let (a, b): (Vec<&str>, Vec<&str>) = (svg.lines().collect(), svg_py.lines().collect());
            let difs = a.iter().zip(b.iter()).filter(|(x, y)| x != y).count();
            eprintln!("{ctx}: SVG difere em {difs} de {} linhas", b.len());
            if let Some((x, y)) = a.iter().zip(b.iter()).find(|(x, y)| x != y) {
                eprintln!("  rust:   {x}\n  python: {y}");
            }
            if p.indice != "binomial" {
                panic!("{ctx}: SVG diferente do Python");
            }
        }
    }
}

#[test]
fn similitude_serj_auto() {
    confere("serj_auto");
}

#[test]
fn similitude_novo142() {
    confere("novo142");
}
