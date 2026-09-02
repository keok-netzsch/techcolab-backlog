"""
backlog/daily_index.py — organiza `Daily/` em ano/mes e gera os indices.

Pedido do Kelvin em 2026-09-02: "organizasse os arquivos de daily em indexes...
ano, mes, arquivo. a lista tende a crescer muito." Uma pasta plana ganha ~250
arquivos por ano e o explorador do Obsidian deixa de servir para navegar.

    Daily/
      _index.md              <- anos
      2026/
        _index.md            <- meses de 2026
        09/
          _index.md          <- dias de setembro
          2026-09-02.md

**Nada aqui apaga nota.** Mover e gerar indice; o conteudo nao e tocado.

Rode sem `--aplicar` para ver o que aconteceria. O comando e idempotente: rodar
duas vezes nao duplica nada e nao move o que ja esta no lugar.

    python -m backlog.daily_index              # simulacao
    python -m backlog.daily_index --aplicar
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from config import VAULT_BASE

DAILY = Path(VAULT_BASE) / "Daily"
# Nome UNICO por indice. O Obsidian resolve [[link]] por nome de arquivo,
# entao cinco arquivos "_index.md" deixam todo link ambiguo ou morto — foi o
# que a primeira versao produziu: [[2026]] e [[2026-09-index]] nao apontavam
# para lugar nenhum. Agora o indice do mes chama "_2026-09-index".
def _nome_indice(*partes) -> str:
    return "_" + "-".join(partes) + "-index.md"
RX_NOTA = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")

MESES = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def notas_planas() -> list[Path]:
    """Notas ainda soltas na raiz de Daily/."""
    if not DAILY.exists():
        return []
    return sorted(p for p in DAILY.iterdir()
                  if p.is_file() and RX_NOTA.match(p.name))


def notas_organizadas() -> list[Path]:
    """Notas ja em Daily/YYYY/MM/."""
    if not DAILY.exists():
        return []
    return sorted(p for p in DAILY.glob("*/*/*.md") if RX_NOTA.match(p.name))


def _destino(p: Path) -> Path:
    a, m, _ = RX_NOTA.match(p.name).groups()
    return DAILY / a / m / p.name


def migrar(aplicar: bool = False) -> list[tuple[Path, Path]]:
    """Move as notas planas para ano/mes. Colisao NUNCA sobrescreve."""
    movidas = []
    for p in notas_planas():
        alvo = _destino(p)
        if alvo.exists():
            # Duas notas do mesmo dia em formatos diferentes e um caso que so
            # aparece se algo escreveu plano depois da migracao. Sobrescrever
            # apagaria uma das duas; anunciar e deixar para o humano e o certo.
            print(f"  [COLISAO] {p.name} ja existe em {alvo.parent} - nao movido")
            continue
        movidas.append((p, alvo))
        if aplicar:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            p.rename(alvo)
    return movidas


def _linha(p: Path) -> str:
    """Link do Obsidian pelo nome do arquivo — resolve em qualquer pasta."""
    stem = p.stem
    try:
        d = date.fromisoformat(stem)
        return f"- [[{stem}]] — {d.strftime('%A')}"
    except ValueError:
        return f"- [[{stem}]]"


def gerar_indices(aplicar: bool = False) -> list[Path]:
    """Escreve _index.md em Daily/, Daily/YYYY/ e Daily/YYYY/MM/."""
    escritos = []
    if not DAILY.exists():
        return escritos

    anos = sorted([d for d in DAILY.iterdir() if d.is_dir() and d.name.isdigit()],
                  reverse=True)

    for ano in anos:
        meses = sorted([d for d in ano.iterdir() if d.is_dir() and d.name.isdigit()],
                       reverse=True)
        for mes in meses:
            dias = sorted((p for p in mes.iterdir() if RX_NOTA.match(p.name)),
                          reverse=True)
            nome_mes = MESES[int(mes.name) - 1]
            corpo = [f"# {nome_mes.capitalize()} de {ano.name}", "",
                     f"{len(dias)} nota(s).", ""]
            corpo += [_linha(p) for p in dias]
            alvo = mes / _nome_indice(ano.name, mes.name)
            escritos.append(alvo)
            if aplicar:
                alvo.write_text("\n".join(corpo) + "\n", encoding="utf-8")

        corpo = [f"# Daily {ano.name}", ""]
        for mes in meses:
            n = len([p for p in mes.iterdir() if RX_NOTA.match(p.name)])
            nome_mes = MESES[int(mes.name) - 1]
            alvo_mes = _nome_indice(ano.name, mes.name)[:-3]
            corpo.append(f"- [[{alvo_mes}|{nome_mes}]] — {n} nota(s)")
        alvo = ano / _nome_indice(ano.name)
        escritos.append(alvo)
        if aplicar:
            alvo.write_text("\n".join(corpo) + "\n", encoding="utf-8")

    corpo = ["# Daily", "",
             "Notas diarias por ano. O arquivo de cada dia continua se chamando",
             "`YYYY-MM-DD`, entao qualquer `[[2026-09-02]]` no vault continua",
             "resolvendo — o Obsidian liga por nome, nao por pasta.", ""]
    for ano in anos:
        n = len([p for p in ano.glob("*/*.md") if RX_NOTA.match(p.name)])
        corpo.append(f"- [[{_nome_indice(ano.name)[:-3]}|{ano.name}]] — {n} nota(s)")
    soltas = notas_planas()
    if soltas:
        corpo += ["", f"> {len(soltas)} nota(s) ainda na raiz — rode "
                      "`python -m backlog.daily_index --aplicar` para organizar."]
    alvo = DAILY / _nome_indice("Daily")
    escritos.append(alvo)
    if aplicar:
        alvo.write_text("\n".join(corpo) + "\n", encoding="utf-8")

    return escritos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aplicar", action="store_true",
                    help="grava de verdade (sem isso, so simula)")
    a = ap.parse_args()

    print(f"Daily: {DAILY}")
    print(f"  planas: {len(notas_planas())} | organizadas: {len(notas_organizadas())}")
    print()

    movidas = migrar(aplicar=a.aplicar)
    for origem, alvo in movidas:
        print(f"  {origem.name} -> {alvo.relative_to(DAILY)}")
    print(f"  {len(movidas)} nota(s) {'movida(s)' if a.aplicar else 'a mover'}")
    print()

    idx = gerar_indices(aplicar=a.aplicar)
    print(f"  {len(idx)} indice(s) {'escrito(s)' if a.aplicar else 'a escrever'}")

    if not a.aplicar:
        print("\n(simulacao — nada foi gravado. use --aplicar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
