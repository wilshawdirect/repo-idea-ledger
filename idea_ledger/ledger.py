"""An append-only ledger of ideas taken from other people's repositories.

One JSON-lines file, one record per idea: which repo it came from, when it was analysed, what the idea is, who it was given to, where
(if anywhere) it was implemented, and what exactly was taken. Ideas only: the ledger stores a repo URL and your own words - it never
downloads, copies or vendors anyone's code. Records are never edited in place; a later state (given, implemented, dropped) is a new
record for the same idea id, and the current view is the newest record per id.

Single writer: run one writer at a time per file (there is no cross-process lock).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

STATES = ("analysed", "given", "implemented", "dropped")
# allowed next states: the README's analysed -> given -> implemented | dropped (an analysed idea may also be dropped)
NEXT = {"analysed": {"given", "dropped"}, "given": {"implemented", "dropped"}, "implemented": set(), "dropped": set()}
_REPO = re.compile(r"https://github\.com/(?!\.{1,2}/)[A-Za-z0-9_][A-Za-z0-9_.-]*/(?!\.{1,2}/?$)[A-Za-z0-9_][A-Za-z0-9_.-]*/?")
_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,63}")


def _filled(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


@dataclass
class Idea:
    id: str
    repo: str
    idea: str
    state: str = "analysed"
    analysed_on: str = ""
    given_to: Optional[str] = None
    implemented_at: Optional[str] = None
    taken: Optional[str] = None
    note: Optional[str] = None
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def validate(self) -> "Idea":
        if not isinstance(self.id, str) or not _ID.fullmatch(self.id):
            raise ValueError(f"id must be 2-64 chars of a-z, 0-9, '-': {self.id!r}")
        if not isinstance(self.repo, str) or not _REPO.fullmatch(self.repo):
            raise ValueError(f"repo must be a https://github.com/<owner>/<name> URL: {self.repo!r}")
        if not _filled(self.idea):
            raise ValueError("idea must say what the idea is")
        if self.state not in STATES:
            raise ValueError(f"state must be one of {STATES}")
        if self.analysed_on:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.analysed_on):
                raise ValueError(f"analysed_on must be YYYY-MM-DD: {self.analysed_on!r}")
            date.fromisoformat(self.analysed_on)
        if self.state == "given" and not _filled(self.given_to):
            raise ValueError("a 'given' idea names who it was given to")
        if self.state == "implemented" and not (_filled(self.implemented_at) and _filled(self.taken)):
            raise ValueError("an 'implemented' idea names where (implemented_at) and what was taken (taken)")
        return self


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def records(self) -> List[dict]:
        if not self.path.exists():
            return []
        out = []
        # split on "\n" only: json.dumps writes U+2028 / U+2029 / U+0085 raw, and str.splitlines() would break a record on them
        for n, line in enumerate(self.path.read_text(encoding="utf-8").split("\n"), 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"{self.path}:{n}: not a JSON record ({exc})") from exc
            if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
                raise ValueError(f"{self.path}:{n}: a record must be a JSON object with an 'id'")
            out.append(rec)
        return out

    def append(self, idea: Idea) -> dict:
        """Validate and append ONE record (never rewrites the file). The first record of an id is 'analysed'; later ones follow NEXT."""
        idea.validate()
        last = {r["id"]: r for r in self.records()}.get(idea.id)
        if last is None and idea.state != "analysed":
            raise ValueError(f"{idea.id}: the first record of an idea is 'analysed', not {idea.state!r}")
        if last is not None and idea.state not in NEXT.get(last.get("state"), set()):
            raise ValueError(f"{idea.id}: cannot go from {last.get('state')!r} to {idea.state!r}")
        rec = asdict(idea)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size:
            with self.path.open("rb") as f:
                f.seek(-1, 2)
                needs_newline = f.read(1) != b"\n"
        else:
            needs_newline = False
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(("\n" if needs_newline else "") + json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return rec

    def current(self) -> List[dict]:
        """The newest record per idea id, carrying forward fields a later record left empty, in first-seen order."""
        view: dict = {}
        for r in self.records():
            prev = view.get(r["id"], {})
            view[r["id"]] = {**prev, **{k: v for k, v in r.items() if v not in (None, "")}}
        return list(view.values())


def render_markdown(rows: Iterable[dict]) -> str:
    """A table for a README: idea, source repo, state, given to, implemented at, what was taken."""
    esc = lambda v: str(v or "-").replace("|", "\\|").replace("\n", " ")  # noqa: E731
    lines = ["| idea | from | state | given to | implemented at | taken |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {esc(r.get('idea'))} | {esc(r.get('repo'))} | {esc(r.get('state'))} | {esc(r.get('given_to'))} | "
            f"{esc(r.get('implemented_at'))} | {esc(r.get('taken'))} |"
        )
    return "\n".join(lines) + "\n"
