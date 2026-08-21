---
type: index
---

# Blue Prince

Notes on Mount Holly. Start here.

## The mysteries

- [[Sigils]] — the notation, and the sigils found so far. **Next on the list**
- [[Erajan Language]] — the foreign tongue, its grammar, and an untranslated letter
- [[Sanctum Keys]] — 8 keys, 3 found
- [[Safes and Codes]] — every safe, every loose number
- [[Timeline]] — every date found, in order. 1987 is where it all happens
- [[The Redguard]] — what is it, and what were they investigating
- [[Red Letters]] — 8 letters by 8 different people
- [[House of Orinda]] — the Aries line

## Reference

- [[Keys]] — all key types
- [[Memos]] — which colours lie, and the Treasure Trove logic puzzle
- [[Terminals and Logins]] — SWANSONG, and the Blackbridge accounts
- [[Open Threads]] — what to do next

## Books

Ten read so far, all in `Artefacts/` with `kind: book` — listed in [[Library]].

## Run log

`log.csv` holds the per-run drafting log (day, room, position, exits, images).
It's read by `blue_prince.py` and `server.py` — not part of the vault.

## How this vault is organised

- `Rooms/` — one note per room. Frontmatter carries `area` and, for rooms with
  nothing written yet, `status: no notes yet`
- `People/` — one note per person, plus family grouping notes
- `Artefacts/` — one note per findable thing: notes, maps, photos, inscriptions.
  Multiple images per artefact is fine. Fields:
  - `kind` — book | email | key | letter | map | note | other | photo | sigil
  - `room` — **must be a link**, `"[[Vault]]"` with the quotes, or the room
    won't list it in its backlinks. Leave blank if genuinely unknown
  - `location` — where in the room (e.g. `Door 1`, `box 370`)
  - `opens` — for keys: what it unlocks, as a link. Gives the door or room
    a backlink to the key without needing an index
  - `from` / `to` — correspondence only. Add them when there's an obvious
    sender; don't stamp them on maps, boards or logs. Link where the person
    has a note, plain text while they're unidentified (e.g. `to: Uncle`)
  - `people` — who the artefact depicts or is about, as a YAML list. Use it
    for portraits, photos and group scenes; `from`/`to` already cover letters
  - `found` — day number, matching `log.csv`
  - `dated` — the date printed on the artefact itself
  - `magnified` — have you checked it with the magnifying glass?
    Renders as a checkbox. Find the outstanding ones with the search
    `[magnified:false]`
- `python3 artefact_lists.py` also prints how many rooms are written up,
  overall and per area — that count lives in the script, not in a note.
- Room and people notes carry an `## Artefacts` list between marker comments.
  Rooms come from `room:`; people are grouped **Wrote** / **Received** /
  **Appears in** from `from:`, `to:` and `people:`. Refresh with
  `python3 artefact_lists.py` (`--check` shows drift, `--remove` strips them).
  The markers mean re-running never touches your own prose.
- `Topics/` — cross-cutting threads that span rooms. Anything that's really
  a physical object belongs in `Artefacts/` instead
- `Templates/` — Templater stamps these on new notes by folder:
  `Artefacts/`, `Rooms/`, `People/`
- `images/` — filed screenshots, embedded with `![[name.png]]`. Gitignored
- `inbox/` — pasted images not yet filed. Empty means nothing outstanding.
  Move to `images/` **inside Obsidian** so embeds get rewritten. Gitignored
