//! Figura da análise de similitude: grafo em halos por bloco (porta `redes/viz/similitude.py`).
//! Layout em dois níveis: cada bloco é arrumado sozinho (molas + separação de caixas) e depois os
//! blocos são dispostos entre si sem que as manchas se toquem.

use std::collections::BTreeMap;

use serde::Serialize;

use crate::nx::{spring_layout, Grafo};
use crate::similitude::{texto_parametros, Similitude};
use crate::util::{cor_do_grupo, esc_limpo, fmt_g, largura, limpa, FONTE_INTER, TINTA, TINTA_FRACA};

pub const FOLGA_TEXTO: f64 = 1.20;
pub const LARGURA_MINIMA: f64 = 680.0;
pub const MARGEM: f64 = 14.0;
pub const FOLGA_HALO: f64 = 20.0;
pub const RAIO_MIN: f64 = 4.5;
pub const RAIO_MAX: f64 = 14.0;
pub const FONTE_MIN: f64 = 11.5;
pub const FONTE_MAX: f64 = 20.5;
pub const LARGURA_COLUNA_LEGENDA: f64 = 280.0;
pub const SEMENTE_LAYOUT: u32 = 3;

#[derive(Clone, Debug, Serialize)]
pub struct NoPos {
    pub id: String,
    pub r: f64,
    pub fs: f64,
    pub tw: f64,
    pub txt: String,
    pub x: f64,
    pub y: f64,
    pub com: usize,
    pub freq: i64,
    pub resumos: usize,
    pub idioma: String,
}

pub fn largura_texto(texto: &str, px: f64, negrito: bool) -> f64 {
    largura(texto, px, negrito) * FOLGA_TEXTO
}

fn f1(x: f64) -> String {
    format!("{:.1}", x)
}

fn rstrip_virgula(t: &str) -> &str {
    t.trim_end_matches(|c| c == ',' || c == ' ')
}

fn cabe(texto: &str, px: f64, tamanho: f64) -> String {
    let texto = limpa(texto);
    if largura_texto(&texto, tamanho, false) <= px {
        return texto;
    }
    let mut cs: Vec<char> = texto.chars().collect();
    while cs.len() > 1 {
        let s: String = cs.iter().collect();
        if largura_texto(&format!("{}…", rstrip_virgula(&s)), tamanho, false) <= px {
            break;
        }
        cs.pop();
    }
    let s: String = cs.iter().collect();
    format!("{}…", rstrip_virgula(&s))
}

fn quebra(texto: &str, px: f64, tamanho: f64) -> Vec<String> {
    let mut linhas = vec![];
    let mut atual = String::new();
    for palavra in limpa(texto).split_whitespace() {
        let teste = format!("{atual} {palavra}").trim().to_string();
        if !atual.is_empty() && largura_texto(&teste, tamanho, false) > px {
            linhas.push(std::mem::take(&mut atual));
            atual = palavra.to_string();
        } else {
            atual = teste;
        }
    }
    if !atual.is_empty() {
        linhas.push(atual);
    }
    linhas
}

fn hull(pts: &[(f64, f64)]) -> Vec<(f64, f64)> {
    let mut p: Vec<(f64, f64)> = pts.to_vec();
    p.sort_by(|a, b| a.partial_cmp(b).unwrap());
    p.dedup();
    if p.len() <= 2 {
        return p;
    }
    let cross = |o: (f64, f64), a: (f64, f64), b: (f64, f64)| (a.0 - o.0) * (b.1 - o.1) - (a.1 - o.1) * (b.0 - o.0);
    let mut lo: Vec<(f64, f64)> = vec![];
    let mut up: Vec<(f64, f64)> = vec![];
    for &q in &p {
        while lo.len() >= 2 && cross(lo[lo.len() - 2], lo[lo.len() - 1], q) <= 0.0 {
            lo.pop();
        }
        lo.push(q);
    }
    for &q in p.iter().rev() {
        while up.len() >= 2 && cross(up[up.len() - 2], up[up.len() - 1], q) <= 0.0 {
            up.pop();
        }
        up.push(q);
    }
    lo.pop();
    up.pop();
    lo.extend(up);
    lo
}

