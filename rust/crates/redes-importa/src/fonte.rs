//! Estrutura comum dos carregadores (porta de `loaders/base.py`).

use indexmap::IndexMap;
use unicode_normalization::UnicodeNormalization;

use crate::rx;
use crate::util::*;

/// Um registro importado, antes de virar linhas do armazenamento.
#[derive(Clone, Debug, Default)]
pub struct DocumentoFonte {
    pub titulo: String,
    pub autores: Vec<String>,
    pub autores_completos: Vec<String>,
    pub ano: String,
    /// `None` = "Cited by" vazio na origem (ausente, diferente de zero).
    pub citacoes: Option<i64>,
    pub periodico: String,
    pub doi: String,
    pub tipo: String,
    pub resumo: String,
    pub afiliacoes: Vec<String>,
    pub paises: Vec<String>,
    pub palavras_autor: Vec<String>,
    pub palavras_fonte: Vec<String>,
    pub referencias: Vec<String>,
    pub referencias_brutas: Vec<String>,
    pub referencias_convertidas: bool,
    pub metadados: IndexMap<String, String>,
}

/// "Lopes, Celi Espasandin" -> "Lopes, C.E."
pub fn abrevia_autor(nome: &str) -> String {
    let nome = strip(nome);
    if nome.is_empty() {
        return String::new();
    }
    let (sobrenome, resto): (String, String) = if let Some((s, r)) = nome.split_once(',') {
        (s.to_string(), r.to_string())
    } else {
        let partes = palavras(nome);
        if partes.len() < 2 {
            return nome.to_string();
        }
        (partes[partes.len() - 1].to_string(), partes[..partes.len() - 1].join(" "))
    };
    let tokens: Vec<&str> = strip(&resto).split(|c: char| e_espaco(c) || c == '-').filter(|p| !p.is_empty()).collect();
    if !tokens.is_empty() && tokens.iter().all(|p| rx!(r"^[A-Z](?:\.?-?[A-Z])*\.?$").is_match(p).unwrap_or(false)) {
        return format!("{}, {}", strip(&sobrenome), tokens.concat());
    }
    let iniciais: Vec<String> = tokens
        .iter()
        .filter(|p| p.chars().next().map_or(false, |c| c.is_alphabetic()))
        .map(|p| format!("{}.", p.chars().next().unwrap().to_uppercase()))
        .collect();
    if iniciais.is_empty() {
        return strip(&sobrenome).to_string();
    }
    format!("{}, {}", strip(&sobrenome), iniciais.concat())
}

// ------------------------------------------------------------------ duplicatas

fn chave_doi(doi: &str) -> String {
    let t = strip(doi).to_lowercase();
    let t = rx!(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)").replace(&t, "").to_string();
    strip(&t).trim_end_matches('.').to_string()
}

fn chave_titulo(titulo: &str, ano: &str) -> String {
    let t: String = titulo.nfkd().filter(|c| !combina(*c)).collect::<String>().to_lowercase();
    let t: String = t.chars().filter(|c| c.is_ascii_lowercase() || c.is_ascii_digit()).collect();
    if t.is_empty() {
        return String::new();
    }
    let a = strip(ano);
    let a4 = rx!(r"^\d{4}").find(a).ok().flatten().map(|m| m.as_str().to_string()).unwrap_or_default();
    format!("{t}|{a4}")
}

fn completude(d: &DocumentoFonte) -> usize {
    d.referencias.len() + d.palavras_autor.len() + d.palavras_fonte.len() + d.afiliacoes.len() + d.autores.len()
        + if d.resumo.is_empty() { 0 } else { 3 }
        + if d.doi.is_empty() { 0 } else { 2 }
}

fn titulo_todo_maiusculo(t: &str) -> bool {
    let letras: Vec<char> = t.chars().filter(|c| c.is_alphabetic()).collect();
    letras.len() > 3 && letras.iter().all(|c| !c.is_lowercase())
}

