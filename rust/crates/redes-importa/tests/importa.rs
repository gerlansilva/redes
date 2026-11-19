//! Testes da importação. A paridade byte a byte com o importador Python é checada por
//! `tests/paridade/paridade.py` (precisa do Python e dos dados de origem).

use std::path::{Path, PathBuf};

use redes_core::{Projeto, Unidade};
use redes_importa::loaders::detecta_formato_texto;
use redes_importa::{importar, interpreta_periodos, Formato, Opcoes, PeriodosPedidos};

fn exemplo() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../examples/exemplo_sintetico.csv")
}

fn escreve(dir: &Path, nome: &str, texto: &str) -> PathBuf {
    let p = dir.join(nome);
    std::fs::write(&p, texto).unwrap();
    p
}

fn contagem(caminho: &Path, sql: &str) -> i64 {
    rusqlite::Connection::open(caminho).unwrap().query_row(sql, [], |r| r.get(0)).unwrap()
}

#[test]
fn detecta_pelo_conteudo() {
    assert_eq!(detecta_formato_texto("TY  - JOUR\nTI  - x\nER  - \n", "txt"), Formato::Ris);
    assert_eq!(detecta_formato_texto("@article{a,\n title={x}\n}", "csv"), Formato::Bibtex);
    assert_eq!(detecta_formato_texto("PT J\nTI x\nER\n", "csv"), Formato::Wos);
    assert_eq!(detecta_formato_texto("PT\tAU\tTI\nJ\ta\tb\n", "txt"), Formato::Wos);
    assert_eq!(detecta_formato_texto("\"Authors\",\"Title\",\"Year\",\"Index Keywords\"\n", "csv"), Formato::Scopus);
    assert_eq!(detecta_formato_texto("Title,Author,Year,Citation count,Author IDs\n", "csv"), Formato::Openalex);
    assert_eq!(detecta_formato_texto("Key,Item Type,Publication Year,Author,Title\n", "csv"), Formato::Zotero);
    assert_eq!(detecta_formato_texto("Title,Authors,Year,Citations\n", "csv"), Formato::Csv);
    assert_eq!(detecta_formato_texto("{\"results\": []}", "json"), Formato::OpenalexJson);
    assert_eq!(detecta_formato_texto("qualquer coisa", "ris"), Formato::Ris);
}

#[test]
fn sintetico_abre_no_core() {
    let dir = tempfile::tempdir().unwrap();
    let g = importar(exemplo(), &Opcoes { pasta: Some(dir.path().to_path_buf()), ..Default::default() }).unwrap();
    assert_eq!(g.caminho, dir.path().join("exemplo_sintetico.redes"));
    let r = &g.resumo;
    assert_eq!(r.formato, "scopus");
    // Valores do importador Python para o mesmo arquivo.
    assert_eq!((r.documentos, r.palavras, r.autores, r.referencias, r.autores_referencia, r.fontes, r.paises), (15, 9, 8, 8, 8, 4, 3));
    assert_eq!(r.periodos, vec!["2009\u{2013}2023".to_string()]);

    let p = Projeto::abrir(&g.caminho).unwrap();
    let periodos = p.periodos().unwrap();
    assert_eq!(periodos.len(), 1);
    let ds = p.dataset(Unidade::Words, periodos[0].id, &["autor".to_string(), "fonte".to_string()]).unwrap();
    assert_eq!(ds.documentos.len(), 15);
    assert_eq!(ds.itens.len(), 9);
}

