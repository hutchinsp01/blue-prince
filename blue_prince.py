#!/usr/bin/env python3
"""Blue Prince room log.

Parse and query the day-by-day room-drafting log kept in ``log.csv``.

Typical use::

    from blue_prince import Log

    log = Log.load()          # reads log.csv next to this file
    print(log.days)           # [14]
    day = log[14]             # -> Day
    print(day.grid())         # the ascii map (same as grid.py)
    room = day.at(1, "C")     # -> Room (entrance-hall)
    print(room.derived_letter)  # 'f'  (from images "face"/"ace")
"""
from __future__ import annotations

import csv
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, fields
from pathlib import Path

COLUMNS = ("A", "B", "C", "D", "E")
OUTER_COLUMN = "O"  # off-grid slot for outer rooms, addressed O1, O2, ...
ROWS = range(9, 0, -1)  # top (9) to bottom (1), matching the printed map

DIRECTIONS = ("N", "E", "S", "W")
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
_STEP = {"N": (1, 0), "S": (-1, 0), "E": (0, 1), "W": (0, -1)}  # (row delta, column-index delta)

DEFAULT_LOG = Path(__file__).with_name("log.csv")


@dataclass(frozen=True)
class Room:
    """A single room as drafted on a given day — one row of the CSV."""

    day: int
    room: str
    column: str
    row: int
    entry: str = ""
    exits: str = ""
    image1: str = ""
    image2: str = ""
    letter: str = ""
    chess_colour: str = ""  # "", "white" or "black"
    chess_piece: str = ""   # "", "pawn", "knight", "bishop", "rook", "queen" or "king"

    @property
    def position(self) -> tuple[int, str]:
        """(row, column) grid coordinate, e.g. ``(1, "C")``."""
        return (self.row, self.column)

    @property
    def doors(self) -> set[str]:
        """The directions this room has a door on (parsed from ``exits``)."""
        return {c for c in self.exits.upper() if c in OPPOSITE}

    @property
    def derived_letter(self) -> str | None:
        """The letter implied by the image pair, or None if it can't be read.

        The puzzle hides a letter in the difference between the two images:
        e.g. "face"/"ace" -> "f", "dessert"/"desert" -> "s". Only works when
        one word is the other with a single extra character inserted.
        """
        long, short = sorted((self.image1, self.image2), key=len, reverse=True)
        if not short or len(long) - len(short) != 1:
            return None
        for i in range(len(long)):
            if long[:i] + long[i + 1:] == short:
                return long[i]
        return None

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "Room":
        """Build a Room from a ``csv.DictReader`` row, tolerating blanks."""
        clean = {k: (v or "").strip() for k, v in row.items() if k in _FIELD_NAMES}
        return cls(
            day=int(clean["day"]),
            room=clean["room"],
            column=clean["column"],
            row=int(clean["row"]),
            entry=clean.get("entry", ""),
            exits=clean.get("exits", ""),
            image1=clean.get("image1", ""),
            image2=clean.get("image2", ""),
            letter=clean.get("letter", ""),
            chess_colour=clean.get("chess_colour", ""),
            chess_piece=clean.get("chess_piece", ""),
        )

    def to_row(self) -> dict[str, object]:
        """This room as a dict keyed by CSV column, for writing back out."""
        return {name: getattr(self, name) for name in FIELDS}


FIELDS = tuple(f.name for f in fields(Room))  # canonical CSV column order
_FIELD_NAMES = set(FIELDS)


