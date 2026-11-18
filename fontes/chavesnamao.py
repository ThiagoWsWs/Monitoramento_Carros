"""Chaves na Mão (chavesnamao.com.br): lê a lista de produtos (schema.org) da página.

Quando a cidade não tem resultados, o site completa a página com anúncios de
cidades vizinhas ou fora do filtro. Por isso usamos só os primeiros
`realResults` itens, e a cidade é tirada do próprio link do anúncio.
"""
from __future__ import annotations

import json
import logging
import re

from .base import Anuncio, baixar, slug

log = logging.getLogger(__name__)
BASE = "https://www.chavesnamao.com.br"
POR_PAGINA = 30

_RE_LDJSON = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
_RE_REAIS = re.compile(r'\\"realResults\\":(\d+)')
_RE_LINK = re.compile(r"/carro/rs-([a-z0-9-]+)/.*?-(\d{4})-[^/]*/id-(\d+)/?")


def _itens(html: str) -> list[dict]:
    for bloco in _RE_LDJSON.findall(html):
        try:
            j = json.loads(bloco)
        except ValueError:
            continue
        if isinstance(j, dict) and j.get("@type") == "ItemList":
            return [e.get("item") or {} for e in j.get("itemListElement", [])]
    return []


def buscar(cfg: dict, busca: dict, cidades: list[str]) -> list[Anuncio]:
    pmin, pmax = int(busca["preco_min"]), int(busca["preco_max"])
    slug_para_nome = {slug(c): c for c in cidades}
    anuncios: dict[str, Anuncio] = {}
    for cidade in cidades:
        url = f"{BASE}/carros-usados/rs-{slug(cidade)}/?filtro=pmin:{pmin},pmax:{pmax}"
        try:
            html = baixar(url)
        except Exception as e:
            log.debug("Chaves na Mão %s: %s", cidade, e)
            continue
        m = _RE_REAIS.search(html)
        reais = int(m.group(1)) if m else 0
        if reais > POR_PAGINA:
            log.warning("Chaves na Mão %s: %d resultados, só os %d primeiros foram lidos",
                        cidade, reais, POR_PAGINA)
        for item in _itens(html)[:reais]:
            link = item.get("url", "")
            ml = _RE_LINK.search(link)
            if not ml:
                continue
            cidade_slug, ano, id_ = ml.groups()
            oferta = item.get("offers") or {}
            anuncios.setdefault(id_, Anuncio(
                fonte="Chaves na Mão",
                id=id_,
                titulo=(item.get("name") or "").title(),
                preco=float(oferta.get("price") or 0),
                cidade=slug_para_nome.get(cidade_slug, cidade_slug.replace("-", " ").title()),
                link=link,
                ano=int(ano),
                vendedor=(oferta.get("seller") or {}).get("name"),
                foto=(item.get("image")[0] if isinstance(item.get("image"), list) and item.get("image")
                      else item.get("image") if isinstance(item.get("image"), str) else ""),
            ))
    log.info("Chaves na Mão: %d anúncios em %d cidades", len(anuncios), len(cidades))
    return list(anuncios.values())
