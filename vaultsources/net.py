"""vaultsources/net.py — sair da rede da NETZSCH sem desligar a verificacao de TLS.

A rede corporativa faz inspecao de TLS: o certificado que chega no Python foi
emitido pela CA interna, e nem o `certifi` nem o `yt-dlp` conhecem essa CA. O
sintoma e `CERTIFICATE_VERIFY_FAILED` em tudo que sai daqui.

A saida preguicosa seria `--no-check-certificates` e `verify=False`. Isso nao
entra: desligar verificacao para resolver um erro de confianca troca um problema
visivel por um invisivel, e o mesmo atalho ja existe neste repo em
`record.py` (`HF_HUB_DISABLE_SSL_VERIFY=1`), onde ninguem lembra mais por que.

O que fazemos: exportar as CAs raiz da maquina (que incluem a CA interna),
concatenar com o bundle do certifi e apontar `SSL_CERT_FILE` para o resultado.
O `yt-dlp` ignora `SSL_CERT_FILE` por padrao porque prefere o certifi dele, entao
ele recebe `--compat-options no-certifi`, que o faz usar o contexto padrao do
Python — e ai o `SSL_CERT_FILE` vale.

Rebuild: `pwsh scripts/build-ca-bundle.ps1` (ou `vaultsources qa --fix-ca`).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BUNDLE_ENV = "TECHCOLAB_CA_BUNDLE"
PROBE_URL = "https://www.youtube.com/robots.txt"


class CABundleMissing(RuntimeError):
    pass


def bundle_path() -> Path:
    override = os.environ.get(BUNDLE_ENV, "").strip()
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "techcolab" if base else Path.home() / ".local" / "share" / "techcolab"
    return root / "ca-bundle.pem"


def build_script() -> Path:
    return Path(__file__).resolve().parent.parent / "scripts" / "build-ca-bundle.ps1"


def build(force: bool = False) -> Path:
    """(Re)gera o bundle chamando o script PowerShell. Idempotente."""
    target = bundle_path()
    if target.exists() and not force:
        return target
    script = build_script()
    if not script.exists():
        raise CABundleMissing("script de build ausente: %s" % script)
    exe = "pwsh" if _has("pwsh") else "powershell"
    proc = subprocess.run([exe, "-NoProfile", "-ExecutionPolicy", "Bypass",
                           "-File", str(script), "-Out", str(target)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)
    if proc.returncode != 0 or not target.exists():
        raise CABundleMissing("build-ca-bundle.ps1 falhou: %s"
                              % ((proc.stderr or proc.stdout or "").strip()[:400]))
    return target


def _has(exe: str) -> bool:
    import shutil
    return shutil.which(exe) is not None


def apply(strict: bool = True) -> Path | None:
    """Aponta as variaveis de TLS deste processo para o bundle.

    Chamado uma vez no inicio do CLI. Com `strict=False` nao estoura quando o
    bundle nao existe — util em maquina fora da rede corporativa, onde o certifi
    padrao ja basta.
    """
    target = bundle_path()
    if not target.exists():
        if strict:
            raise CABundleMissing(
                "CA bundle nao encontrado em %s.\n"
                "A rede da NETZSCH inspeciona TLS, entao sem ele toda busca externa "
                "morre com CERTIFICATE_VERIFY_FAILED.\n"
                "Gere com: pwsh -File %s" % (target, build_script())
            )
        return None
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        os.environ[var] = str(target)
    return target


def ytdlp_argv(extra: list[str] | None = None) -> list[str]:
    """argv para chamar o yt-dlp do proprio interpretador, com o bundle valendo.

    Modulo do Python, nao o .EXE: o executavel congelado carrega o certifi
    embutido e ignora `SSL_CERT_FILE`, entao o bundle nao teria efeito nenhum.
    """
    argv = [sys.executable, "-m", "yt_dlp", "--compat-options", "no-certifi"]
    return argv + list(extra or [])


def probe(timeout: int = 20) -> tuple[bool, str]:
    """Confere que uma requisicao real passa. E o que o QA chama."""
    try:
        import requests
        r = requests.get(PROBE_URL, timeout=timeout)
        return (r.status_code < 500, "HTTP %s" % r.status_code)
    except Exception as exc:
        return (False, "%s: %s" % (type(exc).__name__, str(exc)[:200]))
