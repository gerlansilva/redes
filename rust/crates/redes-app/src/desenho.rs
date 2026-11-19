//! Monta as cenas do grafo e do diagrama estratégico de Callon.

use crate::cena::{Alvo, Ancora, Cena, Lugar, Prim, Rotulo};
use crate::layout;
use crate::modelo::*;
use crate::tema::{cor_grupo, PALETA};

const TINTA: [u8; 4] = [0x14, 0x20, 0x4A, 0xFF];
const FRACA: [u8; 4] = [0x64, 0x74, 0x8B, 0xFF];
const LINHA: [u8; 4] = [0xDC, 0xE3, 0xF0, 0xFF];
const AZUL: [u8; 4] = [0x2F, 0x2B, 0xFF, 0xFF];

fn q_cor(q: Quadrante) -> [u8; 4] {
    let c = crate::tema::cor_quadrante(q);
    [c.r(), c.g(), c.b(), 0xFF]
}

/// Tamanho da cena interativa: cresce com o número de elementos para que 100 ou
/// mais agrupamentos tenham espaço (o zoom ajusta a vista a cada janela).
pub fn mundo(elementos: usize) -> (f32, f32) {
    let f = (elementos as f32 / 50.0).sqrt().clamp(1.0, 4.0);
    (900.0 * f, 620.0 * f)
}

/// Grafo com halo por agrupamento (cena estática, para exportar).
pub fn rede(r: &Resultado, largura: f32, altura: f32) -> Cena {
    rede_com(r, largura, altura, false)
}

/// Grafo para a tela: sem textos fixos, com rótulos por nível de detalhe.
pub fn rede_interativa(r: &Resultado) -> Cena {
    let (w, h) = mundo(r.nos.len());
    rede_com(r, w, h, true)
}

