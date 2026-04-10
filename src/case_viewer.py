"""Simple graphical case viewer for Detective AI (Modules 1–3).

Shows culprit/weapon/room and room state per time slot. Uses tkinter (stdlib).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Keys in metadata for solution (module 1 random case)
_SOLUTION_KEYS = ("_solution_culprit", "_solution_weapon", "_solution_room", "_solution_time")
_CONTRADICTION_KEY = "CONTRADICTION"
_CONTRADICTION_GROUNDED_RULES_KEY = "_CONTRADICTION_GROUNDED_RULES"
MAP_CELL_PX = 140
MAP_GRID_SIZE = 3
MAP_CARD_PADDING = 4
MAP_TEXT_FONT = ("Helvetica", 7)
WINDOW_BG = "#f3f6fb"
TIMELINE_HEIGHT = 48
TIMELINE_MIN_WIDTH = 680
TIMELINE_SIDE_MARGIN = 30
TIMELINE_NODE_RADIUS_ACTIVE = 11
TIMELINE_NODE_RADIUS_IDLE = 9
FADE_ALPHA_TARGET = 0.9
FADE_ALPHA_STEP = 0.05
FADE_FRAME_MS = 14
MAX_EXTRA_LINES = 8

# Map / timeline / dual-label palette (single source for repeated UI literals)
_MAP_GRID_LINE = "#dbe4f2"
_MAP_CELL_BODY_BG = "#ffdede"
_MAP_CELL_NORMAL_BG = "#eef3ff"
_MAP_CELL_BODY_OUTLINE = "#b34040"
_MAP_CELL_NORMAL_OUTLINE = "#52627a"
_MAP_TEXT_MAIN = "#111"
_LEGEND_FG = "#243447"
_TIMELINE_EDGE_ACTIVE = "#4f7bd9"
_TIMELINE_EDGE_IDLE = "#c8d3ea"
_TIMELINE_NODE_ACTIVE = "#2f67d8"
_TIMELINE_NODE_COMPLETE = "#6f95e6"
_TIMELINE_NODE_IDLE = "#dfe7f6"
_TIMELINE_NODE_OUTLINE_ACTIVE = "#204aa0"
_TIMELINE_NODE_OUTLINE_IDLE = "#8ba2cf"
_TIMELINE_TEXT_ACTIVE = "#ffffff"
_TIMELINE_TEXT_LABEL = "#5b6f97"
_TIMELINE_SUBLABEL = "#3f516e"
_LABEL_ACTUAL_BG = "#ecfff0"
_LABEL_ACTUAL_FG = "#12361c"
_LABEL_M4_BG = "#eef3ff"
_LABEL_M4_FG = "#1f3555"


def _predicate_parts(
    prop: str,
    predicate: str,
    min_segments: int,
    *,
    reject_not: bool = True,
) -> list[str] | None:
    """Split ``Predicate_...`` propositions into underscore segments if shape matches."""
    if reject_not and prop.startswith("NOT_"):
        return None
    prefix = predicate + "_"
    if not prop.startswith(prefix):
        return None
    parts = prop.split("_")
    if len(parts) < min_segments:
        return None
    return parts


def _parse_at(prop: str) -> tuple[str, str, str] | None:
    """At_Person_Room_Time -> (person, room, time)."""
    parts = _predicate_parts(prop, "At", 4, reject_not=True)
    if parts is None:
        return None
    return (parts[1], parts[2], parts[3])


def _parse_weapon(prop: str) -> tuple[str, str] | None:
    """Weapon_WeaponName_Room -> (weapon, room)."""
    parts = _predicate_parts(prop, "Weapon", 3, reject_not=True)
    if parts is None:
        return None
    return (parts[1], parts[2])


def _parse_door_locked(prop: str) -> tuple[str, str] | None:
    """DoorLocked_Room_Time -> (room, time)."""
    parts = _predicate_parts(prop, "DoorLocked", 3, reject_not=False)
    if parts is None:
        return None
    return (parts[1], parts[2])


def _parse_murder_location(prop: str) -> str | None:
    """MurderLocation_Room -> room."""
    parts = _predicate_parts(prop, "MurderLocation", 2, reject_not=False)
    if parts is None:
        return None
    return parts[1]


def _parse_victim_found(prop: str) -> str | None:
    """VictimFound_Room -> room (where body was found)."""
    parts = _predicate_parts(prop, "VictimFound", 2, reject_not=True)
    if parts is None:
        return None
    return parts[1]


def _parse_body_dragged_from(prop: str) -> str | None:
    """BodyDraggedFrom_Room -> room (where the body was dragged from)."""
    parts = _predicate_parts(prop, "BodyDraggedFrom", 2, reject_not=True)
    if parts is None:
        return None
    return parts[1]


def _parse_culprit_positive(prop: str) -> tuple[str, str] | None:
    """Culprit_Person_Time (positive only) -> (person, time)."""
    parts = _predicate_parts(prop, "Culprit", 3, reject_not=False)
    if parts is None:
        return None
    return (parts[1], parts[2])


def _format_room_state_cell(
    state_at_time: dict[str, Any],
    *,
    body_label: str,
    dragged_label: str,
    locked_label: str,
) -> tuple[str, bool, bool]:
    """Build table/map cell text and body/drag row flags."""
    people = state_at_time.get("people", [])
    weapons = state_at_time.get("weapons", [])
    locked = state_at_time.get("door_locked")
    body_found = bool(state_at_time.get("body_found"))
    dragged_from = bool(state_at_time.get("dragged_from"))
    parts: list[str] = []
    if body_found:
        parts.append(body_label)
    if dragged_from:
        parts.append(dragged_label)
    if people:
        parts.append(", ".join(people))
    if weapons:
        parts.append("W: " + ", ".join(weapons))
    if locked is True:
        parts.append(locked_label)
    return (", ".join(parts) if parts else "—", body_found, dragged_from)


def parse_evidence_to_room_state(
    evidence: dict[str, bool],
    rooms: list[str],
    time_points: list[str],
    murder_time: str | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Build room state from evidence: room -> time -> {people, weapons, door_locked, body_found, dragged_from}.

    evidence: proposition name -> True (only true facts).
    body_found: True in the room where VictimFound_Room is in evidence; if murder_time is given,
    only that time slot shows the body (where and when); otherwise the body room shows Body at all times.
    """
    # Weapon locations are not time-dependent in our schema
    weapons_in_room: dict[str, list[str]] = {r: [] for r in rooms}
    body_room: str | None = None
    dragged_from_room: str | None = None
    for prop in evidence:
        if prop in (_CONTRADICTION_KEY, _CONTRADICTION_GROUNDED_RULES_KEY):
            continue
        t = _parse_weapon(prop)
        if t:
            w, r = t
            if r in weapons_in_room:
                weapons_in_room[r].append(w)
        vf = _parse_victim_found(prop)
        if vf and vf in rooms:
            body_room = vf

        df = _parse_body_dragged_from(prop)
        if df and df in rooms:
            dragged_from_room = df

    result: dict[str, dict[str, dict[str, Any]]] = {}
    for room in rooms:
        result[room] = {}
        for time in time_points:
            people: list[str] = []
            door_locked: bool | None = None
            for prop in evidence:
                if prop in (_CONTRADICTION_KEY, _CONTRADICTION_GROUNDED_RULES_KEY):
                    continue
                at = _parse_at(prop)
                if at:
                    p, r, t = at
                    if r == room and t == time:
                        people.append(p)
                dl = _parse_door_locked(prop)
                if dl:
                    r, t = dl
                    if r == room and t == time:
                        door_locked = True
            body_found = body_room is not None and room == body_room
            if body_found and murder_time is not None:
                body_found = time == murder_time
            result[room][time] = {
                "people": sorted(people),
                "weapons": weapons_in_room.get(room, [])[:],
                "door_locked": door_locked,
                "body_found": body_found,
                "dragged_from": dragged_from_room is not None and room == dragged_from_room,
            }
    return result


