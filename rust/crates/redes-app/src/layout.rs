//! Posicionamento do grafo (Fruchterman-Reingold determinístico).
//! Devolve coordenadas normalizadas em [0, 1] x [0, 1].

use crate::modelo::Resultado;

pub fn posicoes(r: &Resultado, iteracoes: usize) -> Vec<(f32, f32)> {
    let n = r.nos.len();
    if n == 0 {
        return vec![];
    }
    if n == 1 {
        return vec![(0.5, 0.5)];
    }
    let ng = r.grupos.len().max(1);
    // Início: grupos num círculo, nós numa espiral pequena ao redor do centro do grupo.
    let mut pos: Vec<(f32, f32)> = vec![(0.0, 0.0); n];
    let mut contagem = vec![0usize; ng];
    for (i, no) in r.nos.iter().enumerate() {
        let g = no.grupo.min(ng - 1);
        let ang = g as f32 / ng as f32 * std::f32::consts::TAU;
        let (cx, cy) = (0.5 + 0.32 * ang.cos(), 0.5 + 0.32 * ang.sin());
        let k = contagem[g];
        contagem[g] += 1;
        let a2 = k as f32 * 2.399963;
        let rr = 0.06 + 0.02 * k as f32;
        pos[i] = (cx + rr * a2.cos(), cy + rr * a2.sin());
    }
    let area = 1.0f32;
    let k = (area / n as f32).sqrt();
    let mut temp = 0.1f32;
    let resfria = temp / (iteracoes.max(1) as f32 + 1.0);
    for _ in 0..iteracoes {
        let mut desl = vec![(0.0f32, 0.0f32); n];
        for i in 0..n {
            for j in i + 1..n {
                let (dx, dy) = (pos[i].0 - pos[j].0, pos[i].1 - pos[j].1);
                let d = (dx * dx + dy * dy).sqrt().max(1e-4);
                let f = 2.2 * k * k / d;
                let (fx, fy) = (dx / d * f, dy / d * f);
                desl[i].0 += fx;
                desl[i].1 += fy;
                desl[j].0 -= fx;
                desl[j].1 -= fy;
            }
        }
        for a in &r.arestas {
            let (dx, dy) = (pos[a.a].0 - pos[a.b].0, pos[a.a].1 - pos[a.b].1);
            let d = (dx * dx + dy * dy).sqrt().max(1e-4);
            // Arestas dentro do grupo puxam mais; entre grupos, menos.
            let mesmo = r.nos[a.a].grupo == r.nos[a.b].grupo;
            let f = d * d / k * if mesmo { 0.6 } else { 0.05 } * (1.0 + 0.1 * a.peso as f32).min(2.0);
            let (fx, fy) = (dx / d * f, dy / d * f);
            desl[a.a].0 -= fx;
            desl[a.a].1 -= fy;
            desl[a.b].0 += fx;
            desl[a.b].1 += fy;
        }
        for i in 0..n {
            // Gravidade leve para o centro.
            desl[i].0 += (0.5 - pos[i].0) * 2.5 * k;
            desl[i].1 += (0.5 - pos[i].1) * 2.5 * k;
            let d = (desl[i].0 * desl[i].0 + desl[i].1 * desl[i].1).sqrt().max(1e-6);
            let m = d.min(temp);
            pos[i].0 += desl[i].0 / d * m;
            pos[i].1 += desl[i].1 / d * m;
        }
        temp = (temp - resfria).max(0.002);
    }
    normalizar(&mut pos);
    pos
}

/// Normaliza para [0, 1]. Com muitos nós, ignora os 3% extremos de cada lado ao
/// escolher a caixa (e prende os que passam), para que componentes isolados
/// não achatem o restante do desenho.
fn normalizar(pos: &mut [(f32, f32)]) {
    fn limites(mut v: Vec<f32>) -> (f32, f32) {
        v.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let corte = if v.len() >= 30 { (v.len() as f32 * 0.03) as usize } else { 0 };
        (v[corte], v[v.len() - 1 - corte])
    }
    let (x0, x1) = limites(pos.iter().map(|p| p.0).collect());
    let (y0, y1) = limites(pos.iter().map(|p| p.1).collect());
    let (sx, sy) = ((x1 - x0).max(1e-6), (y1 - y0).max(1e-6));
    for p in pos.iter_mut() {
        p.0 = ((p.0 - x0) / sx).clamp(0.0, 1.0);
        p.1 = ((p.1 - y0) / sy).clamp(0.0, 1.0);
    }
}

#[cfg(test)]
mod testes {
    use super::*;
    use crate::backend::{mock::Demonstracao, Backend};
    use crate::modelo::Parametros;

    #[test]
    fn dentro_do_quadrado_e_determinista() {
        let mut d = Demonstracao::default();
        d.abrir_demonstracao().unwrap();
        let r = d.executar(&Parametros::default()).unwrap();
        let a = posicoes(&r, 150);
        let b = posicoes(&r, 150);
        assert_eq!(a, b);
        assert_eq!(a.len(), r.nos.len());
        for p in &a {
            assert!((0.0..=1.0).contains(&p.0) && (0.0..=1.0).contains(&p.1));
            assert!(p.0.is_finite() && p.1.is_finite());
        }
    }

    #[test]
    fn casos_pequenos() {
        assert!(posicoes(&Resultado::default(), 10).is_empty());
    }

    #[test]
    fn nos_do_mesmo_grupo_ficam_mais_perto() {
        let mut d = Demonstracao::default();
        d.abrir_demonstracao().unwrap();
        let r = d.executar(&Parametros::default()).unwrap();
        let p = posicoes(&r, 200);
        let (mut dentro, mut nd, mut fora, mut nf) = (0.0f32, 0, 0.0f32, 0);
        for i in 0..p.len() {
            for j in i + 1..p.len() {
                let d = ((p[i].0 - p[j].0).powi(2) + (p[i].1 - p[j].1).powi(2)).sqrt();
                if r.nos[i].grupo == r.nos[j].grupo { dentro += d; nd += 1 } else { fora += d; nf += 1 }
            }
        }
        assert!(dentro / nd as f32 <= fora / nf as f32);
    }
}