fn rede_com(r: &Resultado, largura: f32, altura: f32, interativa: bool) -> Cena {
    let mut cena = Cena::nova(largura, altura);
    if r.nos.is_empty() {
        cena.push(Prim::Texto {
            pos: (largura / 2.0, altura / 2.0), texto: "Sem dados para este período.".into(),
            tam: 14.0, cor: FRACA, ancora: Ancora::Centro, negrito: false, vertical: false,
        });
        return cena;
    }
    let margem = if interativa { 56.0 } else { (largura.min(altura) * 0.15).max(64.0) };
    let pos_n = layout::posicoes(r, 220);
    let pos: Vec<(f32, f32)> = pos_n
        .iter()
        .map(|p| (margem + p.0 * (largura - 2.0 * margem), margem + p.1 * (altura - 2.0 * margem)))
        .collect();
    let pmax = r.nos.iter().map(|n| n.peso).fold(1.0f64, f64::max);
    // Com a cena maior, os nós crescem um pouco para continuarem visíveis na vista geral.
    let k = if interativa { (largura / 900.0).powf(0.35) } else { 1.0 };
    let raio = |n: &No| k * (5.0 + 13.0 * (n.peso / pmax).sqrt() as f32);

    // Halos.
    let mut halos: Vec<(f32, f32, f32)> = Vec::new();
    for g in &r.grupos {
        let idx: Vec<usize> = r.nos.iter().filter(|n| n.grupo == g.id).map(|n| n.id).collect();
        if idx.is_empty() {
            halos.push((0.0, 0.0, 0.0));
            continue;
        }
        let (mut cx, mut cy) = (0.0, 0.0);
        for &i in &idx {
            cx += pos[i].0;
            cy += pos[i].1;
        }
        cx /= idx.len() as f32;
        cy /= idx.len() as f32;
        let rr = idx
            .iter()
            .map(|&i| ((pos[i].0 - cx).powi(2) + (pos[i].1 - cy).powi(2)).sqrt() + raio(&r.nos[i]))
            .fold(0.0f32, f32::max)
            + 14.0 * k;
        halos.push((cx, cy, rr));
        cena.push(Prim::Circulo {
            c: (cx, cy), r: rr,
            preench: Some(cor_grupo(g.id, 36)),
            borda: Some((cor_grupo(g.id, 110), 1.2)),
            dica: Some(format!("{} · {}", g.nome, g.quadrante.curto())),
            alvo: Some(Alvo::Grupo(g.id)),
        });
    }
    // Arestas.
    let pw = r.arestas.iter().map(|a| a.peso).fold(1.0f64, f64::max);
    // Com muitas ligações, esmaece-as para o desenho continuar legível.
    let densa = r.arestas.len() > 150;
    for a in &r.arestas {
        let entre = r.nos[a.a].grupo != r.nos[a.b].grupo;
        let (ae, ai) = if densa { (38, 90) } else { (150, 120) };
        cena.push(Prim::Linha {
            a: pos[a.a], b: pos[a.b],
            cor: if entre { [0x8A, 0x94, 0xA6, ae] } else { [0x64, 0x74, 0x8B, ai] },
            larg: if densa { 0.6 + 1.6 * (a.peso / pw) as f32 } else { 0.8 + 2.6 * (a.peso / pw) as f32 },
            tracejada: entre,
        });
    }
    // Nós.
    for n in &r.nos {
        cena.push(Prim::Circulo {
            c: pos[n.id], r: raio(n),
            preench: Some(cor_grupo(n.grupo, 255)),
            borda: Some(([255, 255, 255, 255], 1.5)),
            dica: Some(format!("{} · peso {:.0} · {}", n.rotulo, n.peso, r.grupos.get(n.grupo).map(|g| g.nome.as_str()).unwrap_or(""))),
            alvo: Some(Alvo::No(n.id)),
        });
    }
    // Títulos dos grupos acima dos halos e, ao lado, o termo mais pesado de cada nó principal.
    let muitos = r.grupos.len() > 12;
    let mut por_tamanho: Vec<usize> = (0..r.grupos.len()).collect();
    por_tamanho.sort_by(|&a, &b| r.grupos[b].tamanho.cmp(&r.grupos[a].tamanho));
    let titulados: Vec<usize> = por_tamanho.into_iter().take(if muitos { 10 } else { usize::MAX }).collect();
    for (g, (cx, cy, rr)) in r.grupos.iter().zip(halos.iter()) {
        if *rr == 0.0 {
            continue;
        }
        if interativa {
            cena.rotulos.push(Rotulo {
                pos: (*cx, *cy - *rr), texto: g.nome.clone(), tam: 12.5, cor: TINTA, negrito: true,
                lugar: Lugar::Acima, prioridade: 1000.0 + g.tamanho as f32, raio: *rr, min_px: 12.0,
                alvo: Some(Alvo::Grupo(g.id)),
            });
            for (ordem, n) in r.nos_do_grupo(g.id).into_iter().take(4).enumerate() {
                cena.rotulos.push(Rotulo {
                    pos: pos[n.id], texto: n.rotulo.clone(), tam: 10.5, cor: FRACA, negrito: false,
                    lugar: Lugar::Direita, prioridade: (n.peso / pmax) as f32 - ordem as f32 * 0.1, raio: raio(n), min_px: 8.0,
                    alvo: Some(Alvo::No(n.id)),
                });
            }
            continue;
        }
        if !titulados.contains(&g.id) {
            continue;
        }
        cena.push(Prim::Texto {
            pos: (*cx, cy - rr - 9.0), texto: g.nome.clone(), tam: 12.5, cor: TINTA,
            ancora: Ancora::Centro, negrito: true, vertical: false,
        });
        if muitos {
            continue;
        }
        for n in r.nos_do_grupo(g.id).into_iter().skip(1).take(2) {
            let p = pos[n.id];
            let esquerda = p.0 > largura * 0.62;
            let dx = raio(n) + 4.0;
            cena.push(Prim::Texto {
                pos: (if esquerda { p.0 - dx } else { p.0 + dx }, p.1), texto: n.rotulo.clone(), tam: 10.5, cor: FRACA,
                ancora: if esquerda { Ancora::Direita } else { Ancora::Esquerda }, negrito: false, vertical: false,
            });
        }
    }
    cena
}

/// Legenda de cores dos grupos (nome, cor RGB), para a interface.
pub fn legenda(r: &Resultado) -> Vec<(String, [u8; 3])> {
    r.grupos.iter().map(|g| (g.nome.clone(), PALETA[g.id % PALETA.len()])).collect()
}

