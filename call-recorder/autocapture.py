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


def _rescue_spools() -> None:
    """Turn spool files left by a dead process into a normal recording.

    The spool is the crash insurance: capture streams to disk every 200ms, so
    if the machine rebooted or the watcher was killed mid-call, the audio up to
    that moment is sitting in `_spool_ch*.<pid>.wav`. Only COLD spools are
    taken (mtime older than 30s) — a live capture touches its spool constantly,
    which makes freshness a liveness check that survives PID reuse.
    """
    import re

    import numpy as np
    import soundfile as sf

    spools = sorted(RECORDINGS.glob("_spool_ch*.wav"))
    if not spools:
        return

    by_pid = {}
    for p in spools:
        m = re.match(r"_spool_ch([01])\.(\d+)\.wav$", p.name)
        if not m:
            continue
        if time.time() - p.stat().st_mtime < 30:
            continue                     # captura viva escrevendo agora
        by_pid.setdefault(m.group(2), {})[int(m.group(1))] = p

    for pid, chans in by_pid.items():
        tracks = []
        for ch in (0, 1):
            p = chans.get(ch)
            if p is None:
                tracks.append(None)
                continue
            try:
                d, _sr = sf.read(str(p), dtype="float32")
                tracks.append(d.reshape(-1, 1))
            except Exception as e:
                log(f"resgate: spool {p.name} ilegivel ({e})")
                tracks.append(None)

        n = max((len(t) for t in tracks if t is not None), default=0)
        seconds = n / record.SAMPLE_RATE
        stamp = None
        for p in chans.values():
            stamp = datetime.fromtimestamp(p.stat().st_mtime)
            break

        if seconds >= MIN_SECONDS:
            full = [t if t is not None and len(t) else np.zeros((n, 1), dtype="float32")
                    for t in tracks]
            full = [t[:n] if len(t) >= n else
                    np.vstack([t, np.zeros((n - len(t), 1), dtype="float32")])
                    for t in full]
            base = f"{stamp:%Y-%m-%d_%H-%M}_auto-recovered"
            wav = RECORDINGS / f"{base}.wav"
            sf.write(wav, np.concatenate(full, axis=1), record.SAMPLE_RATE)
            (RECORDINGS / f"{base}.pending.json").write_text(json.dumps({
                "wav": wav.name,
                "source": "spool-rescue",
                "ended": stamp.isoformat(timespec="seconds"),
                "duration_s": round(seconds),
                "window_title": "",
                "channels": list(record.SPEAKER_LABELS),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"resgate: {wav.name} ({seconds/60:.1f} min) recuperado de spool "
                f"de processo morto (pid {pid})")
        else:
            log(f"resgate: spool do pid {pid} com {seconds:.0f}s (< {MIN_SECONDS}s) - descartado")

        for p in chans.values():
            try:
                p.unlink()
            except OSError:
                pass


def record_call() -> None:
    """Capture until Teams releases the mic, then persist wav + pending sidecar."""
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
    try:
        dual = record.capture_dual(stop.is_set)
        stop.set()

        if dual is None:
            log("[WARN] captura falhou - nada gravado. Ver record.log para a causa.")
            return

        mic, sysa = dual
        seconds = len(mic) / record.SAMPLE_RATE
        if seconds < MIN_SECONDS:
            log(f"descartado: {seconds:.0f}s (< {MIN_SECONDS}s)")
            return
        _persist_call(started, title, mic, sysa, seconds)
    finally:
        # Spools ja cumpriram o papel (o wav final existe, ou a captura foi
        # descartada de proposito). Sem isto, o resgate do proximo startup
        # ressuscitaria uma call curta que foi descartada por decisao.
        record.cleanup_spools()


def _persist_call(started, title, mic, sysa, seconds) -> None:
    import numpy as np
    import soundfile as sf

    # Diagnostico por canal, gravado no log e no sidecar. Um canal plano pode
    # ser mute do usuario (legitimo) ou endpoint errado (bug), e depois do fato
    # nao da para distinguir sem isto. Fala tem faixa dinamica alta e e
    # intermitente; mute/chiado e continuo e plano.
    def _profile(track):
        win = record.SAMPLE_RATE // 2
        k = len(track) // win
        if k == 0:
            return {"active_pct": 0.0, "dynamic_db": 0.0}
        rms = np.sqrt((track[:k * win].reshape(k, win).astype(np.float64) ** 2).mean(axis=1))
        floor = float(np.percentile(rms, 10))
        peak = float(np.percentile(rms, 95))
        dyn = 20 * np.log10(peak + 1e-12) - 20 * np.log10(floor + 1e-12)
        active = float((rms > max(floor * 4, 10 ** (-60 / 20))).mean())
        return {"active_pct": round(100 * active, 1), "dynamic_db": round(dyn, 1)}

    prof = [_profile(mic[:, 0]), _profile(sysa[:, 0])]
    for idx, (label, pf) in enumerate(zip(record.SPEAKER_LABELS, prof, strict=True)):
        flag = "" if pf["active_pct"] >= 2 and pf["dynamic_db"] >= 6 else "  <-- SEM FALA"
        log(f"  canal {idx} ({label}): fala {pf['active_pct']}%, "
            f"dinamica {pf['dynamic_db']} dB{flag}")

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
        "channel_profile": {lab: pf for lab, pf in zip(record.SPEAKER_LABELS, prof, strict=True)},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"salvo: {wav.name}  ({seconds/60:.1f} min) - aguardando classificacao")
    _avisar_meia_conversa()


def _avisar_meia_conversa() -> None:
    """Caixa na tela quando a gravacao saiu com um lado so. Padrao 12.

    O sidecar acabou de ser escrito, entao a regra le do disco pelo mesmo caminho
    que o relatorio diario usa (`transcript_quality.canal_mudo`) — uma regra, nao
    duas. Aqui so decidimos QUANDO avisar; o QUE conta como meia conversa mora la.

    Nunca derruba o watcher: se o notify falhar, a gravacao ja esta salva e o
    alerta continua no log e no relatorio das 07:00. Perder o aviso e ruim;
    perder o autocapture por causa do aviso seria pior.
    """
    import subprocess

    try:
        import halfcall_notify
        achados = halfcall_notify.pendentes()
        if not achados:
            return
        notify = HERE.parent / "scripts" / "notify.ps1"
        if not notify.exists():
            log(f"[WARN] meia-conversa detectada mas notify.ps1 nao existe em {notify}")
            return
        # Marca ANTES de disparar, e de proposito. A caixa e `messagebox`, que
        # bloqueia ate ele clicar OK; esperar o subprocesso para so entao marcar
        # travaria o watcher no meio do dia. Marcar antes troca "perder um aviso
        # se a caixa falhar" por "repetir o aviso a cada call das proximas 24h".
        # A primeira falha e coberta pelo record.log e pelo relatorio das 07:00;
        # a segunda mata o lembrete, que e como este defeito sobreviveu 7 dias.
        halfcall_notify.marcar([s for s, _ in achados])
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(notify), "-Profile", "capture-half-call"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        log("[multi] meia-conversa: aviso disparado (perfil capture-half-call)")
    except Exception as e:
        log(f"[WARN] aviso de meia-conversa falhou: {e}")


def _acquire_single_instance():
    """Refuse to start if another watcher is already running.

    The task is registered "at logon", and a manual launch during debugging is
    the obvious way to end up with two. Two watchers means two capture_dual()
    calls fighting for the same microphone endpoint, and a call recorded twice
    or half in each file. A named mutex is the cheap Windows answer; the handle
    is returned so it stays alive for the process lifetime.
    """
    import ctypes

    k32 = ctypes.windll.kernel32
    handle = k32.CreateMutexW(None, False, "Local\\CallRecorderAutoCaptureSingleton")
    if k32.GetLastError() == 183:      # ERROR_ALREADY_EXISTS
        return None
    return handle


def main() -> None:
    _mutex = _acquire_single_instance()
    if _mutex is None:
        log("[ERRO] outra instancia do autocapture ja esta rodando - encerrando.")
        return

    log(f"autocapture iniciado (poll {POLL_SECONDS}s, minimo {MIN_SECONDS}s)")
    log(f"para pausar, crie: {PAUSE_FILE}")
    try:
        _rescue_spools()
    except Exception as e:
        log(f"[WARN] resgate de spools falhou: {e}")
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
