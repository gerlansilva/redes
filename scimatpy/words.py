"""Canonicalização de palavras-chave.

Antes de agrupar por plural, é preciso escolher uma grafia por termo: a mesma
palavra aparece em caixa alta, baixa, com hífen, com acento ou no plural. A
escolha é a grafia mais frequente (empate pela mais curta e depois pela ordem
alfabética). Sinônimos explícitos, num arquivo ``canônico = variante; variante``,
entram antes dessa contagem.
"""

from __future__ import annotations

from pathlib import Path

from .text_utils import chave


class Sinonimos:
    """Pares declarados à mão entre um termo canônico e suas variantes."""

    def __init__(self, caminho: str | Path | None = None) -> None:
        self.canonico: dict[str, str] = {}
        if not caminho:
            return
        for linha in Path(caminho).read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            canonico, variantes = linha.split("=", 1)
            for variante in variantes.split(";"):
                variante = variante.strip()
                if variante:
                    self.canonico[chave(variante)] = canonico.strip()

    def aplica(self, termo: str) -> str | None:
        return self.canonico.get(chave(termo))


class Canonicalizador:
    """Escolhe uma grafia por termo e reescreve listas com ela."""

    def __init__(self, sinonimos: Sinonimos | None = None) -> None:
        self.contagem: dict[str, dict[str, int]] = {}
        self.sinonimos = sinonimos or Sinonimos()

    def registra(self, termos) -> None:
        for termo in termos:
            k = chave(termo)
            if not k:
                continue
            self.contagem.setdefault(k, {})
            self.contagem[k][termo] = self.contagem[k].get(termo, 0) + 1

    def escolha(self, termo: str) -> str:
        declarado = self.sinonimos.aplica(termo)
        if declarado:
            return declarado
        opcoes = self.contagem.get(chave(termo))
        if not opcoes:
            return termo
        return sorted(opcoes.items(), key=lambda par: (-par[1], len(par[0]), par[0]))[0][0]

    def aplica(self, termos) -> list[str]:
        vistos = []
        for termo in termos:
            canonico = self.escolha(termo)
            if canonico not in vistos:
                vistos.append(canonico)
        return vistos

    def variantes(self) -> dict[str, dict[str, int]]:
        return {k: v for k, v in self.contagem.items() if len(v) > 1}