/// Raio, fonte e largura do rótulo de cada forma (posição ainda zerada).
pub fn tamanhos(res: &Similitude) -> Vec<NoPos> {
    let fmin = res.formas.iter().map(|f| f.frequencia).min().unwrap();
    let fmax = res.formas.iter().map(|f| f.frequencia).max().unwrap();
    res.formas
        .iter()
        .map(|f| {
            let t = ((f.frequencia - fmin) as f64 / ((fmax - fmin).max(1)) as f64).sqrt();
            let r = RAIO_MIN + (RAIO_MAX - RAIO_MIN) * t;
            let fs = FONTE_MIN + (FONTE_MAX - FONTE_MIN) * t;
            let txt = limpa(&f.forma);
            NoPos {
                id: f.id.clone(),
                r,
                fs,
                tw: largura_texto(&txt, fs, false),
                txt,
                x: 0.0,
                y: 0.0,
                com: f.comunidade,
                freq: f.frequencia,
                resumos: f.resumos,
                idioma: f.idioma.clone(),
            }
        })
        .collect()
}

fn caixa(d: &NoPos, folga: f64) -> (f64, f64, f64, f64) {
    let h = (2.0 * d.r).max(1.25 * d.fs) + 2.0 * folga;
    (d.x - d.r - folga, d.y - h / 2.0, d.x + d.r + 4.0 + d.tw + folga, d.y + h / 2.0)
}

fn remove_sobreposicao(nos: &mut [NoPos], ids: &[usize], iters: usize) {
    for _ in 0..iters {
        let mut moveu = false;
        for (i, &ia) in ids.iter().enumerate() {
            let mut ba = caixa(&nos[ia], 3.0);
            for &ib in &ids[i + 1..] {
                let bb = caixa(&nos[ib], 3.0);
                let dx = ba.2.min(bb.2) - ba.0.max(bb.0);
                let dy = ba.3.min(bb.3) - ba.1.max(bb.1);
                if dx > 0.0 && dy > 0.0 {
                    moveu = true;
                    if dy * 1.6 < dx {
                        let s = if nos[ia].y < nos[ib].y || (nos[ia].y == nos[ib].y && nos[ia].id < nos[ib].id) { 1.0 } else { -1.0 };
                        nos[ia].y -= s * (dy / 2.0 + 0.5);
                        nos[ib].y += s * (dy / 2.0 + 0.5);
                    } else {
                        let s = if (ba.0 + ba.2) <= (bb.0 + bb.2) { 1.0 } else { -1.0 };
                        nos[ia].x -= s * (dx / 2.0 + 0.5);
                        nos[ib].x += s * (dx / 2.0 + 0.5);
                    }
                    ba = caixa(&nos[ia], 3.0);
                }
            }
        }
        if !moveu {
            break;
        }
    }
}

fn matriz(g: &Grafo) -> Vec<Vec<f64>> {
    let n = g.n();
    let mut a = vec![vec![0.0; n]; n];
    for u in 0..n {
        for (&v, &w) in &g.adj[u] {
            a[u][v] = w;
        }
    }
    a
}

/// Liga os pedaços desconexos pelo primeiro nó de cada um (peso `w`), como o Python.
fn liga_pedacos(g: &mut Grafo, w: f64) {
    let mut pedacos: Vec<Vec<usize>> = g
        .componentes()
        .into_iter()
        .map(|mut c| {
            c.sort();
            c
        })
        .collect();
    pedacos.sort_by_key(|p| p[0]);
    for par in pedacos.windows(2) {
        g.add_aresta(par[0][0], par[1][0], w);
    }
}

struct Bloco {
    mem: Vec<usize>,
    r: f64,
}

