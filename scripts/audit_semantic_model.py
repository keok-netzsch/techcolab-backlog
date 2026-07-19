"""
audit_semantic_model.py — PoC: automated first pass of the Semantic Model Curation Checklist
(vault/guia-curadoria-modelo-semantico.md) against a real .pbix file.

Usage:
    python scripts/audit_semantic_model.py "path/to/model.pbix" [--json]

Design principle (deliberate): this script does NOT claim to auto-score the whole
100-point checklist. Several items are structurally impossible to verify from static
model metadata alone (e.g. "is the grain semantically consistent", "was this tested
with Copilot"). Those are surfaced as NOT_AUTOMATED with supporting context, not
silently scored as pass or fail. The Claude skill that wraps this script is expected
to apply judgment on those items using the guide as reference.

Requires: pip install pbixray pandas
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pandas as pd
from pbixray import PBIXRay

# ── Heuristics ──────────────────────────────────────────────────────────────

# Word-style technical prefixes (dim_, fact_, fct_, d_, f_) — case-insensitive is safe here
# because each branch requires the separator/whole-word boundary, not just a bare letter.
_TECHNICAL_PREFIX_WORD_RE = re.compile(r"^(dim[_ ]|fact[_ ]|fct[_ ]|f_|d_)", re.IGNORECASE)
# camelCase-style technical prefix (fBusiness, dCalendar) — MUST stay case-sensitive:
# a lowercase f/d immediately followed by an uppercase letter. Under IGNORECASE this
# would match almost any word starting with D or F (e.g. "DataQuality") — verified bug,
# caught by testing against a real .pbix before shipping.
_TECHNICAL_PREFIX_CAMEL_RE = re.compile(r"^[fd](?=[A-Z])")
_SNAKE_OR_CAMEL_RE = re.compile(r"^[a-z]+(_[a-z0-9]+)+$|^[a-z]+([A-Z][a-z0-9]*)+$")
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
_NUMERIC_DTYPES = {"int64", "Int64", "float64", "Float64", "double", "decimal"}
_DATETIME_DTYPES = {"datetime64[ns]", "date"}


def _is_technical_name(name: str) -> bool:
    stripped = name.strip()
    return bool(_TECHNICAL_PREFIX_WORD_RE.match(stripped) or _TECHNICAL_PREFIX_CAMEL_RE.match(stripped))


def _is_snake_or_camel(name: str) -> bool:
    return bool(_SNAKE_OR_CAMEL_RE.match(name.strip()))


def _has_emoji(name: str) -> bool:
    return bool(_EMOJI_RE.search(name))


def _clean_name_flags(name: str) -> list[str]:
    flags = []
    if _is_technical_name(name):
        flags.append("technical_prefix")
    if _is_snake_or_camel(name):
        flags.append("snake_or_camel_case")
    if _has_emoji(name):
        flags.append("emoji")
    return flags


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    id: str
    label: str
    max_points: float
    automated: bool
    score: float | None  # None when not automated
    detail: dict = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class Category:
    id: str
    label: str
    checks: list[CheckResult]

    @property
    def max_points(self) -> float:
        return sum(c.max_points for c in self.checks)

    @property
    def automated_points(self) -> float:
        return sum(c.score for c in self.checks if c.automated and c.score is not None)

    @property
    def automated_max(self) -> float:
        return sum(c.max_points for c in self.checks if c.automated)


# ── Model loading + unified frames ────────────────────────────────────────────

def load_model(pbix_path: str) -> PBIXRay:
    return PBIXRay(pbix_path)


def unified_columns(model: PBIXRay) -> pd.DataFrame:
    """Join pandas-friendly dtypes (model.schema) with TOM metadata (model.tmschema_columns)."""
    schema = model.schema.rename(columns={"ColumnName": "Name"})
    tom = model.tmschema_columns
    merged = schema.merge(tom, on=["TableName", "Name"], how="left", suffixes=("", "_tom"))
    return merged


def relationships(model: PBIXRay) -> pd.DataFrame:
    return model.relationships


def measures(model: PBIXRay) -> pd.DataFrame:
    return model.dax_measures


# ── Fact-table heuristic (used by several checks) ─────────────────────────────

def guess_fact_tables(rels: pd.DataFrame) -> set[str]:
    """Heuristic: a table on the 'many' side (M:1) of at least one relationship
    is a fact-table candidate. This is a heuristic, not ground truth — surfaced
    to the human/LLM reviewer, never used to silently fail a model."""
    if rels.empty:
        return set()
    many_side = rels[rels["Cardinality"].astype(str).str.startswith("M")]
    return set(many_side["FromTableName"].unique())


# ── Category A — Fundamentos (25 pts) ─────────────────────────────────────────

def check_a(model: PBIXRay, rels: pd.DataFrame) -> Category:
    fact_candidates = sorted(guess_fact_tables(rels))

    # A1 — grão consistente (10 pts) — NOT automatable from static metadata.
    a1 = CheckResult(
        id="A1", label="Toda tabela fato tem grão único e consistente", max_points=10,
        automated=False, score=None,
        detail={"fact_table_candidates": fact_candidates},
        note="Não dá pra verificar grão só pela metadata do modelo — exige entender o "
             "significado de negócio de cada linha. Revisar manualmente as tabelas candidatas "
             "a fato listadas em 'detail'.",
    )

    # A2 — relacionamentos 1:N, sem M:N direto, role-playing resolvido
    mn_rels = rels[rels["Cardinality"].astype(str).str.contains("M:N", na=False)] if not rels.empty else pd.DataFrame()
    pair_counts = (
        rels.groupby(["FromTableName", "ToTableName"]).size().reset_index(name="n")
        if not rels.empty else pd.DataFrame(columns=["FromTableName", "ToTableName", "n"])
    )
    role_playing_candidates = pair_counts[pair_counts["n"] > 1]
    a2_score = 10.0 if mn_rels.empty else 0.0
    a2 = CheckResult(
        id="A2",
        label="Relacionamentos 1:N (sem M:N direto); role-playing dimensions resolvidas",
        max_points=10, automated=True, score=a2_score,
        detail={
            "many_to_many_relationships": mn_rels.to_dict("records") if not mn_rels.empty else [],
            "role_playing_candidates (table pairs with >1 relationship)":
                role_playing_candidates.to_dict("records") if not role_playing_candidates.empty else [],
        },
        note="Score automático cobre só a ausência de M:N direto. Os pares de tabelas com "
             "mais de 1 relacionamento (possível role-playing) estão listados em 'detail' "
             "para revisão manual — nem sempre é um problema, mas merece checar se foi "
             "resolvido com tabelas separadas (bom) ou relações inativas acumuladas (ruim).",
    )

    # A3 — bidirecional usado com entendimento — presence is checkable, judgment isn't.
    bidir = rels[rels["CrossFilteringBehavior"] == "Both"] if not rels.empty else pd.DataFrame()
    a3 = CheckResult(
        id="A3", label="Bidirecional usado só onde necessário e documentado", max_points=5,
        automated=False, score=None,
        detail={"bidirectional_relationships": bidir.to_dict("records") if not bidir.empty else []},
        note="Presença é automática, mas 'necessário e entendido' exige julgamento humano. "
             f"{len(bidir)} relacionamento(s) bidirecional(is) encontrado(s) — revisar cada um.",
    )

    return Category(id="A", label="Fundamentos", checks=[a1, a2, a3])


# ── Category B — Curadoria para negócio (45 pts) ──────────────────────────────

def check_b(model: PBIXRay, cols: pd.DataFrame, meas: pd.DataFrame, fact_candidates: list[str]) -> Category:
    # B1 — nomenclatura de negócio (heuristic regex pass over tables, columns, measures)
    table_names = list(model.tables)
    col_names = cols["Name"].dropna().tolist()
    measure_names = meas["Name"].dropna().tolist() if not meas.empty else []

    flagged = []
    all_names = (
        [("table", t) for t in table_names]
        + [("column", c) for c in col_names]
        + [("measure", m) for m in measure_names]
    )
    for kind, name in all_names:
        flags = _clean_name_flags(str(name))
        if flags:
            flagged.append({"kind": kind, "name": name, "flags": flags})

    total_names = len(all_names) or 1
    clean_ratio = 1 - (len(flagged) / total_names)
    b1_score = 10.0 if clean_ratio >= 0.9 else 5.0 if clean_ratio >= 0.7 else 0.0
    b1 = CheckResult(
        id="B1", label="Nomes em linguagem de negócio, sem prefixo técnico/sigla", max_points=10,
        automated=True, score=b1_score,
        detail={"clean_ratio": round(clean_ratio, 3), "flagged_names": flagged[:50],
                "flagged_count": len(flagged), "total_names": total_names},
        note="Heurística por regex (prefixo técnico tipo f_/d_/dim_/fact_, snake_case/camelCase, "
             "emoji). Não pega tudo (siglas de negócio legítimas podem ser sinalizadas à toa) — "
             "revisar a lista antes de penalizar o analista.",
    )

    # B2 — medidas nomeiam o resultado / período padronizado — NOT automatable (semantic judgment)
    b2 = CheckResult(
        id="B2", label="Medidas nomeiam o resultado, período/unidade padronizados", max_points=5,
        automated=False, score=None,
        detail={"measure_names": measure_names},
        note="Julgamento semântico — não dá pra saber programaticamente se um nome 'descreve o "
             "resultado' de forma consistente. Revisar a lista de nomes de medida.",
    )

    # B3 — colunas técnicas da tabela fato ocultas
    if fact_candidates:
        fact_cols = cols[cols["TableName"].isin(fact_candidates)]
        non_key_fact_cols = fact_cols[fact_cols["IsKey"] != 1] if "IsKey" in fact_cols else fact_cols
        hidden_ratio = (
            non_key_fact_cols["IsHidden"].fillna(0).astype(int).mean()
            if not non_key_fact_cols.empty else 1.0
        )
        b3_score = 5.0 if hidden_ratio >= 0.9 else 2.5 if hidden_ratio >= 0.5 else 0.0
        visible_fact_cols = non_key_fact_cols[non_key_fact_cols["IsHidden"].fillna(0).astype(int) == 0]
        b3_detail = {
            "fact_table_candidates": fact_candidates,
            "hidden_ratio": round(float(hidden_ratio), 3),
            "visible_technical_columns": visible_fact_cols[["TableName", "Name"]].to_dict("records"),
        }
    else:
        b3_score, b3_detail = None, {"note": "Nenhuma tabela fato candidata identificada (ver A1)."}
    b3 = CheckResult(
        id="B3", label="Colunas técnicas da tabela fato ocultas — só medidas visíveis", max_points=5,
        automated=fact_candidates != [], score=b3_score, detail=b3_detail,
        note="Depende da heurística de tabela fato de A1 — confirme se a lista de candidatas faz sentido.",
    )

    # B4 — hierarquias com atributos ocultos
    hier = model.tmschema_hierarchies
    n_hierarchies = len(hier) if hier is not None else 0
    b4 = CheckResult(
        id="B4", label="Hierarquias criadas onde faz sentido, atributos ocultos", max_points=5,
        automated=False, score=None,
        detail={"hierarchies_found": n_hierarchies},
        note=f"{n_hierarchies} hierarquia(s) encontrada(s) no modelo. Zero hierarquias não é "
             "necessariamente um erro (depende se o modelo tem atributos que formam uma "
             "hierarquia de negócio real) — julgamento humano.",
    )

    # B5 — display folders
    has_folder_cols = cols["DisplayFolder"].fillna("").astype(str).str.strip().ne("").mean() if not cols.empty else 0
    has_folder_meas = (
        meas["DisplayFolder"].fillna("").astype(str).str.strip().ne("").mean() if not meas.empty else 0
    )
    combined_folder_ratio = (has_folder_cols + has_folder_meas) / 2
    b5_score = 5.0 if combined_folder_ratio >= 0.8 else 2.5 if combined_folder_ratio >= 0.4 else 0.0
    b5 = CheckResult(
        id="B5", label="Medidas/colunas organizadas em display folders", max_points=5,
        automated=True, score=b5_score,
        detail={"columns_with_folder_ratio": round(float(has_folder_cols), 3),
                "measures_with_folder_ratio": round(float(has_folder_meas), 3)},
    )

    # B6 — nomes duplicados entre tabelas
    dupe_names = (
        cols.groupby(cols["Name"].str.lower())["TableName"].nunique()
        if not cols.empty else pd.Series(dtype=int)
    )
    dupes = dupe_names[dupe_names > 1]
    b6_score = 5.0 if dupes.empty else 0.0
    b6 = CheckResult(
        id="B6", label="Nenhum nome de campo duplicado entre tabelas", max_points=5,
        automated=True, score=b6_score,
        detail={"duplicated_column_names": dupes.index.tolist()},
    )

    # B7 — descrições preenchidas
    def _desc_ratio(df: pd.DataFrame) -> float:
        if df.empty or "Description" not in df:
            return 0.0
        return df["Description"].fillna("").astype(str).str.strip().ne("").mean()

    desc_ratio_cols = _desc_ratio(cols)
    desc_ratio_meas = _desc_ratio(meas)
    combined_desc = (desc_ratio_cols + desc_ratio_meas) / 2
    b7_score = 5.0 if combined_desc >= 0.8 else 2.0 if combined_desc >= 0.3 else 0.0
    b7 = CheckResult(
        id="B7", label="Descrições preenchidas em tabelas/colunas/medidas", max_points=5,
        automated=True, score=b7_score,
        detail={"columns_with_description_ratio": round(float(desc_ratio_cols), 3),
                "measures_with_description_ratio": round(float(desc_ratio_meas), 3)},
    )

    # B8 — format string / data category
    numeric_or_date = cols[cols["PandasDataType"].isin(_NUMERIC_DTYPES | _DATETIME_DTYPES)]
    fs_ratio = (
        numeric_or_date["FormatString"].fillna("").astype(str).str.strip().ne("").mean()
        if not numeric_or_date.empty else None
    )
    meas_fs_ratio = None  # dax_measures from pbixray doesn't expose FormatStringExpression directly
    b8_score = None
    if fs_ratio is not None:
        b8_score = 5.0 if fs_ratio >= 0.8 else 2.0 if fs_ratio >= 0.4 else 0.0
    b8 = CheckResult(
        id="B8", label="Format string e data category preenchidos", max_points=5,
        automated=fs_ratio is not None, score=b8_score,
        detail={"numeric_or_date_columns_with_format_string_ratio":
                    round(float(fs_ratio), 3) if fs_ratio is not None else None,
                "note_measures": "dax_measures não expõe format string de medida via pbixray "
                                  "nesta versão — conferir manualmente no Power BI."},
    )

    return Category(id="B", label="Curadoria para negócio", checks=[b1, b2, b3, b4, b5, b6, b7, b8])


# ── Category C — AI-readiness / Copilot (30 pts) ──────────────────────────────

def check_c(model: PBIXRay, cols: pd.DataFrame, meas: pd.DataFrame) -> Category:
    # C1 — descrições claras nos 200 caracteres (medidas + colunas-chave)
    key_cols = cols[cols["IsKey"] == 1] if "IsKey" in cols else cols.iloc[0:0]
    relevant = pd.concat([
        meas[["Name", "Description"]].assign(kind="measure") if not meas.empty else pd.DataFrame(),
        key_cols[["Name", "Description"]].assign(kind="key_column") if not key_cols.empty else pd.DataFrame(),
    ], ignore_index=True) if (not meas.empty or not key_cols.empty) else pd.DataFrame(columns=["Name", "Description", "kind"])

    def _has_good_desc(v) -> bool:
        s = str(v).strip() if pd.notna(v) else ""
        return 0 < len(s) <= 200

    if not relevant.empty:
        good_ratio = relevant["Description"].apply(_has_good_desc).mean()
        too_long = relevant[relevant["Description"].fillna("").astype(str).str.len() > 200]
        c1_score = 10.0 if good_ratio >= 0.8 else 5.0 if good_ratio >= 0.4 else 0.0
    else:
        good_ratio, too_long, c1_score = 0.0, pd.DataFrame(), 0.0
    c1 = CheckResult(
        id="C1", label="Medidas e colunas-chave com descrição clara ≤200 caracteres", max_points=10,
        automated=True, score=c1_score,
        detail={"good_description_ratio": round(float(good_ratio), 3),
                "descriptions_over_200_chars": too_long["Name"].tolist() if not too_long.empty else []},
    )

    # C2 — sinônimos (best-effort: only checks presence of Q&A linguistic metadata, not content quality)
    ling = model.tmschema_linguistic_metadata
    has_ling = ling is not None and not ling.empty
    synonym_hits = 0
    if has_ling:
        try:
            synonym_hits = sum(str(c).count("Synonyms") for c in ling["Content"].tolist())
        except Exception:
            synonym_hits = 0
    c2 = CheckResult(
        id="C2", label="Sinônimos configurados para termos alternativos", max_points=5,
        automated=False, score=None,
        detail={"linguistic_metadata_present": bool(has_ling), "synonyms_json_hits": synonym_hits},
        note="Detecção best-effort — só confirma se existe metadata linguística no modelo, "
             "não valida qualidade/cobertura dos sinônimos. Conferir manualmente na aba "
             "Linguistic Schema / Q&A setup.",
    )

    # C3 — schema simplificado pra IA — not reliably automatable (needs to know what's "unused")
    total_cols = len(cols)
    hidden_cols = int(cols["IsHidden"].fillna(0).astype(int).sum()) if "IsHidden" in cols else 0
    total_meas = len(meas)
    c3 = CheckResult(
        id="C3", label="Schema exposto à IA simplificado (Prep data for AI)", max_points=10,
        automated=False, score=None,
        detail={"total_columns": total_cols, "hidden_columns": hidden_cols,
                "total_measures": total_meas},
        note="Não dá pra saber que campo é 'não usado' só pela metadata do modelo (dependeria "
             "de analisar todos os relatórios que o consomem). Rodar 'Prep data for AI' no "
             "Power BI Desktop é o passo real — este número é só contexto de tamanho do modelo.",
    )

    # C4 — testado com Copilot — cannot be automated at all
    c4 = CheckResult(
        id="C4", label='Testado com perguntas reais no Copilot antes de "Approved for Copilot"',
        max_points=5, automated=False, score=None, detail={},
        note="Não automatizável — exige sessão real no Copilot do Power BI. Confirmar manualmente.",
    )

    return Category(id="C", label="AI-readiness / Copilot", checks=[c1, c2, c3, c4])


# ── Report assembly ────────────────────────────────────────────────────────────

def run_audit(pbix_path: str) -> dict:
    model = load_model(pbix_path)
    rels = relationships(model)
    cols = unified_columns(model)
    meas = measures(model)
    fact_candidates = sorted(guess_fact_tables(rels))

    cat_a = check_a(model, rels)
    cat_b = check_b(model, cols, meas, fact_candidates)
    cat_c = check_c(model, cols, meas)

    categories = [cat_a, cat_b, cat_c]
    automated_total = sum(c.automated_points for c in categories)
    automated_max = sum(c.automated_max for c in categories)
    grand_max = sum(c.max_points for c in categories)
    not_automated = [
        {"category": cat.id, "id": chk.id, "label": chk.label, "max_points": chk.max_points, "note": chk.note}
        for cat in categories for chk in cat.checks if not chk.automated
    ]

    return {
        "file": pbix_path,
        "tables": list(model.tables),
        "categories": [
            {
                "id": cat.id, "label": cat.label,
                "max_points": cat.max_points,
                "automated_points": round(cat.automated_points, 2),
                "automated_max": cat.automated_max,
                "checks": [c.to_dict() for c in cat.checks],
            }
            for cat in categories
        ],
        "summary": {
            "automated_score": round(automated_total, 2),
            "automated_max": automated_max,
            "grand_max_possible": grand_max,
            "not_automated_count": len(not_automated),
            "not_automated_points_pending_review": grand_max - automated_max,
        },
        "not_automated_items": not_automated,
    }


def print_human_report(report: dict) -> None:
    print(f"\n=== Auditoria de Modelo Semântico — {Path(report['file']).name} ===\n")
    print(f"Tabelas no modelo: {len(report['tables'])}")
    for cat in report["categories"]:
        print(f"\n-- Categoria {cat['id']} — {cat['label']} "
              f"({cat['automated_points']}/{cat['automated_max']} pts automatizados de {cat['max_points']} pts totais) --")
        for chk in cat["checks"]:
            status = f"{chk['score']}/{chk['max_points']}" if chk["automated"] else "REVISÃO MANUAL"
            print(f"  [{chk['id']}] {chk['label']} — {status}")
            if chk["note"]:
                print(f"        nota: {chk['note']}")
    s = report["summary"]
    print(f"\n=== Resumo ===")
    print(f"Score automatizado: {s['automated_score']}/{s['automated_max']} "
          f"(de um total possível de {s['grand_max_possible']} pts)")
    print(f"Itens que precisam de revisão manual/LLM: {s['not_automated_count']} "
          f"(vale {s['not_automated_points_pending_review']} pts)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python audit_semantic_model.py <path/to/model.pbix> [--json]")
        sys.exit(1)

    path = sys.argv[1]
    as_json = "--json" in sys.argv

    result = run_audit(path)
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print_human_report(result)
