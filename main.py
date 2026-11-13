"""Monitor diário de carros -> Telegram.

Uso:
    python main.py            # busca, envia no Telegram e salva o histórico
    python main.py --teste    # busca e mostra no terminal (não envia, não salva)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import tomllib
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import cidades
import telegram
from fontes import chavesnamao, mobiauto, napista
from fontes.base import Anuncio, normalizar

RAIZ = Path(__file__).parent
ARQ_CONFIG = RAIZ / "config.toml"
ARQ_VISTOS = RAIZ / "dados" / "vistos.json"
DIAS_PARA_ESQUECER = 30  # anúncio sumido há mais que isso sai do histórico
FUSO = ZoneInfo("America/Sao_Paulo")

log = logging.getLogger("monitor")


def coletar(cfg: dict, lista_cidades: list[str]) -> tuple[list[Anuncio], list[str]]:
    busca, fontes = cfg["busca"], cfg.get("fontes", {})
    tarefas = {
        "Mobiauto": (mobiauto, lambda m, c: m.buscar(c, busca)),
        "NaPista": (napista, lambda m, c: m.buscar(c, busca, lista_cidades)),
        "Chaves na Mão": (chavesnamao, lambda m, c: m.buscar(c, busca, lista_cidades)),
    }
    chaves_cfg = {"Mobiauto": "mobiauto", "NaPista": "napista", "Chaves na Mão": "chavesnamao"}
    todos, falhas = [], []
    for nome, (modulo, rodar) in tarefas.items():
        c = fontes.get(chaves_cfg[nome], {})
        if not c.get("ativo", True):
            continue
        try:
            achados = rodar(modulo, c)
            log.info("%s: %d anúncios brutos", nome, len(achados))
            if not achados:
                falhas.append(f"{nome} (nenhum resultado, o site pode ter mudado)")
            todos.extend(achados)
        except Exception as e:
            log.exception("Falha na fonte %s", nome)
            falhas.append(f"{nome} ({type(e).__name__})")
    return todos, falhas


def filtrar(anuncios: list[Anuncio], busca: dict) -> list[Anuncio]:
    pmin, pmax = busca["preco_min"], busca["preco_max"]
    centro, raio = busca["cidade_centro"], busca["raio_km"]
    ano_min = busca.get("ano_min") or 0
    excluir = [normalizar(p) for p in busca.get("palavras_excluir", [])]
    modelos = [normalizar(p) for p in busca.get("modelos", [])]

    ok, desconhecidas = [], set()
    for a in anuncios:
        if not (pmin <= a.preco <= pmax):
            continue
        if ano_min and a.ano and a.ano < ano_min:
            continue
        titulo = f" {normalizar(a.titulo)} "
        if any(f" {p} " in titulo for p in excluir):
            continue
        if modelos and not any(f" {p} " in titulo for p in modelos):
            continue
        d = cidades.distancia(centro, a.cidade)
        if d is None:
            desconhecidas.add(a.cidade)
            continue
        if d > raio:
            continue
        a.distancia_km = d
        a.cidade = cidades.nome_oficial(a.cidade)
        if a.km is not None and a.km < 100:  # "0 km"/"1 km" = vendedor não informou
            a.km = None
        ok.append(a)
    if desconhecidas:
        log.info("Cidades não reconhecidas (ignoradas): %s", sorted(desconhecidas))
    return ok


def _palavras(titulo: str) -> set[str]:
    return {p for p in normalizar(titulo).split() if len(p) >= 2}


def agrupar(anuncios: list[Anuncio]) -> list[Anuncio]:
    """Junta o mesmo carro anunciado em sites diferentes.

    Critério: mesma cidade, preço e ano, km igual (quando os dois informam)
    e pelo menos 2 palavras do título em comum (ex.: marca + modelo).
    """
    grupos: dict[tuple, list[Anuncio]] = {}
    unicos: list[Anuncio] = []
    for a in anuncios:
        k = (normalizar(a.cidade), a.preco, a.ano)
        par = None
        for b in grupos.get(k, []):
            if b.fonte == a.fonte or any(d.fonte == a.fonte for d in b.duplicados):
                continue
            if a.km and b.km and a.km != b.km:
                continue
            if len(_palavras(a.titulo) & _palavras(b.titulo)) >= 2:
                par = b
                break
        if par:
            par.duplicados.append(a)
        else:
            grupos.setdefault(k, []).append(a)
            unicos.append(a)
    return unicos


def comparar(anuncios: list[Anuncio], vistos: dict, hoje: str):
    novos, baixaram = [], []
    for a in anuncios:
        anteriores = [vistos[k] for k in a.todas_chaves if k in vistos]
        if not anteriores:
            novos.append(a)
        else:
            preco_antes = min(v["preco"] for v in anteriores)
            if a.preco < preco_antes:
                baixaram.append((a, preco_antes))
        primeiro = min((v["primeiro"] for v in anteriores), default=hoje)
        for x in [a] + a.duplicados:
            vistos[x.chave] = {
                "preco": x.preco,
                "titulo": x.titulo,
                "primeiro": primeiro,
                "ultimo": hoje,
            }
    limite = (datetime.fromisoformat(hoje) - timedelta(days=DIAS_PARA_ESQUECER)).date().isoformat()
    for k in [k for k, v in vistos.items() if v["ultimo"] < limite]:
        del vistos[k]
    return novos, baixaram


def reais(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",", ".")


def bloco(a: Anuncio, extra: str = "") -> str:
    e = telegram.esc
    detalhes = [reais(a.preco)]
    if a.ano:
        detalhes.append(str(a.ano))
    if a.km:
        detalhes.append(f"{a.km:,} km".replace(",", "."))
    def href(x: Anuncio) -> str:
        return telegram.esc(x.link).replace('"', "&quot;")

    fontes = e(a.fonte) + "".join(
        f' · <a href="{href(d)}">{e(d.fonte)}</a>' for d in a.duplicados
    )
    linhas = [
        f'🚗 <b><a href="{href(a)}">{e(a.titulo)}</a></b>',
        f"💰 {' · '.join(detalhes)}{extra}",
        f"📍 {e(a.cidade)} ({a.distancia_km:.0f} km) · {fontes}",
    ]
    return "\n".join(linhas)


def montar_mensagem(cfg, novos, baixaram, total, falhas):
    b, env = cfg["busca"], cfg.get("envio", {})
    maximo = env.get("max_por_dia", 40)
    data = datetime.now(FUSO).strftime("%d/%m")
    cab = (
        f"🔎 <b>Carros de {reais(b['preco_min'])} a {reais(b['preco_max'])}</b>\n"
        f"até {b['raio_km']} km de {telegram.esc(b['cidade_centro'])} · {data}\n"
        f"<b>{len(novos)}</b> novos · <b>{len(baixaram)}</b> baixaram de preço · "
        f"{total} anúncios no total"
    )
    blocos = []
    for a, antes in sorted(baixaram, key=lambda x: x[0].preco)[:maximo]:
        blocos.append(bloco(a, f"  📉 <s>{reais(antes)}</s>"))
    for a in sorted(novos, key=lambda x: x.preco)[: max(0, maximo - len(blocos))]:
        blocos.append(bloco(a))
    rodape = []
    nao_mostrados = len(novos) + len(baixaram) - len(blocos)
    if nao_mostrados > 0:
        rodape.append(f"➕ Mais {nao_mostrados} anúncios não mostrados (limite de {maximo} por dia).")
    if falhas:
        rodape.append("⚠️ Fontes com problema hoje: " + ", ".join(telegram.esc(f) for f in falhas))
    return cab, blocos, "\n".join(rodape)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--teste", action="store_true", help="não envia nem salva; só mostra")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = tomllib.loads(ARQ_CONFIG.read_text(encoding="utf-8"))
    busca = cfg["busca"]
    lista = cidades.cidades_no_raio(busca["cidade_centro"], busca["raio_km"])
    log.info("%d cidades no raio de %s km: %s", len(lista), busca["raio_km"], ", ".join(lista))

    brutos, falhas = coletar(cfg, lista)
    filtrados = filtrar(brutos, busca)
    anuncios = agrupar(filtrados)
    log.info("%d anúncios dentro dos filtros (%d após juntar repetidos entre sites)",
             len(filtrados), len(anuncios))

    vistos = json.loads(ARQ_VISTOS.read_text(encoding="utf-8")) if ARQ_VISTOS.exists() else {}
    primeira_vez = not vistos
    hoje = datetime.now(FUSO).date().isoformat()
    novos, baixaram = comparar(anuncios, vistos, hoje)
    cab, blocos, rodape = montar_mensagem(cfg, novos, baixaram, len(anuncios), falhas)
    if primeira_vez:
        cab += ("\n\n👋 <i>Primeira execução: todos os anúncios atuais contam como novos. "
                "Seguem os mais baratos; a partir de amanhã chegam só as novidades.</i>")

    if args.teste:
        sys.stdout.reconfigure(encoding="utf-8")
        print("\n" + cab + "\n\n" + "\n\n".join(blocos) + ("\n\n" + rodape if rodape else ""))
        return 0

    if blocos or falhas or cfg.get("envio", {}).get("avisar_sem_novidades", True):
        if not blocos:
            cab += "\n\nNenhum anúncio novo hoje. 😴"
        telegram.enviar_blocos(cab, blocos, rodape)

    ARQ_VISTOS.parent.mkdir(exist_ok=True)
    ARQ_VISTOS.write_text(json.dumps(vistos, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    # Se TODAS as fontes falharem, sai com erro para o GitHub avisar por e-mail.
    return 1 if brutos == [] and falhas else 0


if __name__ == "__main__":
    sys.exit(main())
