mod comum;
use comum::*;
use redes_analises::areas::Regras;
use redes_analises::{db, duplo_mapa};
use serde_json::Value;

fn itens(rs: &[duplo_mapa::Item], py: &Value, ctx: &str) {
    let py = py.as_array().unwrap();
    assert_eq!(rs.len(), py.len(), "{ctx} itens");
    for (a, b) in rs.iter().zip(py) {
        assert_eq!(a.nome, b["nome"].as_str().unwrap(), "{ctx} nome");
        assert_eq!(a.original, b["original"].as_str().unwrap());
        assert_eq!(a.area, b["area"].as_str().unwrap(), "{ctx} area de {}", a.nome);
        assert_eq!(a.termo, b["termo"].as_str().unwrap(), "{ctx} termo de {}", a.nome);
        assert_eq!(a.valor, b["valor"].as_i64().unwrap());
        assert_eq!(a.no_desenho, b.get("no_desenho").and_then(|v| v.as_i64()));
        assert_eq!(a.total, b.get("total").and_then(|v| v.as_i64()));
    }
}

fn confere(nome: &str) {
    let Some(caminho) = projeto(nome) else { return };
    let r = referencia(nome);
    let c = db::abre(&caminho).unwrap();
    for (rotulo, py) in r["duplo_mapa"].as_object().unwrap() {
        let (e, d) = (py["max"][0].as_u64().unwrap() as usize, py["max"][1].as_u64().unwrap() as usize);
        let dm = duplo_mapa::calcula_do_banco(&c, e, d, &Regras::padrao());
        let pd = &py["dados"];
        let ctx = format!("{nome}/{rotulo}");
        assert_eq!(dm.aplicavel, pd["aplicavel"].as_bool().unwrap(), "{ctx} aplicavel");
        assert_eq!(duplo_mapa::aplicavel(&c), py["aplicavel"].as_bool().unwrap());
        assert_eq!(dm.aviso, pd["aviso"].as_str().unwrap(), "{ctx} aviso");
        if !dm.aplicavel {
            continue;
        }
        itens(&dm.esquerda, &pd["esquerda"], &format!("{ctx} esquerda"));
        itens(&dm.direita, &pd["direita"], &format!("{ctx} direita"));
        let pa = pd["areas"].as_array().unwrap();
        assert_eq!(dm.areas.len(), pa.len(), "{ctx} areas");
        for (a, b) in dm.areas.iter().zip(pa) {
            assert_eq!((a.nome.as_str(), a.cor.as_str()), (b["nome"].as_str().unwrap(), b["cor"].as_str().unwrap()));
            assert_eq!((a.esquerda as i64, a.direita as i64, a.saida, a.entrada),
                (b["esquerda"].as_i64().unwrap(), b["direita"].as_i64().unwrap(), b["saida"].as_i64().unwrap(), b["entrada"].as_i64().unwrap()), "{ctx} area {}", a.nome);
        }
        let pf = pd["fluxos"].as_array().unwrap();
        assert_eq!(dm.fluxos.len(), pf.len(), "{ctx} fluxos");
        for (a, b) in dm.fluxos.iter().zip(pf) {
            assert_eq!((a.origem.as_str(), a.destino.as_str(), a.valor), (b["origem"].as_str().unwrap(), b["destino"].as_str().unwrap(), b["valor"].as_i64().unwrap()));
            assert!(perto(a.pct, b["pct"].as_f64().unwrap(), 1e-12));
        }
        let pt = pd["tabela"].as_array().unwrap();
        assert_eq!(dm.tabela.len(), pt.len(), "{ctx} tabela");
        for (a, b) in dm.tabela.iter().zip(pt) {
            assert_eq!((a.revista.as_str(), a.area.as_str(), a.termo.as_str(), a.publica, a.citada, a.no_desenho),
                (b["revista"].as_str().unwrap(), b["area"].as_str().unwrap(), b["termo"].as_str().unwrap(), b["publica"].as_i64().unwrap(), b["citada"].as_i64().unwrap(), b["no_desenho"].as_bool().unwrap()), "{ctx} tabela");
        }
        let pc = &pd["cobertura"];
        let c = &dm.cobertura;
        assert_eq!((c.referencias, c.desenhadas, c.sem_fonte, c.revistas as i64, c.revistas_nao_classificadas as i64, c.documentos, c.documentos_com_revista),
            (pc["referencias"].as_i64().unwrap(), pc["desenhadas"].as_i64().unwrap(), pc["sem_fonte"].as_i64().unwrap(), pc["revistas"].as_i64().unwrap(), pc["revistas_nao_classificadas"].as_i64().unwrap(), pc["documentos"].as_i64().unwrap(), pc["documentos_com_revista"].as_i64().unwrap()), "{ctx} cobertura");
        for (x, k) in [(c.pct_revistas_nao_classificadas, "pct_revistas_nao_classificadas"), (c.pct_citadas_nao_classificadas, "pct_citadas_nao_classificadas"),
            (c.pct_citantes_nao_classificadas, "pct_citantes_nao_classificadas"), (c.pct_desenho_nao_classificadas, "pct_desenho_nao_classificadas")] {
            assert!(perto(x, pc[k].as_f64().unwrap(), 1e-12), "{ctx} {k}");
        }
        let pl = pd["ligacoes"].as_array().unwrap();
        assert_eq!(dm.ligacoes.len(), pl.len(), "{ctx} ligacoes");
        for (a, b) in dm.ligacoes.iter().zip(pl) {
            assert_eq!((a.origem.as_str(), a.destino.as_str(), a.valor), (b["origem"].as_str().unwrap(), b["destino"].as_str().unwrap(), b["valor"].as_i64().unwrap()));
        }
        let avisos: Vec<&str> = pd["avisos"].as_array().unwrap().iter().map(|v| v.as_str().unwrap()).collect();
        assert_eq!(dm.avisos.iter().map(|s| s.as_str()).collect::<Vec<_>>(), avisos);
        assert_eq!((dm.total_esquerda as i64, dm.total_direita as i64), (pd["total_esquerda"].as_i64().unwrap(), pd["total_direita"].as_i64().unwrap()));
        let svg = duplo_mapa::svg(&dm, "Duplo mapa", duplo_mapa::LARGURA, None);
        let svg_py = py["svg_texto"].as_str().unwrap();
        assert_eq!(contagem_svg(&svg), contagem_svg(svg_py), "{ctx} elementos");
        igual_texto(&sem_hash2(&svg), &sem_hash2(svg_py), &format!("{ctx} SVG"));
    }
}

fn sem_hash2(s: &str) -> String {
    let re = regex::Regex::new(r"dm[0-9a-f]{6}").unwrap();
    re.replace_all(s, "dmXXXXXX").into_owned()
}

#[test]
fn duplo_mapa_serj_auto() {
    confere("serj_auto");
}

#[test]
fn duplo_mapa_novo142() {
    confere("novo142");
}
