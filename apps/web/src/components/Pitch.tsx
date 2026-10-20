import { useRef } from "react";
import type { MatchEvent, ScenarioMeta } from "../api/types";
import { mmss } from "../lib/format";

export const TEAM_COLORS = { home: "#1d4ed8", away: "#c2410c" } as const;
const TRAIL = 6;
const ARROW_TYPES = new Set(["pass", "carry", "shot"]);

export function playerName(meta: ScenarioMeta, id: string): string {
  return meta.players.find((p) => p.id === id)?.name ?? id;
}

export function describeEvent(e: MatchEvent, meta: ScenarioMeta): string {
  const team = meta.teams.find((t) => t.id === e.team_id)?.name ?? e.team_id;
  const who = e.player_id ? `, ${playerName(meta, e.player_id)}` : "";
  const to = e.recipient_player_id ? ` to ${playerName(meta, e.recipient_player_id)}` : "";
  const outcome = e.outcome ? ` (${e.outcome.replace(/_/g, " ")})` : "";
  return `${mmss(e.event_time_ms)} ${team} ${e.type.replace(/_/g, " ")}${who}${to}${outcome}`;
}

function PitchMarkings() {
  const line = { fill: "none", stroke: "#ffffff", strokeWidth: 0.25 } as const;
  return (
    <g {...line}>
      <rect x="0" y="0" width="105" height="68" />
      <line x1="52.5" y1="0" x2="52.5" y2="68" />
      <circle cx="52.5" cy="34" r="9.15" />
      <circle cx="52.5" cy="34" r="0.3" fill="#ffffff" />
      <rect x="0" y="13.84" width="16.5" height="40.32" />
      <rect x="88.5" y="13.84" width="16.5" height="40.32" />
      <rect x="0" y="24.84" width="5.5" height="18.32" />
      <rect x="99.5" y="24.84" width="5.5" height="18.32" />
    </g>
  );
}

export function Pitch({ events, index, meta }: { events: MatchEvent[]; index: number; meta: ScenarioMeta }) {
  const warned = useRef(new Set<string>());
  const sideOf = (teamId: string) => meta.teams.find((t) => t.id === teamId)?.side;
  const upTo = events.slice(0, index + 1);
  const drawable = upTo
    .filter((e) => {
      if (e.x === null || e.y === null) return false;
      if (sideOf(e.team_id)) return true;
      if (!warned.current.has(e.team_id)) {
        warned.current.add(e.team_id);
        console.warn(`Pitch: skipping events of unknown team_id "${e.team_id}"`);
      }
      return false;
    })
    .slice(-TRAIL);
  const latest = events[index]!;
  return (
    <figure className="pitch">
      <svg
        viewBox="0 0 105 68"
        role="img"
        aria-label={describeEvent(latest, meta)}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {(["home", "away"] as const).map((s) => (
            <marker key={s} id={`arrow-${s}`} viewBox="0 0 6 6" refX="5" refY="3"
              markerWidth="3.5" markerHeight="3.5" orient="auto-start-reverse">
              <path d="M0,0 L6,3 L0,6 z" fill={TEAM_COLORS[s]} />
            </marker>
          ))}
        </defs>
        <rect x="0" y="0" width="105" height="68" fill="#2e7d32" />
        {/* contract frame: origin bottom-left, so flip y */}
        <g transform="translate(0,68) scale(1,-1)">
          <PitchMarkings />
          {drawable.map((e, i) => {
            const side = sideOf(e.team_id)!;
            const color = TEAM_COLORS[side];
            const isLatest = e === latest;
            const opacity = isLatest ? 1 : 0.35 + (0.4 * (i + 1)) / drawable.length;
            const x = e.x as number;
            const y = e.y as number;
            return (
              <g key={e.event_id} data-event-id={e.event_id} data-latest={isLatest ? "true" : "false"} opacity={opacity}>
                {e.type === "pressure" ? (
                  <circle cx={x} cy={y} r={isLatest ? 2.2 : 1.6} fill="none" stroke={color}
                    strokeWidth={isLatest ? 0.7 : 0.45} strokeDasharray="0.8 0.5" />
                ) : (
                  <>
                    {ARROW_TYPES.has(e.type) && e.end_x !== null && e.end_y !== null && (
                      <line x1={x} y1={y} x2={e.end_x} y2={e.end_y} stroke={color}
                        strokeWidth={isLatest ? 0.7 : 0.4} markerEnd={`url(#arrow-${side})`} />
                    )}
                    <circle cx={x} cy={y} r={isLatest ? 1.4 : 0.9} fill={color} stroke="#ffffff"
                      strokeWidth={isLatest ? 0.4 : 0.2} />
                  </>
                )}
              </g>
            );
          })}
        </g>
      </svg>
      <figcaption className="legend">
        <ul>
          {meta.teams.map((t) => (
            <li key={t.id}>
              <span className="swatch" style={{ background: TEAM_COLORS[t.side] }} aria-hidden="true" />
              {t.name} ({t.side}) attacks {t.side === "home" ? "→ right" : "← left"}
            </li>
          ))}
          <li>Dot = on-ball event, arrow = pass/carry/shot, ring = pressure</li>
        </ul>
      </figcaption>
    </figure>
  );
}
