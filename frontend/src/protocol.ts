/**
 * WebSocket message protocol -- mirrors backend/app/pipeline/protocol.py by
 * hand. No zod: twenty lines Omar can read out loud beats a dependency
 * whose failure modes he'd have to explain (docs/plans/blocks/01-skeleton-deploy.md).
 *
 * Block 2 adds start/end/barge (client-driven turn boundaries) and
 * transcript/reply/audio_start/audio_end/turn_failed (the server's half of
 * a turn). Binary frames carry the raw PCM audio itself; these messages are
 * how the two sides agree on what a run of binary frames means.
 *
 * Block 3 adds client_timing (c->s) -- the two latency legs only the
 * browser can see.
 *
 * Block A (the deep dive) adds `segments` (the gated answer -- kept AND
 * rejected, rejection struck through), `quota` (the vendor request
 * ledger), and `fact_card` (D15's payload -- received and logged here;
 * Block C renders it, nothing paints it yet).
 *
 * Block B (memory) adds sign_in/sign_out/forget (c->s) and `memory` (s->c),
 * which drives the whole "what Sarjy remembers" panel. A server->client
 * `timings` message stays reserved and unbuilt -- the client already knows
 * its own headline number, so no round trip back is needed to show it on
 * screen.
 */

// Bumped from 4: this block adds sign_in/sign_out/forget (c->s) and memory
// (s->c) to the wire. A stale tab left open fails the handshake cleanly ("A
// new version is available -- reload.") instead of sending messages the old
// server half-understands. backend/app/pipeline/protocol.py's own constant
// moves in the SAME commit -- a mismatch here fails every handshake.
export const PROTOCOL_VERSION = 5;

// ---------------------------------------------------------------------------
// Client -> server
// ---------------------------------------------------------------------------

export interface HelloMessage {
  t: "hello";
  v: number;
  session_id: string | null;
  client_ts_ms: number;
}

export interface PingMessage {
  t: "ping";
  id: string;
  client_ts_ms: number;
}

export interface ByeMessage {
  t: "bye";
  reason: "rotate" | "leave";
}

export interface StartMessage {
  t: "start";
  turn_id: string;
  client_ts_ms: number;
}

export interface EndMessage {
  t: "end";
  turn_id: string;
  samples: number;
  client_ts_ms: number;
}

export interface BargeMessage {
  t: "barge";
  turn_id: string;
}

/**
 * The two legs only the browser can see -- endpointing and first audio
 * out -- plus the VAD setting that produced them. Sent once per turn (App.tsx's
 * reportTurnTiming enforces exactly one send), at the first of: first audio
 * buffer scheduled, or turn_failed. `endpoint_ms`/`first_audio_ms` are
 * nullable because a barge before any audio ever played means neither leg
 * completed -- the message is still sent so the server's merge has a
 * turn_id to key off.
 */
export interface ClientTimingMessage {
  t: "client_timing";
  turn_id: string;
  endpoint_ms: number | null;
  first_audio_ms: number | null;
  redemption_ms: number;
  output_latency_ms: number | null;
}

/** Typed sign-in -- name + 4-digit PIN (D3). The reliable path; voice
 * sign-in (D8) is a deterministic sub-flow on the server, not a wire type. */
export interface SignInMessage {
  t: "sign_in";
  name: string;
  pin: string;
}

export interface SignOutMessage {
  t: "sign_out";
}

/** `key: null` forgets every fact but keeps the signed-in identity -- the
 * panel's "Forget everything" button. */
export interface ForgetMessage {
  t: "forget";
  key: string | null;
}

export type ClientMessage =
  | HelloMessage
  | PingMessage
  | ByeMessage
  | StartMessage
  | EndMessage
  | BargeMessage
  | ClientTimingMessage
  | SignInMessage
  | SignOutMessage
  | ForgetMessage;

// ---------------------------------------------------------------------------
// Server -> client
// ---------------------------------------------------------------------------

export type ConversationState = "idle" | "listening" | "thinking" | "speaking";

export interface ReadyMessage {
  t: "ready";
  v: number;
  session_id: string;
  resumed: boolean;
  connection_n: number;
  rotate_after_ms: number;
  hard_max_ms: number;
  server_started_at_ms: number;
  seq: number;
  ts_ms: number;
}

export interface StateMessage {
  t: "state";
  value: ConversationState;
  seq: number;
  ts_ms: number;
}

export interface PongMessage {
  t: "pong";
  id: string;
  client_ts_ms: number;
  seq: number;
  ts_ms: number;
}

export type ErrorCode = "bad_message" | "protocol_version" | "unsupported" | "internal";

export interface ErrorMessage {
  t: "error";
  code: ErrorCode;
  message: string;
  recoverable: boolean;
  seq: number;
  ts_ms: number;
}

export type ClosingReason = "rotate_ceiling" | "shutdown" | "superseded" | "protocol_version";

export interface ClosingMessage {
  t: "closing";
  reason: ClosingReason;
  reconnect: boolean;
  seq: number;
  ts_ms: number;
}