const BRANCO: [u8; 4] = [255, 255, 255, 255];

/// Diagrama estratégico de Callon: centralidade (x) por densidade (y), nas faixas
/// normalizadas (1..n)/n com o cruzamento em 0,5, como em `redes/viz/strategic.py`.
/// Esferas numeradas, com a legenda ao lado para que nada se sobreponha.
pub fn estrategico(r: &Resultado, largura: f32, altura: f32) -> Cena {
    estrategico_com(r, largura, altura, false)
}

/// Diagrama para a tela: sem legenda lateral (o nome aparece por nível de detalhe e no painel).
pub fn estrategico_interativo(r: &Resultado) -> Cena {
    let (w, h) = mundo(r.grupos.len() * 6 / 5);
    estrategico_com(r, w, h, true)
}

fn estrategico_com(r: &Resultado, largura: f32, altura: f32, interativa: bool) -> Cena {
    let mut cena = Cena::nova(largura, altura);
    if r.grupos.is_empty() {
        cena.push(Prim::Texto {
            pos: (largura / 2.0, altura / 2.0), texto: "Sem temas para este período.".into(),
            tam: 14.0, cor: FRACA, ancora: Ancora::Centro, negrito: false, vertical: false,
        });
        return cena;
    }
    let legenda_larg = if interativa { 0.0 } else { (largura * 0.28).clamp(190.0, 300.0) };
    let (ml, mr, mt, mb) = (62.0f32, if interativa { 56.0 } else { legenda_larg + 24.0 }, 28.0f32, 60.0f32);
    let (x0, x1, y0, y1) = (ml, largura - mr, mt, altura - mb);
    let px = |c: f64| x0 + (c.clamp(0.0, 1.0) as f32) * (x1 - x0);
    let py = |d: f64| y1 - (d.clamp(0.0, 1.0) as f32) * (y1 - y0);
    let (lx, ly) = (px(0.5), py(0.5));

    let fundo = |q: Quadrante, a: (f32, f32), b: (f32, f32), cena: &mut Cena| {
        let c = q_cor(q);
        cena.push(Prim::Retangulo { min: a, max: b, preench: Some([c[0], c[1], c[2], 14]), borda: None });
    };
    fundo(Quadrante::Nicho, (x0, y0), (lx, ly), &mut cena);
    fundo(Quadrante::Motor, (lx, y0), (x1, ly), &mut cena);
    fundo(Quadrante::Emergente, (x0, ly), (lx, y1), &mut cena);
    fundo(Quadrante::Basico, (lx, ly), (x1, y1), &mut cena);
    cena.push(Prim::Retangulo { min: (x0, y0), max: (x1, y1), preench: None, borda: Some((LINHA, 1.0)) });

    for k in 0..=4 {
        let v = k as f64 / 4.0;
        let (x, y) = (px(v), py(v));
        cena.push(Prim::Linha { a: (x, y1), b: (x, y1 + 4.0), cor: FRACA, larg: 1.0, tracejada: false });
        cena.push(Prim::Texto { pos: (x, y1 + 15.0), texto: fmt_num(v), tam: 10.5, cor: FRACA, ancora: Ancora::Centro, negrito: false, vertical: false });
        cena.push(Prim::Linha { a: (x0 - 4.0, y), b: (x0, y), cor: FRACA, larg: 1.0, tracejada: false });
        cena.push(Prim::Texto { pos: (x0 - 8.0, y), texto: fmt_num(v), tam: 10.5, cor: FRACA, ancora: Ancora::Direita, negrito: false, vertical: false });
    }
    cena.push(Prim::Linha { a: (lx, y0), b: (lx, y1), cor: [0x0B, 0x1F, 0x66, 150], larg: 1.2, tracejada: true });
    cena.push(Prim::Linha { a: (x0, ly), b: (x1, ly), cor: [0x0B, 0x1F, 0x66, 150], larg: 1.2, tracejada: true });
    let rot = |q: Quadrante, pos: (f32, f32), anc: Ancora, cena: &mut Cena| {
        cena.push(Prim::Texto { pos, texto: q.rotulo().to_string(), tam: 11.0, cor: q_cor(q), ancora: anc, negrito: true, vertical: false });
    };
    rot(Quadrante::Nicho, (x0 + 10.0, y0 + 14.0), Ancora::Esquerda, &mut cena);
    rot(Quadrante::Motor, (x1 - 10.0, y0 + 14.0), Ancora::Direita, &mut cena);
    rot(Quadrante::Emergente, (x0 + 10.0, y1 - 12.0), Ancora::Esquerda, &mut cena);
    rot(Quadrante::Basico, (x1 - 10.0, y1 - 12.0), Ancora::Direita, &mut cena);
    cena.push(Prim::Texto { pos: ((x0 + x1) / 2.0, altura - 16.0), texto: "Centralidade (relevância no campo)".into(), tam: 12.0, cor: TINTA, ancora: Ancora::Centro, negrito: true, vertical: false });
    cena.push(Prim::Texto { pos: (16.0, (y0 + y1) / 2.0), texto: "Densidade (desenvolvimento do tema)".into(), tam: 12.0, cor: TINTA, ancora: Ancora::Centro, negrito: true, vertical: true });

    // Esferas: área proporcional ao número de nós; maiores primeiro, para as pequenas ficarem por cima.
    let tmax = r.grupos.iter().map(|g| g.tamanho).max().unwrap_or(1).max(1) as f32;
    let raio = |g: &Grupo| 9.0 + 17.0 * (g.tamanho as f32 / tmax).sqrt();
    let mut ordem: Vec<&Grupo> = r.grupos.iter().collect();
    ordem.sort_by(|a, b| b.tamanho.cmp(&a.tamanho));
    for g in &ordem {
        cena.push(Prim::Circulo {
            c: (px(g.faixa_c), py(g.faixa_d)), r: raio(g),
            preench: Some(cor_grupo(g.id, 170)), borda: Some((cor_grupo(g.id, 255), 1.5)),
            dica: Some(format!("{}. {} · {} · {} nós · {} documentos", g.id + 1, g.nome, g.quadrante.curto(), g.tamanho, g.documentos)),
            alvo: Some(Alvo::Grupo(g.id)),
        });
    }
    for g in &ordem {
        let (cx, cy) = (px(g.faixa_c), py(g.faixa_d));
        let cor = if [0usize, 4].contains(&(g.id % crate::tema::PALETA.len())) { BRANCO } else { TINTA };
        if interativa {
            cena.rotulos.push(Rotulo {
                pos: (cx, cy), texto: (g.id + 1).to_string(), tam: 11.0, cor, negrito: true,
                lugar: Lugar::Dentro, prioridade: 2000.0 + g.tamanho as f32, raio: raio(g), min_px: 8.0,
                alvo: Some(Alvo::Grupo(g.id)),
            });
            cena.rotulos.push(Rotulo {
                pos: (cx, cy), texto: g.nome.clone(), tam: 11.0, cor: TINTA, negrito: false,
                lugar: Lugar::Direita, prioridade: g.tamanho as f32, raio: raio(g), min_px: 7.0,
                alvo: Some(Alvo::Grupo(g.id)),
            });
        } else {
            cena.push(Prim::Texto { pos: (cx, cy), texto: (g.id + 1).to_string(), tam: 11.0, cor, ancora: Ancora::Centro, negrito: true, vertical: false });
        }
    }
    if interativa {
        return cena;
    }

    // Legenda numerada à direita.
    let lx0 = largura - legenda_larg - 6.0;
    cena.push(Prim::Texto { pos: (lx0, y0 + 6.0), texto: "Agrupamentos".into(), tam: 12.0, cor: TINTA, ancora: Ancora::Esquerda, negrito: true, vertical: false });
    let passo = 18.0f32;
    let linhas = (((y1 - y0 - 24.0) / passo).floor() as usize).max(1);
    let max_chars = ((legenda_larg - 34.0) / 6.2) as usize;
    let mut lista: Vec<&Grupo> = r.grupos.iter().collect();
    lista.sort_by_key(|g| g.id);
    for (k, g) in lista.iter().take(linhas).enumerate() {
        let y = y0 + 30.0 + k as f32 * passo;
        cena.push(Prim::Circulo { c: (lx0 + 7.0, y), r: 6.0, preench: Some(cor_grupo(g.id, 255)), borda: None, dica: None, alvo: None });
        let mut nome = format!("{}. {}", g.id + 1, g.nome);
        if nome.chars().count() > max_chars {
            nome = nome.chars().take(max_chars.saturating_sub(1)).collect::<String>() + "…";
        }
        cena.push(Prim::Texto { pos: (lx0 + 20.0, y), texto: nome, tam: 11.0, cor: TINTA, ancora: Ancora::Esquerda, negrito: false, vertical: false });
    }
    if lista.len() > linhas {
        cena.push(Prim::Texto { pos: (lx0, y0 + 30.0 + linhas as f32 * passo), texto: format!("e mais {}", lista.len() - linhas), tam: 11.0, cor: FRACA, ancora: Ancora::Esquerda, negrito: false, vertical: false });
    }
    let _ = AZUL;
    cena
}

