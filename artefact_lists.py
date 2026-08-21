#!/usr/bin/env python3
"""Write Artefacts lists into room and people notes.

Rooms list every artefact whose `room:` points at them. People notes list
artefacts they wrote (`from:`), received (`to:`) or appear in (`people:`),
grouped by role. Each list sits between markers, so re-running replaces it and
leaves the rest of the note alone; a note with nothing to list has any stale
block removed. Links are real text, so they work offline, count in the graph
and survive on GitHub.

    python3 artefact_lists.py            # update every room and person note
    python3 artefact_lists.py --check    # report drift, change nothing
    python3 artefact_lists.py --remove   # strip the blocks
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

VAULT = Path(__file__).parent
START, END = "<!-- artefacts:start -->", "<!-- artefacts:end -->"
HEADING = "## Artefacts"
LINK = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\]")
PATTERN = re.compile(
    rf"\n*{re.escape(HEADING)}\n{re.escape(START)}.*?{re.escape(END)}", re.S)

# frontmatter field -> subheading on the person's note, in display order
ROLES = [("from", "Wrote"), ("to", "Received"), ("people", "Appears in")]


def frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    return m.group(1) if m else ""


def field(fm: str, name: str) -> str:
    """Raw text of one frontmatter field, single value or YAML list."""
    m = re.search(rf"^{name}:(.*?)(?=^\w|\Z)", fm + "\n", flags=re.M | re.S)
    return m.group(1) if m else ""


def index(folder: str) -> tuple[set[str], dict[str, str]]:
    """Note names in a folder, and alias -> name."""
    known = {p.stem for p in (VAULT / folder).glob("*.md")}
    aliases: dict[str, str] = {}
    for p in (VAULT / folder).glob("*.md"):
        raw = field(frontmatter(p.read_text(encoding="utf-8")), "aliases")
        for a in re.findall(r"[-\[]\s*([^,\]\n]+)", raw):
            aliases[a.strip().strip('"')] = p.stem
    return known, aliases


def resolve(name: str, known: set[str], aliases: dict[str, str]) -> str | None:
    return name if name in known else aliases.get(name)


def collect() -> tuple[dict, dict, list]:
    rooms_known, rooms_alias = index("Rooms")
    ppl_known, ppl_alias = index("People")
    by_room: dict[str, list[str]] = defaultdict(list)
    by_person: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    missing: list[tuple[str, str, str]] = []

    for p in sorted((VAULT / "Artefacts").glob("*.md")):
        fm = frontmatter(p.read_text(encoding="utf-8"))
        for room in (r.strip() for r in LINK.findall(field(fm, "room"))):
            target = resolve(room, rooms_known, rooms_alias)
            (by_room[target].append(p.stem) if target
             else missing.append(("room", room, p.stem)))
        for key, _ in ROLES:
            for who in (w.strip() for w in LINK.findall(field(fm, key))):
                target = resolve(who, ppl_known, ppl_alias)
                (by_person[target][key].append(p.stem) if target
                 else missing.append((key, who, p.stem)))
    return by_room, by_person, missing


def render(names: list[str]) -> list[str]:
    return [f"- [[{n}]]" for n in sorted(set(names))]


def update(path: Path, lines: list[str], check: bool) -> bool:
    text = path.read_text(encoding="utf-8")
    if lines:
        block = "\n".join([HEADING, START] + lines + [END])
        new = (PATTERN.sub("\n\n" + block, text) if PATTERN.search(text)
               else text.rstrip() + "\n\n" + block + "\n")
    else:
        new = PATTERN.sub("", text).rstrip() + "\n"
    if new == text:
        return False
    if not check:
        path.write_text(new, encoding="utf-8")
    return True


def summary() -> str:
    """One line of room-completion counts, overall and per area."""
    per: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    done = total = 0
    for p in (VAULT / "Rooms").glob("*.md"):
        fm = frontmatter(p.read_text(encoding="utf-8"))
        area = (re.search(r"^area: (.+)$", fm, flags=re.M) or [None, "?"])[1].strip()
        written = "status: no notes yet" not in fm
        per[area][0] += written
        per[area][1] += 1
        done += written
        total += 1
    parts = " · ".join(f"{a} {w}/{n}" for a, (w, n) in sorted(per.items()))
    return f"rooms: {done}/{total} written up — {parts}"


def main() -> None:
    check, remove = "--check" in sys.argv, "--remove" in sys.argv
    by_room, by_person, missing = collect()
    changed = []

    for p in sorted((VAULT / "Rooms").glob("*.md")):
        lines = [] if remove else render(by_room.get(p.stem, []))
        if update(p, lines, check):
            changed.append(("Rooms", p.stem, len(lines)))

    for p in sorted((VAULT / "People").glob("*.md")):
        lines: list[str] = []
        if not remove:
            roles = by_person.get(p.stem, {})
            for key, label in ROLES:
                if roles.get(key):
                    lines += [f"### {label}"] + render(roles[key]) + [""]
            while lines and lines[-1] == "":
                lines.pop()
        if update(p, lines, check):
            changed.append(("People", p.stem, sum(1 for l in lines if l.startswith("- "))))

    verb = "would update" if check else ("stripped from" if remove else "updated")
    print(f"{verb} {len(changed)} notes")
    print(summary())
    for folder, name, count in changed:
        print(f"   {folder:8} {name:28} {count} artefacts")
    if missing:
        print("\npoints at a note that does not exist:")
        for key, name, artefact in missing:
            print(f"   {key}: [[{name}]]  <- {artefact}")


if __name__ == "__main__":
    main()
