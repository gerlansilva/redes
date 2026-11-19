//! Paridade da segunda leva com o Python (`tests/gera_referencia2.py`):
//! Instituições, componente mínimo, citações por tema, centralidades, pontos de
//! virada, qualidade, rótulos por tema e mapas longitudinais. Os projetos
//! `.redes` são procurados em `$REDES_DADOS`, `<repo>/tests/dados` e
//! `/home/claude/t`; sem eles o teste é pulado.

use std::collections::BTreeMap;
use std::io::Read;
use std::path::PathBuf;

use redes_core::longitudinal::evolucao;
use redes_core::pipeline::executar_analise;
use redes_core::{Parametros, Projeto, Similaridade};
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

fn referencia(nome: &str) -> Value {
    let caminho = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(format!("tests/referencia2/{nome}.json.gz"));
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

fn strs(v: &Value) -> Vec<String> {
    v.as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_string()).collect()
}

fn opt_f(v: &Value) -> Option<f64> {
    v.as_f64()
}

fn titulo(p: &Parametros) -> String {
    format!(
        "{:?}/{:?}/{:?}/{:?} minf={} cm={:?} rede={}..{} map={:?}",
        p.unidade, p.matriz, p.algoritmo, p.similaridade, p.min_freq, p.componente_minimo, p.rede_min, p.rede_max, p.mapeadores
    )
}

struct Dif {
    ctx: String,
    lista: Vec<String>,
}

impl Dif {
    fn ok(&mut self, campo: &str, ok: bool, rust: impl std::fmt::Debug, py: impl std::fmt::Debug) {
        if !ok {
            self.lista.push(format!("[{}] {campo}: rust={rust:?} python={py:?}", self.ctx));
        }
    }
    fn f(&mut self, campo: &str, rust: f64, py: &Value) {
        let ok = py.as_f64().map(|p| proximo(rust, p)).unwrap_or(false);
        self.ok(campo, ok, rust, py);
    }
}

fn a_grupos(a: &redes_core::Analise) -> Vec<Vec<i64>> {
    a.conjunto.agrupamentos.iter().map(|g| g.nos.clone()).collect()
}

/// Silhuetas dos nós de grupos com 3 ou mais nós.
fn silhuetas_validas(a: &redes_core::Analise, listas: &[Vec<i64>]) -> Vec<f64> {
    let Some((_, rot, val)) = redes_core::qualidade::silhuetas(&a.rede, listas) else { return Vec::new() };
    let tam: Vec<usize> = listas.iter().map(|g| g.len()).collect();
    rot.iter().zip(val).filter(|(r, _)| tam[**r] >= redes_core::qualidade::MINIMO_NOS_SILHUETA).map(|(_, v)| v).collect()
}

