//! Mapa de densidade estilo VOSviewer (porta de `viz/densidade.py`).
//!
//! Os itens mais frequentes da rede de co-ocorrência são posicionados por um layout de atração e
//! repulsão (energia do tipo VOS: ligações fortes aproximam, todos os pares se repelem) e, sobre as
//! posições, soma-se um núcleo gaussiano por item ponderado pela frequência. O resultado é
//! normalizado pelo máximo e pintado de branco a amarelo (imagem PNG embutida no SVG).
//!
//! Divergência: o Python sorteia as posições iniciais com `numpy.random.default_rng(3)`; aqui
//! usa-se um gerador próprio (SplitMix64 + Box-Muller, semente 3). O método e os parâmetros são os
//! mesmos, mas as posições finais (e, portanto, a imagem) diferem; a estrutura do SVG é a mesma.

use std::collections::BTreeMap;
use std::io::Write;

use redes_core::Resultado;
use serde::Serialize;

use crate::corpus::Corpus;
use crate::util::*;

pub const LARGURA: f64 = 1100.0;
pub const ALTURA_QUADRO: f64 = 600.0;
pub const TOPO_TITULO: f64 = 46.0;
pub const RODAPE: f64 = 50.0;
pub const MARGEM_QUADRO: f64 = 16.0;
pub const MARGEM_NOS: f64 = 44.0;
pub const TOPO_NOS: usize = 150;
pub const LIMITE_NOS: (usize, usize) = (20, 300);
pub const SUAVIZACAO: usize = 4;
pub const LIMITE_SUAVIZACAO: (usize, usize) = (1, 9);
pub const SIGMA_POR_PASSO: f64 = 0.008;
pub const COMPRESSAO_PERIFERIA: f64 = 0.25;
pub const GAMMA: f64 = 0.8;
pub const MAX_ROTULOS: usize = 40;
pub const LIMITE_ROTULO: usize = 26;
pub const MINIMO_NOS: usize = 5;
pub const RESOLUCAO: f64 = 4.0;
pub const ITERACOES: usize = 600;
const SEMENTE: u64 = 3;

const PARADAS: [(f64, [f64; 3]); 7] = [
    (0.0, [255.0, 255.0, 255.0]),
    (0.04, [236.0, 242.0, 250.0]),
    (0.15, [120.0, 150.0, 215.0]),
    (0.35, [40.0, 160.0, 150.0]),
    (0.60, [110.0, 200.0, 70.0]),
    (0.85, [235.0, 225.0, 40.0]),
    (1.0, [255.0, 235.0, 20.0]),
];

/// Itens e ligações que alimentam o mapa.
#[derive(Clone, Debug, Default)]
pub struct EntradaDensidade {
    pub nos: Vec<i64>,
    pub frequencia: BTreeMap<i64, usize>,
    pub rotulos: BTreeMap<i64, String>,
    pub arestas: Vec<(i64, i64, f64)>,
    pub unidade: String,
}

