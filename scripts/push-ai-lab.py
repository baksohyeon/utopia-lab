#!/usr/bin/env python3
"""Push the Dionz ai-lab markdown corpus into a Utopia API source.

Read-only on ai-lab, stdlib only, no state file: Utopia already answers
`unchanged` for identical content, so every run simply pushes everything and
lets the server decide what is new. Identity is the repo-relative path.

    UTOPIA_INGEST_TOKEN=utp_... UTOPIA_SOURCE_ID=<uuid> python3 scripts/push-ai-lab.py --corpus ai-lab
    python3 scripts/push-ai-lab.py --corpus ideation-v1 --dry-run   # list files and doc_time, no network

Each corpus is its own Utopia API source (own token, own source id).

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

DEFAULT_BASE = "http://localhost:1516"
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
KO_DATE = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일")

# One entry per corpus. `scope` is (subdir, recursive, excluded-path regex); `time_keys`
# is the frontmatter key that is "the document's time", in priority order. Both agreed
# with the ai-lab maintainer on 2026-09-04; ideation-v1 is an Obsidian vault whose
# Notion mirror (_Source-Notion) is the body of fact and _Knowledge the interpretation.
# Hub pages, Dataview dashboards, templates, prompts, sync logs and _Active/ (mirrors
# ai-lab, would double-ingest) are out.
CORPORA = {
    "ai-lab": {
        "root": "/Users/cnai/dev/work/Dionz/ai-lab",
        "scope": [
            ("docs/journal/2026", True, r"\.raw\.md$"),
            ("docs/journal/postmortem", False, r"/README\.md$"),
            ("docs/decisions", False, r"/README\.md$"),
        ],
        # `created` is what the journals used before 35dd92f; harmless to keep
        "time_keys": ("decided_at", "created_at", "created", "updated_at"),
    },
    "ideation-v1": {
        "root": "/Users/cnai/dev/work/Dionz/ideation-v1",
        "scope": [
            ("dionz/_Source-Notion", True, r"/(_deleted|_unfiled)/|/_sync-log\.md$"),
            ("dionz/_Knowledge", True, r"/_loop/"),
        ],
        "time_keys": ("updated_at", "created_at"),
    },
}


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


def doc_time(fm: dict, path: Path, time_keys, body: str = ""):
    """First matching field, else a date in the filename. Sent as UTC midnight so a
    UTC-day rounding on the server cannot shift the date (KST midnight would)."""
    for k in time_keys:
        v = fm.get(k, "")
        m = DATE.search(v)
        if m:
            return f"{m.group(0)}T00:00:00Z"
    m = DATE.search(path.name)
    if m:
        return f"{m.group(0)}T00:00:00Z"
    # Notion mirrors in ideation-v1 often carry no date in frontmatter but open with
    # a line like "업데이트: 2026년 6월 29일 오후 2:08". Read the first lines of the body
    # for that before giving up; no date at all means the server uses ingestion time.
    head = "\n".join(body.splitlines()[:40])
    m = KO_DATE.search(head) or DATE.search(head)
    if not m:
        return None
    if m.re is KO_DATE:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}T00:00:00Z"
    return f"{m.group(0)}T00:00:00Z"


def files(root: Path, scope):
    for sub, recursive, excl in scope:
        base = root / sub
        if not base.is_dir():
            print(f"warn: missing {base}", file=sys.stderr)
            continue
        it = base.rglob("*.md") if recursive else base.glob("*.md")
        for p in sorted(it):
            if ".orca" in p.parts or ".obsidian" in p.parts:
                continue
            if excl and re.search(excl, "/" + p.relative_to(root).as_posix()):
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
    ap.add_argument("--corpus", choices=sorted(CORPORA), default="ai-lab")
    ap.add_argument("--root", help="override the corpus root")
    ap.add_argument("--base", default=os.environ.get("UTOPIA_BASE", DEFAULT_BASE))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    corpus = CORPORA[a.corpus]
    root = Path(a.root or corpus["root"])

    token = os.environ.get("UTOPIA_INGEST_TOKEN", "")
    source_id = os.environ.get("UTOPIA_SOURCE_ID", "")
    if not a.dry_run and not (token and source_id):
        print("need UTOPIA_INGEST_TOKEN and UTOPIA_SOURCE_ID (or --dry-run)", file=sys.stderr)
        return 2

    counts: dict[str, int] = {}
    for p in files(root, corpus["scope"]):
        text = p.read_text(encoding="utf-8")
        rel = p.relative_to(root).as_posix()
        payload = {
            "filename": p.name,
            "content": text,
            # prefixed so two corpora can never collide on a relative path
            "external_id": f"{a.corpus}:{rel}",
        }
        t = doc_time(frontmatter(text), p, corpus["time_keys"], text)
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
