//! Figuras SVG do período: diagrama estratégico de Callon, rede completa em
//! halos e rede de um agrupamento (portas de `viz/strategic.py`, `viz/halo.py`
//! e `viz/cluster.py`). Determinísticas; sem dependências além da std.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::fmt::Write;

use crate::dados::*;
use crate::metodo::quadrante_chave;
use crate::texto::{corta, esc, inicial_maiuscula, normaliza_espacos};

pub const PALETA: [&str; 15] = [
    "#2F2BFF", "#00A344", "#6A3BFF", "#B45309", "#0B1F66", "#0E7490", "#8B5CF6", "#4D7C0F", "#9D174D", "#0369A1", "#A16207",
    "#7C3AED", "#0F766E", "#BE185D", "#DC2626",
];
const CINZA_LIGACAO: &str = "#CBD5E1";
const TINTA: &str = "#14204A";
const TINTA_FRACA: &str = "#64748B";
const FONTE: &str = "Inter, Arial, sans-serif";
const LARGURA_COLUNA_LEGENDA: i64 = 236;
const COLUNAS_MAX_LEGENDA: i64 = 4;

/// Cor do agrupamento: a paleta fixa e, depois, tons espalhados pelo ângulo áureo.
pub fn cor_do_grupo(posicao: usize) -> String {
    if posicao < PALETA.len() {
        return PALETA[posicao].to_string();
    }
    let extra = posicao - PALETA.len();
    let matiz = (extra as f64 * 137.508 + 20.0) % 360.0;
    let luz = [0.40, 0.50, 0.33][extra % 3];
    let sat = [0.62, 0.55, 0.70][extra % 3];
    let c = (1.0 - (2.0 * luz - 1.0f64).abs()) * sat;
    let x = c * (1.0 - ((matiz / 60.0) % 2.0 - 1.0).abs());
    let m = luz - c / 2.0;
    let (r, g, b) = match (matiz / 60.0).floor() as i64 % 6 {
        0 => (c, x, 0.0),
        1 => (x, c, 0.0),
        2 => (0.0, c, x),
        3 => (0.0, x, c),
        4 => (x, 0.0, c),
        _ => (c, 0.0, x),
    };
    let f = |v: f64| ((v + m) * 255.0).round() as i64;
    format!("#{:02X}{:02X}{:02X}", f(r), f(g), f(b))
}

// ------------------------------------------------------------ rótulos

/// Texto curto (até `termos` termos) de um rótulo novo.
pub fn texto_rotulo_novo(rotulo: Option<&str>, termos: usize) -> Option<String> {
    let t = rotulo?;
    let partes: Vec<&str> = t.split(" · ").map(|s| s.trim()).filter(|s| !s.is_empty()).collect();
    let texto = if partes.is_empty() { normaliza_espacos(t) } else { partes.iter().take(termos).cloned().collect::<Vec<_>>().join(" · ") };
    let texto = normaliza_espacos(&texto);
    if texto.is_empty() {
        None
    } else {
        Some(texto)
    }
}

/// Nome legível do agrupamento: termo, autor ou referência abreviada.
pub fn rotulo_curto(texto: &str, unidade: &str, limite: usize) -> String {
    let t = texto.trim();
    let mut t = if t.is_empty() { "Sem grupo".to_string() } else { t.to_string() };
    match unidade {
        "Words" => t = redes_core::texto::termo_legivel(&t),
        "References" => {
            t = match ref_autor_ano(&t) {
                Some(s) => s,
                None => t.chars().take(36).collect(),
            }
        }
        "ReferenceSources" => t = t.chars().take(40).collect(),
        _ => {}
    }
    corta(&t, limite)
}

/// `^(.{2,34}?),\s*(\d{4})` → "autor, ano".
fn ref_autor_ano(t: &str) -> Option<String> {
    let c: Vec<char> = t.chars().collect();
    for len in 2..=34usize {
        if len >= c.len() {
            return None;
        }
        if c[len] == ',' {
            let mut j = len + 1;
            while j < c.len() && c[j].is_whitespace() {
                j += 1;
            }
            if j + 4 <= c.len() && c[j..j + 4].iter().all(|x| x.is_ascii_digit()) {
                let autor: String = c[..len].iter().collect();
                let ano: String = c[j..j + 4].iter().collect();
                return Some(format!("{autor}, {ano}"));
            }
        }
    }
    None
}

pub fn nome_curto(texto: &str, unidade: &str, novo: Option<&str>, limite: usize) -> String {
    if let Some(n) = novo {
        let n = inicial_maiuscula(n);
        return if n.chars().count() <= limite { n } else { corta(&n, limite) };
    }
    rotulo_curto(texto, unidade, limite)
}

fn novo_curto(g: &GrupoRel) -> Option<String> {
    texto_rotulo_novo(g.rotulo_novo.as_deref(), 2)
}

// ---------------------------------------------------------------- legenda

#[derive(Clone, Copy, Debug)]
pub struct Legenda {
    pub colunas: i64,
    pub linhas: i64,
    pub passo: i64,
    pub visiveis: i64,
    pub restantes: i64,
}

pub fn geometria_legenda(quantidade: i64, altura: i64, topo: i64, base: i64) -> Legenda {
    let (passo_max, passo_min) = (24i64, 16i64);
    let disponivel = (altura - base - topo).max(80);
    if quantidade <= 0 {
        return Legenda { colunas: 0, linhas: 0, passo: passo_max, visiveis: 0, restantes: 0 };
    }
    for colunas in 1..=COLUNAS_MAX_LEGENDA {
        let linhas = (quantidade + colunas - 1) / colunas;
        let passo = passo_max.min(passo_min.max(disponivel.div_euclid(linhas.max(1))));
        if linhas * passo <= disponivel {
            return Legenda { colunas, linhas, passo, visiveis: quantidade, restantes: 0 };
        }
    }
    let linhas = (disponivel / passo_min).max(1);
    let visiveis = linhas * COLUNAS_MAX_LEGENDA;
    Legenda { colunas: COLUNAS_MAX_LEGENDA, linhas, passo: passo_min, visiveis: quantidade.min(visiveis), restantes: (quantidade - visiveis).max(0) }
}

// -------------------------------------------------------------- estratégico

fn quadros(unidade: &str) -> [(&'static str, &'static str, &'static str, &'static str); 4] {
    // (chave, rótulo, cor, fundo): motor, nicho, emergente, basico
    if unidade == "Countries" {
        [
            ("motor", "Núcleos de cooperação", "#2F2BFF", "#EDEBFF"),
            ("nicho", "Grupos isolados", "#067647", "#E6F8EE"),
            ("emergente", "Periféricos", "#A16207", "#FFF8D6"),
            ("basico", "Cooperação dispersa", "#0B1F66", "#EEF2FF"),
        ]
    } else {
        [
            ("motor", "Temas motores", "#2F2BFF", "#EDEBFF"),
            ("nicho", "Temas de nicho", "#067647", "#E6F8EE"),
            ("emergente", "Temas emergentes ou em declínio", "#A16207", "#FFF8D6"),
            ("basico", "Temas básicos e transversais", "#0B1F66", "#EEF2FF"),
        ]
    }
}

fn quadrante_xy(x: f64, y: f64) -> &'static str {
    if x >= 0.5 && y >= 0.5 {
        "motor"
    } else if x < 0.5 && y >= 0.5 {
        "nicho"
    } else if x < 0.5 {
        "emergente"
    } else {
        "basico"
    }
}