def get_solution_from_metadata(metadata: dict) -> dict[str, str | None]:
    """Extract solution from module 1 metadata (_solution_*)."""
    return {
        "culprit": metadata.get("_solution_culprit"),
        "weapon": metadata.get("_solution_weapon"),
        "room": metadata.get("_solution_room"),
        "time": metadata.get("_solution_time"),
    }


def get_solution_from_evidence(evidence: dict[str, bool]) -> dict[str, str | None]:
    """Infer solution from evidence if one positive Culprit, one MurderLocation, one Weapon in that room."""
    culprit_time: tuple[str, str] | None = None
    murder_room: str | None = None
    weapon_in_murder_room: str | None = None
    for prop in evidence:
        if prop in (_CONTRADICTION_KEY, _CONTRADICTION_GROUNDED_RULES_KEY):
            continue
        c = _parse_culprit_positive(prop)
        if c:
            culprit_time = c
        m = _parse_murder_location(prop)
        if m:
            murder_room = m
    if murder_room:
        for prop in evidence:
            if prop in (_CONTRADICTION_KEY, _CONTRADICTION_GROUNDED_RULES_KEY):
                continue
            w = _parse_weapon(prop)
            if w:
                weapon_name, room = w
                if room == murder_room:
                    weapon_in_murder_room = weapon_name
                    break
    if culprit_time and murder_room:
        return {
            "culprit": culprit_time[0],
            "weapon": weapon_in_murder_room,
            "room": murder_room,
            "time": culprit_time[1],
        }
    return {"culprit": None, "weapon": weapon_in_murder_room, "room": murder_room, "time": None}


