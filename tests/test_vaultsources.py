"""Testes de vaultsources — offline, sem tocar o vault real.

Divisao com o `tester`: aqui prova-se que o codigo faz o que diz, com fixture e
sem rede. O `python -m vaultsources tester` sai na rede com conteudo real e prova
que o processo entrega. Um nao substitui o outro: a suite verde nunca teria pego
a CA da rede corporativa nem o comando apontando para repo inexistente.

Padrao 10 (teste nao escreve no vault real): todo teste que grava usa
`monkeypatch` em `vaultsources.paths` para um `tmp_path`.
"""

from __future__ import annotations

import json
import re

import pytest

from vaultsources import concepts, feeds, governance, linkedin, note, paths, qa, questions


@pytest.fixture(autouse=True)
def vault_tmp(tmp_path, monkeypatch):
    """Aponta todo caminho de escrita para tmp_path antes de qualquer teste."""
    monkeypatch.setattr(paths, "VAULT", tmp_path)
    monkeypatch.setattr(paths, "SOURCES_DIR", tmp_path / "Sources")
    monkeypatch.setattr(paths, "CONCEPTS_DIR", tmp_path / "Concepts")
    monkeypatch.setattr(paths, "WATCHLIST", tmp_path / "Sources" / "_watchlist.json")
    monkeypatch.setattr(paths, "QUEUE", tmp_path / "Sources" / "_queue.json")
    monkeypatch.setattr(paths, "PROPOSALS_DIR", tmp_path / "Concepts" / "_proposals")
    monkeypatch.setattr(paths, "REJECTED_DIR", tmp_path / "Concepts" / "_rejected")
    monkeypatch.setattr(paths, "REPORTS_DIR", tmp_path / "_reports")
    monkeypatch.setattr(paths, "QA_REPORT", tmp_path / "_reports" / "Sources-QA.md")
    monkeypatch.setattr(questions, "_PEOPLE_CACHE", None, raising=False)
    paths.ensure_dirs()
    return tmp_path


def make_doc(**kw) -> note.SourceDoc:
    base = dict(kind="youtube", url="https://youtu.be/abcdefghijk", title="Titulo de teste",
                author="Canal", published="2026-01-02", lang="en", duration_seconds=120,
                provenance="youtube-transcript-api", text="palavra " * 30,
                external_id="abcdefghijk")
    base.update(kw)
    return note.SourceDoc(**base)


# ── governanca ────────────────────────────────────────────────────────────────

def test_payload_do_vault_nao_vai_para_provedor_externo():
    for purpose in ("research-web", "x-read", "x-pulse"):
        with pytest.raises(governance.EgressDenied):
            governance.check_egress(purpose, "vault")


def test_purpose_nao_declarado_e_recusado():
    with pytest.raises(governance.EgressDenied):
        governance.check_egress("research-deep", "user")


def test_local_aceita_qualquer_origem():
    for origin in ("public", "user", "vault"):
        governance.check_egress("source-summarize", origin)


def test_origem_invalida_estoura():
    with pytest.raises(ValueError):
        governance.check_egress("research-web", "qualquer-coisa")


def test_todo_purpose_usado_no_codigo_esta_declarado():
    """O mesmo check que o QA roda. Aqui ele quebra a suite, nao so o relatorio."""
    achados = [f for f in qa.check_governance() if f.severity == qa.ERRO]
    assert not achados, [f.title for f in achados]


# ── nota de fonte ─────────────────────────────────────────────────────────────

def test_fonte_sem_url_nao_entra():
    with pytest.raises(ValueError):
        make_doc(url="")


def test_provenance_invalida_e_recusada():
    with pytest.raises(ValueError):
        make_doc(provenance="chutei")


def test_texto_e_canonicalizado_antes_do_hash():
    """Sem o strip no __post_init__ o sha do objeto e o do texto relido divergiam
    por um \\n, e a procedencia acusava adulteracao que nunca houve."""
    a = make_doc(text="  conteudo  \n")
    b = make_doc(text="conteudo")
    assert a.text_sha256 == b.text_sha256


def test_roundtrip_preserva_o_hash_com_texto_inline():
    doc = make_doc(text="curto " * 10)
    p = note.write(doc)
    assert note.read_doc(p).text_sha256 == doc.text_sha256


