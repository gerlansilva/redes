//! CSS do relatório (tema claro; azul #2F2BFF / #0B1F66), igual ao do Python.

pub const CSS_PASTA: &str = r####"
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
       color:#1F2A44; max-width: 980px; margin: 32px auto; padding: 0 24px;
       line-height:1.5; font-size:14px; }
a { color:#1D3E8F; }
h1 { font-size:24px; color:#0B1F66; border-bottom:1px solid #D7DBE6;
     padding-bottom:6px; }
h2 { font-size:18px; color:#0B1F66; margin-top:28px; }
h3 { font-size:15px; color:#1F2A44; }
table { border-collapse:collapse; margin:12px 0 4px; width:100%; }
caption { caption-side:top; text-align:left; font-weight:600;
          padding-bottom:6px; color:#1F2A44; }
th, td { border:1px solid #E3E6EC; padding:5px 8px; text-align:left;
         vertical-align:top; }
th { background:#F5F6F9; color:#0B1F66; font-weight:600; }
img, svg { max-width:100%; height:auto; }
img.mapa-sobreposicao { display:block; margin:10px auto; }
.cabecalho { display:flex; align-items:center; justify-content:space-between;
             gap:24px; border-bottom:1px solid #E3E6EC;
             padding-bottom:10px; margin-bottom:24px; }
.marca-relatorio { font-size:10px; font-weight:600; letter-spacing:.14em;
                   text-transform:uppercase; color:#64748B; margin:0; }
.logo-relatorio { display:block; height:32px; width:auto; flex:none; }
.voltar { margin:0 0 10px; font-size:13px; }
.sumario { position:sticky; top:0; background:#fff; padding:8px 0; border-bottom:1px solid #E6E9F2; margin:0 0 18px;
  display:flex; flex-wrap:wrap; gap:6px 16px; font-size:13px; z-index:2; }
.miniaturas { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:14px; margin:8px 0 22px; }
.miniaturas figure { margin:0; border:1px solid #E6E9F2; border-radius:10px; padding:8px; background:#fff; }
.miniaturas img { width:100%; height:auto; display:block; }
.miniaturas figcaption { font-size:12px; color:#475569; margin-top:6px; }
.fonte { color:#64748B; font-size:12px; margin:0 0 18px; }
.aviso { background:#FFF9E0; border:1px solid #F0D98A; border-left:4px solid #FFC400; border-radius:8px; padding:8px 14px; margin:0 0 16px; font-size:13px; color:#5C4500; }
.aviso ul { margin:6px 0 0; padding-left:18px; }
.num { text-align:right; }
nav a { margin-right:14px; }

.metodo p { margin:6px 0; }
.metodo ul, .metodo ol { margin:4px 0 8px; padding-left:22px; }
.metodo li { margin:2px 0; }
.metodo code.formula { background:#F5F6F9; border:1px solid #E3E6EC; border-radius:4px;
                       padding:1px 6px; font-family:inherit; white-space:nowrap; }
.rolagem { overflow-x:auto; max-width:100%; }
@media print { .rolagem { overflow:visible; } }
.metodo .nota-metodo { color:#475569; font-size:12.5px; }
@media print { .metodo { break-inside:auto; } .metodo p, .metodo li { orphans:3; widows:3; } }
.selo-q { display:inline-block; padding:1px 9px; border-radius:999px; border:1px solid;
          font-size:12px; font-weight:600; white-space:nowrap; line-height:1.5; }
.selo-q-ok { color:#067647; background:#E6F8EE; border-color:#9ED8BA; }
.selo-q-atencao { color:#7A4E00; background:#FFF3C4; border-color:#E8CB6A; }
.selo-q-ruim { color:#B42318; background:#FEF3F2; border-color:#F4A9A1; }
.selo-q-indefinido { color:#475569; background:#F1F3F8; border-color:#C5CCDB; }
.avisos-qualidade { margin:4px 0 14px; font-size:12.5px; color:#334155; }
.avisos-qualidade ul { margin:2px 0 6px; padding-left:20px; }
.avisos-qualidade li { margin:1px 0; }
.cel-agrupamento { min-width:170px; }
.rot-novo { color:#0B1F66; }
.rot-ind { color:#7A4E00; font-size:11px; font-weight:600; white-space:nowrap; }
.rot-atual { color:#64748B; font-size:11px; }
@media print { .selo-q { -webkit-print-color-adjust:exact; print-color-adjust:exact; } }
"####;

pub const CSS_UNICO_EXTRA: &str = r####"
.sumario { position:static; display:block; border:1px solid #E3E6EC; border-radius:8px;
           padding:10px 18px; margin:0 0 24px; background:#FAFBFD; }
.sumario h2 { margin:6px 0 8px; font-size:16px; }
.sumario ol { list-style:none; margin:0; padding:0; }
.sumario li { margin:2px 0; }
.sumario li.n2 { font-weight:600; margin-top:8px; }
.sumario li.n3 { padding-left:20px; }
.sumario li.n4 { padding-left:40px; font-size:12.5px; }
.sumario small { color:#64748B; }
.capa { text-align:center; padding:28px 0 18px; border-bottom:1px solid #D7DBE6; margin-bottom:24px; }
.capa img.logo-capa, .capa svg.logo-capa { width:220px; height:auto; margin:0 auto 10px; display:block; }
.capa h1 { border:0; font-size:30px; margin:6px 0 4px; }
.capa .projeto { font-size:16px; color:#1F2A44; margin:0 0 14px; }
.capa dl { display:inline-grid; grid-template-columns:auto auto; gap:4px 18px; text-align:left;
           margin:6px 0 0; font-size:14px; }
.capa dt { color:#64748B; }
.capa dd { margin:0; font-weight:600; }
h2 { border-bottom:1px solid #D7DBE6; padding-bottom:4px; }
h3 { color:#0B1F66; margin-top:22px; }
h4 { color:#1F2A44; margin:20px 0 6px; font-size:14px; }
h5 { color:#1F2A44; margin:16px 0 6px; font-size:13.5px; }
figure { margin:14px 0 18px; text-align:center; }
figure svg { display:block; margin:0 auto; max-width:100%; height:auto; }
figcaption { font-size:12.5px; color:#475569; margin-top:6px; text-align:left; }
table { font-size:13px; }
table.larga { font-size:11.5px; }
.rolagem { overflow-x:auto; max-width:100%; }
@media print { .rolagem { overflow:visible; } }
table.larga th, table.larga td { padding:4px 5px; }
.redes-grupos figure { max-width:720px; margin:12px auto; border:1px solid #E6E9F2;
                       border-radius:8px; padding:6px; }
.nota { color:#475569; font-size:13px; font-style:italic; }
@media print {
  @page { size: A4; margin: 16mm 14mm; }
  html, body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { max-width:none; margin:0; padding:0; font-size:11pt; }
  .sumario { position:static; background:none; }
  h2 { break-before: page; page-break-before: always; }
  h2, h3, h4, caption, h4 + p, h3 + p { break-after: avoid; page-break-after: avoid; }
  figure, .aviso, .capa { break-inside: avoid; page-break-inside: avoid; }
  tr { break-inside: avoid; page-break-inside: avoid; }
  thead { display: table-header-group; }
  table { break-inside: auto; }
  a { color: inherit; text-decoration: none; }
  .sumario a { color:#1D3E8F; }
}
"####;
