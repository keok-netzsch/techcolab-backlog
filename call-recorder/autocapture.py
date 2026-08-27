"""autocapture.py — grava automaticamente enquanto o Teams estiver em call.

Sinal de deteccao: o Windows zera `LastUsedTimeStop` no ConsentStore do microfone
enquanto um app esta capturando, e grava um FILETIME quando ele solta. Isso e mais
confiavel que olhar processo (o Teams fica aberto o dia todo) e nao precisa de
biblioteca nativa nem admin.

Gravacao nao vira job automaticamente: sai um `<base>.pending.json` ao lado do
`.wav`. Classificar (quem / que tipo) e um passo separado — `classify.py` — para
que a captura nunca dependa de uma decisao tomada na hora de entrar na call.

Desligar: crie o arquivo `autocapture.paused` nesta pasta. Enquanto ele existir,
nada e gravado.
"""
import json
import os
import sys
import threading
import time
import winreg
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import record  # noqa: E402  (capture_dual + SAMPLE_RATE)

HERE = Path(__file__).parent
RECORDINGS = HERE / "recordings"
PAUSE_FILE = HERE / "autocapture.paused"
LOG_FILE = HERE / "autocapture.log"

TEAMS_KEY = (r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager"
             r"\ConsentStore\microphone\MSTeams_8wekyb3d8bbwe")

POLL_SECONDS = 3
MIN_SECONDS = 120     # sub-2-minute blips are mic tests and dropped calls, not meetings
SETTLE_POLLS = 2      # consecutive idle reads before stopping, so a brief mute/unmute
                      # or device switch mid-call does not split one call into two files


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    # File first, and console only if there is one: under pythonw.exe sys.stdout
    # is None, so printing raises and would otherwise kill the watcher silently.
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    if sys.stdout is not None:
        try:
            print(line, flush=True)
        except (OSError, ValueError, AttributeError):
            pass


def teams_mic_active() -> bool:
    """True while Teams holds the microphone (LastUsedTimeStop == 0)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, TEAMS_KEY) as k:
            return winreg.QueryValueEx(k, "LastUsedTimeStop")[0] == 0
    except FileNotFoundError:
        return False          # Teams never used the mic on this profile
    except OSError as e:
        log(f"[WARN] leitura do registro falhou: {e}")
        return False


def teams_window_title() -> str:
    """Best-effort meeting name, so classification later has a hint to work from."""
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return ""

    user32 = ctypes.windll.user32
    titles = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            t = buf.value
            if "Teams" in t or "Reuni" in t or "Meeting" in t:
                titles.append(t)
        return True

    try:
        user32.EnumWindows(each, 0)
    except Exception:
        return ""
    # The call window is usually the more specific one; prefer the longest title.
    return max(titles, key=len) if titles else ""


def record_call() -> None:
    """Capture until Teams releases the mic, then persist wav + pending sidecar."""
    import numpy as np
    import soundfile as sf

    started = datetime.now()
    title = teams_window_title()
    log(f"call detectada -> gravando  {('| ' + title) if title else ''}")

    idle_streak = 0
    stop = threading.Event()

    def watch():
        nonlocal idle_streak
        while not stop.is_set():
            if teams_mic_active():
                idle_streak = 0
            else:
                idle_streak += 1
                if idle_streak >= SETTLE_POLLS:
                    stop.set()
                    return
            time.sleep(POLL_SECONDS)

    threading.Thread(target=watch, daemon=True).start()
    dual = record.capture_dual(stop.is_set)
    stop.set()

    if dual is None:
        log("[WARN] captura falhou - nada gravado.")
        return

    mic, sysa = dual
    seconds = len(mic) / record.SAMPLE_RATE
    if seconds < MIN_SECONDS:
        log(f"descartado: {seconds:.0f}s (< {MIN_SECONDS}s)")
        return

    RECORDINGS.mkdir(exist_ok=True)
    base = f"{started:%Y-%m-%d_%H-%M}_auto"
    wav = RECORDINGS / f"{base}.wav"
    sf.write(wav, np.concatenate([mic, sysa], axis=1), record.SAMPLE_RATE)

    (RECORDINGS / f"{base}.pending.json").write_text(json.dumps({
        "wav": wav.name,
        "source": "autocapture",
        "started": started.isoformat(timespec="seconds"),
        "ended": datetime.now().isoformat(timespec="seconds"),
        "duration_s": round(seconds),
        "window_title": title,
        "channels": list(record.SPEAKER_LABELS),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"salvo: {wav.name}  ({seconds/60:.1f} min) - aguardando classificacao")


def main() -> None:
    log(f"autocapture iniciado (poll {POLL_SECONDS}s, minimo {MIN_SECONDS}s)")
    log(f"para pausar, crie: {PAUSE_FILE}")
    was_active = False
    while True:
        try:
            if PAUSE_FILE.exists():
                if was_active:
                    log("pausado pelo usuario")
                was_active = False
                time.sleep(POLL_SECONDS)
                continue
            active = teams_mic_active()
            if active and not was_active:
                record_call()          # blocks for the whole call
                was_active = False
                continue
            was_active = active
        except Exception as e:
            log(f"[ERRO] {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
