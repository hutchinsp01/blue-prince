---
type: index
---

# Blue Prince

Notes on Mount Holly. Start here.

## Indexes

- [[Rooms Index]] — every room, grouped by house / grounds / underground
- [[People Index]] — everyone named so far

## The mysteries

- [[Sigils]] — the notation, and the sigils found so far. **Next on the list**
- [[Erajan Language]] — the foreign tongue, its grammar, and an untranslated letter
- [[Sanctum Keys]] — 8 keys, 3 found
- [[Safes and Codes]] — every safe, every loose number
- [[Timeline]] — every date found, in order. 1987 is where it all happens
- [[The Redguard]] — what is it, and what were they investigating
- [[Red Notes]] — 8 letters by 8 different people
- [[House of Orinda]] — the Aries line
- [[The Red Prince]] — person or book?

## Reference

- [[Keys]] — all key types
- [[Memos]] — which colours lie, and the Treasure Trove logic puzzle
- [[Terminals and Logins]] — SWANSONG, and the Blackbridge accounts
- [[House Rules]] — house-wide mechanics
- [[Open Threads]] — what to do next

## Books

Ten read so far in the [[Library]].

## Run log

`log.csv` holds the per-run drafting log (day, room, position, exits, images).
It's read by `blue_prince.py` and `server.py` — not part of the vault.

## How this vault is organised

- `Rooms/` — one note per room. Frontmatter carries `area` and, for rooms with
  nothing written yet, `status: no notes yet`
- `People/` — one note per person, plus family grouping notes
- `Books/` — one note per book read in the [[Library]]
- `Topics/` — cross-cutting threads that span rooms
- `Indexes/` — generated lists
- `images/` — screenshots, embedded with `![[name.png]]`. Gitignored