def _room_map_cell_index(room_idx: int) -> tuple[int, int] | None:
    """Map the Nth room into a cell on a 9x9 canvas.

    We place the 9 rooms into the top-left 3x3 region:
      idx 0..8 -> (row=idx//3, col=idx%3)
    leaving the rest blank.
    """
    if room_idx < 0 or room_idx > 8:
        return None
    return (room_idx // 3, room_idx % 3)


def _show_room_9x9_map_popup(
    parent_root: Any,
    title: str,
    solution: dict[str, str | None],
    evidence: dict[str, bool],
    rooms: list[str],
    time_points: list[str],
) -> None:
    """Show a 3x3 room map where each (of the 9) rooms is drawn as one square.

    The 9 rooms are mapped into row-major order:
      idx 0..8 -> (row=idx//3, col=idx%3)
    """
    try:
        import tkinter as tk
    except ImportError:
        return

    map_time = solution.get("time") or (time_points[0] if time_points else None)
    if map_time is None:
        map_time = ""

    state = parse_evidence_to_room_state(
        evidence,
        rooms,
        time_points,
        murder_time=map_time if map_time else None,
    )

    popup = tk.Toplevel(parent_root)
    popup.title(title)
    popup.configure(background=WINDOW_BG)

    cell = MAP_CELL_PX
    grid = MAP_GRID_SIZE
    canvas_w = grid * cell
    canvas_h = grid * cell
    canvas = tk.Canvas(
        popup,
        width=canvas_w,
        height=canvas_h,
        background=WINDOW_BG,
        highlightthickness=0,
        bd=0,
    )
    canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, MAP_CARD_PADDING))

    # Draw background grid.
    for i in range(grid + 1):
        x = i * cell
        canvas.create_line(x, 0, x, canvas_h, fill=_MAP_GRID_LINE)
        canvas.create_line(0, i * cell, canvas_w, i * cell, fill=_MAP_GRID_LINE)

    # Draw each room in its mapped cell.
    for room_idx, room_name in enumerate(rooms[:9]):
        cell_rc = _room_map_cell_index(room_idx)
        if cell_rc is None:
            continue
        r_i, c_i = cell_rc
        x0 = c_i * cell
        y0 = r_i * cell

        s = state.get(room_name, {}).get(map_time, {})
        people = s.get("people", [])
        weapons = s.get("weapons", [])
        locked = s.get("door_locked")
        body_found = s.get("body_found")
        dragged_from = s.get("dragged_from")

        fill = _MAP_CELL_BODY_BG if body_found else _MAP_CELL_NORMAL_BG
        outline = _MAP_CELL_BODY_OUTLINE if body_found else _MAP_CELL_NORMAL_OUTLINE
        canvas.create_rectangle(
            x0 + MAP_CARD_PADDING,
            y0 + MAP_CARD_PADDING,
            x0 + cell - MAP_CARD_PADDING,
            y0 + cell - MAP_CARD_PADDING,
            fill=fill,
            outline=outline,
            width=2,
        )

        lines: list[str] = [room_name]
        if body_found:
            lines.append("● Body")
        if dragged_from:
            lines.append("↳ DraggedFrom")
        if people:
            lines.append("P: " + ", ".join(people[:3]))
        if weapons:
            lines.append("W: " + ", ".join(weapons[:2]))
        if locked is True:
            lines.append("🔒 Locked")

        canvas.create_text(
            x0 + cell / 2,
            y0 + cell / 2,
            text="\n".join(lines),
            font=MAP_TEXT_FONT,
            fill=_MAP_TEXT_MAIN,
            justify="center",
        )

    legend = tk.Label(
        popup,
        text="● Body   ↳ DraggedFrom   🔒 DoorLocked   P People   W Weapons",
        bg=WINDOW_BG,
        fg=_LEGEND_FG,
        anchor="w",
        padx=12,
    )
    legend.pack(fill=tk.X, pady=(0, 10))


