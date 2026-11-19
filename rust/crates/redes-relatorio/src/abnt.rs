//! Referências no padrão ABNT (porta de `report.referencia_abnt`).
//!
//! O armazenamento guarda `AUTOR, ANO, FONTE, Vvolume, Ppáginas, Título`. A ABNT
//! pede `AUTOR. Título. Fonte, ano. v. X. p. Y.`: o autor em maiúsculas, o título
//! (quando existe) e o volume e as páginas no fim, sem os prefixos "V" e "P" do
//! armazenamento.

fn sem_prefixo(campo: &str, letra: char) -> &str {
    let mut it = campo.chars();
    match (it.next(), it.next()) {
        (Some(c), Some(d)) if c == letra && d.is_ascii_digit() => &campo[c.len_utf8()..],
        _ => campo,
    }
}

/// Converte a referência no formato guardado pelo Redes para o padrão ABNT.
pub fn referencia_abnt(completa: &str) -> String {
    let campos: Vec<&str> = completa.splitn(6, ',').map(|c| c.trim()).collect();
    let pega = |i: usize| campos.get(i).copied().unwrap_or("");
    let (autor, ano, fonte, volume, paginas, titulo) = (pega(0), pega(1), pega(2), sem_prefixo(pega(3), 'V'), sem_prefixo(pega(4), 'P'), pega(5));
    let fonte = if fonte.eq_ignore_ascii_case("sem fonte") { "" } else { fonte };
    let autor = if autor.eq_ignore_ascii_case("sem autor") { "" } else { autor };
    let mut partes: Vec<String> = Vec::new();
    if !autor.is_empty() {
        let a = autor.to_uppercase();
        partes.push(if a.ends_with('.') { a } else { format!("{a}.") });
    }
    if !titulo.is_empty() {
        partes.push(format!("{}.", titulo.trim_end_matches('.')));
    }
    if !fonte.is_empty() {
        partes.push(format!("{}{}", fonte, if ano.is_empty() { "." } else { "," }));
    }
    if !ano.is_empty() {
        partes.push(format!("{ano}."));
    }
    if !volume.is_empty() {
        partes.push(format!("v. {volume}."));
    }
    if !paginas.is_empty() {
        partes.push(format!("p. {paginas}."));
    }
    if partes.is_empty() {
        completa.to_string()
    } else {
        partes.join(" ")
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn converte() {
        assert_eq!(referencia_abnt("Silva J., 1999, Revista X, V12, P34-56, Um título"), "SILVA J. Um título. Revista X, 1999. v. 12. p. 34-56.");
        assert_eq!(referencia_abnt("Silva J., 1999, Revista X"), "SILVA J. Revista X, 1999.");
        assert_eq!(referencia_abnt("Silva J., 1999, Sem fonte, , , "), "SILVA J. 1999.");
        assert_eq!(referencia_abnt(""), "");
    }
}