pub fn fmt_num(v: f64) -> String {
    let s = format!("{:.2}", v);
    let s = s.trim_end_matches('0').trim_end_matches('.').replace('.', ",");
    if s.is_empty() { "0".into() } else { s }
}

#[cfg(test)]
mod testes {
    use super::*;
    use crate::backend::{mock::Demonstracao, Backend};

    fn dados() -> Resultado {
        let mut d = Demonstracao::default();
        d.abrir_demonstracao().unwrap();
        d.executar(&Parametros::default()).unwrap()
    }

    #[test]
    fn rede_tem_halo_por_grupo_e_no() {
        let r = dados();
        let c = rede(&r, 900.0, 640.0);
        let circulos = c.prims.iter().filter(|p| matches!(p, Prim::Circulo { alvo: Some(Alvo::Grupo(_)), .. })).count();
        assert_eq!(circulos, r.grupos.len());
        let nos = c.prims.iter().filter(|p| matches!(p, Prim::Circulo { alvo: Some(Alvo::No(_)), .. })).count();
        assert_eq!(nos, r.nos.len());
        for p in &c.prims {
            if let Prim::Circulo { c: ce, .. } = p {
                assert!(ce.0 > 0.0 && ce.0 < 900.0 && ce.1 > 0.0 && ce.1 < 640.0);
            }
        }
    }