/// Diagrama estratégico (Callon) de um período. `metrica`: "nucleo:h" etc.
pub fn diagrama_svg(p: &PeriodoRel, unidade: &str, titulo: &str, metrica: Option<&str>, rotulo_metrica: Option<&str>) -> Option<String> {
    let grupos = &p.grupos;
    if grupos.is_empty() {
        return None;
    }
    let qs = quadros(unidade);
    let cor = |k: &str| qs.iter().find(|q| q.0 == k).map(|q| q.2).unwrap();
    let fundo = |k: &str| qs.iter().find(|q| q.0 == k).map(|q| q.3).unwrap();
    let rotulo_q = |k: &str| qs.iter().find(|q| q.0 == k).map(|q| q.1).unwrap();

    let mut ordem: Vec<usize> = (0..grupos.len()).collect();
    ordem.sort_by(|&a, &b| grupos[b].itens().cmp(&grupos[a].itens()));

    let altura = 820i64;
    let legenda = geometria_legenda(grupos.len() as i64, altura, 118, 206);
    let legenda_largura = (26 + legenda.colunas * LARGURA_COLUNA_LEGENDA).max(330);
    let largura = 1120i64.max(820 + legenda_largura);
    let pw = (largura - legenda_largura) as f64;
    let (margem_esq, margem_dir, margem_topo, margem_base) = (70.0, 34.0, 84.0, 74.0);
    let (x0, x1) = (margem_esq, pw - margem_dir);
    let (y0, y1) = (margem_topo, altura as f64 - margem_base);
    let px = |v: f64| x0 + v * (x1 - x0);
    let py = |v: f64| y1 - v * (y1 - y0);

    let mut legenda_area = match metrica {
        Some(m) => {
            let nome = m.split_once(':').map(|x| x.1).unwrap_or("");
            format!("área da esfera = {}", rotulo_metrica.filter(|s| !s.is_empty()).unwrap_or(if nome.is_empty() { m } else { nome }))
        }
        None => "área da esfera = número de nós".to_string(),
    };
    let mut tamanhos: Vec<f64>;
    let mut maior: f64;
    if let Some(m) = metrica {
        let chave = if m.contains(':') { m.to_string() } else { format!("nucleo:{m}") };
        tamanhos = grupos.iter().map(|g| g.medidas.get(&chave).copied().unwrap_or(0.0)).collect();
        maior = tamanhos.iter().cloned().fold(0.0, f64::max);
        if maior <= 0.0 {
            tamanhos = grupos.iter().map(|g| g.itens() as f64).collect();
            maior = tamanhos.iter().cloned().fold(0.0, f64::max);
            legenda_area = "área da esfera = número de nós (medida sem valor neste recorte)".into();
        }
    } else {
        tamanhos = grupos.iter().map(|g| g.itens() as f64).collect();
        maior = tamanhos.iter().cloned().fold(0.0, f64::max);
    }
    let raio_base = 30.0;
    let raios: Vec<f64> = tamanhos.iter().map(|t| raio_base * (t / maior.max(1e-9)).sqrt() + 9.0).collect();

    let (mx, my) = (px(0.5), py(0.5));
    let mut s = String::new();
    let _ = write!(
        s,
        "<rect x=\"{x0}\" y=\"{y0}\" width=\"{:.0}\" height=\"{:.0}\" fill=\"{}\"/>\
<rect x=\"{:.0}\" y=\"{y0}\" width=\"{:.0}\" height=\"{:.0}\" fill=\"{}\"/>\
<rect x=\"{x0}\" y=\"{:.0}\" width=\"{:.0}\" height=\"{:.0}\" fill=\"{}\"/>\
<rect x=\"{:.0}\" y=\"{:.0}\" width=\"{:.0}\" height=\"{:.0}\" fill=\"{}\"/>",
        mx - x0,
        my - y0,
        fundo("nicho"),
        mx,
        x1 - mx,
        my - y0,
        fundo("motor"),
        my,
        mx - x0,
        y1 - my,
        fundo("emergente"),
        mx,
        my,
        x1 - mx,
        y1 - my,
        fundo("basico")
    );
    let rodape = if unidade == "Countries" { "centralidade = ligações ao resto; densidade = coesão interna" } else { "cruzamento em 0,5 da faixa normalizada" };
    let y_quad = altura - 190;
    let mut blocos = String::new();
    let _ = write!(
        blocos,
        "<text x=\"{}\" y=\"{y_quad}\" font-size=\"11\" font-weight=\"700\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">QUADRANTES</text>",
        pw + 16.0
    );
    for (pos, chave) in ["motor", "nicho", "emergente", "basico"].iter().enumerate() {
        let linha_y = y_quad + 22 + pos as i64 * 22;
        let _ = write!(
            blocos,
            "<rect x=\"{}\" y=\"{}\" width=\"16\" height=\"12\" rx=\"2\" fill=\"{}\" stroke=\"{}\"/>\
<text x=\"{}\" y=\"{}\" font-size=\"11.5\" fill=\"{TINTA}\" font-family=\"{FONTE}\">{}</text>",
            pw + 18.0,
            linha_y - 9,
            fundo(chave),
            cor(chave),
            pw + 40.0,
            linha_y + 1,
            rotulo_q(chave)
        );
    }
    let eixos = format!(
        "<rect x=\"{x0}\" y=\"{y0}\" width=\"{}\" height=\"{}\" fill=\"none\" stroke=\"#D8D6CE\"/>\
<line x1=\"{x0}\" y1=\"{my:.0}\" x2=\"{x1}\" y2=\"{my:.0}\" stroke=\"#9C998F\" stroke-dasharray=\"5 4\"/>\
<line x1=\"{mx:.0}\" y1=\"{y0}\" x2=\"{mx:.0}\" y2=\"{y1}\" stroke=\"#9C998F\" stroke-dasharray=\"5 4\"/>",
        x1 - x0,
        y1 - y0
    );
    let mut marcas = String::new();
    for v in [0.0, 0.5, 1.0] {
        let _ = write!(
            marcas,
            "<text x=\"{:.0}\" y=\"{}\" text-anchor=\"middle\" font-size=\"11\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">{v:.1}</text>\
<text x=\"{}\" y=\"{:.0}\" text-anchor=\"end\" font-size=\"11\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">{v:.1}</text>",
            px(v),
            y1 + 22.0,
            x0 - 12.0,
            py(v) + 4.0
        );
    }
    let ym = (y0 + y1) / 2.0;
    let titulos_eixos = format!(
        "<text x=\"{:.0}\" y=\"{}\" text-anchor=\"middle\" font-size=\"12\" font-weight=\"600\" fill=\"{TINTA}\" font-family=\"{FONTE}\">Centralidade de Callon (faixa normalizada)</text>\
<text x=\"22\" y=\"{ym:.0}\" text-anchor=\"middle\" font-size=\"12\" font-weight=\"600\" fill=\"{TINTA}\" font-family=\"{FONTE}\" transform=\"rotate(-90 22 {ym:.0})\">Densidade de Callon (faixa normalizada)</text>",
        (x0 + x1) / 2.0,
        altura - 26
    );

    // esferas e selos
    let mut esferas = String::new();
    let meio = ((x0 + x1) / 2.0, (y0 + y1) / 2.0);
    for (pos_ordem, &i) in ordem.iter().enumerate() {
        let g = &grupos[i];
        let r = raios[i];
        let cx = px(g.centralidade_faixa).max(x0 + r + 2.0).min(x1 - r - 2.0);
        let cy = py(g.densidade_faixa).max(y0 + r + 2.0).min(y1 - r - 2.0);
        let (vx, vy) = (cx - meio.0, cy - meio.1);
        let norma = vx.hypot(vy);
        let norma = if norma == 0.0 { 1.0 } else { norma };
        let sx = (cx + vx / norma * (r + 14.0)).max(x0 + 16.0).min(x1 - 16.0);
        let sy = (cy + vy / norma * (r + 14.0)).max(y0 + 16.0).min(y1 - 16.0);
        let c = cor(quadrante_xy(g.centralidade_faixa, g.densidade_faixa));
        let _ = write!(
            esferas,
            "<circle cx=\"{cx:.1}\" cy=\"{cy:.1}\" r=\"{r:.1}\" fill=\"{c}\" fill-opacity=\"0.16\" stroke=\"{c}\" stroke-width=\"1.4\"/>\
<circle cx=\"{sx:.1}\" cy=\"{sy:.1}\" r=\"12\" fill=\"#ffffff\" stroke=\"{c}\" stroke-width=\"2.5\"/>\
<text x=\"{sx:.1}\" y=\"{:.1}\" text-anchor=\"middle\" font-size=\"12\" font-weight=\"700\" fill=\"{c}\" font-family=\"{FONTE}\">{}</text>",
            sy + 4.0,
            pos_ordem + 1
        );
    }
    // legenda
    let mut leg = String::new();
    let linhas = legenda.linhas.max(1);
    for (posicao, &i) in ordem.iter().take(legenda.visiveis as usize).enumerate() {
        let g = &grupos[i];
        let c = cor(quadrante_xy(g.centralidade_faixa, g.densidade_faixa));
        let nome = nome_curto(&g.rotulo, unidade, novo_curto(g).as_deref(), 30);
        let (coluna, linha) = ((posicao as i64) / linhas, (posicao as i64) % linhas);
        let x = pw as i64 + 26 + coluna * LARGURA_COLUNA_LEGENDA;
        let y = 122 + linha * legenda.passo;
        let _ = write!(
            leg,
            "<circle cx=\"{x}\" cy=\"{}\" r=\"10\" fill=\"#ffffff\" stroke=\"{c}\" stroke-width=\"2.5\"/>\
<text x=\"{x}\" y=\"{}\" text-anchor=\"middle\" font-size=\"11\" font-weight=\"700\" fill=\"{c}\" font-family=\"{FONTE}\">{}</text>\
<text x=\"{}\" y=\"{}\" font-size=\"12\" fill=\"{TINTA}\" font-family=\"{FONTE}\">{} <tspan fill=\"{TINTA_FRACA}\">({})</tspan></text>",
            y - 4,
            y + 1,
            posicao + 1,
            x + 20,
            y + 1,
            esc(&nome),
            g.itens()
        );
    }
    if legenda.restantes > 0 {
        let _ = write!(
            leg,
            "<text x=\"{}\" y=\"{}\" font-size=\"11.5\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">+ {} agrupamentos (ver tabela)</text>",
            pw as i64 + 26,
            122 + legenda.linhas * legenda.passo + 4,
            legenda.restantes
        );
    }

    Some(format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{t}\" viewBox=\"0 0 {largura} {altura}\" width=\"{largura}\" height=\"{altura}\">\
<rect width=\"{largura}\" height=\"{altura}\" fill=\"#ffffff\"/>\
<text x=\"40\" y=\"40\" font-size=\"18\" font-weight=\"600\" fill=\"{TINTA}\" font-family=\"{FONTE}\">{t}</text>\
<text x=\"40\" y=\"62\" font-size=\"12\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">{} agrupamentos · {} nós; {}</text>\
{s}{eixos}{marcas}{titulos_eixos}{esferas}{leg}{blocos}\
<text x=\"40\" y=\"{}\" font-size=\"10\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">Redes · {rodape}</text>\
</svg>",
        grupos.len(),
        p.rede_nos,
        esc(&legenda_area),
        altura - 8,
        t = esc(titulo)
    ))
}

