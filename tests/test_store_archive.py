"""Store must handle archived ideas in subfolders (e.g. _arquivo/):
load them, count them for next-id, and save edits back to their location
(no duplicate created in the root)."""
from pathlib import Path

from backlog.store import BacklogStore


def _md(idea_id: str, status: str = "concluído") -> str:
    return (
        f"---\nid: {idea_id}\ntitulo: T {idea_id}\nstatus: {status}\n"
        f"prioridade: média\n---\n\n## Descricao\nx\n\n## To-dos\n_nenhum_\n\n"
        f"## Notas\n_sem notas_\n"
    )


def test_archived_ideas_load_and_count(tmp_path):
    store = BacklogStore(tmp_path)
    (tmp_path / "idea-001.md").write_text(_md("idea-001", "backlog"), encoding="utf-8")
    arch = tmp_path / "_arquivo"
    arch.mkdir()
    (arch / "idea-002.md").write_text(_md("idea-002", "concluído"), encoding="utf-8")
    (arch / "idea-003.md").write_text(_md("idea-003", "descartado"), encoding="utf-8")

    ideas = {i.id for i in store.load_all()}
    assert ideas == {"idea-001", "idea-002", "idea-003"}      # archived still loaded
    assert store._next_id() == "idea-004"                     # archived counted (no reuse)
    assert store.load_by_id("idea-002") is not None           # findable by id


def test_save_archived_idea_writes_back_not_duplicate(tmp_path):
    store = BacklogStore(tmp_path)
    arch = tmp_path / "_arquivo"
    arch.mkdir()
    (arch / "idea-009.md").write_text(_md("idea-009", "concluído"), encoding="utf-8")

    idea = store.load_by_id("idea-009")
    idea.notes = "editado"
    store.save(idea)

    assert (arch / "idea-009.md").exists()                    # saved back to archive
    assert not (tmp_path / "idea-009.md").exists()            # no duplicate in root
    assert len([p for p in tmp_path.rglob("idea-009.md")]) == 1
