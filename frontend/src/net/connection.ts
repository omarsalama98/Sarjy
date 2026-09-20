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
  type ClientMessage,
  type ClosingReason,
  type ConversationState,
  type ErrorMessage,
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
const LIVENESS_PONG_DEADLINE_MS = 3_000;

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
    const elapsed = performance.now() - this.connectedAtMs;
    if (elapsed <= this.rotateAfterMs - TURN_BUDGET_MS) return;
    await new Promise<void>((resolve) => {
      this.readyWaiters.push(resolve);
      this.rotate();
    });
  }

  dispose(): void {
    document.removeEventListener("visibilitychange", this.handleVisibilityChange);
    window.clearTimeout(this.rotationTimer);
    window.clearTimeout(this.reconnectTimer);
    this.stopLiveness();
    this.terminal = true;
    this.ws?.close(1000);
  }

  // -- connecting -----------------------------------------------------------

  private connectNow(): void {
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => {
      this.send({ t: "hello", v: PROTOCOL_VERSION, session_id: this.sessionId, client_ts_ms: Date.now() });
    };
    ws.onmessage = (ev: MessageEvent<unknown>) => {
      if (typeof ev.data === "string") this.handleMessage(ev.data);
    };
    ws.onclose = () => this.handleClose();
    ws.onerror = () => {
      // onclose always follows for a browser WebSocket; nothing to act on
      // here beyond visibility during development.
      console.warn("sarjy: websocket error");
    };
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
        this.callbacks.onNotice(
          msg.resumed ? `Reconnected (connection #${msg.connection_n}).` : "New session started.",
        );
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
        if (msg.id === this.pendingLivenessId) this.pendingLivenessId = null;
        this.callbacks.onPong(Date.now() - msg.client_ts_ms);
        break;
      case "error":
        this.handleError(msg);
        break;
      case "closing":
        this.handleClosing(msg.reason, msg.reconnect);
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
    this.setConnectionState("rotating");
    this.send({ t: "bye", reason: "rotate" });
    this.ws?.close(1000);
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
    } else {
      this.connectNow();
    }
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