// ------------------------------------------------------------------- halo

type V2 = (f64, f64);

struct Grafo {
    ids: Vec<i64>,
    idx: HashMap<i64, usize>,
    arestas: Vec<(usize, usize, f64)>,
}

fn grafo_da_rede(rede: &RedeRel) -> Grafo {
    let ids: Vec<i64> = rede.nos.iter().map(|n| n.id).collect();
    let idx: HashMap<i64, usize> = ids.iter().enumerate().map(|(i, &n)| (n, i)).collect();
    let arestas = rede.arestas.iter().filter_map(|a| Some((*idx.get(&a.a)?, *idx.get(&a.b)?, a.peso))).collect();
    Grafo { ids, idx, arestas }
}

/// Fruchterman-Reingold determinístico: posições iniciais em círculo (ordem dos nós).
fn mola(n: usize, arestas: &[(usize, usize, f64)], k: f64, iteracoes: usize, fixos: &[Option<V2>]) -> Vec<V2> {
    let mut pos: Vec<V2> = (0..n)
        .map(|i| match fixos.get(i).copied().flatten() {
            Some(p) => p,
            None => {
                let a = std::f64::consts::TAU * i as f64 / n.max(1) as f64;
                (0.5 + 0.35 * a.cos() + 0.01 * ((i * 7) % 5) as f64, 0.5 + 0.35 * a.sin() + 0.01 * ((i * 3) % 5) as f64)
            }
        })
        .collect();
    if n < 2 {
        return pos;
    }
    let mut t = 0.1;
    let dt = t / (iteracoes as f64 + 1.0);
    for _ in 0..iteracoes {
        let mut d = vec![(0.0f64, 0.0f64); n];
        for i in 0..n {
            for j in i + 1..n {
                let (dx, dy) = (pos[i].0 - pos[j].0, pos[i].1 - pos[j].1);
                let dist = (dx * dx + dy * dy).sqrt().max(0.01);
                let f = k * k / dist;
                let (fx, fy) = (dx / dist * f, dy / dist * f);
                d[i].0 += fx;
                d[i].1 += fy;
                d[j].0 -= fx;
                d[j].1 -= fy;
            }
        }
        for &(a, b, w) in arestas {
            let (dx, dy) = (pos[a].0 - pos[b].0, pos[a].1 - pos[b].1);
            let dist = (dx * dx + dy * dy).sqrt().max(0.01);
            let f = dist * dist / k * w.max(1e-9).min(1.0).max(0.1);
            let (fx, fy) = (dx / dist * f, dy / dist * f);
            d[a].0 -= fx;
            d[a].1 -= fy;
            d[b].0 += fx;
            d[b].1 += fy;
        }
        for i in 0..n {
            if fixos.get(i).copied().flatten().is_some() {
                continue;
            }
            let m = (d[i].0 * d[i].0 + d[i].1 * d[i].1).sqrt().max(1e-9);
            let passo = m.min(t);
            pos[i].0 += d[i].0 / m * passo;
            pos[i].1 += d[i].1 / m * passo;
        }
        t = (t - dt).max(0.002);
    }
    pos
}

