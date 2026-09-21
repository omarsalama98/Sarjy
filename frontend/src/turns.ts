import type { FactCardMessage, PlaceCard, SegmentWire } from "./protocol";

export interface Turn {
  id: string;
  at: number;
  transcript: string | null;
  reply: string | null;
  segments: SegmentWire[];
  factCard: FactCardMessage | null;
  places: PlaceCard[] | null;
  hedged: boolean;
  failed: { stage: string; message: string } | null;
  timings: { firstAudioMs: number | null; endpointMs: number; redemptionMs: number } | null;
}

export function registerLabel(kind: SegmentWire["kind"]): string {
  return kind === "judgement" ? "view" : kind;
}

export function fmt(ms: number | null): string {
  return ms === null ? "—" : `${(ms / 1000).toFixed(2)} s`;
}
