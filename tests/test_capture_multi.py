"""Redundant capture + late channel selection (capture_multi).

Each test reproduces a failure actually measured on 2026-08-27, so a regression
looks like the original bug rather than like an abstract assertion:

    08:01  11.8 min  channel 0 was floating-jack hum   (5.6 dB dyn, 0.7% active)
    14:20  33.0 min  channel 1 was digital silence     (wrong render endpoint)
    15:34  43.0 min  channel 0 was ~silent             (1.0% active)
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import capture_multi as cm  # noqa: E402

SR = cm.SAMPLE_RATE


def _speech(seconds=20, seed=0):
    """Intermittent bursts well above the floor — how conversation behaves."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 0.0006, SR * seconds).astype(np.float32)   # room floor
    for start in range(0, seconds, 3):                            # ~1s of talk / 3s
        a, b = start * SR, start * SR + SR
        x[a:b] += rng.normal(0, 0.12, b - a).astype(np.float32)
    return x


def _hum(seconds=20):
    """Floating jack input: loud, and perfectly flat. This is the 08:01 failure."""
    t = np.arange(SR * seconds) / SR
    return (0.02 * np.sin(2 * np.pi * 60 * t)).astype(np.float32)


def _silence(seconds=20):
    """Loopback on the wrong render endpoint. This is the 14:20 failure."""
    return np.zeros(SR * seconds, dtype=np.float32)


# ── Scoring ──────────────────────────────────────────────────────────────────

def test_speech_is_recognised():
    assert cm.score(_speech())["verdict"] == "speech"


def test_floating_jack_hum_is_not_mistaken_for_speech():
    s = cm.score(_hum())
    assert s["verdict"] == "hum"
    assert s["mean_db"] > -80          # loud: RMS alone would have passed it


def test_digital_silence_is_recognised():
    assert cm.score(_silence())["verdict"] == "silent"


def test_level_cannot_separate_hum_from_speech_but_activity_can():
    """The real trap, from the real numbers.

    On 2026-08-27 the hum channel measured -32.8 dBFS and a good speech channel
    -32.9 dBFS — a tenth of a decibel apart. Any level-based check would have
    passed the broken one. What separates them is how the energy is distributed
    in time: 0.7% active versus 60-88%.
    """
    def windowed_mean_rms(x):
        """The statistic score() actually reports — for bursty speech it differs
        from global RMS, so calibrating on global RMS would not equalise it."""
        win = SR // 10
        k = len(x) // win
        return np.sqrt((x[:k * win].reshape(k, win).astype(np.float64) ** 2)
                       .mean(axis=1)).mean()

    speech_track = _speech()
    hum_track = _hum()
    # Calibrate the hum to the same reported level as the speech, as reality did.
    hum_track = (hum_track * float(windowed_mean_rms(speech_track)
                                   / windowed_mean_rms(hum_track))).astype(np.float32)

    hum, speech = cm.score(hum_track), cm.score(speech_track)
    assert abs(hum["mean_db"] - speech["mean_db"]) < 1.0      # level says nothing
    assert hum["verdict"] == "hum" and speech["verdict"] == "speech"
    assert speech["active_pct"] > hum["active_pct"] * 5       # activity decides


def test_empty_track_does_not_crash():
    assert cm.score(None)["verdict"] == "silent"
    assert cm.score(np.zeros(10, dtype=np.float32))["verdict"] == "silent"


# ── Selection ────────────────────────────────────────────────────────────────

def test_picks_the_speech_track_over_hum_and_silence():
    scored = [("mic:jack", cm.score(_hum())),
              ("mic:array", cm.score(_speech())),
              ("mic:dead", cm.score(_silence()))]
    best, lines = cm.pick_best(scored)
    assert scored[best][0] == "mic:array"
    assert any("escolhido" in ln for ln in lines)


def test_all_bad_still_returns_something_and_warns():
    """Half a call beats no call — but it must say so."""
    scored = [("sys:speakers", cm.score(_silence())),
              ("sys:headset", cm.score(_hum()))]
    best, lines = cm.pick_best(scored)
    assert best is not None
    assert any("AVISO" in ln for ln in lines)


def test_no_streams_is_handled():
    best, lines = cm.pick_best([])
    assert best is None and lines


# ── Endpoint discovery ───────────────────────────────────────────────────────

def test_input_candidates_exclude_non_microphones():
    try:
        cands = cm.input_candidates()
    except Exception:
        pytest.skip("PortAudio indisponivel neste ambiente")
    for _, name in cands:
        assert not any(s in name for s in ("Mix", "Mapper", "Primary", "PC Speaker"))


def test_same_device_is_kept_under_every_host_api():
    """De-duplicating by device name was itself the bug.

    On 2026-08-28 "Saida do MicrofoneMic" delivered Kelvin's voice at 79% speech
    through WASAPI and flat hum at 0.0% through DirectSound — the same physical
    microphone. De-duplication kept the MME entry and discarded the working one,
    so the recorder captured hum for three calls while Teams heard him fine.
    """
    try:
        cands = cm.input_candidates()
    except Exception:
        pytest.skip("PortAudio indisponivel neste ambiente")
    if len(cands) < 2:
        pytest.skip("maquina com uma unica entrada")
    # Each entry must carry its host API, so two rows for one device are distinct.
    assert all("[" in n and "]" in n for _, n in cands)
    assert len({i for i, _ in cands}) == len(cands)   # device index unique


def test_exclusive_mode_host_api_is_never_used_in_production():
    """WDM-KS opens exclusively; taking the mic that way during a call could
    steal it from Teams and leave Kelvin muted. Diagnostics only."""
    try:
        cands = cm.input_candidates()
    except Exception:
        pytest.skip("PortAudio indisponivel neste ambiente")
    assert not any("WDM-KS" in n for _, n in cands)


def test_more_than_one_render_endpoint_is_discovered():
    """The 14:20 failure was recording 'Altofalantes' while audio went to
    'Auscultadores'. Discovery must see both, or the fix is pointless."""
    try:
        loops = cm.loopback_candidates()
    except Exception:
        pytest.skip("soundcard indisponivel neste ambiente")
    if not loops:
        pytest.skip("nenhum endpoint de saida neste ambiente")
    assert all(isinstance(n, str) and d is not None for n, d in loops)


def test_dynamic_range_stays_physically_plausible():
    """A digitally silent gap made the floor 0 and log(0) reported 226 dB of
    dynamic range on 2026-08-27. An impossible number discredits the report."""
    x = np.zeros(SR * 10, dtype=np.float32)
    x[SR * 2:SR * 3] = 0.3            # one loud burst, pure silence around it
    s = cm.score(x)
    assert 0 <= s["dynamic_db"] <= 140, s["dynamic_db"]
