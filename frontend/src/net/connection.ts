/**
 * The connection manager: reconnect-and-resume, transparently.
 *
 * Modal kills a WebSocket somewhere in (5s, 160s] (measured,
 * docs/measurements/day1-spikes.md S1). Without reconnect the demo dies
 * mid-conversation, live, in front of the reviewer. The design rests on one
 * invariant:
 *
 *     A turn never spans a connection.
 *
 * Because of that, "resume" only ever carries identity (a session id) --
 * never mid-turn audio or tool state. Two rules hold the invariant:
 *
 *   1. Rotate the socket only when the conversation is idle. If the timer
 *      fires mid-turn, rotation waits for the next idle transition.
 *   2. `ensureFresh()` refuses to let a turn start if the socket doesn't
 *      have enough life left to plausibly finish it -- Block 2 awaits this
 *      before sending `start`.
 *
 * The rotation itself is an ordinary close: send `bye`, call `close(1000)`,
 * and let the one `onclose` handler reconnect immediately (no backoff,
 * because we did this on purpose). A REAL drop uses the same `onclose`
 * handler but backs off, because that one wasn't on purpose. One path, one
 * flag deciding which branch it takes -- and because rotation exercises it
 * every ~75s, it is the best-tested code in the app by the time of the demo.
 */

import {
  type ClientTimingMessage,
  type ClosingReason,
  type ClientMessage,
  type ConversationState,
  type ErrorMessage,
  type FactCardMessage,
  type MemoryMessage,
  type PlaceCard,
  type QuotaMessage,
  type SegmentWire,
  type TurnFailedStage,
  PROTOCOL_VERSION,
  parseServerMessage,
} from "../protocol";

export type ConnectionState = "connecting" | "ready" | "rotating" | "reconnecting" | "offline" | "stale";

export interface ReadyInfo {
  sessionId: string;
  resumed: boolean;
  connectionN: number;
}

export interface ConnectionCallbacks {
  onConnectionState(state: ConnectionState): void;
  onConversationState(state: ConversationState): void;
  onReady(info: ReadyInfo): void;
  onPong(rttMs: number): void;
  /** Human-readable, for the status line: new session, reconnected,
   * a fatal reason, a server error. Not structured -- there is exactly one
   * consumer (a line of text), so a string is the plainest thing that works. */
  onNotice(message: string): void;
  onTranscript(turnId: string, text: string): void;
  onReply(turnId: string, text: string): void;
  onAudioStart(turnId: string, sampleRate: number): void;
  /** One binary frame -- raw PCM16 samples, at the rate `onAudioStart` gave. */
  onAudioChunk(turnId: string, chunk: ArrayBuffer): void;
  onAudioEnd(turnId: string): void;
  onTurnFailed(turnId: string, stage: TurnFailedStage, message: string): void;
  /** Block A -- the gated answer, kept AND rejected segments, and the
   * exact string TTS was handed. */
  onSegments(turnId: string, segments: SegmentWire[], spoken: string, hedged: boolean): void;
  onQuota(quota: Omit<QuotaMessage, "t" | "seq" | "ts_ms">): void;
  /** D15 -- received and held; Block C renders it, nothing paints it yet. */
  onFactCard(card: FactCardMessage): void;
  /** Wikimedia place cards -- arrive after TTS has started, never on the
   * first-audio path. Failed lookups are included (ok: false). */
  onPlaces(turnId: string, places: PlaceCard[]): void;
  /** Block B -- drives the WHOLE "what Sarjy remembers" panel. Sent after
   * `ready`, and again after sign-in, sign-out, forget, or an extraction
   * that changed something -- there is no client-side memory state to
   * drift, since every change re-sends the full record. */
  onMemory(memory: MemoryMessage): void;
}

// A turn plus its answer, worst case -- ensureFresh() refuses to start one
// this close to a scheduled rotation.
const TURN_BUDGET_MS = 30_000;

const BACKOFF_SCHEDULE_MS = [250, 500, 1000, 2000, 4000];
const BACKOFF_CAP_MS = 5000;
const BACKOFF_JITTER = 0.2;
const MAX_AUTO_RETRIES = 5;

