//! Utilitários que reproduzem comportamentos do Python (`str.strip`, `splitlines`,
//! `round`, `html.unescape`) e as normalizações de `text_utils.py`.


use unicode_normalization::char::canonical_combining_class;
use unicode_normalization::UnicodeNormalization;

/// Regex compilada uma vez. Uso: `rx!(r"...")`.
#[macro_export]
macro_rules! rx {
    ($p:expr) => {{
        static R: std::sync::OnceLock<fancy_regex::Regex> = std::sync::OnceLock::new();
        R.get_or_init(|| fancy_regex::Regex::new($p).expect("regex inválida"))
    }};
}

pub fn e_espaco(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// `str.strip()` do Python.
pub fn strip(s: &str) -> &str {
    s.trim_matches(e_espaco)
}

pub fn strip_chars<'a>(s: &'a str, cs: &str) -> &'a str {
    s.trim_matches(|c| cs.contains(c))
}

/// `str.splitlines()` do Python.
pub fn splitlines(s: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut ini = 0;
    let b = s.as_bytes();
    let mut it = s.char_indices().peekable();
    while let Some((i, c)) = it.next() {
        let quebra = matches!(c, '\n' | '\r' | '\u{b}' | '\u{c}' | '\u{1c}' | '\u{1d}' | '\u{1e}' | '\u{85}' | '\u{2028}' | '\u{2029}');
        if quebra {
            out.push(&s[ini..i]);
            let mut fim = i + c.len_utf8();
            if c == '\r' && b.get(fim) == Some(&b'\n') {
                fim += 1;
                it.next();
            }
            ini = fim;
        }
    }
    if ini < s.len() {
        out.push(&s[ini..]);
    }
    out
}

/// `str.split(None)`: separa por espaços em branco.
pub fn palavras(s: &str) -> Vec<&str> {
    s.split(e_espaco).filter(|p| !p.is_empty()).collect()
}

pub fn eh_maiuscula(s: &str) -> bool {
    let mut tem = false;
    for c in s.chars() {
        if c.is_lowercase() {
            return false;
        }
        if c.is_uppercase() {
            tem = true;
        }
    }
    tem
}

pub fn eh_digito(c: char) -> bool {
    c.is_ascii_digit() || (c as u32 > 127 && c.is_numeric() && c.to_digit(10).is_some())
}

pub fn primeira_maiuscula(s: &str) -> bool {
    s.chars().next().map_or(false, |c| c.is_uppercase())
}

pub fn primeira_minuscula(s: &str) -> bool {
    s.chars().next().map_or(false, |c| c.is_lowercase())
}

pub fn primeiro_digito(s: &str) -> bool {
    s.chars().next().map_or(false, eh_digito)
}

pub fn n_chars(s: &str) -> usize {
    s.chars().count()
}

/// `round()` do Python 3 (arredonda metades para o par).
pub fn py_round(x: f64) -> i64 {
    let r = x.round();
    if (x - x.trunc()).abs() == 0.5 {
        let t = x.trunc() as i64;
        if t % 2 == 0 {
            t
        } else {
            t + if x > 0.0 { 1 } else { -1 }
        }
    } else {
        r as i64
    }
}

/// Decodifica bytes como o Python tentaria: UTF-8 (com ou sem BOM), UTF-16 com BOM, senão latin-1.
pub fn decodifica(dados: &[u8]) -> String {
    if dados.starts_with(&[0xFF, 0xFE]) || dados.starts_with(&[0xFE, 0xFF]) {
        let le = dados[0] == 0xFF;
        let u: Vec<u16> = dados[2..]
            .chunks(2)
            .filter(|c| c.len() == 2)
            .map(|c| if le { u16::from_le_bytes([c[0], c[1]]) } else { u16::from_be_bytes([c[0], c[1]]) })
            .collect();
        return String::from_utf16_lossy(&u);
    }
    match std::str::from_utf8(dados) {
        Ok(s) => s.strip_prefix('\u{feff}').unwrap_or(s).to_string(),
        Err(_) => dados.iter().map(|&b| b as char).collect(),
    }
}

