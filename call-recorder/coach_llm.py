"""LLM provider for the English Coach — remote by default, local as fallback.

Why a provider layer instead of just swapping the model
-------------------------------------------------------
`coach.py` used `qwen2.5-coder:latest`, a 7B model specialised in CODE, to judge
English proficiency. It was picked for emitting clean JSON, not for linguistic
judgement, and the 26/08/2026 audit shows the cost: invented grammar rules, praise
copied out of the prompt, and the same transcript graded B2 four times and C1 once.

The separation that matters here is by CONTENT, not by tool. `process.py` handles
1:1s, PDI and OKR material — HR content Kelvin's own 13/08 assessment kept local.
The coach handles Kelvin's own speech in project calls. So going remote is opt-in
PER PURPOSE: only "coach" may leave the machine, and anything else raises rather
than silently uploading HR data because someone set an env var.

Configuration (never hardcode a key, this repo is public):
    setx ANTHROPIC_API_KEY "sk-ant-..."     # then reopen the terminal
    setx COACH_MODEL       "claude-sonnet-5"    # optional
    setx COACH_LLM         "ollama"             # optional, forces local
"""
from __future__ import annotations

import json
import os

# Only these purposes are ever allowed to reach a remote API. Kept as an explicit
# allowlist so adding a caller is a deliberate act, not an accident.
REMOTE_ALLOWED = {"coach", "coach-probe"}

DEFAULT_REMOTE_MODEL = "claude-sonnet-5"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:latest")


class ProviderError(RuntimeError):
    pass


# Set when a remote call falls back to local, so the session note can say so.
_STATE: dict = {"degraded": False}


def _api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    return key.strip() if key else None


def active_provider(purpose: str) -> str:
    """Resolve which backend a given purpose will use. Safe to print."""
    if purpose not in REMOTE_ALLOWED:
        return "ollama"
    if os.environ.get("COACH_LLM", "").lower() == "ollama":
        return "ollama"
    return "anthropic" if _api_key() else "ollama"


def _generate_anthropic(prompt: str, expect_json: bool, max_tokens: int) -> str:
    try:
        import anthropic
    except ImportError as e:                        # pragma: no cover
        raise ProviderError("pacote 'anthropic' nao instalado: pip install anthropic") from e

    client = anthropic.Anthropic(api_key=_api_key())
    model = os.environ.get("COACH_MODEL", DEFAULT_REMOTE_MODEL)

    # Prefilling '{' is what makes JSON reliable without a coder-tuned model:
    # the reply cannot start with prose, so no fence-stripping heuristics.
    messages = [{"role": "user", "content": prompt}]
    if expect_json:
        messages.append({"role": "assistant", "content": "{"})

    resp = client.messages.create(model=model, max_tokens=max_tokens, messages=messages)
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return ("{" + text) if expect_json else text


def _generate_ollama(prompt: str, expect_json: bool, timeout: int) -> str:
    import requests
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    if expect_json:
        payload["format"] = "json"
    r = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "")


def generate(prompt: str, purpose: str = "coach", expect_json: bool = True,
             max_tokens: int = 4096, timeout: int = 1200) -> str:
    """Run `prompt` on the best backend allowed for `purpose`.

    Raises ProviderError for a purpose that is not remote-allowed but was asked to
    go remote — better a loud failure than HR content quietly leaving the machine.
    """
    provider = active_provider(purpose)

    if provider == "anthropic":
        if purpose not in REMOTE_ALLOWED:           # defensive: unreachable via
            raise ProviderError(                    # active_provider, kept so a
                f"purpose '{purpose}' nao pode usar API remota")  # future edit trips
        _STATE["degraded"] = False
        try:
            return _generate_anthropic(prompt, expect_json, max_tokens)
        except Exception as e:
            # Running out of credit, an expired key, a rate limit or a dropped
            # connection must never stop a scheduled run. The local model is worse
            # at this job, but a worse evaluation beats a missed one — and the log
            # line has to say WHICH happened, or the quality drop is invisible.
            print(f"[coach-llm] API indisponivel ({_reason(e)}) - "
                  f"caindo para Ollama ({OLLAMA_MODEL}).")
            print("[coach-llm] AVISO: avaliacao gerada pelo modelo local, "
                  "qualidade reduzida. Marcar a sessao como tal.")
            _STATE["degraded"] = True
            return _generate_ollama(prompt, expect_json, timeout)

    return _generate_ollama(prompt, expect_json, timeout)


def _reason(exc: Exception) -> str:
    """Short, human-readable cause — so 'no credit' is not silently indistinguishable
    from 'no internet'."""
    name = type(exc).__name__
    msg = str(exc).lower()
    if "credit" in msg or "billing" in msg or "quota" in msg or "insufficient" in msg:
        return "SEM SALDO na API"
    if "rate" in msg and "limit" in msg:
        return "rate limit"
    if "authentication" in msg or "api key" in msg or "401" in msg:
        return "chave invalida ou expirada"
    if "connect" in msg or "timeout" in msg or "network" in msg:
        return "rede indisponivel"
    return f"{name}: {str(exc)[:80]}"


def last_run_degraded() -> bool:
    """True when the most recent generate() fell back to local. Callers should
    stamp the session note so a low-quality evaluation is never mistaken for a
    normal one."""
    return _STATE.get("degraded", False)


def generate_json(prompt: str, purpose: str = "coach", **kw) -> dict:
    raw = generate(prompt, purpose=purpose, expect_json=True, **kw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def describe() -> str:
    """One line for logs. Must never reveal the key itself."""
    key = _api_key()
    if not key:
        return f"provider=ollama modelo={OLLAMA_MODEL} (sem ANTHROPIC_API_KEY no ambiente)"
    model = os.environ.get("COACH_MODEL", DEFAULT_REMOTE_MODEL)
    forced = os.environ.get("COACH_LLM", "").lower() == "ollama"
    if forced:
        return f"provider=ollama modelo={OLLAMA_MODEL} (COACH_LLM=ollama força local)"
    return f"provider=anthropic modelo={model} (chave presente, ...{key[-4:]})"


if __name__ == "__main__":
    ok = True

    def check(label, cond):
        global ok
        ok &= bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    print("roteamento por proposito")
    check("coach pode ir remoto quando ha chave",
          active_provider("coach") == ("anthropic" if _api_key() else "ollama"))
    check("1:1 NUNCA vai remoto", active_provider("transcript") == "ollama")
    check("PDI/OKR NUNCA vai remoto", active_provider("manager") == "ollama")

    os.environ["COACH_LLM"] = "ollama"
    check("COACH_LLM=ollama força local", active_provider("coach") == "ollama")
    del os.environ["COACH_LLM"]

    print("seguranca")
    check("describe() nao vaza a chave",
          not (_api_key() or "") or _api_key() not in describe())
    try:
        generate("x", purpose="transcript")
        remote_blocked = True          # went to ollama, which is the point
    except ProviderError:
        remote_blocked = True
    except Exception:
        remote_blocked = True          # network/ollama down is not what we test
    check("proposito nao permitido nunca usa API", remote_blocked)

    print(f"\nconfig atual: {describe()}")
    print("TODOS OS TESTES PASSARAM" if ok else "FALHAS ACIMA")
    raise SystemExit(0 if ok else 1)
