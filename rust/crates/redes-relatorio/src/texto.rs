//! Formatação de texto e números em português, e a tabela HTML.

use std::time::{SystemTime, UNIX_EPOCH};

/// `html.escape` do Python (com aspas).
pub fn esc(s: &str) -> String {
    let mut o = String::with_capacity(s.len() + 8);
    for c in s.chars() {
        match c {
            '&' => o.push_str("&amp;"),
            '<' => o.push_str("&lt;"),
            '>' => o.push_str("&gt;"),
            '"' => o.push_str("&quot;"),
            '\'' => o.push_str("&#x27;"),
            _ => o.push(c),
        }
    }
    o
}

/// `report._numero`: inteiro sem casas, senão duas casas sem zeros à direita (ponto).
pub fn numero(v: f64) -> String {
    if (v - v.round()).abs() < 1e-9 {
        return format!("{}", v.round() as i64);
    }
    let s = format!("{:.2}", v);
    s.trim_end_matches('0').trim_end_matches('.').to_string()
}

/// `relatorio_unico._n`: como `numero`, com vírgula.
pub fn n(v: f64) -> String {
    numero(v).replace('.', ",")
}

/// Inteiro com ponto de milhar.
pub fn inteiro(v: usize) -> String {
    let s = v.to_string();
    let b = s.as_bytes();
    let mut o = String::new();
    for (i, c) in b.iter().enumerate() {
        if i > 0 && (b.len() - i) % 3 == 0 {
            o.push('.');
        }
        o.push(*c as char);
    }
    o
}

/// `metodo._decimal`.
pub fn decimal(v: f64) -> String {
    if (v - v.round()).abs() < 1e-9 {
        return format!("{}", v.round() as i64);
    }
    let s = format!("{:.2}", v);
    s.trim_end_matches('0').trim_end_matches('.').replace('.', ",")
}

pub fn plural<'a>(n: usize, singular: &'a str, plural: &'a str) -> &'a str {
    if n == 1 {
        singular
    } else {
        plural
    }
}

/// `metodo._n2`: "—" sem valor.
pub fn n2(v: Option<f64>, casas: usize) -> String {
    match v {
        None => "—".into(),
        Some(x) => format!("{:.*}", casas, x).replace('.', ","),
    }
}

/// `metodo._n4`.
pub fn n4(v: Option<f64>) -> String {
    n2(v, 4)
}

/// `f"{x:.0%}"` do Python (arredonda para o par, sobre o valor binário).
pub fn pct0(x: f64) -> String {
    format!("{:.0}%", x * 100.0)
}

const MESES: [&str; 12] = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
    "dezembro",
];

/// Data de hoje (UTC) por extenso: "19 de novembro de 2026".
pub fn hoje_extenso() -> String {
    let dias = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| (d.as_secs() / 86_400) as i64).unwrap_or(0);
    let (a, m, d) = civil_de_dias(dias);
    format!("{} de {} de {}", d, MESES[(m - 1) as usize], a)
}