fn separar(pos: &mut [V2], raios: &[f64], largura: f64, altura: f64, iteracoes: usize, folga: f64, topo: f64, base: f64) {
    let n = pos.len();
    if n < 2 {
        return;
    }
    for _ in 0..iteracoes {
        let anterior = pos.to_vec();
        let mut houve = false;
        let mut novo = pos.to_vec();
        for i in 0..n {
            let (mut sx, mut sy) = (0.0, 0.0);
            for j in 0..n {
                if i == j {
                    continue;
                }
                let (dx, dy) = (pos[i].0 - pos[j].0, pos[i].1 - pos[j].1);
                let dist = (dx * dx + dy * dy).sqrt() + 1e-6;
                let falta = (raios[i] + raios[j] + folga - dist).max(0.0) / dist;
                if falta > 0.0 {
                    houve = true;
                }
                sx += falta * dx;
                sy += falta * dy;
            }
            novo[i].0 = (pos[i].0 + 0.5 * sx).max(raios[i] + 8.0).min(largura - raios[i] - 8.0);
            novo[i].1 = (pos[i].1 + 0.5 * sy).max(raios[i] + topo).min(altura - raios[i] - base);
        }
        pos.copy_from_slice(&novo);
        if !houve && pos == anterior.as_slice() {
            break;
        }
    }
}

fn separados(pos: &[V2], raios: &[f64], folga: f64) -> bool {
    for i in 0..pos.len() {
        for j in i + 1..pos.len() {
            let d = ((pos[i].0 - pos[j].0).powi(2) + (pos[i].1 - pos[j].1).powi(2)).sqrt();
            if d < raios[i] + raios[j] + folga {
                return false;
            }
        }
    }
    true
}

struct NoDesenhado {
    id: i64,
    grupo: Option<usize>,
    raio: f64,
    x: f64,
    y: f64,
}

struct HaloGrupo {
    indice: usize,
    chave: String,
    origem: Vec<usize>,
    cor: String,
    nos: usize,
    x: f64,
    y: f64,
    raio: f64,
    selo: V2,
}

struct LayoutHalo {
    largura: i64,
    altura: i64,
    pw: f64,
    ph: f64,
    legenda: Legenda,
    grupos: Vec<HaloGrupo>,
    soltos: Vec<i64>,
    nos: Vec<NoDesenhado>,
    internas: Vec<(i64, i64, usize)>,
    entre: Vec<(usize, usize, usize)>,
    cruzadas: Vec<(i64, i64, f64)>,
    soltas: Vec<(i64, i64)>,
}

fn tamanhos_por_posto(valores: &[usize]) -> HashMap<usize, f64> {
    let mut m = HashMap::new();
    if valores.is_empty() {
        return m;
    }
    let mut ord = valores.to_vec();
    ord.sort_unstable();
    if ord.len() == 1 {
        m.insert(ord[0], 11.0);
        return m;
    }
    let corte1 = ord[(ord.len() / 3).saturating_sub(1)];
    let corte2 = ord[(2 * ord.len() / 3).saturating_sub(1)];
    for &v in valores {
        m.insert(v, if v <= corte1 { 7.0 } else if v <= corte2 { 11.0 } else { 15.0 });
    }
    m
}

