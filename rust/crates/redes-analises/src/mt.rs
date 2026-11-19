//! Mersenne Twister (MT19937) compatível com `random.Random(seed)` do Python e com
//! `numpy.random.RandomState(seed)`, para reproduzir a ordem de embaralhamento do Louvain do
//! networkx e as posições iniciais do `spring_layout`.

pub struct Mt {
    mt: [u32; 624],
    idx: usize,
}

impl Mt {
    pub fn init_genrand(s: u32) -> Mt {
        let mut mt = [0u32; 624];
        mt[0] = s;
        for i in 1..624 {
            mt[i] = 1812433253u32.wrapping_mul(mt[i - 1] ^ (mt[i - 1] >> 30)).wrapping_add(i as u32);
        }
        Mt { mt, idx: 624 }
    }

    pub fn init_by_array(key: &[u32]) -> Mt {
        let mut m = Mt::init_genrand(19650218);
        let (mut i, mut j) = (1usize, 0usize);
        let n = 624usize;
        for _ in 0..n.max(key.len()) {
            m.mt[i] = (m.mt[i] ^ (m.mt[i - 1] ^ (m.mt[i - 1] >> 30)).wrapping_mul(1664525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= n {
                m.mt[0] = m.mt[n - 1];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
        }
        for _ in 0..n - 1 {
            m.mt[i] = (m.mt[i] ^ (m.mt[i - 1] ^ (m.mt[i - 1] >> 30)).wrapping_mul(1566083941)).wrapping_sub(i as u32);
            i += 1;
            if i >= n {
                m.mt[0] = m.mt[n - 1];
                i = 1;
            }
        }
        m.mt[0] = 0x80000000;
        m.idx = 624;
        m
    }

    /// `random.Random(seed)` com semente inteira não negativa de até 32 bits.
    pub fn python(seed: u32) -> Mt {
        Mt::init_by_array(&[seed])
    }

    /// `numpy.random.RandomState(seed)` (semeadura legada).
    pub fn numpy(seed: u32) -> Mt {
        Mt::init_genrand(seed)
    }

    fn gera(&mut self) {
        const UPPER: u32 = 0x80000000;
        const LOWER: u32 = 0x7fffffff;
        for k in 0..624 {
            let y = (self.mt[k] & UPPER) | (self.mt[(k + 1) % 624] & LOWER);
            let mut v = self.mt[(k + 397) % 624] ^ (y >> 1);
            if y & 1 != 0 {
                v ^= 0x9908b0df;
            }
            self.mt[k] = v;
        }
        self.idx = 0;
    }

    pub fn genrand(&mut self) -> u32 {
        if self.idx >= 624 {
            self.gera();
        }
        let mut y = self.mt[self.idx];
        self.idx += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9d2c5680;
        y ^= (y << 15) & 0xefc60000;
        y ^= y >> 18;
        y
    }

    pub fn getrandbits(&mut self, k: u32) -> u32 {
        self.genrand() >> (32 - k)
    }

    /// `Random._randbelow(n)` (n >= 1).
    pub fn randbelow(&mut self, n: usize) -> usize {
        let k = usize::BITS - n.leading_zeros();
        let mut r = self.getrandbits(k) as usize;
        while r >= n {
            r = self.getrandbits(k) as usize;
        }
        r
    }

    /// `Random.shuffle`.
    pub fn shuffle<T>(&mut self, x: &mut [T]) {
        for i in (1..x.len()).rev() {
            let j = self.randbelow(i + 1);
            x.swap(i, j);
        }
    }

    /// `random_sample()` do numpy / `random()` do Python (53 bits).
    pub fn res53(&mut self) -> f64 {
        let a = (self.genrand() >> 5) as f64;
        let b = (self.genrand() >> 6) as f64;
        (a * 67108864.0 + b) / 9007199254740992.0
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn python_random_semente_7() {
        // random.Random(7): random() -> 0.32383276483316237, 0.15084917392450192
        let mut m = Mt::python(7);
        assert_eq!(m.res53(), 0.32383276483316237);
        assert_eq!(m.res53(), 0.15084917392450192);
    }

    #[test]
    fn numpy_semente_3() {
        // np.random.RandomState(3).rand() -> 0.5507979025745755, 0.7081478226181048
        let mut m = Mt::numpy(3);
        assert_eq!(m.res53(), 0.5507979025745755);
        assert_eq!(m.res53(), 0.7081478226181048);
    }
}
