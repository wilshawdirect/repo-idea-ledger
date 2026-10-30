"""repo-idea-ledger: record ideas taken from GitHub repos - ideas only, never their code.

idea-ledger add  --id retry-jitter --repo https://github.com/owner/name --idea "exponential backoff with full jitter" --on 2026-10-27
idea-ledger give --id retry-jitter --to "billing worker"
idea-ledger done --id retry-jitter --at "src/billing/retry.py" --taken "the jitter formula, re-written from the paper"
idea-ledger drop --id retry-jitter --note "the queue already retries"
idea-ledger list [--state implemented] [--markdown]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .ledger import STATES, Idea, Ledger, render_markdown


def _last(ledger: Ledger, idea_id: str) -> dict:
    for r in ledger.current():
        if r["id"] == idea_id:
            return r
    raise ValueError(f"{idea_id}: no such idea - add it first")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="idea-ledger", description=__doc__.splitlines()[0])
    ap.add_argument("--file", default="ideas.jsonl", help="the ledger file (default ideas.jsonl)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_add = sub.add_parser("add")
    a_add.add_argument("--id", required=True)
    a_add.add_argument("--repo", required=True)
    a_add.add_argument("--idea", required=True)
    a_add.add_argument("--on", default="", help="analysed on (YYYY-MM-DD)")
    a_add.add_argument("--note")
    a_give = sub.add_parser("give")
    a_give.add_argument("--id", required=True)
    a_give.add_argument("--to", required=True)
    a_done = sub.add_parser("done")
    a_done.add_argument("--id", required=True)
    a_done.add_argument("--at", required=True)
    a_done.add_argument("--taken", required=True)
    a_drop = sub.add_parser("drop")
    a_drop.add_argument("--id", required=True)
    a_drop.add_argument("--note", required=True)
    a_list = sub.add_parser("list")
    a_list.add_argument("--state", choices=STATES)
    a_list.add_argument("--markdown", action="store_true")
    a = ap.parse_args(argv)
    ledger = Ledger(Path(a.file))
    try:
        if a.cmd == "add":
            ledger.append(Idea(id=a.id, repo=a.repo, idea=a.idea, analysed_on=a.on, note=a.note))
        elif a.cmd in ("give", "done", "drop"):
            base = _last(ledger, a.id)
            if a.cmd == "give":
                extra = {"state": "given", "given_to": a.to}
            elif a.cmd == "done":
                extra = {"state": "implemented", "implemented_at": a.at, "taken": a.taken}
            else:
                extra = {"state": "dropped", "note": a.note}
            keep = {k: base.get(k) for k in ("given_to", "implemented_at", "taken")}
            ledger.append(Idea(id=a.id, repo=base["repo"], idea=base["idea"], analysed_on=base.get("analysed_on", ""), **{**keep, **extra}))
        else:
            rows = [r for r in ledger.current() if not a.state or r.get("state") == a.state]
            print(render_markdown(rows) if a.markdown else json.dumps(rows, indent=2, ensure_ascii=False))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
