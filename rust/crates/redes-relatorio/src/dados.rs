//! Entrada de dados do relatório (`DadosRelatorio`), serializável com serde.
//!
//! O gerador não calcula análises: recebe tudo pronto (parâmetros, grupos, nós,
//! arestas, índices, quadrantes, figuras SVG e textos). Quem calcula (redes-core,
//! redes-analises, redes-importa) preenche esta estrutura; o adaptador
//! [`crate::adaptador`] faz isso a partir do `Resultado` do redes-core.
//!
//! Convenções:
//! - nomes de enumerações iguais aos do Python (`"Words"`, `"CoOccurrence"`,
//!   `"EquivalenceIndex"`, `"CentersSimples"`; mapeadores `"nucleo"`, `"interseccao"`...);
//! - células de tabela (`Bloco::Tabela::linhas`) são HTML já escapado, como no
//!   Python; cabeçalhos e legendas são texto simples (o gerador escapa);
//! - todos os campos opcionais têm padrão, então um JSON parcial vale.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

/// Medidas de desempenho, na ordem das tabelas.
pub const ORDEM_MEDIDAS: &[&str] = &["documentos", "h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"];

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct DadosRelatorio {
    pub projeto: InfoProjeto,
    /// Seção 1 (visão geral descritiva); `None` omite a seção e a numeração
    /// das análises começa em 1.
    pub visao_geral: Option<VisaoGeral>,
    /// Análises, uma por seção (2, 3, 4...).
    pub secoes: Vec<SecaoAnalise>,
    /// Análises que não puderam ser geradas, com o motivo.
    pub ignoradas: Vec<Ignorada>,
    /// Medida temporal da evolução (padrão `EquivalenceIndex`).
    pub medida_temporal: String,
    /// Relatório estendido (só na pasta): documentos por mapeador em cada agrupamento.
    pub estendido: bool,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct InfoProjeto {
    /// Nome do arquivo do projeto (aparece na capa).
    pub nome: String,
    pub documentos: usize,
    /// Nomes dos períodos do projeto, na ordem.
    pub periodos: Vec<String>,
    /// Data da capa, já por extenso ("19 de novembro de 2026"); `None` = hoje.
    pub data: Option<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct Ignorada {
    pub rotulo: String,
    pub motivo: String,
}

// ------------------------------------------------------------------ blocos

/// Unidade de conteúdo livre: o que os módulos de figura e tabela entregam.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(tag = "tipo", rename_all = "snake_case")]
pub enum Bloco {
    /// HTML já escapado, inserido como está.
    Html { html: String },
    /// `<p class="nota">` (texto simples).
    Nota { texto: String },
    /// `<p class="fonte">` (texto simples).
    Fonte { texto: String },
    /// Subtítulo numerado (h4) dentro de uma subseção.
    Subtitulo { texto: String },
    /// Figura numerada (SVG completo).
    Figura { svg: String, legenda: String },
    /// Tabela numerada. `linhas`: células em HTML já escapado.
    Tabela {
        cabecalho: Vec<String>,
        linhas: Vec<Vec<String>>,
        legenda: String,
        #[serde(default)]
        numericas: Vec<usize>,
        #[serde(default)]
        larga: bool,
    },
    /// Lista de itens (texto simples).
    Lista { itens: Vec<String> },
}

impl Bloco {
    pub fn nota(t: impl Into<String>) -> Bloco {
        Bloco::Nota { texto: t.into() }
    }
    pub fn figura(svg: impl Into<String>, legenda: impl Into<String>) -> Bloco {
        Bloco::Figura { svg: svg.into(), legenda: legenda.into() }
    }
    /// Tabela cujas células são texto simples (escapa cada uma).
    pub fn tabela_texto(cabecalho: &[&str], linhas: &[Vec<String>], legenda: &str, numericas: &[usize]) -> Bloco {
        Bloco::Tabela {
            cabecalho: cabecalho.iter().map(|s| s.to_string()).collect(),
            linhas: linhas.iter().map(|l| l.iter().map(|c| crate::texto::esc(c)).collect()).collect(),
            legenda: legenda.to_string(),
            numericas: numericas.to_vec(),
            larga: false,
        }
    }
}

// ------------------------------------------------------------ visão geral

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct VisaoGeral {
    /// "O que falta neste corpus" (aviso amarelo).
    pub lacunas: Vec<String>,
    /// Tabela "Informações principais": Indicador, Valor, Observação (texto simples).
    pub cartoes: Vec<Vec<String>>,
    /// Subseções 1.1, 1.2... na ordem. A última, "Método e parâmetros", é
    /// acrescentada pelo gerador (a menos que `sem_metodo`).
    pub subsecoes: Vec<Subsecao>,
    pub sem_metodo: bool,
    /// Tabela de parâmetros da visão geral (pares); `None` usa os padrões do código.
    pub parametros: Option<Vec<Vec<String>>>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct Subsecao {
    pub titulo: String,
    pub blocos: Vec<Bloco>,
}

// -------------------------------------------------------------- análises

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct SecaoAnalise {
    /// Nome curto (pasta no relatório em pastas): "conceitual", "autores"...
    pub chave: String,
    pub rotulo: String,
    pub descricao: String,
    pub config: ConfigRel,
    /// Frequência mínima efetiva; `None` = `config.minimo_frequencia`.
    pub frequencia: Option<usize>,
    /// Medida temporal desta seção; `None` = a do relatório.
    pub medida_temporal: Option<String>,
    pub periodos: Vec<PeriodoRel>,
    /// Indicadores de "Todos os períodos" (união); `None` soma o que der.
    pub total: Option<TotalRel>,
    /// Blocos extras, na ordem de exibição (evolução, linha do tempo, densidade...).
    pub extras: Vec<ExtraRel>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct TotalRel {
    pub documentos: Option<usize>,
    pub documentos_com_itens: Option<usize>,
    pub grafias: Option<usize>,
    pub itens: Option<usize>,
    pub itens_reduzidos: Option<usize>,
    pub itens_agrupados: Option<usize>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TipoExtra {
    Evolucao,
    LinhaDoTempo,
    Densidade,
    DuploMapa,
    Similitude,
}

impl TipoExtra {
    pub fn titulo_padrao(self) -> &'static str {
        match self {
            TipoExtra::Evolucao => "Evolução e sobreposição temática",
            TipoExtra::LinhaDoTempo => "Linha do tempo (corpus completo)",
            TipoExtra::Densidade => "Mapa de densidade (corpus completo)",
            TipoExtra::DuploMapa => crate::TITULO_DUPLO,
            TipoExtra::Similitude => crate::TITULO_SIMILITUDE,
        }
    }
    pub fn ancora(self) -> &'static str {
        match self {
            TipoExtra::Evolucao => "evolucao",
            TipoExtra::LinhaDoTempo => "linha-do-tempo",
            TipoExtra::Densidade => "densidade",
            TipoExtra::DuploMapa => "duplo-mapa",
            TipoExtra::Similitude => "similitude",
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExtraRel {
    pub tipo: TipoExtra,
    #[serde(default)]
    pub titulo: Option<String>,
    #[serde(default)]
    pub blocos: Vec<Bloco>,
}

/// Parâmetros efetivos da análise (os nomes de enumeração são os do Python).
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct ConfigRel {
    pub unidade: String,
    pub matriz: String,
    pub similaridade: String,
    pub algoritmo: String,
    pub minimo_frequencia: usize,
    pub minimo_coocorrencia: f64,
    pub tamanho_minimo: usize,
    pub tamanho_maximo: usize,
    pub corte: f64,
    pub mapeadores: Vec<String>,
    pub k_core: usize,
    /// Índices de desempenho ("h", "g", "hg", "q2", "media", "soma", "minimo", "maximo").
    pub indices: Vec<String>,
    /// Origens das palavras ("autor", "fonte", "adicionada").
    pub palavras: Vec<String>,
    pub ignorar: Vec<String>,
    /// Tamanho mínimo do componente (autores, países, IES); 1 = sem filtro.
    pub agrupamento_minimo: usize,
}

impl Default for ConfigRel {
    fn default() -> Self {
        ConfigRel {
            unidade: "Words".into(),
            matriz: "CoOccurrence".into(),
            similaridade: "EquivalenceIndex".into(),
            algoritmo: "CentersSimples".into(),
            minimo_frequencia: 1,
            minimo_coocorrencia: 1.0,
            tamanho_minimo: 2,
            tamanho_maximo: 15,
            corte: 0.0,
            mapeadores: vec!["nucleo".into()],
            k_core: 2,
            indices: ["h", "g", "hg", "q2", "media", "soma", "minimo", "maximo"].iter().map(|s| s.to_string()).collect(),
            palavras: vec!["autor".into(), "fonte".into()],
            ignorar: Vec::new(),
            agrupamento_minimo: 1,
        }
    }
}

impl ConfigRel {
    pub fn mapeador_principal(&self) -> &str {
        self.mapeadores.first().map(|s| s.as_str()).unwrap_or("nucleo")
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct PeriodoRel {
    pub nome: String,
    pub documentos: usize,
    /// Documentos com pelo menos um item; `None` = `documentos`.
    pub documentos_com_itens: Option<usize>,
    /// "Grupos de <itens>": itens do conjunto original, antes da redução.
    pub itens: usize,
    pub grafias: Option<usize>,
    pub itens_reduzidos: usize,
    pub rede_nos: usize,
    pub rede_arestas: usize,
    /// Nós em agrupamentos; `None` = soma dos grupos.
    pub itens_agrupados: Option<usize>,
    /// Nós sem agrupamento; `None` = rede_nos − agrupados.
    pub itens_sem_agrupamento: Option<usize>,
    pub grupos: Vec<GrupoRel>,
    pub rede: Option<RedeRel>,
    pub qualidade: Option<Qualidade>,
    pub pivos: Option<Pivos>,
    /// Figuras prontas; as ausentes são desenhadas por este crate quando há `rede`.
    pub diagrama_svg: Option<String>,
    pub halo_svg: Option<String>,
    /// Rede de cada agrupamento (mesma ordem de `grupos`).
    pub redes_grupos: Vec<Option<String>>,
    /// Dendrograma do período (figura, nota e leitura), vindo do redes-analises.
    pub dendrograma: Vec<Bloco>,
    pub ies: Option<IesInfo>,
    pub filtro_agrupamento: Option<FiltroAgrupamento>,
}

impl PeriodoRel {
    pub fn docs_com_itens(&self) -> usize {
        self.documentos_com_itens.unwrap_or(self.documentos)
    }
    pub fn agrupados(&self) -> usize {
        self.itens_agrupados.unwrap_or_else(|| self.grupos.iter().map(|g| g.itens()).sum())
    }
    pub fn sem_agrupamento(&self) -> usize {
        self.itens_sem_agrupamento.unwrap_or_else(|| self.rede_nos.saturating_sub(self.agrupados()))
    }
    pub fn maior_grupo(&self) -> usize {
        self.grupos.iter().map(|g| g.itens()).max().unwrap_or(0)
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct GrupoRel {
    /// Posição (1-based) na lista original de agrupamentos.
    pub id: usize,
    /// Rótulo guardado (chave de ordenação e de união de halos).
    pub rotulo: String,
    /// Rótulo atual, de exibição (item central).
    pub exibicao: String,
    /// Rótulo novo (termos distintivos), quando há.
    pub rotulo_novo: Option<String>,
    pub indicativo: bool,
    /// Identificadores dos nós do agrupamento.
    pub nos: Vec<i64>,
    /// Número de itens, quando `nos` não vem preenchido.
    pub tamanho: usize,
    pub silhueta: Option<f64>,
    pub ano_medio: Option<f64>,
    pub documentos_nucleo: Option<usize>,
    pub centralidade: f64,
    pub densidade: f64,
    pub centralidade_faixa: f64,
    pub densidade_faixa: f64,
    /// Índices de desempenho: chaves "nucleo:h", "interseccao:g"...
    pub medidas: BTreeMap<String, f64>,
    /// Documentos por mapeador, para o relatório estendido.
    pub documentos: BTreeMap<String, Vec<DocumentoRel>>,
}

impl GrupoRel {
    pub fn itens(&self) -> usize {
        if self.nos.is_empty() {
            self.tamanho
        } else {
            self.nos.len()
        }
    }
    pub fn nome_exibicao(&self) -> &str {
        if self.exibicao.is_empty() {
            "Sem grupo"
        } else {
            &self.exibicao
        }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct DocumentoRel {
    pub titulo: String,
    pub autores: String,
    pub ano: String,
    pub fonte: String,
    pub citacoes: i64,
    /// Referências no formato guardado ("AUTOR, ANO, FONTE, Vvol, Ppág, Título").
    pub referencias: Vec<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct RedeRel {
    pub nos: Vec<NoRel>,
    pub arestas: Vec<ArestaRel>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct NoRel {
    pub id: i64,
    pub rotulo: String,
    pub frequencia: usize,
    /// Índice (0-based) em `PeriodoRel::grupos`; `None` = sem agrupamento.
    pub grupo: Option<usize>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct ArestaRel {
    pub a: i64,
    pub b: i64,
    pub peso: f64,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct Qualidade {
    /// "ok", "atencao", "ruim" ou "indefinido".
    pub nivel: String,
    pub n_nos: usize,
    pub q: Option<f64>,
    pub q_louvain: Option<f64>,
    pub razao: Option<f64>,
    pub silhueta_media: Option<f64>,
    pub pct_agrupados: f64,
    pub pct_em_grupos_grandes: Option<f64>,
    pub pct_silhueta_negativa: Option<f64>,
    pub avisos: Vec<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct Pivos {
    pub n_nos: usize,
    pub suficiente: bool,
    pub itens: Vec<PivoItem>,
    pub termos_descritores: Vec<TermoDescritor>,
    pub avisos: Vec<String>,
    pub nao_calculado: Option<String>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct PivoItem {
    pub no: i64,
    pub rotulo: String,
    pub intermediacao: f64,
    pub grupos_vizinhos: usize,
    /// Índice (0-based) do agrupamento do nó.
    pub grupo: Option<usize>,
    pub frequencia: usize,
    pub sigma: Option<f64>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct TermoDescritor {
    pub rotulo: String,
    pub proporcao_documentos: f64,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct IesInfo {
    pub unioes: Vec<UniaoIes>,
    pub componentes_pequenos: usize,
    pub componente_minimo: usize,
    pub isolados: usize,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct UniaoIes {
    pub adotado: String,
    pub variantes: Vec<VarianteIes>,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct VarianteIes {
    pub nome: String,
    pub documentos: usize,
    pub motivo: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct FiltroAgrupamento {
    pub minimo: usize,
    pub grupos_antes: usize,
    pub grupos_depois: usize,
    pub nos_sem_agrupamento: usize,
    pub isolados: usize,
}
