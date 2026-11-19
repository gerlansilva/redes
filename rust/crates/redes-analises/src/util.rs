//! Utilidades comuns: texto, escape, largura de rótulo, formatação à moda do Python e paletas.

use unicode_normalization::char::is_combining_mark;
use unicode_normalization::UnicodeNormalization;

pub const TINTA: &str = "#14204A";
pub const TINTA_FRACA: &str = "#64748B";
pub const FONTE_INTER: &str = "Inter, Arial, sans-serif";

pub const PALETA_GRUPOS: [&str; 15] = [
    "#2F2BFF", "#00A344", "#6A3BFF", "#B45309", "#0B1F66", "#0E7490", "#8B5CF6", "#4D7C0F", "#9D174D", "#0369A1",
    "#A16207", "#7C3AED", "#0F766E", "#BE185D", "#DC2626",
];

/// Cor do agrupamento (`viz.halo.cor_do_grupo`): paleta fixa e, depois, ângulo áureo.
pub fn cor_do_grupo(posicao: usize) -> String {
    if posicao < PALETA_GRUPOS.len() {
        return PALETA_GRUPOS[posicao].to_string();
    }
    let extra = posicao - PALETA_GRUPOS.len();
    let matiz = (extra as f64 * 137.508 + 20.0) % 360.0;
    let luz = [0.40, 0.50, 0.33][extra % 3];
    let sat = [0.62, 0.55, 0.70][extra % 3];
    let c = (1.0 - (2.0_f64 * luz - 1.0).abs()) * sat;
    let x = c * (1.0 - ((matiz / 60.0) % 2.0 - 1.0).abs());
    let m = luz - c / 2.0;
    let (r, g, b) = match ((matiz / 60.0).floor() as i64).rem_euclid(6) {
        0 => (c, x, 0.0),
        1 => (x, c, 0.0),
        2 => (0.0, c, x),
        3 => (0.0, x, c),
        4 => (x, 0.0, c),
        _ => (c, 0.0, x),
    };
    let t = |v: f64| py_round_int((v + m) * 255.0);
    format!("#{:02X}{:02X}{:02X}", t(r), t(g), t(b))
}

/// `round(x)` do Python (empate para o par).
pub fn py_round_int(x: f64) -> i64 {
    x.round_ties_even() as i64
}

/// `round(x, n)` do Python (arredonda o valor binário exato, empate para o par).
pub fn py_round(x: f64, n: usize) -> f64 {
    if !x.is_finite() {
        return x;
    }
    format!("{:.*}", n, x).parse().unwrap_or(x)
}

/// `f"{x:g}"` do Python (seis algarismos significativos).
pub fn fmt_g(x: f64) -> String {
    fmt_g_prec(x, 6)
}

