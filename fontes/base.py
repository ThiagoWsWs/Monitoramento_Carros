"""Estruturas e utilitários comuns às fontes."""
from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}
PAUSA_ENTRE_REQUISICOES = 1.0  # segundos, para não sobrecarregar os sites

_sessao = requests.Session()
_sessao.headers.update(HEADERS)


@dataclass
class Anuncio:
    fonte: str
    id: str
    titulo: str
    preco: float
    cidade: str
    link: str
    ano: int | None = None
    km: int | None = None
    vendedor: str | None = None
    distancia_km: float | None = field(default=None, compare=False)
    # Mesmo carro encontrado em outros sites (preenchido em main.agrupar).
    duplicados: list["Anuncio"] = field(default_factory=list, compare=False, repr=False)

    @property
    def chave(self) -> str:
        return f"{self.fonte}:{self.id}"

    @property
    def todas_chaves(self) -> list[str]:
        return [self.chave] + [d.chave for d in self.duplicados]


def baixar(url: str) -> str:
    """GET simples com pausa educada e texto em UTF-8."""
    time.sleep(PAUSA_ENTRE_REQUISICOES)
    r = _sessao.get(url, timeout=40)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def next_data(html: str) -> dict:
    """Extrai o JSON __NEXT_DATA__ que sites em Next.js embutem na página."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("página sem __NEXT_DATA__ (o layout do site mudou?)")
    return json.loads(m.group(1))


def normalizar(texto: str) -> str:
    """'São Leopoldo' -> 'sao leopoldo' (sem acento, minúsculo)."""
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", " ", t.lower())
    return t.strip()


def slug(texto: str) -> str:
    """'São Leopoldo' -> 'sao-leopoldo'."""
    return normalizar(texto).replace(" ", "-")
