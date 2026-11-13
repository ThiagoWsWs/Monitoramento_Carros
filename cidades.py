"""Coordenadas dos municípios do RS e cálculo de distância."""
from __future__ import annotations

import csv
import math
from pathlib import Path

from fontes.base import normalizar

ARQUIVO = Path(__file__).parent / "dados" / "municipios_rs.csv"


def _carregar() -> dict[str, tuple[str, float, float]]:
    cidades = {}
    with open(ARQUIVO, encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            cidades[normalizar(linha["nome"])] = (
                linha["nome"],
                float(linha["latitude"]),
                float(linha["longitude"]),
            )
    return cidades


MUNICIPIOS = _carregar()


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def distancia(centro: str, cidade: str) -> float | None:
    """Distância em km entre duas cidades do RS, ou None se não reconhecer."""
    a = MUNICIPIOS.get(normalizar(centro))
    b = MUNICIPIOS.get(normalizar(cidade))
    if not a or not b:
        return None
    return haversine(a[1], a[2], b[1], b[2])


def nome_oficial(cidade: str) -> str:
    """'CANOAS' -> 'Canoas' (se for um município conhecido)."""
    c = MUNICIPIOS.get(normalizar(cidade))
    return c[0] if c else cidade


def cidades_no_raio(centro: str, raio_km: float) -> list[str]:
    """Nomes oficiais dos municípios até `raio_km` do centro, do mais perto ao mais longe."""
    if normalizar(centro) not in MUNICIPIOS:
        raise ValueError(f"Cidade '{centro}' não encontrada em {ARQUIVO.name}")
    lista = []
    for nome, _, _ in MUNICIPIOS.values():
        d = distancia(centro, nome)
        if d is not None and d <= raio_km:
            lista.append((d, nome))
    return [nome for _, nome in sorted(lista)]