// Detection, not a keepalive -- S1 measured a 20s protocol-level ping
// failing to save a dying connection. This exists to notice a stale socket
// faster than TCP would, not to hold one open past whatever Modal decides.
const LIVENESS_PING_INTERVAL_MS = 15_000;
// 3s was too tight Riyadh→us-east: a slow pong looked like a dead socket
// and forceReconnect()'d in a loop. Detection, not a keepalive.
const LIVENESS_PONG_DEADLINE_MS = 12_000;

type ReconnectMode = "immediate" | "backoff";

export class Connection {
  private ws: WebSocket | null = null;
  private sessionId: string | null = null;
  private connectionState: ConnectionState = "connecting";
  private conversationState: ConversationState = "idle";

  private rotateAfterMs = 75_000; // overwritten by the server's `ready` on first connect
  private connectedAtMs = 0; // performance.now() at the last `ready`

  private rotationTimer: number | undefined;
  private rotatePending = false;
  private nextReconnectMode: ReconnectMode = "backoff";
  private terminal = false; // a reconnect:false closing was received -- stop entirely

  private consecutiveFailures = 0;
  private reconnectTimer: number | undefined;

  private livenessTimer: number | undefined;
  private livenessDeadlineTimer: number | undefined;
  private pendingLivenessId: string | null = null;

  private readyWaiters: Array<() => void> = [];

  // Binary frames carry no turn id (see protocol.py's module doc) -- this is
  // the one place that gap gets closed, so every other callback can assume
  // a turn id is always available.
  private currentAudioTurnId: string | null = null;

  // Only the latest connectNow() owns onclose. An older socket closing
  // after we have already opened a replacement used to schedule a second
  // reconnect -- CONNECTED → RECONNECTING → CONNECTED in a tight loop.
  private socketGen = 0;

  constructor(
    private readonly url: string,
    private readonly callbacks: ConnectionCallbacks,
  ) {}

  connect(): void {
    document.addEventListener("visibilitychange", this.handleVisibilityChange);
    this.setConnectionState("connecting");
    this.connectNow();
  }

  /** Manual recovery after the backoff loop has given up. */
  retry(): void {
    this.terminal = false;
    this.consecutiveFailures = 0;
    this.setConnectionState("connecting");
    this.connectNow();
  }

  /** The UI's Ping button. Any pong -- manual or the liveness check's own --
   * reports its round-trip time via onPong(), so this needs no bookkeeping. */
  sendPing(): void {
    this.send({ t: "ping", id: `manual-${Date.now()}`, client_ts_ms: Date.now() });
  }

  /** Block 2 awaits this before sending `start`. Rotates first if the
   * socket is too close to its scheduled rotation to plausibly finish a
   * turn -- see the module doc's invariant. */
  async ensureFresh(): Promise<void> {
    // Nothing to rotate if the socket isn't already `ready` -- reconnecting/
    // offline/stale all mean the reconnect loop already owns getting back
    // to `ready`, and there's nothing to gain by waiting on a rotate()
    // here. Without this guard, a user speaking while offline (backoff
    // exhausted, `connectedAtMs` from a "ready" long in the past) computed
    // `elapsed` as huge, called rotate() against an already-dead socket,
    // and parked handleUtterance() forever -- rotate()'s close(1000) on a
    // socket that's already CLOSED fires no `onclose`, so no reconnect was
    // ever scheduled and the waiter below never resolved. The caller
    // (App.tsx's handleUtterance) checks isReady() right after this
    // returns and surfaces a visible failure instead of sending into a
    // dead socket.
    if (this.connectionState !== "ready") return;
    const elapsed = performance.now() - this.connectedAtMs;
    if (elapsed <= this.rotateAfterMs - TURN_BUDGET_MS) return;
    await new Promise<void>((resolve) => {
      this.readyWaiters.push(resolve);
      this.rotate();
    });
  }

