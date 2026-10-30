# repo-idea-ledger

Keep an honest record of the ideas you take from other people's repositories: which repo, when you analysed it, what the idea is, who you
gave it to, where it was implemented and what exactly was taken.

**Ideas only.** The ledger stores a repo URL and your own words. It never downloads, copies or vendors anyone's code - if you implement an
idea, you write it yourself and record what you took (an approach, a formula, a pattern), so credit and licence questions stay answerable.

**Append-only.** Every change (given, implemented, dropped) is a new line in a JSON-lines file; nothing is edited in place. The current
view is the newest record per idea, with earlier fields carried forward. A corrupt line is reported with its line number, never skipped.

## Use

```bash
pip install -e .
idea-ledger add  --id retry-jitter --repo https://github.com/owner/name --idea "exponential backoff with full jitter" --on 2026-10-27
idea-ledger give --id retry-jitter --to "billing worker"
idea-ledger done --id retry-jitter --at "src/billing/retry.py" --taken "the jitter formula, re-written from the paper"
idea-ledger drop --id other-idea --note "the queue already retries"
idea-ledger list --state implemented          # JSON
idea-ledger list --markdown > IDEAS.md        # a table for a README
```

States, enforced: `analysed` (always the first record) -> `given` (names who) -> `implemented` (names where and what was taken), or
`dropped` from `analysed` / `given`. `implemented` and `dropped` are final. `--file` picks the ledger (default `ideas.jsonl`).
One writer at a time per file (there is no cross-process lock). A file whose last line lost its newline is repaired on the next append.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest -q
```

MIT licence.
