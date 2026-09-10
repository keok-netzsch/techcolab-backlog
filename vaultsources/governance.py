"""vaultsources/governance.py — a fronteira entre o que sai da máquina e o que não sai.

O ADR 2026-08-29 (`doc-triad-e-producao`) diz: produção é local-por-design ou
SharePoint, **nunca free tier externo** para dado NETZSCH. O corolário do padrão 4
(revisto 2026-09-02) abre o gateway NETZSCH para dado de pessoa em `oneonone`,
`manager` e `agenda`, e mantém local `note`, `capture` e `transcript`.

O braço de pesquisa quebra essa regra em um ponto específico e só nele:
`/research-deep` varre o vault e manda o contexto para a Perplexity. Buscar dado
público de fora é seguro; **mandar texto do vault para fora não é**. A distinção
que este módulo impõe não é o destino, é a ORIGEM do payload.

    origem "public"     -> texto que já era público antes de chegar aqui
    origem "user"       -> texto que o Kelvin digitou nesta conversa
    origem "vault"      -> qualquer coisa lida de um arquivo do vault

Provedor externo (xAI/Grok, Perplexity) aceita "public" e "user". Recusa "vault",
sempre, sem flag de contorno — o mesmo formato do allowlist por `purpose` de
`call-recorder/coach_llm.py`, que é forçado no código e não por variável de
ambiente (padrão 4).
"""

from __future__ import annotations


class EgressDenied(RuntimeError):
    """Payload do vault tentando sair para provedor externo."""


# Provedor -> origens de payload que ele aceita.
# Ordem importa para a leitura: quanto mais à direita, mais permissivo.
PROVIDERS: dict[str, frozenset[str]] = {
    # Fora da NETZSCH, sem contrato, logado pelo dono do serviço.
    "xai": frozenset({"public", "user"}),
    "perplexity": frozenset({"public", "user"}),
    # Gateway NETZSCH: infra da empresa, logada pelo empregador. Só isso pode
    # receber texto do vault, e ainda assim por `purpose` no allowlist do coach.
    "netzsch-gateway": frozenset({"public", "user", "vault"}),
    # Nada sai da máquina.
    "local": frozenset({"public", "user", "vault"}),
}

ORIGINS = frozenset({"public", "user", "vault"})

# Propósitos conhecidos deste pacote e o provedor que cada um usa.
# Um propósito novo entra aqui, no código, nunca por env var.
PURPOSES: dict[str, str] = {
    "transcript-fetch": "local",      # legenda pública do YouTube
    "media-download": "local",        # yt-dlp baixando áudio público
    "media-transcribe": "local",      # faster-whisper na máquina
    "feed-poll": "local",             # RSS público de canal/playlist
    "web-fetch": "local",             # baixar uma página pública
    "source-summarize": "local",      # o resumo é feito pelo Claude da sessão
    "research-web": "perplexity",     # pergunta aberta -> web, sem contexto do vault
    "x-read": "xai",                  # post público do X
    "x-pulse": "xai",                 # tendências públicas do X
}


def check_egress(purpose: str, origin: str) -> None:
    """Levanta EgressDenied se este payload não pode ir a este provedor.

    Chamado antes de qualquer request de rede que carregue texto nosso.
    """
    if origin not in ORIGINS:
        raise ValueError(f"origem desconhecida: {origin!r} (use {sorted(ORIGINS)})")
    provider = PURPOSES.get(purpose)
    if provider is None:
        raise EgressDenied(
            f"purpose {purpose!r} não está no allowlist de vaultsources.governance.PURPOSES. "
            "Adicione no código, com o provedor explícito, ou não faça a chamada."
        )
    allowed = PROVIDERS[provider]
    if origin not in allowed:
        raise EgressDenied(
            f"purpose {purpose!r} usa o provedor {provider!r}, que aceita {sorted(allowed)} "
            f"e recebeu payload de origem {origin!r}.\n"
            "ADR 2026-08-29: dado NETZSCH não vai para free tier externo. "
            "Se a pergunta precisa do contexto do vault, rode pelo gateway NETZSCH "
            "ou reescreva a pergunta sem o contexto."
        )


def provider_of(purpose: str) -> str:
    """Provedor declarado para um propósito. KeyError se não declarado."""
    return PURPOSES[purpose]


def is_local(purpose: str) -> bool:
    return PURPOSES.get(purpose) == "local"
