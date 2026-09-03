"""
vaultindex/bench.py — measure retrieval against a golden set, per stream and per model.

The golden set is JSONL, one question per line: {"q": "...", "expect": "rel/path.md"}.
It lives in the vault (App/Personal toolkit/bench/golden.jsonl), never in the public repo:
the questions name people and projects. hit@1, hit@k and MRR per mode; the ADR (§2.5)
says the numbers pick the embedding model, so this is the file that gets to decide.
"""

from __future__ import annotations

import json
from pathlib import Path

from vaultindex.search import search

MODES: dict[str, dict] = {
    "fts": {"streams": ("fts",), "neighbours": False},
    "vec": {"streams": ("vec",), "neighbours": False},
    "hybrid": {"streams": ("fts", "vec"), "neighbours": True},
}


def default_golden_path() -> Path:
    from config import VAULT_ROOT

    return Path(VAULT_ROOT) / "bench" / "golden.jsonl"


def load_golden(path: Path) -> list[dict]:
    items = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        item = json.loads(line)
        if "q" not in item or "expect" not in item:
            raise ValueError(f"linha do golden set sem q/expect: {line[:80]}")
        items.append(item)
    return items


def _rank_of(expect: str, results: list[dict]) -> int | None:
    expect_l = expect.lower()
    for r in results:
        p = r["path"].lower()
        if p == expect_l or p.endswith("/" + expect_l):
            return r["rank"]
    return None


def run_bench(
    golden: Path | None = None,
    *,
    index_dir: Path | None = None,
    root: Path | None = None,
    models: list[str] | None = None,
    modes: tuple[str, ...] = ("fts", "vec", "hybrid"),
    k: int = 5,
    embedder=None,
) -> dict:
    items = load_golden(golden or default_golden_path())
    models = models or [None]  # None = the active model in the index
    report: dict = {"golden": str(golden or default_golden_path()), "questions": len(items), "k": k, "runs": []}
    for model in models:
        for mode in modes:
            cfg = MODES[mode]
            ranks: list[int | None] = []
            details = []
            for item in items:
                out = search(
                    item["q"],
                    k=max(k, 10),
                    include_sensitive=True,
                    refresh=False,
                    root=root,
                    index_dir=index_dir,
                    streams=cfg["streams"],
                    neighbours=cfg["neighbours"],
                    model=model,
                    embedder=embedder,
                )
                rank = _rank_of(item["expect"], out["results"])
                ranks.append(rank)
                details.append({"q": item["q"], "expect": item["expect"], "rank": rank, "top": out["results"][0]["path"] if out["results"] else None})
            n = len(ranks) or 1
            run = {
                "model": model or "(ativo)",
                "mode": mode,
                "hit@1": round(sum(1 for r in ranks if r == 1) / n, 3),
                f"hit@{k}": round(sum(1 for r in ranks if r is not None and r <= k) / n, 3),
                "mrr": round(sum(1.0 / r for r in ranks if r) / n, 3),
                "missed": sum(1 for r in ranks if r is None),
                "details": details,
            }
            report["runs"].append(run)
    return report


def render(report: dict) -> str:
    k = report["k"]
    lines = [f"golden: {report['golden']} · {report['questions']} perguntas · k={k}", ""]
    lines.append(f"{'modelo':<42} {'modo':<8} {'hit@1':>6} {'hit@' + str(k):>6} {'mrr':>6} {'perdeu':>6}")
    for run in report["runs"]:
        lines.append(
            f"{run['model']:<42} {run['mode']:<8} {run['hit@1']:>6.3f} {run['hit@' + str(k)]:>6.3f} {run['mrr']:>6.3f} {run['missed']:>6}"
        )
    return "\n".join(lines)
