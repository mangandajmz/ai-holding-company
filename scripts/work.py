from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kernel.db import connect  # noqa: E402
from kernel.views import render_status_text, work_status  # noqa: E402
from kernel.work_items import (  # noqa: E402
    approve_work_item,
    block_work_item,
    create_work_item,
    done_work_item,
    get_work_item,
    scan_ready_for_review_markdown,
    start_work_item,
)


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal AI company OS work ledger.")
    parser.add_argument("--db", default=None, help="Optional work ledger DB path.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show work that needs decision, execution, measurement, or unblock.")

    scan = sub.add_parser("scan_reviews", help="Scan markdown files for READY FOR MA REVIEW.")
    scan.add_argument("--root", default=str(ROOT / "finance_web_page"), help="Root directory to scan.")

    create = sub.add_parser("create", help="Create a work item.")
    create.add_argument("--title", required=True)
    create.add_argument("--type", default="task")
    create.add_argument("--source", default="manual")
    create.add_argument("--owner", default="Unassigned")
    create.add_argument("--due-at", default="")
    create.add_argument("--needs-approval", action="store_true")
    create.add_argument("--completion-signal", default="")
    create.add_argument("--next-step", default="")

    show = sub.add_parser("show", help="Show one work item.")
    show.add_argument("work_id")

    approve = sub.add_parser("approve", help="Approve work with execution fields.")
    approve.add_argument("work_id")
    approve.add_argument("--owner", required=True)
    approve.add_argument("--due-at", required=True)
    approve.add_argument("--completion-signal", required=True)
    approve.add_argument("--next-step", default="")

    start = sub.add_parser("start", help="Mark approved work in progress.")
    start.add_argument("work_id")
    start.add_argument("--note", default="")

    block = sub.add_parser("block", help="Mark work blocked.")
    block.add_argument("work_id")
    block.add_argument("--reason", required=True)

    done = sub.add_parser("done", help="Close work with result and evidence.")
    done.add_argument("work_id")
    done.add_argument("--result", required=True)
    done.add_argument("--evidence", required=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    conn = connect(args.db)
    try:
        if args.command == "status":
            print(render_status_text(work_status(conn)))
            return 0
        if args.command == "scan_reviews":
            _print_json(scan_ready_for_review_markdown(conn, root=args.root))
            return 0
        if args.command == "create":
            item, created = create_work_item(
                conn,
                title=args.title,
                work_type=args.type,
                source=args.source,
                owner=args.owner,
                due_at=args.due_at.strip() or None,
                needs_approval=bool(args.needs_approval),
                completion_signal=args.completion_signal.strip() or None,
                next_step=args.next_step.strip() or None,
            )
            _print_json({"ok": True, "created": created, "item": item})
            return 0
        if args.command == "show":
            item = get_work_item(conn, args.work_id)
            _print_json({"ok": item is not None, "item": item})
            return 0 if item is not None else 1
        if args.command == "approve":
            _print_json(
                {
                    "ok": True,
                    "item": approve_work_item(
                        conn,
                        args.work_id,
                        owner=args.owner,
                        due_at=args.due_at,
                        completion_signal=args.completion_signal,
                        next_step=args.next_step.strip() or None,
                    ),
                }
            )
            return 0
        if args.command == "start":
            _print_json({"ok": True, "item": start_work_item(conn, args.work_id, note=args.note)})
            return 0
        if args.command == "block":
            _print_json({"ok": True, "item": block_work_item(conn, args.work_id, args.reason)})
            return 0
        if args.command == "done":
            _print_json(
                {
                    "ok": True,
                    "item": done_work_item(
                        conn,
                        args.work_id,
                        result=args.result,
                        evidence=args.evidence,
                    ),
                }
            )
            return 0
    except ValueError as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1
    finally:
        conn.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