#[test]
fn esquema_com_gatilhos() {
    let dir = tempfile::tempdir().unwrap();
    let g = importar(exemplo(), &Opcoes { pasta: Some(dir.path().to_path_buf()), nome: Some("meu projeto".into()), ..Default::default() }).unwrap();
    assert!(g.caminho.ends_with("meu projeto.redes"));
    assert_eq!(contagem(&g.caminho, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"), 30);
    assert_eq!(contagem(&g.caminho, "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'"), 34);
    assert_eq!(contagem(&g.caminho, "SELECT COUNT(*) FROM KnowledgeBaseVersion WHERE knowledgeBaseVersion='v1_03'"), 1);
    // contadores mantidos pelos gatilhos
    assert!(contagem(&g.caminho, "SELECT SUM(author_documentsCount) FROM Author") > 0);
}

#[test]
fn ris_bibtex_wos_openalex_json() {
    let dir = tempfile::tempdir().unwrap();
    let ris = escreve(dir.path(), "a.ris", "TY  - JOUR\nTI  - Titulo\n  continuado\nAU  - Lopes, Celi Espasandin\nPY  - 2018\nJO  - Rev X\nKW  - a; b\nN1  - Cited By: 5\nC1  - Univ Sao Paulo, Sao Paulo, Brazil\nER  - \n");
    let g = importar(&ris, &Opcoes::default()).unwrap();
    assert_eq!((g.resumo.formato.as_str(), g.resumo.documentos, g.resumo.palavras, g.resumo.paises), ("ris", 1, 2, 1));
    assert_eq!(contagem(&g.caminho, "SELECT citationsCount FROM Document"), 5);
    assert_eq!(contagem(&g.caminho, "SELECT COUNT(*) FROM Author WHERE authorName='Lopes, C.E.'"), 1);

    let bib = escreve(dir.path(), "a.bib", "@article{k,\n title={Educa{\\c{c}}{\\~a}o},\n author={Silva, Jo{\\~a}o and Souza, M.},\n year={2020},\n journal={Rev},\n keywords={x, y}\n}\n");
    let g = importar(&bib, &Opcoes::default()).unwrap();
    assert_eq!((g.resumo.formato.as_str(), g.resumo.autores, g.resumo.palavras), ("bibtex", 2, 2));
    assert_eq!(contagem(&g.caminho, "SELECT COUNT(*) FROM Document WHERE title='Educação'"), 1);

    let wos = escreve(dir.path(), "w.txt", "PT J\nAU Lopes, CE\n   Batanero, C\nTI Titulo\nSO REV\nPY 2017\nTC 3\nDE a; b\nC1 Univ Granada, Granada, Spain.\nCR Smith J, 2001, J EDUC, V3, P5\nER\n\nEF\n");
    let g = importar(&wos, &Opcoes::default()).unwrap();
    assert_eq!((g.resumo.formato.as_str(), g.resumo.autores, g.resumo.paises), ("wos", 2, 1));

    let tab = escreve(dir.path(), "t.txt", "PT\tAU\tTI\tSO\tPY\tTC\tDE\tC1\nJ\tLopes, CE; Batanero, C\tTitulo\tREV\t2017\t3\ta; b\tUniv Granada, Granada, Spain\n");
    let g = importar(&tab, &Opcoes::default()).unwrap();
    assert_eq!((g.resumo.formato.as_str(), g.resumo.documentos, g.resumo.autores, g.resumo.palavras), ("wos", 1, 2, 2));

    let json = escreve(
        dir.path(),
        "o.json",
        r#"{"results":[{"id":"https://openalex.org/W1","title":"Um trabalho","publication_year":2021,"cited_by_count":4,"doi":"https://doi.org/10.1/x","type":"article",
        "authorships":[{"author":{"display_name":"Celi Espasandin Lopes"},"institutions":[{"display_name":"UFSCar","country_code":"BR"}]}],
        "keywords":[{"display_name":"estatistica"}],"primary_location":{"source":{"display_name":"Rev Z"}},
        "abstract_inverted_index":{"Um":[0],"resumo":[1]}}]}"#,
    );
    let g = importar(&json, &Opcoes::default()).unwrap();
    assert_eq!((g.resumo.formato.as_str(), g.resumo.documentos, g.resumo.paises), ("openalex-json", 1, 1));
    assert_eq!(contagem(&g.caminho, "SELECT citationsCount FROM Document"), 4);
}