export interface TranscriptMessage {
  t: "transcript";
  turn_id: string;
  text: string;
  seq: number;
  ts_ms: number;
}

export interface ReplyMessage {
  t: "reply";
  turn_id: string;
  text: string;
  seq: number;
  ts_ms: number;
}

export interface AudioStartMessage {
  t: "audio_start";
  turn_id: string;
  sample_rate: number;
  seq: number;
  ts_ms: number;
}

export interface AudioEndMessage {
  t: "audio_end";
  turn_id: string;
  samples: number;
  seq: number;
  ts_ms: number;
}

export type TurnFailedStage = "audio" | "stt" | "llm" | "tool" | "gate" | "tts";

export interface TurnFailedMessage {
  t: "turn_failed";
  turn_id: string;
  stage: TurnFailedStage;
  message: string;
  seq: number;
  ts_ms: number;
}

// -- Block A: the grounding gate, on the wire --------------------------------

export type Register = "sourced" | "quoted" | "judgement";
export type ToolLayer = "live" | "cache" | "map" | "csv";

export type GateReason =
  | "unknown_tool_call_id"
  | "absent_path"
  | "field_mismatch"
  | "no_placeholder"
  | "bare_digit"
  | "number_word"
  | "value_too_long"
  | "field_not_allowlisted"
  | "wrong_pair"
  | "quote_not_allowlisted"
  | "quoted_text_supplied"
  | "injection_marker"
  | "too_many_quotes"
  | "malformed_line";

/** One rendered segment, kept OR rejected -- `ok: false` is still sent and
 * shown struck through with its `reason`. That visibility is the demo. */
export interface SegmentWire {
  kind: Register;
  text: string;
  ok: boolean;
  reason: GateReason | null;
  attribution: string | null; // quoted only: "According to Travel Buddy:"
  field: string | null; // quoted only: the path the words came from
  citation: string | null;
  source_url: string | null;
  source_date: string | null;
  layer: ToolLayer | null;
}

export interface SegmentsMessage {
  t: "segments";
  turn_id: string;
  segments: SegmentWire[];
  spoken: string; // EXACTLY the string handed to TTS -- the proof, on screen
  hedged: boolean;
  seq: number;
  ts_ms: number;
}

export interface QuotaMessage {
  t: "quota";
  total: number;
  spent: number;
  reserve: number;
  remaining: number;
  seq: number;
  ts_ms: number;
}

export interface FactRowWire {
  path: string;
  label: string;
  value: string;
  kind: "sourced" | "quoted";
}

/** D15 -- Block A emits this, Block C renders it. Received and logged here
 * (verification turn 8); nothing paints it on screen yet. */
export interface FactCardMessage {
  t: "fact_card";
  turn_id: string;
  passport: string;
  passport_name: string;
  destination: string;
  destination_name: string;
  covered: boolean;
  facts: FactRowWire[];
  layer: ToolLayer | null;
  degraded: boolean;
  source_name: string | null;
  source_url: string | null;
  source_date: string | null;
  retrieved: string | null;
  embassy_url: string | null;
  seq: number;
  ts_ms: number;
}

// -- Block B: memory, on the wire --------------------------------------------

export type FactKind = "profile" | "open";

/** One stored fact -- `quote` is the attribution, the demo's whole point:
 * "how do you know that?" is answered on screen, not in a console. */
export interface FactWire {
  key: string;
  label: string;
  value: string;
  kind: FactKind;
  learned_at: string; // ISO 8601 Z
  turn_id: string | null;
  quote: string | null;
}

/** Drives the ENTIRE "what Sarjy remembers" panel -- there is no
 * client-side memory state to drift; every change re-sends this whole
 * record rather than a diff. */
export interface MemoryMessage {
  t: "memory";
  tier: "anonymous" | "signed_in";
  name: string | null;
  facts: FactWire[];
  used: number;
  capacity: number;
  persisted: boolean;
  degraded: boolean;
  message: string | null;
  seq: number;
  ts_ms: number;
}

export type ServerMessage =
  | ReadyMessage
  | StateMessage
  | PongMessage
  | ErrorMessage
  | ClosingMessage
  | TranscriptMessage
  | ReplyMessage
  | AudioStartMessage
  | AudioEndMessage
  | TurnFailedMessage
  | SegmentsMessage
  | QuotaMessage
  | FactCardMessage
  | MemoryMessage;

function isConversationState(v: unknown): v is ConversationState {
  return v === "idle" || v === "listening" || v === "thinking" || v === "speaking";
}

/**
 * Hand-rolled parser, not a schema library. Forward-compatible in the
 * direction that matters (the server can be newer than a cached browser
 * bundle): an unknown "t" is logged once and ignored rather than thrown; an
 * unknown error.code still renders message/recoverable.
 */
