"""Diafonia tem que ser MEDIDA, nao inferida de "os dois canais estao ocupados".

Custo que gerou este arquivo (2026-09-04): o gate anterior decidia por
`Kelvin% + Interlocutor% > 120` e acusou 9 gravacoes. Remedidas contra o audio,
nenhuma tinha vazamento — correlacao entre canais de -0.26 a -0.15 nas acusadas e
de -0.07 a -0.01 nas limpas, faixas que se sobrepoem. Entre elas as 6 de 17 que
ficaram no registro como "contaminadas" desde 28/08, e uma Avaliacao GPTW de 42
min marcada como `grave` no mesmo dia.

O estrago de um gate assim nao e o ruido: e o Kelvin desconfiar de gravacao boa.
A frase que ele produzia era "atribuicao de falante nao e confiavel".

Estes testes sintetizam o sinal em vez de depender de audio real, porque `.wav` de
gravacao e apagado em 7 dias e teste nao pode depender de arquivo que some.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

CR = Path(__file__).parent.parent / "call-recorder"
if str(CR) not in sys.path:
    sys.path.insert(0, str(CR))

import crosstalk  # noqa: E402
import transcript_quality as tq  # noqa: E402

RATE = 16000


SEEDS = (7, 3, 21, 42)


def _trecho(dur_s, rng, ativo, piso=0.03, ambiente=0.0):
    """Fala com envelope, sempre sobre um piso de ruido que existe nos dois canais."""
    n = int(RATE * dur_s)
    base = rng.normal(0, piso, n)
    if ambiente:
        base = base + rng.normal(0, ambiente, n)
    if not ativo:
        return base
    env = np.abs(np.sin(np.linspace(0, dur_s * 6, n))) + 0.2
    return rng.normal(0, 1.0, n) * env + base


def conversa(turnos=200, dur=1.5, seed=7, p_pausa=0.35, p_overlap=0.12,
             p_ambiente=0.0):
    """Conversa alternada COM pausas e sobreposicao, que e o que existe de verdade.

    Duas correcoes que este gerador levou antes de servir para calibrar, e as duas
    valem como registro:

    1. **Sem pausas dava -0.81.** A primeira versao alternava perfeitamente — um
       fala, o outro cala, sempre. Nenhuma das 16 gravacoes reais chega perto:
       a faixa real e -0.26 a -0.01. Os trechos em que os DOIS calam sao o que
       puxa a correlacao para cima, e um limiar validado contra -0.81 aprovaria
       numero que nao funciona no audio de verdade.
    2. **40 turnos tinham variancia demais.** A correlacao efetiva e por TURNO,
       nao por janela de 50 ms, entao 40 turnos sao 40 amostras e a mesma
       configuracao ia de -0.22 a +0.18 conforme a seed. Com 200 turnos a faixa
       limpa fecha em -0.11 a +0.12, comparavel a real.

    `p_ambiente` liga ruido de fundo em parte dos trechos do canal 0: e o mic
    aberto. O ruido e por TRECHO, nao por amostra — ruido constante levanta o
    proprio piso do detector e o canal volta a marcar 0% de atividade, que nao e
    o que o audio real mostra.
    """
    rng = np.random.default_rng(seed)
    ch0, ch1 = [], []
    for i in range(turnos):
        r = rng.random()
        if r < p_pausa:
            k, o = False, False
        elif r < p_pausa + p_overlap:
            k, o = True, True
        else:
            k, o = (i % 2 == 0), (i % 2 != 0)
        amb = 0.5 if (p_ambiente and rng.random() < p_ambiente) else 0.0
        ch0.append(_trecho(dur, rng, k, ambiente=amb))
        ch1.append(_trecho(dur, rng, o))
    return np.concatenate(ch0), np.concatenate(ch1)


def mic_quente(seed=7):
    """Mic aberto: canal 0 ocupado o tempo todo, sem nada do outro dentro."""
    return conversa(seed=seed, p_ambiente=0.7)


# ── O sinal existe e tem direcao ─────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_conversa_alternada_nao_acusa(seed):
    a, b = conversa(seed=seed)
    m = crosstalk.medir_arrays(a, b, RATE)
    assert crosstalk.veredito(m["corr"]) == ""


@pytest.mark.parametrize("seed", SEEDS)
def test_vazamento_forte_acusa_grave(seed):
    a, b = conversa(seed=seed)
    m = crosstalk.medir_arrays(a + 0.8 * b, b, RATE)
    assert crosstalk.veredito(m["corr"]) == "grave"


def test_correlacao_sobe_monotonicamente_com_o_vazamento():
    """A propriedade que faz do numero um detector, e nao uma coincidencia."""
    a, b = conversa()
    corrs = [crosstalk.medir_arrays(a + g * b, b, RATE)["corr"]
             for g in (0.0, 0.2, 0.4, 0.6, 0.8)]
    assert corrs == sorted(corrs)
    assert corrs[0] < 0 < corrs[-1]


def test_mic_quente_sem_vazamento_nao_acusa():
    """O falso positivo que derrubou o criterio antigo.

    Canal do Kelvin quente (mic aberto, ambiente com ruido) e o outro falando
    normalmente. A soma dos dois passa de 120%; diafonia, zero. Foi exatamente o
    que aconteceu em 04/09 com 3 gravacoes, entre elas uma Avaliacao GPTW de 42
    min marcada como `grave`.
    """
    a, b = mic_quente()
    m = crosstalk.medir_arrays(a, b, RATE)
    assert m["ch0_pct"] + m["ch1_pct"] > 120     # o criterio velho acusaria
    assert crosstalk.veredito(m["corr"]) == ""   # o novo nao


@pytest.mark.parametrize("seed", SEEDS)
def test_vazamento_e_detectado_mesmo_com_mic_quente(seed):
    """O que o criterio novo nao pode perder: mic quente E vazando de verdade.

    E o caso dificil. O lift praticamente nao se move aqui — por isso quem decide
    e a correlacao.
    """
    a, b = mic_quente(seed=seed)
    m = crosstalk.medir_arrays(a + 0.8 * b, b, RATE)
    assert crosstalk.veredito(m["corr"]) == "grave"


def test_lift_se_move_menos_que_a_correlacao_com_mic_quente():
    """Justifica a escolha de correlacao em vez de lift.

    Medido no audio real de 04/09: com o mic quente, injetar ganho 0.8 levou o
    lift de 0.76 a 1.20 (+0.44) enquanto a correlacao foi de -0.17 a +0.94
    (+1.11). Um detector que mal se move na gravacao problematica nao serve para
    decidir.
    """
    a, b = mic_quente()
    limpo = crosstalk.medir_arrays(a, b, RATE)
    vazando = crosstalk.medir_arrays(a + 0.8 * b, b, RATE)
    assert vazando["corr"] - limpo["corr"] > vazando["lift"] - limpo["lift"]


# ── Bordas: nada disso pode virar acusacao ───────────────────────────────────

def test_canal_constante_nao_acusa():
    n = RATE * 3
    m = crosstalk.medir_arrays(np.zeros(n), np.ones(n), RATE)
    assert crosstalk.veredito(m["corr"]) == ""


def test_audio_curto_demais_nao_acusa():
    m = crosstalk.medir_arrays(np.zeros(10), np.zeros(10), RATE)
    assert m["corr"] is None
    assert crosstalk.veredito(m["corr"]) == ""


def test_corr_ausente_nunca_acusa():
    assert crosstalk.veredito(None) == ""


# ── O gate le a medida, e nao acusa o que nao mediu ──────────────────────────

def _sidecar(tmp_path, stem, corr=None, k=50.0, i=50.0, classified=False):
    j = {"wav": f"{stem}.wav", "duration_s": 1800,
         "channel_profile": {"Kelvin": {"active_pct": k, "dynamic_db": 40.0},
                             "Interlocutor": {"active_pct": i, "dynamic_db": 40.0}}}
    if corr is not None:
        j["crosstalk"] = {"corr": corr, "lift": 1.0, "ch0_pct": k,
                          "ch1_pct": i, "win_ms": 50}
    nome = f"{stem}.pending.json" + (".classified" if classified else "")
    (tmp_path / nome).write_text(json.dumps(j), encoding="utf-8")


def test_gate_acusa_quando_a_medida_acusa(tmp_path):
    _sidecar(tmp_path, "2026-09-05_09-00_auto", corr=0.55)
    nivel, corr, det = tq.contaminacao_de_canal("2026-09-05_09-00_auto", rdir=tmp_path)
    assert nivel == "grave"
    assert corr == 0.55
    assert "canal do Kelvin" in det


def test_gate_nao_acusa_soma_alta_sem_diafonia(tmp_path):
    """O caso de 04/09: soma 146%, correlacao -0.17."""
    _sidecar(tmp_path, "2026-09-04_11-02_auto", corr=-0.17, k=75.6, i=70.4)
    nivel, _corr, det = tq.contaminacao_de_canal("2026-09-04_11-02_auto", rdir=tmp_path)
    assert nivel == ""
    assert "sem diafonia" in det


def test_gravacao_antiga_diz_nao_medido_em_vez_de_herdar_veredito(tmp_path):
    """Sidecar sem o campo nao pode virar 'grave' pelo criterio aposentado."""
    _sidecar(tmp_path, "2026-08-28_11-46_auto", corr=None, k=66.9, i=66.5)
    nivel, corr, det = tq.contaminacao_de_canal("2026-08-28_11-46_auto", rdir=tmp_path)
    assert nivel == ""
    assert corr is None
    assert "nao medida" in det


def test_canal_mudo_nao_vira_relato_de_diafonia(tmp_path):
    """Meia conversa deixa a correlacao indefinida, e isso tem nome proprio.

    Sem esta distincao o gate dizia "gravacao anterior a 2026-09-04" para uma
    gravacao de hoje com um canal morto, mandando procurar o problema errado.
    `canal_mudo` e quem reporta esse caso.
    """
    j = {"wav": "x.wav", "duration_s": 600,
         "channel_profile": {"Kelvin": {"active_pct": 30.0, "dynamic_db": 40.0},
                             "Interlocutor": {"active_pct": 0.0, "dynamic_db": 0.0}},
         "crosstalk": {"corr": None, "lift": None, "ch0_pct": 30.0,
                       "ch1_pct": 0.0, "win_ms": 50}}
    (tmp_path / "2026-09-04_09-34_auto.pending.json").write_text(
        json.dumps(j), encoding="utf-8")
    nivel, _corr, det = tq.contaminacao_de_canal("2026-09-04_09-34_auto", rdir=tmp_path)
    assert nivel == ""
    assert "nao mensuravel" in det
    assert tq.canal_mudo("2026-09-04_09-34_auto", rdir=tmp_path)[0] is True


def test_gate_segue_o_sidecar_depois_do_classify(tmp_path):
    _sidecar(tmp_path, "2026-09-05_10-00_auto", corr=0.42, classified=True)
    assert tq.contaminacao_de_canal("2026-09-05_10-00_auto", rdir=tmp_path)[0] == "grave"


def test_sem_sidecar_nao_acusa(tmp_path):
    assert tq.contaminacao_de_canal("2026-01-01_00-00_auto", rdir=tmp_path)[0] == ""


def test_sidecar_ilegivel_nao_derruba(tmp_path):
    (tmp_path / "2026-09-05_11-00_auto.pending.json").write_text("{ truncado",
                                                                 encoding="utf-8")
    assert tq.contaminacao_de_canal("2026-09-05_11-00_auto", rdir=tmp_path)[0] == ""


# ── Backfill ─────────────────────────────────────────────────────────────────

def test_backfill_preenche_sidecar_a_partir_do_wav(tmp_path):
    import wave
    a, b = conversa(turnos=6)
    stem = "2026-09-04_12-00_auto"
    with wave.open(str(tmp_path / f"{stem}.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE)
        n = min(len(a), len(b))
        pcm = np.stack([a[:n], b[:n]], axis=1)
        pcm = (pcm / max(np.abs(pcm).max(), 1e-9) * 20000).astype(np.int16)
        w.writeframes(pcm.tobytes())
    _sidecar(tmp_path, stem, corr=None)

    assert crosstalk.backfill(rdir=tmp_path, log=lambda _m: None) == 1
    j = json.loads((tmp_path / f"{stem}.pending.json").read_text(encoding="utf-8"))
    assert j["crosstalk"]["corr"] is not None
    assert tq.contaminacao_de_canal(stem, rdir=tmp_path)[0] == ""


def test_backfill_nao_remede_o_que_ja_tem(tmp_path):
    _sidecar(tmp_path, "2026-09-04_13-00_auto", corr=-0.1)
    (tmp_path / "2026-09-04_13-00_auto.wav").write_bytes(b"")
    assert crosstalk.backfill(rdir=tmp_path, log=lambda _m: None) == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
