//! `redes-importa-cli <arquivo> [opções]`: importa uma exportação bibliográfica e grava `.redes`.

use std::io::Write;
use std::path::PathBuf;

use redes_importa::{importar_com_progresso, AutoresReferencia, Formato, Opcoes};

const AJUDA: &str = "uso: redes-importa-cli <arquivo> [opções]
  --formato auto|csv|bibtex|ris|openalex|openalex-json|wos|scopus|zotero   (padrão: auto)
  --saida CAMINHO.redes        arquivo de saída (padrão: <arquivo>.redes ao lado da origem)
  --nome NOME                  nome do projeto (arquivo NOME.redes na pasta da origem)
  --periodos FAIXAS            2008-2014,2015-2020 | N (quantidade) | unico  (padrão: 1 a 4 automáticos)
  --manter-repetidos           não junta registros com o mesmo DOI ou título e ano
  --autores-referencia primeiro|todos|lista
  --nao-unir-periodicos        não junta periódicos que só diferem por caixa, acento ou pontuação
  --json                       imprime o resumo em JSON
  -q                           sem mensagens de progresso";

fn main() {
    if let Err(e) = executa() {
        eprintln!("redes-importa-cli: erro: {e}");
        std::process::exit(2);
    }
}

fn executa() -> Result<(), String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args.iter().any(|a| a == "-h" || a == "--help") {
        println!("{AJUDA}");
        return Ok(());
    }
    let mut arquivo: Option<PathBuf> = None;
    let mut o = Opcoes::default();
    let mut json = false;
    let mut quieto = false;
    let mut i = 0;
    let valor = |i: &mut usize, nome: &str| -> Result<String, String> {
        *i += 1;
        args.get(*i).cloned().ok_or_else(|| format!("falta o valor de {nome}"))
    };
    while i < args.len() {
        match args[i].as_str() {
            "--formato" => {
                let v = valor(&mut i, "--formato")?;
                o.formato = if v == "auto" { None } else { Some(Formato::de_nome(&v).ok_or_else(|| format!("formato desconhecido: {v}"))?) };
            }
            "--saida" => {
                let v = PathBuf::from(valor(&mut i, "--saida")?);
                let nome = v.file_stem().and_then(|s| s.to_str()).unwrap_or("projeto").to_string();
                o.pasta = Some(v.parent().map(|p| p.to_path_buf()).filter(|p| !p.as_os_str().is_empty()).unwrap_or_else(|| PathBuf::from(".")));
                o.nome = Some(nome);
            }
            "--nome" => o.nome = Some(valor(&mut i, "--nome")?),
            "--periodos" => o.periodos = Some(valor(&mut i, "--periodos")?),
            "--manter-repetidos" => o.remove_repetidos = false,
            "--nao-unir-periodicos" => o.unir_periodicos = false,
            "--autores-referencia" => {
                o.autores_referencia = match valor(&mut i, "--autores-referencia")?.as_str() {
                    "primeiro" => AutoresReferencia::Primeiro,
                    "todos" => AutoresReferencia::Todos,
                    "lista" => AutoresReferencia::Lista,
                    v => return Err(format!("--autores-referencia inválido: {v}")),
                }
            }
            "--json" => json = true,
            "-q" => quieto = true,
            a if a.starts_with("--") => return Err(format!("opção desconhecida: {a}\n{AJUDA}")),
            a => arquivo = Some(PathBuf::from(a)),
        }
        i += 1;
    }
    let arquivo = arquivo.ok_or_else(|| format!("falta o arquivo de origem\n{AJUDA}"))?;
    let mut ultima = String::new();
    let g = importar_com_progresso(&arquivo, &o, &mut |fase, f| {
        if !quieto && fase != ultima {
            eprintln!("[{:>3}%] {fase}", (f * 100.0) as u32);
            ultima = fase.to_string();
        }
    })
    .map_err(|e| e.to_string())?;
    let r = &g.resumo;
    if json {
        println!("{}", serde_json::to_string_pretty(&g).map_err(|e| e.to_string())?);
    } else {
        let mut out = std::io::stdout();
        let _ = writeln!(out, "{} documentos ({}) -> {}", r.documentos, r.formato, g.caminho.display());
        if r.duplicatas_removidas > 0 {
            let _ = writeln!(out, "duplicatas removidas: {} de {} registros lidos", r.duplicatas_removidas, r.documentos_lidos);
        }
        if r.sem_citacoes > 0 {
            let _ = writeln!(out, "AVISO: {} documento(s) sem 'Cited by' (campo vazio): guardados como ausentes, não como zero citações", r.sem_citacoes);
        }
        let _ = writeln!(out, "sem palavras-chave: {}; sem país: {}; sem referências: {}", r.sem_palavras, r.sem_pais, r.sem_referencias);
        let _ = writeln!(out, "palavras: {} grafias, {} grupos", r.palavras, r.grupos_palavra);
        let _ = writeln!(out, "autores: {} grafias, {} grupos", r.autores, r.grupos_autor);
        let _ = writeln!(out, "referências: {} itens, {} grupos", r.referencias, r.grupos_referencia);
        let _ = writeln!(out, "autores de referência: {} grafias, {} grupos", r.autores_referencia, r.grupos_autor_referencia);
        let _ = writeln!(out, "períodos: {}", r.periodos.join(", "));
    }
    Ok(())
}
