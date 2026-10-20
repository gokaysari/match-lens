// Hand-written mirror of src/contracts (schema_version 1.0). Field names are the JSON ones.

export type EventType =
  | "kick_off" | "pass" | "carry" | "dribble" | "pressure" | "tackle" | "interception"
  | "ball_recovery" | "clearance" | "shot" | "foul" | "out_of_play" | "substitution";

export type Outcome =
  | "complete" | "incomplete" | "won" | "lost" | "saved" | "blocked" | "off_target" | "goal";

export interface MatchEvent {
  schema_version: "1.0";
  match_id: string;
  event_id: string;
  sequence: number;
  period: 1 | 2;
  event_time_ms: number;
  team_id: string;
  player_id: string | null;
  possession_id: string | null;
  recipient_player_id: string | null;
  pressured_player_id: string | null;
  type: EventType;
  outcome: Outcome | null;
  x: number | null;
  y: number | null;
  end_x: number | null;
  end_y: number | null;
  scenario_seed: number;
  synthetic: true;
}

export interface Team { id: string; name: string; side: "home" | "away" }
export interface Player { id: string; team_id: string; name: string; shirt_number: number }
export interface Score { home: number; away: number }

/** GET /meta: what a client may know before the replay starts (contract MatchInfo). */
export interface MatchInfo {
  schema_version: "1.0";
  match_id: string;
  teams: Team[];
  players: Player[];
  initial_score: Score;
  segment_start_ms: number;
  segment_end_ms: number;
  synthetic: true;
}

export interface ApiErrorBody { code: string; message: string }

export interface Snapshot {
  schema_version: "1.0";
  match_id: string;
  snapshot_id: string;
  watermark_seq: number;
  watermark_event_id: string;
  clock_ms: number;
  period: 1 | 2;
  score: Score;
  goal_event_ids: string[];
  last_event: MatchEvent;
  synthetic: true;
}

export interface EventPage {
  schema_version: "1.0";
  match_id: string;
  snapshot_id: string;
  events: MatchEvent[];
  synthetic: true;
}

export type MetricName =
  | "passes_attempted" | "passes_completed" | "pass_completion" | "pressures" | "pressures_opp_half"
  | "ball_wins" | "high_ball_wins" | "shots" | "goals";

export interface MetricValue {
  name: MetricName;
  team_id: string;
  value: number | null;
  unit: "count" | "ratio";
  numerator: number | null;
  denominator: number | null;
  definition_version: "metrics-v1";
  event_ids: string[];
}

export interface WindowMetrics {
  schema_version: "1.0";
  match_id: string;
  snapshot_id: string;
  window_start_ms: number;
  window_end_ms: number;
  metrics: MetricValue[];
  synthetic: true;
}

export type CardKind = "goal" | "press_surge";

export interface Card {
  card_id: string;
  kind: CardKind;
  template_id: "fact-card";
  title: string;
  body: string;
  trigger_seq: number;
  trigger_clock_ms: number;
  expires_at_ms: number;
  metrics: MetricValue[];
  evidence_event_ids: string[];
  origin: "template";
}

export interface CardList {
  schema_version: "1.0";
  match_id: string;
  snapshot_id: string;
  cards: Card[];
  synthetic: true;
}
