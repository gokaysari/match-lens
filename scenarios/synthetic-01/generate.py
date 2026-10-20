"""Deterministic generator for synthetic-01 (Northbridge FC v Harbour Athletic, 58:00-62:00 of period 2).

Run: python scenarios/synthetic-01/generate.py
The script (who does what, outcomes, ordering) is fixed in code. The seeded
random.Random is used only for small jitter in coordinates and timings.
Home (nbr) attacks toward x=105, away (hba) toward x=0; metres, origin bottom-left.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from contracts.events import ON_BALL_TYPES, MatchEvent, ScenarioMeta  # noqa: E402

SEED = 2026
MATCH_ID = "synthetic-01"
START_MS = 58 * 60_000
FIRST_SEQUENCE = 2001

NBR_NAMES = ["Tomas Reed", "Callum Ashby", "Idris Vane", "Rowan Locke", "Jonas Pryor", "Mateo Kerr",
             "Felix Dunmore", "Owen Garrick", "Dario Holt", "Ezra Whitlock", "Kian Marlow"]
HBA_NAMES = ["Anselm Crowe", "Silas Brandt", "Teo Raventhorpe", "Lucan Mercer", "Bram Ostler", "Nico Fairley",
             "Ravi Calloway", "Joss Hartigan", "Emil Strand", "Dante Ibsen", "Arlo Penhale"]

# Northbridge shape in their own half during build-up.
POS = {1: (6, 34), 2: (24, 10), 3: (18, 26), 4: (18, 42), 5: (24, 58), 6: (32, 34),
       7: (46, 10), 8: (38, 22), 9: (60, 34), 10: (38, 46), 11: (46, 58)}

# Moment a: patient build-up, holder sequence (every consecutive pair is a completed pass).
A_CHAIN = [4, 3, 1, 2, 6, 3, 4, 5, 6, 8, 6, 10, 4, 3, 2, 6, 10, 8, 6, 3, 4, 6, 3, 6]
# Moment b, per cycle: (target, pass completes?, then for a turnover:
# Harbour winning action, Harbour player, Harbour's next pass recipient, Northbridge regain action,
# Northbridge player). The final cycle (the pass Harbour intercept in moment c) is built separately.
B_CYCLES = [
    (10, True, None, None, None, None, None),
    (4, True, None, None, None, None, None),
    (3, False, "tackle", 7, 10, "ball_recovery", 8),
    (6, True, None, None, None, None, None),
    (8, False, "ball_recovery", 11, 9, "interception", 6),
    (2, False, "interception", 10, 8, "tackle", 5),
    (6, True, None, None, None, None, None),
    (4, False, "tackle", 9, 7, "ball_recovery", 3),
]
PRESSERS = [9, 10, 11, 7, 8]
# Moment d: (target, x, y) low-threat waypoints; index D_FAIL is an incomplete pass.
D_WAYPOINTS = [(10, 50, 42), (6, 44, 34), (8, 48, 24), (2, 52, 12), (8, 50, 22), (6, 46, 34), (10, 50, 44),
               (5, 54, 56), (10, 52, 46), (6, 48, 34), (3, 40, 28), (4, 40, 40), (10, 48, 44), (8, 54, 26),
               (7, 60, 14), (8, 56, 24), (9, 62, 32), (10, 58, 42), (11, 62, 56), (10, 60, 46), (6, 52, 36),
               (8, 58, 28), (10, 62, 40), (11, 66, 54), (10, 70, 44)]
D_FAIL = 11  # index into D_WAYPOINTS; the tackle that follows is won by nbr-06


def pid(team: str, n: int) -> str:
    return f"{team}-{n:02d}"


class Builder:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.seed = seed
        self.rows: list[dict] = []
        self.t = START_MS
        self.cursor = (0.0, 0.0)
        self.poss_n = 0
        self.poss_team = ""

    def _j(self, v: float, hi: float, fixed: bool = False) -> float:
        if fixed:
            return round(v, 1)
        return round(min(max(v + self.rng.uniform(-1.0, 1.0), 0.0), hi), 1)

    def add(self, dt: int, team: str, player: int | None, typ: str, outcome: str | None,
            x: float | None = None, y: float | None = None, end: tuple[float, float] | None = None,
            fixed_end: bool = False, fixed_start: bool = False, recipient: int | None = None,
            pressured: int | None = None) -> str:
        self.t += max(400, dt + self.rng.randint(-250, 250)) if self.rows else 0
        px, py = (x, y) if x is not None else self.cursor
        ex = ey = None
        if end is not None:
            ex, ey = self._j(end[0], 105.0, fixed_end), self._j(end[1], 68.0)
        possession = None
        if typ in ON_BALL_TYPES:
            if typ == "kick_off" or team != self.poss_team:
                self.poss_n += 1
                self.poss_team = team
            possession = f"p{self.poss_n:02d}"
        i = len(self.rows)
        row = {
            "schema_version": "1.0", "match_id": MATCH_ID, "event_id": f"e{i + 1:03d}",
            "sequence": FIRST_SEQUENCE + i, "period": 2, "event_time_ms": self.t, "team_id": team,
            "player_id": pid(team, player) if player is not None else None, "possession_id": possession,
            "recipient_player_id": pid(team, recipient) if recipient is not None else None,
            "pressured_player_id": pid("nbr", pressured) if pressured is not None else None,
            "type": typ, "outcome": outcome,
            "x": self._j(px, 105.0, fixed_start), "y": self._j(py, 68.0, fixed_start), "end_x": ex, "end_y": ey,
            "scenario_seed": self.seed, "synthetic": True,
        }
        self.rows.append(row)
        self.cursor = (ex, ey) if ex is not None else (row["x"], row["y"])
        return row["event_id"]


def build(seed: int) -> tuple[ScenarioMeta, list[dict]]:
    b = Builder(seed)
    moments: dict[str, list[str]] = {}

    # a. patient build-up
    b.cursor = POS[A_CHAIN[0]]
    first = None
    for frm, to in zip(A_CHAIN, A_CHAIN[1:]):
        eid = b.add(2600, "nbr", frm, "pass", "complete", end=POS[to], recipient=to)
        first = first or eid
    moments["a"] = [first, eid]
    holder = A_CHAIN[-1]

    # b. Harbour press, Northbridge pass completion drops
    first = None
    for k, (target, ok, h_kind, h_player, h_to, n_kind, n_player) in enumerate(B_CYCLES):
        for j in range(2):
            eid = b.add(2200 if (k, j) == (0, 0) else 1700, "hba", PRESSERS[(2 * k + j) % 5], "pressure",
                        None, pressured=holder)
            first = first or eid
        tx, ty = POS[target]
        if ok:
            b.add(1500, "nbr", holder, "pass", "complete", end=(tx, ty), recipient=target)
            holder = target
            continue
        b.add(1500, "nbr", holder, "pass", "incomplete", end=(tx + 4, ty - 3), recipient=target)
        sx, sy = b.cursor
        b.add(1100, "hba", h_player, h_kind, "won" if h_kind == "tackle" else None)
        # Harbour's pass is only completed when Northbridge regain by tackling its recipient;
        # a recovery or interception needs an incomplete pass to explain the turnover.
        h_ok = n_kind == "tackle"
        b.add(1700, "hba", h_player, "pass", "complete" if h_ok else "incomplete",
              end=(sx - 3, sy + 5), recipient=h_to)
        b.add(1400, "nbr", n_player, n_kind, "won" if n_kind == "tackle" else None)
        holder = n_player
    for j in range(2):
        b.add(1700, "hba", PRESSERS[j], "pressure", None, pressured=holder)
    eid = b.add(1500, "nbr", holder, "pass", "incomplete", end=(32, 36), recipient=6)
    moments["b"] = [first, eid]
    b_secs = round((b.rows[-1]["event_time_ms"] - b.rows[int(first[1:]) - 1]["event_time_ms"]) / 1000)

    # c. fast counter: high recovery, <= 4 actions, goal
    c0 = b.add(1200, "hba", 8, "interception", None)
    b.add(2400, "hba", 8, "pass", "complete", end=(21, 30), recipient=10)
    b.add(2600, "hba", 10, "carry", "complete", end=(13, 33))
    c1 = b.add(3000, "hba", 10, "shot", "goal", end=(0.0, 35), fixed_end=True)
    moments["c"] = [c0, c1]

    # d. Northbridge possession, low threat, one blocked shot
    d0 = b.add(30_000, "nbr", 9, "kick_off", None, x=52.5, y=34, fixed_start=True)
    holder = 9
    for idx, (target, wx, wy) in enumerate(D_WAYPOINTS):
        if idx == D_FAIL:
            b.add(2400, "nbr", holder, "pass", "incomplete", end=(wx - 4, wy + 4), recipient=target)
            b.add(900, "hba", 6, "ball_recovery", None)
            b.add(1100, "nbr", 6, "tackle", "won")
            holder = 6
            continue
        b.add(2400, "nbr", holder, "pass", "complete", end=(wx, wy), recipient=target)
        holder = target
    b.add(2600, "nbr", 10, "carry", "complete", end=(78, 42))
    b.add(1600, "nbr", 10, "shot", "blocked", end=(90, 40))
    d1 = b.add(900, "hba", 4, "clearance", None)
    moments["d"] = [d0, d1]

    desc = {
        "a": "Northbridge build up patiently with short passes in their own half; no threat.",
        "b": f"Harbour press in Northbridge's half for {b_secs} seconds; Northbridge pass completion drops.",
        "c": "Harbour win the ball high up the pitch and score within 10 seconds (0-1).",
        "d": "Northbridge respond with possession but only low-threat passes and one blocked shot.",
    }
    meta = ScenarioMeta.model_validate({
        "schema_version": "1.0", "match_id": MATCH_ID, "scenario_seed": seed,
        "title": "Northbridge FC v Harbour Athletic - Harbour counter-attack, period 2 (58:00-62:00)",
        "teams": [{"id": "nbr", "name": "Northbridge FC", "side": "home"},
                  {"id": "hba", "name": "Harbour Athletic", "side": "away"}],
        "players": [{"id": pid(t, n), "team_id": t, "name": names[n - 1], "shirt_number": n}
                    for t, names in (("nbr", NBR_NAMES), ("hba", HBA_NAMES)) for n in range(1, 12)],
        "initial_score": {"home": 0, "away": 0}, "segment_start_ms": START_MS, "segment_end_ms": 62 * 60_000,
        "moments": [{"key": k, "description": desc[k], "first_event_id": moments[k][0],
                     "last_event_id": moments[k][1]} for k in "abcd"],
        "synthetic": True,
    })
    return meta, b.rows


def render(seed: int = SEED) -> dict[str, bytes]:
    meta, rows = build(seed)
    events = [MatchEvent.model_validate(r).model_dump(mode="json") for r in rows]
    return {
        "meta.json": (json.dumps(meta.model_dump(mode="json"), indent=2) + "\n").encode(),
        "events.jsonl": "".join(json.dumps(e) + "\n" for e in events).encode(),
    }


def main() -> None:
    for name, data in render().items():
        (HERE / name).write_bytes(data)


if __name__ == "__main__":
    main()
