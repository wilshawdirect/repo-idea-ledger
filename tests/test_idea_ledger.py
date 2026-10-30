import json

import pytest

from idea_ledger.cli import main
from idea_ledger.ledger import Idea, Ledger, render_markdown

REPO = "https://github.com/example-owner/example-repo"


def test_validation_names_every_gap():
    good = Idea(id="retry-jitter", repo=REPO, idea="backoff with full jitter", analysed_on="2026-10-27")
    assert good.validate() is good
    bad = [
        {"id": "Bad Id"},
        {"repo": "https://gitlab.com/a/b"},
        {"repo": "https://github.com/onlyowner"},
        {"idea": "  "},
        {"state": "merged"},
        {"analysed_on": "27/10/2026"},
        {"state": "given"},
        {"state": "implemented", "implemented_at": "src/x.py"},
    ]
    for over in bad:
        with pytest.raises(ValueError):
            Idea(**{**good.__dict__, **over}).validate()


def test_append_only_and_first_record_is_analysed(tmp_path):
    lg = Ledger(tmp_path / "ideas.jsonl")
    with pytest.raises(ValueError, match="first record"):
        lg.append(Idea(id="x1", repo=REPO, idea="i", state="given", given_to="team"))
    lg.append(Idea(id="x1", repo=REPO, idea="i"))
    before = (tmp_path / "ideas.jsonl").read_text(encoding="utf-8")
    lg.append(Idea(id="x1", repo=REPO, idea="i", state="given", given_to="team"))
    after = (tmp_path / "ideas.jsonl").read_text(encoding="utf-8")
    assert after.startswith(before) and len(after.splitlines()) == 2


def test_current_is_the_newest_record_per_id_with_fields_carried(tmp_path):
    lg = Ledger(tmp_path / "ideas.jsonl")
    lg.append(Idea(id="a1", repo=REPO, idea="cache warmup", analysed_on="2026-10-01"))
    lg.append(Idea(id="b2", repo=REPO, idea="dead-man switch"))
    lg.append(Idea(id="a1", repo=REPO, idea="cache warmup", state="given", given_to="api team"))
    cur = {r["id"]: r for r in lg.current()}
    assert list(cur) == ["a1", "b2"]
    assert cur["a1"]["state"] == "given" and cur["a1"]["given_to"] == "api team" and cur["a1"]["analysed_on"] == "2026-10-01"


def test_a_corrupt_line_is_reported_not_skipped(tmp_path):
    p = tmp_path / "ideas.jsonl"
    p.write_text('{"id": "a1"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match=":2:"):
        Ledger(p).records()


def test_markdown_escapes_pipes():
    md = render_markdown([{"idea": "a | b", "repo": REPO, "state": "analysed"}])
    assert "a \\| b" in md and md.count("\n") == 3


def test_cli_lifecycle(tmp_path, capsys):
    f = str(tmp_path / "ideas.jsonl")
    assert main(["--file", f, "add", "--id", "retry-jitter", "--repo", REPO, "--idea", "full jitter", "--on", "2026-10-27"]) == 0
    assert main(["--file", f, "give", "--id", "retry-jitter", "--to", "billing worker"]) == 0
    assert main(["--file", f, "done", "--id", "retry-jitter", "--at", "src/retry.py", "--taken", "the formula, re-written"]) == 0
    assert main(["--file", f, "give", "--id", "nope", "--to", "x"]) == 1
    capsys.readouterr()
    assert main(["--file", f, "list", "--state", "implemented"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1 and rows[0]["given_to"] == "billing worker" and rows[0]["taken"] == "the formula, re-written"
    assert main(["--file", f, "drop", "--id", "retry-jitter", "--note", "superseded"]) == 1  # implemented is final
    assert main(["--file", f, "add", "--id", "other-idea", "--repo", REPO, "--idea", "a second idea"]) == 0
    assert main(["--file", f, "drop", "--id", "other-idea", "--note", "the queue already retries"]) == 0
    assert main(["--file", f, "list", "--markdown"]) == 0
    assert "dropped" in capsys.readouterr().out


# advisor must-fixes (each reproduced before the fix)
def test_unicode_line_separators_never_split_a_record(tmp_path):
    lg = Ledger(tmp_path / "ideas.jsonl")
    for ch in ("\u2028", "\u2029", "\u0085"):
        lg.append(Idea(id=f"u{ord(ch)}", repo=REPO, idea=f"x{ch}y"))
    assert [r["idea"] for r in lg.records()] == ["x\u2028y", "x\u2029y", "x\u0085y"]
    lg.append(Idea(id="after", repo=REPO, idea="still works"))
    assert len(lg.records()) == 4


def test_a_missing_final_newline_never_merges_two_records(tmp_path):
    p = tmp_path / "ideas.jsonl"
    lg = Ledger(p)
    lg.append(Idea(id="a1", repo=REPO, idea="one"))
    p.write_bytes(p.read_bytes().rstrip(b"\n"))
    lg.append(Idea(id="b2", repo=REPO, idea="two"))
    assert [r["id"] for r in lg.records()] == ["a1", "b2"]


def test_trailing_newlines_and_dot_paths_fail_validation():
    for over in (
        {"id": "ab\n"},
        {"repo": REPO + "\n"},
        {"repo": "https://github.com/../x"},
        {"repo": "https://github.com/a/.."},
        {"analysed_on": "20261027"},
        {"state": "given", "given_to": "  "},
    ):
        with pytest.raises(ValueError):
            Idea(**{**Idea(id="ok", repo=REPO, idea="i").__dict__, **over}).validate()


def test_the_state_order_is_enforced(tmp_path):
    lg = Ledger(tmp_path / "ideas.jsonl")
    lg.append(Idea(id="s1", repo=REPO, idea="i"))
    with pytest.raises(ValueError, match="cannot go"):
        lg.append(Idea(id="s1", repo=REPO, idea="i", state="implemented", implemented_at="x", taken="y"))
    lg.append(Idea(id="s1", repo=REPO, idea="i", state="given", given_to="team"))
    lg.append(Idea(id="s1", repo=REPO, idea="i", state="dropped", note="no longer needed"))
    with pytest.raises(ValueError, match="cannot go"):
        lg.append(Idea(id="s1", repo=REPO, idea="i", state="given", given_to="team"))


def test_a_non_object_line_is_a_clean_error(tmp_path):
    p = tmp_path / "ideas.jsonl"
    p.write_text("[1]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        Ledger(p).records()
    assert main(["--file", str(p), "list"]) == 1