export function parseServerMessage(raw: string): ServerMessage | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null || !("t" in data)) return null;
  const m = data as Record<string, unknown>;

  switch (m.t) {
    case "ready":
      if (
        typeof m.v === "number" &&
        typeof m.session_id === "string" &&
        typeof m.resumed === "boolean" &&
        typeof m.connection_n === "number" &&
        typeof m.rotate_after_ms === "number" &&
        typeof m.hard_max_ms === "number" &&
        typeof m.server_started_at_ms === "number" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "ready",
          v: m.v,
          session_id: m.session_id,
          resumed: m.resumed,
          connection_n: m.connection_n,
          rotate_after_ms: m.rotate_after_ms,
          hard_max_ms: m.hard_max_ms,
          server_started_at_ms: m.server_started_at_ms,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    case "state":
      if (isConversationState(m.value) && typeof m.seq === "number" && typeof m.ts_ms === "number") {
        return { t: "state", value: m.value, seq: m.seq, ts_ms: m.ts_ms };
      }
      return null;

    case "pong":
      if (
        typeof m.id === "string" &&
        typeof m.client_ts_ms === "number" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return { t: "pong", id: m.id, client_ts_ms: m.client_ts_ms, seq: m.seq, ts_ms: m.ts_ms };
      }
      return null;

    case "error":
      if (
        typeof m.code === "string" &&
        typeof m.message === "string" &&
        typeof m.recoverable === "boolean" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "error",
          code: m.code as ErrorCode,
          message: m.message,
          recoverable: m.recoverable,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    case "closing":
      if (
        typeof m.reason === "string" &&
        typeof m.reconnect === "boolean" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "closing",
          reason: m.reason as ClosingReason,
          reconnect: m.reconnect,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    case "transcript":
      if (
        typeof m.turn_id === "string" &&
        typeof m.text === "string" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return { t: "transcript", turn_id: m.turn_id, text: m.text, seq: m.seq, ts_ms: m.ts_ms };
      }
      return null;

    case "reply":
      if (
        typeof m.turn_id === "string" &&
        typeof m.text === "string" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return { t: "reply", turn_id: m.turn_id, text: m.text, seq: m.seq, ts_ms: m.ts_ms };
      }
      return null;

    case "audio_start":
      if (
        typeof m.turn_id === "string" &&
        typeof m.sample_rate === "number" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "audio_start",
          turn_id: m.turn_id,
          sample_rate: m.sample_rate,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    case "audio_end":
      if (
        typeof m.turn_id === "string" &&
        typeof m.samples === "number" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return { t: "audio_end", turn_id: m.turn_id, samples: m.samples, seq: m.seq, ts_ms: m.ts_ms };
      }
      return null;

    case "turn_failed":
      if (
        typeof m.turn_id === "string" &&
        typeof m.stage === "string" &&
        typeof m.message === "string" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "turn_failed",
          turn_id: m.turn_id,
          stage: m.stage as TurnFailedStage,
          message: m.message,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    case "segments":
      if (
        typeof m.turn_id === "string" &&
        Array.isArray(m.segments) &&
        typeof m.spoken === "string" &&
        typeof m.hedged === "boolean" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "segments",
          turn_id: m.turn_id,
          segments: m.segments as SegmentWire[],
          spoken: m.spoken,
          hedged: m.hedged,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    case "quota":
      if (
        typeof m.total === "number" &&
        typeof m.spent === "number" &&
        typeof m.reserve === "number" &&
        typeof m.remaining === "number" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "quota",
          total: m.total,
          spent: m.spent,
          reserve: m.reserve,
          remaining: m.remaining,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    case "fact_card":
      if (
        typeof m.turn_id === "string" &&
        typeof m.passport === "string" &&
        typeof m.passport_name === "string" &&
        typeof m.destination === "string" &&
        typeof m.destination_name === "string" &&
        typeof m.covered === "boolean" &&
        Array.isArray(m.facts) &&
        typeof m.degraded === "boolean" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "fact_card",
          turn_id: m.turn_id,
          passport: m.passport,
          passport_name: m.passport_name,
          destination: m.destination,
          destination_name: m.destination_name,
          covered: m.covered,
          facts: m.facts as FactRowWire[],
          layer: (m.layer ?? null) as ToolLayer | null,
          degraded: m.degraded,
          source_name: (m.source_name ?? null) as string | null,
          source_url: (m.source_url ?? null) as string | null,
          source_date: (m.source_date ?? null) as string | null,
          retrieved: (m.retrieved ?? null) as string | null,
          embassy_url: (m.embassy_url ?? null) as string | null,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    case "memory":
      if (
        (m.tier === "anonymous" || m.tier === "signed_in") &&
        Array.isArray(m.facts) &&
        typeof m.used === "number" &&
        typeof m.capacity === "number" &&
        typeof m.persisted === "boolean" &&
        typeof m.degraded === "boolean" &&
        typeof m.seq === "number" &&
        typeof m.ts_ms === "number"
      ) {
        return {
          t: "memory",
          tier: m.tier,
          name: (m.name ?? null) as string | null,
          facts: m.facts as FactWire[],
          used: m.used,
          capacity: m.capacity,
          persisted: m.persisted,
          degraded: m.degraded,
          message: (m.message ?? null) as string | null,
          seq: m.seq,
          ts_ms: m.ts_ms,
        };
      }
      return null;

    default:
      console.warn(`sarjy: unknown server message type ${JSON.stringify(m.t)}, ignoring`);
      return null;
  }
}
