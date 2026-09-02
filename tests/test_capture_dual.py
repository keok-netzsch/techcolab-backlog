"""Testes do caminho de captura em 2 canais.

Este caminho nunca teve teste, e em 2026-08-27 uma call de 50 minutos foi
perdida por isso: o microfone falhou ao abrir, `capture_dual` devolveu None
porque um canal veio vazio, e o autocapture descartou TAMBEM o canal do
loopback, que estava intacto.

Os testes abaixo travam o contrato que faltava:
  - falha de um canal nunca descarta o outro;
  - so devolve None quando nao ha absolutamente nada;
  - os canais saem alinhados;
  - a guarda de densidade da transcricao aceita 1:1 saudavel e recusa
    transcricao degenerada.

Nenhum teste toca hardware: `sounddevice` e `soundcard` sao substituidos por
dublês, entao isto roda em CI e numa maquina sem placa de audio.
"""
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))
import record  # noqa: E402

# ── Dublês ────────────────────────────────────────────────────────────────────

class _FakeStream:
    """InputStream do sounddevice. `frames` None simula falha ao abrir."""

    def __init__(self, buf, frames, callback):
        self._buf, self._frames, self._cb = buf, frames, callback

    def __enter__(self):
        if self._frames is None:
            raise RuntimeError("Error opening InputStream: Device unavailable")
        self._cb(self._frames, len(self._frames), None, None)
        return self

    def __exit__(self, *a):
        return False


class _FakeRecorder:
    def __init__(self, frames):
        self._frames = frames

    def __enter__(self):
        if self._frames is None:
            raise RuntimeError("loopback endpoint sumiu")
        return self

    def __exit__(self, *a):
        return False

    def record(self, numframes):
        out, self._frames = self._frames, np.zeros((0, 1), dtype="float32")
        return out


def _install_fakes(monkeypatch, mic_frames, sys_frames, tmp_path=None):
    """Injeta sounddevice/soundcard falsos e para a captura na 1a passada.

    `tmp_path` redireciona o spool (que usa soundfile REAL) para fora do
    diretorio de producao — sem isso cada rodada de teste deixaria
    `_spool_ch*.wav` em call-recorder/recordings/."""
    if tmp_path is not None:
        monkeypatch.setattr(record, "SPOOL_DIR", str(tmp_path))
    sd = types.ModuleType("sounddevice")
    sd.default = types.SimpleNamespace(device=(1, 4))
    sd.query_devices = lambda i=None: {"name": "Mic de Teste"}
    sd.sleep = lambda ms: None

    def InputStream(callback=None, **kw):
        return _FakeStream(None, mic_frames, callback)

    sd.InputStream = InputStream
    sd.rec = lambda *a, **k: np.zeros((10, 1), dtype="float32")
    sd.wait = lambda: None

    sc = types.ModuleType("soundcard")
    speaker = types.SimpleNamespace(name="Alto-falante de Teste")
    sc.default_speaker = lambda: speaker
    sc.get_microphone = lambda name, include_loopback=False: types.SimpleNamespace(
        recorder=lambda samplerate, channels: _FakeRecorder(sys_frames))

    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.setitem(sys.modules, "soundcard", sc)
    monkeypatch.setattr(record, "_log", lambda *a, **k: None)


def _tone(seconds=1.0):
    n = int(record.SAMPLE_RATE * seconds)
    return np.ones((n, 1), dtype="float32") * 0.1


def _stop_after(n_iteracoes=1):
    """stop_flag que deixa o laco rodar n vezes antes de mandar parar.

    Um stop_flag sempre-verdadeiro faria o laco do loopback nunca executar, e o
    teste passaria a medir o dublê em vez do codigo.
    """
    estado = {"n": 0}

    def flag():
        estado["n"] += 1
        return estado["n"] > n_iteracoes

    return flag


# ── capture_dual ──────────────────────────────────────────────────────────────

def test_dois_canais_ok_devolve_ambos(monkeypatch, tmp_path):
    _install_fakes(monkeypatch, _tone(), _tone(), tmp_path)
    mic, sysa = record.capture_dual(_stop_after(2))
    assert len(mic) > 0 and len(sysa) > 0
    assert len(mic) == len(sysa), "os canais precisam sair alinhados"


