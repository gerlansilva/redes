//! Exportações CSV do OpenAlex. Porta de `loaders/openalex.py` (e de `words.Canonicalizador`).

use std::collections::HashMap;

use indexmap::IndexMap;

use crate::erro::Resultado;
use crate::fonte::{abrevia_autor, DocumentoFonte};
use crate::loaders::csv_tab::py_float;
use crate::loaders::{campo, dict_reader};
use crate::paises::{paises_de, pais_por_sigla};
use crate::referencias::{converte_referencia, limpa_texto, separa_referencias};
use crate::rx;
use crate::util::*;

const ESTRUTURADAS: &[&str] = &[
    "Authors", "Author full names", "Title", "Year", "Source title", "DOI", "Affiliations", "Abstract", "Author Keywords",
    "Source Keywords", "References", "Cited by", "Type", "Author", "Citation count",
];

const PARTICULAS: &[&str] = &["de", "da", "do", "das", "dos", "e", "di", "del", "della", "van", "von", "der", "den", "la", "le", "y"];

/// Uma grafia por termo: a mais frequente (empate: mais curta, depois alfabética).
#[derive(Default)]
pub struct Canonicalizador {
    contagem: HashMap<String, IndexMap<String, i64>>,
}

impl Canonicalizador {
    pub fn registra(&mut self, termos: &[String]) {
        for t in termos {
            let k = chave(t);
            if k.is_empty() {
                continue;
            }
            *self.contagem.entry(k).or_default().entry(t.clone()).or_insert(0) += 1;
        }
    }

    fn escolha(&self, termo: &str) -> String {
        match self.contagem.get(&chave(termo)) {
            None => termo.to_string(),
            Some(op) => {
                let mut v: Vec<(&String, &i64)> = op.iter().collect();
                v.sort_by(|a, b| b.1.cmp(a.1).then(n_chars(a.0).cmp(&n_chars(b.0))).then(a.0.cmp(b.0)));
                v[0].0.clone()
            }
        }
    }

    pub fn aplica(&self, termos: &[String]) -> Vec<String> {
        let mut vistos: Vec<String> = vec![];
        for t in termos {
            let c = self.escolha(t);
            if !vistos.contains(&c) {
                vistos.push(c);
            }
        }
        vistos
    }
}

pub fn abrevia_nome_do_site(nome: &str) -> String {
    let partes = palavras(nome);
    if partes.len() < 2 {
        return strip(nome).to_string();
    }
    let mut sobrenome = partes[partes.len() - 1].to_string();
    if eh_maiuscula(&sobrenome) && n_chars(&sobrenome) > 1 {
        // str.capitalize()
        let mut cs = sobrenome.chars();
        let p = cs.next().unwrap();
        sobrenome = p.to_uppercase().chain(cs.flat_map(|c| c.to_lowercase())).collect();
    }
    let resto: Vec<&str> = partes[..partes.len() - 1].iter().copied().filter(|p| !PARTICULAS.contains(&p.to_lowercase().as_str())).collect();
    if resto.is_empty() {
        sobrenome
    } else {
        abrevia_autor(&format!("{}, {}", sobrenome, resto.join(" ")))
    }
}

fn nomes_do_site(registro: &IndexMap<String, String>) -> Option<(Vec<String>, Vec<String>)> {
    if !campo(registro, "Authors").is_empty() || !registro.contains_key("Author") {
        return None;
    }
    let completos: Vec<String> = campo(registro, "Author").split('|').map(strip).filter(|n| !n.is_empty()).map(String::from).collect();
    Some((completos.iter().map(|n| abrevia_nome_do_site(n)).collect(), completos))
}

fn paises_por_sigla(valor: &str) -> Vec<String> {
    let mut achados: Vec<String> = vec![];
    for parte in valor.split(['|', ';', ',']) {
        if let Some(n) = pais_por_sigla(parte) {
            if !achados.iter().any(|a| a == n) {
                achados.push(n.to_string());
            }
        }
    }
    achados
}

fn palavras_do_resumo(resumo: &str) -> Vec<String> {
    let re = rx!(r"(?is)(?:palavras?[\s\-]*chaves?|palabras?[\s\-]*claves?|keywords?|mots[\s\-]*cl[ée]s)\s*:\s*(.+?)\s*$");
    if let Ok(Some(c)) = re.captures(resumo) {
        let texto = strip(c.get(1).unwrap().as_str()).trim_end_matches('.').to_string();
        return texto.split([';', ',']).map(limpa_texto).filter(|p| !p.is_empty()).collect();
    }
    vec![]
}

