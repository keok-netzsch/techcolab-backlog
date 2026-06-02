"""
ingestion/extractor.py — Uses a local Ollama LLM to extract structured ideas from raw notes.

Each note may contain 0..N ideas. The model returns a JSON list.
Ollama exposes an OpenAI-compatible endpoint at http://localhost:11434/v1.
"""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from config import EXTRACTION_MODEL, OLLAMA_BASE_URL
from ingestion.parser import RawNote

_SYSTEM_PROMPT = """
Você é um assistente de gestão de produto e inovação.
Receberá o conteúdo bruto de uma nota de ideias e deverá extrair todas as ideias distintas presentes nela.

Para cada ideia, retorne um JSON com os seguintes campos:
- titulo: string curta e clara (máx. 60 chars)
- descricao: descrição objetiva da ideia (2-5 frases)
- area: categoria ou área de aplicação (ex: "dados", "automação", "produto", "processo", "infra")
- prioridade: "alta" | "média" | "baixa" (estime com base no impacto implícito)
- todos: lista de strings — próximos passos ou ações necessárias para avançar com a ideia

Retorne APENAS um array JSON válido, sem markdown, sem explicações, sem texto extra.
Exemplo de saída (conteúdo fictício, apenas para ilustrar o formato):
[
  {
    "titulo": "Automatizar envio de relatório mensal",
    "descricao": "Substituir o processo manual de copiar e colar dados no relatório mensal por um script que gera e envia o arquivo automaticamente.",
    "area": "automação",
    "prioridade": "média",
    "todos": [
      "Mapear os dados de origem do relatório",
      "Criar script de geração do arquivo",
      "Configurar envio automático por e-mail"
    ]
  }
]

Se a nota não contiver nenhuma ideia acionável (ex: é apenas um rascunho sem sentido, lista de compras, etc.), retorne [].
""".strip()


def _parse_json_array(raw_text: str, source: str) -> list[dict[str, Any]]:
    """
    Extract the first valid JSON array from raw_text.
    Handles extra text before/after the array and truncated responses by
    progressively trimming the tail until the JSON parses.
    """
    start = raw_text.find("[")
    if start == -1:
        raise ValueError(f"No JSON array found in model output for '{source}'.\nRaw: {raw_text[:300]}")

    candidate = raw_text[start:]

    # Try as-is first
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Truncated response: walk back from the last complete object
    # Find the last complete '}' followed eventually by ']'
    end = candidate.rfind("}")
    while end > 0:
        attempt = candidate[: end + 1] + "\n]"
        try:
            result = json.loads(attempt)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
        end = candidate.rfind("}", 0, end)

    raise ValueError(f"Could not parse JSON from model output for '{source}'.\nRaw: {raw_text[:300]}")


def extract_ideas_from_note(note: RawNote, client: OpenAI) -> list[dict[str, Any]]:
    """
    Send a raw note to the local Ollama model and return a list of extracted idea dicts.
    Raises on API error. Returns [] if no ideas found.
    """
    response = client.chat.completions.create(
        model=EXTRACTION_MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Nota (origem: {note.relative_path}):\n\n{note.content}"},
        ],
    )

    raw_text = response.choices[0].message.content.strip()

    # Strip accidental markdown fences
    raw_text = re.sub(r"^```json\s*", "", raw_text)
    raw_text = re.sub(r"\s*```$", "", raw_text)

    return _parse_json_array(raw_text, note.relative_path)


_TODO_PROMPT = """
Você é um assistente de gestão de projetos.
Dado o título e a descrição de uma ideia, sugira de 3 a 5 próximos passos práticos e acionáveis (to-dos).

Regras:
- Cada to-do deve ser uma ação concreta, começando com verbo no infinitivo
- Máximo 80 caracteres por to-do
- Retorne APENAS uma lista JSON de strings, sem texto extra

Exemplo de saída:
["Mapear fontes de dados disponíveis", "Criar protótipo inicial", "Validar com stakeholders"]
""".strip()


def suggest_todos(title: str, description: str, client: OpenAI) -> list[str]:
    """Ask the model for to-do suggestions given a title and description."""
    user_msg = f"Título: {title}\nDescrição: {description or '(sem descrição)'}"
    response = client.chat.completions.create(
        model=EXTRACTION_MODEL,
        max_tokens=512,
        messages=[
            {"role": "system", "content": _TODO_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("[")
    if start == -1:
        return []
    try:
        result = json.loads(raw[start:])
        return [str(t).strip() for t in result if str(t).strip()]
    except json.JSONDecodeError:
        return []


_CLAUDE_TIPS_PROMPT = """
Você é um especialista em engenharia de software e desenvolvimento de produto com IA.
Dado o título e a descrição de um item do backlog, sugira de 3 a 5 dicas práticas e criativas de como o Claude (assistente de IA da Anthropic) pode ajudar a desenvolver ou otimizar esse item.

Regras:
- Cada dica deve ser específica para o item descrito, não genérica
- Mencione casos de uso concretos (gerar código, escrever testes, revisar arquitetura, criar documentação, brainstorming, analisar edge cases, etc.)
- Pode incluir sugestões criativas e inusitadas
- Máximo 120 caracteres por dica
- Retorne APENAS uma lista JSON de strings, sem texto extra

Exemplo de saída:
["Peça ao Claude para gerar os casos de teste com base na descrição do fluxo", "Use Claude para revisar a arquitetura e identificar edge cases"]
""".strip()


def suggest_claude_tips(title: str, description: str, client: OpenAI) -> list[str]:
    """Ask the model for Claude-usage tips for developing a backlog item."""
    user_msg = f"Título: {title}\nDescrição: {description or '(sem descrição)'}"
    response = client.chat.completions.create(
        model=EXTRACTION_MODEL,
        max_tokens=600,
        messages=[
            {"role": "system", "content": _CLAUDE_TIPS_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("[")
    if start == -1:
        return []
    try:
        result = json.loads(raw[start:])
        return [str(t).strip() for t in result if str(t).strip()]
    except json.JSONDecodeError:
        return []


def build_client() -> OpenAI:
    return OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
