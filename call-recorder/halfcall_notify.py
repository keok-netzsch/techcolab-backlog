"""Gravacoes que sairam pela metade e ainda nao foram anunciadas ao Kelvin.

O detector ja existia duas vezes e nenhuma das duas chegava nele no dia da call:

  1. `capture_multi.select_channels` escreve `*** ALERTA: canal 1 sem fala ***` no
     `record.log` no instante em que a gravacao fecha. Correto desde 27/08, sem
     leitor.
  2. `daily_report._check_capture_quality` acusa o mesmo no relatorio das 07:00.
     Correto, mas so na manha seguinte — a call ja virou nota.

Em 03/09 as duas gravacoes da manha (Hernan 08:53, Genesis 09:34) sairam com o
canal do interlocutor em silencio digital (pico 0, nao "baixo"). O Kelvin
descobriu em 04/09, um dia depois, e so porque perguntou. A causa tecnica
(`CoInitializeEx` faltando na thread de loopback) foi corrigida em `685de09`
as 10:45 de 03/09 — mas o buraco de ENTREGA continuou aberto, e e ele que este
modulo fecha.

CONSUMIDOR NOMEADO (padrao 12 da ARCHITECTURE.md): o perfil `capture-half-call`
do `scripts/notify.ps1`, disparado pelo `autocapture` logo depois de salvar o
`.wav`. Minutos depois da call, nao no relatorio do dia seguinte.

POR QUE NO FIM E NAO NO COMECO DA CALL: a falha do loopback e conhecida na
abertura (`Error 0x800401f0`), mas o modo `messagebox` e TopMost e bloqueante.
Disparar durante uma call rouba o foco — ja aconteceu em call com camera ligada,
e um alerta que atrapalha e um alerta que ele desliga. O fim da gravacao e o
primeiro momento seguro, e ainda serve: ele sabe na hora que aquela nota vai ter
um lado so, com a conversa fresca na cabeca.

MARCA DE ANUNCIADO: um `<base>.halfcall-notified` ao lado do `.wav`. Sem ela, a
mesma gravacao reapareceria na caixa a cada call seguinte dentro da janela e o
lembrete deixaria de ser lido — que e como o alerta anterior morreu.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

RECORDINGS = HERE / "recordings"

# Janela de 24h. A do relatorio diario e de 72h porque ele roda uma vez por dia e
# precisa cobrir o fim de semana; aqui o disparo e por call, entao 72h so aumenta
# a chance de repetir o que ele ja viu.
JANELA_H = 24.0

MARCA = ".halfcall-notified"


def _stem(p: Path) -> str:
    return p.name.split(".pending")[0]


def pendentes(rdir=None, janela_h: float = JANELA_H, agora: float | None = None):
    """[(stem, detalhe)] das gravacoes meia-conversa recentes ainda nao anunciadas.

    So le. Marcar e trabalho de `marcar()`, para que um `--peek` (e o teste)
    possam perguntar sem gastar o anuncio.
    """
    import transcript_quality as tq

    raiz = Path(rdir) if rdir else RECORDINGS
    if not raiz.exists():
        return []
    agora = time.time() if agora is None else agora

    achados = []
    vistos = set()
    for p in sorted(raiz.glob("*.pending.json*")):
        stem = _stem(p)
        if stem in vistos:
            continue
        vistos.add(stem)
        if (agora - p.stat().st_mtime) / 3600.0 > janela_h:
            continue
        if (raiz / (stem + MARCA)).exists():
            continue
        mudo, detalhe = tq.canal_mudo(stem, rdir=raiz)
        if mudo:
            achados.append((stem, detalhe))
    return achados


def marcar(stems, rdir=None) -> None:
    raiz = Path(rdir) if rdir else RECORDINGS
    for stem in stems:
        try:
            (raiz / (stem + MARCA)).write_text("", encoding="utf-8")
        except OSError:
            # Falhar em marcar repete o aviso, o que e chato; falhar em avisar
            # perde a call. A ordem de preferencia e essa.
            pass


def corpo(achados) -> str:
    """Texto da caixa. Vazio quando nao ha nada — o notify.ps1 fica silencioso."""
    if not achados:
        return ""
    linhas = [f"  - {stem}: {detalhe}" for stem, detalhe in achados[:5]]
    plural = "gravacao" if len(achados) == 1 else "gravacoes"
    return (
        f"{len(achados)} {plural} com METADE DA CONVERSA:\n\n"
        + "\n".join(linhas)
        + "\n\n"
        "So um lado foi para o disco. A transcricao e a nota do vault vao sair\n"
        "parecendo completas, sem dizer que falta a outra metade.\n\n"
        "Se a conversa importa, escreva agora o que voce lembra — o audio do\n"
        "outro lado nao existe e nao tem como recuperar."
    )


def main(argv=None) -> int:
    """Imprime o corpo e NAO marca nada. Ler nunca gasta o anuncio.

    Marcar aqui parecia natural e esta errado: o `notify.ps1 -WhatIf` roda o
    gerador para mostrar o que apareceria, e na primeira versao esse ensaio
    consumiu o anuncio da call do Genesis — o proximo disparo real teria ficado
    mudo por causa de um teste. Quem marca e o `autocapture`, que e o unico que
    sabe que houve disparo de verdade.
    """
    print(corpo(pendentes()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
