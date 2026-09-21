/**
 * The persona. Concentric SVG rings driven by a rAF loop that writes CSS
 * custom properties onto the element -- never setState at 60fps.
 *
 * Levels are sampled from refs the parent owns (mic AnalyserNode, PCM RMS
 * of TTS chunks). Under prefers-reduced-motion the loop never starts and
 * each state is a static ring.
 */

import { useEffect, useRef, type MutableRefObject, type RefObject } from "react";
import type { MicAnalyser } from "../audio/level";

export type OrbRing =
  | "ring-loading"
  | "ring-idle"
  | "ring-listening"
  | "ring-thinking"
  | "ring-speaking"
  | "ring-error";

interface OrbProps {
  ring: OrbRing;
  reducedMotion: boolean;
  micAnalyserRef: RefObject<MicAnalyser | null>;
  speakLevelRef: MutableRefObject<number>;
}

export function Orb({ ring, reducedMotion, micAnalyserRef, speakLevelRef }: OrbProps): JSX.Element {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el || reducedMotion) {
      el?.style.setProperty("--orb-level", "0");
      el?.style.setProperty("--orb-breathe", "0.4");
      return;
    }

    let raf = 0;
    const loop = (t: number) => {
      const breathe = 0.5 + 0.5 * Math.sin(t / 1400);
      let level = 0;
      if (ring === "ring-listening") {
        level = micAnalyserRef.current?.sample() ?? 0;
      } else if (ring === "ring-speaking") {
        level = speakLevelRef.current;
      } else if (ring === "ring-idle" || ring === "ring-loading") {
        level = breathe * 0.18;
      }
      el.style.setProperty("--orb-level", level.toFixed(3));
      el.style.setProperty("--orb-breathe", breathe.toFixed(3));
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [ring, reducedMotion, micAnalyserRef, speakLevelRef]);

  return (
    <div ref={rootRef} className={`orb ${ring}`} aria-hidden="true">
      <svg viewBox="0 0 100 100">
        <circle className="orb-ring orb-ring-3" cx="50" cy="50" r="42" />
        <circle className="orb-ring orb-ring-2" cx="50" cy="50" r="32" />
        <circle className="orb-ring orb-ring-1" cx="50" cy="50" r="22" />
        <text className="orb-mark" x="50" y="50" textAnchor="middle" dominantBaseline="central">
          S
        </text>
      </svg>
    </div>
  );
}