fn layout_halo(p: &PeriodoRel, rede: &RedeRel) -> LayoutHalo {
    let (largura0, altura, legenda_largura0) = (1280i64, 780i64, 300i64);
    let g = grafo_da_rede(rede);

    // agrupamentos de mesmo rótulo viram um halo só
    let mut chaves: Vec<String> = Vec::new();
    let mut membros: HashMap<String, Vec<i64>> = HashMap::new();
    let mut origem: HashMap<String, Vec<usize>> = HashMap::new();
    let mut agrupados: HashSet<i64> = HashSet::new();
    for (pos, gr) in p.grupos.iter().enumerate() {
        let c = if gr.rotulo.is_empty() { "Sem grupo".to_string() } else { gr.rotulo.clone() };
        if !membros.contains_key(&c) {
            chaves.push(c.clone());
        }
        membros.entry(c.clone()).or_default().extend(gr.nos.iter().copied());
        origem.entry(c).or_default().push(pos);
        agrupados.extend(gr.nos.iter().copied());
    }
    let soltos: Vec<i64> = g.ids.iter().copied().filter(|n| !agrupados.contains(n)).collect();
    chaves.sort_by(|a, b| membros[b].len().cmp(&membros[a].len()).then_with(|| a.cmp(b)));
    let lista: Vec<&Vec<i64>> = chaves.iter().map(|c| &membros[c]).collect();
    let mut indice: HashMap<i64, usize> = HashMap::new();
    for (i, m) in lista.iter().enumerate() {
        for &no in m.iter() {
            indice.insert(no, i);
        }
    }
    let k = lista.len();

    let legenda = geometria_legenda((k + usize::from(!soltos.is_empty())) as i64, altura, 118, 48);
    let largura_legenda = if k > 0 || !soltos.is_empty() { 26 + legenda.colunas.max(1) * LARGURA_COLUNA_LEGENDA } else { 0 };
    let largura_legenda = legenda_largura0.max(largura_legenda);
    let largura = largura0.max(880 + largura_legenda);
    let pw = (largura - largura_legenda) as f64;
    let ph = altura as f64;

    let mut meta: BTreeMap<(usize, usize), usize> = BTreeMap::new();
    for &(a, b, _) in &g.arestas {
        if let (Some(&ia), Some(&ib)) = (indice.get(&g.ids[a]), indice.get(&g.ids[b])) {
            if ia != ib {
                *meta.entry((ia.min(ib), ia.max(ib))).or_insert(0) += 1;
            }
        }
    }

    // posição-base dos grupos: círculo, com mola entre grupos quando há ligações
    let circulo: Vec<V2> = (0..k)
        .map(|i| {
            let a = std::f64::consts::TAU * i as f64 / k.max(1) as f64;
            (0.5 + 0.34 * a.cos(), 0.5 + 0.34 * a.sin())
        })
        .collect();
    let base: Vec<V2> = if k > 1 && k <= 400 && meta.len() >= k {
        let ar: Vec<(usize, usize, f64)> = meta.iter().map(|(&(a, b), &w)| (a, b, w as f64)).collect();
        let m = mola(k, &ar, 0.6, 200, &[]);
        let (mut x0, mut x1, mut y0, mut y1) = (f64::MAX, f64::MIN, f64::MAX, f64::MIN);
        for q in &m {
            x0 = x0.min(q.0);
            x1 = x1.max(q.0);
            y0 = y0.min(q.1);
            y1 = y1.max(q.1);
        }
        (0..k)
            .map(|i| {
                let (mx, my) = ((m[i].0 - x0) / (x1 - x0 + 1e-9), (m[i].1 - y0) / (y1 - y0 + 1e-9));
                (0.65 * circulo[i].0 + 0.35 * mx, 0.65 * circulo[i].1 + 0.35 * my)
            })
            .collect()
    } else {
        circulo
    };

    // desenho interno de cada agrupamento
    let iter_mola = if k <= 300 { 300 } else { 120 };
    let mut internos: Vec<(Vec<(i64, V2)>, usize)> = Vec::new(); // (nó, deslocamento unitário), nº de nós
    let mut arestas_int: Vec<Vec<(i64, i64)>> = Vec::new();
    for m in &lista {
        let n = m.len();
        let local: HashMap<i64, usize> = m.iter().enumerate().map(|(i, &x)| (x, i)).collect();
        let mut ar_loc = Vec::new();
        let mut ar_ids = Vec::new();
        for &(a, b, w) in &g.arestas {
            if let (Some(&la), Some(&lb)) = (local.get(&g.ids[a]), local.get(&g.ids[b])) {
                ar_loc.push((la, lb, w));
                ar_ids.push((g.ids[a], g.ids[b]));
            }
        }
        let q: Vec<V2> = if n == 1 {
            vec![(0.0, 0.0)]
        } else if n == 2 {
            vec![(-1.0, 0.0), (1.0, 0.0)]
        } else {
            mola(n, &ar_loc, 1.3 / (n as f64).sqrt(), iter_mola, &[])
        };
        let cx = q.iter().map(|v| v.0).sum::<f64>() / n as f64;
        let cy = q.iter().map(|v| v.1).sum::<f64>() / n as f64;
        let escala = q.iter().map(|v| (v.0 - cx).abs().max((v.1 - cy).abs())).fold(1e-6, f64::max);
        internos.push((m.iter().zip(q.iter()).map(|(&no, v)| (no, ((v.0 - cx) / escala, (v.1 - cy) / escala))).collect(), n));
        arestas_int.push(ar_ids);
    }

    let mut unit = 30.0f64;
    let tentativas = if k <= 50 { 14 } else if k <= 150 { 5 } else { 1 };
    let iteracoes = if k <= 50 { 600 } else if k <= 150 { 350 } else { 120 };
    let refinos = if k <= 150 { 8 } else { 2 };
    let mut desloc: Vec<Vec<(i64, V2)>> = Vec::new();
    let mut raios: Vec<f64> = Vec::new();
    let mut pos: Vec<V2> = vec![(0.0, 0.0); k];
    if k > 0 {
        for _ in 0..tentativas {
            desloc.clear();
            raios.clear();
            for (v, n) in &internos {
                let diametro = unit * (*n as f64).sqrt() + unit * 0.7;
                desloc.push(v.iter().map(|&(no, d)| (no, (d.0 * diametro / 2.0, d.1 * diametro / 2.0))).collect());
                raios.push(diametro / 2.0 + 10.0);
            }
            pos = base.iter().map(|b| (40.0 + b.0 * (pw - 80.0), 90.0 + b.1 * (ph - 130.0))).collect();
            separar(&mut pos, &raios, pw, ph, iteracoes, 8.0, 96.0, 40.0);
            if k == 1 || separados(&pos, &raios, 2.0) {
                break;
            }
            unit *= 0.9;
        }
        for _ in 0..refinos {
            separar(&mut pos, &raios, pw, ph, iteracoes.min(400), 8.0, 96.0, 40.0);
            if separados(&pos, &raios, 6.0) || k < 2 {
                break;
            }
            for d in desloc.iter_mut() {
                for e in d.iter_mut() {
                    e.1 = (e.1 .0 * 0.94, e.1 .1 * 0.94);
                }
            }
            for r in raios.iter_mut() {
                *r *= 0.94;
            }
            for q in pos.iter_mut() {
                *q = (q.0 * 0.94 + pw / 2.0 * 0.06, q.1 * 0.94 + (90.0 + ph - 40.0) / 2.0 * 0.06);
            }
        }
        // enquadramento
        let xmin = (0..k).map(|i| pos[i].0 - raios[i]).fold(f64::MAX, f64::min);
        let xmax = (0..k).map(|i| pos[i].0 + raios[i]).fold(f64::MIN, f64::max);
        let ymin = (0..k).map(|i| pos[i].1 - raios[i]).fold(f64::MAX, f64::min);
        let ymax = (0..k).map(|i| pos[i].1 + raios[i]).fold(f64::MIN, f64::max);
        let fator = ((pw - 100.0) / (xmax - xmin).max(1e-6)).min((ph - 170.0) / (ymax - ymin).max(1e-6)).min(2.2);
        if fator > 1.0 {
            let (cx, cy) = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0);
            for q in pos.iter_mut() {
                *q = (pw / 2.0 + (q.0 - cx) * fator, (90.0 + ph - 40.0) / 2.0 + (q.1 - cy) * fator);
            }
        }
    }

    let mut nodepos: HashMap<i64, V2> = HashMap::new();
    for (i, d) in desloc.iter().enumerate() {
        for &(no, dd) in d {
            nodepos.insert(no, (pos[i].0 + dd.0, pos[i].1 + dd.1));
        }
    }
    // nós soltos: anel externo e relaxamento
    let dentro = |q: V2| -> V2 {
        let (bx, by, ax, ay) = (20.0, 104.0, pw - 20.0, ph - 44.0);
        let refl = |v: f64, lo: f64, hi: f64| {
            let f = hi - lo;
            lo + ((v - lo).rem_euclid(2.0 * f) - f).abs()
        };
        (refl(q.0, bx, ax), refl(q.1, by, ay))
    };
    if !soltos.is_empty() {
        for (j, &no) in soltos.iter().enumerate() {
            let a = std::f64::consts::TAU * j as f64 / soltos.len().max(1) as f64 + 0.4;
            nodepos.insert(no, (pw / 2.0 + a.cos() * pw * 0.42, ph / 2.0 + a.sin() * ph * 0.40));
        }
        let m = soltos.len();
        let mut pts: Vec<V2> = soltos.iter().map(|n| nodepos[n]).collect();
        let extras: Vec<f64> = soltos.iter().map(|n| (n.unsigned_abs() % 12) as f64).collect();
        for _ in 0..300 {
            for a in 0..m.saturating_sub(1) {
                for b in a + 1..m {
                    let (dx, dy) = (pts[a].0 - pts[b].0, pts[a].1 - pts[b].1);
                    let d = (dx * dx + dy * dy).sqrt() + 1e-6;
                    if d < 16.0 {
                        let f = (16.0 - d) / 2.0 / d;
                        pts[a].0 += dx * f;
                        pts[a].1 += dy * f;
                        pts[b].0 -= dx * f;
                        pts[b].1 -= dy * f;
                    }
                }
            }
            for j in 0..m {
                for i in 0..k {
                    let lim = raios[i] + 8.0 + extras[j];
                    let (dx, dy) = (pts[j].0 - pos[i].0, pts[j].1 - pos[i].1);
                    let d = (dx * dx + dy * dy).sqrt() + 1e-6;
                    if d < lim {
                        pts[j].0 += (lim - d) * dx / d;
                        pts[j].1 += (lim - d) * dy / d;
                    }
                }
                pts[j] = dentro(pts[j]);
            }
        }
        for (j, &no) in soltos.iter().enumerate() {
            nodepos.insert(no, pts[j]);
        }
    }

    let selos: Vec<V2> = (0..k)
        .map(|i| {
            let (mut vx, mut vy) = (pos[i].0 - pw / 2.0, pos[i].1 - ph / 2.0);
            let n = vx.hypot(vy);
            if n > 1e-6 {
                vx /= n;
                vy /= n;
            } else {
                vx = 0.0;
                vy = -1.0;
            }
            let (qx, qy) = (pos[i].0 + vx * raios[i], pos[i].1 + vy * raios[i]);
            (qx.max(30.0).min(pw - 30.0), qy.max(96.0).min(ph - 42.0))
        })
        .collect();

    let freqs: Vec<usize> = rede.nos.iter().map(|n| n.frequencia.max(1)).collect();
    let tam = tamanhos_por_posto(&freqs);
    let nos: Vec<NoDesenhado> = rede
        .nos
        .iter()
        .map(|n| {
            let (x, y) = nodepos.get(&n.id).copied().unwrap_or((pw / 2.0, ph / 2.0));
            NoDesenhado { id: n.id, grupo: indice.get(&n.id).copied(), raio: tam.get(&n.frequencia.max(1)).copied().unwrap_or(7.0) / 2.0, x, y }
        })
        .collect();

    let grupos: Vec<HaloGrupo> = (0..k)
        .map(|i| HaloGrupo {
            indice: i + 1,
            chave: chaves[i].clone(),
            origem: origem[&chaves[i]].clone(),
            cor: cor_do_grupo(i),
            nos: lista[i].len(),
            x: pos[i].0,
            y: pos[i].1,
            raio: raios[i],
            selo: selos[i],
        })
        .collect();

    let mut internas = Vec::new();
    for (i, ar) in arestas_int.iter().enumerate() {
        for &(a, b) in ar {
            internas.push((a, b, i));
        }
    }
    let entre: Vec<(usize, usize, usize)> = meta.iter().map(|(&(a, b), &w)| (a, b, w)).collect();
    let soltas: Vec<(i64, i64)> = g
        .arestas
        .iter()
        .filter(|&&(a, b, _)| !(indice.contains_key(&g.ids[a]) && indice.contains_key(&g.ids[b])))
        .map(|&(a, b, _)| (g.ids[a], g.ids[b]))
        .collect();
    let mut cruzadas: Vec<(i64, i64, f64)> = g
        .arestas
        .iter()
        .filter(|&&(a, b, _)| matches!((indice.get(&g.ids[a]), indice.get(&g.ids[b])), (Some(x), Some(y)) if x != y))
        .map(|&(a, b, w)| (g.ids[a], g.ids[b], w))
        .collect();
    if cruzadas.len() > 600 {
        cruzadas.clear();
    }
    let _ = &g.idx;
    LayoutHalo { largura, altura, pw, ph, legenda, grupos, soltos, nos, internas, entre, cruzadas, soltas }
}