fn compara_periodo(projeto: &Projeto, p: &Parametros, per_id: i64, per_nome: &str, r: &Value, dif: &mut Vec<String>) {
    let mut d = Dif { ctx: format!("{} | {per_nome}", titulo(p)), lista: Vec::new() };
    let a = match executar_analise(projeto, per_id, per_nome, p) {
        Ok(a) => a,
        Err(e) => {
            dif.push(format!("[{}] erro: {e}", d.ctx));
            return;
        }
    };
    let analise = &a;
    let res = &a.resultado;
    let s = &res.resumo;
    for (campo, rust) in [
        ("documentos", s.documentos),
        ("documentos_projeto", s.documentos_projeto),
        ("itens", s.itens),
        ("itens_reduzidos", s.itens_reduzidos),
        ("grupos", s.grupos),
        ("maior_grupo", s.maior_grupo),
        ("grupos_unitarios", s.grupos_unitarios),
        ("nos_rede", s.nos_rede),
        ("arestas_rede", s.arestas_rede),
    ] {
        let py = r[campo].as_u64().unwrap() as usize;
        d.ok(campo, rust == py, rust, py);
    }
    let soma: f64 = res.arestas.iter().map(|x| x.peso).sum();
    d.f("arestas_soma", soma, &r["arestas_soma"]);
    let freq = digest(&res.nos.iter().map(|n| n.frequencia as i64).collect::<Vec<_>>());
    d.ok("frequencias", freq == ints(&r["frequencias"]), &freq, &r["frequencias"]);

    let gl = r["grupos_lista"].as_array().unwrap();
    if gl.len() == res.grupos.len() {
        for (i, (g, rg)) in res.grupos.iter().zip(gl).enumerate() {
            d.ok(&format!("grupo {i} nós"), g.nos == ints(&rg["nos"]), &g.nos, &rg["nos"]);
            d.ok(&format!("grupo {i} principal"), g.principal == rg["principal"].as_i64(), g.principal, &rg["principal"]);
            d.ok(&format!("grupo {i} exibição"), g.exibicao == rg["exibicao"].as_str().unwrap(), &g.exibicao, &rg["exibicao"]);
            d.f(&format!("grupo {i} centralidade"), g.centralidade, &rg["c"]);
            d.f(&format!("grupo {i} densidade"), g.densidade, &rg["d"]);
            d.ok(&format!("grupo {i} citações"), g.citacoes == rg["citacoes"].as_i64(), g.citacoes, &rg["citacoes"]);
            for (m, docs) in &g.documentos {
                let dg = digest(docs);
                d.ok(&format!("grupo {i} docs {m}"), dg == ints(&rg["docs"][m]), &dg, &rg["docs"][m]);
            }
            let py_med: BTreeMap<String, f64> =
                rg["medidas"].as_object().unwrap().iter().map(|(k, v)| (k.clone(), v.as_f64().unwrap())).collect();
            for (k, v) in &py_med {
                let rust = g.medidas.get(k).copied();
                d.ok(&format!("grupo {i} medida {k}"), rust.map(|x| proximo(x, *v)).unwrap_or(false), rust, v);
            }
        }
    }

    // filtro de componente mínimo
    match (&res.filtro_agrupamento, r["filtro"].is_null()) {
        (Some(f), false) => {
            let py = &r["filtro"];
            for (campo, rust) in [
                ("minimo", f.minimo),
                ("grupos_antes", f.grupos_antes),
                ("grupos_depois", f.grupos_depois),
                ("componentes_pequenos", f.componentes_pequenos),
                ("isolados", f.isolados),
                ("nos_sem_agrupamento", f.nos_sem_agrupamento),
            ] {
                d.ok(&format!("filtro {campo}"), py[campo].as_u64() == Some(rust as u64), rust, &py[campo]);
            }
        }
        (None, true) => {}
        (f, _) => d.ok("filtro presença", false, f.is_some(), &r["filtro"]),
    }

    // instituições
    if let Some(i) = &res.ies {
        let py = &r["ies"];
        d.ok("ies componente_minimo", py["componente_minimo"].as_u64() == Some(i.componente_minimo as u64), i.componente_minimo, &py["componente_minimo"]);
        d.ok("ies variantes_unidas", py["variantes_unidas"].as_u64() == Some(i.variantes_unidas as u64), i.variantes_unidas, &py["variantes_unidas"]);
        d.ok("ies isolados", py["isolados"].as_u64() == Some(i.isolados as u64), i.isolados, &py["isolados"]);
        let comps: Vec<i64> = ints(&py["componentes"]);
        d.ok("ies componentes", i.componentes.iter().map(|&x| x as i64).collect::<Vec<_>>() == comps, &i.componentes, &py["componentes"]);
        let pq: Vec<Vec<String>> = py["componentes_pequenos"].as_array().unwrap().iter().map(strs).collect();
        d.ok("ies componentes_pequenos", i.componentes_pequenos == pq, &i.componentes_pequenos, &pq);
        let uni = py["unioes"].as_array().unwrap();
        d.ok("ies unioes (n)", uni.len() == i.unioes.len(), i.unioes.len(), uni.len());
        for (k, (u, pu)) in i.unioes.iter().zip(uni).enumerate() {
            d.ok(&format!("união {k} id"), pu["id"].as_i64() == Some(u.id), u.id, &pu["id"]);
            d.ok(&format!("união {k} adotado"), pu["adotado"].as_str() == Some(u.adotado.as_str()), &u.adotado, &pu["adotado"]);
            d.ok(&format!("união {k} documentos"), pu["documentos"].as_u64() == Some(u.documentos as u64), u.documentos, &pu["documentos"]);
            let vs = pu["variantes"].as_array().unwrap();
            d.ok(&format!("união {k} variantes (n)"), vs.len() == u.variantes.len(), u.variantes.len(), vs.len());
            for (v, pv) in u.variantes.iter().zip(vs) {
                let ok = pv["nome"].as_str() == Some(v.nome.as_str())
                    && pv["documentos"].as_u64() == Some(v.documentos as u64)
                    && pv["motivo"].as_str() == Some(v.motivo.as_str());
                d.ok(&format!("união {k} variante {}", v.nome), ok, v, pv);
            }
        }
    } else {
        d.ok("ies ausente", r.get("ies").is_none(), "None", &r["ies"]);
    }

    // centralidades
    if let (Some(c), Some(py)) = (&res.centralidades, r.get("centralidades").filter(|v| !v.is_null())) {
        let py = py.as_object().unwrap();
        d.ok("centralidades (n)", py.len() == c.len(), c.len(), py.len());
        for x in c {
            let Some(v) = py.get(&x.id.to_string()) else {
                d.ok(&format!("centralidade nó {}", x.id), false, "presente", "ausente");
                continue;
            };
            let rust = [x.grau, x.intermediacao, x.proximidade, x.autovetor, x.pagerank];
            for (k, nome) in ["grau", "intermediacao", "proximidade", "autovetor", "pagerank"].iter().enumerate() {
                d.f(&format!("nó {} {nome}", x.id), rust[k], &v[k]);
            }
        }
    }

    // pontos de virada
    if let (Some(pv), Some(py)) = (&res.pontos_de_virada, r.get("pivos").filter(|v| !v.is_null())) {
        d.ok("pivos n_nos", py["n_nos"].as_u64() == Some(pv.n_nos as u64), pv.n_nos, &py["n_nos"]);
        d.ok("pivos suficiente", py["suficiente"].as_bool() == Some(pv.suficiente), pv.suficiente, &py["suficiente"]);
        d.ok("pivos avisos", strs(&py["avisos"]) == pv.avisos, &pv.avisos, &py["avisos"]);
        d.ok("pivos nao_calculado", py["nao_calculado"].as_str() == pv.nao_calculado.as_deref(), &pv.nao_calculado, &py["nao_calculado"]);
        for (nome, lista, pl) in [("pivo", &pv.pivos, &py["pivos"]), ("descritor", &pv.termos_descritores, &py["termos_descritores"])] {
            let pl = pl.as_array().unwrap();
            d.ok(&format!("{nome}s (n)"), pl.len() == lista.len(), lista.len(), pl.len());
            for (k, (x, px)) in lista.iter().zip(pl).enumerate() {
                d.ok(&format!("{nome} {k} nó"), px["no"].as_i64() == Some(x.no), x.no, &px["no"]);
                d.ok(&format!("{nome} {k} rótulo"), px["rotulo"].as_str() == Some(x.rotulo.as_str()), &x.rotulo, &px["rotulo"]);
                d.f(&format!("{nome} {k} intermediação"), x.intermediacao, &px["intermediacao"]);
                d.ok(&format!("{nome} {k} grau"), px["grau"].as_u64() == Some(x.grau as u64), x.grau, &px["grau"]);
                d.ok(&format!("{nome} {k} vizinhos"), px["grupos_vizinhos"].as_u64() == Some(x.grupos_vizinhos as u64), x.grupos_vizinhos, &px["grupos_vizinhos"]);
                d.ok(&format!("{nome} {k} grupo"), px["grupo"].as_u64() == x.grupo.map(|g| g as u64), x.grupo, &px["grupo"]);
                d.ok(&format!("{nome} {k} frequência"), px["frequencia"].as_u64() == Some(x.frequencia as u64), x.frequencia, &px["frequencia"]);
                if nome == "descritor" {
                    d.f(&format!("{nome} {k} proporção"), x.proporcao_documentos.unwrap_or(-1.0), &px["proporcao_documentos"]);
                    d.ok(&format!("{nome} {k} motivo"), px["motivo"].as_str() == x.motivo.as_deref(), &x.motivo, &px["motivo"]);
                }
            }
        }
    }

    // qualidade
    if let (Some(q), Some(py)) = (&res.qualidade, r.get("qualidade").filter(|v| !v.is_null())) {
        d.ok("qualidade nivel", py["nivel"].as_str() == Some(q.nivel.as_str()), &q.nivel, &py["nivel"]);
        d.ok("qualidade n_nos", py["n_nos"].as_u64() == Some(q.n_nos as u64), q.n_nos, &py["n_nos"]);
        d.ok("qualidade n_grupos", py["n_grupos"].as_u64() == Some(q.n_grupos as u64), q.n_grupos, &py["n_grupos"]);
        d.ok("qualidade componentes", py["componentes"].as_u64() == Some(q.componentes as u64), q.componentes, &py["componentes"]);
        d.f("qualidade pct_agrupados", q.pct_agrupados, &py["pct_agrupados"]);
        d.f("qualidade pct_em_grupos_grandes", q.pct_em_grupos_grandes, &py["pct_em_grupos_grandes"]);
        for (campo, rust) in [
            ("q", q.q),
            ("q_louvain", q.q_louvain),
            ("razao", q.razao),
            ("silhueta_media", q.silhueta_media),
            ("pct_silhueta_negativa", q.pct_silhueta_negativa),
        ] {
            let pyv = opt_f(&py[campo]);
            let ok = match (rust, pyv) {
                (Some(a), Some(b)) if campo == "pct_silhueta_negativa" => {
                    // Silhueta nula em teoria sai com sinal ao acaso (ruído de 1e-16 que depende da
                    // ordem das somas do BLAS do numpy): cada empate pode mudar a contagem de um item.
                    let listas: Vec<Vec<i64>> = a_grupos(analise);
                    let validos = silhuetas_validas(analise, &listas);
                    let empates = validos.iter().filter(|v| v.abs() < 1e-12).count() as f64;
                    let folga = if validos.is_empty() { 0.0 } else { 100.0 * empates / validos.len() as f64 };
                    proximo(a, b) || (a - b).abs() <= folga + 1e-9
                }
                (Some(a), Some(b)) => proximo(a, b),
                (None, None) => true,
                _ => false,
            };
            d.ok(&format!("qualidade {campo}"), ok, rust, pyv);
        }
        let ps = py["silhueta_por_grupo"].as_array().unwrap();
        d.ok("qualidade silhueta_por_grupo (n)", ps.len() == q.silhueta_por_grupo.len(), q.silhueta_por_grupo.len(), ps.len());
        for (k, (x, px)) in q.silhueta_por_grupo.iter().zip(ps).enumerate() {
            let ok = match (x, opt_f(px)) {
                (Some(a), Some(b)) => proximo(*a, b),
                (None, None) => true,
                _ => false,
            };
            d.ok(&format!("qualidade silhueta grupo {k}"), ok, x, px);
        }
        d.ok("qualidade avisos", strs(&py["avisos"]) == q.avisos, &q.avisos, &py["avisos"]);
    }

    // rótulos por tema
    if let Some(py) = r.get("rotulos").filter(|v| !v.is_null()) {
        let py = py.as_object().unwrap();
        let rust: BTreeMap<usize, _> = res.grupos.iter().enumerate().filter_map(|(i, g)| g.tema.clone().map(|t| (i, t))).collect();
        d.ok("rótulos (n)", py.len() == rust.len(), rust.len(), py.len());
        for (i, t) in &rust {
            let Some(px) = py.get(&i.to_string()) else {
                d.ok(&format!("rótulo {i}"), false, &t.rotulo, "ausente");
                continue;
            };
            d.ok(&format!("rótulo {i} termos"), strs(&px["termos"]) == t.termos, &t.termos, &px["termos"]);
            d.ok(&format!("rótulo {i} rotulo"), px["rotulo"].as_str() == Some(t.rotulo.as_str()), &t.rotulo, &px["rotulo"]);
            d.ok(&format!("rótulo {i} indicativo"), px["indicativo"].as_bool() == Some(t.indicativo), t.indicativo, &px["indicativo"]);
            d.ok(&format!("rótulo {i} documentos"), px["documentos"].as_u64() == Some(t.documentos as u64), t.documentos, &px["documentos"]);
        }
    }
    dif.extend(d.lista);
}