def test_roundtrip_preserva_o_hash_com_sidecar():
    """Transcricao longa vai para o sidecar. O separador de frontmatter e o mesmo
    de tres tracos, entao o parse tem que usar a sentinela e nao o primeiro '---'."""
    doc = make_doc(text="palavra " * 2000)
    p = note.write(doc)
    assert note.transcript_path(doc).exists()
    assert note.read_doc(p).text_sha256 == doc.text_sha256


def test_nota_nasce_com_analise_pendente():
    p = note.write(make_doc())
    raw = p.read_text(encoding="utf-8")
    assert "analysis: pending" in raw
    assert note.PENDING_MARK in raw


def test_complete_preenche_analise_sem_tocar_no_texto():
    doc = make_doc(text="palavra " * 2000)
    p = note.write(doc)
    note.complete(p, {"thesis": "a tese", "for_future_claude": "resumo",
                      "claims": [{"text": "afirmacao", "as_of": "2026-01"}]})
    raw = p.read_text(encoding="utf-8")
    assert "analysis: proposed" in raw
    assert "a tese" in raw
    assert note.PENDING_MARK not in raw.split("## Texto bruto")[0]
    assert note.read_doc(p).text_sha256 == doc.text_sha256


def test_gravar_duas_vezes_sem_overwrite_estoura():
    doc = make_doc()
    note.write(doc)
    with pytest.raises(FileExistsError):
        note.write(doc)


def test_find_by_url_acha_a_nota_existente():
    doc = make_doc()
    note.write(doc)
    assert note.find_by_url(doc.url) is not None
    assert note.find_by_url("https://outra/coisa") is None


def test_titulo_com_aspas_nao_quebra_o_yaml():
    doc = make_doc(title='Ele disse: "governanca" e saiu')
    p = note.write(doc)
    from vaultindex.corpus import split_frontmatter
    fm, _body, ok = split_frontmatter(p.read_text(encoding="utf-8"))
    assert ok and fm["source-title"] == 'Ele disse: "governanca" e saiu'


# ── conceitos ─────────────────────────────────────────────────────────────────

def test_proposta_nao_altera_a_pagina():
    page = concepts.create("Tema", stance="posicao", why="motivo")
    antes = page.read_text(encoding="utf-8")
    concepts.propose("Tema", source_slug="fonte-x", relation="contradiz", claim="c")
    assert page.read_text(encoding="utf-8") == antes


def test_aceitar_aplica_e_conta_contradicao():
    page = concepts.create("Tema", stance="posicao", why="motivo")
    prop = concepts.propose("Tema", source_slug="fonte-x", relation="contradiz",
                            claim="a fonte discorda")
    concepts.accept(prop.name)
    raw = page.read_text(encoding="utf-8")
    assert "open-contradictions: 1" in raw
    assert "sources: 1" in raw
    assert "a fonte discorda" in raw
    assert "[[Sources/fonte-x]]" in raw
    assert not (paths.PROPOSALS_DIR / prop.name).exists()


def test_descartar_guarda_e_nao_apaga():
    concepts.create("Tema", stance="p", why="m")
    prop = concepts.propose("Tema", source_slug="f", relation="acrescenta", claim="c")
    alvo = concepts.reject(prop.name, why="nao serve")
    assert alvo.exists()
    assert json.loads(alvo.read_text(encoding="utf-8"))["rejected_why"] == "nao serve"
    assert not (paths.PROPOSALS_DIR / prop.name).exists()


def test_aceitar_para_pagina_inexistente_falha_claro():
    prop = concepts.propose("Nao existe", source_slug="f", relation="confirma", claim="c")
    with pytest.raises(FileNotFoundError):
        concepts.accept(prop.name)


def test_relacao_invalida_e_recusada():
    with pytest.raises(ValueError):
        concepts.propose("Tema", source_slug="f", relation="inventada", claim="c")


# ── feeds ─────────────────────────────────────────────────────────────────────

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/">
  <entry>
    <yt:videoId>ABCDEFGHIJK</yt:videoId>
    <title>Data governance and master data quality</title>
    <author><name>Canal X</name></author>
    <published>2026-09-01T10:00:00+00:00</published>
    <media:group><media:description>sobre governanca</media:description></media:group>
  </entry>