    #[test]
    fn estrategico_uma_bolha_por_tema_e_dentro_do_quadro() {
        let r = dados();
        let c = estrategico(&r, 900.0, 640.0);
        let bolhas: Vec<_> = c.prims.iter().filter_map(|p| match p { Prim::Circulo { c, dica: Some(_), .. } => Some(*c), _ => None }).collect();
        assert_eq!(bolhas.len(), r.grupos.len());
        for b in bolhas {
            assert!(b.0 >= 62.0 && b.0 <= 900.0 && b.1 >= 28.0 && b.1 <= 640.0 - 60.0);
        }
    }

    #[test]
    fn interativas_trocam_textos_por_rotulos_lod() {
        let r = dados();
        let c = rede_interativa(&r);
        assert!(!c.prims.iter().any(|p| matches!(p, Prim::Texto { .. })));
        assert!(c.rotulos.iter().filter(|l| l.alvo.is_some_and(|a| matches!(a, Alvo::Grupo(_)))).count() == r.grupos.len());
        let e = estrategico_interativo(&r);
        assert_eq!(e.rotulos.len(), 2 * r.grupos.len());
        // Sem legenda lateral: nenhum círculo sem alvo.
        assert!(e.prims.iter().all(|p| !matches!(p, Prim::Circulo { alvo: None, .. })));
    }

    #[test]
    fn mundo_cresce_com_o_numero_de_elementos() {
        assert_eq!(mundo(10), (900.0, 620.0));
        assert!(mundo(640).0 > 2000.0);
        assert_eq!(mundo(1_000_000).0, 3600.0);
    }

    #[test]
    fn vazio_nao_quebra() {
        assert_eq!(rede(&Resultado::default(), 500.0, 400.0).prims.len(), 1);
        assert_eq!(estrategico(&Resultado::default(), 500.0, 400.0).prims.len(), 1);
    }

    #[test]
    fn formato() {
        assert_eq!(fmt_num(0.5), "0,5");
        assert_eq!(fmt_num(0.0), "0");
    }
}
