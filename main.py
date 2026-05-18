"""
TechColab Backlog CLI
Usage:
  python main.py ingest                              # parse notes, extract ideas, clean source files
  python main.py backlog list [--status <status>]    # list ideas
  python main.py backlog show <id>                   # show idea detail
  python main.py backlog update <id> --status <s>    # update status
  python main.py backlog update <id> --priority <p>  # update priority
"""

import argparse
import sys

from ingestion.pipeline import run_ingestion
from backlog.store import BacklogStore
from backlog.schema import VALID_STATUSES, VALID_PRIORITIES
from config import VAULT_NOTES_DIR, BACKLOG_DIR


def cmd_ingest(args):
    print(f"[ingest] Reading notes from: {VAULT_NOTES_DIR}")
    print(f"[ingest] Backlog output:      {BACKLOG_DIR}")
    results = run_ingestion(dry_run=args.dry_run)
    print(f"\n[ingest] Done. {results['created']} ideas created, {results['skipped']} skipped, {results['cleaned']} notes cleaned.")


def cmd_list(args):
    store = BacklogStore(BACKLOG_DIR)
    ideas = store.load_all()

    if args.status:
        ideas = [i for i in ideas if i.status == args.status]

    if not ideas:
        print("No ideas found.")
        return

    # Sort by priority then created_at
    priority_order = {"alta": 0, "média": 1, "baixa": 2}
    ideas.sort(key=lambda i: (priority_order.get(i.priority, 9), i.created_at))

    col_w = [6, 35, 22, 8, 12]
    header = f"{'ID':<{col_w[0]}}  {'Título':<{col_w[1]}}  {'Status':<{col_w[2]}}  {'Prior.':<{col_w[3]}}  {'Criado':<{col_w[4]}}"
    print(header)
    print("-" * (sum(col_w) + 8))
    for idea in ideas:
        print(
            f"{idea.id:<{col_w[0]}}  "
            f"{idea.title[:col_w[1]]:<{col_w[1]}}  "
            f"{idea.status:<{col_w[2]}}  "
            f"{idea.priority:<{col_w[3]}}  "
            f"{str(idea.created_at):<{col_w[4]}}"
        )


def cmd_show(args):
    store = BacklogStore(BACKLOG_DIR)
    idea = store.load_by_id(args.id)
    if not idea:
        print(f"Idea '{args.id}' not found.")
        sys.exit(1)

    print(f"\nID:         {idea.id}")
    print(f"Título:     {idea.title}")
    print(f"Status:     {idea.status}")
    print(f"Prioridade: {idea.priority}")
    print(f"Área:       {idea.area or '-'}")
    print(f"Origem:     {idea.origin or '-'}")
    print(f"Criado:     {idea.created_at}")
    print(f"Atualizado: {idea.updated_at}")
    print(f"\nDescrição:\n{idea.description or '-'}")
    if idea.todos:
        print(f"\nTo-dos:")
        for todo in idea.todos:
            mark = "x" if todo["done"] else " "
            print(f"  [{mark}] {todo['text']}")
    if idea.notes:
        print(f"\nNotas:\n{idea.notes}")


def cmd_update(args):
    store = BacklogStore(BACKLOG_DIR)
    idea = store.load_by_id(args.id)
    if not idea:
        print(f"Idea '{args.id}' not found.")
        sys.exit(1)

    changed = False
    if args.status:
        if args.status not in VALID_STATUSES:
            print(f"Invalid status. Valid: {VALID_STATUSES}")
            sys.exit(1)
        idea.status = args.status
        changed = True

    if args.priority:
        if args.priority not in VALID_PRIORITIES:
            print(f"Invalid priority. Valid: {VALID_PRIORITIES}")
            sys.exit(1)
        idea.priority = args.priority
        changed = True

    if args.area:
        idea.area = args.area
        changed = True

    if changed:
        store.save(idea)
        print(f"Updated {idea.id}: {idea.title}")
    else:
        print("Nothing to update. Use --status, --priority, or --area.")


def main():
    parser = argparse.ArgumentParser(description="TechColab Backlog CLI")
    subparsers = parser.add_subparsers(dest="command")

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Parse notes and populate backlog")
    p_ingest.add_argument("--dry-run", action="store_true", help="Preview without writing files")

    # backlog
    p_backlog = subparsers.add_parser("backlog", help="Manage backlog")
    backlog_sub = p_backlog.add_subparsers(dest="subcommand")

    p_list = backlog_sub.add_parser("list", help="List ideas")
    p_list.add_argument("--status", choices=VALID_STATUSES, help="Filter by status")

    p_show = backlog_sub.add_parser("show", help="Show idea detail")
    p_show.add_argument("id", help="Idea ID (e.g. idea-001)")

    p_update = backlog_sub.add_parser("update", help="Update idea fields")
    p_update.add_argument("id", help="Idea ID")
    p_update.add_argument("--status", help="New status")
    p_update.add_argument("--priority", help="New priority")
    p_update.add_argument("--area", help="New area")

    args = parser.parse_args()

    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "backlog":
        if args.subcommand == "list":
            cmd_list(args)
        elif args.subcommand == "show":
            cmd_show(args)
        elif args.subcommand == "update":
            cmd_update(args)
        else:
            p_backlog.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
