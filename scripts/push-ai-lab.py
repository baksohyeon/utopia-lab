#!/usr/bin/env python3
"""Push the Dionz ai-lab markdown corpus into a Utopia API source.

Read-only on ai-lab, stdlib only, no state file: Utopia already answers
`unchanged` for identical content, so every run simply pushes everything and
lets the server decide what is new. Identity is the repo-relative path.

    UTOPIA_INGEST_TOKEN=utp_... UTOPIA_SOURCE_ID=<uuid> python3 scripts/push-ai-lab.py
    python3 scripts/push-ai-lab.py --dry-run          # list files and doc_time, no network

Scope and doc_time fields were agreed with the ai-lab maintainer on 2026-09-04:
journal (not *.raw.md), postmortems, decisions (not README). Registry YAML is an
entity dictionary, not documents, and is deliberately not pushed here.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ROOT = "/Users/cnai/dev/work/Dionz/ai-lab"
DEFAULT_BASE = "http://localhost:1516"

# (directory, recursive, excluded basename regex)
SCOPE = [
    ("docs/journal/2026", True, r"\.raw\.md$"),
    ("docs/journal/postmortem", False, r"^README\.md$"),
    ("docs/decisions", False, r"^README\.md$"),
]
# Which frontmatter key is "the document's time", in priority order. `created`
# is what the journals actually use; the rest per the maintainer's answer.
TIME_KEYS = ("decided_at", "created_at", "created", "updated_at")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def frontmatter(text: str) -> dict:
    """Top-level `key: value` pairs of the leading --- block. Nested YAML is skipped;
    the time fields we need are all flat scalars."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if m and m.group(2) and not m.group(2).startswith(("[", "{", "-", "|", ">")):
            out[m.group(1)] = m.group(2).strip("\"'")
    return out


def doc_time(fm: dict, path: Path):
    """First matching field, else a date in the filename. Sent as UTC midnight so a
    UTC-day rounding on the server cannot shift the date (KST midnight would)."""
    for k in TIME_KEYS:
        v = fm.get(k, "")
        m = DATE.search(v)
        if m:
            return f"{m.group(0)}T00:00:00Z"
    m = DATE.search(path.name)
    return f"{m.group(0)}T00:00:00Z" if m else None


def files(root: Path):
    for sub, recursive, excl in SCOPE:
        base = root / sub
        if not base.is_dir():
            print(f"warn: missing {base}", file=sys.stderr)
            continue
        it = base.rglob("*.md") if recursive else base.glob("*.md")
        for p in sorted(it):
            if ".orca" in p.parts:
                continue
            if excl and re.search(excl, p.name):
                continue
            yield p


def push(base: str, source_id: str, token: str, payload: dict) -> str:
    req = urllib.request.Request(
        f"{base}/api/v1/sources/{source_id}/ingest",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("action", "?")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("AI_LAB_ROOT", DEFAULT_ROOT))
    ap.add_argument("--base", default=os.environ.get("UTOPIA_BASE", DEFAULT_BASE))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)

    token = os.environ.get("UTOPIA_INGEST_TOKEN", "")
    source_id = os.environ.get("UTOPIA_SOURCE_ID", "")
    if not a.dry_run and not (token and source_id):
        print("need UTOPIA_INGEST_TOKEN and UTOPIA_SOURCE_ID (or --dry-run)", file=sys.stderr)
        return 2

    counts: dict[str, int] = {}
    for p in files(root):
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(root).as_posix()
        payload = {
            "filename": p.name,
            "content": text,
            "external_id": rel,
        }
        t = doc_time(frontmatter(text), p)
        if t:
            payload["doc_time"] = t
        if a.dry_run:
            print(f"{t or '(no time)':<22} {rel}")
            continue
        try:
            action = push(a.base, source_id, token, payload)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            print(f"FAIL {rel}: HTTP {e.code} {body}", file=sys.stderr)
            action = "failed"
        counts[action] = counts.get(action, 0) + 1
        print(f"{action:<10} {rel}")
    if not a.dry_run:
        print(json.dumps(counts))
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