// ------------------------------------------------------------ html.unescape

const ENTIDADES: &[(&str, &str)] = &[
    ("amp", "&"), ("lt", "<"), ("gt", ">"), ("quot", "\""), ("apos", "'"), ("nbsp", "\u{a0}"),
    ("iexcl", "¡"), ("cent", "¢"), ("pound", "£"), ("curren", "¤"), ("yen", "¥"), ("brvbar", "¦"),
    ("sect", "§"), ("uml", "¨"), ("copy", "©"), ("ordf", "ª"), ("laquo", "«"), ("not", "¬"),
    ("shy", "\u{ad}"), ("reg", "®"), ("macr", "¯"), ("deg", "°"), ("plusmn", "±"), ("sup2", "²"),
    ("sup3", "³"), ("acute", "´"), ("micro", "µ"), ("para", "¶"), ("middot", "·"), ("cedil", "¸"),
    ("sup1", "¹"), ("ordm", "º"), ("raquo", "»"), ("frac14", "¼"), ("frac12", "½"), ("frac34", "¾"),
    ("iquest", "¿"), ("Agrave", "À"), ("Aacute", "Á"), ("Acirc", "Â"), ("Atilde", "Ã"), ("Auml", "Ä"),
    ("Aring", "Å"), ("AElig", "Æ"), ("Ccedil", "Ç"), ("Egrave", "È"), ("Eacute", "É"), ("Ecirc", "Ê"),
    ("Euml", "Ë"), ("Igrave", "Ì"), ("Iacute", "Í"), ("Icirc", "Î"), ("Iuml", "Ï"), ("ETH", "Ð"),
    ("Ntilde", "Ñ"), ("Ograve", "Ò"), ("Oacute", "Ó"), ("Ocirc", "Ô"), ("Otilde", "Õ"), ("Ouml", "Ö"),
    ("times", "×"), ("Oslash", "Ø"), ("Ugrave", "Ù"), ("Uacute", "Ú"), ("Ucirc", "Û"), ("Uuml", "Ü"),
    ("Yacute", "Ý"), ("THORN", "Þ"), ("szlig", "ß"), ("agrave", "à"), ("aacute", "á"), ("acirc", "â"),
    ("atilde", "ã"), ("auml", "ä"), ("aring", "å"), ("aelig", "æ"), ("ccedil", "ç"), ("egrave", "è"),
    ("eacute", "é"), ("ecirc", "ê"), ("euml", "ë"), ("igrave", "ì"), ("iacute", "í"), ("icirc", "î"),
    ("iuml", "ï"), ("eth", "ð"), ("ntilde", "ñ"), ("ograve", "ò"), ("oacute", "ó"), ("ocirc", "ô"),
    ("otilde", "õ"), ("ouml", "ö"), ("divide", "÷"), ("oslash", "ø"), ("ugrave", "ù"), ("uacute", "ú"),
    ("ucirc", "û"), ("uuml", "ü"), ("yacute", "ý"), ("thorn", "þ"), ("yuml", "ÿ"), ("OElig", "Œ"),
    ("oelig", "œ"), ("Scaron", "Š"), ("scaron", "š"), ("Yuml", "Ÿ"), ("fnof", "ƒ"), ("circ", "ˆ"),
    ("tilde", "˜"), ("ensp", "\u{2002}"), ("emsp", "\u{2003}"), ("thinsp", "\u{2009}"), ("ndash", "–"),
    ("mdash", "—"), ("lsquo", "‘"), ("rsquo", "’"), ("sbquo", "‚"), ("ldquo", "“"), ("rdquo", "”"),
    ("bdquo", "„"), ("dagger", "†"), ("Dagger", "‡"), ("bull", "•"), ("hellip", "…"), ("permil", "‰"),
    ("prime", "′"), ("Prime", "″"), ("lsaquo", "‹"), ("rsaquo", "›"), ("euro", "€"), ("trade", "™"),
    ("alpha", "α"), ("beta", "β"), ("gamma", "γ"), ("delta", "δ"), ("epsilon", "ε"), ("mu", "μ"),
    ("pi", "π"), ("sigma", "σ"), ("chi", "χ"), ("lambda", "λ"), ("theta", "θ"), ("rho", "ρ"),
    ("tau", "τ"), ("phi", "φ"), ("omega", "ω"), ("Delta", "Δ"), ("Sigma", "Σ"), ("Omega", "Ω"),
    ("le", "≤"), ("ge", "≥"), ("ne", "≠"), ("infin", "∞"), ("minus", "−"), ("larr", "←"), ("rarr", "→"),
];