impl EntradaDensidade {
    pub fn de_corpus(c: &Corpus) -> Self {
        EntradaDensidade {
            nos: c.rede.nos.clone(),
            frequencia: c.frequencia.clone(),
            rotulos: c.rede.nos.iter().map(|&n| (n, c.rotulo(n))).collect(),
            arestas: c.rede.arestas(),
            unidade: c.parametros.unidade.nome().into(),
        }
    }
    pub fn de_resultado(r: &Resultado) -> Self {
        EntradaDensidade {
            nos: r.nos.iter().map(|n| n.id).collect(),
            frequencia: r.nos.iter().map(|n| (n.id, n.frequencia)).collect(),
            rotulos: r.nos.iter().map(|n| (n.id, n.rotulo.clone())).collect(),
            arestas: r.arestas.iter().map(|a| (a.a, a.b, a.peso)).collect(),
            unidade: r.parametros.unidade.nome().into(),
        }
    }
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct DadosDensidade {
    pub nos: Vec<i64>,
    pub x: Vec<f64>,
    pub y: Vec<f64>,
    pub pesos: Vec<f64>,
    #[serde(skip)]
    pub densidade: Vec<Vec<f64>>,
    pub sigma: f64,
    pub total: usize,
    pub suavizacao: usize,
    pub topo: usize,
    pub largura: f64,
    pub altura: f64,
    pub aviso: Option<String>,
}

/// Posições 2D minimizando Σ s_ij d_ij² − c Σ ln d_ij (descida com momento).
pub fn layout_vos(sim: &[Vec<f64>], iteracoes: usize, semente: u64) -> Vec<[f64; 2]> {
    let n = sim.len();
    let mut rng = Aleatorio(semente);
    let mut x: Vec<[f64; 2]> = (0..n).map(|_| [rng.normal(), rng.normal()]).collect();
    let soma: f64 = sim.iter().map(|l| l.iter().sum::<f64>()).sum();
    let norm = if soma > 0.0 { soma / (n * (n - 1)) as f64 } else { 1.0 };
    let s: Vec<Vec<f64>> = sim.iter().map(|l| l.iter().map(|v| (v / norm).min(25.0)).collect()).collect();
    let c = 4.0;
    let maxlin = s.iter().map(|l| l.iter().sum::<f64>()).fold(0.0f64, f64::max).max(1.0);
    let lipschitz = 8.0 * maxlin / n as f64;
    let passo = 0.05f64.min(1.0 / lipschitz);
    let mut v = vec![[0.0f64; 2]; n];
    for _ in 0..iteracoes {
        let mut g = vec![[0.0f64; 2]; n];
        for i in 0..n {
            let (mut gx, mut gy) = (0.0, 0.0);
            for j in 0..n {
                let dx = x[i][0] - x[j][0];
                let dy = x[i][1] - x[j][1];
                let d2 = dx * dx + dy * dy + 1e-6;
                gx += 4.0 * s[i][j] * dx - 2.0 * c * dx / d2;
                gy += 4.0 * s[i][j] * dy - 2.0 * c * dy / d2;
            }
            g[i] = [gx / n as f64, gy / n as f64];
        }
        for i in 0..n {
            v[i][0] = 0.8 * v[i][0] - passo * g[i][0];
            v[i][1] = 0.8 * v[i][1] - passo * g[i][1];
            let norma = (v[i][0] * v[i][0] + v[i][1] * v[i][1]).sqrt();
            if norma > 0.5 {
                let f = 0.5 / norma.max(1e-12);
                v[i][0] *= f;
                v[i][1] *= f;
            }
            x[i][0] += v[i][0];
            x[i][1] += v[i][1];
        }
        let mx = x.iter().map(|p| p[0]).sum::<f64>() / n as f64;
        let my = x.iter().map(|p| p[1]).sum::<f64>() / n as f64;
        for p in x.iter_mut() {
            p[0] -= mx;
            p[1] -= my;
        }
    }
    x
}

fn mediana(v: &[f64]) -> f64 {
    let mut s = v.to_vec();
    s.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = s.len();
    if n % 2 == 1 {
        s[n / 2]
    } else {
        (s[n / 2 - 1] + s[n / 2]) / 2.0
    }
}

/// `numpy.percentile` (interpolação linear).
fn percentil(v: &[f64], q: f64) -> f64 {
    let mut s = v.to_vec();
    s.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let pos = (s.len() - 1) as f64 * q / 100.0;
    let lo = pos.floor() as usize;
    let hi = (lo + 1).min(s.len() - 1);
    s[lo] + (s[hi] - s[lo]) * (pos - lo as f64)
}

fn linspace(fim: f64, n: usize) -> Vec<f64> {
    if n == 1 {
        return vec![0.0];
    }
    (0..n).map(|i| fim * i as f64 / (n - 1) as f64).collect()
}

/// Posições, pesos e grade de densidade (sem desenhar).
pub fn calcula(e: &EntradaDensidade, topo: usize, suavizacao: usize) -> DadosDensidade {
    let topo = topo.clamp(LIMITE_NOS.0, LIMITE_NOS.1);
    let suavizacao = suavizacao.clamp(LIMITE_SUAVIZACAO.0, LIMITE_SUAVIZACAO.1);
    let largura = LARGURA - 2.0 * MARGEM_QUADRO;
    let altura = ALTURA_QUADRO;
    let mut ordem: Vec<i64> = e.nos.clone();
    ordem.sort_by(|a, b| {
        let fa = e.frequencia.get(a).copied().unwrap_or(0) as i64;
        let fb = e.frequencia.get(b).copied().unwrap_or(0) as i64;
        let la = limpa(e.rotulos.get(a).map(|s| s.as_str()).unwrap_or(""));
        let lb = limpa(e.rotulos.get(b).map(|s| s.as_str()).unwrap_or(""));
        (-fa, la, a.to_string()).cmp(&(-fb, lb, b.to_string()))
    });
    let nos: Vec<i64> = ordem.iter().copied().take(topo).collect();
    let n = nos.len();
    let vazio = DadosDensidade { total: ordem.len(), suavizacao, topo, largura, altura, ..Default::default() };
    if n < MINIMO_NOS {
        return DadosDensidade {
            aviso: Some(format!("Poucos itens na rede ({n}) para um mapa de densidade (mínimo de {MINIMO_NOS}).")),
            ..vazio
        };
    }
    let pos: BTreeMap<i64, usize> = nos.iter().enumerate().map(|(i, &x)| (x, i)).collect();
    let mut s = vec![vec![0.0f64; n]; n];
    for &(a, b, v) in &e.arestas {
        if let (Some(&i), Some(&j)) = (pos.get(&a), pos.get(&b)) {
            if a != b && v > 0.0 {
                let m = s[i][j].max(v);
                s[i][j] = m;
                s[j][i] = m;
            }
        }
    }
    let maximo = s.iter().flat_map(|l| l.iter()).cloned().fold(0.0f64, f64::max);
    if maximo <= 0.0 {
        return DadosDensidade {
            aviso: Some("Os itens mais frequentes não têm ligações entre si; não há como posicioná-los.".into()),
            ..vazio
        };
    }
    for l in s.iter_mut() {
        for v in l.iter_mut() {
            *v /= maximo;
        }
    }
    let mut x = layout_vos(&s, ITERACOES, SEMENTE);
    let centro = [mediana(&x.iter().map(|p| p[0]).collect::<Vec<_>>()), mediana(&x.iter().map(|p| p[1]).collect::<Vec<_>>())];
    let dist: Vec<f64> = x.iter().map(|p| ((p[0] - centro[0]).powi(2) + (p[1] - centro[1]).powi(2)).sqrt()).collect();
    let raio = 1.3 * percentil(&dist, 85.0);
    if raio > 0.0 {
        for (p, &d) in x.iter_mut().zip(&dist) {
            let nova = if d > raio { raio + (d - raio) * COMPRESSAO_PERIFERIA } else { d };
            let f = nova / d.max(1e-12);
            p[0] = centro[0] + (p[0] - centro[0]) * f;
            p[1] = centro[1] + (p[1] - centro[1]) * f;
        }
    }
    let (minx, maxx) = x.iter().fold((f64::MAX, f64::MIN), |a, p| (a.0.min(p[0]), a.1.max(p[0])));
    let (miny, maxy) = x.iter().fold((f64::MAX, f64::MIN), |a, p| (a.0.min(p[1]), a.1.max(p[1])));
    let amp = [(maxx - minx).max(1e-9), (maxy - miny).max(1e-9)];
    let util = [largura - 2.0 * MARGEM_NOS, altura - 2.0 * MARGEM_NOS];
    let esc = (util[0] / amp[0]).min(util[1] / amp[1]);
    let (cx, cy) = ((maxx + minx) / 2.0, (maxy + miny) / 2.0);
    let px: Vec<f64> = x.iter().map(|p| (p[0] - cx) * esc + largura / 2.0).collect();
    let py: Vec<f64> = x.iter().map(|p| (p[1] - cy) * esc + altura / 2.0).collect();
    let pesos: Vec<f64> = nos.iter().map(|no| e.frequencia.get(no).copied().unwrap_or(1).max(1) as f64).collect();
    let sigma = suavizacao as f64 * SIGMA_POR_PASSO * largura;
    let (colunas, linhas) = ((largura / RESOLUCAO).floor() as usize, (altura / RESOLUCAO).floor() as usize);
    let gx = linspace(largura, colunas);
    let gy = linspace(altura, linhas);
    let kx: Vec<Vec<f64>> = px.iter().map(|&p| gx.iter().map(|&g| (-((g - p).powi(2)) / (2.0 * sigma * sigma)).exp()).collect()).collect();
    let ky: Vec<Vec<f64>> = py.iter().map(|&p| gy.iter().map(|&g| (-((g - p).powi(2)) / (2.0 * sigma * sigma)).exp()).collect()).collect();
    let mut dens = vec![vec![0.0f64; colunas]; linhas];
    for i in 0..n {
        for r in 0..linhas {
            let w = ky[i][r] * pesos[i];
            if w < 1e-300 {
                continue;
            }
            for c in 0..colunas {
                dens[r][c] += w * kx[i][c];
            }
        }
    }
    let m = dens.iter().flat_map(|l| l.iter()).cloned().fold(0.0f64, f64::max);
    if m > 0.0 {
        for l in dens.iter_mut() {
            for v in l.iter_mut() {
                *v /= m;
            }
        }
    }
    DadosDensidade { nos, x: px, y: py, pesos, densidade: dens, sigma, total: ordem.len(), suavizacao, topo, largura, altura, aviso: None }
}

// ------------------------------------------------------------------ imagem

pub fn mapa_de_cores(t: f64) -> [u8; 3] {
    let t = t.clamp(0.0, 1.0);
    let mut saida = [0.0f64; 3];
    for w in PARADAS.windows(2) {
        let ((a, ca), (b, cb)) = (w[0], w[1]);
        if t >= a && t <= b {
            let f = (t - a) / (b - a);
            for k in 0..3 {
                saida[k] = ca[k] * (1.0 - f) + cb[k] * f;
            }
        }
    }
    [saida[0].round_ties_even() as u8, saida[1].round_ties_even() as u8, saida[2].round_ties_even() as u8]
}

fn crc32(dados: &[u8]) -> u32 {
    let mut tabela = [0u32; 256];
    for n in 0..256u32 {
        let mut c = n;
        for _ in 0..8 {
            c = if c & 1 != 0 { 0xedb88320 ^ (c >> 1) } else { c >> 1 };
        }
        tabela[n as usize] = c;
    }
    let mut c = 0xffffffffu32;
    for &b in dados {
        c = tabela[((c ^ b as u32) & 0xff) as usize] ^ (c >> 8);
    }
    c ^ 0xffffffff
}

/// PNG RGB de 8 bits a partir de linhas de pixels.
pub fn png_rgb(img: &[Vec<[u8; 3]>]) -> Vec<u8> {
    let h = img.len();
    let w = img[0].len();
    let mut bruto = Vec::with_capacity(h * (3 * w + 1));
    for l in img {
        bruto.push(0u8);
        for p in l {
            bruto.extend_from_slice(p);
        }
    }
    let mut enc = flate2::write::ZlibEncoder::new(Vec::new(), flate2::Compression::best());
    enc.write_all(&bruto).unwrap();
    let comprimido = enc.finish().unwrap();
    let bloco = |tipo: &[u8; 4], dados: &[u8]| -> Vec<u8> {
        let mut corpo = tipo.to_vec();
        corpo.extend_from_slice(dados);
        let mut s = (dados.len() as u32).to_be_bytes().to_vec();
        s.extend_from_slice(&corpo);
        s.extend_from_slice(&crc32(&corpo).to_be_bytes());
        s
    };
    let mut ihdr = Vec::new();
    ihdr.extend_from_slice(&(w as u32).to_be_bytes());
    ihdr.extend_from_slice(&(h as u32).to_be_bytes());
    ihdr.extend_from_slice(&[8, 2, 0, 0, 0]);
    let mut png = b"\x89PNG\r\n\x1a\n".to_vec();
    png.extend(bloco(b"IHDR", &ihdr));
    png.extend(bloco(b"IDAT", &comprimido));
    png.extend(bloco(b"IEND", &[]));
    png
}

pub fn base64(dados: &[u8]) -> String {
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut s = String::with_capacity(dados.len() * 4 / 3 + 4);
    for c in dados.chunks(3) {
        let b = [c[0], *c.get(1).unwrap_or(&0), *c.get(2).unwrap_or(&0)];
        let n = (b[0] as u32) << 16 | (b[1] as u32) << 8 | b[2] as u32;
        s.push(T[(n >> 18) as usize & 63] as char);
        s.push(T[(n >> 12) as usize & 63] as char);
        s.push(if c.len() > 1 { T[(n >> 6) as usize & 63] as char } else { '=' });
        s.push(if c.len() > 2 { T[n as usize & 63] as char } else { '=' });
    }
    s
}

// ------------------------------------------------------------------ rótulos

fn fonte(peso: f64, maximo: f64) -> f64 {
    11.0 + 7.0 * (peso / maximo).sqrt()
}

/// Rótulos por ordem de frequência, sem sobreposição e inteiros dentro de `caixa`.
/// Devolve (índice, largura da caixa, altura da caixa, tamanho da fonte).
pub fn escolhe_rotulos(textos: &[String], x: &[f64], y: &[f64], pesos: &[f64], caixa: (f64, f64, f64, f64), maximo: usize) -> Vec<(usize, f64, f64, f64)> {
    let (x0, y0, x1, y1) = caixa;
    let pmax = pesos.iter().cloned().fold(0.0f64, f64::max);
    let pmax = if pmax == 0.0 { 1.0 } else { pmax };
    let mut ocupadas: Vec<(f64, f64, f64, f64)> = Vec::new();
    let mut escolhidos = Vec::new();
    let mut ordem: Vec<usize> = (0..textos.len()).collect();
    ordem.sort_by(|&a, &b| pesos[b].partial_cmp(&pesos[a]).unwrap().then(a.cmp(&b)));
    for i in ordem {
        let fs = fonte(pesos[i], pmax);
        let larg = largura(&textos[i], fs, false) * 1.06 + 8.0;
        let alt = fs + 5.0;
        let b = (x[i] - larg / 2.0, y[i] - alt / 2.0, x[i] + larg / 2.0, y[i] + alt / 2.0);
        if b.0 < x0 + 4.0 || b.2 > x1 - 4.0 || b.1 < y0 + 4.0 || b.3 > y1 - 4.0 {
            continue;
        }
        if ocupadas.iter().any(|c| !(b.2 < c.0 || b.0 > c.2 || b.3 < c.1 || b.1 > c.3)) {
            continue;
        }
        ocupadas.push(b);
        escolhidos.push((i, larg, alt, fs));
        if escolhidos.len() >= maximo {
            break;
        }
    }
    escolhidos
}

fn corta(texto: &str, limite: usize) -> String {
    curto(texto, limite)
}

fn nome_unidade_minusculo(u: &str) -> &str {
    match u {
        "Words" => "palavras-chave",
        "Authors" => "autores",
        "References" => "referências",
        "AuthorsReference" => "autores citados",
        "ReferenceSources" => "fontes citadas",
        "Countries" => "países",
        "Institutions" => "instituições",
        _ => "itens",
    }
}

/// Mapa de densidade em SVG ("" quando não há o que desenhar). `titulo` vazio: sem faixa de título.
pub fn svg(e: &EntradaDensidade, dados: &DadosDensidade, titulo: &str, rotulos_max: usize) -> String {
    let d = dados;
    if d.nos.is_empty() {
        return String::new();
    }
    let (larg_q, alt_q) = (d.largura, d.altura);
    let topo_q = if titulo.is_empty() { 12.0 } else { TOPO_TITULO };
    let altura_total = topo_q + alt_q + RODAPE;
    let (qx, qy) = (MARGEM_QUADRO, topo_q);
    let textos_cheios: Vec<String> = d
        .nos
        .iter()
        .map(|no| {
            let t = limpa(e.rotulos.get(no).map(|s| s.as_str()).unwrap_or(""));
            if t.is_empty() {
                no.to_string()
            } else {
                t
            }
        })
        .collect();
    let textos: Vec<String> = textos_cheios.iter().map(|t| corta(t, LIMITE_ROTULO)).collect();
    let xs: Vec<f64> = d.x.iter().map(|v| v + qx).collect();
    let ys: Vec<f64> = d.y.iter().map(|v| v + qy).collect();
    let escolhidos = escolhe_rotulos(&textos, &xs, &ys, &d.pesos, (qx, qy, qx + larg_q, qy + alt_q), rotulos_max);
    let img: Vec<Vec<[u8; 3]>> =
        d.densidade.iter().map(|l| l.iter().map(|v| mapa_de_cores(v.powf(GAMMA))).collect()).collect();
    let uri = format!("data:image/png;base64,{}", base64(&png_rgb(&img)));
    let p = format!("dn{}", hash8(&format!("{:?}{}|{}|{}", textos, d.suavizacao, d.nos.len(), titulo)));
    let nome = nome_unidade_minusculo(&e.unidade);
    let resumo = format!(
        "Mapa de densidade de {}: {} itens mais frequentes; as áreas mais quentes concentram itens frequentes e fortemente ligados.",
        nome,
        d.nos.len()
    );
    let mut o: Vec<String> = Vec::new();
    o.push(format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 {w} {h}\" width=\"{w}\" height=\"{h}\" font-family=\"{f}\" role=\"img\" \
         aria-labelledby=\"{p}-t {p}-d\"><title id=\"{p}-t\">{t}</title><desc id=\"{p}-d\">{r}</desc>",
        w = LARGURA as i64,
        h = fmt_g(altura_total),
        f = FONTE_INTER,
        p = p,
        t = esc_limpo(if titulo.is_empty() { "Mapa de densidade" } else { titulo }),
        r = esc_limpo(&resumo)
    ));
    o.push(format!("<rect width=\"{}\" height=\"{}\" fill=\"#fff\"/>", LARGURA as i64, fmt_g(altura_total)));
    if !titulo.is_empty() {
        o.push(format!(
            "<text x=\"{}\" y=\"30\" font-size=\"16\" font-weight=\"700\" fill=\"{}\">{}</text>",
            qx as i64,
            TINTA,
            esc_limpo(&curto(&limpa(titulo), 110))
        ));
    }
    o.push(format!(
        "<image href=\"{}\" x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" preserveAspectRatio=\"none\"/>",
        uri,
        qx as i64,
        fmt_g(qy),
        fmt_g(larg_q),
        fmt_g(alt_q)
    ));
    o.push(format!(
        "<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"none\" stroke=\"#CBD5E1\" stroke-width=\"1\"/>",
        qx as i64,
        fmt_g(qy),
        fmt_g(larg_q),
        fmt_g(alt_q)
    ));
    for (x, y) in d.x.iter().zip(&d.y) {
        o.push(format!("<circle cx=\"{:.1}\" cy=\"{:.1}\" r=\"1.8\" fill=\"{}\" fill-opacity=\".38\"/>", x + qx, y + qy, TINTA));
    }
    for &(i, _l, _a, fs) in &escolhidos {
        let (x, y) = (d.x[i] + qx, d.y[i] + qy);
        o.push(format!(
            "<text x=\"{:.1}\" y=\"{:.1}\" text-anchor=\"middle\" font-size=\"{:.1}\" fill=\"{}\" stroke=\"#fff\" stroke-width=\"3\" \
             paint-order=\"stroke\" stroke-linejoin=\"round\" stroke-opacity=\".75\"><title>{} — {} documentos</title>{}</text>",
            x,
            y + fs * 0.35,
            fs,
            TINTA,
            esc_limpo(&textos_cheios[i]),
            d.pesos[i] as i64,
            esc_limpo(&textos[i])
        ));
    }
    let ly = qy + alt_q + 20.0;
    let paradas: String = PARADAS
        .iter()
        .map(|(a, c)| format!("<stop offset=\"{}\" stop-color=\"rgb({},{},{})\"/>", fmt_g(*a), c[0] as i64, c[1] as i64, c[2] as i64))
        .collect();
    o.push(format!("<defs><linearGradient id=\"{p}-g\" x1=\"0\" x2=\"1\" y1=\"0\" y2=\"0\">{paradas}</linearGradient></defs>"));
    o.push(format!(
        "<rect x=\"{}\" y=\"{}\" width=\"220\" height=\"10\" rx=\"2\" fill=\"url(#{p}-g)\" stroke=\"#CBD5E1\" stroke-width=\".8\"/>",
        qx as i64,
        fmt_g(ly)
    ));
    o.push(format!("<text x=\"{}\" y=\"{}\" font-size=\"11\" fill=\"{}\">menor densidade</text>", qx as i64, fmt_g(ly + 25.0), TINTA_FRACA));
    o.push(format!(
        "<text x=\"{}\" y=\"{}\" font-size=\"11\" text-anchor=\"end\" fill=\"{}\">maior densidade</text>",
        (qx + 220.0) as i64,
        fmt_g(ly + 25.0),
        TINTA_FRACA
    ));
    o.push(format!(
        "<text x=\"{}\" y=\"{}\" font-size=\"11\" text-anchor=\"end\" fill=\"{}\">{} de {} {} · {} rótulos · suavização {}</text>",
        fmt_g(qx + larg_q),
        fmt_g(ly + 9.0),
        TINTA_FRACA,
        d.nos.len(),
        d.total,
        esc(nome),
        escolhidos.len(),
        d.suavizacao
    ));
    o.push("</svg>".into());
    o.join("\n")
}

/// Atalho: dados e SVG do corpus completo.
pub fn do_corpus(c: &Corpus, titulo: &str, topo: usize, suavizacao: usize) -> (DadosDensidade, String) {
    let e = EntradaDensidade::de_corpus(c);
    let d = calcula(&e, topo, suavizacao);
    let s = svg(&e, &d, titulo, MAX_ROTULOS);
    (d, s)
}
