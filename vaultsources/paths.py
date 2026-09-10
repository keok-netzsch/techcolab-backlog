"""vaultsources/paths.py — onde cada coisa mora, e nada mais.

Sem fallback de conveniência: caminho de dado com default silencioso já produziu
uma leitura que mentia com exit code 0 (ver o docstring de config.py, 2026-09-01).
Aqui todo caminho deriva de config.VAULT_BASE, que estoura no import se
TECHCOLAB_VAULT não estiver setada.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from config import VAULT_BASE  # noqa: E402

VAULT = Path(VAULT_BASE)

# Camada nova: fonte externa e conceito.
SOURCES_DIR = VAULT / "Sources"
CONCEPTS_DIR = VAULT / "Concepts"

# Estado do cano. Um escritor por arquivo: o CLI de vaultsources.
WATCHLIST = SOURCES_DIR / "_watchlist.json"
QUEUE = SOURCES_DIR / "_queue.json"

# Área de contradição: a fonte propõe, ninguém aplica sozinho (padrão 3).
PROPOSALS_DIR = CONCEPTS_DIR / "_proposals"
REJECTED_DIR = CONCEPTS_DIR / "_rejected"

# Saídas geradas (refeitas do zero, nunca editadas à mão).
REPORTS_DIR = VAULT / "_reports"
QA_REPORT = REPORTS_DIR / "Sources-QA.md"

# Cache de mídia baixada. Fora do OneDrive e fora do vault: é lixo reproduzível
# e áudio de vídeo não precisa sincronizar.
def media_cache() -> Path:
    """Cache de midia e de texto bruto. Fora do vault, fora do OneDrive.

    Guarda na FONTE, nao so na fixture (padrao 10 do ARCHITECTURE.md): sob pytest,
    apontar para o cache real deixa lixo na maquina do Kelvin e, pior, um teste
    passa a enxergar o arquivo que outro escreveu. Foi assim que o teste do sidecar
    quebrou: outro teste tinha gravado um cache com o mesmo slug.
    """
    import os
    if os.environ.get("PYTEST_CURRENT_TEST"):
        import tempfile
        return Path(tempfile.gettempdir()) / "vaultsources-test-cache"
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "techcolab" if base else Path.home() / ".local" / "share" / "techcolab"
    return root / "sources-media"


def ensure_dirs() -> None:
    for d in (SOURCES_DIR, CONCEPTS_DIR, PROPOSALS_DIR, REJECTED_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