const CP1252: [char; 32] = [
    '\u{20ac}', '\u{81}', '\u{201a}', '\u{192}', '\u{201e}', '\u{2026}', '\u{2020}', '\u{2021}', '\u{2c6}', '\u{2030}',
    '\u{160}', '\u{2039}', '\u{152}', '\u{8d}', '\u{17d}', '\u{8f}', '\u{90}', '\u{2018}', '\u{2019}', '\u{201c}',
    '\u{201d}', '\u{2022}', '\u{2013}', '\u{2014}', '\u{2dc}', '\u{2122}', '\u{161}', '\u{203a}', '\u{153}', '\u{9d}',
    '\u{17e}', '\u{178}',
];

/// `html.unescape` (entidades numéricas e as nomeadas mais comuns, com `;`).
pub fn html_unescape(s: &str) -> String {
    if !s.contains('&') {
        return s.to_string();
    }
    let re = rx!(r"&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)");
    let mut out = String::with_capacity(s.len());
    let mut ult = 0;
    for m in re.captures_iter(s).flatten() {
        let tudo = m.get(0).unwrap();
        out.push_str(&s[ult..tudo.start()]);
        ult = tudo.end();
        let g = m.get(1).unwrap().as_str();
        let rep: Option<String> = if let Some(num) = g.strip_prefix('#') {
            let num = num.trim_end_matches(';');
            let cp = if let Some(h) = num.strip_prefix(['x', 'X']) { u32::from_str_radix(h, 16).ok() } else { num.parse::<u32>().ok() };
            match cp {
                Some(c) if (0x80..=0x9f).contains(&c) => Some(CP1252[(c - 0x80) as usize].to_string()),
                Some(0) => Some("\u{fffd}".into()),
                Some(c) => Some(char::from_u32(c).filter(|ch| !(0xd800..=0xdfff).contains(&(*ch as u32))).unwrap_or('\u{fffd}').to_string()),
                None => Some("\u{fffd}".into()),
            }
        } else if let Some(nome) = g.strip_suffix(';') {
            ENTIDADES.iter().find(|(n, _)| *n == nome).map(|(_, v)| v.to_string())
        } else {
            None
        };
        match rep {
            Some(r) => out.push_str(&r),
            None => out.push_str(tudo.as_str()),
        }
    }
    out.push_str(&s[ult..]);
    out
}

// ------------------------------------------------------------ text_utils.py

pub fn combina(c: char) -> bool {
    canonical_combining_class(c) != 0
}

pub fn sem_acentos(texto: &str) -> String {
    texto.nfd().filter(|c| !combina(*c)).collect()
}

/// Chave de comparação: caixa, acento, pontuação e espaço não contam.
pub fn chave(nome: &str) -> String {
    sem_acentos(nome).to_lowercase().replace('&', "and").chars().filter(|c| c.is_ascii_lowercase() || c.is_ascii_digit()).collect()
}

fn tipografia(c: char) -> char {
    match c {
        '\u{2019}' | '\u{2018}' | '\u{2bc}' | '\u{b4}' | '`' | '\u{2032}' | '\u{201b}' => '\'',
        '\u{2010}' | '\u{2011}' | '\u{2012}' | '\u{2013}' | '\u{2014}' | '\u{2212}' => '-',
        c => c,
    }
}

