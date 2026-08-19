#!/usr/bin/env python3
"""Report which images still need filing.

An image is "assigned" once an Artefacts/ note embeds it. Images embedded only
from a room or topic note are fine if they are scenery, but they are the pool
to draw new artefacts from.

    python3 unfiled.py
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

VAULT = Path(__file__).parent
IMAGE_DIRS = ("images", "inbox")
SKIP_DIRS = {".git", ".obsidian", "__pycache__", ".playwright-mcp", "Templates"}
EMBED = re.compile(r"!\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\]")


def notes() -> list[Path]:
    return [
        p for p in VAULT.rglob("*.md")
        if not any(part in SKIP_DIRS for part in p.relative_to(VAULT).parts)
    ]


def embeds_by_image() -> dict[str, list[Path]]:
    """image filename (lowercased) -> notes embedding it."""
    found: dict[str, list[Path]] = defaultdict(list)
    for note in notes():
        for m in EMBED.finditer(note.read_text(encoding="utf-8")):
            # embeds may carry a folder prefix: ![[images/foo.png]]
            key = m.group(1).strip().rsplit("/", 1)[-1].lower()
            found[key].append(note.relative_to(VAULT))
    return found


def images() -> dict[str, Path]:
    out = {}
    for d in IMAGE_DIRS:
        folder = VAULT / d
        if folder.is_dir():
            for p in sorted(folder.iterdir()):
                if p.is_file() and not p.name.startswith("."):
                    out[p.name.lower()] = p.relative_to(VAULT)
    return out


def main() -> None:
    used, imgs = embeds_by_image(), images()
    inbox, unassigned, assigned, orphans = [], [], [], []

    for key, path in imgs.items():
        holders = used.get(key, [])
        artefacts = [h for h in holders if h.parts[0] == "Artefacts"]
        if path.parts[0] == "inbox" and not artefacts:
            inbox.append((path, holders))
        elif artefacts:
            assigned.append(path)
        elif holders:
            unassigned.append((path, holders))
        else:
            orphans.append(path)

    if inbox:
        print(f"\nINBOX — {len(inbox)} pasted, no artefact yet")
        for p, h in inbox:
            where = f"  (embedded in {h[0]})" if h else "  (not embedded anywhere)"
            print(f"   {p.name}{where}")

    if unassigned:
        verbose = "-v" in sys.argv
        print(f"\nNO ARTEFACT — {len(unassigned)} embedded only outside Artefacts/")
        print("   fine if it is scenery; otherwise these are your candidates")
        if verbose:
            for p, h in sorted(unassigned):
                print(f"   {p.name:38} -> {', '.join(str(x) for x in h[:2])}")
        else:
            groups: dict[str, tuple[int, set[str]]] = {}
            for p, h in sorted(unassigned):
                key = re.sub(r"[-_]?\d+$", "", p.stem) or p.stem
                n, where = groups.get(key, (0, set()))
                groups[key] = (n + 1, where | {str(x) for x in h})
            print(f"   {len(groups)} likely artefacts, -v for every file\n")
            for key, (n, where) in sorted(groups.items()):
                count = f"({n} images)" if n > 1 else ""
                dest = ", ".join(sorted(where)[:2])
                print(f"   {key:32} {count:12} -> {dest}")

    if orphans:
        print(f"\nORPHANS — {len(orphans)} in no note at all")
        for p in sorted(orphans):
            print(f"   {p.name}")

    print(f"\nassigned to an artefact: {len(assigned)} / {len(imgs)}")


if __name__ == "__main__":
    main()
