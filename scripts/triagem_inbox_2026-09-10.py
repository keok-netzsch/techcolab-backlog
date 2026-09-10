"""Triagem unica da fila do Inbox, decidida em 2026-09-10 (ledger P-118).

Contexto: 27 notas com `status: a-triar` acumuladas de 27/08 a 09/09. Elas nao sao
gravacoes esperando roteamento (a fila do `route.py` tinha 1 item). Sao notas ja
escritas que ficaram sem destino, orfas de um fluxo anterior.

Este script NAO e um mecanismo permanente. E a limpeza de um passivo, com o plano
explicito no proprio arquivo para que a decisao fique auditavel. O fluxo corrente
(`route.py`, roteamento por assunto) nao produz mais este tipo de orfao.

Quatro tratamentos, e a escolha de cada nota esta no PLANO abaixo:

    rotear     destino claro e resumo coerente com o recorte -> link no destino,
               `status: triado`, e o arquivo se move quando o destino ja e pasta
    revisar    o resumo gerado contradiz o recorte ou cita coisa que nao existe na
               call -> o resumo sai e vira marcador `<!-- unparsed -->`. Padrao 5:
               falha de processamento nao pode ocupar o campo que o leitor le como
               conteudo. A transcricao fica intacta
    sensivel   assunto e compensacao, carreira, saude ou vida privada -> nao encosto.
               Fica na fila e vai para o ledger, para o Kelvin decidir o destino
    arquivar   ja processado em outro lugar, ou captura pela metade sem valor

Rodar: python scripts/triagem_inbox_2026-09-10.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import VAULT_BASE  # noqa: E402

VAULT = Path(VAULT_BASE)
INBOX = VAULT / "Inbox"

# nome do arquivo -> (tratamento, destino, motivo)
PLANO: dict[str, tuple[str, str, str]] = {
    "2026-06-04 — Market Share Tool Review — Santiago Requena + Eva Belmonte.md": (
        "arquivar", "",
        "transcricao bruta; a propria nota diz que as notas processadas ja estao "
        "em Stakeholders/Santiago-Requena/1on1/ e Stakeholders/Eva-Belmonte/1on1/"),

    "2026-08-10_10-01_nota-avulsa.md": (
        "revisar", "",
        "resumo mistura migracao do Horizon, politica de dados e 'conceito de "
        "Linux'; nao da para dizer qual e o assunto da call"),

    "2026-08-27_08-01_project-meeting.md": (
        "sensivel", "",
        "incidente com funcionario: manuseio de documentos, monitoramento, consulta "
        "medica e possivel acompanhamento legal"),

    "2026-08-27_08-20_project-meeting.md": (
        "rotear", "Projects/BIA-015-NBS-Reporting.md",
        "incidente de refresh dos relatorios NBS/HR; nota escrita a mao a partir da "
        "transcricao, com causa raiz tecnica identificada"),

    "2026-08-27_08-31_project-meeting.md": (
        "rotear", "Areas/AI-Governance.md",
        "liberacao do Genie para o Olaf e RLS no Databricks"),

    "2026-08-27_14-20_project-meeting.md": (
        "arquivar", "",
        "canal do interlocutor vazio (RMS 0): so o microfone do Kelvin entrou. A "
        "propria nota registra que o conteudo nao e prioritario"),

    "2026-08-27_15-34_project-meeting.md": (
        "rotear", "Projects/CRM-LATAM-Automation-PoC",
        "CRM Latam do Alan Carvalho: automatizar a extracao para o Power BI"),

    "2026-08-28_07-34_project-meeting.md": (
        "rotear", "Projects/CRM-LATAM-Automation-PoC",
        "mesma PoC de CRM, repasse para avaliacao tecnica"),

    "2026-08-28_08-01_project-meeting.md": (
        "rotear", "Areas/Team Memory",
        "Facilitator como diario de bordo automatico do time"),

    "2026-08-28_08-15_project-meeting.md": (
        "rotear", "Areas/Team Memory",
        "Facilitator e Graph API para a apuracao de data products"),

    "2026-08-28_11-00_project-meeting.md": (
        "rotear", "Projects/TEAM NEM OKR-001 Revisão Política Export Permissão PBI PRJ_PENDING",
        "governanca do Power BI como facilitador ou guarda-chuva; e o assunto do OKR-001"),

    "2026-08-28_14-40_nota-avulsa.md": (
        "sensivel", "",
        "PLR e percentual de participacao sobre salario"),

    "2026-09-01_10-00_project-meeting.md": (
        "rotear", "Areas/OKR 2027/OKR 04 - Controle de horas SN",
        "planejado versus realizado no ServiceNow e WBS gerado por IA"),

    "2026-09-01_10-26_nota-avulsa.md": (
        "sensivel", "",
        "salario de analistas e engenheiros; e o assunto do vazamento de 02/09"),

    "2026-09-02_08-03_nota-avulsa.md": (
        "sensivel", "",
        "cidadania italiana e questoes juridicas e fiscais pessoais; nao e assunto "
        "de trabalho e nao deveria estar num vault profissional"),

    "2026-09-03_09-34_idea-capture.md": (
        "rotear", "Projects/NDB-EEE-Capex-Configurator",
        "calculadora de capex para saneamento na NDB"),

    "2026-09-04_08-02_project-meeting.md": (
        "rotear", "Projects/Enterprise-Data-Catalog.md",
        "primeira versao produtiva do data catalog apresentada ao Florian"),

    "2026-09-04_08-17_project-meeting.md": (
        "sensivel", "",
        "ferias, cobranca de entrega e conflito de responsabilidade entre duas "
        "pessoas do time; e fato sobre pessoa e passa por gate"),

    "2026-09-04_09-15_project-meeting.md": (
        "rotear", "Resources/ServiceNow-Project-Standard.md",
        "treinamento de WBS no ServiceNow: Start ASAP, dependencias, DoR e DoD"),

    "2026-09-04_10-01_project-meeting.md": (
        "rotear", "Areas/Data Governance.md",
        "servidor da India migrado sem aviso e licenca Power BI Pro devolvida ao time"),

    "2026-09-04_11-02_project-meeting.md": (
        "sensivel", "",
        "grade, senioridade, carreira e como tirar salario da conversa"),

    "2026-09-04_14-00_project-meeting.md": (
        "rotear", "Projects/BIA-004-Finding-Nemo-Hunting-List",
        "ASM: RLS por coluna, tabelas de India e Brasil, clientes sem zip code"),

    "2026-09-08_08-15_project-meeting.md": (
        "rotear", "Areas/OKR 2027",
        "percentuais do apoio fechando 50/40/10 e valores nulos no dataset do ASM"),

    "2026-09-09_08-01_project-meeting.md": (
        "revisar", "Areas/Data Governance.md",
        "o recorte fala de formato de documento de governanca; o resumo gerado fala "
        "de viagem a Aruba, tsunami na Indonesia e corrupcao no governo"),

    "2026-09-09_09-04_project-meeting.md": (
        "rotear", "Areas/Data Governance.md",
        "atribuicao de licenca Power BI Pro passa ao service desk de primeiro nivel"),

    "2026-09-09_09-34_project-meeting.md": (
        "revisar", "Areas/Data Governance.md",
        "o recorte e a Ana sem conseguir abrir o Data Tower; o resumo gerado fala de "
        "metodologia de ensino, alunos e professora"),

    "2026-09-09_14-00_project-meeting.md": (
        "rotear", "Areas/Team-Events",
        "agenda do evento Latam de 16/09 na NDB"),

    "2026-09-09_15-37_project-meeting.md": (
        "revisar", "Areas/Team-Events",
        "resumo registra 'evento em 16 e 17 de [data]' com o placeholder literal, e "
        "poe o almoco as 15h30 duas linhas antes de dizer que a sessao vai ate 15h30"),
}

ARQUIVO = VAULT / "Archive"
MARCA = "<!-- unparsed -->"


def _slug(name: str) -> str:
    import unicodedata
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9]+", "-", n).strip("-")


def _set_fm(text: str, key: str, value: str) -> str:
    pat = re.compile(r"^" + re.escape(key) + r":.*$", re.M)
    if pat.search(text):
        return pat.sub(key + ": " + value, text, count=1)
    parts = text.split("---", 2)
    if len(parts) >= 3:
        return "---" + parts[1].rstrip() + "\n" + key + ": " + value + "\n---" + parts[2]
    return text


def _dest_note(dest: str) -> Path | None:
    """A nota que recebe o backlink: o .md do destino, ou o principal da pasta.

    Pasta sem nota principal nao ganha backlink nenhum: o proprio movimento ja e o
    arquivamento. A primeira versao caia no `sorted(...)[0]`, e depois de mover a
    nota ela mesma passava a ser o primeiro .md da pasta — 6 notas ganharam um
    link para si proprias. Chute alfabetico nao e destino.
    """
    p = VAULT / dest
    if p.is_file():
        return p
    if p.is_dir():
        same = p / (p.name + ".md")
        return same if same.exists() else None
    return None


def _link(dest_note: Path, target_rel: str, resumo: str, data: str, dry: bool) -> bool:
    text = dest_note.read_text(encoding="utf-8", errors="replace")
    linha = "- [[%s]] — %s (%s)" % (target_rel.replace(".md", ""), resumo, data)
    if target_rel.replace(".md", "") in text:
        return False
    head = "## Calls e reunioes roteadas"
    if head in text:
        i = text.index(head)
        j = text.find("\n## ", i + 4)
        bloco = text[i:j] if j != -1 else text[i:]
        novo = bloco.rstrip() + "\n" + linha + "\n"
        text = text[:i] + novo + ("\n" + text[j:].lstrip("\n") if j != -1 else "\n")
    else:
        text = text.rstrip() + "\n\n" + head + "\n\n" + linha + "\n"
    if not dry:
        dest_note.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run
    hoje = datetime.now().strftime("%Y-%m-%d")
    contagem = {"rotear": 0, "revisar": 0, "sensivel": 0, "arquivar": 0, "ausente": 0}

    for nome, (trat, dest, motivo) in PLANO.items():
        src = INBOX / nome
        if not src.exists():
            print("AUSENTE  %s" % nome)
            contagem["ausente"] += 1
            continue
        text = src.read_text(encoding="utf-8", errors="replace")
        data = (re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", text, re.M) or [None, hoje])[1] \
            if re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", text, re.M) else hoje

        if trat == "sensivel":
            text = _set_fm(text, "status", "espera-kelvin")
            text = _set_fm(text, "triagem-motivo", '"' + motivo + '"')
            if not dry:
                src.write_text(text, encoding="utf-8")
            print("SENSIVEL %s\n         %s" % (nome, motivo))
            contagem["sensivel"] += 1
            continue

        if trat == "arquivar":
            text = _set_fm(text, "status", "arquivado")
            text = _set_fm(text, "triagem-motivo", '"' + motivo + '"')
            alvo = ARQUIVO / ("_archived_" + _slug(src.stem) + ".md")
            if not dry:
                ARQUIVO.mkdir(parents=True, exist_ok=True)
                src.write_text(text, encoding="utf-8")
                shutil.move(str(src), str(alvo))
            print("ARQUIVAR %s -> Archive/%s" % (nome, alvo.name))
            contagem["arquivar"] += 1
            continue

        if trat == "revisar":
            # O resumo gerado sai; a transcricao fica. Falha de processamento nao
            # pode ocupar o campo que o leitor le como conteudo (padrao 5).
            corte = None
            for h in ("## Transcricao", "## Transcrição"):
                if h in text:
                    corte = text.index(h)
                    break
            fm_end = text.index("---", 3) + 3 if text.startswith("---") else 0
            ctx = re.search(r"^> \*\*Contexto:\*\*.*$", text, re.M)
            cabeca = (ctx.group(0) + "\n\n") if ctx else ""
            aviso = (MARCA + "\n\n> **Resumo removido na triagem de " + hoje + ".** "
                     + motivo + " O texto gerado foi retirado para nao ser lido como "
                     "registro. A transcricao abaixo esta intacta e e a unica fonte.\n\n")
            text = text[:fm_end] + "\n\n" + cabeca + aviso + (text[corte:] if corte else "")
            text = _set_fm(text, "status", "resumo-removido")
            text = _set_fm(text, "triagem-motivo", '"' + motivo + '"')
            if dest:
                text = _set_fm(text, "destino", dest)
            if not dry:
                src.write_text(text, encoding="utf-8")
            print("REVISAR  %s\n         %s" % (nome, motivo))
            contagem["revisar"] += 1
            trat = "rotear" if dest else trat

        if trat == "rotear":
            alvo_dir = VAULT / dest
            movido = None
            if alvo_dir.is_dir():
                movido = alvo_dir / (data + "-" + _slug(src.stem)[11:] + ".md")
                if not dry:
                    shutil.move(str(src), str(movido))
                rel = str(movido.relative_to(VAULT)).replace("\\", "/")
            else:
                text = _set_fm(text, "status", "triado")
                text = _set_fm(text, "destino", dest)
                if not dry:
                    src.write_text(text, encoding="utf-8")
                rel = "Inbox/" + nome
            note = _dest_note(dest)
            if note is not None:
                _link(note, rel, motivo, data, dry)
            print("ROTEAR   %s -> %s%s" % (nome, dest, "  (movido)" if movido else "  (link)"))
            contagem["rotear"] += 1

    print("\n" + " · ".join("%s: %d" % (k, v) for k, v in contagem.items()))
    if dry:
        print("(dry-run: nada foi gravado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
