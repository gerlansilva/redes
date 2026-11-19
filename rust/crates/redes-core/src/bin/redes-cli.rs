//! `redes-cli analisa <projeto> [opções]`: imprime o resultado em JSON (ou TSV
//! com as colunas de `python3 -m redes analisa`).

use anyhow::{bail, Context, Result};
use redes_core::pipeline::{linha_tsv, CABECALHO_TSV};
use redes_core::{executar_periodos, Algoritmo, Mapeador, Matriz, Parametros, Projeto, Similaridade, Unidade};

const AJUDA: &str = "uso: redes-cli analisa <projeto.redes> [opções]
  --unidade Words|Authors|References|AuthorsReference|ReferenceSources|Countries
  --matriz CoOccurrence|BasicCoupling|AggregatedCouplingBasedOnAuthor|AggregatedCouplingBasedOnJournal
  --algoritmo CentersSimples|AverageLink|CompleteLink|SingleLink|SumLink|Louvain
  --similaridade AssociationStrength|EquivalenceIndex|InclusionIndex|JaccardIndex|SaltonCosine
  --min-freq N  --min-cooc N  --rede-min N  --rede-max N  --corte X  --k-core N
  --mapeadores nucleo interseccao secundarios kcore uniao acoplamento
  --palavras autor fonte adicionada      --ignorar ITEM...
  --periodo NOME...                      (padrão: todos os períodos)
  --formato json|tsv                     (padrão: json)
  --sem-rede                             (JSON sem a lista de nós e arestas)";

fn valor(args: &[String], i: &mut usize, nome: &str) -> Result<String> {
    *i += 1;
    args.get(*i).cloned().with_context(|| format!("falta o valor de {nome}"))
}

fn lista(args: &[String], i: &mut usize) -> Vec<String> {
    let mut v = Vec::new();
    while let Some(a) = args.get(*i + 1) {
        if a.starts_with("--") {
            break;
        }
        v.push(a.clone());
        *i += 1;
    }
    v
}

fn main() {
    if let Err(e) = executa() {
        eprintln!("redes-cli: erro: {e}");
        std::process::exit(2);
    }
}

fn executa() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args[0] == "-h" || args[0] == "--help" {
        println!("{AJUDA}");
        return Ok(());
    }
    if args[0] != "analisa" {
        bail!("comando desconhecido: {} (use `analisa`)\n{AJUDA}", args[0]);
    }
    let mut caminho: Option<String> = None;
    let mut p = Parametros::default();
    let mut periodos: Vec<String> = Vec::new();
    let mut formato = "json".to_string();
    let mut sem_rede = false;

    let mut i = 1;
    while i < args.len() {
        let a = args[i].clone();
        match a.as_str() {
            "--unidade" => p.unidade = Unidade::de_texto(&valor(&args, &mut i, &a)?)?,
            "--matriz" => p.matriz = Matriz::de_texto(&valor(&args, &mut i, &a)?)?,
            "--algoritmo" => p.algoritmo = Algoritmo::de_texto(&valor(&args, &mut i, &a)?)?,
            "--similaridade" => p.similaridade = Similaridade::de_texto(&valor(&args, &mut i, &a)?)?,
            "--min-freq" => p.min_freq = valor(&args, &mut i, &a)?.parse()?,
            "--min-cooc" => p.min_cooc = valor(&args, &mut i, &a)?.parse()?,
            "--rede-min" => p.rede_min = valor(&args, &mut i, &a)?.parse()?,
            "--rede-max" => p.rede_max = valor(&args, &mut i, &a)?.parse()?,
            "--corte" => p.corte = valor(&args, &mut i, &a)?.parse()?,
            "--k-core" => p.k_core = valor(&args, &mut i, &a)?.parse()?,
            "--mapeadores" => {
                p.mapeadores = lista(&args, &mut i).iter().map(|m| Mapeador::de_texto(m)).collect::<Result<_, _>>()?
            }
            "--palavras" => p.palavras = lista(&args, &mut i),
            "--ignorar" => {
                p.ignorar = lista(&args, &mut i)
                    .iter()
                    .flat_map(|v| v.replace('\n', ";").split(';').map(|s| s.trim().to_string()).collect::<Vec<_>>())
                    .filter(|s| !s.is_empty())
                    .collect()
            }
            "--periodo" => periodos = lista(&args, &mut i),
            "--formato" => formato = valor(&args, &mut i, &a)?,
            "--sem-rede" => sem_rede = true,
            _ if a.starts_with("--") => bail!("opção desconhecida: {a}\n{AJUDA}"),
            _ => {
                if caminho.is_some() {
                    bail!("argumento extra: {a}");
                }
                caminho = Some(a);
            }
        }
        i += 1;
    }
    let caminho = caminho.context("informe o projeto .redes")?;
    let projeto = Projeto::abrir(&caminho)?;
    let mut resultados = executar_periodos(&projeto, &p, &periodos)?;

    match formato.as_str() {
        "tsv" => {
            println!("{}", CABECALHO_TSV.join("\t"));
            for r in &resultados {
                println!("{}", linha_tsv(r).join("\t"));
            }
        }
        "json" => {
            if sem_rede {
                for r in &mut resultados {
                    r.nos.clear();
                    r.arestas.clear();
                }
            }
            use std::io::Write;
            let mut saida = std::io::stdout().lock();
            let _ = writeln!(saida, "{}", serde_json::to_string(&resultados)?); // pipe fechado não é erro
        }
        outro => bail!("formato desconhecido: {outro}"),
    }
    Ok(())
}
