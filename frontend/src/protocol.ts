/**
 * WebSocket message protocol -- mirrors backend/app/pipeline/protocol.py by
 * hand. No zod: twenty lines Omar can read out loud beats a dependency
 * whose failure modes he'd have to explain (docs/plans/blocks/01-skeleton-deploy.md).
 *
 * Reserved for later blocks -- named so the envelope never needs a redesign,
 * but not built here: start/end/barge, binary audio, transcript (Block 2),
 * timings (Block 3), segments (Block 4/6), quota (Block 5), memory (Block 7).
 */

export const PROTOCOL_VERSION = 1;

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

export type ClientMessage = HelloMessage | PingMessage | ByeMessage;

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

export type ServerMessage = ReadyMessage | StateMessage | PongMessage | ErrorMessage | ClosingMessage;

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

    default:
      console.warn(`sarjy: unknown server message type ${JSON.stringify(m.t)}, ignoring`);
      return null;
  }
}
