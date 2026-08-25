"""
agent/agent_io.py — console I/O hardening for the scheduled agent entrypoints.

Why this exists
---------------
`run_agent.bat` redirects stdout to `logs\agent-last.log`. When stdout is a
redirected pipe (and not a console), Python picks the legacy Windows ANSI code
page — cp1252 on this machine — instead of UTF-8. Any `print()` carrying a
character cp1252 cannot represent (an arrow, an emoji, a box-drawing rule)
then raises `UnicodeEncodeError` *inside* whatever code was printing.

That is exactly how Phase 2 of the daily agent silently died: the worker
finished its Ollama analysis, tried to log `-> {icon} {decision}`, blew up on
U+2192, and the surrounding `except Exception` threw the finished analysis
away and reported a generic "Worker error".

Two layers of defence, so no future non-ASCII output can repeat this:

1. `force_utf8_stdio()` — reconfigure stdout/stderr to UTF-8 at import time of
   each entrypoint. This is the real fix; it makes the whole log UTF-8.
2. `safe_print()` — a `print()` that degrades to escapes instead of raising,
   for the case where stdout cannot be reconfigured at all (a wrapped stream
   under a test harness, a stream someone else owns). Logging must never be
   able to destroy the work it is describing.

`run_agent.bat` additionally sets `PYTHONIOENCODING=utf-8`, which covers any
child process this agent spawns (pytest, git, the call-recorder pipeline).
"""

import sys

__all__ = ["force_utf8_stdio", "safe_print"]


def force_utf8_stdio() -> None:
    """
    Reconfigure stdout/stderr to UTF-8 with `errors="replace"`.

    Idempotent and never raises: a stream that cannot be reconfigured (already
    detached, replaced by a non-TextIOWrapper capture object, closed) is left
    as-is and `safe_print` remains the fallback.
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, AttributeError):
            # Detached, closed, or a stream that refuses reconfiguration.
            pass


def safe_print(*args, sep: str = " ", end: str = "\n", file=None, flush: bool = False) -> None:
    """
    `print()` that cannot raise `UnicodeEncodeError`.

    On an encoding failure the whole line is re-encoded with
    `backslashreplace`, so the message still lands in the log (with the
    offending characters escaped) instead of taking down the caller.
    """
    stream = file if file is not None else sys.stdout
    text = sep.join(str(a) for a in args) + end
    try:
        stream.write(text)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        stream.write(text.encode(encoding, "backslashreplace").decode(encoding, "replace"))
    if flush:
        try:
            stream.flush()
        except (ValueError, OSError):
            pass
