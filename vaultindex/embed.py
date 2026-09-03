"""
vaultindex/embed.py — sentence embeddings in-process: ONNX int8 on CPU, no API, no server.

Two candidate models, both pinned by sha256 (ADR §2.5). The only network call this module
ever makes is the one-time download of the model files; the query and the notes never leave
the machine. Which model is active is a fact stored in the index (`meta.embedding_model`),
written by `embed`, and the bench is what decides it, not the blog post that inspired this.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from vaultindex.db import default_index_dir


@dataclass(frozen=True)
class ModelSpec:
    name: str
    base_url: str
    files: dict[str, tuple[str, str]]  # local name -> (remote path, sha256)
    dim: int
    max_len: int  # tokens; text beyond this is cut, so chunks must stay under it
    languages: str


MODELS: dict[str, ModelSpec] = {
    "all-MiniLM-L6-v2": ModelSpec(
        name="all-MiniLM-L6-v2",
        base_url="https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/",
        files={
            "model.onnx": (
                "onnx/model_quint8_avx2.onnx",
                "b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21",
            ),
            "tokenizer.json": (
                "tokenizer.json",
                "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
            ),
        },
        dim=384,
        max_len=256,
        languages="en",
    ),
    "paraphrase-multilingual-MiniLM-L12-v2": ModelSpec(
        name="paraphrase-multilingual-MiniLM-L12-v2",
        base_url="https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/resolve/main/",
        files={
            "model.onnx": (
                "onnx/model_quint8_avx2.onnx",
                "98a01d88b7de996cdea58c32ca71208c09968d143798814b2ea09d3439dc334f",
            ),
            "tokenizer.json": (
                "tokenizer.json",
                "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8",
            ),
        },
        dim=384,
        max_len=128,
        languages="50 languages, pt included",
    ),
}

# Chosen by the bench on 2026-09-03 (ADR §8): 38 real questions, hybrid hit@5 0.684 against
# 0.579 for FTS alone; the English-only all-MiniLM-L6-v2 dragged hybrid down to 0.395.
# TECHCOLAB_EMBED_MODEL overrides.
DEFAULT_MODEL = os.environ.get("TECHCOLAB_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
BATCH = 32
COMMIT_EVERY = 256  # chunks per commit while embedding, so a crash keeps its progress


class ModelUnavailable(RuntimeError):
    """The model files are not on disk and could not (or may not) be fetched."""


def models_dir(index_dir: Path | None = None) -> Path:
    return Path(index_dir or default_index_dir()) / "models"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ensure_model(name: str, index_dir: Path | None = None, *, download: bool = True) -> Path:
    """Return the model directory, downloading and hash-checking what is missing."""
    spec = MODELS.get(name)
    if spec is None:
        raise ModelUnavailable(f"modelo desconhecido: {name!r}; conhecidos: {', '.join(MODELS)}")
    d = models_dir(index_dir) / name
    d.mkdir(parents=True, exist_ok=True)
    for local, (remote, sha) in spec.files.items():
        p = d / local
        if not p.exists():
            if not download:
                raise ModelUnavailable(f"{p} ausente e download desligado; rode: python -m vaultindex embed --model {name}")
            tmp = p.with_name(p.name + ".part")
            try:
                urllib.request.urlretrieve(spec.base_url + remote, tmp)
            except Exception as e:  # network, proxy, 404: all the same to the caller
                tmp.unlink(missing_ok=True)
                raise ModelUnavailable(f"download falhou: {spec.base_url + remote}: {e}") from e
            os.replace(tmp, p)
        got = _sha256(p)
        if got != sha:
            p.unlink(missing_ok=True)
            raise ModelUnavailable(
                f"sha256 de {name}/{local} não bate ({got[:12]}… esperado {sha[:12]}…); arquivo removido, rode de novo"
            )
    return d


def chunk_text_for_embedding(title: str, heading: str | None, text: str) -> str:
    """What the model sees for a chunk: the note title and section heading give the
    vector context that a 900-character slice alone does not carry."""
    return "\n".join(p for p in (title, heading or "", text) if p)


class Embedder:
    """ONNX runtime session + tokenizer for one model. Build once, encode many."""

    def __init__(self, name: str | None = None, index_dir: Path | None = None, *, download: bool = True):
        import onnxruntime as ort  # heavy imports stay out of the FTS-only path
        from tokenizers import Tokenizer

        self.name = name or DEFAULT_MODEL
        spec = MODELS.get(self.name)
        if spec is None:
            raise ModelUnavailable(f"modelo desconhecido: {self.name!r}; conhecidos: {', '.join(MODELS)}")
        d = ensure_model(self.name, index_dir, download=download)
        self.dim = spec.dim
        self.max_len = spec.max_len
        self.tok = Tokenizer.from_file(str(d / "tokenizer.json"))
        preset = self.tok.padding
        self.pad_id = preset.get("pad_id") if preset else None
        if self.pad_id is None:
            self.pad_id = next(
                (self.tok.token_to_id(t) for t in ("[PAD]", "<pad>") if self.tok.token_to_id(t) is not None), 0
            )
        self.tok.no_padding()
        self.tok.enable_truncation(spec.max_len)
        so = ort.SessionOptions()
        so.log_severity_level = 3
        self.session = ort.InferenceSession(str(d / "model.onnx"), sess_options=so, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.session.get_inputs()}

    def encode(self, texts: list[str], batch_size: int = BATCH) -> np.ndarray:
        """L2-normalised mean-pooled embeddings, shape (len(texts), dim), float32."""
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encs = self.tok.encode_batch(batch)
            width = max((len(e.ids) for e in encs), default=1) or 1
            ids = np.full((len(batch), width), self.pad_id, dtype=np.int64)
            mask = np.zeros((len(batch), width), dtype=np.int64)
            for i, e in enumerate(encs):
                n = len(e.ids)
                ids[i, :n] = e.ids
                mask[i, :n] = 1
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(None, feed)[0]  # (b, width, dim)
            m = mask[:, :, None].astype(np.float32)
            pooled = (hidden * m).sum(axis=1) / np.maximum(m.sum(axis=1), 1e-9)
            pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
            out[start : start + len(batch)] = pooled.astype(np.float32)
        return out


_CACHE: dict[tuple[str, str], Embedder] = {}


def get_embedder(name: str | None = None, index_dir: Path | None = None, *, download: bool = True) -> Embedder:
    key = (name or DEFAULT_MODEL, str(index_dir or ""))
    if key not in _CACHE:
        _CACHE[key] = Embedder(name, index_dir, download=download)
    return _CACHE[key]


def load_vectors(con, model: str) -> tuple[np.ndarray, np.ndarray]:
    """All vectors for `model` as (chunk_ids int64[n], matrix float32[n, dim])."""
    rows = con.execute("SELECT chunk_id, dim, vec FROM embeddings WHERE model = ? ORDER BY chunk_id", (model,)).fetchall()
    if not rows:
        return np.zeros(0, dtype=np.int64), np.zeros((0, 0), dtype=np.float32)
    dim = rows[0]["dim"]
    ids = np.fromiter((r["chunk_id"] for r in rows), dtype=np.int64, count=len(rows))
    mat = np.frombuffer(b"".join(r["vec"] for r in rows), dtype=np.float32).reshape(len(rows), dim)
    return ids, mat


def embed_missing(
    con,
    model: str,
    *,
    embedder=None,
    index_dir: Path | None = None,
    batch_size: int = BATCH,
    progress=None,
    activate: bool = True,
) -> int:
    """Embed every chunk with no vector for `model`. The caller holds the writer lock.

    Commits every COMMIT_EVERY chunks. When done (and `activate`), records the model as the
    one `search` uses. Returns how many chunks were embedded.
    """
    emb = embedder or get_embedder(model, index_dir)
    rows = con.execute(
        """SELECT c.id, c.title, c.heading, c.text FROM chunks c
           LEFT JOIN embeddings e ON e.chunk_id = c.id AND e.model = ?
           WHERE e.chunk_id IS NULL ORDER BY c.id""",
        (model,),
    ).fetchall()
    done = 0
    for start in range(0, len(rows), COMMIT_EVERY):
        part = rows[start : start + COMMIT_EVERY]
        vecs = emb.encode([chunk_text_for_embedding(r["title"], r["heading"], r["text"]) for r in part], batch_size)
        con.executemany(
            "INSERT OR REPLACE INTO embeddings (chunk_id, model, dim, vec) VALUES (?, ?, ?, ?)",
            [(r["id"], model, int(vecs.shape[1]), vecs[i].tobytes()) for i, r in enumerate(part)],
        )
        con.commit()
        done += len(part)
        if progress:
            progress(done, len(rows))
    if activate:
        con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('embedding_model', ?)", (model,))
        con.commit()
    return done
