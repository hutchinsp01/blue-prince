#!/usr/bin/env python3
"""Local web form for entering rooms into log.csv.

Run:  python blue_prince.py serve   (or python -m blue_prince serve)
Then open http://127.0.0.1:8765 in a browser.

Click a grid cell, click each door (off -> exit -> entrance) on the room
diagram, right-click a door to mark it locked/security, type the room name,
and hit Save. Stdlib only.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from blue_prince import (COLUMNS, DEFAULT_LOG, OUTER_COLUMN, Log, Room,
                         add_room_name, load_room_names)

DEFAULT_PORT = 8765  # 8000 is often taken (Docker/Django); pick something quieter


def build_state(day: int | None = None) -> dict[str, object]:
    log = Log.load()
    days = log.days
    if day is None:
        day = days[-1] if days else 14
    view = log.day(day)
    grid_cols = set(COLUMNS)
    rooms = []
    for r in view:
        data = r.to_row()
        if r.column in grid_cols:
            data["door_status"] = {d: view.door_status(r, d) for d in sorted(r.doors)}
        else:  # outer room: off-grid, connections not modelled
            data["door_status"] = {d: "outer" for d in sorted(r.doors)}
        rooms.append(data)

    # Chess prefill is by ROOM NAME, not position: a given room always holds the
    # same piece across days. Map each name to its most recently recorded piece.
    chess_by_room: dict[str, dict[str, object]] = {}
    for r in log.rooms:
        piece = r.chess_piece.strip().lower()
        name = r.room.strip().lower()
        if not piece or not name:
            continue
        prev = chess_by_room.get(name)
        if prev is None or r.day >= prev["day"]:
            chess_by_room[name] = {"chess_colour": r.chess_colour.strip().lower(),
                                   "chess_piece": piece, "day": r.day}

    return {"day": day, "days": days, "columns": list(COLUMNS), "rooms": rooms,
            "chess_by_room": chess_by_room, "room_names": load_room_names()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # silence per-request noise
        pass

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: object, status: int = 200) -> None:
        self._send(json.dumps(obj).encode(), "application/json", status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(PAGE.encode(), "text/html; charset=utf-8")
        elif parsed.path == "/api/state":
            query = parse_qs(parsed.query)
            day = int(query["day"][0]) if "day" in query else None
            self._send_json(build_state(day))
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/room":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        try:
            day = int(payload["day"])
            row = int(payload["row"])
            column = str(payload["column"]).upper()
        except (KeyError, ValueError, TypeError):
            self._send_json({"error": "day, column and row are required"}, 400)
            return
        if column not in COLUMNS and column != OUTER_COLUMN:
            self._send_json({"error": f"column must be one of {list(COLUMNS)} or {OUTER_COLUMN}"}, 400)
            return

        log = Log.load()
        if payload.get("_delete"):
            log.remove(day, column, row)
            print(f"deleted: day {day} {column}{row}")
        else:
            # The form no longer edits images/letter (that puzzle is done);
            # carry stored values through so re-saving a cell keeps them.
            existing = log.day(day).at(row, column)
            room = Room(
                day=day,
                room=str(payload.get("room", "")).strip(),
                column=column,
                row=row,
                entry=str(payload.get("entry", "")).strip().upper(),
                exits=str(payload.get("exits", "")).strip().upper(),
                image1=existing.image1 if existing else "",
                image2=existing.image2 if existing else "",
                letter=existing.letter if existing else "",
                chess_colour=str(payload.get("chess_colour", "")).strip().lower(),
                chess_piece=str(payload.get("chess_piece", "")).strip().lower(),
                locked=str(payload.get("locked", "")).strip().upper(),
                security=str(payload.get("security", "")).strip().upper(),
            )
            log.upsert(room)
            if add_room_name(room.room):
                print(f"new room name recorded: {room.room}")
            print(f"saved: day {day} {column}{row} = {room.room or '(unnamed)'}")
        log.save()
        self._send_json(build_state(day))


def serve(port: int = DEFAULT_PORT) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Blue Prince entry form  ->  http://127.0.0.1:{port}   (Ctrl-C to stop)", flush=True)
    print(f"Writing to {DEFAULT_LOG}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blue Prince — room log</title>
<style>
  * { box-sizing: border-box; }
  body { font: 14px/1.4 system-ui, sans-serif; margin: 0; color: #1a2233; background: #eef1f6; }
  header { display: flex; align-items: center; gap: 12px; padding: 12px 20px; background: #25406b; color: #fff; }
  header h1 { font-size: 16px; margin: 0 auto 0 0; }
  header input { width: 60px; padding: 4px 6px; border: none; border-radius: 4px; }
  header .hint { color: #b9c6e0; }
  header button { padding: 5px 12px; border: none; border-radius: 5px; cursor: pointer; background: #f0a500; color: #1a2233; font-weight: 600; }
  main { display: flex; gap: 24px; padding: 20px; align-items: flex-start; }
  .hint { color: #6b7488; font-size: 12px; }
  table.grid { border-collapse: separate; border-spacing: 4px; }
  table.grid th { color: #6b7488; font-weight: 600; width: 34px; text-align: center; }
  button.cell { position: relative; width: 34px; height: 34px; border: 1px solid #c3cad8; background: #fff; border-radius: 6px; font: 600 11px monospace; cursor: pointer; color: #1a2233; padding: 0; }
  button.cell.filled { background: #dbe7ff; border-color: #9db8ee; }
  button.cell.sel { outline: 3px solid #f0a500; }
  button.cell:hover { border-color: #25406b; }
  .doormark { position: absolute; background: #b7bfce; border-radius: 2px; pointer-events: none; }
  .doormark.dm-N { top: -3px; left: 50%; transform: translateX(-50%); width: 12px; height: 5px; }
  .doormark.dm-S { bottom: -3px; left: 50%; transform: translateX(-50%); width: 12px; height: 5px; }
  .doormark.dm-E { right: -3px; top: 50%; transform: translateY(-50%); width: 5px; height: 12px; }
  .doormark.dm-W { left: -3px; top: 50%; transform: translateY(-50%); width: 5px; height: 12px; }
  .doormark.st-connected { background: #2f9d57; }
  .doormark.st-blocked { background: #d64545; }
  .doormark.st-open { background: #e0a63a; }
  .doormark.lk-locked { background: #8a4fd0; }
  .doormark.lk-security { background: #3552c4; }
  .doormark.dm-entry { outline: 2px solid #25406b; }
  .maplegend { margin-top: 6px; }
  .mm { display: inline-block; width: 14px; height: 6px; border-radius: 2px; vertical-align: middle; margin: 0 4px 0 12px; }
  .mm:first-child { margin-left: 0; }
  .mm.st-connected { background: #2f9d57; }
  .mm.st-blocked { background: #d64545; }
  .mm.st-open { background: #e0a63a; }
  .mm.lk-locked { background: #8a4fd0; }
  .mm.lk-security { background: #3552c4; }
  .outerbox { display: flex; align-items: center; gap: 10px; margin-top: 16px; }
  .outerlabel { color: #6b7488; font-size: 12px; font-weight: 600; }
  .ocellwrap { display: inline-flex; flex-direction: column; align-items: center; gap: 4px; }
  .olabel { font: 600 10px monospace; color: #6b7488; }
  #formPane { background: #fff; border: 1px solid #d5dbe6; border-radius: 10px; padding: 18px; width: 340px; flex: 0 0 340px; }
  #formPane h2 { font-size: 15px; margin: 0 0 12px; }
  #formPane label { display: block; margin: 10px 0; font-size: 13px; color: #48506a; }
  #formPane input[type=text] { width: 100%; padding: 6px 8px; border: 1px solid #c3cad8; border-radius: 6px; font: 14px system-ui; margin-top: 3px; }
  #room.unknown { background: #fff3d6; border-color: #e0a63a; }
  .suggestwrap { position: relative; display: block; }
  .suggest { position: absolute; top: 100%; left: 0; right: 0; z-index: 10; display: none;
             background: #fff; border: 1px solid #c3cad8; border-radius: 6px; margin-top: 2px;
             max-height: 220px; overflow-y: auto; box-shadow: 0 4px 12px rgba(26, 34, 51, .15); }
  .suggest.open { display: block; }
  .suggest .opt { padding: 5px 9px; cursor: pointer; font-size: 13px; }
  .suggest .opt.hi { background: #dbe7ff; }
  .suggest .opt b { color: #25406b; }
  .chessrow select.prefilled { background: #fffbe6; }
  #chessNote:not(:empty) { color: #9a7b1a; margin: 8px 0; }
  .doorwrap { margin: 16px 0; }
  .chesswrap { margin: 16px 0; }
  .chessrow { display: flex; gap: 8px; margin-top: 6px; }
  .chessrow select { flex: 1; padding: 6px 8px; border: 1px solid #c3cad8; border-radius: 6px; font: 14px system-ui; background: #fff; color: #1a2233; }
  .clabel { font-size: 12px; color: #6b7488; margin-bottom: 6px; }
  .compass { display: grid; grid-template-columns: repeat(3, 44px); grid-template-rows: repeat(3, 44px); gap: 4px; }
  .compass .croom { display: flex; align-items: center; justify-content: center; color: #aeb6c9; grid-area: 2 / 2; }
  button.door { border: 1px solid #c3cad8; background: #f5f7fb; border-radius: 6px; cursor: pointer; font: 600 14px system-ui; color: #48506a; position: relative; }
  button.door:hover { border-color: #25406b; }
  button.door.st-exit { background: #dbe7ff; border-color: #4f7ae0; color: #1e3a86; }
  button.door.st-entry { background: #c9f0d4; border-color: #2f9d57; color: #166534; box-shadow: inset 0 0 0 2px #2f9d57; }
  button.door.st-entry::after { content: "in"; position: absolute; top: 1px; right: 3px; font: 700 9px system-ui; color: #2f9d57; }
  button.door.lk-locked::before { content: "🔒"; position: absolute; top: 1px; left: 2px; font-size: 10px; }
  button.door.lk-security::before { content: "🛡"; position: absolute; top: 1px; left: 2px; font-size: 10px; }
  .swatch.lk-locked { background: #8a4fd0; border-color: #8a4fd0; }
  .swatch.lk-security { background: #3552c4; border-color: #3552c4; }
  .legend { margin-top: 8px; }
  .swatch { display: inline-block; width: 12px; height: 12px; border-radius: 3px; vertical-align: middle; margin: 0 3px 0 12px; border: 1px solid #c3cad8; }
  .swatch:first-child { margin-left: 0; }
  .swatch.st-exit { background: #dbe7ff; border-color: #4f7ae0; }
  .swatch.st-entry { background: #c9f0d4; border-color: #2f9d57; }
  .actions { display: flex; align-items: center; gap: 10px; margin-top: 16px; }
  button.primary { background: #25406b; color: #fff; border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font: 600 14px system-ui; }
  button.danger { background: #fff; color: #b23; border: 1px solid #e2b6bd; padding: 8px 14px; border-radius: 6px; cursor: pointer; }
  .status { font-size: 13px; color: #166534; }
  .summary { background: #f5f7fb; border: 1px solid #e2e6ef; border-radius: 6px; padding: 8px 10px; font: 12px/1.5 monospace; color: #48506a; margin-top: 16px; white-space: pre; }
  .checklist { margin-top: 16px; background: #fff; border: 1px solid #d5dbe6; border-radius: 8px; padding: 12px 14px; max-width: 300px; }
  .cl-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; color: #25406b; }
  table.cl { border-collapse: collapse; width: 100%; }
  table.cl th { font: 600 12px system-ui; color: #6b7488; text-align: center; padding: 3px 6px; }
  table.cl tbody th { text-align: left; color: #48506a; }
  table.cl td { text-align: center; padding: 3px 6px; font: 600 14px system-ui; cursor: default; }
  table.cl td.on { color: #2f9d57; }
  table.cl td.off { color: #ccd3e0; font-weight: 400; }
  .cl-list { list-style: none; margin: 10px 0 0; padding: 8px 0 0; border-top: 1px solid #eef1f6; font-size: 12px; line-height: 1.5; color: #48506a; }
  .cl-list li { padding: 1px 0; }
  .cl-list b { color: #25406b; font-weight: 600; }
  .cl-empty { margin-top: 8px; }
</style>
</head>
<body>
<header>
  <h1>Blue Prince — room log</h1>
  <label style="color:#fff">Day <input id="day" type="number" min="1" value="14"></label>
  <button id="load">Load</button>
</header>
<main>
  <section>
    <div id="grid"></div>
    <p class="hint">Click a cell to edit that spot. Marks on a cell's sides are its doors.</p>
    <div class="maplegend hint">
      <span class="mm st-connected"></span>connected
      <span class="mm st-blocked"></span>blocked (no door back)
      <span class="mm st-open"></span>open (empty next door)
      <span class="mm lk-locked"></span>locked
      <span class="mm lk-security"></span>security
    </div>
    <div id="chessChecklist" class="checklist"></div>
  </section>
  <section id="formPane">
    <h2 id="cellTitle">No cell selected</h2>
    <label>Room name
      <span class="suggestwrap">
        <input id="room" type="text" placeholder="entrance-hall" autocomplete="off">
        <div id="roomSuggest" class="suggest"></div>
      </span>
      <span class="hint" id="roomHint"></span>
    </label>
    <div class="doorwrap">
      <div class="clabel">Doors &middot; click a side: off &rarr; exit &rarr; entrance &middot; right-click: none &rarr; &#128274; locked &rarr; &#128737; security</div>
      <div class="compass" id="doors"></div>
      <div class="legend hint">
        <span class="swatch st-exit"></span>exit
        <span class="swatch st-entry"></span>entrance (max one)
        <span class="swatch lk-locked"></span>locked
        <span class="swatch lk-security"></span>security
      </div>
    </div>
    <div class="chesswrap">
      <div class="clabel">Chess piece</div>
      <div class="chessrow">
        <select id="chessColour">
          <option value="">— colour —</option>
          <option value="white">White</option>
          <option value="black">Black</option>
        </select>
        <select id="chessPiece">
          <option value="">— piece —</option>
          <option value="pawn">Pawn</option>
          <option value="knight">Knight</option>
          <option value="bishop">Bishop</option>
          <option value="rook">Rook</option>
          <option value="queen">Queen</option>
          <option value="king">King</option>
        </select>
      </div>
      <div id="chessNote" class="hint"></div>
    </div>
    <div class="actions">
      <button id="save" class="primary">Save</button>
      <button id="delete" class="danger">Delete</button>
      <span id="status" class="status"></span>
    </div>
    <div id="summary" class="summary"></div>
  </section>
</main>
<script>
const DIRS = ["N", "E", "S", "W"];
const CHESS_PIECES = ["king", "queen", "rook", "bishop", "knight", "pawn"];
const CHESS_COLOURS = ["white", "black"];
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const esc = s => s.replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const initials = n => (n || "").split(/[^a-z0-9]+/i).filter(Boolean)
  .map(w => w[0]).join("").toUpperCase() || "·";
const $ = id => document.getElementById(id);
let state = null;
let sel = null;                                  // {column, row}
let doors = { N: "", E: "", S: "", W: "" };      // "" | "exit" | "entry"
let locks = { N: "", E: "", S: "", W: "" };      // "" | "locked" | "security"
let chessAuto = true;                            // is the chess piece tracking the room name?

async function load(day) {
  const url = "/api/state" + (day != null ? "?day=" + day : "");
  state = await (await fetch(url)).json();
  $("day").value = state.day;
  renderGrid();
  if (sel) selectCell(sel.column, sel.row);
}

function roomAt(col, row) {
  return state.rooms.find(r => r.column === col && r.row === row) || null;
}

function cellButton(col, row) {
  const r = roomAt(col, row);
  const cls = ["cell"];
  if (r) cls.push("filled");
  if (sel && sel.column === col && sel.row === row) cls.push("sel");
  const mark = r ? initials(r.room) : "";
  const title = r ? r.room : "";
  let doorHtml = "";
  if (r && r.door_status) {
    for (const [d, st] of Object.entries(r.door_status)) {
      const entryCls = d === r.entry ? " dm-entry" : "";
      const lockCls = (r.security || "").includes(d) ? " lk-security"
                    : (r.locked || "").includes(d) ? " lk-locked" : "";
      doorHtml += `<span class="doormark dm-${d} st-${st}${entryCls}${lockCls}"></span>`;
    }
  }
  return `<button class="${cls.join(" ")}" data-col="${col}" data-row="${row}" title="${title}">${mark}${doorHtml}</button>`;
}

function outerRows() {
  return [1];  // only O1 for now (add more rows here later if needed)
}

function renderGrid() {
  let html = '<table class="grid"><thead><tr><th></th>';
  for (const c of state.columns) html += `<th>${c}</th>`;
  html += "</tr></thead><tbody>";
  for (let row = 9; row >= 1; row--) {
    html += `<tr><th>${row}</th>`;
    for (const c of state.columns) html += `<td>${cellButton(c, row)}</td>`;
    html += "</tr>";
  }
  html += "</tbody></table>";
  let outer = '<div class="outerbox"><span class="outerlabel">Outer</span>';
  for (const row of outerRows()) {
    outer += `<span class="ocellwrap">${cellButton("O", row)}<span class="olabel">O${row}</span></span>`;
  }
  outer += "</div>";
  $("grid").innerHTML = html + outer;
  $("grid").querySelectorAll("button.cell").forEach(b => {
    b.onclick = () => selectCell(b.dataset.col, parseInt(b.dataset.row));
  });
  renderChessChecklist();
}

function renderChessChecklist() {
  const el = $("chessChecklist");
  if (!el || !state) { if (el) el.innerHTML = ""; return; }
  // colour|piece -> [room labels],  and piece -> [labels] when colour missing
  const seen = {}, noColour = {};
  let total = 0;
  for (const r of state.rooms) {
    const piece = (r.chess_piece || "").toLowerCase();
    if (!piece) continue;
    total++;
    const colour = (r.chess_colour || "").toLowerCase();
    const label = r.room || (r.column + r.row);
    if (colour === "white" || colour === "black") {
      (seen[colour + "|" + piece] ??= []).push(label);
    } else {
      (noColour[piece] ??= []).push(label);
    }
  }
  // grid: show the COUNT in each cell (not just a tick), · when none seen
  let html = `<div class="cl-title">Chess seen — day ${state.day} <span class="hint">(${total} total)</span></div>`;
  html += '<table class="cl"><thead><tr><th></th>';
  for (const c of CHESS_COLOURS) html += `<th>${cap(c)}</th>`;
  html += "</tr></thead><tbody>";
  for (const p of CHESS_PIECES) {
    html += `<tr><th>${cap(p)}</th>`;
    for (const c of CHESS_COLOURS) {
      const rooms = seen[c + "|" + p];
      html += rooms
        ? `<td class="on" title="${rooms.join(", ")}">${rooms.length}</td>`
        : `<td class="off">·</td>`;
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  // always-visible breakdown (no hover needed) — count + rooms for each piece seen
  const lines = [];
  for (const c of CHESS_COLOURS) for (const p of CHESS_PIECES) {
    const rooms = seen[c + "|" + p];
    if (rooms) lines.push(`<li><b>${cap(c)} ${p}</b> &times;${rooms.length} — ${rooms.join(", ")}</li>`);
  }
  for (const [p, rooms] of Object.entries(noColour)) {
    lines.push(`<li><b>${p}</b> <span class="hint">(no colour)</span> &times;${rooms.length} — ${rooms.join(", ")}</li>`);
  }
  html += lines.length
    ? `<ul class="cl-list">${lines.join("")}</ul>`
    : `<div class="cl-empty hint">Nothing logged this day yet.</div>`;
  el.innerHTML = html;
}

function buildCompass() {
  const el = $("doors");
  el.innerHTML = "";
  const room = document.createElement("div");
  room.className = "croom";
  room.textContent = "▢";
  el.appendChild(room);
  const area = { N: "1 / 2", E: "2 / 3", S: "3 / 2", W: "2 / 1" };
  for (const d of DIRS) {
    const btn = document.createElement("button");
    btn.className = "door";
    btn.textContent = d;
    btn.dataset.dir = d;
    btn.style.gridArea = area[d];
    btn.onclick = () => cycleDoor(d);
    btn.oncontextmenu = e => { e.preventDefault(); cycleLock(d); };
    el.appendChild(btn);
  }
}

function cycleDoor(d) {
  const next = { "": "exit", "exit": "entry", "entry": "" }[doors[d]];
  if (next === "entry") {
    // only one entrance: demote any current entrance back to a plain exit
    for (const k of DIRS) if (doors[k] === "entry") doors[k] = "exit";
  }
  doors[d] = next;
  if (next === "") locks[d] = "";  // no door, nothing to lock
  refreshDoors();
  updateSummary();
}

function cycleLock(d) {
  if (doors[d] === "") doors[d] = "exit";  // a locked door is still a door
  locks[d] = { "": "locked", "locked": "security", "security": "" }[locks[d]];
  refreshDoors();
  updateSummary();
}

function refreshDoors() {
  $("doors").querySelectorAll(".door").forEach(b => {
    const s = doors[b.dataset.dir];
    b.classList.toggle("st-exit", s === "exit");
    b.classList.toggle("st-entry", s === "entry");
    b.classList.toggle("lk-locked", locks[b.dataset.dir] === "locked");
    b.classList.toggle("lk-security", locks[b.dataset.dir] === "security");
  });
}

function setDoorsFromRoom(r) {
  const exits = new Set(r ? (r.exits || "").split("").filter(Boolean) : []);
  const entry = r ? (r.entry || "") : "";
  const locked = r ? (r.locked || "") : "";
  const security = r ? (r.security || "") : "";
  for (const d of DIRS) {
    doors[d] = d === entry ? "entry" : (exits.has(d) ? "exit" : "");
    locks[d] = security.includes(d) ? "security" : (locked.includes(d) ? "locked" : "");
  }
}

function selectCell(col, row) {
  sel = { column: col, row: row };
  const r = roomAt(col, row);

  $("cellTitle").textContent = `Cell ${col}${row}` + (r ? ` — ${r.room}` : " (empty)");
  $("room").value = r ? r.room : "";
  // Chess is keyed by room NAME (a room always holds the same piece). Use the
  // stored value when this cell already recorded one, else prefill from the name.
  if (r && (r.chess_piece || r.chess_colour)) {
    chessAuto = false;
    $("chessColour").value = r.chess_colour || "";
    $("chessPiece").value = r.chess_piece || "";
    $("chessNote").textContent = "";
    markChessPrefilled(false);
  } else {
    chessAuto = true;
    applyChessPrefill();   // reads the room name currently in the form
  }
  setDoorsFromRoom(r);   // doors are room-specific, never prefilled

  updateRoomHint();
  refreshDoors();
  updateSummary();
  renderGrid();
  $("status").textContent = "";
}

function knownRoom(name) {
  return !!(state && state.room_names && state.room_names.includes(name));
}

// --- room-name autocomplete: the list narrows as you type ---
let sugIndex = -1;  // highlighted option, -1 = none

function roomMatches(q) {
  const names = (state && state.room_names) || [];
  q = q.trim().toLowerCase();
  if (!q) return names;
  const starts = [], contains = [];
  for (const n of names) {
    const i = n.toLowerCase().indexOf(q);
    if (i === 0) starts.push(n);
    else if (i > 0) contains.push(n);
  }
  return starts.concat(contains);
}

function renderSuggest() {
  const el = $("roomSuggest");
  const q = $("room").value.trim().toLowerCase();
  const names = roomMatches(q);
  if (!names.length) return closeSuggest();
  el.innerHTML = names.map((n, i) => {
    const at = q ? n.toLowerCase().indexOf(q) : -1;
    const label = at < 0 ? esc(n)
      : esc(n.slice(0, at)) + "<b>" + esc(n.slice(at, at + q.length)) + "</b>" + esc(n.slice(at + q.length));
    return `<div class="opt${i === sugIndex ? " hi" : ""}" data-name="${esc(n)}">${label}</div>`;
  }).join("");
  el.classList.add("open");
  el.querySelectorAll(".opt").forEach(o => {
    o.onmousedown = e => { e.preventDefault(); pickSuggest(o.dataset.name); };
  });
  const hi = el.querySelector(".opt.hi");
  if (hi) hi.scrollIntoView({ block: "nearest" });
}

function closeSuggest() {
  sugIndex = -1;
  $("roomSuggest").classList.remove("open");
}

function pickSuggest(name) {
  $("room").value = name;
  closeSuggest();
  applyChessPrefill();
  updateRoomHint();
}

$("room").onfocus = () => { sugIndex = -1; renderSuggest(); };
$("room").onblur = () => closeSuggest();
$("room").onkeydown = e => {
  const open = $("roomSuggest").classList.contains("open");
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    if (!open) return renderSuggest();
    const count = $("roomSuggest").querySelectorAll(".opt").length;
    sugIndex = e.key === "ArrowDown"
      ? (sugIndex + 1) % count
      : (sugIndex - 1 + count) % count;
    renderSuggest();
  } else if (e.key === "Enter" && open && sugIndex >= 0) {
    e.preventDefault();
    const hi = $("roomSuggest").querySelector(".opt.hi");
    if (hi) pickSuggest(hi.dataset.name);
  } else if (e.key === "Escape") {
    closeSuggest();
  }
};

// Amber-flag the room field while the name doesn't match the known-rooms list.
function updateRoomHint() {
  const name = $("room").value.trim();
  const unknown = !!name && !knownRoom(name);
  $("room").classList.toggle("unknown", unknown);
  $("roomHint").textContent = unknown ? "not in room list — new room or typo?" : "";
}

function chessForRoom(name) {
  name = (name || "").trim().toLowerCase();
  return (name && state && state.chess_by_room) ? state.chess_by_room[name] : null;
}

function markChessPrefilled(on) {
  $("chessColour").classList.toggle("prefilled", on);
  $("chessPiece").classList.toggle("prefilled", on);
}

// Fill the chess dropdowns from the room-name map, unless the user has taken over.
function applyChessPrefill() {
  if (!chessAuto) return;
  const hit = chessForRoom($("room").value);
  $("chessColour").value = hit ? hit.chess_colour : "";
  $("chessPiece").value = hit ? hit.chess_piece : "";
  $("chessNote").textContent = hit ? `prefilled from day ${hit.day}` : "";
  markChessPrefilled(!!hit);
}

function updateSummary() {
  const exits = DIRS.filter(d => doors[d] !== "").join("");
  const entry = DIRS.find(d => doors[d] === "entry") || "";
  const locked = DIRS.filter(d => locks[d] === "locked").join("");
  const security = DIRS.filter(d => locks[d] === "security").join("");
  $("summary").textContent =
    `entrance: ${entry || "—"}\ndoors:    ${exits || "—"}` +
    `\nlocked:   ${locked || "—"}\nsecurity: ${security || "—"}`;
}

async function post(body) {
  const res = await fetch("/api/room", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

function setStatus(msg, ok = true) {
  const el = $("status");
  el.textContent = msg;
  el.style.color = ok ? "#166534" : "#b23";
}

$("room").oninput = () => {                      // chess follows the room name until edited
  applyChessPrefill();
  updateRoomHint();
  sugIndex = -1;                                 // typing re-narrows the list
  renderSuggest();
};
$("chessColour").onchange = $("chessPiece").onchange = () => {
  chessAuto = false;                             // user took over — stop auto-tracking
  markChessPrefilled(false);
  $("chessNote").textContent = "";
};

$("save").onclick = async () => {
  if (!sel) return setStatus("Pick a cell first", false);
  const room = $("room").value.trim();
  if (!room) return setStatus("Room name required", false);
  if (!knownRoom(room) &&
      !confirm(`"${room}" isn't in the room list.\nSave it as a new room name?`)) {
    return setStatus("Not saved — check the name", false);
  }
  const data = await post({
    day: parseInt($("day").value),
    column: sel.column,
    row: sel.row,
    room,
    entry: DIRS.find(d => doors[d] === "entry") || "",
    exits: DIRS.filter(d => doors[d] !== "").join(""),
    locked: DIRS.filter(d => locks[d] === "locked").join(""),
    security: DIRS.filter(d => locks[d] === "security").join(""),
    chess_colour: $("chessColour").value,
    chess_piece: $("chessPiece").value,
  });
  if (data.error) return setStatus("Error: " + data.error, false);
  state = data;
  selectCell(sel.column, sel.row);
  setStatus("Saved ✓");
};

$("delete").onclick = async () => {
  if (!sel) return;
  state = await post({ day: parseInt($("day").value), column: sel.column, row: sel.row, _delete: true });
  selectCell(sel.column, sel.row);
  setStatus("Deleted");
};

$("load").onclick = () => load(parseInt($("day").value));
$("day").onchange = () => load(parseInt($("day").value));

buildCompass();
load();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT)
