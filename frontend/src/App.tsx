/**
 * Sarjy. One screen -- a trip dossier that grows.
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
 * Display state (transcript, reply, segments, fact card, places) lives in
 * a growing `turns` array. Everything on a useRef stays on a useRef --
 * currentTurnIdRef, turnTimingRef, turnInFlightRef, playbackQueueRef,
 * detectorRef and the barge window are untouched. Timing legs and barge
 * are the two things a state refactor would silently break, and pytest
 * cannot catch either.
 */

import type { FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { clearSharedMicStream, getSharedMicStream, TARGET_SAMPLE_RATE } from "./audio/capture";
import { MicAnalyser, pcm16Rms } from "./audio/level";
import { PlaybackQueue } from "./audio/playback";
import { createTurnDetector, type EndpointTiming, type TurnDetector } from "./audio/turn";
import type { ConnectionCallbacks, ConnectionState } from "./net/connection";
import { Connection } from "./net/connection";
import type {
  ConversationState,
  FactCardMessage,
  MemoryMessage,
  PlaceCard,
  SegmentWire,
} from "./protocol";
import { FactCard } from "./ui/FactCard";
import { Orb, type OrbRing } from "./ui/Orb";
import { PlaceStrip } from "./ui/PlaceStrip";

const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws${window.location.search}`;

const PLAYBACK_SAMPLE_RATE = 24_000; // Deepgram's native output rate -- no resampling on this hot path.

const MAX_BINARY_CHUNK_BYTES = 32 * 1024;

const BARGE_IGNORE_WINDOW_MS = 300;

const REDUCED_MOTION =
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type VoiceIssueKind = "unavailable" | "mic-blocked" | "mic-missing";

interface VoiceIssue {
  kind: VoiceIssueKind;
  message: string;
}

interface Turn {
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

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  connecting: "CONNECTING",
  ready: "CONNECTED",
  rotating: "REFRESHING",
  reconnecting: "RECONNECTING",
  offline: "OFFLINE",
  stale: "STALE",
};

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
  return { kind: "unavailable", message: err instanceof Error ? err.message : String(err) };
}

function getOutputLatencyMs(ctx: AudioContext | null): number | null {
  if (!ctx || !Number.isFinite(ctx.outputLatency)) return null;
  return Math.round(ctx.outputLatency * 1000);
}

function fmt(ms: number | null): string {
  return ms === null ? "—" : `${(ms / 1000).toFixed(2)} s`;
}

function registerLabel(kind: SegmentWire["kind"]): string {
  return kind === "judgement" ? "view" : kind;
}

function stateCopy(
  started: boolean,
  assetsReady: boolean,
  voiceIssue: VoiceIssue | null,
  conversationState: ConversationState,
  interrupted: boolean,
): { ring: OrbRing; headline: string; sub: string } {
  if (voiceIssue?.kind === "mic-blocked") {
    return { ring: "ring-error", headline: "MICROPHONE BLOCKED", sub: voiceIssue.message };
  }
  if (voiceIssue?.kind === "mic-missing") {
    return { ring: "ring-error", headline: "NO MICROPHONE", sub: voiceIssue.message };
  }
  if (voiceIssue?.kind === "unavailable") {
    return { ring: "ring-error", headline: "VOICE UNAVAILABLE", sub: voiceIssue.message };
  }
  if (!started && !assetsReady) {
    return { ring: "ring-loading", headline: "WARMING UP", sub: "Loading voice detection…" };
  }
  if (!started) {
    return { ring: "ring-idle", headline: "READY WHEN YOU ARE", sub: "Press start, then just talk." };
  }
  const table: Record<ConversationState, { ring: OrbRing; headline: string; sub: string }> = {
    idle: { ring: "ring-idle", headline: "READY", sub: "Speak whenever you like." },
    listening: {
      ring: "ring-listening",
      headline: "HEARING YOU",
      sub: "Keep going — I'll answer when you stop.",
    },
    thinking: {
      ring: "ring-thinking",
      headline: "CHECKING SOURCES",
      sub: "Looking for a source for this.",
    },
    speaking: { ring: "ring-speaking", headline: "SPEAKING", sub: "Interrupt any time." },
  };
  const row = table[conversationState];
  if (interrupted) {
    return { ...row, sub: `${row.sub} · you interrupted` };
  }
  return row;
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
  const [assetsReady, setAssetsReady] = useState(false);
  const [voiceIssue, setVoiceIssue] = useState<VoiceIssue | null>(null);
  const [interrupted, setInterrupted] = useState(false);
  const [quota, setQuota] = useState<{
    total: number;
    spent: number;
    reserve: number;
    remaining: number;
  } | null>(null);
  const [memory, setMemory] = useState<MemoryMessage | null>(null);
  const [signInName, setSignInName] = useState("");
  const [signInPin, setSignInPin] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);

  const connectionRef = useRef<Connection | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playbackQueueRef = useRef<PlaybackQueue | null>(null);
  const detectorRef = useRef<TurnDetector | null>(null);
  const currentTurnIdRef = useRef<string | null>(null);
  const currentSampleRateRef = useRef(PLAYBACK_SAMPLE_RATE);
  const speakingStartedAtRef = useRef(0);
  const turnCounterRef = useRef(0);
  const turnInFlightRef = useRef(false);
  const turnTimingRef = useRef<{
    turnId: string;
    acousticEndAtMs: number;
    endpointMs: number;
    redemptionMs: number;
    sent: boolean;
  } | null>(null);
  const micAnalyserRef = useRef<MicAnalyser | null>(null);
  const speakLevelRef = useRef(0);
  const dossierEndRef = useRef<HTMLDivElement | null>(null);

  const patchTurn = useCallback((turnId: string, patch: Partial<Turn>): void => {
    setTurns((ts) => ts.map((t) => (t.id === turnId ? { ...t, ...patch } : t)));
  }, []);

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
    setTurns((ts) =>
      ts.map((t) =>
        t.id === turnId
          ? {
              ...t,
              timings: { firstAudioMs, endpointMs: ref.endpointMs, redemptionMs: ref.redemptionMs },
            }
          : t,
      ),
    );
  }, []);

  const handleUtterance = useCallback(async (pcm: ArrayBuffer, endpoint: EndpointTiming): Promise<void> => {
    const connection = connectionRef.current;
    if (!connection) return;

    await connection.ensureFresh();

    if (!connection.isReady()) {
      setConversationState("idle");
      setNotice("Connection is down — wait for it to reconnect, then try again.");
      return;
    }

    turnCounterRef.current += 1;
    const turnId = `t-${turnCounterRef.current}`;
    setInterrupted(false);
    setTurns((ts) => [
      ...ts,
      {
        id: turnId,
        at: Date.now(),
        transcript: null,
        reply: null,
        segments: [],
        factCard: null,
        places: null,
        hedged: false,
        failed: null,
        timings: null,
      },
    ]);

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
    speakLevelRef.current = 0;
    setInterrupted(true);
    setConversationState("listening");
    connectionRef.current?.bargeTurn(turnId);
  }, []);

  const handleConnectionState = useCallback((state: ConnectionState): void => {
    setConnectionState(state);
    const dropped = state === "reconnecting" || state === "offline" || state === "stale";
    if (!dropped || !turnInFlightRef.current) return;

    turnInFlightRef.current = false;
    currentTurnIdRef.current = null;
    playbackQueueRef.current?.stop();
    detectorRef.current?.setSpeaking(false);
    speakLevelRef.current = 0;
    setConversationState("idle");
    setNotice("Connection dropped mid-answer — ask again.");
  }, []);

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

  const detachMicAnalyser = useCallback((): void => {
    micAnalyserRef.current?.disconnect();
    micAnalyserRef.current = null;
  }, []);

  const handleMicRevoked = useCallback((): void => {
    detachMicAnalyser();
    void detectorRef.current?.destroy();
    detectorRef.current = null;
    clearSharedMicStream();
    setStarted(false);
    setVoiceIssue({
      kind: "mic-blocked",
      message: "Sarjy needs the microphone to hear you. Allow it in the address bar, then press Retry.",
    });
  }, [detachMicAnalyser]);

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
      await capture.resume();
      await playback.resume();

      if (!detectorRef.current) {
        detectorRef.current = await buildDetector();
      }
      await detectorRef.current.start();
      watchForMicRevocation();
      detachMicAnalyser();
      const stream = await getSharedMicStream();
      micAnalyserRef.current = new MicAnalyser(capture, stream);
      setStarted(true);
    } catch (err) {
      setVoiceIssue(classifyVoiceError(err));
    } finally {
      setStarting(false);
    }
  }, [starting, buildDetector, watchForMicRevocation, detachMicAnalyser]);

  useEffect(() => {
    const capture = createCaptureContext();
    const playback = new AudioContext({ sampleRate: PLAYBACK_SAMPLE_RATE });
    captureCtxRef.current = capture;
    playbackCtxRef.current = playback;
    playbackQueueRef.current = new PlaybackQueue(playback);

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
      onTranscript: (turnId, text) => patchTurn(turnId, { transcript: text }),
      onReply: (turnId, text) => patchTurn(turnId, { reply: text }),
      onSegments: (turnId, segs, _spoken, isHedged) => {
        patchTurn(turnId, { segments: segs, hedged: isHedged });
      },
      onQuota: (q) => setQuota(q),
      onMemory: (m) => setMemory(m),
      onFactCard: (card) => {
        patchTurn(card.turn_id, { factCard: card });
      },
      onPlaces: (turnId, places) => patchTurn(turnId, { places }),
      onAudioStart: (turnId, sampleRate) => {
        currentTurnIdRef.current = turnId;
        currentSampleRateRef.current = sampleRate;
        playbackQueueRef.current?.beginTurn(() => {
          speakingStartedAtRef.current = performance.now();
          detectorRef.current?.setSpeaking(true);
          setConversationState("speaking");
          const ref = turnTimingRef.current;
          const firstAudioMs = ref ? Math.round(performance.now() - ref.acousticEndAtMs) : null;
          reportTurnTiming(turnId, firstAudioMs);
        });
      },
      onAudioChunk: (turnId, chunk) => {
        if (turnId !== currentTurnIdRef.current) return;
        speakLevelRef.current = pcm16Rms(chunk);
        playbackQueueRef.current?.enqueue(chunk, currentSampleRateRef.current);
      },
      onAudioEnd: (turnId) => {
        if (turnId !== currentTurnIdRef.current) return;
        turnInFlightRef.current = false;
        currentTurnIdRef.current = null;
        detectorRef.current?.setSpeaking(false);
        speakLevelRef.current = 0;
      },
      onTurnFailed: (turnId, stage, message) => {
        turnInFlightRef.current = false;
        if (turnId === currentTurnIdRef.current) {
          currentTurnIdRef.current = null;
          detectorRef.current?.setSpeaking(false);
        }
        speakLevelRef.current = 0;
        patchTurn(turnId, { failed: { stage, message } });
        reportTurnTiming(turnId, null);
      },
    };
    const conn = new Connection(WS_URL, callbacks);
    connectionRef.current = conn;
    conn.connect();

    return () => {
      cancelled = true;
      conn.dispose();
      detachMicAnalyser();
      void detectorRef.current?.destroy();
      void capture.close();
      void playback.close();
    };
  }, [buildDetector, handleConnectionState, reportTurnTiming, patchTurn, detachMicAnalyser]);

  const lastTurn = turns[turns.length - 1];
  useEffect(() => {
    dossierEndRef.current?.scrollIntoView({
      behavior: REDUCED_MOTION ? "auto" : "smooth",
      block: "nearest",
    });
  }, [turns.length, lastTurn?.factCard, lastTurn?.places, lastTurn?.reply, lastTurn?.segments.length]);

  const canStart = assetsReady && !started && !voiceIssue;
  const showRetry = voiceIssue?.kind === "mic-blocked" || voiceIssue?.kind === "mic-missing";
  const copy = stateCopy(started, assetsReady, voiceIssue, conversationState, interrupted);

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <h1 className="wordmark">Sarjy</h1>
          <p className="purpose">A voice for the document · live voice</p>
        </div>
        <div className="header-chips">
          <span className={`chip chip-connection conn-${connectionState}`}>
            {CONNECTION_LABEL[connectionState]}
          </span>
          {quota && (
            <span
              className={`chip chip-quota${quota.remaining === 0 ? " warn" : ""}`}
              title={`spent ${quota.spent} of ${quota.total}; ${quota.reserve} held back as reserve`}
            >
              {quota.remaining === 0
                ? "visa quota · reserve only"
                : `visa quota · ${quota.remaining} left`}
            </span>
          )}
        </div>
      </header>

      <div className="app-main">
        <div className="stage">
          <Orb
            ring={copy.ring}
            reducedMotion={REDUCED_MOTION}
            micAnalyserRef={micAnalyserRef}
            speakLevelRef={speakLevelRef}
          />
          <div className="state-copy">
            <p className="state-headline" aria-live="polite">
              {copy.headline}
            </p>
            <p className="state-sub">{copy.sub}</p>
            <div className="cta">
              {!assetsReady && !voiceIssue && <button disabled>Loading voice detection…</button>}
              {canStart && (
                <button onClick={() => void handleStart()} disabled={starting}>
                  {starting ? "Starting…" : "Start talking"}
                </button>
              )}
              {showRetry && (
                <button onClick={() => void handleStart()}>Retry</button>
              )}
              {voiceIssue?.kind === "unavailable" && (
                <button disabled title={voiceIssue.message}>
                  Start talking
                </button>
              )}
            </div>
          </div>
        </div>

        {notice && <p className="notice">{notice}</p>}

        <div className="dossier">
          {turns.map((turn) => (
            <TurnBlock key={turn.id} turn={turn} />
          ))}
          <div ref={dossierEndRef} />
        </div>

        <div className="diagnostics" aria-live="off">
          {lastTurn?.timings && (
            <span>
              last turn {fmt(lastTurn.timings.firstAudioMs)} voice-to-voice · endpoint{" "}
              {fmt(lastTurn.timings.endpointMs)} · redemption {lastTurn.timings.redemptionMs} ms
            </span>
          )}
          {sessionId && <span>session {sessionId.slice(0, 8)}</span>}
          {connectionN > 0 && <span>#{connectionN}</span>}
          {lastRttMs !== null && <span>{lastRttMs}ms</span>}
          <button className="secondary" type="button" onClick={() => connectionRef.current?.sendPing()}>
            Ping
          </button>
          {connectionState === "offline" && (
            <button type="button" onClick={() => connectionRef.current?.retry()}>
              Retry connection
            </button>
          )}
        </div>
      </div>

      <aside className="rail memory-panel" aria-live="polite">
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
    </div>
  );
}

function TurnBlock({ turn }: { turn: Turn }): JSX.Element {
  const kept = turn.segments.filter((s) => s.ok).length;
  const rejected = turn.segments.length - kept;

  return (
    <article className="turn">
      {turn.transcript && (
        <p className="transcript">
          <span className="who">You</span>
          {turn.transcript}
        </p>
      )}
      {turn.factCard && <FactCard card={turn.factCard} />}
      {turn.places && turn.places.length > 0 && <PlaceStrip places={turn.places} />}
      {turn.reply && (
        <p className="reply">
          <span className="who">Sarjy</span>
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
