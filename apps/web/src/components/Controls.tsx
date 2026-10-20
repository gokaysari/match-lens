import { SPEEDS, type Speed } from "../hooks";
import { mmss } from "../lib/format";

interface Props {
  index: number;
  last: number;
  clockMs: number;
  playing: boolean;
  speed: Speed;
  onIndex: (i: number) => void;
  onPlaying: (p: boolean) => void;
  onSpeed: (s: Speed) => void;
}

export function Controls({ index, last, clockMs, playing, speed, onIndex, onPlaying, onSpeed }: Props) {
  return (
    <section className="controls" aria-label="Replay controls">
      <div className="control-row">
        <button type="button" aria-label="Step back" onClick={() => onIndex(index - 1)} disabled={index <= 0}>
          <span aria-hidden="true">⏮</span> Step back
        </button>
        <button type="button" onClick={() => onPlaying(!playing)} aria-label={playing ? "Pause" : "Play"}>
          <span aria-hidden="true">{playing ? "⏸" : "▶"}</span>
        </button>
        <button type="button" aria-label="Step forward" onClick={() => onIndex(index + 1)} disabled={index >= last}>
          Step forward <span aria-hidden="true">⏭</span>
        </button>
        <div className="speeds" role="group" aria-label="Playback speed">
          {SPEEDS.map((s) => (
            <button key={s} type="button" aria-label={`Speed ${s}x`} aria-pressed={speed === s}
              onClick={() => onSpeed(s)}>
              {s}x
            </button>
          ))}
        </div>
        <span className="replay-clock">{mmss(clockMs)}</span>
      </div>
      <input
        type="range"
        aria-label="Replay position"
        aria-valuetext={`Event ${index + 1} of ${last + 1}, ${mmss(clockMs)}`}
        min={0}
        max={last}
        value={index}
        onChange={(e) => onIndex(Number(e.target.value))}
      />
    </section>
  );
}