</feed>"""


def test_parse_do_atom_do_youtube():
    items = feeds.parse_feed(ATOM)
    assert len(items) == 1
    assert items[0]["video_id"] == "ABCDEFGHIJK"
    assert items[0]["published"] == "2026-09-01"
    assert items[0]["url"].endswith("ABCDEFGHIJK")


def test_score_explica_por_que_o_candidato_apareceu():
    item = {"title": "Data governance and master data quality", "description": ""}
    qs = [{"text": "como medir data quality de master data"}]
    s, reason = feeds.score(item, qs, [])
    assert s > 0
    assert "pergunta aberta" in reason


def test_score_zero_diz_que_ninguem_pediu():
    item = {"title": "receita de bolo de cenoura", "description": ""}
    s, reason = feeds.score(item, [{"text": "governanca de dados"}], [])
    assert s == 0
    assert "nenhuma pergunta" in reason


def test_watchlist_recusa_feed_duplicado():
    feeds.add_feed("UC12345678901234567890AB", label="X")
    with pytest.raises(ValueError):
        feeds.add_feed("UC12345678901234567890AB")


def test_estado_invalido_na_fila_e_recusado():
    q = feeds.load_queue()
    q["candidates"].append({"video_id": "X", "title": "t", "state": "proposed"})
    feeds.save_queue(q)
    with pytest.raises(ValueError):
        feeds.set_state("X", "quase-aprovado")


def test_json_corrompido_nao_e_sobrescrito_em_silencio():
    paths.WATCHLIST.write_text("{isto nao e json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        feeds.load_watchlist()


# ── perguntas ─────────────────────────────────────────────────────────────────

def test_pergunta_que_cita_pessoa_do_vault_e_sensivel(vault_tmp, monkeypatch):
    (vault_tmp / "Stakeholders" / "Stefan-Lautenschlager").mkdir(parents=True)
    monkeypatch.setattr(questions, "_PEOPLE_CACHE", None)
    q = {"text": "Revisar Overview proposto para Stefan-Lautenschlager", "ref": ""}
    flag, why = questions.is_sensitive(q)
    assert flag and "pessoa" in why


def test_pergunta_tecnica_nao_e_sensivel(vault_tmp, monkeypatch):
    (vault_tmp / "Team" / "Ana-Leite").mkdir(parents=True)
    monkeypatch.setattr(questions, "_PEOPLE_CACHE", None)
    flag, _ = questions.is_sensitive({"text": "DQ cycle Plan-Deploy-Monitor-Act", "ref": ""})
    assert not flag


def test_ref_em_pasta_sensivel_barra():
    flag, why = questions.is_sensitive({"text": "qualquer", "ref": "Team/Ana-Leite/PDI.md"})
    assert flag and "Team" in why


# ── linkedin ──────────────────────────────────────────────────────────────────

def test_taboo_barra_transicao_com_acento():
    assert linkedin._is_taboo("plano nao seguido nesta transição para a nova posicao")


def test_taboo_barra_documento_de_visto():
    assert linkedin._is_taboo("Atualizar o CV antes de enviar a empresa de vistos")


def test_taboo_deixa_passar_historia_de_projeto():
    assert not linkedin._is_taboo(
        "O baseline de MDM mostrou 12% de duplicidade no material master do SAP")


def test_taboo_barra_nome_de_colega(vault_tmp, monkeypatch):
    (vault_tmp / "Team" / "Ana-Leite").mkdir(parents=True)
    monkeypatch.setattr(questions, "_PEOPLE_CACHE", None)
    assert linkedin._is_taboo("conversei com Ana Leite sobre o pipeline")


def test_export_sem_linha_de_post_estoura_em_vez_de_gravar_vazio(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.append(["seguidores", "total"])
    wb.active.append([10, 20])
    f = tmp_path / "analytics.xlsx"
    wb.save(f)
    with pytest.raises(RuntimeError, match="nao reconheci"):
        linkedin.parse_export(f)


# ── qa ────────────────────────────────────────────────────────────────────────

def test_qa_acusa_hash_divergente(vault_tmp):
    doc = make_doc(text="palavra " * 10)
    p = note.write(doc)
    raw = p.read_text(encoding="utf-8")
    p.write_text(raw.replace("palavra palavra", "adulterado palavra"), encoding="utf-8")
    achados = [f for f in qa.check_notes() if "sha256" in f.title]
    assert achados and achados[0].severity == qa.ERRO


def test_qa_ignora_o_index_da_pasta(vault_tmp):
    (paths.SOURCES_DIR / "_index.md").write_text(
        "---\ndate: 2026-09-10\ntype: area\n---\n\n# indice\n", encoding="utf-8")
    assert not qa.check_notes()


def test_qa_acusa_pasta_prometida_que_nao_existe(vault_tmp):
    (vault_tmp / "_CLAUDE.md").write_text(
        "## Folder Map\n\n| Folder | Purpose |\n|---|---|\n"
        "| `NaoExiste/` | promessa |\n", encoding="utf-8")
    achados = qa.check_folders()
    assert any("NaoExiste" in f.title and f.severity == qa.ERRO for f in achados)


def test_qa_nao_confunde_tabela_de_mapeamento_com_folder_map(vault_tmp):
    """A tabela de mapeamento das skills genericas lista de proposito pastas que
    este vault NAO usa. Checar aquela tabela virava 5 erros de uma explicacao certa."""
    (vault_tmp / "_CLAUDE.md").write_text(
        "## Folder Map\n\n| Folder | Purpose |\n|---|---|\n| `Sources/` | fontes |\n"
        "\n## Command Mapping\n\n| Generic | Aqui |\n|---|---|\n"
        "| `raw/` | nao usado |\n| `wiki/entities/` | nao usado |\n", encoding="utf-8")
    (vault_tmp / "Sources").mkdir(exist_ok=True)
    achados = qa.check_folders()
    assert not [f for f in achados if "raw" in f.title or "wiki" in f.title]


def test_qa_acusa_afirmacao_de_pasta_vazia_que_envelheceu(vault_tmp):
    (vault_tmp / "Daily" / "2026" / "09").mkdir(parents=True)
    (vault_tmp / "Daily" / "2026" / "09" / "2026-09-01.md").write_text("x", encoding="utf-8")
    (vault_tmp / "_CLAUDE.md").write_text(
        "## Folder Map\n\n| Folder | Purpose |\n|---|---|\n\n"
        "## Notas\n\nA pasta `Daily/` is **empty** as of this writing.\n", encoding="utf-8")
    achados = qa.check_folders()
    assert any("vazia" in f.title for f in achados)


def test_qa_acusa_placeholder_no_registro(vault_tmp):
    d = vault_tmp / "Inbox"
    d.mkdir(exist_ok=True)
    (d / "nota.md").write_text(
        "---\ndate: 2026-09-09\n---\n\n- O evento sera em 16 e 17 de [data].\n",
        encoding="utf-8")
    achados = qa.check_placeholders()
    assert any("[data]" in f.title for f in achados)


def test_qa_acusa_loop_declarado_que_nunca_produziu(vault_tmp):
    achados = qa.check_deadloops()
    assert any(f.severity == qa.ERRO and "nunca produziu" in f.title for f in achados)


def test_check_que_estoura_vira_achado_em_vez_de_silencio(monkeypatch):
    def explode():
        raise RuntimeError("quebrei")
    monkeypatch.setitem(qa.CHECKS, "inbox", explode)
    achados = qa.run(["inbox"], online=False)
    assert achados and achados[0].severity == qa.ERRO
    assert "o proprio check quebrou" in achados[0].title


def test_relatorio_de_qa_tem_frontmatter_e_contagem(vault_tmp):
    findings = [qa.Finding("refs", qa.ERRO, "titulo", "detalhe", "onde", "conserto")]
    md = qa.render(findings)
    assert md.startswith("---")
    assert "type: qa-report" in md
    assert "| erro | 1 |" in md
    assert "## For future Claude" in md


def test_relatorio_de_qa_limpo_diz_que_esta_limpo():
    assert "Nenhuma inconsistencia" in qa.render([])


# ── refs: o defeito que originou o pacote ─────────────────────────────────────

def test_caminho_ancorado_inexistente_e_erro(tmp_path, monkeypatch):
    doc = tmp_path / "comando.md"
    doc.write_text("Rode a partir de `~/Projects/personal/nao-existe-mesmo/`.\n",
                   encoding="utf-8")
    monkeypatch.setattr(qa, "_doc_files", lambda: [doc])
    achados = qa.check_refs()
    assert achados and achados[0].severity == qa.ERRO


def test_fragmento_com_base_conhecida_nao_vira_achado(tmp_path, monkeypatch):
    doc = tmp_path / "comando.md"
    doc.write_text("O script e `vaultsources/qa.py`, sob o repo.\n", encoding="utf-8")
    monkeypatch.setattr(qa, "_doc_files", lambda: [doc])
    monkeypatch.setattr(qa, "_BASENAMES", {"qa.py"})
    assert not qa.check_refs()


def test_molde_de_nome_nao_e_cobrado(tmp_path, monkeypatch):
    doc = tmp_path / "comando.md"
    doc.write_text("Grave em `AI/sessions/YYYY-MM-DD.md`.\n", encoding="utf-8")
    monkeypatch.setattr(qa, "_doc_files", lambda: [doc])
    assert not qa.check_refs()


# ── adaptadores (sem rede) ────────────────────────────────────────────────────

def test_id_do_youtube_em_todas_as_formas():
    from vaultsources import adapters
    for u in ("https://youtu.be/dQw4w9WgXcQ",
              "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1",
              "https://www.youtube.com/shorts/dQw4w9WgXcQ",
              "dQw4w9WgXcQ"):
        assert adapters.youtube_id(u) == "dQw4w9WgXcQ"


def test_url_sem_id_falha_com_motivo():
    from vaultsources import adapters
    with pytest.raises(adapters.FetchError, match="11 caracteres"):
        adapters.youtube_id("https://exemplo.com/pagina")


def test_linkedin_manda_usar_clip_em_vez_de_fingir_fetch():
    from vaultsources import adapters
    with pytest.raises(adapters.FetchError, match="clip"):
        adapters.fetch("https://www.linkedin.com/posts/alguem-123")


def test_clip_sem_texto_e_recusado():
    from vaultsources import adapters
    with pytest.raises(adapters.FetchError, match="casca"):
        adapters.from_clip(url="https://x/y", title="t", text="   ")


def test_slug_normaliza_acento_e_pontuacao():
    assert note.slugify("Governança: o que é?") == "governanca-o-que-e"
    assert note.slugify("") == "sem-titulo"


def test_duplicado_so_e_achado_quando_alguem_linka_sem_caminho(vault_tmp):
    """Convencao declarada (Overview/Playbook por pessoa) nao e colisao. O defeito
    e o link nu que resolve para o arquivo errado."""
    for pessoa in ("Ana", "Bruno", "Carla"):
        d = vault_tmp / "Team" / pessoa
        d.mkdir(parents=True)
        (d / "Overview.md").write_text("# overview", encoding="utf-8")
    assert not qa.check_duplicates()

    (vault_tmp / "Team" / "Ana" / "Playbook.md").write_text(
        "ver [[Overview]]", encoding="utf-8")
    achados = qa.check_duplicates()
    assert achados and "[[Overview]]" in achados[0].title


def test_duplicado_ignora_link_com_caminho(vault_tmp):
    for pessoa in ("Ana", "Bruno"):
        d = vault_tmp / "Team" / pessoa
        d.mkdir(parents=True)
        (d / "Overview.md").write_text("x", encoding="utf-8")
    (vault_tmp / "Team" / "Ana" / "Playbook.md").write_text(
        "ver [[Team/Ana/Overview]]", encoding="utf-8")
    assert not qa.check_duplicates()


def test_duplicado_nao_le_o_proprio_relatorio(vault_tmp):
    """O relatorio cita `[[Overview]]` ao dizer que `[[Overview]]` e ambiguo. Se o
    scan lesse `_reports/`, o check se realimentaria para sempre."""
    for pessoa in ("Ana", "Bruno"):
        d = vault_tmp / "Team" / pessoa
        d.mkdir(parents=True)
        (d / "Overview.md").write_text("x", encoding="utf-8")
    rep = vault_tmp / "_reports"
    rep.mkdir(exist_ok=True)
    (rep / "Sources-QA.md").write_text("`[[Overview]]` e ambiguo", encoding="utf-8")
    assert not qa.check_duplicates()