def test_microfone_falha_mas_loopback_e_salvo(monkeypatch, tmp_path):
    """A regressao de 2026-08-27: 50 min de loopback jogados fora."""
    _install_fakes(monkeypatch, None, _tone(2.0), tmp_path)
    result = record.capture_dual(_stop_after(2))
    assert result is not None, "nunca descartar tudo porque o mic falhou"
    mic, sysa = result
    assert len(sysa) == int(record.SAMPLE_RATE * 2)
    assert len(mic) == len(sysa)
    assert not np.any(mic), "canal do mic deve vir zerado, nao ausente"


def test_loopback_falha_mas_microfone_e_salvo(monkeypatch, tmp_path):
    _install_fakes(monkeypatch, _tone(2.0), None, tmp_path)
    result = record.capture_dual(_stop_after(2))
    assert result is not None, "nunca descartar tudo porque o loopback falhou"
    mic, sysa = result
    assert len(mic) == int(record.SAMPLE_RATE * 2)
    assert len(mic) == len(sysa)
    assert not np.any(sysa)


def test_so_devolve_none_quando_nao_ha_nada(monkeypatch, tmp_path):
    _install_fakes(monkeypatch, None, None, tmp_path)
    assert record.capture_dual(_stop_after(2)) is None


def test_sem_soundcard_grava_mic_only(monkeypatch, tmp_path):
    """Sem a lib de loopback o gravador degrada para mic-only, nao perde a call.

    O contrato antigo retornava None aqui — ANTES de capturar qualquer coisa —
    e o autocapture nao tem fallback proprio: a call inteira era perdida com o
    microfone funcionando. Mesmo furo em loopback indisponivel.
    """
    _install_fakes(monkeypatch, _tone(2.0), _tone(), tmp_path)

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, *a, **k):
        if name == "soundcard":
            raise ImportError("nao instalado")
        return real_import(name, *a, **k)

    monkeypatch.setattr("builtins.__import__", fake_import)
    result = record.capture_dual(_stop_after(2))
    assert result is not None, "sem soundcard o mic ainda tem que ser gravado"
    mic, sysa = result
    assert len(mic) == int(record.SAMPLE_RATE * 2)
    assert len(mic) == len(sysa) and not np.any(sysa)


def test_capture_system_audio_desligado_grava_mic_only(monkeypatch, tmp_path):
    """CAPTURE_SYSTEM_AUDIO=0 vale para todos os chamadores, incluindo autocapture."""
    _install_fakes(monkeypatch, _tone(2.0), _tone(), tmp_path)
    monkeypatch.setattr(record, "CAPTURE_SYSTEM_AUDIO", False)
    result = record.capture_dual(_stop_after(2))
    assert result is not None
    mic, sysa = result
    assert len(mic) == int(record.SAMPLE_RATE * 2) and not np.any(sysa)


def test_transcribe_nao_quebra_com_container_que_soundfile_nao_le(monkeypatch, tmp_path):
    """Fix do File Processing: sf.info explode em mp4/mov; transcribe segue single-channel.

    Regressao real: o dispatch de 2 canais chamava sf.info sem guarda, entao
    `record.py --input reuniao.mp4` (idea-031) morria antes do Whisper.
    """
    class _Seg:
        start, text = 0.0, "conteudo transcrito"

    class _FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, path, **kw):
            return [_Seg()], types.SimpleNamespace(language="pt", duration=10.0)

    fw = types.ModuleType("faster_whisper")
    fw.WhisperModel = _FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fw)

    sf = types.ModuleType("soundfile")

    def _boom(path):
        raise RuntimeError("Format not recognised")

    sf.info = _boom
    monkeypatch.setitem(sys.modules, "soundfile", sf)

    fake = tmp_path / "reuniao.mp4"
    fake.write_bytes(b"\x00")
    text, lang = record.transcribe(str(fake), language="pt")
    assert "conteudo transcrito" in text and lang == "pt"


# ── guarda de densidade da transcricao ────────────────────────────────────────

