import hashlib
import json
import shutil
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from redes import api, build, linha_do_tempo
from redes.kb import ProjetoScimat
from redes.loaders.base import DocumentoFonte
from redes.viz import linha_do_tempo as viz

SERJ = Path("/home/claude/t/serj_auto.redes")
NS = "{http://www.w3.org/2000/svg}"

TEMAS = [["alfa", "beta", "gama"], ["delta", "epsilon", "zeta"], ["eta", "teta", "iota"]]


def _config(unidade="Words", minimo=2, maximo=15):
    return api._config({"unidade": unidade, "minimo_frequencia": minimo,
                        "tamanho_maximo": maximo, "tamanho_minimo": 2,
                        "mapeadores": ["nucleo"]})


def _docs(anos=range(2010, 2020), temas=TEMAS, por_ano=3, palavras_extra=None):
    docs = []
    n = 0
    for ano in anos:
        for k in range(por_ano):
            tema = temas[(n + k) % len(temas)]
            palavras = list(tema) + (palavras_extra or [])
            docs.append(DocumentoFonte(
                titulo=f"Estudo {n}", ano=str(ano) if ano is not None else "",
                autores=[f"Autor{n % 4}, A."], palavras_autor=palavras,
                referencias=[f"Ref{j} A., {1990 + j}, Rev" for j in {(n // 2) % 5, (n // 2 + 1) % 5}]))
            n += 1
    return docs


def _projeto(docs, periodos=None):
    pasta = tempfile.TemporaryDirectory()
    destino = Path(pasta.name) / "p.redes"
    build.constroi(docs, destino, periodos)
    return pasta, destino


def _dados(docs, **kw):
    pasta, destino = _projeto(docs)
    try:
        with ProjetoScimat(destino) as kb:
            return linha_do_tempo.constroi(kb, _config(), **kw)
    finally:
        pasta.cleanup()


def _arvore(texto):
    return ET.fromstring(texto)


def _nos(dados):
    return [n for f in dados["faixas"] for n in f["nos"]]


def _no(id_, rotulo, ano, freq=3, **kw):
    base = {"id": id_, "rotulo": rotulo, "ano": ano, "frequencia": freq, "rajada": False,
            "rajada_inicio": None, "rajada_fim": None, "primeiro": ano, "ultimo": ano}
    base.update(kw)
    return base


def _faixa(indice, rotulo, nos):
    return {"indice": indice, "rotulo": rotulo, "frequencia_total": sum(n["frequencia"] for n in nos),
            "itens_total": len(nos), "nos": nos}


def _manual(faixas, ligacoes=(), **kw):
    d = {"unidade": "Words", "faixas": faixas, "ligacoes": list(ligacoes),
         "anos": [min(n["ano"] for f in faixas for n in f["nos"]),
                  max(n["ano"] for f in faixas for n in f["nos"])] if faixas else [],
         "atividade": True, "posicao": "media", "avisos": [], "omitidos": {"itens": 0, "agrupamentos": 0, "sem_ano": 0}}
    d.update(kw)
    return d


class EstruturaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dados = _dados(_docs())

    def test_estrutura_e_serializavel(self):
        d = self.dados
        for chave in ("faixas", "ligacoes", "anos", "avisos", "omitidos", "unidade"):
            self.assertIn(chave, d)
        self.assertEqual(d["unidade"], "Words")
        self.assertGreaterEqual(len(d["faixas"]), 1)
        json.dumps(d)
        for f in d["faixas"]:
            for chave in ("indice", "rotulo", "nos"):
                self.assertIn(chave, f)
            for n in f["nos"]:
                for chave in ("id", "rotulo", "ano", "frequencia", "rajada", "primeiro", "ultimo"):
                    self.assertIn(chave, n)
                self.assertLessEqual(n["primeiro"], n["ano"])
                self.assertGreaterEqual(n["ultimo"], n["ano"])

    def test_faixas_por_frequencia_total(self):
        totais = [f["frequencia_total"] for f in self.dados["faixas"]]
        self.assertEqual(totais, sorted(totais, reverse=True))

    def test_anos_e_ano_medio(self):
        d = self.dados
        nos = _nos(d)
        self.assertEqual(d["anos"], [min(n["ano"] for n in nos), max(n["ano"] for n in nos)])
        self.assertTrue(all(2010 <= n["ano"] <= 2019 for n in nos))

    def test_ligacoes_validas(self):
        ids = {n["id"] for n in _nos(self.dados)}
        for l in self.dados["ligacoes"]:
            self.assertIn(l["origem"], ids)
            self.assertIn(l["destino"], ids)
            self.assertGreater(l["valor"], 0)

    def test_determinismo(self):
        a, b = _dados(_docs()), _dados(_docs())
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(viz.svg(a, "T"), viz.svg(b, "T"))


class LimitesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # muitos temas pequenos: mais de 40 itens e faixas com mais de 8 itens
        temas = [[f"t{t}p{k}" for k in range(4)] for t in range(16)]
        grande = [[f"g{k}" for k in range(12)]]
        cls.docs = _docs(temas=temas + grande * 4, por_ano=8)

    def test_limite_global_de_40_nos(self):
        d = _dados(self.docs)
        self.assertLessEqual(len(_nos(d)), 40)
        self.assertEqual(len(_nos(d)), 40)
        self.assertGreater(d["omitidos"]["itens"], 0)
        self.assertTrue(any("de fora" in a for a in d["avisos"]))

    def test_limite_por_faixa(self):
        d = _dados(self.docs, max_nos=100, por_faixa=3)
        self.assertTrue(all(len(f["nos"]) <= 3 for f in d["faixas"]))
        d = _dados(self.docs, max_nos=100)
        self.assertTrue(all(len(f["nos"]) <= 8 for f in d["faixas"]))

    def test_mais_frequentes_escolhidos_globalmente(self):
        d = _dados(self.docs, max_nos=5, por_faixa=8)
        escolhidos = sorted(n["frequencia"] for n in _nos(d))
        todos = sorted((n["frequencia"] for n in _nos(_dados(self.docs, max_nos=1000, por_faixa=1000))),
                       reverse=True)
        self.assertEqual(escolhidos, sorted(todos[:5]))

    def test_ligacoes_cruzadas_no_maximo_6_e_internas_top3(self):
        d = _dados(self.docs, max_nos=1000, por_faixa=1000)
        self.assertLessEqual(sum(1 for l in d["ligacoes"] if l["cruzada"]), 6)
        faixa_de = {n["id"]: i for i, f in enumerate(d["faixas"]) for n in f["nos"]}
        for l in d["ligacoes"]:
            self.assertEqual(faixa_de[l["origem"]] != faixa_de[l["destino"]], l["cruzada"])


class SemAnosEUmAnoTest(unittest.TestCase):
    def test_documentos_sem_ano_sao_omitidos_com_aviso(self):
        docs = _docs(anos=[None], por_ano=6)
        pasta, destino = _projeto(docs)
        try:
            with ProjetoScimat(destino) as kb:
                d = linha_do_tempo.constroi(kb, _config())
        finally:
            pasta.cleanup()
        self.assertEqual(d["faixas"], [])
        self.assertTrue(d["avisos"])
        texto = viz.svg(d, "Sem anos")
        _arvore(texto)
        self.assertIn("sem ano", texto)

    def test_um_so_ano_avisa_e_desenha(self):
        d = _dados(_docs(anos=[2015], por_ano=9))
        self.assertEqual(d["anos"][0], d["anos"][1])
        self.assertTrue(any("mesmo ano" in a for a in d["avisos"]))
        raiz = _arvore(viz.svg(d, "Um ano"))
        self.assertGreater(len(raiz.findall(f".//{NS}circle")), 0)

    def test_sem_agrupamentos(self):
        pasta, destino = _projeto(_docs(por_ano=1))
        try:
            with ProjetoScimat(destino) as kb:
                vazio = linha_do_tempo.constroi(kb, _config(minimo=999))
        finally:
            pasta.cleanup()
        self.assertEqual(vazio["faixas"], [])
        self.assertTrue(vazio["avisos"])
        _arvore(viz.svg(vazio, "Vazio"))
        _arvore(viz.svg({"faixas": [], "ligacoes": [], "avisos": []}))


class EixoTest(unittest.TestCase):
    def test_eixo_recortado_aos_nos_com_margem_de_um_ano(self):
        d = _manual([_faixa(0, "A", [_no(1, "x", 2012), _no(2, "y", 2016)])], atividade=False)
        textos = [t.text for t in _arvore(viz.svg(d)).iter(f"{NS}text") if t.get("class") == "lt-eixo"]
        anos = sorted({int(t) for t in textos})
        self.assertEqual(anos[0], 2011)
        self.assertEqual(anos[-1], 2017)
        self.assertEqual(anos, list(range(2011, 2018)))

    def test_ticks_legiveis_em_intervalo_longo(self):
        d = _manual([_faixa(0, "A", [_no(1, "x", 1950), _no(2, "y", 2020)])], atividade=False)
        textos = {int(t.text) for t in _arvore(viz.svg(d)).iter(f"{NS}text") if t.get("class") == "lt-eixo"}
        self.assertLessEqual(len(textos), 15)
        self.assertTrue(all(a % 5 == 0 for a in textos))


class RajadaEAtividadeTest(unittest.TestCase):
    def test_rajada_so_com_anel_e_legenda_condicional(self):
        sem = _manual([_faixa(0, "A", [_no(1, "x", 2012, primeiro=2010, ultimo=2014),
                                       _no(2, "y", 2016)])])
        texto = viz.svg(sem)
        self.assertNotIn("rajada", texto.lower())
        com = _manual([_faixa(0, "A", [_no(1, "x", 2012, rajada=True, rajada_inicio=2011,
                                           rajada_fim=2013, primeiro=2010, ultimo=2014),
                                       _no(2, "y", 2016)])])
        t2 = viz.svg(com)
        self.assertIn("anel vermelho", t2)
        self.assertEqual(t2.count('stroke="#DC2626" stroke-width="2"/>') , 2)  # anel + amostra da legenda

    def test_rajadas_reais_obedecem_as_regras(self):
        # termo "surto" aparece só nos últimos anos; os demais são constantes
        docs = []
        n = 0
        for ano in range(2010, 2020):
            for k in range(4):
                palavras = ["base1", "base2"]
                if ano >= 2017 and k < 3:
                    palavras += ["surto", "base1"]
                docs.append(DocumentoFonte(titulo=f"E{n}", ano=str(ano), palavras_autor=palavras))
                n += 1
        d = _dados(docs)
        raj = [n_ for n_ in _nos(d) if n_["rajada"]]
        self.assertTrue(raj)
        self.assertIn("SURTO", {r["rotulo"].upper() for r in raj})
        from redes import rajadas
        pasta, destino = _projeto(docs)
        try:
            with ProjetoScimat(destino) as kb:
                top = rajadas.calcula(kb.conexao, "palavras", limite=10, minimo_documentos=3)["rajadas"]
        finally:
            pasta.cleanup()
        permitidos = {r["termo"] for r in top if r["documentos"] >= 3}
        from redes.text_utils import chave
        self.assertTrue({chave(r["rotulo"]) for r in raj} <= {chave(p) for p in permitidos})
        self.assertLessEqual(len(raj), 10)

    def test_referencia_sem_linha_de_atividade_nem_tracos(self):
        pasta, destino = _projeto(_docs(por_ano=6))
        try:
            with ProjetoScimat(destino) as kb:
                d = linha_do_tempo.constroi(kb, _config("References", minimo=2))
        finally:
            pasta.cleanup()
        self.assertFalse(d["atividade"])
        self.assertTrue(_nos(d))
        for n in _nos(d):
            self.assertEqual(n["primeiro"], n["ultimo"])
            self.assertIsNone(n["rajada_inicio"])
            self.assertTrue(1990 <= n["ano"] <= 1995, n)
        raiz = _arvore(viz.svg(d, "Refs"))
        self.assertEqual(raiz.findall(f".//{NS}line[@stroke-opacity='.38']"), [])
        self.assertNotIn("linha fina", viz.svg(d))
        self.assertIn("ano da própria referência", viz.svg(d))

    def test_palavras_tem_linha_de_atividade(self):
        d = _manual([_faixa(0, "A", [_no(1, "x", 2013, primeiro=2011, ultimo=2015), _no(2, "y", 2012)])])
        raiz = _arvore(viz.svg(d))
        linhas = [e for e in raiz.iter(f"{NS}line") if e.get("stroke-opacity") == ".38"]
        self.assertEqual(len(linhas), 1)
        self.assertIn("linha fina", viz.svg(d))


class SvgTest(unittest.TestCase):
    def test_escape_xml_controles_emoji_rtl(self):
        feio = [_no(1, 'A<b>&"\'\x00\x07‮ evil 😀', 2012),
                _no(2, "שלום עולם مرحبا", 2014),
                _no(3, "x" * 80, 2015)]
        d = _manual([_faixa(0, "Faixa <&> \x01 ‭", feio)], avisos=["aviso <&>\x02"])
        texto = viz.svg(d, 'Título <"&"> \x00', rotulos={0: "Novo <rótulo> & \x03"})
        raiz = _arvore(texto)
        self.assertEqual(raiz.tag, NS + "svg")
        self.assertNotRegex(texto, "[\x00-\x08\x0b\x0c\x0e-\x1f‮‭]")
        self.assertIn("😀", texto)
        self.assertIn("שלום", texto)
        self.assertIn("Novo &lt;rótulo&gt; &amp;", texto)

    def test_truncamento_so_acima_de_34_e_titulo_completo(self):
        exato = "a" * 34
        longo = "b" * 35
        d = _manual([_faixa(0, "A", [_no(1, exato, 2012), _no(2, longo, 2015)])])
        texto = viz.svg(d)
        self.assertIn(">" + exato + "<", texto)
        self.assertNotIn(">" + longo + "<", texto)
        self.assertIn("b" * 33 + "…", texto)
        self.assertIn(longo, texto)       # no <title>

    def test_largura_por_classe(self):
        self.assertAlmostEqual(viz.largura("A"), 8.2)
        self.assertAlmostEqual(viz.largura("a"), 6.6)
        self.assertAlmostEqual(viz.largura("1"), 7.0)
        self.assertAlmostEqual(viz.largura("i"), 3.4)
        self.assertAlmostEqual(viz.largura("A", 24), 16.4)

    def test_estrutura_acessivel_e_ids_unicos(self):
        d1 = _manual([_faixa(0, "A", [_no(1, "x", 2012), _no(2, "y", 2014)])])
        d2 = _manual([_faixa(0, "B", [_no(1, "x", 2012), _no(2, "y", 2014)])])
        r1 = _arvore(viz.svg(d1, "T"))
        self.assertEqual(r1.get("role"), "img")
        self.assertEqual(r1.get("width"), "1100")
        ids1 = [e.get("id") for e in r1.iter() if e.get("id")]
        ids2 = [e.get("id") for e in _arvore(viz.svg(d2, "T")).iter() if e.get("id")]
        self.assertEqual(len(ids1), len(set(ids1)))
        self.assertFalse(set(ids1) & set(ids2))
        labelled = r1.get("{http://www.w3.org/2000/svg}x") or r1.get("aria-labelledby")
        for i in labelled.split():
            self.assertIn(i, ids1)
        self.assertNotIn("<script", viz.svg(d1))

    def test_altura_proporcional_e_faixa_minima(self):
        uma = _manual([_faixa(0, "A", [_no(1, "x", 2012)])])
        tres = _manual([_faixa(i, f"F{i}", [_no(10 * i + 1, "x", 2012)]) for i in range(3)])
        h1 = float(_arvore(viz.svg(uma)).get("height"))
        h3 = float(_arvore(viz.svg(tres)).get("height"))
        self.assertGreaterEqual(h3 - h1, 2 * viz.FAIXA_MIN)

    def test_colisao_resolvida_verticalmente(self):
        nos = [_no(i, f"palavra{i}", 2012, freq=3) for i in range(1, 5)]
        d = _manual([_faixa(0, "A", nos)])
        raiz = _arvore(viz.svg(d))
        ys = sorted({round(float(c.get("cy")), 1) for c in raiz.iter(f"{NS}circle") if c.get("fill-opacity") == ".88"})
        self.assertEqual(len(ys), 4)

    def test_legenda_nao_encosta_no_eixo(self):
        d = _manual([_faixa(0, "A", [_no(1, "x", 2012), _no(2, "y", 2014)])])
        raiz = _arvore(viz.svg(d))
        eixo_baixo = max(float(t.get("y")) for t in raiz.iter(f"{NS}text") if t.get("class") == "lt-eixo")
        legenda = min(float(t.get("y")) for t in raiz.iter(f"{NS}text") if t.get("class") == "lt-sub"
                      and float(t.get("y")) > eixo_baixo)
        self.assertGreaterEqual(legenda - eixo_baixo, 30)

    def test_rotulos_novos_por_indice(self):
        d = _manual([_faixa(0, "Antigo", [_no(1, "x", 2012)]), _faixa(5, "Outro", [_no(2, "y", 2013)])])
        texto = viz.svg(d, rotulos={5: "Rótulo novo"})
        self.assertIn("Rótulo novo", texto)
        self.assertIn("Antigo", texto)
        self.assertNotIn("Outro", texto)
        self.assertIn("Rótulo novo", viz.svg(d, rotulos={"5": {"rotulo": "Rótulo novo"}}))


class ProjetoRealTest(unittest.TestCase):
    def test_nao_grava_no_projeto(self):
        pasta, destino = _projeto(_docs())
        try:
            antes = hashlib.sha256(destino.read_bytes()).hexdigest()
            with ProjetoScimat(destino) as kb:
                periodos = len(kb.periodos())
                linha_do_tempo.constroi(kb, _config())
                linha_do_tempo.constroi(kb, _config("References", minimo=2))
                self.assertEqual(len(kb.periodos()), periodos)
            self.assertEqual(hashlib.sha256(destino.read_bytes()).hexdigest(), antes)
            self.assertEqual([p.name for p in destino.parent.iterdir()], [destino.name])
        finally:
            pasta.cleanup()

    @unittest.skipUnless(SERJ.exists(), "projeto de exemplo ausente")
    def test_serj_palavras_e_referencias(self):
        with tempfile.TemporaryDirectory() as pasta:
            copia = Path(pasta) / "serj_auto.redes"
            shutil.copy(SERJ, copia)
            antes = hashlib.sha256(SERJ.read_bytes()).hexdigest()
            for unidade, minimo in (("Words", 3), ("References", 8)):
                with ProjetoScimat(copia) as kb:
                    t = time.perf_counter()
                    d = linha_do_tempo.constroi(kb, _config(unidade, minimo=minimo))
                    texto = viz.svg(d, f"serj {unidade}")
                    gasto = time.perf_counter() - t
                self.assertLess(gasto, 5.0, f"{unidade}: {gasto:.2f}s")
                self.assertTrue(d["faixas"])
                self.assertLessEqual(len(_nos(d)), 40)
                self.assertTrue(all(len(f["nos"]) <= 8 for f in d["faixas"]))
                _arvore(texto)
                self.assertEqual(d["atividade"], unidade == "Words")
            self.assertEqual(hashlib.sha256(SERJ.read_bytes()).hexdigest(), antes)


NOVO142 = Path("/home/claude/t/novo142.redes")
JS_LIMITES = """() => {
  const r = document.querySelector('clipPath rect');
  const A = {x0: +r.getAttribute('x'), y0: +r.getAttribute('y'),
             x1: +r.getAttribute('x') + +r.getAttribute('width'),
             y1: +r.getAttribute('y') + +r.getAttribute('height')};
  const fora = [];
  const tol = 0.6;
  const confere = (el, nome, y) => {
    const b = el.getBBox();
    if (b.x < A.x0 - tol || b.x + b.width > A.x1 + tol ||
        (y && (b.y < A.y0 - tol || b.y + b.height > A.y1 + tol)))
      fora.push(nome + ' ' + (el.textContent || el.getAttribute('d') || '').slice(0, 40) +
                ' [' + [b.x, b.y, b.x + b.width, b.y + b.height].map(v => v.toFixed(1)) + ']');
  };
  document.querySelectorAll('text.lt-rot, text.lt-eixo').forEach(e => confere(e, 'texto', false));
  document.querySelectorAll('.lt-plot path, .lt-plot line').forEach(e => confere(e, 'forma', true));
  return {fora, area: A, textos: document.querySelectorAll('text.lt-rot').length};
}"""


def _playwright():
    try:
        import os
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except Exception:
        return None


@unittest.skipUnless(_playwright(), "Playwright indisponível")
class DentroDaAreaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory()
        cls.casos = {}
        for nome, origem, unidade, minimo in (("serj_palavras", SERJ, "Words", 3),
                                              ("serj_refs", SERJ, "References", 8),
                                              ("novo142_palavras", NOVO142, "Words", 3)):
            if not origem.exists():
                continue
            copia = Path(cls.pasta.name) / f"{nome}.redes"
            shutil.copy(origem, copia)
            with ProjetoScimat(copia) as kb:
                cls.casos[nome] = viz.svg(linha_do_tempo.constroi(kb, _config(unidade, minimo=minimo)), nome)
        longos = [_no(i, "Rótulo extremamente comprido número %d com muitas palavras e W" % i + "W" * 30,
                      2010 + 2 * (i % 5), freq=1 + i, rajada=(i % 3 == 0)) for i in range(1, 9)]
        longos.append(_no(20, "M" * 60, 2010))
        longos.append(_no(21, "M" * 60, 2018, freq=9))
        faixas = [_faixa(0, "Faixa " + "muito longa " * 12, longos[:5]), _faixa(1, "B", longos[5:])]
        ligs = [{"origem": 1, "destino": 2, "valor": 1.0, "cruzada": False},
                {"origem": 1, "destino": 6, "valor": .9, "cruzada": True},
                {"origem": 21, "destino": 20, "valor": .8, "cruzada": True},
                {"origem": 5, "destino": 8, "valor": .7, "cruzada": True}]
        cls.casos["longos"] = viz.svg(_manual(faixas, ligs, anos=[2010, 2018]), "Rótulos longos")

    @classmethod
    def tearDownClass(cls):
        cls.pasta.cleanup()

    def test_nada_fora_da_area_do_grafico(self):
        sync = _playwright()
        with sync() as pw:
            nav = pw.chromium.launch()
            try:
                pg = nav.new_page(viewport={"width": 1100, "height": 900})
                for nome, texto in self.casos.items():
                    pg.set_content(f"<!doctype html><meta charset=utf-8><body style='margin:0'>{texto}")
                    r = pg.evaluate(JS_LIMITES)
                    self.assertGreater(r["textos"], 0, nome)
                    self.assertEqual(r["fora"], [], nome)
            finally:
                nav.close()


if __name__ == "__main__":
    unittest.main()
