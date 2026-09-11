"""vaultsources/profile.py — o vocabulario do que interessa ao Kelvin, tirado do vault.

Item 2 da lista de conserto de 2026-09-10. O ranking cruzava o titulo do video com
as 114 perguntas abertas e com os topicos que alguem deu ao feed. Nao olhava o
perfil dele, nem os OKRs, nem os projetos. Com 114 perguntas, duas palavras em
comum acontecem por acaso, e foi assim que "10 SUVs bons e baratos" ficou no topo
da fila do Watch Later.

O que ele faz ja esta escrito no vault, em varios lugares. Este modulo le esses
lugares e monta uma lista de termos com peso. Nao inventa nada e nao usa modelo:
conta ocorrencia, tira palavra vazia, e **exige que o termo apareca em pelo menos
duas fontes diferentes** — assim o jargao de uma nota so nao vira criterio.

De onde vem, e por que so daqui:

    kelvin-profile.md        quem ele e e o que faz, escrito por ele
    Areas/OKR 2027/*/        os objetivos do ciclo, que sao a prioridade declarada
    Projects/                o que esta em andamento de fato
    Concepts/                as posicoes que ele ja sustenta
    Areas/*.md               as responsabilidades continuas

`Team/` e `Stakeholders/` ficam de fora. Nome de colega nao e criterio de
relevancia de video, e manter isso fora do vocabulario evita que um nome vaze para
qualquer lugar que consuma este modulo.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from vaultsources import paths

# Termo de 4+ letras; numero sozinho nao vira criterio.
_WORD = re.compile(r"[a-z][a-z0-9-]{3,}")

_STOP = set("""
para como esse essa isso pelo pela mais menos sobre quando onde porque entao ainda
cada todo toda todos todas outro outra outros outras muito pouco tambem apenas
depois antes sempre nunca algum alguma alguns algumas nada tudo aqui ali assim
pode podem podia deve devem sera serao esta estao estava estavam estar sendo foram
fica ficam ficou ficar quem qual quais entre dentro fora sobre desde ate mesmo
mesma mesmos mesmas partir seja sejam existe existem havia tinha tem temos teve
numero parte partes forma formas caso casos vez vezes lugar lado ponto pontos
coisa coisas ideia ideias exemplo exemplos hoje amanha ontem semana mes ano anos
dias hora horas primeiro segundo terceiro proximo proxima anterior atual nova novo
novas novos velho grande pequeno melhor pior alto baixo longo curto varios varias
nao sim talvez porem contudo entretanto portanto assim logo enquanto durante
there with from that this have will your what when which them they been were into
then than some more most only also such each other about would could should must
which where while after before because between during through over under again
very just even still both many much such does doing done make makes made take
takes taken give gives given need needs needed want wants like likes want using
used uses first second third next last same other another every here well back
good great best better worse thing things people person time times year years
month day days week weeks part parts case cases point points example examples
vault nota notas arquivo arquivos claude future date type tags true false null
none http https www markdown frontmatter kelvin okuda note item itens fonte fontes
documento documentos texto secao secoes titulo campo campos linha linhas tabela
lista listas nome nomes status owner overview related source sources content
""".split())

CACHE_DIAS = 7
TOP_N = 120
COTA_GRUPO = 30   # termos garantidos por grupo de fonte


def _flat(text: str) -> str:
    n = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in n if not unicodedata.combining(c))


_PESSOAS: set[str] | None = None


def _pessoas() -> set[str]:
    """Nomes de colega, para que nunca virem criterio de relevancia de video.

    A primeira execucao devolveu `stefan` entre os termos de maior peso: as notas
    de projeto citam gente o tempo todo. Nome de pessoa nao diz nada sobre o
    assunto de um video, e deixar isso no vocabulario e o comeco de um vazamento."""
    global _PESSOAS
    if _PESSOAS is None:
        try:
            from vaultsources import questions
            _PESSOAS = {p.replace(" ", "") for p in questions.known_people()} | {
                w for p in questions.known_people() for w in p.split()}
        except Exception:
            _PESSOAS = set()
    return _PESSOAS


def _terms(text: str) -> list[str]:
    fora = _STOP | _pessoas()
    return [w for w in _WORD.findall(_flat(text)) if w not in fora]


def _fontes() -> list[tuple[str, list[Path], int]]:
    """(rotulo, arquivos, peso). Peso alto onde a intencao e mais explicita."""
    V = paths.VAULT
    okr = V / "Areas" / "OKR 2027"
    return [
        ("perfil", [V / "vault" / "kelvin-personal" / "kelvin-profile.md"], 3),
        ("okr", sorted(okr.glob("*/charter.md")) if okr.exists() else [], 3),
        ("conceitos", sorted(paths.CONCEPTS_DIR.glob("*.md"))
         if paths.CONCEPTS_DIR.exists() else [], 2),
        ("projetos", sorted((V / "Projects").glob("*.md"))
         + sorted((V / "Projects").glob("*/*.md"))[:60]
         if (V / "Projects").exists() else [], 2),
        ("areas", sorted((V / "Areas").glob("*.md")) if (V / "Areas").exists() else [], 1),
        # Prioridade de estudo e prioridade declarada, e muda mais rapido que
        # projeto. Sem esta fonte o vocabulario nao conhecia SC-401, Purview,
        # Copilot Studio nem alemao, e conteudo desses assuntos so ranqueava por
        # topico do feed. Entrou em 2026-09-10, quando o Kelvin trocou a ordem das
        # provas e pediu canais de SAP MM, MDG, SC-401, alemao e ingles.
        ("estudo", _arquivos_de_estudo(), 3),
    ]


def _arquivos_de_estudo() -> list[Path]:
    """Roteiro de exames e conceitos fracos. Score nunca entra aqui, so vocabulario."""
    raiz = paths.VAULT / "vault" / "study-tools"
    if not raiz.exists():
        return []
    out = [raiz / "study" / "certifications.json"]
    out += sorted(raiz.glob("*/*-weak-concepts.json"))
    return [p for p in out if p.exists()]


_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_HEADING = re.compile(r"^#{1,6} .*$", re.M)
_TABELA = re.compile(r"^\|.*$", re.M)

# Teto de frequencia documental, alto de proposito. A primeira versao usou 35% e o
# resultado foi pior: `governance`, `dados`, `power bi` e `copilot` sumiram do
# vocabulario justamente por serem frequentes, e serem frequentes e o que os torna
# o foco dele. Frequencia nao era o problema; palavra de gabarito era, e isso se
# resolve com lista de parada, nao com corte estatistico.
DF_MAX = 0.85


def _corpo(texto: str) -> str:
    """Texto sem frontmatter, sem titulo de secao e sem tabela.

    Sem isto o vocabulario sai cheio de palavra de gabarito: as notas do vault tem
    todas os mesmos campos e as mesmas secoes, entao esses termos aparecem em 100%
    dos arquivos e afogam o assunto."""
    texto = _FRONTMATTER.sub("", texto)
    texto = _HEADING.sub("", texto)
    texto = _TABELA.sub("", texto)
    return texto


def compute() -> dict:
    """Conta termos por fonte, tira o vocabulario do formato, e mantem o que
    aparece em pelo menos dois grupos diferentes."""
    por_fonte: dict[str, Counter] = {}
    df: Counter = Counter()
    lidos = 0
    for rotulo, arquivos, peso in _fontes():
        c: Counter = Counter()
        for p in arquivos:
            if not p.exists() or p.name.startswith("_"):
                continue
            if "CONFIDENCIAL" in str(p).upper():
                continue
            try:
                texto = p.read_text(encoding="utf-8", errors="replace")[:20000]
            except OSError:
                continue
            lidos += 1
            termos_do_arquivo = set(_terms(_corpo(texto)))
            for t in termos_do_arquivo:
                c[t] += peso
                df[t] += 1
        por_fonte[rotulo] = c

    total: Counter = Counter()
    grupos: Counter = Counter()
    for _rotulo, c in por_fonte.items():
        for t, v in c.items():
            total[t] += v
            grupos[t] += 1

    teto = max(2, int(lidos * DF_MAX))
    # A regra dos dois grupos protege contra jargao de um arquivo so, mas mata
    # termo que legitimamente mora num lugar unico. `sc-401` aparece so no roteiro
    # de exames e `goethe` so ali tambem, e os dois sao prioridade declarada, nao
    # jargao. Entao perfil, OKR e estudo passam por cima da regra: sao os lugares
    # onde ele DIZ o que importa, e dizer uma vez ja basta.
    autoritativos = {"perfil", "okr", "estudo"}
    isentos = {t2 for rot in autoritativos for t2 in por_fonte.get(rot, {})}
    termos = {t: v for t, v in total.items()
              if df[t] <= teto and (grupos[t] >= 2 or t in isentos)}

    # Cota por grupo. Um top-N global e dominado por quem tem mais arquivos: com
    # 60 notas de projeto contra 4 de estudo, `purview`, `sc-401` e `goethe` nao
    # chegavam nem perto do corte, e prioridade de estudo e das coisas que mais
    # mudam. A cota garante que cada grupo apareca, e o resto do espaco vai para os
    # de maior peso.
    # Grupo pequeno e autoritativo entra INTEIRO. `perfil` e `estudo` tem um ou dois
    # arquivos, entao todos os termos deles empatam no mesmo peso e um
    # `most_common(30)` escolhe 30 quaisquer entre duzentos empatados — foi assim
    # que `sc-401` e `goethe` ficaram de fora mesmo estando escritos no roteiro de
    # exames. Desempate arbitrario em fonte de prioridade e pior que nao filtrar.
    top: dict[str, int] = {}
    for rotulo, c in por_fonte.items():
        elegiveis = {k: v for k, v in c.items() if k in termos}
        cota = len(elegiveis) if rotulo in ("perfil", "estudo") else COTA_GRUPO
        for t2, _v in Counter(elegiveis).most_common(cota):
            top[t2] = termos[t2]
    limite = TOP_N + COTA_GRUPO * 2 + len(top)
    for t2, v in Counter(termos).most_common(TOP_N):
        if len(top) >= limite:
            break
        top.setdefault(t2, v)
    top = dict(sorted(top.items(), key=lambda kv: -kv[1]))
    return {"gerado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "arquivos_lidos": lidos, "df_teto": teto, "termos": top}


def _cache_file() -> Path:
    return paths.media_cache() / "profile-terms.json"


def load(refresh: bool = False) -> dict:
    f = _cache_file()
    if not refresh and f.exists():
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            quando = datetime.strptime(d["gerado"], "%Y-%m-%d %H:%M")
            if datetime.now() - quando < timedelta(days=CACHE_DIAS):
                return d
        except Exception:
            pass
    d = compute()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return d


def match(titulo: str, perfil: dict | None = None) -> tuple[int, list[str]]:
    """Quantos termos do foco dele o titulo toca, e quais."""
    perfil = perfil or load()
    termos = perfil.get("termos", {})
    achados = sorted({w for w in _terms(titulo) if w in termos},
                     key=lambda w: -termos[w])
    return len(achados), achados[:5]