  /** Whether a message sent right now would actually go anywhere. Callers
   * that are about to start a turn check this after ensureFresh() --
   * Connection.send/sendBinary silently no-op on a closed socket, and an
   * utterance sent into that silence would vanish with nothing on screen
   * (Invariant 7: degrade visibly, never hang). */
  isReady(): boolean {
    return this.connectionState === "ready";
  }

  startTurn(turnId: string, lang: "en" | "ar" = "en"): void {
    this.send({ t: "start", turn_id: turnId, client_ts_ms: Date.now(), lang });
  }

  /** Raw PCM16 samples, one binary frame. */
  sendBinary(data: ArrayBuffer): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    }
  }

  endTurn(turnId: string, samples: number): void {
    this.send({ t: "end", turn_id: turnId, samples, client_ts_ms: Date.now() });
  }

  bargeTurn(turnId: string): void {
    this.send({ t: "barge", turn_id: turnId });
  }

  /** The client's own half of a turn's latency record -- the server can't
   * see endpointing or first-audio-out, so this is how those two legs cross
   * the wire. App.tsx's reportTurnTiming() enforces exactly one call per
   * turn; this method just puts it on the wire like everything else. */
  sendClientTiming(m: Omit<ClientTimingMessage, "t">): void {
    this.send({ t: "client_timing", ...m });
  }

  /** The typed sign-in form -- D3's reliable path (voice sign-in, D8, is a
   * server-side sub-flow with no dedicated wire message of its own). */
  signIn(name: string, pin: string): void {
    this.send({ t: "sign_in", name, pin });
  }

  signOut(): void {
    this.send({ t: "sign_out" });
  }

  /** `key: null` forgets every fact but keeps the signed-in identity --
   * the panel's "Forget everything" button. */
  forget(key: string | null): void {
    this.send({ t: "forget", key });
  }

  dispose(): void {
    document.removeEventListener("visibilitychange", this.handleVisibilityChange);
    window.clearTimeout(this.rotationTimer);
    window.clearTimeout(this.reconnectTimer);
    this.stopLiveness();
    this.terminal = true;
    this.socketGen += 1;
    this.dropSocket();
  }

  // -- connecting -----------------------------------------------------------

  private connectNow(): void {
    this.dropSocket();
    const gen = ++this.socketGen;
    const ws = new WebSocket(this.url);
    // Server audio is raw PCM16 binary frames -- without this, a binary
    // message arrives as a Blob, which needs an async read before its bytes
    // are usable and would delay scheduling every single audio chunk.
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onopen = () => {
      if (gen !== this.socketGen) return;
      this.send({ t: "hello", v: PROTOCOL_VERSION, session_id: this.sessionId, client_ts_ms: Date.now() });
    };
    ws.onmessage = (ev: MessageEvent<unknown>) => {
      if (gen !== this.socketGen) return;
      if (typeof ev.data === "string") {
        this.handleMessage(ev.data);
      } else if (ev.data instanceof ArrayBuffer) {
        if (this.currentAudioTurnId !== null) {
          this.callbacks.onAudioChunk(this.currentAudioTurnId, ev.data);
        }
        // Else: a chunk for a turn we've already moved past (a barge raced
        // ahead of in-flight frames) -- dropped, not an error.
      }
    };
    ws.onclose = () => {
      if (gen !== this.socketGen) return;
      this.handleClose();
    };
    ws.onerror = () => {
      // onclose always follows for a browser WebSocket; nothing to act on
      // here beyond visibility during development.
      if (gen !== this.socketGen) return;
      console.warn("sarjy: websocket error");
    };
  }

  /** Detach handlers so a replaced socket's `onclose` cannot start a second
   * reconnect. Close is best-effort; Modal reaps the input slot either way. */
  private dropSocket(): void {
    const ws = this.ws;
    this.ws = null;
    if (!ws) return;
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      try {
        ws.close(1000);
      } catch {
        /* already closing */
      }
    }
  }

  private send(msg: ClientMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private setConnectionState(state: ConnectionState): void {
    this.connectionState = state;
    this.callbacks.onConnectionState(state);
  }

  // -- incoming messages ------------------------------------------------------

  private handleMessage(raw: string): void {
    const msg = parseServerMessage(raw);
    if (!msg) return; // unknown/malformed -- parseServerMessage already logged it

    switch (msg.t) {
      case "ready": {
        this.sessionId = msg.session_id;
        this.rotateAfterMs = msg.rotate_after_ms;
        // msg.hard_max_ms is the server's own backstop (it closes the
        // connection unprompted past that point -- handleClosing() reacts
        // to that when it happens). Nothing client-side needs to track it
        // independently.
        this.connectedAtMs = performance.now();
        this.consecutiveFailures = 0;
        this.terminal = false;
        this.setConnectionState("ready");
        this.callbacks.onReady({
          sessionId: msg.session_id,
          resumed: msg.resumed,
          connectionN: msg.connection_n,
        });
        this.scheduleRotationTimer();
        this.startLiveness();
        this.drainReadyWaiters();
        break;
      }
      case "state":
        this.conversationState = msg.value;
        this.callbacks.onConversationState(msg.value);
        if (msg.value === "idle" && this.rotatePending) {
          this.rotatePending = false;
          this.rotate();
        }
        break;
      case "pong":
        this.pendingLivenessId = null;
        this.callbacks.onPong(Date.now() - msg.client_ts_ms);
        break;
      case "error":
        this.handleError(msg);
        break;
      case "closing":
        this.handleClosing(msg.reason, msg.reconnect);
        break;
      case "transcript":
        this.callbacks.onTranscript(msg.turn_id, msg.text);
        break;
      case "reply":
        this.callbacks.onReply(msg.turn_id, msg.text);
        break;
      case "audio_start":
        this.currentAudioTurnId = msg.turn_id;
        this.callbacks.onAudioStart(msg.turn_id, msg.sample_rate);
        break;
      case "audio_end":
        this.currentAudioTurnId = null;
        this.callbacks.onAudioEnd(msg.turn_id);
        break;
      case "turn_failed":
        this.currentAudioTurnId = null;
        this.callbacks.onTurnFailed(msg.turn_id, msg.stage, msg.message);
        break;
      case "segments":
        this.callbacks.onSegments(msg.turn_id, msg.segments, msg.spoken, msg.hedged);
        break;
      case "quota":
        this.callbacks.onQuota({
          total: msg.total,
          spent: msg.spent,
          reserve: msg.reserve,
          remaining: msg.remaining,
        });
        break;
      case "fact_card":
        this.callbacks.onFactCard(msg);
        break;
      case "places":
        this.callbacks.onPlaces(msg.turn_id, msg.places);
        break;
      case "memory":
        this.callbacks.onMemory(msg);
        break;
    }
  }

  private handleError(msg: ErrorMessage): void {
    console.warn(`sarjy: server error ${msg.code}: ${msg.message}`);
    this.callbacks.onNotice(msg.message);
  }

  private handleClosing(reason: ClosingReason, reconnect: boolean): void {
    if (!reconnect) {
      this.terminal = true;
      this.callbacks.onNotice(this.describeClosing(reason));
      return;
    }
    // The server-driven rotate_ceiling case: we didn't call rotate()
    // ourselves, so nothing has set "immediate" yet. Do it here.
    this.nextReconnectMode = "immediate";
  }

  private describeClosing(reason: ClosingReason): string {
    switch (reason) {
      case "protocol_version":
        return "A new version is available — reload.";
      case "superseded":
        return "This session is connected in another tab.";
      case "shutdown":
        return "Disconnected by the server.";
      default:
        return "Disconnected.";
    }
  }

  // -- rotation (proactive, planned) ------------------------------------------

  private scheduleRotationTimer(): void {
    window.clearTimeout(this.rotationTimer);
    this.rotationTimer = window.setTimeout(() => {
      if (this.conversationState === "idle") {
        this.rotate();
      } else {
        this.rotatePending = true; // fires from the "state" handler's idle branch instead
      }
    }, this.rotateAfterMs);
  }

  private rotate(): void {
    if (this.connectionState === "rotating" || this.connectionState === "connecting") return;
    this.nextReconnectMode = "immediate";

    // Defence in depth for ensureFresh()'s guard above: if this is ever
    // reached against a socket that's already CLOSED (or was never opened),
    // close(1000) here fires no `onclose` -- a closed socket can't close
    // again -- so nothing would ever schedule a reconnect and any
    // readyWaiters would be stranded. Route straight into the same
    // recovery path an unplanned drop takes instead of "rotating" a socket
    // that's already dead (which also hides the manual Retry button, gated
    // on connectionState === "offline").
    if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
      this.handleClose();
      return;
    }

    this.setConnectionState("rotating");
    this.send({ t: "bye", reason: "rotate" });
    this.ws.close(1000);
  }

  private drainReadyWaiters(): void {
    const waiters = this.readyWaiters;
    this.readyWaiters = [];
    waiters.forEach((resolve) => resolve());
  }

  // -- reconnection (reactive, unplanned) --------------------------------------

  private handleClose(): void {
    window.clearTimeout(this.rotationTimer);
    this.stopLiveness();

    if (this.terminal) return; // protocol_version / superseded / shutdown: stop here

    const mode = this.nextReconnectMode;
    this.nextReconnectMode = "backoff";

    if (mode === "immediate") {
      this.setConnectionState("connecting");
      this.connectNow();
      return;
    }

    this.consecutiveFailures += 1;
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.consecutiveFailures > MAX_AUTO_RETRIES) {
      this.setConnectionState("offline");
      this.callbacks.onNotice("Connection lost. Click Retry to reconnect.");
      return;
    }
    const base = BACKOFF_SCHEDULE_MS[this.consecutiveFailures - 1] ?? BACKOFF_CAP_MS;
    const jitter = base * BACKOFF_JITTER * (Math.random() * 2 - 1);
    const delay = Math.max(0, Math.min(base, BACKOFF_CAP_MS) + jitter);
    this.setConnectionState("reconnecting");
    this.reconnectTimer = window.setTimeout(() => this.connectNow(), delay);
  }

  /** Used by both the liveness check and the visibility check: something is
   * suspicious about this socket, so stop waiting politely and force it. */
  private forceReconnect(): void {
    this.nextReconnectMode = "immediate";
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.send({ t: "bye", reason: "leave" });
      this.ws.close(1000);
      return;
    }
    // CONNECTING / already CLOSED: do not open a second socket on top of
    // one that will also fire onclose. One connectNow owns recovery.
    if (this.ws && this.ws.readyState === WebSocket.CONNECTING) return;
    this.connectNow();
  }

  // -- liveness ping (detection, not a keepalive) ------------------------------

  private startLiveness(): void {
    this.stopLiveness();
    this.livenessTimer = window.setInterval(() => this.pingForLiveness(), LIVENESS_PING_INTERVAL_MS);
  }

  private stopLiveness(): void {
    window.clearInterval(this.livenessTimer);
    window.clearTimeout(this.livenessDeadlineTimer);
    this.pendingLivenessId = null;
  }

  private pingForLiveness(): void {
    const id = `lp-${Date.now()}`;
    this.pendingLivenessId = id;
    this.send({ t: "ping", id, client_ts_ms: Date.now() });
    window.clearTimeout(this.livenessDeadlineTimer);
    this.livenessDeadlineTimer = window.setTimeout(() => {
      if (this.pendingLivenessId === id) {
        this.setConnectionState("stale");
        this.forceReconnect();
      }
    }, LIVENESS_PONG_DEADLINE_MS);
  }

  // -- backgrounded tabs --------------------------------------------------------

  private handleVisibilityChange = (): void => {
    if (document.visibilityState !== "visible") return;
    // Chrome throttles background timers to >=1min, which can silently push
    // a scheduled rotation past the point Modal has already killed the
    // socket. Coming back into view, check directly rather than trust the
    // timer fired on schedule.
    const elapsed = performance.now() - this.connectedAtMs;
    if (elapsed > this.rotateAfterMs) {
      this.rotate();
    } else {
      this.pingForLiveness();
    }
  };
}