/// Posição de cada forma (mesma ordem de `res.formas`).
pub fn layout(res: &Similitude, usa_extras: bool, semente: u32) -> Vec<NoPos> {
    let mut nos = tamanhos(res);
    let pos_de: std::collections::HashMap<&str, usize> =
        res.formas.iter().enumerate().map(|(k, f)| (f.id.as_str(), k)).collect();
    let com: Vec<usize> = nos.iter().map(|d| d.com).collect();
    let cids: Vec<usize> = {
        let mut v: Vec<usize> = com.clone();
        v.sort();
        v.dedup();
        v
    };
    let arvore: Vec<(usize, usize)> = res
        .arestas
        .iter()
        .filter(|a| a.tipo == "arvore")
        .map(|a| (pos_de[a.origem.as_str()], pos_de[a.destino.as_str()]))
        .collect();
    let extras: Vec<(usize, usize)> = if usa_extras {
        res.arestas
            .iter()
            .filter(|a| a.tipo == "extra")
            .map(|a| (pos_de[a.origem.as_str()], pos_de[a.destino.as_str()]))
            .collect()
    } else {
        vec![]
    };
    let mut blocos: BTreeMap<usize, Bloco> = BTreeMap::new();
    for &c in &cids {
        // membros ordenados por id (texto)
        let mut mem: Vec<usize> = (0..nos.len()).filter(|&i| com[i] == c).collect();
        mem.sort_by(|&a, &b| nos[a].id.cmp(&nos[b].id));
        let local: std::collections::HashMap<usize, usize> = mem.iter().enumerate().map(|(k, &i)| (i, k)).collect();
        let mut h = Grafo::com_nos(mem.len());
        for &(u, v) in &arvore {
            if com[u] == c && com[v] == c {
                h.add_aresta(local[&u], local[&v], 1.0);
            }
        }
        for &(u, v) in &extras {
            if com[u] == c && com[v] == c && !h.tem_aresta(local[&u], local[&v]) {
                h.add_aresta(local[&u], local[&v], 0.35);
            }
        }
        liga_pedacos(&mut h, 0.1);
        let pos: Vec<[f64; 2]> = if mem.len() == 1 {
            vec![[0.0, 0.0]]
        } else {
            spring_layout(&matriz(&h), Some(1.5 / (mem.len() as f64).sqrt()), 300, semente)
        };
        let area: f64 = mem
            .iter()
            .map(|&i| {
                let d = &nos[i];
                (2.0 * d.r + 4.0 + d.tw) * (2.0 * d.r).max(1.25 * d.fs)
            })
            .sum();
        let l = (area * 4.5).sqrt();
        let n = mem.len() as f64;
        let media = [pos.iter().map(|p| p[0]).sum::<f64>() / n, pos.iter().map(|p| p[1]).sum::<f64>() / n];
        let ptp = |d: usize| {
            pos.iter().map(|p| p[d]).fold(f64::MIN, f64::max) - pos.iter().map(|p| p[d]).fold(f64::MAX, f64::min)
        };
        let denom = ptp(0).max(ptp(1)) / 2.0 + 1e-9;
        for (k, &i) in mem.iter().enumerate() {
            nos[i].x = (pos[k][0] - media[0]) / denom * (l / 2.0);
            nos[i].y = (pos[k][1] - media[1]) / denom * (l / 2.0);
        }
        remove_sobreposicao(&mut nos, &mem, 300);
        let caixas: Vec<(f64, f64, f64, f64)> = mem.iter().map(|&i| caixa(&nos[i], 1.0)).collect();
        let cx = (caixas.iter().map(|b| b.0).fold(f64::MAX, f64::min) + caixas.iter().map(|b| b.2).fold(f64::MIN, f64::max)) / 2.0;
        let cy = (caixas.iter().map(|b| b.1).fold(f64::MAX, f64::min) + caixas.iter().map(|b| b.3).fold(f64::MIN, f64::max)) / 2.0;
        for &i in &mem {
            nos[i].x -= cx;
            nos[i].y -= cy;
        }
        let mut rad: f64 = 0.0;
        for &i in &mem {
            let b = caixa(&nos[i], 1.0);
            for (x, y) in [(b.0, b.1), (b.2, b.1), (b.0, b.3), (b.2, b.3)] {
                rad = rad.max(x.hypot(y));
            }
        }
        blocos.insert(c, Bloco { mem, r: rad + FOLGA_HALO + 5.0 });
    }
    // grafo dos blocos
    let cpos: std::collections::HashMap<usize, usize> = cids.iter().enumerate().map(|(k, &c)| (c, k)).collect();
    let mut s = Grafo::com_nos(cids.len());
    for &(u, v) in arvore.iter().chain(extras.iter()) {
        let (a, b) = (com[u], com[v]);
        if a != b {
            let (a, b) = (cpos[&a], cpos[&b]);
            let w = s.peso(a, b).unwrap_or(0.0) + 1.0;
            s.add_aresta(a, b, w);
        }
    }
    let sp: Vec<[f64; 2]> = if cids.len() == 1 {
        vec![[0.0, 0.0]]
    } else {
        let mut s2 = s.clone();
        liga_pedacos(&mut s2, 0.2);
        spring_layout(&matriz(&s2), Some(1.2), 300, semente)
    };
    let nb = cids.len() as f64;
    let media = [sp.iter().map(|p| p[0]).sum::<f64>() / nb, sp.iter().map(|p| p[1]).sum::<f64>() / nb];
    let mut p: Vec<[f64; 2]> = sp.iter().map(|q| [q[0] - media[0], q[1] - media[1]]).collect();
    let span: Vec<f64> = (0..2)
        .map(|d| p.iter().map(|q| q[d]).fold(f64::MIN, f64::max) - p.iter().map(|q| q[d]).fold(f64::MAX, f64::min) + 1e-9)
        .collect();
    for q in p.iter_mut() {
        q[0] = q[0] / span[0] * 2.0;
        q[1] = q[1] / span[1] * 2.0;
    }
    let area_tot: f64 = cids.iter().map(|c| std::f64::consts::PI * blocos[c].r.powi(2)).sum();
    let esc = (area_tot / std::f64::consts::PI).sqrt() * 0.85;
    let mut cen: Vec<[f64; 2]> = p.iter().map(|q| [q[0] * esc, q[1] * esc]).collect();
    let raios: Vec<f64> = cids.iter().map(|c| blocos[c].r).collect();
    let nc = cids.len();
    for it in 0..3000 {
        let mut moveu = false;
        for a in 0..nc {
            for b in (a + 1)..nc {
                let mut d = [cen[b][0] - cen[a][0], cen[b][1] - cen[a][1]];
                let mut dist = d[0].hypot(d[1]) + 1e-9;
                if dist == 1e-9 {
                    d = [1.0, 0.0];
                    dist = 1.0;
                }
                let need = raios[a] + raios[b];
                if dist < need {
                    moveu = true;
                    let push = [d[0] / dist * (need - dist) / 2.0 * 1.02, d[1] / dist * (need - dist) / 2.0 * 1.02];
                    cen[a][0] -= push[0];
                    cen[a][1] -= push[1];
                    cen[b][0] += push[0];
                    cen[b][1] += push[1];
                }
            }
        }
        for c in cen.iter_mut() {
            c[0] -= c[0] * 0.01;
            c[1] -= c[1] * 0.01;
        }
        for (a, b, w) in s.arestas() {
            let d = [cen[b][0] - cen[a][0], cen[b][1] - cen[a][1]];
            let dist = d[0].hypot(d[1]) + 1e-9;
            let need = raios[a] + raios[b];
            if dist > need {
                let f = (dist - need).min(6.0) * 0.06 * w.min(6.0);
                let pull = [d[0] / dist * f, d[1] / dist * f];
                cen[a][0] += pull[0];
                cen[a][1] += pull[1];
                cen[b][0] -= pull[0];
                cen[b][1] -= pull[1];
            }
        }
        if !moveu && it > 400 {
            break;
        }
    }
    for _ in 0..500 {
        let mut moveu = false;
        for a in 0..nc {
            for b in (a + 1)..nc {
                let d = [cen[b][0] - cen[a][0], cen[b][1] - cen[a][1]];
                let dist = d[0].hypot(d[1]) + 1e-9;
                let need = raios[a] + raios[b];
                if dist < need - 0.01 {
                    moveu = true;
                    let u = if dist > 1e-6 { [d[0] / dist, d[1] / dist] } else { [1.0, 0.0] };
                    let push = [u[0] * (need - dist) / 2.0 * 1.02, u[1] * (need - dist) / 2.0 * 1.02];
                    cen[a][0] -= push[0];
                    cen[a][1] -= push[1];
                    cen[b][0] += push[0];
                    cen[b][1] += push[1];
                }
            }
        }
        if !moveu {
            break;
        }
    }
    for (k, c) in cids.iter().enumerate() {
        for &i in &blocos[c].mem {
            nos[i].x += cen[k][0];
            nos[i].y += cen[k][1];
        }
    }
    nos
}