/// Rede completa do período, em halos. `pivos`: ids dos pontos de virada, em ordem.
pub fn halo_svg(p: &PeriodoRel, unidade: &str, matriz: &str, titulo: &str, pivos: &[i64]) -> Option<String> {
    let rede = p.rede.as_ref()?;
    let d = layout_halo(p, rede);
    let (largura, altura, pw) = (d.largura, d.altura, d.pw);
    let _ = d.ph;
    let k = d.grupos.len();
    let nodepos: HashMap<i64, (f64, f64, f64)> = d.nos.iter().map(|n| (n.id, (n.x, n.y, n.raio))).collect();

    let halos: String = d
        .grupos
        .iter()
        .map(|g| format!("<circle cx=\"{:.0}\" cy=\"{:.0}\" r=\"{:.0}\" fill=\"{}\" fill-opacity=\"0.09\"/>", g.x, g.y, g.raio, g.cor))
        .collect();

    let mut ligacoes = String::new();
    if !d.cruzadas.is_empty() {
        let pmax = d.cruzadas.iter().map(|c| c.2).fold(0.0f64, f64::max);
        let _ = pmax;
        for &(a, b, peso) in &d.cruzadas {
            let (pa, pb) = (nodepos[&a], nodepos[&b]);
            let _ = write!(ligacoes, "<path d=\"M{:.1} {:.1}L{:.1} {:.1}\" stroke-width=\"{:.2}\"/>", pa.0, pa.1, pb.0, pb.1, 1.0 + 0.9 * peso.min(1.0));
        }
    } else {
        let mut e = d.entre.clone();
        e.sort_by(|a, b| b.2.cmp(&a.2));
        for (gi, gj, peso) in e.into_iter().take(30) {
            if peso < 2 {
                continue;
            }
            let (a, b) = (&d.grupos[gi], &d.grupos[gj]);
            let _ = write!(ligacoes, "<path d=\"M{:.0} {:.0}L{:.0} {:.0}\" stroke-width=\"{:.1}\"/>", a.x, a.y, b.x, b.y, 1.2 + 0.35 * (peso.min(10) as f64));
        }
    }
    let ligacoes_soltas: String = d
        .soltas
        .iter()
        .map(|&(a, b)| {
            let (pa, pb) = (nodepos[&a], nodepos[&b]);
            format!("<path d=\"M{:.1} {:.1}L{:.1} {:.1}\" stroke-width=\"0.9\"/>", pa.0, pa.1, pb.0, pb.1)
        })
        .collect();

    let mut grupos_svg = String::new();
    for (i, g) in d.grupos.iter().enumerate() {
        let arestas: String = d
            .internas
            .iter()
            .filter(|e| e.2 == i)
            .map(|&(a, b, _)| {
                let (pa, pb) = (nodepos[&a], nodepos[&b]);
                format!("M{:.1} {:.1}L{:.1} {:.1}", pa.0, pa.1, pb.0, pb.1)
            })
            .collect();
        let n_ar = d.internas.iter().filter(|e| e.2 == i).count();
        let mut por_espessura: Vec<(f64, String)> = Vec::new();
        for n in d.nos.iter().filter(|n| n.grupo == Some(i)) {
            let esp = n.raio * 2.0;
            let seg = format!("M{:.1} {:.1}h0", n.x, n.y);
            match por_espessura.iter_mut().find(|(e, _)| *e == esp) {
                Some((_, s)) => s.push_str(&seg),
                None => por_espessura.push((esp, seg)),
            }
        }
        let opac = (8.0 / (n_ar.max(1) as f64).sqrt()).min(0.55).max(0.18);
        let _ = write!(grupos_svg, "<g stroke=\"{}\" fill=\"none\" stroke-linecap=\"round\"><path d=\"{arestas}\" stroke-width=\"1.4\" opacity=\"{opac:.2}\"/>", g.cor);
        for (esp, caminho) in por_espessura {
            let _ = write!(grupos_svg, "<path d=\"{caminho}\" stroke-width=\"{}\"/>", fmt_py(esp));
        }
        grupos_svg.push_str("</g>");
    }

    let mut soltos_svg = String::new();
    for &no in &d.soltos {
        let (x, y, r) = nodepos[&no];
        let _ = write!(soltos_svg, "<circle cx=\"{x:.1}\" cy=\"{y:.1}\" r=\"{r:.1}\" fill=\"#ffffff\" stroke=\"{TINTA_FRACA}\" stroke-width=\"1.5\"/>");
    }

    let selos: String = d
        .grupos
        .iter()
        .map(|g| {
            format!(
                "<circle cx=\"{:.0}\" cy=\"{:.0}\" r=\"17\" fill=\"#ffffff\" stroke=\"{c}\" stroke-width=\"3\"/>\
<text x=\"{:.0}\" y=\"{:.0}\" text-anchor=\"middle\" font-size=\"19\" font-weight=\"700\" fill=\"{c}\" font-family=\"{FONTE}\">{}</text>",
                g.selo.0,
                g.selo.1,
                g.selo.0,
                g.selo.1 + 6.0,
                g.indice,
                c = g.cor
            )
        })
        .collect();

    let mut marcados: Vec<i64> = Vec::new();
    for &no in pivos {
        if nodepos.contains_key(&no) && !marcados.contains(&no) {
            marcados.push(no);
        }
    }
    let mut aneis = String::new();
    for (num, no) in marcados.iter().enumerate() {
        let (x, y, r0) = nodepos[no];
        let r = r0 + 3.5;
        let _ = write!(
            aneis,
            "<circle cx=\"{x:.1}\" cy=\"{y:.1}\" r=\"{r:.1}\" fill=\"none\" stroke=\"#ffffff\" stroke-width=\"5.2\"/>\
<circle cx=\"{x:.1}\" cy=\"{y:.1}\" r=\"{r:.1}\" fill=\"none\" stroke=\"{TINTA}\" stroke-width=\"2.2\"/>\
<text x=\"{:.1}\" y=\"{:.1}\" font-size=\"11\" font-weight=\"700\" fill=\"{TINTA}\" font-family=\"{FONTE}\" stroke=\"#ffffff\" stroke-width=\"3\" paint-order=\"stroke\">{}</text>",
            x + r + 3.0,
            y - r + 2.0,
            num + 1
        );
    }
    let legenda_pivos = if marcados.is_empty() {
        String::new()
    } else {
        format!(
            "<circle cx=\"46\" cy=\"{}\" r=\"6.5\" fill=\"none\" stroke=\"{TINTA}\" stroke-width=\"2.2\"/>\
<text x=\"60\" y=\"{}\" font-size=\"11\" fill=\"{TINTA}\" font-family=\"{FONTE}\">ponto de virada (liga agrupamentos diferentes; o número é o Nº da tabela)</text>",
            altura - 40,
            altura - 36
        )
    };

    // legenda
    let mut entradas: Vec<(&str, i64)> = (0..k).map(|i| ("grupo", i as i64)).collect();
    if !d.soltos.is_empty() {
        entradas.push(("soltos", 0));
    }
    let mut visiveis: Vec<(&str, i64)> = entradas.into_iter().take(d.legenda.visiveis.max(0) as usize).collect();
    if d.legenda.restantes > 0 {
        if let Some(u) = visiveis.last_mut() {
            *u = ("restantes", d.legenda.restantes);
        }
    }
    let mut leg = String::new();
    let linhas = d.legenda.linhas.max(1);
    for (ordem, (tipo, valor)) in visiveis.iter().enumerate() {
        let (coluna, linha) = ((ordem as i64) / linhas, (ordem as i64) % linhas);
        let x = pw as i64 + 26 + coluna * LARGURA_COLUNA_LEGENDA;
        let y = 118 + linha * d.legenda.passo;
        match *tipo {
            "grupo" => {
                let g = &d.grupos[*valor as usize];
                let novo = if g.origem.len() == 1 { p.grupos.get(g.origem[0]).and_then(novo_curto) } else { None };
                let nome = nome_curto(&g.chave, unidade, novo.as_deref(), 30);
                let _ = write!(
                    leg,
                    "<circle cx=\"{x}\" cy=\"{}\" r=\"10\" fill=\"#ffffff\" stroke=\"{c}\" stroke-width=\"2.5\"/>\
<text x=\"{x}\" y=\"{}\" text-anchor=\"middle\" font-size=\"11\" font-weight=\"700\" fill=\"{c}\" font-family=\"{FONTE}\">{}</text>\
<text x=\"{}\" y=\"{}\" font-size=\"12\" fill=\"{TINTA}\" font-family=\"{FONTE}\">{} <tspan fill=\"{TINTA_FRACA}\">({})</tspan></text>",
                    y - 4,
                    y + 1,
                    g.indice,
                    x + 18,
                    y + 1,
                    esc(&nome),
                    g.nos,
                    c = g.cor
                );
            }
            "soltos" => {
                let _ = write!(
                    leg,
                    "<circle cx=\"{x}\" cy=\"{}\" r=\"7\" fill=\"#ffffff\" stroke=\"{TINTA_FRACA}\" stroke-width=\"1.5\"/>\
<text x=\"{}\" y=\"{}\" font-size=\"12\" fill=\"{TINTA}\" font-family=\"{FONTE}\">Sem agrupamento <tspan fill=\"{TINTA_FRACA}\">({})</tspan></text>",
                    y - 4,
                    x + 18,
                    y + 1,
                    d.soltos.len()
                );
            }
            _ => {
                let _ = write!(leg, "<text x=\"{x}\" y=\"{}\" font-size=\"11.5\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">+ {valor} agrupamentos (ver tabela)</text>", y + 1);
            }
        }
    }

    let mut subtitulo = format!("{k} agrupamentos · {} nós · {} arestas", rede.nos.len(), rede.arestas.len());
    if matriz != "CoOccurrence" {
        subtitulo.push_str(" · nós = documentos");
    }
    Some(format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"{t}\" viewBox=\"0 0 {largura} {altura}\" width=\"{largura}\" height=\"{altura}\">\
<rect width=\"{largura}\" height=\"{altura}\" fill=\"#ffffff\"/>\
<text x=\"40\" y=\"38\" font-size=\"17\" font-weight=\"600\" fill=\"{TINTA}\" font-family=\"{FONTE}\">{t}</text>\
<text x=\"40\" y=\"60\" font-size=\"12\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">{}</text>\
<text x=\"{}\" y=\"86\" font-size=\"11\" font-weight=\"700\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">AGRUPAMENTOS</text>\
<g fill=\"none\" stroke=\"{CINZA_LIGACAO}\" stroke-linecap=\"round\" opacity=\"0.62\">{ligacoes}</g>\
{halos}\
<g fill=\"none\" stroke=\"{CINZA_LIGACAO}\" stroke-linecap=\"round\" opacity=\"0.6\">{ligacoes_soltas}</g>\
{grupos_svg}{soltos_svg}{aneis}{selos}{leg}{legenda_pivos}\
<text x=\"40\" y=\"{}\" font-size=\"10\" fill=\"{TINTA_FRACA}\" font-family=\"{FONTE}\">Redes · halo = agrupamento; ponto branco = nó sem agrupamento</text>\
</svg>",
        esc(&subtitulo),
        pw as i64 + 16,
        altura - 16,
        t = esc(titulo)
    ))
}