fn autores_curtos(curto: &str, completo: &str) -> Vec<String> {
    let completos: Vec<String> = completo.split(';').map(strip).filter(|n| !n.is_empty()).map(String::from).collect();
    let partes: Vec<&str> = curto.split(',').map(strip).filter(|p| !p.is_empty()).collect();
    let mut nomes: Vec<String> = vec![];
    let mut atual: Vec<&str> = vec![];
    for parte in partes {
        if atual.is_empty() {
            atual = vec![parte];
        } else if rx!(r"^[A-Z](?:\.?-?[A-Z])*\.?$").is_match(parte).unwrap_or(false) {
            atual.push(parte);
            nomes.push(atual.join(", "));
            atual = vec![];
        } else {
            nomes.push(atual.join(", "));
            atual = vec![parte];
        }
    }
    if !atual.is_empty() {
        nomes.push(atual.join(", "));
    }
    if !completos.is_empty() && completos.len() != nomes.len() {
        return completos;
    }
    if nomes.is_empty() { completos } else { nomes }
}

fn autores_completos(valor: &str) -> Vec<String> {
    valor.split(';').map(strip).filter(|n| !n.is_empty()).map(String::from).collect()
}

fn citacoes(valor: &str) -> Option<i64> {
    let v = strip(valor);
    if v.is_empty() {
        return None;
    }
    py_float(&v.replace(',', ".")).map(|f| f as i64)
}

fn separa_ponto_e_virgula(valor: &str) -> Vec<String> {
    valor.split(';').map(limpa_texto).filter(|p| !p.is_empty()).collect()
}

fn palavras_autor_registro(r: &IndexMap<String, String>) -> Vec<String> {
    let dadas = separa_ponto_e_virgula(campo(r, "Author Keywords"));
    if dadas.is_empty() { palavras_do_resumo(campo(r, "Abstract")) } else { dadas }
}

pub fn le(texto: &str) -> Resultado<Vec<DocumentoFonte>> {
    let registros: Vec<IndexMap<String, String>> = dict_reader(texto, b',')?.into_iter().filter(|r| !limpa_texto(campo(r, "Title")).is_empty()).collect();

    let mut palavras_c = Canonicalizador::default();
    for r in &registros {
        palavras_c.registra(&palavras_autor_registro(r));
        palavras_c.registra(&separa_ponto_e_virgula(campo(r, "Source Keywords")));
    }
    let curtos_e_completos = |r: &IndexMap<String, String>| -> (Vec<String>, Vec<String>) {
        if let Some(s) = nomes_do_site(r) {
            return s;
        }
        (autores_curtos(campo(r, "Authors"), campo(r, "Author full names")), autores_completos(campo(r, "Author full names")))
    };
    let mut autores_c = Canonicalizador::default();
    for r in &registros {
        autores_c.registra(&curtos_e_completos(r).0);
    }

    let mut canonicas: HashMap<String, String> = HashMap::new();
    let mut docs = vec![];
    for r in &registros {
        let mut do_documento: std::collections::HashSet<String> = Default::default();
        let afiliacoes: Vec<String> = separa_ponto_e_virgula(campo(r, "Affiliations"));
        let mut refs = vec![];
        let mut brutas = vec![];
        for bruta in separa_referencias(campo(r, "References")) {
            let Some(mut item) = converte_referencia(bruta) else { continue };
            let k = chave(&item);
            match canonicas.get(&k) {
                Some(c) => item = c.clone(),
                None => {
                    canonicas.insert(k, item.clone());
                }
            }
            if !do_documento.insert(item.clone()) {
                continue;
            }
            refs.push(item);
            brutas.push(limpa_texto(bruta));
        }
        let (curtos, completos) = curtos_e_completos(r);
        let c = campo(r, "Cited by");
        let cit = citacoes(if c.is_empty() { campo(r, "Citation count") } else { c });
        let pais_col = campo(r, "Country");
        let mut paises = paises_de(&afiliacoes, pais_col);
        if paises.is_empty() {
            paises = paises_por_sigla(pais_col);
        }
        let tipo = limpa_texto(campo(r, "Type"));
        let mut meta = IndexMap::new();
        for (k, v) in r {
            let l = limpa_texto(v);
            if !ESTRUTURADAS.contains(&k.as_str()) && !l.is_empty() {
                meta.insert(k.clone(), l);
            }
        }
        docs.push(DocumentoFonte {
            titulo: limpa_texto(campo(r, "Title")),
            autores: autores_c.aplica(&curtos),
            autores_completos: completos,
            ano: limpa_texto(campo(r, "Year")),
            citacoes: cit,
            periodico: limpa_texto(campo(r, "Source title")),
            doi: limpa_texto(campo(r, "DOI")),
            tipo: if tipo.is_empty() { "article".into() } else { tipo },
            resumo: limpa_texto(campo(r, "Abstract")),
            afiliacoes,
            paises,
            palavras_autor: palavras_c.aplica(&palavras_autor_registro(r)),
            palavras_fonte: palavras_c.aplica(&separa_ponto_e_virgula(campo(r, "Source Keywords"))),
            referencias: refs,
            referencias_brutas: brutas,
            referencias_convertidas: true,
            metadados: meta,
        });
    }
    Ok(docs)
}
