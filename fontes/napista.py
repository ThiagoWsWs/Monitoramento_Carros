"""NaPista (napista.com.br): busca cidade por cidade, lendo o JSON da página."""
from __future__ import annotations

import logging

from .base import Anuncio, baixar, next_data, slug

log = logging.getLogger(__name__)
BASE = "https://napista.com.br"
MAX_PAGINAS = 10


def buscar(cfg: dict, busca: dict, cidades: list[str]) -> list[Anuncio]:
    pmax = int(busca["preco_max"])
    anuncios: dict[str, Anuncio] = {}
    for cidade in cidades:
        for pagina in range(1, MAX_PAGINAS + 1):
            url = f"{BASE}/busca/carro/rs/{slug(cidade)}/ate-{pmax}-reais?pn={pagina}"
            try:
                dados = next_data(baixar(url))
            except Exception as e:  # cidade sem página própria, etc.
                log.debug("NaPista %s: %s", cidade, e)
                break
            res = dados["props"]["pageProps"].get("searchResult") or {}
            ofertas = res.get("offers") or []
            for o in ofertas:
                local = o.get("location") or {}
                titulo = o.get("versionName") or f"{o.get('makeName', '')} {o.get('modelName', '')}"
                anuncios.setdefault(o["id"], Anuncio(
                    fonte="NaPista",
                    id=o["id"],
                    titulo=titulo.strip(),
                    preco=float(o.get("price") or 0),
                    cidade=local.get("city", ""),
                    link=f"{BASE}/anuncios/{o['id']}",
                    ano=o.get("modelYear"),
                    km=o.get("mileage") or None,
                    vendedor=o.get("seller"),
                    foto=next((p.get("url") for p in sorted(o.get("photos") or [],
                                                           key=lambda p: p.get("order", 0))
                               if p.get("url")), ""),
                ))
            total = res.get("offersTotal") or 0
            if not ofertas or pagina * len(ofertas) >= total:
                break
    log.info("NaPista: %d anúncios em %d cidades", len(anuncios), len(cidades))
    return list(anuncios.values())
