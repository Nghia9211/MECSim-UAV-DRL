"""Markdown link tooling: list broken relative links, or move tracked .md files and rewrite links.

  python scripts/md_links.py check                     # print broken relative links (JSON)
  python scripts/md_links.py move DEST FILE [FILE...]  # git mv FILEs into DEST and fix links everywhere

Links inside fenced code blocks and http(s)/mailto links are ignored. Rewriting keeps the
same target path; links that were already broken stay broken (and are reported).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)(\))")
FENCE = re.compile(r"```[\s\S]*?```")


def tracked_markdown():
    out = subprocess.check_output(["git", "ls-files", "*.md"], cwd=ROOT, text=True)
    return [ROOT / p for p in out.splitlines() if (ROOT / p).exists()]


def external(target):
    return re.match(r"^(https?:|mailto:|#)", target) is not None


def split(target):
    path, sep, anchor = target.partition("#")
    return path, sep + anchor


def broken_links():
    result = []
    for md in tracked_markdown():
        text = FENCE.sub("", md.read_text(encoding="utf-8"))
        for m in LINK.finditer(text):
            target = m.group(2)
            if external(target):
                continue
            path, _ = split(target)
            if path and not (md.parent / path).exists():
                result.append((md.relative_to(ROOT).as_posix(), target))
    return result


def rewrite(text, old_dir, new_dir, moved):
    """Rewrite links of a file that lived in old_dir and now lives in new_dir."""
    parts = re.split(r"(```[\s\S]*?```)", text)
    for i in range(0, len(parts), 2):  # even indices are outside code fences
        def fix(m):
            target = m.group(2)
            if external(target):
                return m.group(0)
            path, anchor = split(target)
            if not path:
                return m.group(0)
            absolute = Path(os.path.normpath(old_dir / path))
            if old_dir == new_dir and absolute not in moved:
                return m.group(0)  # neither this file nor the target moved: keep the text as is
            absolute = moved.get(absolute, absolute)
            new = os.path.relpath(absolute, new_dir).replace(os.sep, "/")
            return m.group(1) + new + anchor + m.group(3)
        parts[i] = LINK.sub(fix, parts[i])
    return "".join(parts)


def move(dest, files):
    dest = (ROOT / dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    moved = {}
    for f in files:
        src = (ROOT / f).resolve()
        moved[src] = dest / src.name
    for src, dst in moved.items():
        if dst.exists():
            raise SystemExit(f"Destination exists: {dst}")
    for md in tracked_markdown():
        md = md.resolve()
        with open(md, encoding="utf-8", newline="") as f:  # keep original line endings
            text = f.read()
        new_location = moved.get(md, md)
        new_text = rewrite(text, md.parent, new_location.parent, moved)
        if new_text != text:
            with open(md, "w", encoding="utf-8", newline="") as f:
                f.write(new_text)
    for src, dst in moved.items():
        subprocess.check_call(["git", "mv", str(src), str(dst)], cwd=ROOT)


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "check":
        print(json.dumps(broken_links(), indent=1))
    elif len(sys.argv) >= 4 and sys.argv[1] == "move":
        move(sys.argv[2], sys.argv[3:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
