"""Zumbido de rede: o filtro tira, e tira nos dois lugares certos.

Contexto (2026-09-03). O microfone que o Kelvin usa entrega ~-24 dBFS constantes
de zumbido de 60/120 Hz — um microfone parado fica entre -60 e -45. O zumbido
fica 11 dB acima da banda da voz, entao `active_pct` da ~0% e o gravador escolhe
o array do notebook, que pontua melhor por acaso e nao e onde ele fala.

Medido na tomada e na bateria com numeros iguais (-24.0 vs -22.6 dBFS, picos
identicos), o que descarta a alimentacao da maquina.

O que estes testes travam nao e o filtro em si, e a FORMA da correcao:

1. O filtro remove 60/120 Hz e preserva a banda da voz.
2. A ESCOLHA do microfone usa o sinal filtrado; o RELATORIO usa o sinal como
   gravado. Trocar os dois faria `canal_mudo` e `contaminacao_de_canal` medirem
   um audio que nao existe em disco.
3. O loopback nao passa pelo filtro. Ele nunca teve o problema (piso -68.9 dBFS)
   e cortar 250 Hz da voz do outro seria estragar o canal que sempre funcionou.
4. Falha do filtro nunca derruba a captura nem a fila da noite.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

CR = Path(__file__).parent.parent / "call-recorder"
if str(CR) not in sys.path:
    sys.path.insert(0, str(CR))

import capture_multi as cm  # noqa: E402

SR = 16000


def _hum(segundos=4.0, nivel=0.05, sr=SR):
    """Zumbido de rede: 60 Hz + 120 Hz, como o medido no dispositivo real."""
    t = np.arange(int(segundos * sr)) / sr
    return (nivel * np.sin(2 * np.pi * 60 * t)
            + nivel * 1.4 * np.sin(2 * np.pi * 120 * t)).astype(np.float32)


def _voz(segundos=4.0, nivel=0.05, sr=SR):
    """Fala sintetica: harmonicos em 400/800/1600 Hz, com pausas.

    Pausa importa: `score` mede quanto tempo o sinal fica acima do proprio piso,
    entao um tom continuo pontua como zumbido por mais limpo que seja.
    """
    t = np.arange(int(segundos * sr)) / sr
    s = sum(nivel / (i + 1) * np.sin(2 * np.pi * f * t)
            for i, f in enumerate((400, 800, 1600)))
    env = (np.sin(2 * np.pi * 1.5 * t) > 0).astype(np.float64)   # liga/desliga
    return (s * env).astype(np.float32)


def _banda_db(x, lo, hi, sr=SR):
    esp = np.abs(np.fft.rfft(x.astype(np.float64) * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    m = (f >= lo) & (f < hi)
    return 20 * np.log10(max(float(esp[m].mean()), 1e-12))


# ── 1. O filtro faz o que diz ────────────────────────────────────────────────

def test_remove_a_banda_do_zumbido():
    x = _hum() + _voz()
    y = cm.dehum(x, SR)
    antes = _banda_db(x, 40, 200)
    depois = _banda_db(y, 40, 200)
    assert depois < antes - 12, f"zumbido caiu so {antes - depois:.1f} dB"


def test_preserva_a_banda_da_voz():
    x = _hum() + _voz()
    y = cm.dehum(x, SR)
    assert _banda_db(y, 400, 3000) > _banda_db(x, 400, 3000) - 3


def test_vira_o_veredito_de_hum_para_speech():
    """O efeito que importa: o stream deixa de ser descartado como zumbido.

    Proporcao de niveis tirada da medicao real, nao escolhida para o teste
    passar: no dispositivo do Kelvin o zumbido esta ~11 dB acima da banda da
    voz. Com a voz MUITO mais baixa que isso o filtro nao salva nada, e o teste
    abaixo documenta esse limite.
    """
    x = _hum(nivel=0.08) + _voz(nivel=0.05)
    assert cm.score(np.ascontiguousarray(x), SR)["verdict"] == "hum"
    assert cm.score(np.ascontiguousarray(cm.dehum(x, SR)), SR)["verdict"] == "speech"


def test_filtro_nao_inventa_fala_que_nao_existe():
    """O limite honesto: voz enterrada 12 dB abaixo do zumbido continua perdida.

    Vale como guarda contra "melhorar" o filtro ate ele produzir speech a partir
    de ruido — que daria ao Whisper exatamente o material de que ele precisa
    para alucinar.
    """
    x = _hum(nivel=0.08) + _voz(nivel=0.02)
    assert cm.score(np.ascontiguousarray(cm.dehum(x, SR)), SR)["verdict"] == "hum"


def test_nao_altera_a_entrada():
    x = _hum() + _voz()
    antes = x.copy()
    cm.dehum(x, SR)
    assert np.array_equal(x, antes)


def test_entrada_degenerada_nao_estoura():
    for ruim in (np.zeros(3, dtype="float32"), np.zeros(0, dtype="float32"),
                 np.array([0.1], dtype="float32")):
        assert cm.dehum(ruim, SR) is not None
    assert cm.dehum(_voz(), SR, cutoff=0) is not None
    assert cm.dehum(_voz(), SR, cutoff=SR) is not None      # acima de Nyquist


def test_sem_degrau_no_inicio():
    """Zero-padding criaria um degrau, e degrau o Whisper decodifica como fala."""
    y = cm.dehum(_hum() + _voz(), SR)
    assert abs(float(y[:80].max())) < 5 * float(np.abs(y[SR:2 * SR]).mean()) + 0.01


def test_custo_aceitavel_numa_call_longa():
    """115 min e o tamanho real da call da Ana. A fila da noite ja gasta horas."""
    import time
    x = (_hum() + _voz())
    longo = np.tile(x, 200)              # ~13 min
    t0 = time.time()
    cm.dehum(longo, SR)
    assert time.time() - t0 < 5.0


# ── 2. Relatorio do original, escolha do filtrado ────────────────────────────

def _s(verdict, din, fala):
    return {"verdict": verdict, "dynamic_db": din, "active_pct": fala, "mean_db": -30.0}


def test_escolha_usa_o_filtrado():
    """O array pontua melhor cru; o mic dele so ganha depois do filtro."""
    i, _ = cm.pick_best([
        ("mic:array-do-notebook", _s("hum", 11.3, 3.7), _s("hum", 11.9, 4.4)),
        ("mic:onde-ele-fala", _s("hum", 7.9, 0.8), _s("speech", 17.6, 15.0)),
    ])
    assert i == 1


def test_relatorio_mostra_o_sinal_como_gravado():
    _, linhas = cm.pick_best([("mic:x", _s("hum", 11.3, 3.7), _s("speech", 17.6, 15.0))])
    texto = "\n".join(linhas)
    assert "11.3" in texto and "3.7" in texto      # o que esta no .wav
    assert "sem zumbido" in texto and "17.6" in texto


def test_forma_de_2_continua_valendo():
    """Loopback nunca passa pelo filtro e chega aqui como (label, score)."""
    i, linhas = cm.pick_best([("sys:Auscultadores", _s("speech", 51.1, 43.8))])
    assert i == 0
    assert "sem zumbido" not in "\n".join(linhas)


def test_aviso_de_menos_ruim_sobrevive():
    _, linhas = cm.pick_best([
        ("mic:a", _s("hum", 5.0, 0.5), _s("hum", 6.0, 0.9)),
        ("mic:b", _s("hum", 4.0, 0.2), _s("hum", 4.5, 0.3)),
    ])
    assert any("menos ruim" in ln for ln in linhas)


# ── 3. O loopback fica de fora ───────────────────────────────────────────────

def test_transcricao_filtra_o_mic_e_nao_o_loopback(tmp_path, monkeypatch):
    import record
    import soundfile as sf

    ruidoso = _hum(nivel=0.08) + _voz(nivel=0.02)
    limpo = _voz(nivel=0.05)
    wav = tmp_path / "call.wav"
    sf.write(wav, np.stack([ruidoso, limpo], axis=1), SR)

    vistos = []

    class ModeloFalso:
        def transcribe(self, track, **kw):
            vistos.append(np.asarray(track).copy())
            class Info:
                language = "pt"
            return iter(()), Info()

    record._transcribe_dual(ModeloFalso(), str(wav), None)
    assert len(vistos) == 2

    # canal 0 chegou filtrado, canal 1 chegou intacto
    assert _banda_db(vistos[0], 40, 200) < _banda_db(ruidoso, 40, 200) - 10
    # atol frouxo de proposito: o .wav e PCM16 e quantiza em ~3e-5.
    assert np.allclose(vistos[1], limpo, atol=1e-4)


def test_filtro_quebrado_nao_derruba_a_transcricao(tmp_path, monkeypatch):
    """A fila da noite nao pode morrer por causa do filtro."""
    import capture_multi
    import record
    import soundfile as sf

    wav = tmp_path / "call.wav"
    sf.write(wav, np.stack([_voz(), _voz()], axis=1), SR)

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(capture_multi, "dehum", explode)

    class ModeloFalso:
        def transcribe(self, track, **kw):
            class Info:
                language = "pt"
            return iter(()), Info()

    record._transcribe_dual(ModeloFalso(), str(wav), None)   # nao levanta


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
