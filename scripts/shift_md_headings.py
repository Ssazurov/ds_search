"""Shift Markdown heading levels in data/raw so the shallowest sub-heading is ##.

Usage: python scripts/shift_md_headings.py [--apply] [domain_dir ...]
Dry-run by default. Prints changed files (relative to data/raw).
"""
import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
HEAD = re.compile(r"^(#{2,6})(?=\s)", re.M)


def shift(md: str) -> str:
    parts = re.split(r"(```.*?```|~~~.*?~~~)", md, flags=re.S)
    levels = [len(m.group(1)) for p in parts[::2] for m in HEAD.finditer(p)]
    if not levels or min(levels) <= 2:
        return md
    d = min(levels) - 2
    parts[::2] = [HEAD.sub(lambda m: "#" * (len(m.group(1)) - d), p) for p in parts[::2]]
    return "".join(parts)


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--apply"]
    apply = "--apply" in sys.argv
    dirs = [RAW / a for a in args] if args else [p for p in RAW.iterdir() if p.is_dir()]
    n = 0
    for d in dirs:
        for f in d.rglob("*.md"):
            old = f.read_text(encoding="utf-8")
            new = shift(old)
            if new != old:
                n += 1
                print(f.relative_to(RAW))
                if apply:
                    f.write_text(new, encoding="utf-8")
    print(f"changed: {n}", "(applied)" if apply else "(dry-run)")


if __name__ == "__main__":
    main()
