"""Reconhecimento de países nas afiliações dos documentos.

As bases grafam o país de formas diferentes: a Scopus e o Web of Science
colocam o país no fim da afiliação (``Universidade, Cidade, País``), o OpenAlex
tem uma coluna ``Country`` e o RIS usa ``C1``. Este módulo reduz todas essas
formas a um nome canônico em português, sem depender de biblioteca externa.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# Formas em inglês (e algumas variantes) que aparecem nas exportações.
_PAISES = {
    "afghanistan": "Afeganistão",
    "albania": "Albânia",
    "algeria": "Argélia",
    "andorra": "Andorra",
    "angola": "Angola",
    "argentina": "Argentina",
    "armenia": "Armênia",
    "australia": "Austrália",
    "austria": "Áustria",
    "azerbaijan": "Azerbaijão",
    "bahrain": "Bahrein",
    "bangladesh": "Bangladesh",
    "barbados": "Barbados",
    "belarus": "Bielorrússia",
    "belgium": "Bélgica",
    "belize": "Belize",
    "benin": "Benim",
    "bhutan": "Butão",
    "bolivia": "Bolívia",
    "bosnia and herzegovina": "Bósnia e Herzegovina",
    "botswana": "Botsuana",
    "brazil": "Brasil",
    "brunei": "Brunei",
    "bulgaria": "Bulgária",
    "burkina faso": "Burquina Fasso",
    "burundi": "Burundi",
    "cambodia": "Camboja",
    "cameroon": "Camarões",
    "canada": "Canadá",
    "cape verde": "Cabo Verde",
    "cabo verde": "Cabo Verde",
    "central african republic": "República Centro-Africana",
    "chad": "Chade",
    "chile": "Chile",
    "china": "China",
    "colombia": "Colômbia",
    "comoros": "Comores",
    "congo": "Congo",
    "costa rica": "Costa Rica",
    "croatia": "Croácia",
    "cuba": "Cuba",
    "cyprus": "Chipre",
    "czech republic": "República Tcheca",
    "czechia": "República Tcheca",
    "denmark": "Dinamarca",
    "djibouti": "Djibuti",
    "dominican republic": "República Dominicana",
    "ecuador": "Equador",
    "egypt": "Egito",
    "el salvador": "El Salvador",
    "england": "Reino Unido",
    "equatorial guinea": "Guiné Equatorial",
    "eritrea": "Eritreia",
    "estonia": "Estônia",
    "eswatini": "Essuatíni",
    "swaziland": "Essuatíni",
    "ethiopia": "Etiópia",
    "fiji": "Fiji",
    "finland": "Finlândia",
    "france": "França",
    "gabon": "Gabão",
    "gambia": "Gâmbia",
    "georgia": "Geórgia",
    "germany": "Alemanha",
    "ghana": "Gana",
    "greece": "Grécia",
    "guatemala": "Guatemala",
    "guinea": "Guiné",
    "guinea-bissau": "Guiné-Bissau",
    "honduras": "Honduras",
    "hong kong": "Hong Kong",
    "hungary": "Hungria",
    "iceland": "Islândia",
    "india": "Índia",
    "indonesia": "Indonésia",
    "iran": "Irã",
    "iraq": "Iraque",
    "ireland": "Irlanda",
    "israel": "Israel",
    "italy": "Itália",
    "ivory coast": "Costa do Marfim",
    "cote d'ivoire": "Costa do Marfim",
    "côte d'ivoire": "Costa do Marfim",
    "jamaica": "Jamaica",
    "japan": "Japão",
    "jordan": "Jordânia",
    "kazakhstan": "Cazaquistão",
    "kenya": "Quênia",
    "kosovo": "Kosovo",
    "kuwait": "Kuwait",
    "kyrgyzstan": "Quirguistão",
    "laos": "Laos",
    "latvia": "Letônia",
    "lebanon": "Líbano",
    "lesotho": "Lesoto",
    "liberia": "Libéria",
    "libya": "Líbia",
    "liechtenstein": "Liechtenstein",
    "lithuania": "Lituânia",
    "luxembourg": "Luxemburgo",
    "macau": "Macau",
    "macao": "Macau",
    "madagascar": "Madagascar",
    "malawi": "Maláui",
    "malaysia": "Malásia",
    "maldives": "Maldivas",
    "mali": "Mali",
    "malta": "Malta",
    "mauritania": "Mauritânia",
    "mauritius": "Maurício",
    "mexico": "México",
    "moldova": "Moldávia",
    "monaco": "Mônaco",
    "mongolia": "Mongólia",
    "montenegro": "Montenegro",
    "morocco": "Marrocos",
    "mozambique": "Moçambique",
    "myanmar": "Mianmar",
    "namibia": "Namíbia",
    "nepal": "Nepal",
    "netherlands": "Países Baixos",
    "new zealand": "Nova Zelândia",
    "nicaragua": "Nicarágua",
    "niger": "Níger",
    "nigeria": "Nigéria",
    "north korea": "Coreia do Norte",
    "north macedonia": "Macedônia do Norte",
    "northern ireland": "Reino Unido",
    "norway": "Noruega",
    "oman": "Omã",
    "pakistan": "Paquistão",
    "palestine": "Palestina",
    "panama": "Panamá",
    "papua new guinea": "Papua-Nova Guiné",
    "paraguay": "Paraguai",
    "peru": "Peru",
    "philippines": "Filipinas",
    "poland": "Polônia",
    "portugal": "Portugal",
    "puerto rico": "Porto Rico",
    "qatar": "Catar",
    "republic of ireland": "Irlanda",
    "republic of korea": "Coreia do Sul",
    "romania": "Romênia",
    "russia": "Rússia",
    "russian federation": "Rússia",
    "rwanda": "Ruanda",
    "samoa": "Samoa",
    "san marino": "San Marino",
    "sao tome and principe": "São Tomé e Príncipe",
    "saudi arabia": "Arábia Saudita",
    "scotland": "Reino Unido",
    "senegal": "Senegal",
    "serbia": "Sérvia",
    "seychelles": "Seicheles",
    "sierra leone": "Serra Leoa",
    "singapore": "Singapura",
    "slovakia": "Eslováquia",
    "slovenia": "Eslovênia",
    "solomon islands": "Ilhas Salomão",
    "somalia": "Somália",
    "south africa": "África do Sul",
    "south korea": "Coreia do Sul",
    "south sudan": "Sudão do Sul",
    "spain": "Espanha",
    "sri lanka": "Sri Lanka",
    "sudan": "Sudão",
    "sweden": "Suécia",
    "switzerland": "Suíça",
    "syria": "Síria",
    "taiwan": "Taiwan",
    "tajikistan": "Tadjiquistão",
    "tanzania": "Tanzânia",
    "thailand": "Tailândia",
    "timor-leste": "Timor-Leste",
    "east timor": "Timor-Leste",
    "togo": "Togo",
    "tonga": "Tonga",
    "trinidad and tobago": "Trinidad e Tobago",
    "tunisia": "Tunísia",
    "turkey": "Turquia",
    "turkiye": "Turquia",
    "türkiye": "Turquia",
    "turkmenistan": "Turcomenistão",
    "uganda": "Uganda",
    "ukraine": "Ucrânia",
    "united arab emirates": "Emirados Árabes Unidos",
    "united kingdom": "Reino Unido",
    "united states": "Estados Unidos",
    "united states of america": "Estados Unidos",
    "usa": "Estados Unidos",
    "us": "Estados Unidos",
    "uruguay": "Uruguai",
    "uzbekistan": "Uzbequistão",
    "vanuatu": "Vanuatu",
    "vatican": "Vaticano",
    "venezuela": "Venezuela",
    "vietnam": "Vietnã",
    "viet nam": "Vietnã",
    "wales": "Reino Unido",
    "yemen": "Iêmen",
    "zambia": "Zâmbia",
    "zimbabwe": "Zimbábue",
}


def _chave(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto).strip(" .,;:()[]").lower()
    return texto


def pais(texto: str) -> str:
    """Nome canônico do país, ou vazio quando o texto não é um país."""
    return _PAISES.get(_chave(texto), "")


def _partes(afiliacao: str) -> list[str]:
    texto = (afiliacao or "").replace("\n", " ")
    texto = re.sub(r"\bemail:.*$", "", texto, flags=re.IGNORECASE)
    return [parte.strip(" .,;:()[]") for parte in texto.split(",") if parte.strip()]


def pais_da_afiliacao(afiliacao: str) -> str:
    """País no fim de uma afiliação do tipo ``Instituição, Cidade, País``."""
    partes = _partes(afiliacao)
    # O país costuma ser o último segmento; a busca recua até três posições
    # para tolerar estado, região ou CEP depois do nome do país.
    for parte in reversed(partes[-3:]):
        achado = pais(parte)
        if achado:
            return achado
    return ""


def paises_de(afiliacoes: Iterable[str], alternativa: str = "") -> list[str]:
    """Países de uma lista de afiliações, sem repetição e na ordem de entrada."""
    encontrados: list[str] = []
    for afiliacao in afiliacoes or ():
        achado = pais_da_afiliacao(afiliacao)
        if achado and achado not in encontrados:
            encontrados.append(achado)
    if not encontrados and alternativa:
        for parte in re.split(r"[;,|]", alternativa):
            achado = pais(parte)
            if achado and achado not in encontrados:
                encontrados.append(achado)
    return encontrados
