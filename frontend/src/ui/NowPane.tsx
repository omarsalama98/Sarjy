/**
 * The current turn, full treatment. Older turns belong on the trail.
 */
import { FactCard } from "./FactCard";
import { PlaceStrip } from "./PlaceStrip";
import { fmt, registerLabel, type Turn } from "../turns";

export function NowPane({ turn, rtl = false }: { turn: Turn; rtl?: boolean }): JSX.Element {
  const kept = turn.segments.filter((s) => s.ok).length;
  const rejected = turn.segments.length - kept;

  return (
    <article className="now-pane turn">
      {turn.transcript && (
        <p className="transcript" dir={rtl ? "rtl" : undefined}>
          <span className="who" dir="ltr">You</span>
          {turn.transcript}
        </p>
      )}
      {turn.factCard && <FactCard card={turn.factCard} />}
      {turn.places && turn.places.length > 0 && <PlaceStrip places={turn.places} />}
      {turn.reply && (
        <p className="reply" dir={rtl ? "rtl" : undefined}>
          <span className="who" dir="ltr">Sarjy</span>
          {turn.reply}
        </p>
      )}
      {turn.failed && (
        <p className="notice turn-failed">
          ({turn.failed.stage}) {turn.failed.message}
        </p>
      )}
      {turn.segments.length > 0 && (
        <details className="audit" {...(rejected > 0 ? { open: true } : {})}>
          <summary>
            What she was allowed to say
            <span className="audit-count">
              {kept} spoken · {rejected} refused
            </span>
          </summary>
          <ul className="segments" aria-live="off">
            {turn.segments.map((s, i) => (
              <li
                key={i}
                className={`segment segment-${registerLabel(s.kind)}${s.ok ? "" : " segment-rejected"}`}
              >
                <span className="segment-kind">{registerLabel(s.kind)}</span>{" "}
                <span className="segment-text">
                  {s.kind === "quoted" && s.ok && s.attribution ? `${s.attribution} "${s.text}"` : s.text}
                </span>
                {!s.ok && s.reason && <span className="segment-reason"> — rejected: {s.reason}</span>}
                {s.ok && s.citation && (
                  <span className="segment-provenance">
                    {" "}
                    ({s.citation}
                    {s.layer ? `, ${s.layer}` : ""}
                    {s.source_date ? `, ${s.source_date}` : ""})
                  </span>
                )}
              </li>
            ))}
          </ul>
          {rejected > 0 && (
            <p className="audit-note">
              The model wrote the struck-through line. Deterministic code refused to speak it.
            </p>
          )}
        </details>
      )}
      {turn.hedged && (
        <p className="notice hedge-notice">
          A tool result came back but nothing was sourced or quoted from it — flagged for review.
        </p>
      )}
      {turn.timings && (
        <p className="turn-metrics" aria-live="off">
          {fmt(turn.timings.firstAudioMs)} voice-to-voice
        </p>
      )}
    </article>
  );
}
