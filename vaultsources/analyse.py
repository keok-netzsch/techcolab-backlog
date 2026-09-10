"""vaultsources/analyse.py — o que a rotina precisa para fechar uma analise sozinha.

O gargalo do cano nunca foi trazer, foi processar. Em 2026-09-10, no fim do dia em
que ele ficou pronto, eram 16 fontes e 14 sem analise. A analise so acontecia
quando o Kelvin pedia numa conversa, e isso nao escala nem sobrevive a uma semana
corrida.

O trabalho em si e limitado e repetitivo: ler um texto que ja esta no disco e
produzir um json. Cabe numa rotina agendada. O que faltava era a rotina conseguir
LER o texto sem saber onde ele foi parar — pode estar na propria nota, num sidecar
de transcricao, ou no cache local fora do vault, dependendo do tamanho e de ter
sido gravado com `--no-raw`.

`pending()` diz o que falta e ha quanto tempo. `show()` entrega tudo o que a
analise precisa, com os timestamps fora: eles sao ~15% de um transcript de legenda
e nao ajudam em nada a decidir a tese.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from vaultsources import note, paths

TIMESTAMP = re.compile(r"\[\d+\.\d+s\]\s*")


def pending() -> list[Path]:
    """Notas de fonte com `analysis: pending`, da mais antiga para a mais nova."""
    if not paths.SOURCES_DIR.exists():
        return []
    out = []
    for p in sorted(paths.SOURCES_DIR.glob("*.md")):
        if p.name.startswith("_"):
            continue
        if "analysis: pending" in p.read_text(encoding="utf-8", errors="replace")[:1500]:
            out.append(p)
    return sorted(out, key=lambda p: _fm_date(p) or datetime.now().date())


def _fm_date(p: Path):
    m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})",
                  p.read_text(encoding="utf-8", errors="replace")[:1500], re.M)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def summary(limit: int = 0) -> list[dict]:
    hoje = datetime.now().date()
    out = []
    for p in pending():
        d = _fm_date(p)
        head = p.read_text(encoding="utf-8", errors="replace")[:1500]
        chars = re.search(r"^text-chars:\s*(\d+)", head, re.M)
        out.append({
            "file": p.name,
            "dias": (hoje - d).days if d else 0,
            "chars": int(chars.group(1)) if chars else 0,
        })
    out.sort(key=lambda x: -x["dias"])
    return out[:limit] if limit else out


class SemTexto(RuntimeError):
    """A nota existe e o texto bruto nao esta em lugar nenhum."""


def show(nome: str, *, max_chars: int = 80000) -> str:
    """Tudo o que a analise precisa ler, num bloco so.

    Timestamps saem: sao ruido para decidir tese e afirmacao, e ocupam espaco que
    na pratica limita quanto do texto cabe numa leitura.
    """
    p = Path(nome) if Path(nome).is_absolute() else paths.SOURCES_DIR / nome
    if not p.exists():
        raise FileNotFoundError(str(p))
    doc = note.read_doc(p)
    cab = [
        "# " + doc.title,
        "arquivo: " + p.name,
        "autor: %s · publicado: %s · %s · %d caracteres"
        % (doc.author or "?", doc.published or "?", doc.provenance, len(doc.text)),
        "puxada por: " + (doc.pulled_by_question or "captura avulsa"),
        "url: " + doc.url,
        "",
    ]
    if not doc.text:
        raise SemTexto(
            "%s nao tem texto bruto na nota, nem no sidecar, nem no cache local. "
            "Rebusque com `fetch \"%s\" --force` antes de analisar." % (p.name, doc.url))
    texto = TIMESTAMP.sub("", doc.text)
    texto = re.sub(r"\n{2,}", "\n", texto).strip()
    if max_chars and len(texto) > max_chars:
        cab += ["--- TEXTO (cortado em %d de %d caracteres) ---" % (max_chars, len(texto)),
                texto[:max_chars],
                "",
                "[faltam %d caracteres. `--max-chars 0` traz tudo.]"
                % (len(texto) - max_chars)]
    else:
        cab += ["--- TEXTO (%d caracteres) ---" % len(texto), texto]
    return "\n".join(cab)
