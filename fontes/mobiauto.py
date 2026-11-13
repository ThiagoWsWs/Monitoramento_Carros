"""Mobiauto (mobiauto.com.br): lê os dados JSON embutidos na página de busca."""
from __future__ import annotations

import logging

from .base import Anuncio, baixar, next_data, slug

log = logging.getLogger(__name__)
BASE = "https://www.mobiauto.com.br/comprar/carros"
MAX_PAGINAS = 40


def _url(cidade_polo: str, pmin: int, pmax: int, pagina: int) -> str:
    u = f"{BASE}/{cidade_polo}/preco-ate-{pmax}/preco-a-partir-de-{pmin}"
    return u if pagina == 1 else f"{u}/pagina-{pagina}"


def _link(item: dict, cidade_polo: str) -> str:
    trim = item.get("trim") or {}
    partes = [
        slug((trim.get("make") or {}).get("name", "")),
        slug((trim.get("model") or {}).get("name", "")),
        str((trim.get("model") or {}).get("year") or trim.get("productionYear") or ""),
        slug(trim.get("name", "")),
    ]
    if all(partes):
        return f"{BASE}/{cidade_polo}/{'/'.join(partes)}/detalhes/{item['id']}"
    return f"{BASE}/{cidade_polo}"


def buscar(cfg: dict, busca: dict) -> list[Anuncio]:
    pmin, pmax = int(busca["preco_min"]), int(busca["preco_max"])
    anuncios: dict[str, Anuncio] = {}
    for polo in cfg.get("cidades_polo", []):
        for pagina in range(1, MAX_PAGINAS + 1):
            dados = next_data(baixar(_url(polo, pmin, pmax, pagina)))
            resultados = dados["props"]["pageProps"]["deals"]["results"]
            if not resultados:
                break
            for it in resultados:
                trim = it.get("trim") or {}
                marca = (trim.get("make") or {}).get("name", "")
                modelo = (trim.get("model") or {}).get("name", "")
                local = (it.get("dealer") or {}).get("location") or {}
                a = Anuncio(
                    fonte="Mobiauto",
                    id=str(it["id"]),
                    titulo=f"{marca} {modelo} {trim.get('name', '')}".strip(),
                    preco=float(it.get("price") or 0),
                    cidade=local.get("city", ""),
                    link=_link(it, polo),
                    ano=(trim.get("model") or {}).get("year") or trim.get("productionYear"),
                    km=it.get("km"),
                    vendedor=(it.get("dealer") or {}).get("name"),
                )
                anuncios.setdefault(a.id, a)
        log.info("Mobiauto %s: %d anúncios acumulados", polo, len(anuncios))
    return list(anuncios.values())
