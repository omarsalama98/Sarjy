/**
 * One older turn, collapsed to a line. Click to expand the same audit the
 * reviewer needs — it is not gone, just not stamped on every row.
 */
import { useState } from "react";
import { NowPane } from "./NowPane";
import type { Turn } from "../turns";

export function TrailRow({ turn, rtl = false }: { turn: Turn; rtl?: boolean }): JSX.Element {
  const [open, setOpen] = useState(false);
  const you = turn.transcript ?? "…";
  const her = turn.reply ?? (turn.failed ? turn.failed.message : "…");

  return (
    <div className="trail-row">
      <button type="button" className="trail-line" onClick={() => setOpen((v) => !v)}>
        <span className="who">You</span>
        <span className="trail-text">{you}</span>
        <span className="who">Sarjy</span>
        <span className="trail-text">{her}</span>
      </button>
      {open && <NowPane turn={turn} rtl={rtl} />}
    </div>
  );
}
