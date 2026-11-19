//! Comportamentos do CPython que o Python de referência usa e que mudam o
//! resultado numérico ou a ordem de iteração: `sum()` de floats (soma
//! compensada de Neumaier desde o Python 3.12) e a ordem de iteração de um
//! `set` de inteiros.

/// `sum()` do CPython sobre floats (Kahan-Babuska-Neumaier).
pub fn py_sum<I: IntoIterator<Item = f64>>(valores: I) -> f64 {
    let mut f = 0.0f64;
    let mut c = 0.0f64;
    for x in valores {
        let t = f + x;
        if f.abs() >= x.abs() {
            c += (f - t) + x;
        } else {
            c += (x - t) + f;
        }
        f = t;
    }
    if c != 0.0 && c.is_finite() {
        f += c;
    }
    f
}

const MINSIZE: usize = 8;
const LINEAR_PROBES: usize = 9;
const PERTURB_SHIFT: u32 = 5;

/// Tabela de hash de `set` do CPython (3.11 a 3.13) para inteiros não
/// negativos pequenos (hash(i) == i). Só serve para reproduzir a ordem de
/// iteração.
struct ConjuntoPy {
    tabela: Vec<Option<i64>>,
    mask: usize,
    fill: usize,
}

impl ConjuntoPy {
    fn novo() -> Self {
        ConjuntoPy { tabela: vec![None; MINSIZE], mask: MINSIZE - 1, fill: 0 }
    }

    fn insere_limpo(tabela: &mut [Option<i64>], mask: usize, chave: i64) {
        let hash = chave as u64;
        let mut perturb = hash as usize;
        let mut i = (hash as usize) & mask;
        loop {
            if tabela[i].is_none() {
                tabela[i] = Some(chave);
                return;
            }
            if i + LINEAR_PROBES <= mask {
                for j in 1..=LINEAR_PROBES {
                    if tabela[i + j].is_none() {
                        tabela[i + j] = Some(chave);
                        return;
                    }
                }
            }
            perturb >>= PERTURB_SHIFT;
            i = (i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb)) & mask;
        }
    }

    fn redimensiona(&mut self, minimo: usize) {
        let mut novo = MINSIZE;
        while novo <= minimo {
            novo <<= 1;
        }
        let mask = novo - 1;
        let mut tabela = vec![None; novo];
        for c in self.tabela.iter().flatten() {
            Self::insere_limpo(&mut tabela, mask, *c);
        }
        self.tabela = tabela;
        self.mask = mask;
    }

    fn adiciona(&mut self, chave: i64) {
        let hash = chave as u64;
        let mask = self.mask;
        let mut i = (hash as usize) & mask;
        let mut perturb = hash as usize;
        let posicao;
        'externo: loop {
            let probes = if i + LINEAR_PROBES <= mask { LINEAR_PROBES } else { 0 };
            for j in 0..=probes {
                match self.tabela[i + j] {
                    None => {
                        posicao = i + j;
                        break 'externo;
                    }
                    Some(c) if c == chave => return,
                    _ => {}
                }
            }
            perturb >>= PERTURB_SHIFT;
            i = (i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb)) & mask;
        }
        self.tabela[posicao] = Some(chave);
        self.fill += 1;
        if self.fill * 5 >= mask * 3 {
            self.redimensiona(self.fill * 4);
        }
    }
}

/// Ordem de iteração de `set(valores)` no CPython (inteiros não negativos).
pub fn ordem_set_py(valores: impl IntoIterator<Item = i64>) -> Vec<i64> {
    let mut c = ConjuntoPy::novo();
    for v in valores {
        c.adiciona(v);
    }
    c.tabela.iter().flatten().copied().collect()
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn soma_compensada() {
        // sum([0.1]*10) == 1.0 no Python 3.12+ (1.0 com soma ingênua daria 0.9999999999999999)
        assert_eq!(py_sum(std::iter::repeat(0.1).take(10)), 1.0);
    }

    #[test]
    fn ordem_set() {
        assert_eq!(ordem_set_py([5, 3, 9, 1]), vec![9, 3, 5, 1]);
        // 8 e 16 colidem na tabela de 8: set([16, 8]) -> {16, 8}
        assert_eq!(ordem_set_py([16, 8]), vec![16, 8]);
    }

    #[test]
    fn ordem_set_aleatorio() {
        let v: Vec<i64> = vec![2653, 1236, 3235, 396, 594, 4390, 772, 2996, 4775, 476, 4157, 1759, 308, 705, 3553, 3426, 573, 1972, 744, 4515, 3478, 485, 4633, 1015, 1829, 4776, 507, 4728, 4797, 3250, 407, 1812, 382, 4561, 1091, 2373, 3434, 1182, 4430, 965, 4677, 2528, 4590, 1481, 845, 4765, 4680, 1540, 3051, 799, 4488, 515, 4624, 489, 1688, 4067, 4356, 3503, 2574, 3815, 4797, 3713, 2963, 2456, 2036, 1473, 2000, 671, 4706, 2460, 4303, 4056, 2814, 3677, 2359, 4989, 600, 968, 4194, 3426, 1352, 2803, 1246, 4006, 3455, 322, 636, 4572, 4695, 2571, 2787, 2869, 4870, 4069, 4751, 3738, 564, 767, 2212, 3884, 533, 498, 2537, 4735, 3651, 2332, 3161, 2843, 185, 3783, 2912, 1377, 960, 4045, 483, 1788, 2355, 1060, 2029, 3260, 3203, 4068, 661, 1363, 3680, 3291, 4502, 2277, 1122, 3527, 4508, 2281, 3403, 2940, 3117, 1891, 1237, 680, 1444, 1240, 1901, 1912, 99, 3973, 4827, 1494, 2153, 2310, 34, 1194];
        let esperado: Vec<i64> = vec![515, 1540, 2571, 2574, 4624, 533, 4633, 34, 1060, 3117, 564, 573, 4157, 1091, 3651, 4677, 4680, 594, 4695, 600, 3161, 2653, 3677, 3680, 4706, 4194, 1122, 99, 2153, 4728, 636, 4735, 3713, 3203, 4751, 661, 1688, 3738, 4765, 1182, 671, 3235, 2212, 4775, 4776, 680, 1194, 3250, 185, 3260, 4797, 705, 3783, 4303, 1236, 1237, 1240, 3291, 4827, 1246, 1759, 2787, 2277, 3815, 744, 2281, 2803, 1788, 2814, 767, 772, 4356, 4870, 2310, 1812, 2843, 2332, 799, 1829, 4390, 3884, 2355, 308, 2869, 2359, 322, 2373, 1352, 3403, 845, 4430, 1363, 2912, 1377, 3426, 1891, 3434, 1901, 1912, 2940, 4989, 382, 3455, 3973, 4488, 396, 2963, 3478, 407, 2456, 4502, 2460, 4508, 4515, 1444, 4006, 3503, 2996, 1972, 960, 1473, 965, 3527, 968, 1481, 4045, 2000, 4561, 1494, 4056, 476, 4572, 2528, 3553, 4067, 483, 485, 4069, 4068, 489, 2537, 3051, 2029, 4590, 498, 2036, 1015, 507];
        assert_eq!(ordem_set_py(v), esperado);
    }
}