def show_case_view(
    module_id: int,
    title: str,
    solution: dict[str, str | None],
    evidence: dict[str, bool],
    rooms: list[str],
    time_points: list[str],
    extra_lines: list[str] | None = None,
) -> None:
    """Show a tkinter popup with solution and room-state grid.

    module_id: 1, 2, or 3 (for header).
    title: window title.
    solution: { culprit, weapon, room, time }.
    evidence: proposition -> True.
    rooms, time_points: for grid.
    extra_lines: optional lines to show (e.g. goal_reached, num inferred).
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        return

    root = tk.Tk()
    root.title(title)
    root.geometry("720x520")
    root.minsize(400, 300)

    main = ttk.Frame(root, padding=10)
    main.pack(fill=tk.BOTH, expand=True)

    # Header
    ttk.Label(main, text=f"Detective AI — Module {module_id} Case View", font=("", 12, "bold")).pack(anchor=tk.W)

    # Solution
    sol_frame = ttk.LabelFrame(main, text="Solution / Identified", padding=5)
    sol_frame.pack(fill=tk.X, pady=(0, 8))
    culp = solution.get("culprit") or "?"
    weap = solution.get("weapon") or "?"
    room = solution.get("room") or "?"
    time = solution.get("time") or "?"
    ttk.Label(sol_frame, text=f"Culprit: {culp}  |  Weapon: {weap}  |  Room: {room}  |  Time: {time}").pack(anchor=tk.W)

    if extra_lines:
        for line in extra_lines:
            ttk.Label(main, text=line).pack(anchor=tk.W)

    # Room state grid (evidence only; culprit at murder time may be in witness_knowledge)
    state = parse_evidence_to_room_state(
        evidence, rooms, time_points, murder_time=solution.get("time")
    )
    grid_frame = ttk.LabelFrame(
        main,
        text="Room state by time slot (known evidence only; culprit location at murder time may be unqueried)",
        padding=5,
    )
    grid_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

    # Table: rooms x time_points
    columns = ["Room"] + list(time_points)
    tree = ttk.Treeview(grid_frame, columns=columns, show="headings", height=min(20, len(rooms) + 1))
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=160 if col == "Room" else 140)
    vsb = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    for room_name in rooms:
        row = [room_name]
        for t in time_points:
            s = state.get(room_name, {}).get(t, {})
            cell_text, _, _ = _format_room_state_cell(
                s,
                body_label="Body",
                dragged_label="DraggedFrom",
                locked_label="Locked",
            )
            row.append(cell_text)
        tree.insert("", tk.END, values=row)

    ttk.Button(
        main,
        text="Open 3x3 room map",
        command=lambda: _show_room_9x9_map_popup(
            root,
            f"{title} — 3x3 map",
            solution,
            evidence,
            rooms,
            time_points,
        ),
    ).pack(anchor=tk.W, pady=(6, 0))

    def on_closing() -> None:
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


def show_case_view_multi(
    steps: list[dict[str, Any]],
    rooms: list[str],
    time_points: list[str],
) -> None:
    """Show one window with a 'Next module' button to cycle through steps.

    steps: list of dicts, each with keys module_id, title, solution, evidence, extra_lines.
    rooms, time_points: same for all steps.
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        return
    if not steps:
        return

    root = tk.Tk()
    root.configure(background=WINDOW_BG)
    module_ids = [str(s.get("module_id", "?")) for s in steps]
    root.title("Detective AI — Case viewer (Module " + " → ".join(module_ids) + ")")
    root.geometry("780x560")
    root.minsize(450, 320)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("Treeview", rowheight=24)
    style.configure("Treeview.Heading", font=("", 10, "bold"))

    main = ttk.Frame(root, padding=10)
    main.pack(fill=tk.BOTH, expand=True)

    idx_var: list[int] = [0]

    header_label = ttk.Label(main, text="", font=("", 12, "bold"))
    header_label.pack(anchor=tk.W)

    sol_frame = ttk.LabelFrame(main, text="Solution / Identified", padding=5)
    sol_frame.pack(fill=tk.X, pady=(0, 4))

    actual_box = ttk.LabelFrame(sol_frame, text="Actual Solution", padding=5)
    module4_box = ttk.LabelFrame(sol_frame, text="Module 4 Hypothesis", padding=5)
    actual_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    module4_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    actual_label = tk.Label(
        actual_box, text="", justify=tk.LEFT, bg=_LABEL_ACTUAL_BG, fg=_LABEL_ACTUAL_FG, padx=6, pady=4
    )
    module4_label = tk.Label(
        module4_box, text="", justify=tk.LEFT, bg=_LABEL_M4_BG, fg=_LABEL_M4_FG, padx=6, pady=4
    )
    actual_label.pack(anchor=tk.W, fill=tk.X)
    module4_label.pack(anchor=tk.W, fill=tk.X)

    actual_solution: dict[str, str | None] = {}
    module4_solution: dict[str, str | None] = {}
    for s in steps:
        if not actual_solution and s.get("module_id") in (0, 1):
            actual_solution = s.get("solution") or {}
        if not module4_solution and s.get("module_id") == 4:
            module4_solution = s.get("solution") or {}

    def _render_solution(sol: dict[str, str | None]) -> str:
        culp = sol.get("culprit") or "?"
        weap = sol.get("weapon") or "?"
        room = sol.get("room") or "?"
        time = sol.get("time") or "?"
        return f"Culprit: {culp}\nWeapon: {weap}\nRoom: {room}\nTime: {time}"

    actual_label.config(text=_render_solution(actual_solution))
    module4_label.config(text="Hidden until Module 4")

    btn_frame = ttk.Frame(main)
    btn_frame.pack(fill=tk.X, pady=(6, 2))
    step_label = ttk.Label(btn_frame, text="")
    step_label.pack(side=tk.RIGHT)
    ttk.Button(
        btn_frame,
        text="Previous module",
        command=lambda: on_prev(),
    ).pack(side=tk.LEFT)
    ttk.Button(
        btn_frame,
        text="Next module (" + " → ".join(module_ids) + ")",
        command=lambda: on_next(),
    ).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(
        btn_frame,
        text="Jump to Module 1",
        command=lambda: on_first(),
    ).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(
        btn_frame,
        text="Open 3x3 room map",
        command=lambda: _show_room_9x9_map_popup(
            root,
            f"{steps[idx_var[0]]['title']} — 3x3 map",
            steps[idx_var[0]].get("solution", {}),
            steps[idx_var[0]].get("evidence", {}),
            rooms,
            time_points,
        ),
    ).pack(side=tk.LEFT, padx=(10, 0))

    timeline_canvas = tk.Canvas(
        main,
        height=TIMELINE_HEIGHT,
        background=WINDOW_BG,
        highlightthickness=0,
        bd=0,
    )
    timeline_canvas.pack(fill=tk.X, pady=(2, 4))

    extra_frame = ttk.Frame(main)
    extra_frame.pack(fill=tk.X)
    extra_labels: list[ttk.Label] = []
    max_extra_lines = MAX_EXTRA_LINES

    grid_frame = ttk.LabelFrame(
        main,
        text="Room state by time slot (known evidence only; culprit location at murder time may be unqueried)",
        padding=5,
    )
    grid_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
    columns = ["Room"] + list(time_points)
    tree = ttk.Treeview(grid_frame, columns=columns, show="headings", height=min(18, len(rooms) + 1))
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150 if col == "Room" else 150)
    tree.tag_configure("body_row", background="#ffe9e9")
    tree.tag_configure("drag_row", background="#fff4e2")
    tree.tag_configure("normal_row", background="#ffffff")
    vsb = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _fade_to(target_alpha: float, *, on_done: Any = None) -> None:
        try:
            current = float(root.attributes("-alpha"))
        except tk.TclError:
            if on_done:
                on_done()
            return
        step = FADE_ALPHA_STEP if target_alpha > current else -FADE_ALPHA_STEP

        def _tick() -> None:
            nonlocal current
            current += step
            if (step > 0 and current >= target_alpha) or (step < 0 and current <= target_alpha):
                try:
                    root.attributes("-alpha", target_alpha)
                except tk.TclError:
                    pass
                if on_done:
                    on_done()
                return
            try:
                root.attributes("-alpha", current)
            except tk.TclError:
                if on_done:
                    on_done()
                return
            root.after(FADE_FRAME_MS, _tick)

        _tick()

    def _draw_timeline_bar(active_idx: int) -> None:
        timeline_canvas.delete("all")
        total = len(steps)
        if total <= 0:
            return
        w = max(timeline_canvas.winfo_width(), TIMELINE_MIN_WIDTH)
        h = max(timeline_canvas.winfo_height(), TIMELINE_HEIGHT)
        x_left = TIMELINE_SIDE_MARGIN
        x_right = w - TIMELINE_SIDE_MARGIN
        y = h // 2
        span = max(1, x_right - x_left)
        step_w = span / max(1, total - 1)
        for i in range(total - 1):
            x0 = x_left + i * step_w
            x1 = x_left + (i + 1) * step_w
            line_color = _TIMELINE_EDGE_ACTIVE if i < active_idx else _TIMELINE_EDGE_IDLE
            timeline_canvas.create_line(x0, y, x1, y, fill=line_color, width=3)

        for i, step in enumerate(steps):
            x = x_left + i * step_w
            module_id = str(step.get("module_id", i + 1))
            active = i == active_idx
            complete = i < active_idx
            fill = _TIMELINE_NODE_ACTIVE if active else (_TIMELINE_NODE_COMPLETE if complete else _TIMELINE_NODE_IDLE)
            outline = _TIMELINE_NODE_OUTLINE_ACTIVE if active else _TIMELINE_NODE_OUTLINE_IDLE
            radius = TIMELINE_NODE_RADIUS_ACTIVE if active else TIMELINE_NODE_RADIUS_IDLE
            timeline_canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius, fill=fill, outline=outline, width=2
            )
            timeline_canvas.create_text(
                x,
                y,
                text=module_id,
                fill=_TIMELINE_TEXT_ACTIVE if active or complete else _TIMELINE_TEXT_LABEL,
                font=("", 9, "bold"),
            )
            timeline_canvas.create_text(
                x, y + 18, text=f"M{module_id}", fill=_TIMELINE_SUBLABEL, font=("", 8)
            )
            timeline_canvas.create_rectangle(
                x - radius, y - radius, x + radius, y + radius,
                outline="", fill="", tags=(f"hit_{i}",)
            )
            timeline_canvas.tag_bind(
                f"hit_{i}",
                "<Button-1>",
                lambda _e, idx=i: _jump_to(idx),
            )

    def _apply_step_content() -> None:
        i = idx_var[0]
        step = steps[i]
        evidence = step["evidence"]
        solution = step["solution"]
        header_label.config(text=f"Detective AI — Module {step['module_id']} Case View")
        root.title(step["title"])
        if step.get("module_id", 0) >= 4 and module4_solution:
            module4_label.config(text=_render_solution(module4_solution))
        else:
            module4_label.config(text="Hidden until Module 4")
        # Actual + Module 4 hypothesis boxes stay fixed while cycling modules.
        # The evidence grid still uses the current step's solution time.
        for lb in extra_labels:
            lb.destroy()
        extra_labels.clear()
        lines = list(step.get("extra_lines") or [])
        shown = lines[:max_extra_lines]
        for line in shown:
            lb = ttk.Label(extra_frame, text=line)
            lb.pack(anchor=tk.W)
            extra_labels.append(lb)
        if len(lines) > max_extra_lines:
            more = len(lines) - max_extra_lines
            lb = ttk.Label(extra_frame, text=f"... ({more} more lines hidden)")
            lb.pack(anchor=tk.W)
            extra_labels.append(lb)
        state = parse_evidence_to_room_state(
            evidence, rooms, time_points, murder_time=solution.get("time")
        )
        for item in tree.get_children(""):
            tree.delete(item)
        for room_name in rooms:
            row = [room_name]
            row_has_body = False
            row_has_drag = False
            for t in time_points:
                s = state.get(room_name, {}).get(t, {})
                cell_text, body_found, dragged_from = _format_room_state_cell(
                    s,
                    body_label="● Body",
                    dragged_label="↳ Dragged",
                    locked_label="🔒 Locked",
                )
                if body_found:
                    row_has_body = True
                if dragged_from:
                    row_has_drag = True
                row.append(cell_text)
            tag = "body_row" if row_has_body else ("drag_row" if row_has_drag else "normal_row")
            tree.insert("", tk.END, values=row, tags=(tag,))
        step_label.config(text=f"Step {idx_var[0] + 1}/{len(steps)}")
        _draw_timeline_bar(idx_var[0])

    def refresh(*, animate: bool = True) -> None:
        if not animate:
            _apply_step_content()
            return

        def _after_fade_out() -> None:
            _apply_step_content()
            _fade_to(1.0)

        _fade_to(FADE_ALPHA_TARGET, on_done=_after_fade_out)

    def _jump_to(target_idx: int) -> None:
        idx_var[0] = target_idx % len(steps)
        refresh()

    def on_prev() -> None:
        idx_var[0] = (idx_var[0] - 1) % len(steps)
        refresh()

    def on_next() -> None:
        idx_var[0] = (idx_var[0] + 1) % len(steps)
        refresh()

    def on_first() -> None:
        idx_var[0] = 0
        refresh()

    timeline_canvas.bind("<Configure>", lambda _e: _draw_timeline_bar(idx_var[0]))
    refresh(animate=False)

    def on_closing() -> None:
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


