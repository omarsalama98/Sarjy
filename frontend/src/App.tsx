/**
 * Sarjy. One screen.
 *
 * Two state machines, deliberately separate (docs/plans/blocks/01-skeleton-deploy.md):
 * connection state (client-owned: connecting/ready/rotating/reconnecting/
 * offline/stale) and conversation state (idle/listening/thinking/speaking).
 * Conflating them is the classic mistake -- a reconnect would then look
 * like the assistant started thinking.
 *
 * Conversation state has two owners, split by who can act first
 * (docs/plans/blocks/02-voice-loop.md, "Who owns which conversation
 * state"): `listening` and `speaking` are set HERE, directly, the instant
 * the VAD or the playback queue notices them -- no round trip. `thinking`
 * and `idle` arrive from the server's own `state` message. Both write to
 * the same `conversationState` value; there is no race between them
 * because the two sides never claim the same value at the same phase of a
 * turn.
 *
 * A third, separate concept -- `voiceIssue` -- covers everything that
 * isn't a normal conversation state at all: the VAD's assets failed to
 * load, the microphone was denied, or none exists. These get their own
 * named UI instead of being squeezed into `idle`, because "idle" and
 * "broken" need to look different on screen (Invariant 7: degrade
 * visibly, never hang).
 */

import type { FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { clearSharedMicStream, getSharedMicStream, TARGET_SAMPLE_RATE } from "./audio/capture";
import { PlaybackQueue } from "./audio/playback";
import { createTurnDetector, type EndpointTiming, type TurnDetector } from "./audio/turn";
import type { ConnectionCallbacks, ConnectionState } from "./net/connection";
import { Connection } from "./net/connection";
import type { ConversationState, FactCardMessage, MemoryMessage, SegmentWire } from "./protocol";
import { FactCard } from "./ui/FactCard";

const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws`;

const PLAYBACK_SAMPLE_RATE = 24_000; // Deepgram's native output rate -- no resampling on this hot path.

// The protocol comment's own limit ("≤32 KiB each") -- an arbitrary but
// generous frame size; the whole point is many small sends, not one giant one.
const MAX_BINARY_CHUNK_BYTES = 32 * 1024;

// Barge-in guard #2 (the block plan's "Barge-in" section): echo cancellation
// is unproven until a human runs task 10/13 on real speakers, so the first
// moment of Sarjy's own audio is never treated as the user interrupting.
const BARGE_IGNORE_WINDOW_MS = 300;

type VoiceIssueKind = "unavailable" | "mic-blocked" | "mic-missing";

interface VoiceIssue {
  kind: VoiceIssueKind;
  message: string;
}

/** F6: if the browser won't honour a 16 kHz AudioContext, fall back to the
 * device's own rate -- vad-web's resampler handles anything >= 16 kHz; it
 * only errors below that. */
function createCaptureContext(): AudioContext {
  try {
    const ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
    if (ctx.sampleRate !== TARGET_SAMPLE_RATE) {
      console.warn(
        `sarjy: capture context runs at ${ctx.sampleRate}Hz, not the requested ${TARGET_SAMPLE_RATE}Hz -- vad-web's resampler handles this`,
      );
    }
    return ctx;
  } catch (err) {
    console.warn("sarjy: 16kHz AudioContext was refused, falling back to the device rate", err);
    return new AudioContext();
  }
}

function classifyVoiceError(err: unknown): VoiceIssue {
  if (err instanceof Error && err.name === "NotAllowedError") {
    return {
      kind: "mic-blocked",
      message: "Sarjy needs the microphone to hear you. Allow it in the address bar, then press Retry.",
    };
  }
  if (err instanceof Error && err.name === "NotFoundError") {
    return { kind: "mic-missing", message: "No microphone was found on this device." };
  }
  // Covers F1/F2: assertVadAssets() and MicVAD.new() both throw plain
  // Errors with an already-legible message naming the exact URL/status.
  return { kind: "unavailable", message: err instanceof Error ? err.message : String(err) };
}

/** 🪤 lib.dom.d.ts types AudioContext.outputLatency as a plain `number`,
 * but Safari doesn't implement the property and returns `undefined` at
 * runtime -- the guard below looks redundant to the type checker (it
 * thinks outputLatency is always a number) but is load-bearing at runtime.
 * Number.isFinite() rejects undefined and NaN alike, so both a
 * non-implementing browser and a not-yet-ready context resolve to null
 * rather than a bogus timestamp. */