class Day:
    """Every room drafted on one day, with map-rendering helpers."""

    def __init__(self, day: int, rooms: Iterable[Room]):
        self.day = day
        self._by_position: dict[tuple[int, str], Room] = {r.position: r for r in rooms}

    def __iter__(self) -> Iterator[Room]:
        return iter(self._by_position.values())

    def __len__(self) -> int:
        return len(self._by_position)

    def __repr__(self) -> str:
        return f"Day(day={self.day}, rooms={len(self)})"

    @property
    def rooms(self) -> list[Room]:
        return list(self._by_position.values())

    def at(self, row: int, column: str) -> Room | None:
        """Room at a grid coordinate, or None if nothing was drafted there."""
        return self._by_position.get((row, column))

    def __getitem__(self, position: tuple[int, str]) -> Room | None:
        row, column = position
        return self.at(row, column)

    def grid(self) -> str:
        """Render the map as text (the original ``grid.py`` output)."""
        lines = ["   " + "  ".join(COLUMNS)]
        for row in ROWS:
            cells = []
            for col in COLUMNS:
                room = self.at(row, col)
                cell = " " if room is None else (room.letter or ".")
                cells.append(cell.center(2))
            lines.append(f"{row}  {' '.join(cells)}")
        outer = sorted(
            (r for r in self if r.column not in COLUMNS),
            key=lambda r: (r.column, r.row),
        )
        if outer:
            lines.append("")
            for r in outer:
                lines.append(f"{r.column}{r.row} {(r.letter or '.').center(2)} {r.room}")
        return "\n".join(lines)

    def neighbour(self, room: Room, direction: str) -> Room | None:
        """The room through ``room``'s door in ``direction``, or None if off-grid/empty."""
        if room.column not in COLUMNS:  # outer rooms sit off the grid, no neighbours
            return None
        d_row, d_col = _STEP[direction]
        col_index = COLUMNS.index(room.column) + d_col
        if not 0 <= col_index < len(COLUMNS):
            return None
        return self.at(room.row + d_row, COLUMNS[col_index])

    def door_status(self, room: Room, direction: str) -> str:
        """Classify one of ``room``'s doors as 'connected', 'blocked', or 'open'.

        connected — the neighbouring room has a matching door back.
        blocked   — a room is next door but has no door on the shared side.
        open      — the door leads to an empty cell or off the grid (the frontier).
        """
        other = self.neighbour(room, direction)
        if other is None:
            return "open"
        return "connected" if OPPOSITE[direction] in other.doors else "blocked"

    def connections(self) -> list[tuple[Room, Room]]:
        """Each pair of rooms joined by matching doors, listed once."""
        return [
            (room, other)
            for room in self
            for direction in room.doors & {"N", "E"}  # count each shared edge once
            if (other := self.neighbour(room, direction)) is not None
            and OPPOSITE[direction] in other.doors
        ]

    def open_doors(self) -> list[tuple[Room, str]]:
        """(room, direction) doors leading to an empty cell or off the grid."""
        return [(r, d) for r in self for d in r.doors if self.neighbour(r, d) is None]

    def blocked_doors(self) -> list[tuple[Room, str]]:
        """(room, direction) doors facing a neighbour that has no matching door back."""
        return [
            (r, d)
            for r in self
            for d in r.doors
            if (o := self.neighbour(r, d)) is not None and OPPOSITE[d] not in o.doors
        ]


class Log:
    """The whole room log — every room across every day."""

    def __init__(self, rooms: Iterable[Room]):
        self.rooms = list(rooms)

    @classmethod
    def load(cls, path: str | Path = DEFAULT_LOG) -> "Log":
        """Read a room log from a CSV file (defaults to ``log.csv``)."""
        with Path(path).open(newline="") as f:
            rooms = [
                Room.from_row(r)
                for r in csv.DictReader(f)
                if (r.get("day") or "").strip()
            ]
        return cls(rooms)

    def __iter__(self) -> Iterator[Room]:
        return iter(self.rooms)

    def __len__(self) -> int:
        return len(self.rooms)

    def __repr__(self) -> str:
        return f"Log(rooms={len(self)}, days={self.days})"

    @property
    def days(self) -> list[int]:
        return sorted({r.day for r in self.rooms})

    def day(self, day: int) -> Day:
        """The Day view for a given day number."""
        return Day(day, [r for r in self.rooms if r.day == day])

    def __getitem__(self, day: int) -> Day:
        return self.day(day)

    def filter(self, **criteria: object) -> list[Room]:
        """Rooms matching every field=value pair, e.g. ``log.filter(exits="N")``."""
        return [
            r
            for r in self.rooms
            if all(getattr(r, k) == v for k, v in criteria.items())
        ]

    def upsert(self, room: Room) -> None:
        """Add a room, replacing any existing one in the same day + grid cell."""
        key = (room.day, room.position)
        for i, existing in enumerate(self.rooms):
            if (existing.day, existing.position) == key:
                self.rooms[i] = room
                return
        self.rooms.append(room)

    def remove(self, day: int, column: str, row: int) -> bool:
        """Delete the room at a day + grid cell. Returns True if one was removed."""
        key = (day, (row, column))
        for i, r in enumerate(self.rooms):
            if (r.day, r.position) == key:
                del self.rooms[i]
                return True
        return False

    def save(self, path: str | Path = DEFAULT_LOG) -> None:
        """Write every room back to a CSV file (defaults to ``log.csv``)."""
        with Path(path).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            for room in self.rooms:
                writer.writerow(room.to_row())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "serve":
        from server import serve

        serve(int(argv[1])) if len(argv) > 1 else serve()
        return 0
    if len(argv) != 1:
        print(f"Usage: {Path(sys.argv[0]).name} <day> | serve [port]", file=sys.stderr)
        return 2
    print(Log.load()[int(argv[0])].grid())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