#[test]
fn periodos_informados_e_automaticos() {
    assert_eq!(interpreta_periodos("").unwrap(), PeriodosPedidos::Automatico);
    assert_eq!(interpreta_periodos("3").unwrap(), PeriodosPedidos::Quantidade(3));
    assert_eq!(interpreta_periodos("unico").unwrap(), PeriodosPedidos::Unico);
    assert_eq!(
        interpreta_periodos("2008-2014, Depois=2015\u{2013}2020").unwrap(),
        PeriodosPedidos::Faixas(vec![("2008\u{2013}2014".into(), 2008, 2014), ("Depois".into(), 2015, 2020)])
    );
    assert!(interpreta_periodos("2014-2008").is_err());
    assert!(interpreta_periodos("abc").is_err());

    let dir = tempfile::tempdir().unwrap();
    let g = importar(exemplo(), &Opcoes { pasta: Some(dir.path().to_path_buf()), periodos: Some("2009-2015,2016-2023".into()), ..Default::default() }).unwrap();
    assert_eq!(g.resumo.periodos, vec!["2009\u{2013}2015".to_string(), "2016\u{2013}2023".to_string()]);
    let p = Projeto::abrir(&g.caminho).unwrap();
    assert_eq!(p.periodos().unwrap().len(), 2);
    let docs: usize = p
        .periodos()
        .unwrap()
        .iter()
        .map(|pe| p.dataset(Unidade::Words, pe.id, &["autor".to_string(), "fonte".to_string()]).unwrap().documentos.len())
        .sum();
    assert_eq!(docs, 15);
}

#[test]
fn divisao_automatica_em_1_a_4() {
    use redes_importa::construtor::sugere_periodos;
    let anos: Vec<i64> = (2000..2020).flat_map(|a| vec![a; 10]).collect(); // 200 docs, 20 anos
    let p = sugere_periodos(&anos, None, 40);
    assert_eq!(p.len(), 4);
    assert_eq!((p[0].1, p.last().unwrap().2), (2000, 2019));
    // poucos documentos: um período só
    assert_eq!(sugere_periodos(&[2001, 2002, 2003], None, 40).len(), 1);
    assert_eq!(sugere_periodos(&[], None, 40), vec![("0\u{2013}9999".to_string(), 0, 9999)]);
}

#[test]
fn erros_claros() {
    let dir = tempfile::tempdir().unwrap();
    assert!(importar(dir.path().join("nao_existe.csv"), &Opcoes::default()).is_err());
    let vazio = escreve(dir.path(), "v.csv", "Title,Authors,Year\n");
    let e = importar(&vazio, &Opcoes::default()).unwrap_err().to_string();
    assert!(e.contains("nenhum documento"), "{e}");
}

#[test]
fn progresso_e_duplicatas() {
    let dir = tempfile::tempdir().unwrap();
    let csv = escreve(dir.path(), "d.csv", "Title,Authors,Year,Citations\nUm artigo,\"A, B.\",2001,3\nUM ARTIGO,\"A, B.\",2001,5\nOutro,\"C, D.\",2002,1\n");
    let mut fases = vec![];
    let g = redes_importa::importar_com_progresso(&csv, &Opcoes::default(), &mut |f, _| fases.push(f.to_string())).unwrap();
    assert_eq!((g.resumo.documentos, g.resumo.documentos_lidos, g.resumo.duplicatas_removidas), (2, 3, 1));
    assert_eq!(fases.first().map(|s| s.as_str()), Some("Lendo o arquivo"));
    assert_eq!(fases.last().map(|s| s.as_str()), Some("Conclu\u{ed}do"));
    let g = importar(&csv, &Opcoes { remove_repetidos: false, nome: Some("sem-junta".into()), ..Default::default() }).unwrap();
    assert_eq!(g.resumo.documentos, 3);
}
