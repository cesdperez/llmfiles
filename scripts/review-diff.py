#!/usr/bin/env python3
"""Writes a local review's diff and anchor map, run from the checkout under review.

<out>/diff.patch holds the change since the merge base with --base, uncommitted work and
untracked files included. <out>/anchors.tsv holds each added line as `path:line<TAB>text`.
Prints a JSON summary.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

HUNK = re.compile(r"^@@ -\S+ \+(\d+)")


def git(*args, ok_codes=(0,)):
    done = subprocess.run(["git", *args], capture_output=True, text=True)
    if done.returncode not in ok_codes:
        raise SystemExit(done.stderr.strip() or f"git {args[0]} failed")
    return done.stdout


def changes(base, *flags):
    tracked = git("diff", *flags, base)
    untracked = git("ls-files", "-z", "--others", "--exclude-standard").split("\0")
    # --no-index exits 1 when the files differ, which they always do here.
    added = [git("diff", "--no-index", *flags, "/dev/null", f, ok_codes=(0, 1)) for f in untracked if f]
    return tracked + "".join(added)


def anchors(unified0):
    path, line, rows, previous = None, 0, [], ""
    for text in unified0.splitlines():
        # An added line that starts with "++ " also reads "+++ "; only a header follows "--- ".
        header = text.startswith("+++ ") and previous.startswith("--- ")
        previous = text
        if header:
            # git appends a tab to a path that holds a space.
            path = text[6:].rstrip("\t")
        elif m := HUNK.match(text):
            line = int(m.group(1))
        elif text.startswith("+") and path is not None:
            if path != "dev/null":
                rows.append(f"{path}:{line}\t{text[1:]}")
            line += 1
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="the ref the change was cut from")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    merge_base = git("merge-base", "HEAD", args.base).strip()
    args.out.mkdir(parents=True, exist_ok=True)
    patch = changes(merge_base)
    rows = anchors(changes(merge_base, "--unified=0"))
    (args.out / "diff.patch").write_text(patch)
    (args.out / "anchors.tsv").write_text("".join(r + "\n" for r in rows))
    print(json.dumps({
        "merge_base": merge_base,
        "diff": str(args.out / "diff.patch"),
        "anchors": str(args.out / "anchors.tsv"),
        "added_lines": len(rows),
        "empty": not patch.strip(),
    }))


main()