def load_evidence_and_rules_for_view(
    evidence_path: str | Path,
    rules_path: str | Path,
) -> tuple[dict[str, bool], list[str], list[str], dict]:
    """Load evidence and game_constraints from files. Returns (evidence, rooms, time_points, metadata)."""
    evidence_path = Path(evidence_path)
    rules_path = Path(rules_path)
    with open(evidence_path, encoding="utf-8") as f:
        data = json.load(f)
    evidence = data.get("evidence", {})
    metadata = data.get("metadata", {})
    with open(rules_path, encoding="utf-8") as f:
        rules = json.load(f)
    gc = rules.get("game_constraints", {})
    rooms = gc.get("rooms", [])
    time_points = gc.get("time_points", ["8pm", "9pm", "10pm"])
    return evidence, rooms, time_points, metadata


def _summarize_new_facts(prev: dict[str, bool], curr: dict[str, bool], max_items: int = 12) -> list[str]:
    prev_set = {k for k, v in prev.items() if v is True}
    curr_set = {k for k, v in curr.items() if v is True}
    added = sorted(curr_set - prev_set)
    if not added:
        return []
    sample = added[:max_items]
    more = len(added) - len(sample)
    lines = [f"New facts learned: {len(added)}"]
    lines.append("New facts (sample): " + ", ".join(sample) + (f" … (+{more} more)" if more > 0 else ""))
    return lines