fn une(mut base: DocumentoFonte, outro: &DocumentoFonte) -> DocumentoFonte {
    if base.ano.is_empty() && !outro.ano.is_empty() {
        base.ano = outro.ano.clone();
    }
    if base.periodico.is_empty() && !outro.periodico.is_empty() {
        base.periodico = outro.periodico.clone();
    }
    if base.doi.is_empty() && !outro.doi.is_empty() {
        base.doi = outro.doi.clone();
    }
    if base.tipo.is_empty() && !outro.tipo.is_empty() {
        base.tipo = outro.tipo.clone();
    }
    if base.resumo.is_empty() && !outro.resumo.is_empty() {
        base.resumo = outro.resumo.clone();
    }
    if n_chars(&outro.resumo) > n_chars(&base.resumo) {
        base.resumo = outro.resumo.clone();
    }
    if titulo_todo_maiusculo(&base.titulo) && !titulo_todo_maiusculo(&outro.titulo) {
        base.titulo = outro.titulo.clone();
    }
    base.citacoes = match (base.citacoes, outro.citacoes) {
        (None, o) => o,
        (b, None) => b,
        (Some(b), Some(o)) => Some(b.max(o)),
    };
    macro_rules! se_vazia {
        ($c:ident) => {
            if base.$c.is_empty() {
                base.$c = outro.$c.clone();
            }
        };
    }
    se_vazia!(autores);
    se_vazia!(autores_completos);
    se_vazia!(afiliacoes);
    se_vazia!(paises);
    se_vazia!(palavras_autor);
    se_vazia!(palavras_fonte);
    macro_rules! mescla {
        ($c:ident) => {{
            let mut vistos: std::collections::HashSet<String> = base.$c.iter().map(|t| t.to_lowercase()).collect();
            for t in &outro.$c {
                if !vistos.contains(&t.to_lowercase()) {
                    base.$c.push(t.clone());
                    vistos.insert(t.to_lowercase());
                }
            }
        }};
    }
    mescla!(palavras_autor);
    mescla!(palavras_fonte);
    if base.referencias.is_empty() && !outro.referencias.is_empty() {
        base.referencias = outro.referencias.clone();
        base.referencias_brutas = outro.referencias_brutas.clone();
        base.referencias_convertidas = outro.referencias_convertidas;
    }
    for (k, v) in &outro.metadados {
        base.metadados.entry(k.clone()).or_insert_with(|| v.clone());
    }
    base
}

/// Junta registros repetidos (mesmo DOI ou mesmo título e ano).
pub fn remove_duplicatas(documentos: Vec<DocumentoFonte>) -> (Vec<DocumentoFonte>, Vec<(String, String)>) {
    let mut indice: std::collections::HashMap<String, usize> = Default::default();
    let mut resultado: Vec<DocumentoFonte> = vec![];
    let mut removidos = vec![];
    for documento in documentos {
        let mut chaves: Vec<(&str, String)> = vec![];
        let doi = chave_doi(&documento.doi);
        if !doi.is_empty() {
            chaves.push(("doi", format!("doi:{doi}")));
        }
        let titulo = chave_titulo(&documento.titulo, &documento.ano);
        if !titulo.is_empty() {
            chaves.push(("título e ano", format!("titulo:{titulo}")));
        }
        let mut posicao = None;
        let mut motivo = "";
        for (rotulo, chave) in &chaves {
            if let Some(&p) = indice.get(chave) {
                posicao = Some(p);
                motivo = rotulo;
                break;
            }
        }
        let pos = match posicao {
            None => {
                resultado.push(documento);
                resultado.len() - 1
            }
            Some(p) => {
                let titulo_removido = documento.titulo.clone();
                if completude(&documento) > completude(&resultado[p]) {
                    let existente = resultado[p].clone();
                    resultado[p] = une(documento, &existente);
                } else {
                    let existente = std::mem::take(&mut resultado[p]);
                    resultado[p] = une(existente, &documento);
                }
                removidos.push((titulo_removido, motivo.to_string()));
                p
            }
        };
        for (_, chave) in chaves {
            indice.entry(chave).or_insert(pos);
        }
    }
    (resultado, removidos)
}

