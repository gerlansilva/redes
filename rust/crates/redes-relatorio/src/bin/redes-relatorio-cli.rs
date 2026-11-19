//! `redes-relatorio-cli`: gera o relatório HTML em português.
//!
//! ```text
//! redes-relatorio-cli projeto <arquivo.redes> -o <saida> [--formato unico|pasta] [--estendido] [--frequencia N]
//! redes-relatorio-cli json <dados.json> -o <saida> [--formato unico|pasta]
//! ```

use std::path::PathBuf;

use anyhow::{bail, Context, Result};
use redes_core::Projeto;
use redes_relatorio::{adaptador, dados::DadosRelatorio, pasta, unico};

const AJUDA: &str = "uso:
  redes-relatorio-cli projeto <arquivo.redes> -o <saida> [--formato unico|pasta] [--estendido] [--frequencia N]
  redes-relatorio-cli json <dados.json> -o <saida> [--formato unico|pasta]
  redes-relatorio-cli exporta-json <arquivo.redes> -o <dados.json> [--estendido] [--frequencia N]
Formato 'unico' (padrão): <saida> é o arquivo HTML; 'pasta': <saida> é a pasta de páginas.";

fn main() {
    if let Err(e) = executa() {
        eprintln!("redes-relatorio-cli: erro: {e:#}");
        std::process::exit(2);
    }
}

fn executa() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() < 2 || args[0] == "-h" || args[0] == "--help" {
        println!("{AJUDA}");
        return Ok(());
    }
    let comando = args[0].clone();
    let entrada = PathBuf::from(&args[1]);
    let mut saida: Option<PathBuf> = None;
    let mut formato = "unico".to_string();
    let mut estendido = false;
    let mut frequencia: Option<usize> = None;
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "-o" | "--saida" => {
                i += 1;
                saida = Some(PathBuf::from(args.get(i).context("falta o valor de -o")?));
            }
            "--formato" => {
                i += 1;
                formato = args.get(i).context("falta o valor de --formato")?.clone();
            }
            "--estendido" => estendido = true,
            "--frequencia" => {
                i += 1;
                frequencia = Some(args.get(i).context("falta o valor de --frequencia")?.parse()?);
            }
            outro => bail!("opção desconhecida: {outro}\n{AJUDA}"),
        }
        i += 1;
    }
    let saida = saida.context("falta -o <saida>")?;
    if formato != "unico" && formato != "pasta" {
        bail!("formato: unico ou pasta");
    }
    let dados: DadosRelatorio = match comando.as_str() {
        "projeto" | "exporta-json" => {
            let projeto = Projeto::abrir(&entrada)?;
            let nome = entrada.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default();
            adaptador::dados_do_projeto(&projeto, &nome, estendido, frequencia)?
        }
        "json" => serde_json::from_str(&std::fs::read_to_string(&entrada)?).context("JSON de entrada inválido")?,
        c => bail!("comando desconhecido: {c}\n{AJUDA}"),
    };
    if comando == "exporta-json" {
        std::fs::write(&saida, serde_json::to_string_pretty(&dados)?)?;
        println!("{}", saida.display());
        return Ok(());
    }
    let caminho = if formato == "pasta" { pasta::gera_pasta(&saida, &dados)? } else { unico::gera_arquivo_unico(&saida, &dados)? };
    println!("{}", caminho.display());
    for i in &dados.ignoradas {
        eprintln!("não gerada: {} — {}", i.rotulo, i.motivo);
    }
    Ok(())
}