/// Número como o Python imprime um float em f-string (`14.0`, `22.0`).
fn fmt_py(v: f64) -> String {
    if v == v.trunc() {
        format!("{v:.1}")
    } else {
        format!("{v}")
    }
}

// ---------------------------------------------------- rede do agrupamento

/// Rede de um agrupamento: nós na circunferência, arestas internas com espessura
/// proporcional ao peso.
pub fn rede_agrupamento_svg(p: &PeriodoRel, grupo: &GrupoRel, titulo_base: &str) -> Option<String> {
    let rede = p.rede.as_ref()?;
    let largura = 720.0f64;
    let novo = texto_rotulo_novo(grupo.rotulo_novo.as_deref(), 3);
    let (titulo, subtitulo) = match &novo {
        Some(n) => (format!("{} — {}", p.nome, n), Some(grupo.nome_exibicao().to_string())),
        None => (titulo_base.to_string(), None),
    };
    let nos = &grupo.nos;
    let limite_titulo = 20usize.max(((largura - 24.0) / 7.4) as usize);
    let corta_t = |t: &str| if t.chars().count() <= limite_titulo { t.to_string() } else { t.chars().take(limite_titulo - 1).collect::<String>().trim_end().to_string() + "…" };
    let titulo_curto = corta_t(&titulo);
    if nos.is_empty() {
        return Some(format!(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{largura}\" height=\"120\" viewBox=\"0 0 {largura} 120\"><rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\
<text x=\"{}\" y=\"60\" text-anchor=\"middle\" font-family=\"Inter, Arial, sans-serif\" font-size=\"14\" fill=\"#64748B\">{} — agrupamento vazio</text></svg>",
            largura / 2.0,
            esc(&titulo_curto)
        ));
    }
    let altura0 = 400.0f64.max(980.0f64.min(36.0 * nos.len() as f64));
    let desloca = if subtitulo.is_some() { 18.0 } else { 0.0 };
    let altura = altura0 + desloca;
    let (cx, cy) = (largura / 2.0, altura / 2.0 - 6.0 + desloca / 2.0);
    let mut raio = (largura * 0.30).min(altura * 0.36);
    let rotulos: HashMap<i64, &str> = rede.nos.iter().map(|n| (n.id, n.rotulo.as_str())).collect();
    let nome = |no: i64| rotulos.get(&no).copied().unwrap_or("").to_string();
    let maior_rotulo = nos.iter().map(|&n| nome(n).chars().count().min(28)).max().unwrap_or(0);
    raio = 40.0f64.max(raio.min(cx - (maior_rotulo as f64 * 6.0 + 14.0 + 10.0)));

    let mut s = format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{largura}\" height=\"{altura}\" viewBox=\"0 0 {largura} {altura}\" role=\"img\" aria-label=\"{t}\">\n\
<title>{t}</title>\n\
<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n\
<text x=\"{}\" y=\"24\" text-anchor=\"middle\" font-family=\"Inter, Arial, sans-serif\" font-size=\"14\" fill=\"#14204A\">{}</text>",
        largura / 2.0,
        esc(&titulo_curto),
        t = esc(&titulo)
    );
    if let Some(sub) = &subtitulo {
        let _ = write!(
            s,
            "\n<text x=\"{}\" y=\"42\" text-anchor=\"middle\" font-family=\"Inter, Arial, sans-serif\" font-size=\"11.5\" fill=\"{TINTA_FRACA}\">{}</text>",
            largura / 2.0,
            esc(&corta_t(sub))
        );
    }
    let mut posicoes: HashMap<i64, V2> = HashMap::new();
    for (i, &no) in nos.iter().enumerate() {
        let ang = std::f64::consts::TAU * i as f64 / nos.len() as f64 - std::f64::consts::FRAC_PI_2;
        posicoes.insert(no, (cx + raio * ang.cos(), cy + raio * ang.sin()));
    }
    let conj: HashSet<i64> = nos.iter().copied().collect();
    let mut internas: Vec<(i64, i64, f64)> = rede.arestas.iter().filter(|a| conj.contains(&a.a) && conj.contains(&a.b)).map(|a| (a.a.min(a.b), a.a.max(a.b), a.peso)).collect();
    internas.sort_by(|a, b| (a.0, a.1).cmp(&(b.0, b.1)));
    internas.dedup_by(|a, b| a.0 == b.0 && a.1 == b.1);
    let maximo = internas.iter().map(|e| e.2).fold(0.0f64, f64::max);
    let maximo = if maximo > 0.0 { maximo } else { 1.0 };
    for &(a, b, v) in &internas {
        let (pa, pb) = (posicoes[&a], posicoes[&b]);
        let _ = write!(
            s,
            "\n<line x1=\"{:.1}\" y1=\"{:.1}\" x2=\"{:.1}\" y2=\"{:.1}\" stroke=\"#CBD5E1\" stroke-width=\"{:.2}\" opacity=\"0.75\"/>",
            pa.0,
            pa.1,
            pb.0,
            pb.1,
            0.6 + 2.8 * (v / maximo)
        );
    }
    for &no in nos {
        let (x, y) = posicoes[&no];
        let _ = write!(s, "\n<circle cx=\"{x:.1}\" cy=\"{y:.1}\" r=\"6\" fill=\"#EDEBFF\" stroke=\"#2F2BFF\" stroke-width=\"1.3\"/>");
        let direita = x >= cx;
        let (ancora, desl) = if direita { ("start", 14.0) } else { ("end", -14.0) };
        let mut r = nome(no);
        if r.chars().count() > 28 {
            r = r.chars().take(26).collect::<String>() + "…";
        }
        let _ = write!(
            s,
            "\n<text x=\"{:.1}\" y=\"{:.1}\" text-anchor=\"{ancora}\" font-family=\"Helvetica, Arial, sans-serif\" font-size=\"10.5\" fill=\"{TINTA}\">{}</text>",
            x + desl,
            y + 4.0,
            esc(&r)
        );
    }
    let n_int = internas.len();
    let _ = write!(
        s,
        "\n<text x=\"{}\" y=\"{}\" text-anchor=\"middle\" font-family=\"Helvetica, Arial, sans-serif\" font-size=\"10\" fill=\"{TINTA_FRACA}\">{} itens · {}</text>\n</svg>",
        largura / 2.0,
        altura - 12.0,
        nos.len(),
        if n_int == 1 { "1 ligação interna".to_string() } else { format!("{n_int} ligações internas") }
    );
    Some(s)
}