def _linhas(qtd_palavras, minutos):
    """Gera linhas no formato do transcript com o total de palavras pedido."""
    por_linha = 10
    n = max(1, qtd_palavras // por_linha)
    return [f"[{i * (minutos * 60 / n):05.1f}s] " + " ".join(["palavra"] * por_linha)
            for i in range(n)]


def test_guarda_aceita_transcricao_saudavel():
    # 1:1s reais nesta maquina: 79-160 palavras/min.
    record._sanity_check(_linhas(qtd_palavras=900, minutos=10), 600)


def test_guarda_recusa_transcricao_degenerada():
    # O caso real: 66 palavras em 43,7 min de audio (1,5/min).
    linhas = [f"[{i * 5:05.1f}s] ." for i in range(500)]
    with pytest.raises(record.TranscriptionTooSparse):
        record._sanity_check(linhas, 43.7 * 60)


def test_guarda_ignora_gravacao_curta():
    """Clipe curto e ruidoso demais para julgar — nao pode falhar por isso."""
    record._sanity_check([f"[{0:05.1f}s] ."], 60)


# ── spool: seguro anti-crash ──────────────────────────────────────────────────

def test_spool_persiste_audio_em_disco_durante_captura(monkeypatch, tmp_path):
    """O audio precisa existir em disco ao fim da captura, nao so em RAM.

    Antes do spool, crash/reboot no meio da call perdia tudo — o .wav so era
    escrito no final. O spool e a prova de que a captura fluiu para disco.
    """
    import os

    import soundfile as sf
    _install_fakes(monkeypatch, _tone(2.0), _tone(2.0), tmp_path)
    mic, sysa = record.capture_dual(_stop_after(2))
    ch0 = record.spool_path(0)
    assert os.path.exists(ch0), "spool do canal 0 nao foi escrito"
    data, sr = sf.read(ch0, dtype="float32")
    assert sr == record.SAMPLE_RATE
    assert len(data) == len(mic), "spool e retorno divergem"
    record.cleanup_spools()
    assert not os.path.exists(ch0), "cleanup_spools nao removeu o spool"


def test_resgate_de_spool_orfao_vira_gravacao(monkeypatch, tmp_path):
    """Spool frio de processo morto vira wav + pending.json no startup."""
    import sys as _sys
    if _sys.platform != "win32":
        pytest.skip("autocapture usa winreg")
    import os
    import time as _time

    import autocapture
    import soundfile as sf

    monkeypatch.setattr(autocapture, "RECORDINGS", tmp_path)
    monkeypatch.setattr(autocapture, "MIN_SECONDS", 1)
    monkeypatch.setattr(autocapture, "log", lambda *a, **k: None)

    dead_pid = 99999999
    tone = np.ones(int(record.SAMPLE_RATE * 2), dtype="float32") * 0.1
    for ch in (0, 1):
        p = tmp_path / f"_spool_ch{ch}.{dead_pid}.wav"
        sf.write(str(p), tone, record.SAMPLE_RATE, subtype="PCM_16")
        old = _time.time() - 120                    # frio: processo morto
        os.utime(p, (old, old))

    autocapture._rescue_spools()

    wavs = list(tmp_path.glob("*_auto-recovered.wav"))
    pend = list(tmp_path.glob("*_auto-recovered.pending.json"))
    assert len(wavs) == 1 and len(pend) == 1, "resgate nao produziu wav+pending"
    data, _ = sf.read(str(wavs[0]), dtype="float32")
    assert data.shape[1] == 2 and len(data) == len(tone)
    assert not list(tmp_path.glob("_spool_*")), "spools resgatados devem sumir"


def test_resgate_ignora_spool_quente(monkeypatch, tmp_path):
    """Spool com mtime recente = captura viva; resgatar seria roubar a call em curso."""
    import sys as _sys
    if _sys.platform != "win32":
        pytest.skip("autocapture usa winreg")
    import autocapture
    import soundfile as sf

    monkeypatch.setattr(autocapture, "RECORDINGS", tmp_path)
    monkeypatch.setattr(autocapture, "MIN_SECONDS", 1)
    monkeypatch.setattr(autocapture, "log", lambda *a, **k: None)

    tone = np.ones(int(record.SAMPLE_RATE * 2), dtype="float32") * 0.1
    p = tmp_path / "_spool_ch0.12345.wav"
    sf.write(str(p), tone, record.SAMPLE_RATE, subtype="PCM_16")  # mtime = agora

    autocapture._rescue_spools()
    assert p.exists(), "spool quente nao pode ser tocado"
    assert not list(tmp_path.glob("*_auto-recovered*"))


def test_loopback_inicializa_com_na_propria_thread(monkeypatch, tmp_path):
    """COM e por thread: sem CoInitializeEx a thread do loopback morre com
    0x800401f0 (CO_E_NOTINITIALIZED) ao abrir o recorder.

    Bug latente desde a criacao da captura dupla — funcionava quando COM ja
    havia sido inicializado por acaso naquela thread. Em 2026-08-27 esvaziou o
    canal 1 de uma call de 33 min.
    """
    import ctypes
    _install_fakes(monkeypatch, _tone(1.0), _tone(1.0), tmp_path)

    chamadas = {"init": 0, "uninit": 0}
    real_ole32 = ctypes.windll.ole32

    class _Ole32Spy:
        def CoInitializeEx(self, *a):
            chamadas["init"] += 1
            return real_ole32.CoInitializeEx(*a)

        def CoUninitialize(self):
            chamadas["uninit"] += 1
            return real_ole32.CoUninitialize()

    class _WinDLLSpy:
        ole32 = _Ole32Spy()

        def __getattr__(self, name):
            return getattr(ctypes.windll, name)

    monkeypatch.setattr(ctypes, "windll", _WinDLLSpy())
    record.capture_dual(_stop_after(2))
    assert chamadas["init"] == 1, "loopback tem que inicializar COM na sua thread"
    assert chamadas["uninit"] == 1, "COM inicializado tem que ser liberado"


# ── Regressao: o vad_filter que faltava no caminho de 2 canais ────────────────
#
# Em 26/08 uma call degenerou em 98% de "." e a correcao foi ligar vad_filter.
# Ela foi aplicada so no ramo de 1 canal. Como a captura 2.0 e SEMPRE de 2
# canais, a correcao nunca rodou em call nenhuma: em 27-28/08, 23 dos 26 canais
# degeneraram, e tres calls sairam num idioma que ninguem falou (nn, nl, sv).
# A do OKR 05 saiu com a fala do Kelvin em russo e foi parar com uma colega.

class _FakeSeg:
    def __init__(self, start, text):
        self.start, self.text = start, text


class _FakeInfo:
    def __init__(self, language):
        self.language = language


class _FakeModel:
    """Grava os kwargs de cada chamada para o teste inspecionar."""

    def __init__(self, por_canal):
        self.por_canal, self.chamadas = por_canal, []

    def transcribe(self, track, **kw):
        self.chamadas.append(kw)
        segs, lang = self.por_canal[len(self.chamadas) - 1]
        return iter([_FakeSeg(s, t) for s, t in segs]), _FakeInfo(lang)


def _stereo_curto(monkeypatch, sr=16000, segundos=2):
    """Audio de 2 canais audiveis e curto demais para o _sanity_check julgar."""
    import soundfile as sf
    data = np.full((sr * segundos, 2), 0.1, dtype=np.float32)
    monkeypatch.setattr(sf, "read", lambda *a, **k: (data, sr))


def test_dual_usa_vad_filter_em_todos_os_canais(monkeypatch):
    _stereo_curto(monkeypatch)
    model = _FakeModel([([(0.0, "ola")], "pt"), ([(1.0, "hello")], "pt")])

    record._transcribe_dual(model, "qualquer.wav", None)

    assert len(model.chamadas) == 2, "os dois canais tem que ser transcritos"
    for i, kw in enumerate(model.chamadas):
        assert kw.get("vad_filter") is True, (
            f"canal {i} sem vad_filter: sem ele um canal que abre em silencio "
            f"leva o decoder a um laco que dura o resto da call"
        )


def test_idioma_vem_do_canal_que_mais_falou_nao_do_canal_zero(monkeypatch):
    """O mic do Kelvin (canal 0) abre mudo com frequencia.

    Deixar o canal 0 decidir sozinho foi como a call do OKR 05 acabou marcada
    'nn' (nynorsk) no vault: a deteccao rodou em cima de 15 min de silencio.
    """
    _stereo_curto(monkeypatch)
    model = _FakeModel([
        ([(0.0, "hm")], "nn"),                                  # canal 0: 1 palavra
        ([(1.0, "this is the actual conversation")], "en"),      # canal 1: 5 palavras
    ])

    _, detected = record._transcribe_dual(model, "qualquer.wav", None)

    assert detected == "en", (
        "o idioma da call e o do canal que mais falou; um canal quase vazio "
        "nao pode carimbar o idioma da call inteira"
    )