pub fn fmt_g_prec(x: f64, prec: usize) -> String {
    if x == 0.0 {
        return if x.is_sign_negative() { "-0".into() } else { "0".into() };
    }
    if !x.is_finite() {
        return if x.is_nan() { "nan".into() } else if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let p = prec.max(1);
    let e = format!("{:.*e}", p - 1, x);
    let (mant, exp) = e.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    if exp < -4 || exp >= p as i32 {
        let mut m = mant.to_string();
        if m.contains('.') {
            m = m.trim_end_matches('0').trim_end_matches('.').to_string();
        }
        format!("{}e{}{:02}", m, if exp < 0 { '-' } else { '+' }, exp.abs())
    } else {
        let dec = (p as i32 - 1 - exp).max(0) as usize;
        let mut s = format!("{:.*}", dec, x);
        if s.contains('.') {
            s = s.trim_end_matches('0').trim_end_matches('.').to_string();
        }
        s
    }
}

/// Controles e marcas bidirecionais que a limpeza de texto de uma linha remove.
pub fn e_controle(c: char) -> bool {
    let n = c as u32;
    n <= 0x1f
        || (0x7f..=0x9f).contains(&n)
        || n == 0x200e
        || n == 0x200f
        || (0x202a..=0x202e).contains(&n)
        || (0x2066..=0x2069).contains(&n)
        || n == 0xfeff
        || n == 0xfffe
        || n == 0xffff
}

/// Texto de uma linha, sem controles nem marcas bidirecionais (`limpa`).
pub fn limpa(texto: &str) -> String {
    let t: String = texto.chars().map(|c| if e_controle(c) { ' ' } else { c }).collect();
    t.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Controles que o escape de SVG descarta (`_CONTROLE` do Python).
fn e_controle_svg(c: char) -> bool {
    let n = c as u32;
    matches!(n, 0..=8 | 0x0b | 0x0c | 0x0e..=0x1f | 0xfffe | 0xffff)
}

/// `html.escape(texto, quote=True)` depois de remover controles.
pub fn esc(texto: &str) -> String {
    let mut s = String::with_capacity(texto.len());
    for c in texto.chars() {
        if e_controle_svg(c) {
            continue;
        }
        match c {
            '&' => s.push_str("&amp;"),
            '<' => s.push_str("&lt;"),
            '>' => s.push_str("&gt;"),
            '"' => s.push_str("&quot;"),
            '\'' => s.push_str("&#x27;"),
            _ => s.push(c),
        }
    }
    s
}

/// `esc(limpa(texto))`.
pub fn esc_limpo(texto: &str) -> String {
    esc(&limpa(texto))
}

/// Sem acentos: decomposição NFD sem marcas combinantes.
pub fn sem_acentos(t: &str) -> String {
    t.nfd().filter(|c| !is_combining_mark(*c)).collect()
}

/// Corta em `limite` caracteres com reticências (`_curto`).
pub fn curto(texto: &str, limite: usize) -> String {
    let n = texto.chars().count();
    if n <= limite {
        texto.to_string()
    } else {
        let t: String = texto.chars().take(limite - 1).collect();
        format!("{}…", t.trim_end())
    }
}

fn largo_oriental(c: char) -> bool {
    let n = c as u32;
    (0x1100..=0x115f).contains(&n)
        || (0x2e80..=0xa4cf).contains(&n)
        || (0xac00..=0xd7a3).contains(&n)
        || (0xf900..=0xfaff).contains(&n)
        || (0xfe30..=0xfe6f).contains(&n)
        || (0xff00..=0xff60).contains(&n)
        || (0xffe0..=0xffe6).contains(&n)
        || (0x20000..=0x3fffd).contains(&n)
}

/// Largura aproximada, em px, de um caractere a 12 px (`linha_do_tempo._largura_caractere`).
pub fn largura_caractere(c: char) -> f64 {
    let cod = c as u32;
    if matches!(cod, 0x200d | 0xfe0f | 0xfe0e) || is_combining_mark(c) {
        return 0.0;
    }
    if c == ' ' {
        return 3.6;
    }
    if largo_oriental(c) || cod >= 0x1f000 || (0x2600..=0x27bf).contains(&cod) {
        return 14.0;
    }
    let estreito = |b: char| "il.,;:'!|¡`".contains(b);
    let meio = |b: char| "jtfrI()[]{}-–—/\\\"".contains(b);
    if c.is_alphabetic() {
        let base = c.to_string().nfd().next().unwrap_or(c);
        if estreito(base) {
            return 3.4;
        }
        if meio(base) {
            return 4.8;
        }
        if "mw".contains(base) {
            return 9.6;
        }
        if "MW".contains(base) {
            return 11.0;
        }
        return if base.is_uppercase() { 8.2 } else { 6.6 };
    }
    if c.is_numeric() {
        return 7.0;
    }
    if estreito(c) {
        return 3.4;
    }
    if meio(c) {
        return 4.8;
    }
    7.0
}

pub fn largura(texto: &str, tamanho: f64, negrito: bool) -> f64 {
    let total: f64 = texto.chars().map(largura_caractere).sum();
    total * tamanho / 12.0 * if negrito { 1.07 } else { 1.0 }
}

/// Texto reduzido com reticências até que `medida` caiba em `px`.
pub fn cabe_com(texto: &str, px: f64, medida: &dyn Fn(&str) -> f64) -> String {
    let mut t: Vec<char> = texto.chars().collect();
    let s: String = t.iter().collect();
    if medida(&s) <= px {
        return s;
    }
    while t.len() > 1 {
        let cand: String = format!("{}…", t.iter().collect::<String>().trim_end());
        if medida(&cand) <= px {
            break;
        }
        t.pop();
    }
    format!("{}…", t.iter().collect::<String>().trim_end())
}

/// Texto reduzido com … até caber em `px` (versão de `viz.linha_do_tempo._cabe`).
pub fn cabe(texto: &str, px: f64, tamanho: f64, negrito: bool) -> String {
    if largura(texto, tamanho, negrito) <= px {
        return texto.to_string();
    }
    let mut t: Vec<char> = texto.chars().collect();
    while !t.is_empty() {
        let s: String = t.iter().collect();
        if largura(&format!("{s}…"), tamanho, negrito) <= px {
            break;
        }
        t.pop();
    }
    format!("{}…", t.iter().collect::<String>().trim_end())
}

/// Quebra por palavras em até `linhas` linhas; a última recebe o … se sobrar.
pub fn quebra(texto: &str, px: f64, linhas: usize, tamanho: f64, negrito: bool) -> Vec<String> {
    let palavras: Vec<&str> = texto.split_whitespace().collect();
    let mut saida: Vec<String> = Vec::new();
    let mut atual = String::new();
    let mut i = 0;
    while i < palavras.len() && saida.len() < linhas {
        let tentativa = format!("{} {}", atual, palavras[i]).trim().to_string();
        if largura(&tentativa, tamanho, negrito) <= px || atual.is_empty() {
            atual = tentativa;
            i += 1;
        } else {
            saida.push(std::mem::take(&mut atual));
        }
    }
    if !atual.is_empty() && saida.len() < linhas {
        saida.push(atual);
    }
    if i < palavras.len() && !saida.is_empty() {
        let ult = saida.pop().unwrap();
        saida.push(cabe(&format!("{} {}", ult, palavras[i..].join(" ")), px, tamanho, negrito));
    }
    let r: Vec<String> = saida.iter().map(|s| cabe(s, px, tamanho, negrito)).collect();
    if r.is_empty() {
        vec![String::new()]
    } else {
        r
    }
}

/// Resumo hexadecimal de 8 dígitos para ids únicos (FNV-1a de 64 bits).
pub fn hash8(texto: &str) -> String {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in texto.as_bytes() {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    format!("{:08x}", (h ^ (h >> 32)) as u32)
}

/// Quebra de linha à moda de `textwrap.wrap` (palavras inteiras, largura em caracteres).
pub fn textwrap(texto: &str, largura: usize) -> Vec<String> {
    let mut linhas = Vec::new();
    let mut atual = String::new();
    for p in texto.split_whitespace() {
        let n = atual.chars().count();
        if n == 0 {
            atual = p.to_string();
        } else if n + 1 + p.chars().count() <= largura {
            atual.push(' ');
            atual.push_str(p);
        } else {
            linhas.push(std::mem::take(&mut atual));
            atual = p.to_string();
        }
    }
    if !atual.is_empty() {
        linhas.push(atual);
    }
    linhas
}

/// Gerador pseudoaleatório pequeno e determinístico (SplitMix64 + Box-Muller).
pub struct Aleatorio(pub u64);

impl Aleatorio {
    pub fn proximo(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e3779b97f4a7c15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d049bb133111eb);
        z ^ (z >> 31)
    }
    pub fn uniforme(&mut self) -> f64 {
        (self.proximo() >> 11) as f64 / (1u64 << 53) as f64
    }
    pub fn normal(&mut self) -> f64 {
        let u1 = self.uniforme().max(1e-300);
        let u2 = self.uniforme();
        (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn g_como_python() {
        assert_eq!(fmt_g(0.0001), "0.0001");
        assert_eq!(fmt_g(123456.0), "123456");
        assert_eq!(fmt_g(1234567.0), "1.23457e+06");
        assert_eq!(fmt_g(0.5), "0.5");
        assert_eq!(fmt_g(2.0), "2");
        assert_eq!(fmt_g(0.00001234), "1.234e-05");
    }

    #[test]
    fn cores_extras() {
        assert_eq!(cor_do_grupo(0), "#2F2BFF");
        assert_eq!(cor_do_grupo(15).len(), 7);
    }
}

/// `repr(float)` do Python para valores comuns (`450.0`, não `450`).
pub fn pyf(x: f64) -> String {
    if x.is_finite() && x == x.trunc() && x.abs() < 1e16 {
        format!("{:.1}", x)
    } else {
        format!("{}", x)
    }
}

/// `sum()` do CPython sobre floats (soma compensada de Neumaier, Python 3.12+).
pub fn soma_py<I: IntoIterator<Item = f64>>(v: I) -> f64 {
    redes_core::pycompat::py_sum(v)
}