/// Chave de quadrante exposta para quem desenha outras figuras.
pub fn quadrante_do_grupo(g: &GrupoRel) -> &'static str {
    quadrante_chave(g)
}

#[cfg(test)]
mod testes {
    use super::*;

    fn periodo() -> PeriodoRel {
        let nos: Vec<NoRel> = (1..=8).map(|i| NoRel { id: i, rotulo: format!("item {i}"), frequencia: i as usize, grupo: Some(if i <= 4 { 0 } else { 1 }) }).collect();
        let arestas = vec![
            ArestaRel { a: 1, b: 2, peso: 0.5 },
            ArestaRel { a: 2, b: 3, peso: 0.4 },
            ArestaRel { a: 3, b: 4, peso: 0.9 },
            ArestaRel { a: 5, b: 6, peso: 0.7 },
            ArestaRel { a: 6, b: 7, peso: 0.2 },
            ArestaRel { a: 4, b: 5, peso: 0.1 },
        ];
        let g = |id: usize, nos: Vec<i64>, c: f64, d: f64| GrupoRel {
            id,
            rotulo: format!("grupo {id}"),
            exibicao: format!("Grupo {id}"),
            nos,
            centralidade_faixa: c,
            densidade_faixa: d,
            ..Default::default()
        };
        PeriodoRel {
            nome: "2020".into(),
            rede_nos: 8,
            rede_arestas: 6,
            grupos: vec![g(1, vec![1, 2, 3, 4], 1.0, 0.5), g(2, vec![5, 6, 7], 0.5, 1.0)],
            rede: Some(RedeRel { nos, arestas }),
            ..Default::default()
        }
    }

    #[test]
    fn diagrama_e_halo_sao_svg() {
        let p = periodo();
        let d = diagrama_svg(&p, "Words", "Diagrama", None, None).unwrap();
        assert!(d.starts_with("<svg") && d.ends_with("</svg>"));
        assert_eq!(d.matches("fill-opacity=\"0.16\"").count(), 2);
        let h = halo_svg(&p, "Words", "CoOccurrence", "Rede", &[3]).unwrap();
        assert!(h.contains("ponto de virada"));
        assert!(h.contains("Sem agrupamento"), "nó 8 está sem agrupamento");
        let c = rede_agrupamento_svg(&p, &p.grupos[0], "2020 — Grupo 1").unwrap();
        assert!(c.contains("4 itens · 3 ligações internas"));
    }

    #[test]
    fn determinismo() {
        let p = periodo();
        assert_eq!(halo_svg(&p, "Words", "CoOccurrence", "R", &[]), halo_svg(&p, "Words", "CoOccurrence", "R", &[]));
    }

    #[test]
    fn rotulos_curtos() {
        assert_eq!(rotulo_curto("SILVA, 1999, Revista", "References", 30), "SILVA, 1999");
        assert_eq!(texto_rotulo_novo(Some("a · b · c"), 2).unwrap(), "a · b");
        let g = geometria_legenda(10, 820, 118, 206);
        assert_eq!(g.colunas, 1);
    }
}