fn titulo_bloco(id: usize, nome: &str, n: usize, idiomas: &[String], multi: bool) -> String {
    let sufixo = if multi {
        format!(" [{}]", idiomas.iter().map(|i| i.to_uppercase()).collect::<Vec<_>>().join("/"))
    } else {
        String::new()
    };
    format!("{id}. {nome} ({n}){sufixo}")
}

/// SVG da análise de similitude, ou "" quando não há o que desenhar.
pub fn svg(res: &Similitude, titulo: &str, prefixo_id: Option<&str>, mostrar_extras: bool, rodape: Option<&str>) -> String {
    if res.formas.len() < 2 {
        return String::new();
    }
    let nos = layout(res, mostrar_extras, SEMENTE_LAYOUT);
    let pos_de: std::collections::HashMap<&str, usize> =
        res.formas.iter().enumerate().map(|(k, f)| (f.id.as_str(), k)).collect();
    let mut ids_com: Vec<usize> = nos.iter().map(|d| d.com).collect();
    ids_com.sort();
    ids_com.dedup();
    let cor = |c: usize| cor_do_grupo(ids_com.iter().position(|&x| x == c).unwrap());
    let arvore: Vec<_> = res.arestas.iter().filter(|a| a.tipo == "arvore").collect();
    let extras: Vec<_> = if mostrar_extras { res.arestas.iter().filter(|a| a.tipo == "extra").collect() } else { vec![] };
    let wmax = arvore.iter().chain(extras.iter()).map(|a| a.peso).fold(1e-9, f64::max);
    let p = prefixo_id.unwrap_or("sim");

    let mut halos: Vec<(usize, Vec<(f64, f64)>)> = vec![];
    for &c in &ids_com {
        let mut pts = vec![];
        for d in nos.iter().filter(|d| d.com == c) {
            let (x0, y0, x1, y1) = caixa(d, 1.0);
            pts.extend([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]);
        }
        halos.push((c, hull(&pts)));
    }
    let (mut gx0, mut gx1, mut gy0, mut gy1) = (f64::MAX, f64::MIN, f64::MAX, f64::MIN);
    for (_, h) in &halos {
        for &(x, y) in h {
            gx0 = gx0.min(x - FOLGA_HALO - 1.0);
            gx1 = gx1.max(x + FOLGA_HALO + 1.0);
            gy0 = gy0.min(y - FOLGA_HALO - 1.0);
            gy1 = gy1.max(y + FOLGA_HALO + 1.0);
        }
    }
    let m = MARGEM;
    let cx_graf = (gx0 + gx1) / 2.0;
    let larg = (gx1 - gx0 + 2.0 * m).max(LARGURA_MINIMA);
    let (vx0, vx1) = (cx_graf - larg / 2.0, cx_graf + larg / 2.0);
    let util = larg - 2.0 * m;
    let multi = res.idiomas_nas_formas.len() > 1;
    let linhas_titulo = if titulo.is_empty() { vec![] } else { quebra(titulo, util, 15.0) };
    let topo = if titulo.is_empty() { 4.0 } else { linhas_titulo.len() as f64 * 20.0 + 14.0 };
    let n_col = ((util / LARGURA_COLUNA_LEGENDA).floor() as usize).clamp(1, 4);
    let col_w = util / n_col as f64;
    let n_lin = (ids_com.len() as f64 / n_col as f64).ceil();
    let alt_leg = n_lin * 20.0 + 12.0;
    let texto_rodape = rodape.map(|s| s.to_string()).unwrap_or_else(|| texto_parametros(res));
    let linhas_rodape = quebra(&texto_rodape, util, 10.5);
    let vy0 = gy0 - topo;
    let y_leg = gy1 + m + 14.0;
    let y_rod = gy1 + m + alt_leg + 12.0;
    let vy1 = y_rod + 14.0 * linhas_rodape.len() as f64 + 2.0;
    let (wv, hv) = (vx1 - vx0, vy1 - vy0);

    let nomes6: Vec<String> = res.comunidades.iter().take(6).map(|c| c.nome.clone()).collect();
    let desc = format!(
        "Grafo de similitude com {} palavras em {} blocos, calculado sobre {} resumos. Blocos: {}.",
        res.formas.len(),
        ids_com.len(),
        res.n_resumos,
        nomes6.join("; ")
    );
    let mut o: Vec<String> = vec![];
    o.push(format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"{} {} {} {}\" width=\"{}\" height=\"{}\" font-family=\"{}\" role=\"img\" aria-labelledby=\"{p}-t {p}-d\">",
        f1(vx0), f1(vy0), f1(wv), f1(hv), f1(wv), f1(hv), FONTE_INTER
    ));
    let t_txt = if titulo.is_empty() { "Análise de similitude dos resumos" } else { titulo };
    o.push(format!("<title id=\"{p}-t\">{}</title><desc id=\"{p}-d\">{}</desc>", esc_limpo(t_txt), esc_limpo(&desc)));
    o.push(format!("<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\" fill=\"#FFFFFF\"/>", f1(vx0), f1(vy0), f1(wv), f1(hv)));
    for (k, linha) in linhas_titulo.iter().enumerate() {
        o.push(format!(
            "<text x=\"{}\" y=\"{}\" font-size=\"15\" font-weight=\"700\" fill=\"{}\">{}</text>",
            f1(vx0 + m), f1(vy0 + 22.0 + 20.0 * k as f64), TINTA, esc_limpo(linha)
        ));
    }
    o.push("<g class=\"sim-halos\">".into());
    for (c, h) in &halos {
        let pts: Vec<String> = h.iter().map(|(x, y)| format!("{},{}", f1(*x), f1(*y))).collect();
        let col = cor(*c);
        o.push(format!(
            "<g opacity=\"0.15\"><polygon points=\"{}\" fill=\"{}\" stroke=\"{}\" stroke-width=\"{}\" stroke-linejoin=\"round\"/></g>",
            pts.join(" "), col, col, fmt_g(2.0 * FOLGA_HALO)
        ));
    }
    o.push("</g>".into());
    if !extras.is_empty() {
        o.push("<g class=\"sim-extras\" stroke-linecap=\"round\">".into());
        for a in &extras {
            let (u, v) = (&nos[pos_de[a.origem.as_str()]], &nos[pos_de[a.destino.as_str()]]);
            let sw = 0.6 + 2.0 * (a.peso / wmax);
            o.push(format!(
                "<line x1=\"{}\" y1=\"{}\" x2=\"{}\" y2=\"{}\" stroke=\"#94A3B8\" stroke-opacity=\"0.6\" stroke-width=\"{:.2}\" stroke-dasharray=\"4 3\"/>",
                f1(u.x), f1(u.y), f1(v.x), f1(v.y), sw
            ));
        }
        o.push("</g>".into());
    }
    o.push("<g class=\"sim-arvore\" stroke-linecap=\"round\">".into());
    for a in &arvore {
        let (iu, iv) = (pos_de[a.origem.as_str()], pos_de[a.destino.as_str()]);
        let (u, v) = (&nos[iu], &nos[iv]);
        let sw = 0.9 + 4.1 * (a.peso / wmax);
        let col = if u.com == v.com { cor(u.com) } else { "#64748B".to_string() };
        o.push(format!(
            "<line x1=\"{}\" y1=\"{}\" x2=\"{}\" y2=\"{}\" stroke=\"{}\" stroke-opacity=\"0.8\" stroke-width=\"{:.2}\"/>",
            f1(u.x), f1(u.y), f1(v.x), f1(v.y), col, sw
        ));
    }
    o.push("</g>".into());
    o.push("<g class=\"sim-nos\">".into());
    for d in &nos {
        let rs = d.resumos;
        o.push(format!(
            "<circle cx=\"{}\" cy=\"{}\" r=\"{}\" fill=\"{}\" stroke=\"#FFFFFF\" stroke-width=\"1.5\"><title>{}: {} resumo{}{}</title></circle>",
            f1(d.x), f1(d.y), f1(d.r), cor(d.com), esc_limpo(&d.txt), rs, if rs == 1 { "" } else { "s" },
            if multi { format!(" · {}", d.idioma.to_uppercase()) } else { String::new() }
        ));
    }
    o.push("</g><g class=\"sim-rotulos\">".into());
    for d in &nos {
        o.push(format!(
            "<text class=\"rot\" x=\"{}\" y=\"{}\" font-size=\"{:.1}\" font-weight=\"500\" fill=\"{}\" stroke=\"#FFFFFF\" stroke-width=\"3\" paint-order=\"stroke\" stroke-linejoin=\"round\">{}</text>",
            f1(d.x + d.r + 4.0), f1(d.y + d.fs * 0.35), d.fs, TINTA, esc_limpo(&d.txt)
        ));
    }
    o.push("</g>".into());
    o.push("<g class=\"sim-legenda\">".into());
    for (k, &c) in ids_com.iter().enumerate() {
        let (ci, li) = (k % n_col, k / n_col);
        let x = vx0 + m + ci as f64 * col_w;
        let y = y_leg + li as f64 * 20.0;
        o.push(format!("<circle cx=\"{}\" cy=\"{}\" r=\"5\" fill=\"{}\"/>", f1(x + 5.0), f1(y - 4.0), cor(c)));
        let info = res.comunidades.iter().find(|i| i.id == c).unwrap();
        let txt = cabe(&titulo_bloco(info.id, &info.nome, info.n, &info.idiomas, multi), col_w - 24.0, 12.0);
        o.push(format!(
            "<text class=\"leg\" x=\"{}\" y=\"{}\" font-size=\"12\" fill=\"{}\">{}</text>",
            f1(x + 15.0), f1(y), TINTA, esc_limpo(&txt)
        ));
    }
    o.push("</g>".into());
    for (k, linha) in linhas_rodape.iter().enumerate() {
        o.push(format!(
            "<text class=\"rod\" x=\"{}\" y=\"{}\" font-size=\"10.5\" fill=\"{}\">{}</text>",
            f1(vx0 + m), f1(y_rod + 14.0 * k as f64), TINTA_FRACA, esc_limpo(linha)
        ));
    }
    o.push("</svg>".into());
    o.join("\n")
}
