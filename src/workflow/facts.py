"""Deterministic Facts: the only values model-written text may quote, by {key}.

Every fact is computed from events visible at the trigger (sequence <= trigger_seq);
a value that does not exist (e.g. a ratio with no attempts) simply has no fact."""

from __future__ import annotations

import re
from collections.abc import Sequence

from contracts.agents import Fact
from contracts.api import Card, MetricName, MetricValue
from contracts.events import MatchEvent, ScenarioMeta
from domain.cards import fmt_clock
from domain.metrics import team_metrics
from domain.moment import events_in_window, period_start_ms, possession_summary, round_half_up
from domain.snapshot import score_after, visible_events

WINDOW_S = 60

_COUNT_DESC = {
    MetricName.passes_attempted: "Passes attempted by {team}",
    MetricName.passes_completed: "Passes completed by {team}",
    MetricName.pressures: "Pressures by {team} anywhere on the pitch",
    MetricName.pressures_opp_half: "Pressures by {team} in {opp}'s half",
    MetricName.ball_wins: "Ball wins by {team} (tackles won, interceptions, recoveries)",
    MetricName.high_ball_wins: "Ball wins by {team} in {opp}'s half",
    MetricName.shots: "Shots by {team}",
    MetricName.goals: "Goals scored by {team}",
}


def _key_part(raw: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", raw.lower())


def _window_facts(prefix: str, label: str, teams, vis: Sequence[MatchEvent], period: int,
                  start_ms: int, end_ms: int) -> list[Fact]:
    rng = f"{fmt_clock(start_ms)}-{fmt_clock(end_ms)}"
    win = events_in_window(vis, period, start_ms, end_ms)
    out: list[Fact] = []
    for team in teams:
        opp = next(t for t in teams if t.id != team.id)
        tk = _key_part(team.id)
        for m in team_metrics(team.id, team.side, win):
            if m.name == MetricName.pass_completion:
                out += _ratio_facts(prefix, label, team.name, tk, rng, m)
                continue
            desc = _COUNT_DESC[m.name].format(team=team.name, opp=opp.name)
            out.append(Fact(key=f"{prefix}{m.name.value}.{tk}", text=str(int(m.value or 0)),
                            meaning=f"{label}{desc}, {rng} (count)", event_ids=m.event_ids))
    return out


def _ratio_facts(prefix: str, label: str, team_name: str, tk: str, rng: str, m: MetricValue) -> list[Fact]:
    if not m.denominator or m.numerator is None:  # no attempts: the ratio does not exist
        return []
    base = f"{prefix}pass_completion.{tk}"
    who = f"{label}{team_name}'s"
    num, den = m.numerator, m.denominator
    return [
        Fact(key=f"{base}.pct", text=f"{round_half_up(100 * num, den)}%",
             meaning=f"{who} pass completion, completed of attempted passes, {rng} (percent)",
             event_ids=m.event_ids),
        Fact(key=f"{base}.frac", text=f"{num} of {den}",
             meaning=f"{who} passes completed of attempted, {rng} (completed of attempted passes)",
             event_ids=m.event_ids),
        Fact(key=f"{base}.num", text=str(num),
             meaning=f"{who} completed passes, {rng} (count)", event_ids=m.event_ids),
        Fact(key=f"{base}.den", text=str(den),
             meaning=f"{who} attempted passes, {rng} (count)", event_ids=m.event_ids),
    ]


def build_facts(meta: ScenarioMeta, events: Sequence[MatchEvent], card: Card,
                trigger_seq: int) -> tuple[Fact, ...]:
    vis = visible_events(events, trigger_seq)
    trigger = vis[-1]
    teams = list(meta.teams)
    names = {t.id: t.name for t in teams}
    end = trigger.event_time_ms
    start = end - WINDOW_S * 1000
    facts: list[Fact] = _window_facts("", "", teams, vis, trigger.period, start, end)

    prev_start = start - WINDOW_S * 1000
    first = period_start_ms(vis, trigger.period)
    if first is not None and prev_start >= first:
        facts += _window_facts("prev.", "Previous window: ", teams, vis, trigger.period, prev_start, start)

    score, goal_ids = score_after(meta, vis)
    home = next(t for t in teams if t.side == "home")
    away = next(t for t in teams if t.side == "away")
    facts.append(Fact(key="score", text=f"{score.home}-{score.away}",
                      meaning=(f"Score after this moment, home-away: {home.name} (home) "
                               f"{score.home}, {away.name} (away) {score.away}"), event_ids=goal_ids))
    for t, n in ((home, score.home), (away, score.away)):
        facts.append(Fact(key=f"score.{_key_part(t.id)}", text=str(n),
                          meaning=f"Goals by {t.name} in the match after this moment", event_ids=goal_ids))

    facts.append(Fact(key="clock", text=fmt_clock(end), meaning="Match clock at this moment (mm:ss)",
                      event_ids=(trigger.event_id,)))
    facts.append(Fact(key="window", text=f"{fmt_clock(start)}-{fmt_clock(end)}",
                      meaning="Match clock range of the last window before this moment (mm:ss-mm:ss)"))
    facts.append(Fact(key="window_s", text=str(WINDOW_S), meaning="Length of that window in seconds"))

    by_id = {e.event_id: e for e in vis}
    for eid in card.evidence_event_ids:
        ev = by_id.get(eid)
        if ev is not None:
            facts.append(Fact(key=f"t.{_key_part(eid)}", text=fmt_clock(ev.event_time_ms),
                              meaning=f"Match clock of event {eid} (mm:ss)", event_ids=(eid,)))

    poss = possession_summary(vis, trigger, {t.id: t.side for t in teams})
    if poss is not None:
        who = names.get(poss.team_id, poss.team_id)
        tenths = round_half_up(poss.duration_ms, 100)
        facts += [
            Fact(key="poss.team", text=who, meaning="Team in possession at this moment",
                 event_ids=poss.event_ids),
            Fact(key="poss.actions", text=str(len(poss.event_ids)),
                 meaning=f"On-ball actions by {who} in the current possession up to this moment (count)",
                 event_ids=poss.event_ids),
            Fact(key="poss.duration_s", text=f"{tenths // 10}.{tenths % 10}",
                 meaning=f"Duration in seconds from the start of {who}'s current possession to this moment",
                 event_ids=poss.event_ids),
            Fact(key="poss.start_dist_m", text=str(poss.start_dist_m),
                 meaning=f"Distance in metres from the goal {who} attack to where their current possession began",
                 event_ids=poss.event_ids[:1]),
        ]
    return tuple(facts)