/// Uniformiza apóstrofo, travessão e espaços.
pub fn limpa_termo(nome: &str) -> String {
    let t: String = nome.nfc().map(tipografia).collect();
    let mut out = String::with_capacity(t.len());
    let mut espaco = false;
    for c in strip(&t).chars() {
        if e_espaco(c) {
            espaco = true;
        } else {
            if espaco {
                out.push(' ');
                espaco = false;
            }
            out.push(c);
        }
    }
    out
}

/// Forma guardada pelo importador: maiúsculas e hífen no lugar do espaço.
pub fn normaliza_palavra(nome: &str) -> String {
    limpa_termo(nome).to_uppercase().replace(' ', "-")
}

pub fn partes_abreviadas(nome: &str) -> Vec<String> {
    let palavras = palavras(strip(nome));
    if palavras.len() < 2 {
        return vec![];
    }
    let mut partes = vec![];
    for p in palavras {
        if !p.ends_with('.') || p == "." {
            return vec![];
        }
        let limpa = strip(&sem_acentos(&p[..p.len() - 1]).to_lowercase()).to_string();
        if limpa.is_empty() {
            return vec![];
        }
        partes.push(limpa);
    }
    partes
}

pub fn parece_abreviacao(nome: &str) -> bool {
    !partes_abreviadas(nome).is_empty()
}

const LIGACOES: &[&str] = &["of", "the", "and", "for", "in", "on", "a", "an", "to", "with", "from", "by", "at", "as", "de", "da", "do", "das", "dos", "e", "y"];

pub fn palavras_significativas(nome: &str) -> Vec<String> {
    sem_acentos(nome)
        .to_lowercase()
        .split(|c: char| !(c.is_ascii_lowercase() || c.is_ascii_digit()))
        .filter(|p| !p.is_empty() && !LIGACOES.contains(p))
        .map(String::from)
        .collect()
}

pub fn abreviacao_de(partes: &[String], alvo: &[String]) -> bool {
    !partes.is_empty() && partes.len() == alvo.len() && partes.iter().zip(alvo).all(|(p, c)| !p.is_empty() && c.starts_with(p.as_str()))
}

pub fn mesmo_plural(a: &str, b: &str) -> bool {
    let um = |a: &str, b: &str| {
        b == format!("{a}S") || b == format!("{a}ES") || (a.ends_with('Y') && b == format!("{}IES", &a[..a.len() - 1]))
            || b == format!("{a}s") || b == format!("{a}es") || (a.ends_with('y') && b == format!("{}ies", &a[..a.len() - 1]))
    };
    um(a, b) || um(b, a)
}

const SUFIXOS_IRREGULARES: &[(&str, &str)] = &[("AO", "OES"), ("AO", "AES"), ("AO", "AOS"), ("M", "NS"), ("AL", "AIS"), ("EL", "EIS"), ("OL", "OIS"), ("UL", "UIS"), ("Z", "CES"), ("IS", "ES")];

fn plural_irregular(singular: &str, plural: &str) -> bool {
    if n_chars(singular) < 5 {
        return false;
    }
    SUFIXOS_IRREGULARES.iter().any(|(fs, fp)| singular.ends_with(fs) && plural.ends_with(fp) && singular[..singular.len() - fs.len()] == plural[..plural.len() - fp.len()])
}

fn mesmo_plural_token(a: &str, b: &str) -> bool {
    a == b || mesmo_plural(a, b) || plural_irregular(a, b) || plural_irregular(b, a)
}

pub fn mesmo_termo(a: &str, b: &str) -> bool {
    if a == b {
        return false;
    }
    if mesmo_plural(a, b) {
        return true;
    }
    let sa = sem_acentos(a).to_uppercase();
    let sb = sem_acentos(b).to_uppercase();
    if sa == sb {
        return true;
    }
    let ta: Vec<&str> = sa.split('-').collect();
    let tb: Vec<&str> = sb.split('-').collect();
    ta.len() == tb.len() && ta.iter().zip(&tb).all(|(x, y)| mesmo_plural_token(x, y))
}

pub fn chave_de_bloco(nome: &str) -> String {
    let sem = sem_acentos(nome).to_uppercase();
    let primeira: String = sem.chars().take(1).collect();
    format!("{}{}", sem.matches('-').count(), primeira)
}