fn roda(nome: &str) {
    let Some(caminho) = procura_projeto(nome) else {
        eprintln!("projeto {nome}.redes não encontrado: teste de paridade pulado");
        return;
    };
    let projeto = Projeto::abrir(&caminho).unwrap();
    let ref_ = referencia(nome);
    let periodos = projeto.periodos().unwrap();
    let mut dif: Vec<String> = Vec::new();
    let mut analises = 0;
    for caso in ref_["casos"].as_array().unwrap() {
        if caso.get("erro").is_some() {
            continue;
        }
        let p: Parametros = serde_json::from_value(caso["params"].clone()).unwrap();
        for (per, r) in periodos.iter().zip(caso["periodos"].as_array().unwrap()) {
            let mut p = p.clone();
            p.periodo = Some(per.nome.clone());
            compara_periodo(&projeto, &p, per.id, &per.nome, r, &mut dif);
            analises += 1;
        }
    }
    let mut longs = 0;
    for l in ref_["longitudinal"].as_array().unwrap() {
        longs += 1;
        let p: Parametros = serde_json::from_value(l["params"].clone()).unwrap();
        let medida = Similaridade::de_texto(l["medida"].as_str().unwrap()).unwrap();
        let mut d = Dif { ctx: format!("longitudinal {} {:?}", titulo(&p), medida), lista: Vec::new() };
        let ev = match evolucao(&projeto, &p, medida, 3) {
            Ok(e) => e,
            Err(e) => {
                dif.push(format!("[{}] erro: {e}", d.ctx));
                continue;
            }
        };
        d.ok("períodos", ev.periodos == strs(&l["periodos"]), &ev.periodos, &l["periodos"]);
        d.ok("parametros", l["parametros"].as_str() == Some(ev.parametros.as_str()), &ev.parametros, &l["parametros"]);
        let pn = l["nos"].as_array().unwrap();
        d.ok("nós (n)", pn.len() == ev.nos.len(), ev.nos.len(), pn.len());
        for (k, (n, x)) in ev.nos.iter().zip(pn).enumerate() {
            let itens: Vec<i64> = n.itens.iter().copied().collect();
            let nomes_ok = x["nomes"].as_object().unwrap().iter().all(|(id, v)| n.nomes.get(&id.parse::<i64>().unwrap()).map(|s| s.as_str()) == v.as_str());
            let ok = x["periodo"].as_u64() == Some(n.periodo as u64)
                && x["selo"].as_u64() == Some(n.selo as u64)
                && x["rotulo"].as_str() == Some(n.rotulo.as_str())
                && ints(&x["itens"]) == itens
                && x["principal"].as_i64() == n.principal
                && x["tamanho"].as_u64() == Some(n.tamanho as u64)
                && nomes_ok;
            d.ok(&format!("nó {k}"), ok, (n.periodo, n.selo, &n.rotulo), x);
        }
        let pe = l["elos"].as_array().unwrap();
        d.ok("elos (n)", pe.len() == ev.elos.len(), ev.elos.len(), pe.len());
        for (k, (e, x)) in ev.elos.iter().zip(pe).enumerate() {
            let ok = x[0].as_u64() == Some(e.origem as u64)
                && x[1].as_u64() == Some(e.destino as u64)
                && proximo(e.peso, x[2].as_f64().unwrap())
                && x[3].as_bool() == Some(e.principal_comum);
            d.ok(&format!("elo {k}"), ok, (e.origem, e.destino, e.peso, e.principal_comum), x);
        }
        for (i, linha) in ev.sobreposicao.iter().enumerate() {
            for (j, v) in linha.iter().enumerate() {
                d.f(&format!("sobreposição {i},{j}"), *v, &l["sobreposicao"][i][j]);
            }
        }
        let pt = l["transicoes"].as_array().unwrap();
        d.ok("transições (n)", pt.len() == ev.transicoes.len(), ev.transicoes.len(), pt.len());
        for (k, (t, x)) in ev.transicoes.iter().zip(pt).enumerate() {
            d.ok(&format!("transição {k} de/para"), x["de"].as_str() == Some(t.de.as_str()) && x["para"].as_str() == Some(t.para.as_str()), &t.de, x);
            d.ok(&format!("transição {k} somem"), strs(&x["somem"]) == t.somem, &t.somem, &x["somem"]);
            d.ok(&format!("transição {k} surgem"), strs(&x["surgem"]) == t.surgem, &t.surgem, &x["surgem"]);
            let pc = x["continuam"].as_array().unwrap();
            d.ok(&format!("transição {k} continuam (n)"), pc.len() == t.continuam.len(), t.continuam.len(), pc.len());
            for (c, xc) in t.continuam.iter().zip(pc) {
                let ok = xc["de"].as_str() == Some(c.de.as_str())
                    && xc["para"].as_str() == Some(c.para.as_str())
                    && xc["sobreposicao"].as_f64() == Some(c.sobreposicao)
                    && xc["itens_comuns"].as_u64() == Some(c.itens_comuns as u64)
                    && strs(&xc["exemplos"]) == c.exemplos
                    && xc["mesmo_no_principal"].as_bool() == Some(c.mesmo_no_principal)
                    && xc["fraca"].as_bool() == Some(c.fraca)
                    && xc["itens_de"].as_u64() == Some(c.itens_de as u64)
                    && xc["itens_para"].as_u64() == Some(c.itens_para as u64);
                d.ok(&format!("transição {k} continua {}", c.de), ok, c, xc);
            }
        }
        let pajek = ev.pajek();
        d.ok("pajek", l["pajek"].as_str() == Some(pajek.as_str()), "(texto)", "(texto)");
        dif.extend(d.lista);
    }
    eprintln!("{nome}: {analises} análises e {longs} mapas longitudinais comparados, {} divergências", dif.len());
    for l in dif.iter().take(40) {
        eprintln!("  {l}");
    }
    assert!(dif.is_empty(), "{} divergências em {nome}", dif.len());
}

#[test]
fn paridade2_serj_auto() {
    roda("serj_auto");
}

#[test]
fn paridade2_novo142() {
    roda("novo142");
}

#[test]
fn paridade2_eecera59_auto() {
    roda("eecera59_auto");
}

#[test]
fn paridade2_zotero() {
    roda("zotero");
}

#[test]
fn paridade2_segat() {
    roda("segat");
}

#[test]
fn paridade2_novo142_auto() {
    roda("novo142_auto");
}