/// Dias desde 1970-01-01 para (ano, mês, dia) (algoritmo de Howard Hinnant).
fn civil_de_dias(z: i64) -> (i64, i64, i64) {
    let z = z + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// Texto sem acentos, para nomes de arquivo e âncoras.
pub fn slug(t: &str) -> String {
    let mut o = String::new();
    let mut ultimo_hifen = true;
    for c in t.chars() {
        let c = desacentua(c);
        if c.is_ascii_alphanumeric() {
            o.push(c);
            ultimo_hifen = false;
        } else if !ultimo_hifen {
            o.push('-');
            ultimo_hifen = true;
        }
    }
    let o = o.trim_matches('-').to_string();
    if o.is_empty() {
        "item".into()
    } else {
        o
    }
}

fn desacentua(c: char) -> char {
    match c {
        'á' | 'à' | 'â' | 'ã' | 'ä' => 'a',
        'Á' | 'À' | 'Â' | 'Ã' | 'Ä' => 'A',
        'é' | 'è' | 'ê' | 'ë' => 'e',
        'É' | 'È' | 'Ê' | 'Ë' => 'E',
        'í' | 'ì' | 'î' | 'ï' => 'i',
        'Í' | 'Ì' | 'Î' | 'Ï' => 'I',
        'ó' | 'ò' | 'ô' | 'õ' | 'ö' => 'o',
        'Ó' | 'Ò' | 'Ô' | 'Õ' | 'Ö' => 'O',
        'ú' | 'ù' | 'û' | 'ü' => 'u',
        'Ú' | 'Ù' | 'Û' | 'Ü' => 'U',
        'ç' => 'c',
        'Ç' => 'C',
        'ñ' => 'n',
        'Ñ' => 'N',
        _ => c,
    }
}

/// Primeira letra maiúscula (`texto[:1].upper() + texto[1:]`).
pub fn inicial_maiuscula(t: &str) -> String {
    let mut it = t.chars();
    match it.next() {
        Some(c) => c.to_uppercase().collect::<String>() + it.as_str(),
        None => String::new(),
    }
}

/// Corta em `limite` caracteres, com reticências (`t[:limite-1] + "…"`).
pub fn corta(t: &str, limite: usize) -> String {
    if t.chars().count() <= limite {
        t.to_string()
    } else {
        t.chars().take(limite.saturating_sub(1)).collect::<String>() + "…"
    }
}

/// Quebra e junta espaços (`" ".join(t.split())`).
pub fn normaliza_espacos(t: &str) -> String {
    t.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// `report._tabela`: HTML de uma tabela. `linhas` já vêm em HTML.
pub fn tabela_html(cabecalho: &[String], linhas: &[Vec<String>], legenda: Option<&str>, numericas: &[usize], larguras: &[&str]) -> String {
    let mut p: Vec<String> = vec!["<table>".into()];
    if !larguras.is_empty() {
        p.push(format!(
            "<colgroup>{}</colgroup>",
            larguras.iter().map(|l| format!("<col style=\"width:{l}\">")).collect::<String>()
        ));
    }
    if let Some(l) = legenda {
        if !l.is_empty() {
            p.push(format!("<caption>{}</caption>", esc(l)));
        }
    }
    p.push(format!(
        "<thead><tr>{}</tr></thead><tbody>",
        cabecalho.iter().map(|c| format!("<th>{}</th>", esc(c))).collect::<String>()
    ));
    for linha in linhas {
        let cel: String = linha
            .iter()
            .enumerate()
            .map(|(i, c)| {
                let cl = if numericas.contains(&i) { " class=\"num\"" } else { "" };
                format!("<td{cl}>{c}</td>")
            })
            .collect();
        p.push(format!("<tr>{cel}</tr>"));
    }
    p.push("</tbody></table>".into());
    p.join("\n")
}

/// Numeração de tabelas: cada relatório aplica a sua.
pub trait Numerador {
    /// Devolve o HTML da tabela, com a legenda no formato do relatório.
    fn tabela(&mut self, cabecalho: &[String], linhas: &[Vec<String>], legenda: &str, numericas: &[usize], larga: bool) -> String;
}

/// Sem numeração (legenda como veio).
pub struct SemNumero;

impl Numerador for SemNumero {
    fn tabela(&mut self, cabecalho: &[String], linhas: &[Vec<String>], legenda: &str, numericas: &[usize], _larga: bool) -> String {
        tabela_html(cabecalho, linhas, Some(legenda), numericas, &[])
    }
}

/// "Tabela N — legenda", contador simples (páginas da pasta).
#[derive(Default)]
pub struct Contador {
    pub n: usize,
}

impl Numerador for Contador {
    fn tabela(&mut self, cabecalho: &[String], linhas: &[Vec<String>], legenda: &str, numericas: &[usize], larga: bool) -> String {
        self.n += 1;
        let l = if legenda.is_empty() { format!("Tabela {}", self.n) } else { format!("Tabela {} — {}", self.n, legenda) };
        let t = tabela_html(cabecalho, linhas, Some(&l), numericas, &[]);
        if larga {
            format!("<div class=\"rolagem\">{t}</div>")
        } else {
            t
        }
    }
}

pub fn strings(v: &[&str]) -> Vec<String> {
    v.iter().map(|s| s.to_string()).collect()
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn formatos() {
        assert_eq!(numero(12.0), "12");
        assert_eq!(numero(15.2), "15.2");
        assert_eq!(numero(17.234), "17.23");
        assert_eq!(n(10.125), "10,12");
        assert_eq!(inteiro(1234567), "1.234.567");
        assert_eq!(inteiro(12), "12");
        assert_eq!(decimal(0.6), "0,6");
        assert_eq!(esc("a<b>&'\""), "a&lt;b&gt;&amp;&#x27;&quot;");
        assert_eq!(slug("Colaboração entre países"), "Colaboracao-entre-paises");
    }

    #[test]
    fn data() {
        assert_eq!(civil_de_dias(0), (1970, 1, 1));
        assert_eq!(civil_de_dias(20_411), (2025, 11, 19));
    }

    #[test]
    fn tabela_basica() {
        let t = tabela_html(&strings(&["A", "B"]), &[vec!["1".into(), "2".into()]], Some("Leg"), &[1], &[]);
        assert!(t.contains("<caption>Leg</caption>"));
        assert!(t.contains("<td class=\"num\">2</td>"));
    }
}