// ------------------------------------------------------------ texto utilitário

fn acento_latex(m: char) -> Option<char> {
    Some(match m {
        '\'' => '\u{301}',
        '`' => '\u{300}',
        '^' => '\u{302}',
        '~' => '\u{303}',
        '"' => '\u{308}',
        '=' => '\u{304}',
        '.' => '\u{307}',
        'c' => '\u{327}',
        'v' => '\u{30c}',
        'u' => '\u{306}',
        'H' => '\u{30b}',
        'k' => '\u{328}',
        'r' => '\u{30a}',
        _ => return None,
    })
}

fn letra_latex(s: &str) -> &'static str {
    match s {
        "ss" => "ß",
        "o" => "ø",
        "O" => "Ø",
        "aa" => "å",
        "AA" => "Å",
        "ae" => "æ",
        "AE" => "Æ",
        "oe" => "œ",
        "OE" => "Œ",
        "l" => "ł",
        "L" => "Ł",
        _ => "",
    }
}

/// Converte acentos LaTeX do BibTeX em Unicode.
pub fn decodifica_latex(texto: &str) -> String {
    if texto.is_empty() || (!texto.contains('\\') && !texto.contains('{')) {
        return texto.to_string();
    }
    let re = rx!(r#"\\(['`^~"=.])\s*(?:\{\s*(\\?[A-Za-z])\s*\}|(\\?[A-Za-z]))|\\([cvuHkr])(?:\s*\{\s*([A-Za-z])\s*\}|\s+([A-Za-z]))"#);
    let mut saida = String::new();
    let mut ult = 0;
    for c in re.captures_iter(texto).flatten() {
        let tudo = c.get(0).unwrap();
        saida.push_str(&texto[ult..tudo.start()]);
        ult = tudo.end();
        let marca = c.get(1).or(c.get(4)).unwrap().as_str().chars().next().unwrap();
        let letra = c.get(2).or(c.get(3)).or(c.get(5)).or(c.get(6)).unwrap().as_str();
        let letra = letra.strip_prefix('\\').unwrap_or(letra);
        let s: String = format!("{}{}", letra, acento_latex(marca).unwrap()).nfc().collect();
        saida.push_str(&s);
    }
    saida.push_str(&texto[ult..]);
    let mut t = String::new();
    let mut ult = 0;
    for c in rx!(r"\\(ss|aa|AA|ae|AE|oe|OE|o|O|l|L)(?![A-Za-z])\s?").captures_iter(&saida).flatten() {
        let tudo = c.get(0).unwrap();
        t.push_str(&saida[ult..tudo.start()]);
        t.push_str(letra_latex(c.get(1).unwrap().as_str()));
        ult = tudo.end();
    }
    t.push_str(&saida[ult..]);
    let t = rx!(r"\\([&%$#_{}])").replace_all(&t, "$1").to_string();
    t.replace(['{', '}'], "").nfc().collect()
}

/// Contagem de citações escrita em notas ("Cited By: 12").
pub fn citacoes_em_texto(textos: &[&str]) -> i64 {
    let re = rx!(r"(?i)(?:cited\s+by|citations?|times\s+cited|citado\s+por|citas?)\s*[:=]?\s*(\d+)");
    for t in textos {
        if let Ok(Some(c)) = re.captures(t) {
            return c.get(1).unwrap().as_str().parse().unwrap_or(0);
        }
    }
    0
}

pub fn acha_doi(textos: &[&str]) -> String {
    for t in textos {
        if let Ok(Some(m)) = rx!(r#"10\.\d{4,9}/[^\s"<>]+"#).find(t) {
            return m.as_str().trim_end_matches(['.', ',', ';', ')']).to_string();
        }
    }
    String::new()
}

/// Palavras-chave separadas por `;` (ou `|`), sem itens vazios.
pub fn divide_termos(valor: &str) -> Vec<String> {
    valor.split([';', '|']).map(strip).filter(|t| !t.is_empty()).map(String::from).collect()
}