function getOutputLatencyMs(ctx: AudioContext | null): number | null {
  if (!ctx || !Number.isFinite(ctx.outputLatency)) return null;
  return Math.round(ctx.outputLatency * 1000);
}

/** Two decimals in seconds ("1.83 s"), or an em dash when the leg never
 * completed (a turn that failed before audio, or a client that never
 * reported). Diagnostic text, not conversational -- see the rendered
 * line's aria-live="off" below. */
function fmt(ms: number | null): string {
  return ms === null ? "—" : `${(ms / 1000).toFixed(2)} s`;
}

export function App() {
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [conversationState, setConversationState] = useState<ConversationState>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [connectionN, setConnectionN] = useState(0);
  const [notice, setNotice] = useState("");
  const [lastRttMs, setLastRttMs] = useState<number | null>(null);

  const [started, setStarted] = useState(false);
  const [starting, setStarting] = useState(false);
  // W4: the VAD (and its ~16MB of ONNX + WASM) is built at page load, not
  // on the Start click -- this flips once that finishes (success OR
  // failure; failure shows through voiceIssue instead). Gates the Start
  // button so a click during the download can't race a detector that
  // doesn't exist yet.
  const [assetsReady, setAssetsReady] = useState(false);
  const [voiceIssue, setVoiceIssue] = useState<VoiceIssue | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [reply, setReply] = useState<string | null>(null);
  const [turnFailedMessage, setTurnFailedMessage] = useState<string | null>(null);
  const [interrupted, setInterrupted] = useState(false);
  // Block A -- the gate, on screen. `segments` carries BOTH kept and
  // rejected entries; a rejected one renders struck through with its
  // reason -- that visibility is the whole demo (F3 in the block plan).
  const [segments, setSegments] = useState<SegmentWire[]>([]);
  const [hedged, setHedged] = useState(false);
  const [quota, setQuota] = useState<{
    total: number;
    spent: number;
    reserve: number;
    remaining: number;
  } | null>(null);
  // Block C -- the deep dive's only visible output. Cleared on every new
  // turn (F-FC4, below) so a card describing one destination can never sit
  // under an answer about another.
  const [factCard, setFactCard] = useState<FactCardMessage | null>(null);
  // Block B -- the WHOLE "what Sarjy remembers" panel is driven by the last
  // `memory` message (D5): there is no separate client-side memory state to
  // drift, since sign-in/sign-out/forget/extraction all re-send the full
  // record rather than a diff.
  const [memory, setMemory] = useState<MemoryMessage | null>(null);
  const [signInName, setSignInName] = useState("");
  const [signInPin, setSignInPin] = useState("");
  // The one line of UI Block 3 adds -- last turn's voice-to-voice number,
  // its endpoint delay, and the redemption setting that produced it. null
  // until the first turn completes or fails.
  const [lastTurn, setLastTurn] = useState<{
    firstAudioMs: number | null;
    endpointMs: number;
    redemptionMs: number;
  } | null>(null);

  const connectionRef = useRef<Connection | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playbackQueueRef = useRef<PlaybackQueue | null>(null);
  const detectorRef = useRef<TurnDetector | null>(null);
  const currentTurnIdRef = useRef<string | null>(null);
  const currentSampleRateRef = useRef(PLAYBACK_SAMPLE_RATE);
  const speakingStartedAtRef = useRef(0);
  const turnCounterRef = useRef(0);
  // True from the moment `start` is sent until audio_end/turn_failed/barge
  // closes the turn out -- the window in which a connection drop must be
  // treated as F13 ("Connection dropped mid-answer"), not a normal idle
  // reconnect that the UI has nothing to say about.
  const turnInFlightRef = useRef(false);
  // The client's half of the current turn's timing record. Set in
  // handleUtterance once the turn id is minted; read back in
  // reportTurnTiming, which enforces exactly one send per turn via `sent`.
  const turnTimingRef = useRef<{
    turnId: string;
    acousticEndAtMs: number;
    endpointMs: number;
    redemptionMs: number;
    sent: boolean;
  } | null>(null);

  /** Sends this turn's client_timing exactly once -- a second call for the
   * same turn (e.g. onAudioStart firing, then a later turn_failed racing
   * in) is a no-op because `sent` is already true. Called with
   * firstAudioMs=null from onTurnFailed, where the headline leg never
   * completed. */
  const reportTurnTiming = useCallback((turnId: string, firstAudioMs: number | null): void => {
    const ref = turnTimingRef.current;
    if (!ref || ref.turnId !== turnId || ref.sent) return;
    ref.sent = true;

    connectionRef.current?.sendClientTiming({
      turn_id: turnId,
      endpoint_ms: ref.endpointMs,
      first_audio_ms: firstAudioMs,
      redemption_ms: ref.redemptionMs,
      output_latency_ms: getOutputLatencyMs(playbackCtxRef.current),
    });
    setLastTurn({ firstAudioMs, endpointMs: ref.endpointMs, redemptionMs: ref.redemptionMs });
  }, []);

  const handleUtterance = useCallback(async (pcm: ArrayBuffer, endpoint: EndpointTiming): Promise<void> => {
    const connection = connectionRef.current;
    if (!connection) return;

    // "A turn never spans a connection" (Block 1) -- this is the one call
    // that makes it true by construction: a rotation can only happen while
    // idle or while the user is speaking, never between `start` and `end`.
    await connection.ensureFresh();

    if (!connection.isReady()) {
      // The socket is down and there was nothing for ensureFresh() to wait
      // on. Without this check, startTurn()/sendBinary()/endTurn() below
      // would all silently no-op (Connection.send on a non-OPEN socket) and
      // the utterance would vanish with nothing on screen -- exactly the
      // "speaking while the socket is down loses the turn silently" gap
      // Invariant 7 forbids.
      setConversationState("idle");
      setTurnFailedMessage("Connection is down — wait for it to reconnect, then try again.");
      return;
    }

    turnCounterRef.current += 1;
    const turnId = `t-${turnCounterRef.current}`;
    setTranscript(null);
    setReply(null);
    setTurnFailedMessage(null);
    setInterrupted(false);
    setSegments([]);
    setHedged(false);
    setFactCard(null);

    // Set after the turn id is minted, not before ensureFresh() -- but
    // endpoint.acousticEndAtMs is a performance.now() reading turn.ts
    // captured synchronously back in onSpeechEnd, BEFORE this async
    // function was even called, so awaiting ensureFresh() above cannot
    // have corrupted it.
    turnTimingRef.current = {
      turnId,
      acousticEndAtMs: endpoint.acousticEndAtMs,
      endpointMs: endpoint.endpointMs,
      redemptionMs: endpoint.redemptionMs,
      sent: false,
    };

    turnInFlightRef.current = true;
    connection.startTurn(turnId);
    const bytes = new Uint8Array(pcm);
    for (let offset = 0; offset < bytes.length; offset += MAX_BINARY_CHUNK_BYTES) {
      const end = Math.min(offset + MAX_BINARY_CHUNK_BYTES, bytes.length);
      connection.sendBinary(bytes.slice(offset, end).buffer);
    }
    connection.endTurn(turnId, bytes.length / 2);
  }, []);

  const handleBarge = useCallback((): void => {
    const turnId = currentTurnIdRef.current;
    if (!turnId) return;
    if (performance.now() - speakingStartedAtRef.current < BARGE_IGNORE_WINDOW_MS) return;

    turnInFlightRef.current = false;
    playbackQueueRef.current?.stop();
    detectorRef.current?.setSpeaking(false);
    currentTurnIdRef.current = null;
    setInterrupted(true);
    // Belt-and-braces: onSpeechStart already set this the moment speech
    // began (onSpeechRealStart, which triggers a barge, fires strictly
    // after it) -- but the turn must never be left LOOKING like it's still
    // "speaking" if something raced.
    setConversationState("listening");
    connectionRef.current?.bargeTurn(turnId);
  }, []);

  /** F13: the socket dropping while a turn is in flight is not an ordinary
   * reconnect the UI can stay quiet about -- the turn it was carrying is
   * gone and cannot be resumed (Block 1's invariant: a turn never spans a
   * connection). "rotating" is excluded on purpose: that only ever happens
   * while idle (Connection defers a scheduled rotation until the
   * conversation state goes idle), so it never carries a live turn. */
  const handleConnectionState = useCallback((state: ConnectionState): void => {
    setConnectionState(state);
    const dropped = state === "reconnecting" || state === "offline" || state === "stale";
    if (!dropped || !turnInFlightRef.current) return;

    turnInFlightRef.current = false;
    currentTurnIdRef.current = null;
    playbackQueueRef.current?.stop();
    detectorRef.current?.setSpeaking(false);
    setConversationState("idle");
    setNotice("Connection dropped mid-answer — ask again.");
  }, []);

  /** The typed sign-in form -- D3's reliable path. The PIN field is cleared
   * immediately after sending, win or lose: it is never held in state any
   * longer than it takes to put it on the wire once (never logged, never
   * re-rendered back into the input). */
  const handleSignIn = useCallback(
    (e: FormEvent): void => {
      e.preventDefault();
      connectionRef.current?.signIn(signInName, signInPin);
      setSignInPin("");
    },
    [signInName, signInPin],
  );

  const handleSignOut = useCallback((): void => {
    connectionRef.current?.signOut();
  }, []);

  const handleForgetEverything = useCallback((): void => {
    connectionRef.current?.forget(null);
  }, []);

  const handleMicRevoked = useCallback((): void => {
    void detectorRef.current?.destroy();
    detectorRef.current = null;
    clearSharedMicStream();
    setStarted(false);
    setVoiceIssue({
      kind: "mic-blocked",
      message: "Sarjy needs the microphone to hear you. Allow it in the address bar, then press Retry.",
    });
  }, []);

  /** F5: permission revoked mid-session. Two independent signals, because
   * neither is reliable alone -- Safari has no "microphone" permission
   * descriptor for `permissions.query`, so the track's own "ended" event is
   * what catches it there. */
  const watchForMicRevocation = useCallback((): void => {
    void getSharedMicStream().then((stream) => {
      stream.getAudioTracks()[0]?.addEventListener("ended", handleMicRevoked, { once: true });
    });
    if (navigator.permissions?.query) {
      navigator.permissions
        .query({ name: "microphone" as PermissionName })
        .then((status) => {
          status.onchange = () => {
            if (status.state !== "granted") handleMicRevoked();
          };
        })
        .catch(() => {
          /* Safari: no "microphone" descriptor -- the "ended" listener above covers it. */
        });
    }
  }, [handleMicRevoked]);

  /** Constructs a VAD instance -- downloads its assets, touches no
   * microphone (turn.ts's createTurnDetector doc comment). Called at page
   * load (the mount effect below) and again from handleStart only in F5's
   * Retry path, where handleMicRevoked already destroyed the previous one. */
  const buildDetector = useCallback(async (): Promise<TurnDetector> => {
    const capture = captureCtxRef.current;
    if (!capture) throw new Error("Voice detection has nothing to attach to yet.");
    return createTurnDetector(capture, {
      onSpeechStart: () => setConversationState("listening"),
      onUtterance: (pcm, _sampleRate, _durationMs, endpoint) => void handleUtterance(pcm, endpoint),
      onMisfire: () => {
        /* Backchannel ("mhm") -- deliberately no state change, no turn opened. */
      },
      onBargeDetected: handleBarge,
    });
  }, [handleUtterance, handleBarge]);

  const handleStart = useCallback(async (): Promise<void> => {
    const capture = captureCtxRef.current;
    const playback = playbackCtxRef.current;
    if (!capture || !playback || starting) return;

    setStarting(true);
    setVoiceIssue(null);
    try {
      // Web Audio requires resuming inside a user gesture -- this click
      // handler IS that gesture (task 10's trap: both contexts are
      // constructed suspended, at page load, and resumed only here).
      await capture.resume();
      await playback.resume();

      // The normal path already has a detector, built at page load (W4).
      // F5's Retry path is the exception: handleMicRevoked() destroyed it,
      // so it's rebuilt here -- the browser has the assets cached, so this
      // resolves fast rather than re-downloading 16MB on every retry.
      if (!detectorRef.current) {
        detectorRef.current = await buildDetector();
      }
      // The ONE getUserMedia call in this click -- NotAllowedError (F3) and
      // NotFoundError (F4) surface here, inside the user gesture.
      await detectorRef.current.start();
      watchForMicRevocation();
      setStarted(true);
    } catch (err) {
      setVoiceIssue(classifyVoiceError(err));
    } finally {
      setStarting(false);
    }
  }, [starting, buildDetector, watchForMicRevocation]);

  useEffect(() => {
    const capture = createCaptureContext();
    const playback = new AudioContext({ sampleRate: PLAYBACK_SAMPLE_RATE });
    captureCtxRef.current = capture;
    playbackCtxRef.current = playback;
    playbackQueueRef.current = new PlaybackQueue(playback);

    // W4: build the VAD now, while the reviewer is still reading the
    // screen, instead of behind a "Starting…" spinner after the click.
    // buildDetector() never calls getUserMedia (turn.ts's createTurnDetector
    // doc comment) -- only detector.start(), called from handleStart, does.
    let cancelled = false;
    buildDetector()
      .then((detector) => {
        if (cancelled) {
          void detector.destroy();
          return;
        }
        detectorRef.current = detector;
        setAssetsReady(true);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setVoiceIssue(classifyVoiceError(err));
      });

    const callbacks: ConnectionCallbacks = {
      onConnectionState: handleConnectionState,
      onConversationState: setConversationState,
      onReady: (info) => {
        setSessionId(info.sessionId);
        setConnectionN(info.connectionN);
      },
      onPong: setLastRttMs,
      onNotice: setNotice,
      onTranscript: (_turnId, text) => setTranscript(text),
      onReply: (_turnId, text) => setReply(text),
      onSegments: (_turnId, segs, _spoken, isHedged) => {
        setSegments(segs);
        setHedged(isHedged);
      },
      onQuota: (q) => setQuota(q),
      onMemory: (m) => setMemory(m),
      onFactCard: (card) => {
        setFactCard(card);
        // Verification turn 8: the browser console is where this is
        // checked -- Block C renders it, nothing paints it yet.
        console.log("sarjy: fact_card", card);
      },
      onAudioStart: (turnId, sampleRate) => {
        currentTurnIdRef.current = turnId;
        currentSampleRateRef.current = sampleRate;
        playbackQueueRef.current?.beginTurn(() => {
          speakingStartedAtRef.current = performance.now();
          detectorRef.current?.setSpeaking(true);
          setConversationState("speaking");
          // The headline leg closes HERE, not at audio_start -- this is the
          // first buffer actually scheduled, the moment PlaybackQueue's own
          // doc comment calls "when the UI flips to speaking."
          const ref = turnTimingRef.current;
          const firstAudioMs = ref ? Math.round(performance.now() - ref.acousticEndAtMs) : null;
          reportTurnTiming(turnId, firstAudioMs);
        });
      },
      onAudioChunk: (turnId, chunk) => {
        if (turnId !== currentTurnIdRef.current) return; // a barge raced ahead of in-flight frames
        playbackQueueRef.current?.enqueue(chunk, currentSampleRateRef.current);
      },
      onAudioEnd: (turnId) => {
        if (turnId !== currentTurnIdRef.current) return;
        turnInFlightRef.current = false;
        currentTurnIdRef.current = null;
        detectorRef.current?.setSpeaking(false);
      },
      onTurnFailed: (turnId, stage, message) => {
        turnInFlightRef.current = false;
        if (turnId === currentTurnIdRef.current) {
          currentTurnIdRef.current = null;
          detectorRef.current?.setSpeaking(false);
        }
        setTurnFailedMessage(`(${stage}) ${message}`);
        // The headline leg never completed -- reported as null, not
        // skipped, so this turn still produces a record (I2).
        reportTurnTiming(turnId, null);
      },
    };
    const conn = new Connection(WS_URL, callbacks);
    connectionRef.current = conn;
    conn.connect();

    return () => {
      cancelled = true;
      conn.dispose();
      void detectorRef.current?.destroy();
      void capture.close();
      void playback.close();
    };
  }, [buildDetector, handleConnectionState, reportTurnTiming]);

  const canStart = assetsReady && !started && !voiceIssue;
  const showRetry = voiceIssue?.kind === "mic-blocked" || voiceIssue?.kind === "mic-missing";

  return (
    <main>
      <h1>Sarjy</h1>

      <p className={`conversation-state state-${voiceIssue ? voiceIssue.kind : conversationState}`} aria-live="polite">
        {voiceIssue ? voiceIssue.kind : conversationState}
        {interrupted && " (interrupted)"}
      </p>

      {voiceIssue && <p className="notice voice-issue">{voiceIssue.message}</p>}

      {!assetsReady && !voiceIssue && <button disabled>Loading voice detection…</button>}
      {canStart && (
        <button onClick={() => void handleStart()} disabled={starting}>
          {starting ? "Starting…" : "Start talking"}
        </button>
      )}
      {showRetry && <button onClick={() => void handleStart()}>Retry</button>}
      {voiceIssue?.kind === "unavailable" && (
        <button disabled title={voiceIssue.message}>
          Start talking
        </button>
      )}

      {started && !voiceIssue && (
        <p className="hint" aria-live="polite">
          {conversationState === "idle" && "Listening for you…"}
          {conversationState === "listening" && "Hearing you…"}
          {conversationState === "thinking" && "Thinking…"}
          {conversationState === "speaking" && "Speaking…"}
        </p>
      )}

      {transcript && (
        <p className="transcript">
          <strong>You:</strong> {transcript}
        </p>
      )}
      {reply && (
        <p className="reply">
          <strong>Sarjy:</strong> {reply}
        </p>
      )}
      {turnFailedMessage && <p className="notice turn-failed">{turnFailedMessage}</p>}

      {/* The card is the evidence; the segments below are the audit trail
          of the sentence built from it -- card first (task 7, block plan). */}
      {factCard && <FactCard card={factCard} />}

      {segments.length > 0 && (
        // F3 (block plan): a rejected segment is still SENT and shown
        // struck through with its reason -- that visibility is the demo,
        // not a debug affordance. A <ul> with a badge is the whole
        // allowance here (Block C owns real styling).
        <ul className="segments" aria-live="off">
          {segments.map((s, i) => (
            <li key={i} className={`segment segment-${s.kind}${s.ok ? "" : " segment-rejected"}`}>
              <span className="segment-kind">[{s.kind}]</span>{" "}
              <span style={s.ok ? undefined : { textDecoration: "line-through" }}>
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
      )}
      {hedged && (
        <p className="notice">
          A tool result came back but nothing was sourced or quoted from it — flagged for review.
        </p>
      )}

      {lastTurn && (
        // aria-live="off" is deliberate: a screen reader announcing a
        // latency figure after every turn is noise -- this is diagnostic,
        // not conversational (Invariant 2 wants it visible, not narrated).
        <p className="metrics" aria-live="off">
          last turn {fmt(lastTurn.firstAudioMs)} voice-to-voice · endpoint {fmt(lastTurn.endpointMs)}
          {" · redemption "}
          {lastTurn.redemptionMs} ms
        </p>
      )}

      <div className="status-line" aria-live="polite">
        <span>connection: {connectionState}</span>
        {sessionId && <span> · session {sessionId.slice(0, 8)}</span>}
        {connectionN > 0 && <span> · #{connectionN}</span>}
        {lastRttMs !== null && <span> · {lastRttMs}ms</span>}
        {quota && (
          <span> · visa quota: {quota.remaining} left above reserve (spent {quota.spent}/{quota.total})</span>
        )}
      </div>

      {notice && <p className="notice">{notice}</p>}

      <button onClick={() => connectionRef.current?.sendPing()}>Ping</button>
      {connectionState === "offline" && (
        <button onClick={() => connectionRef.current?.retry()}>Retry connection</button>
      )}

      {/* Block B -- D5: the whole panel is driven by ONE `memory` message,
          re-sent in full after every sign-in/sign-out/forget/extraction.
          No per-fact delete here (D9's cut ladder item 3) -- Forget
          everything is the correction path. */}
      <aside className="memory-panel" aria-live="polite">
        <h2>What Sarjy remembers</h2>
        {memory && (
          <>
            <p className="memory-tier">
              {memory.tier === "signed_in"
                ? `Signed in as ${memory.name}`
                : "Remembered for this session only — sign in to keep these"}
            </p>
            {memory.message && <p className="notice memory-message">{memory.message}</p>}

            {memory.facts.length > 0 ? (
              <ul className="memory-facts">
                {memory.facts.map((f) => (
                  <li key={f.key}>
                    <strong>{f.label}</strong> — {f.value}
                    <span className="memory-fact-meta">
                      {" "}
                      · learned {new Date(f.learned_at).toLocaleTimeString()}
                      {f.quote && <> · you said: "{f.quote}"</>}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hint">Nothing remembered yet.</p>
            )}

            <p className="memory-capacity">
              {memory.used} / {memory.capacity}
            </p>

            {memory.tier === "signed_in" ? (
              <button onClick={handleSignOut}>Sign out</button>
            ) : (
              <form onSubmit={handleSignIn} className="sign-in-form">
                <input
                  type="text"
                  placeholder="Name"
                  value={signInName}
                  onChange={(e) => setSignInName(e.target.value)}
                  maxLength={32}
                  required
                />
                <input
                  type="password"
                  inputMode="numeric"
                  placeholder="4-digit PIN"
                  value={signInPin}
                  onChange={(e) => setSignInPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
                  maxLength={4}
                  pattern="\d{4}"
                  required
                />
                <button type="submit">Sign in</button>
              </form>
            )}

            <button onClick={handleForgetEverything} disabled={memory.facts.length === 0}>
              Forget everything
            </button>
          </>
        )}
      </aside>
    </main>
  );
}