if __name__ == "__main__":
    """Run from project root: python -m src.case_viewer
    Runs Module 1 (random case_init) → Module 2 (query plan) → Module 3 (FOL inference),
    then shows one viewer with 'Next module' to cycle through each stage.
    """
    import tempfile
    from pathlib import Path
    from src import module_1, module_2, module_3, module_4
    root = Path(__file__).resolve().parent.parent
    rules_path = root / "integration_tests" / "module_1" / "rules.json"
    if not rules_path.exists():
        raise SystemExit(f"Rules not found: {rules_path}")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        # Module 1: create random case_init and evidence_found.json
        case = module_1.run_random_case(rules_path, out, seed=42, kb_ratio=0.4)
        evidence_path = out / "evidence_found.json"
        evidence1, rooms, time_points, metadata = load_evidence_and_rules_for_view(
            evidence_path, rules_path
        )
        solution1 = get_solution_from_metadata(metadata)
        steps = [
            {
                "module_id": 1,
                "title": "Module 1 — Case init & evidence",
                "solution": solution1,
                "evidence": evidence1,
                "extra_lines": [
                    "Module 1 created a random case_init and ran inference.",
                    "Solution (culprit, weapon, room) is from the generated case; grid shows known evidence only.",
                ],
            },
        ]
        # Module 2: beam-search query planning (enriches evidence with observations)
        search_result = module_2.run_search(
            evidence_path,
            case["witness_knowledge"],
            query_budget=200,
            output_dir=out,
            beam_width=3,
            rules_path=rules_path,
        )
        final_kb = dict(evidence1)
        for obs in search_result["observations"]:
            if obs.get("result") is True:
                final_kb[obs.get("action", "")] = True
        solution2 = get_solution_from_metadata(metadata)
        if solution2.get("culprit") is None:
            solution2 = get_solution_from_evidence(final_kb)
        qplan = search_result.get("query_plan", [])
        qplan_text = ", ".join(qplan) if qplan else "—"
        steps.append({
            "module_id": 2,
            "title": "Module 2 — After query plan & observations",
            "solution": solution2,
            "evidence": final_kb,
            "extra_lines": [
                f"Goal reached: {search_result['goal_reached']}",
                f"Queries used: {len(search_result['query_plan'])}",
                f"Queries: {qplan_text}",
                *_summarize_new_facts(evidence1, final_kb),
            ],
        })
        # Module 3: FOL inference (evidence + inferred facts; base = module 2 final_kb for cumulative view)
        kb_fol_path = out / "kb_fol.json"
        inferred_facts_path = out / "inferred_facts.json"
        m3_result = module_3.run(
            evidence_path,
            rules_path,
            kb_fol_path=kb_fol_path,
            inferred_facts_path=inferred_facts_path,
            show_case_view=False,
        )
        evidence3 = dict(final_kb)
        for fol in m3_result.get("fol_propositions", []):
            if fol.get("value") is True and not fol.get("negated"):
                prop = fol.get("propositional")
                if prop:
                    evidence3[prop] = True
        solution3 = get_solution_from_evidence(evidence3)
        if solution3.get("culprit") is None:
            solution3 = get_solution_from_metadata(metadata)
        steps.append({
            "module_id": 3,
            "title": "Module 3 — After FOL inference",
            "solution": solution3,
            "evidence": evidence3,
            "extra_lines": [
                f"Inferred facts: {len(m3_result.get('inferred_facts', []))}",
                f"Total FOL propositions: {len(m3_result.get('fol_propositions', []))}",
                *_summarize_new_facts(final_kb, evidence3),
            ],
        })

        # Module 4: hypothesis generation from kb_fol.json + inferred_facts.json
        module_4_output_dir = out / "module_4_out"
        module_4_output_dir.mkdir(parents=True, exist_ok=True)
        module_4.run(
            kb_fol_path=kb_fol_path,
            inferred_facts_path=inferred_facts_path,
            output_dir=module_4_output_dir,
            top_k=3,
        )
        hypotheses_ranked_path = module_4_output_dir / "hypotheses_ranked.json"
        solution4 = get_solution_from_evidence(evidence3)
        best_score = None
        best_hyp = None
        if hypotheses_ranked_path.exists():
            try:
                with open(hypotheses_ranked_path, encoding="utf-8") as f:
                    hyp_data = json.load(f)
                ranked = hyp_data.get("hypotheses_ranked", [])
                if ranked:
                    best_hyp = ranked[0]
                    solution4 = {
                        "culprit": best_hyp.get("culprit"),
                        "weapon": best_hyp.get("weapon"),
                        "room": best_hyp.get("room"),
                        "time": best_hyp.get("time"),
                    }
                    best_score = best_hyp.get("score")
            except (OSError, json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, AttributeError) as e:
                logger.debug("Could not read Module 4 ranked hypotheses: %s", e, exc_info=True)

        # For visualization, inject the best-hypothesis placement into evidence
        # so the room map can show where Module 4 believes the culprit was.
        evidence4 = dict(evidence3)
        if solution4.get("culprit") and solution4.get("room") and solution4.get("time"):
            evidence4[f"At_{solution4['culprit']}_{solution4['room']}_{solution4['time']}"] = True
        if solution4.get("weapon") and solution4.get("room"):
            evidence4[f"Weapon_{solution4['weapon']}_{solution4['room']}"] = True
        if solution4.get("room"):
            # Align dragged-body visualization with the hypothesized murder room.
            for k in list(evidence4.keys()):
                if k.startswith("BodyDraggedFrom_"):
                    evidence4.pop(k, None)
            evidence4[f"BodyDraggedFrom_{solution4['room']}"] = True

        steps.append({
            "module_id": 4,
            "title": "Module 4 — After hypothesis ranking",
            "solution": solution4,
            "evidence": evidence4,
            "extra_lines": [
                f"Best hypothesis score: {best_score if best_score is not None else '—'}",
                "Module 4 generates hypotheses (ranked); this step visualizes the top choice.",
            ],
        })

        show_case_view_multi(steps, rooms, time_points)
