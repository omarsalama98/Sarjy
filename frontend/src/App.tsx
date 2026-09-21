/**
 * Sarjy. One screen -- a trip dossier that grows.
 *
 * Two state machines, deliberately separate (docs/plans/blocks/01-skeleton-deploy.md):
 * connection state (client-owned: connecting/ready/rotating/reconnecting/
 * offline/stale) and conversation state (idle/listening/thinking/speaking).
 * Conflating them is the classic mistake -- a reconnect would then look
 * like the assistant started thinking.
 *
 * Conversation state has two owners, split by who can act first:
 * `listening` and `speaking` are set HERE, directly, the instant
 * the user taps the mic or the playback queue schedules a chunk --
 * no round trip. `thinking` and `idle` arrive from the server's own
 * `state` message.
 *
 * Display state (transcript, reply, segments, fact card, places) lives in
 * a growing `turns` array. Everything on a useRef stays on a useRef --
 * currentTurnIdRef, turnTimingRef, turnInFlightRef, playbackQueueRef,
 * recorderRef and the barge window are untouched. Timing legs and barge
 * are the two things a state refactor would silently break, and pytest
 * cannot catch either.
 */

import type { FormEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { clearSharedMicStream, getSharedMicStream, TARGET_SAMPLE_RATE } from "./audio/capture";
import { MicAnalyser, pcm16Rms } from "./audio/level";
import { PlaybackQueue, type AudioHealth } from "./audio/playback";
import { MicRecorder } from "./audio/recorder";
import type { ConnectionCallbacks, ConnectionState } from "./net/connection";
import { Connection } from "./net/connection";
import type { ConversationState, MemoryMessage, PlaceCard } from "./protocol";
import { fmt, type Turn } from "./turns";
import { NowPane } from "./ui/NowPane";
import { Orb, type OrbRing } from "./ui/Orb";
import { TrailRow } from "./ui/TrailRow";
import { TripDossier } from "./ui/TripDossier";

const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws${window.location.search}`;

const PLAYBACK_SAMPLE_RATE = 24_000; // Deepgram's native output rate -- no resampling on this hot path.

const BARGE_IGNORE_WINDOW_MS = 300;

const REDUCED_MOTION =
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

type VoiceIssueKind = "unavailable" | "mic-blocked" | "mic-missing";

interface VoiceIssue {
  kind: VoiceIssueKind;
  message: string;
}

function createCaptureContext(): AudioContext {
  try {
    const ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
    if (ctx.sampleRate !== TARGET_SAMPLE_RATE) {
      console.warn(
        `sarjy: capture context runs at ${ctx.sampleRate}Hz, not the requested ${TARGET_SAMPLE_RATE}Hz -- the recorder downsamples`,
      );
    }
    return ctx;
  } catch (err) {
    console.warn("sarjy: 16kHz AudioContext was refused, falling back to the device rate", err);
    return new AudioContext();
  }
}

function createPlaybackContext(): AudioContext {
  // Prefer Deepgram's 24 kHz so there is no resampling on the hot path.
  // A device-rate fallback is what recovers from an output-device change
  // that left a 24 kHz context running-but-silent (the silent-Sarjy bug).
  try {
    return new AudioContext({ sampleRate: PLAYBACK_SAMPLE_RATE });
  } catch (err) {
    console.warn("sarjy: 24kHz AudioContext was refused, falling back to the device rate", err);
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

function stateCopy(
  started: boolean,
  voiceIssue: VoiceIssue | null,
  conversationState: ConversationState,
  interrupted: boolean,
  recording: boolean,
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
  if (!started) {
    return { ring: "ring-idle", headline: "READY WHEN YOU ARE", sub: "Tap the mic to talk." };
  }
  if (recording) {
    return { ring: "ring-listening", headline: "HEARING YOU", sub: "Tap again when you're done." };
  }
  const table: Record<ConversationState, { ring: OrbRing; headline: string; sub: string }> = {
    idle: { ring: "ring-idle", headline: "READY", sub: "Tap the mic to talk." },
    listening: {
      ring: "ring-listening",
      headline: "HEARING YOU",
      sub: "Tap again when you're done.",
    },
    thinking: {
      ring: "ring-thinking",
      headline: "CHECKING SOURCES",
      sub: "Looking for a source for this.",
    },
    speaking: { ring: "ring-speaking", headline: "SPEAKING", sub: "Tap the mic to interrupt." },
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
  const [recording, setRecording] = useState(false);
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
  const [audioHealth, setAudioHealth] = useState<AudioHealth>("ok");

  const connectionRef = useRef<Connection | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playbackQueueRef = useRef<PlaybackQueue | null>(null);
  const recorderRef = useRef<MicRecorder | null>(null);
  const currentTurnIdRef = useRef<string | null>(null);
  const outgoingTurnIdRef = useRef<string | null>(null);
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
  const recreatePlaybackRef = useRef<() => Promise<boolean>>(async () => false);

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

  const stopRecordingRef = useRef<() => Promise<void>>(async () => undefined);

  const handleBarge = useCallback((): void => {
    const turnId = currentTurnIdRef.current;
    if (!turnId) return;
    if (performance.now() - speakingStartedAtRef.current < BARGE_IGNORE_WINDOW_MS) return;

    turnInFlightRef.current = false;
    playbackQueueRef.current?.stop();
    currentTurnIdRef.current = null;
    speakLevelRef.current = 0;
    setInterrupted(true);
    setConversationState("listening");
    connectionRef.current?.bargeTurn(turnId);
  }, []);

  const beginOutgoingTurn = useCallback(async (): Promise<string | null> => {
    const connection = connectionRef.current;
    if (!connection) return null;
    await connection.ensureFresh();
    if (!connection.isReady()) {
      setConversationState("idle");
      setNotice("Connection is down — wait for it to reconnect, then try again.");
      return null;
    }
    if (turnInFlightRef.current) {
      handleBarge();
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
      acousticEndAtMs: performance.now(),
      endpointMs: 0,
      redemptionMs: 0,
      sent: false,
    };
    outgoingTurnIdRef.current = turnId;
    currentTurnIdRef.current = turnId;
    connection.startTurn(turnId);
    return turnId;
  }, [handleBarge]);

  const startRecording = useCallback(async (): Promise<void> => {
    const capture = captureCtxRef.current;
    if (!capture || recorderRef.current?.isRecording) return;
    const turnId = await beginOutgoingTurn();
    if (!turnId) return;
    const recorder = new MicRecorder(capture, {
      onChunk: (pcm) => {
        connectionRef.current?.sendBinary(pcm);
      },
      onAutoStop: () => {
        void stopRecordingRef.current();
      },
    });
    recorderRef.current = recorder;
    try {
      await recorder.start();
    } catch (err) {
      setVoiceIssue(classifyVoiceError(err));
      recorderRef.current = null;
      outgoingTurnIdRef.current = null;
      return;
    }
    setRecording(true);
    setConversationState("listening");
  }, [beginOutgoingTurn]);

  const stopRecording = useCallback(async (): Promise<void> => {
    const recorder = recorderRef.current;
    const turnId = outgoingTurnIdRef.current;
    if (!recorder || !turnId) {
      setRecording(false);
      return;
    }
    const { samples, elapsedMs } = recorder.stop();
    recorderRef.current = null;
    outgoingTurnIdRef.current = null;
    setRecording(false);

    const timing = turnTimingRef.current;
    if (timing && timing.turnId === turnId) {
      timing.endpointMs = elapsedMs;
      timing.acousticEndAtMs = performance.now();
    }

    if (samples < TARGET_SAMPLE_RATE / 10) {
      connectionRef.current?.endTurn(turnId, samples);
      turnInFlightRef.current = false;
      setConversationState("idle");
      setNotice("That was too short — tap, speak, then tap again.");
      return;
    }

    turnInFlightRef.current = true;
    connectionRef.current?.endTurn(turnId, samples);
  }, []);

  stopRecordingRef.current = stopRecording;

  const handleConnectionState = useCallback((state: ConnectionState): void => {
    setConnectionState(state);
    const dropped = state === "offline";
    if (!dropped || !turnInFlightRef.current) return;

    turnInFlightRef.current = false;
    currentTurnIdRef.current = null;
    playbackQueueRef.current?.stop();
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

  const attachPlaybackHealth = useCallback((queue: PlaybackQueue): void => {
    queue.setHealthListener(
      (health) => {
        setAudioHealth(health);
        // The chip is the idle signal (a fresh context is suspended until a
        // gesture). Only a *dead* graph needs a banner — and it must clear
        // when health returns to ok, or a recovered context still looks broken.
        setNotice((current) => {
          if (health === "dead") return "Audio output died — tap AUDIO to restore.";
          if (current.startsWith("Audio ")) return "";
          return current;
        });
      },
      () => {
        void recreatePlaybackRef.current();
      },
    );
  }, []);

  const recreatePlayback = useCallback(async (): Promise<boolean> => {
    const old = playbackCtxRef.current;
    playbackQueueRef.current?.stop();
    const next = createPlaybackContext();
    try {
      await next.resume();
    } catch (err) {
      console.warn("sarjy: playback recreate resume failed", err);
    }
    playbackCtxRef.current = next;
    const queue = new PlaybackQueue(next);
    playbackQueueRef.current = queue;
    attachPlaybackHealth(queue);
    if (old && old.state !== "closed") {
      void old.close();
    }
    if (next.state !== "running") {
      setAudioHealth("blocked");
      return false;
    }
    setAudioHealth("ok");
    setNotice("");
    return true;
  }, [attachPlaybackHealth]);

  recreatePlaybackRef.current = recreatePlayback;

  const restoreAudio = useCallback(async (): Promise<void> => {
    const queue = playbackQueueRef.current;
    if (queue && (await queue.ensureRunning())) {
      setNotice("");
      return;
    }
    await recreatePlayback();
  }, [recreatePlayback]);

  const detachMicAnalyser = useCallback((): void => {
    micAnalyserRef.current?.disconnect();
    micAnalyserRef.current = null;
  }, []);

  const handleMicRevoked = useCallback((): void => {
    detachMicAnalyser();
    void recorderRef.current?.destroy();
    recorderRef.current = null;
    setRecording(false);
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

  const handleStart = useCallback(async (): Promise<void> => {
    const capture = captureCtxRef.current;
    const playback = playbackCtxRef.current;
    if (!capture || !playback || starting) return;

    setStarting(true);
    setVoiceIssue(null);
    try {
      await capture.resume();
      await playback.resume();
      await playbackQueueRef.current?.ensureRunning();
      watchForMicRevocation();
      detachMicAnalyser();
      const stream = await getSharedMicStream();
      micAnalyserRef.current = new MicAnalyser(capture, stream);
      setStarted(true);
      await startRecording();
    } catch (err) {
      setVoiceIssue(classifyVoiceError(err));
    } finally {
      setStarting(false);
    }
  }, [starting, watchForMicRevocation, detachMicAnalyser, startRecording]);

  const onMicClick = useCallback((): void => {
    if (starting) return;
    if (recorderRef.current?.isRecording) {
      void stopRecording();
      return;
    }
    if (!started) {
      void handleStart();
      return;
    }
    void startRecording();
  }, [starting, started, handleStart, startRecording, stopRecording]);

  useEffect(() => {
    const capture = createCaptureContext();
    const playback = createPlaybackContext();
    captureCtxRef.current = capture;
    playbackCtxRef.current = playback;
    const queue = new PlaybackQueue(playback);
    playbackQueueRef.current = queue;
    attachPlaybackHealth(queue);

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
        void playbackQueueRef.current?.ensureRunning();
        playbackQueueRef.current?.beginTurn(() => {
          speakingStartedAtRef.current = performance.now();
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
        speakLevelRef.current = 0;
      },
      onTurnFailed: (turnId, stage, message) => {
        turnInFlightRef.current = false;
        if (turnId === currentTurnIdRef.current) {
          currentTurnIdRef.current = null;
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
      conn.dispose();
      detachMicAnalyser();
      void recorderRef.current?.destroy();
      void capture.close();
      void playback.close();
    };
  }, [handleConnectionState, reportTurnTiming, patchTurn, detachMicAnalyser, attachPlaybackHealth]);

  const lastTurn = turns[turns.length - 1];
  const trail = turns.slice(0, -1);
  const latestCard = [...turns].reverse().find((t) => t.factCard)?.factCard ?? null;
  const accumulatedPlaces = (() => {
    const seen = new Set<string>();
    const out: PlaceCard[] = [];
    for (const t of turns) {
      for (const p of t.places ?? []) {
        const key = p.name;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(p);
      }
    }
    return out;
  })();
  useEffect(() => {
    dossierEndRef.current?.scrollIntoView({
      behavior: REDUCED_MOTION ? "auto" : "smooth",
      block: "nearest",
    });
  }, [turns.length, lastTurn?.factCard, lastTurn?.places, lastTurn?.reply, lastTurn?.segments.length]);

  const connectionChip =
    connectionState === "offline"
      ? "OFFLINE"
      : connectionState === "ready" || connectionN > 0
        ? "CONNECTED"
        : "CONNECTING";
  const canStart = !started && !voiceIssue;
  const showRetry = voiceIssue?.kind === "mic-blocked" || voiceIssue?.kind === "mic-missing";
  const copy = stateCopy(started, voiceIssue, conversationState, interrupted, recording);

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <h1 className="wordmark">Sarjy</h1>
          <p className="purpose">A voice for the document · live voice</p>
        </div>
        <div className="header-chips">
          <span
            className={`chip chip-connection conn-${connectionState === "offline" ? "offline" : "ready"}`}
          >
            {connectionChip}
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
          <button
            type="button"
            className={`chip chip-audio${audioHealth !== "ok" ? " warn" : ""}`}
            onClick={() => void restoreAudio()}
            title={
              audioHealth === "ok"
                ? "Playback is running. Click if you can't hear her."
                : "Audio output is blocked or dead. Click to restore — browsers need a tap."
            }
          >
            {audioHealth === "ok" ? "audio · live" : audioHealth === "blocked" ? "audio · blocked" : "audio · dead"}
          </button>
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
              {canStart && (
                <button className={recording ? "mic-hot" : ""} disabled={starting} onClick={onMicClick}>
                  {starting ? "Starting…" : "Tap to talk"}
                </button>
              )}
              {started && !voiceIssue && (
                <button className={recording ? "mic-hot" : ""} onClick={onMicClick}>
                  {recording
                    ? "Listening — tap to send"
                    : conversationState === "speaking"
                      ? "Tap to interrupt"
                      : "Tap to talk"}
                </button>
              )}
              {showRetry && (
                <button onClick={() => void handleStart()}>Retry</button>
              )}
              {voiceIssue?.kind === "unavailable" && (
                <button disabled title={voiceIssue.message}>
                  Mic unavailable
                </button>
              )}
            </div>
          </div>
        </div>

        {notice && <p className="notice">{notice}</p>}

        <div className="dossier">
          {turns.length === 0 && !voiceIssue && (
            <p className="opening-cue">
              When you're ready, try:{" "}
              <span className="opening-line">
                I'm travelling on a Saudi passport. Do I need a visa for Japan?
              </span>
            </p>
          )}
          {lastTurn && <NowPane turn={lastTurn} />}
          {trail.length > 0 && (
            <div className="trail">
              <h2 className="trail-heading">Earlier</h2>
              {[...trail].reverse().map((turn) => (
                <TrailRow key={turn.id} turn={turn} />
              ))}
            </div>
          )}
          <div ref={dossierEndRef} />
        </div>

        <div className="diagnostics" aria-live="off">
          {lastTurn?.timings && (
            <span>
              last turn {fmt(lastTurn.timings.firstAudioMs)} voice-to-voice · spoke{" "}
              {fmt(lastTurn.timings.endpointMs)}
            </span>
          )}
          {connectionState === "offline" && (
            <button type="button" onClick={() => connectionRef.current?.retry()}>
              Retry connection
            </button>
          )}
          <details className="diagnostics-more">
            <summary>session</summary>
            {sessionId && <span>session {sessionId.slice(0, 8)}</span>}
            {connectionN > 0 && <span>#{connectionN}</span>}
            {lastRttMs !== null && <span>{lastRttMs}ms rtt</span>}
            <button className="secondary" type="button" onClick={() => connectionRef.current?.sendPing()}>
              Ping
            </button>
          </details>
        </div>
      </div>

      <TripDossier
        memory={memory}
        latestCard={latestCard}
        places={accumulatedPlaces}
        signInName={signInName}
        signInPin={signInPin}
        onSignInName={setSignInName}
        onSignInPin={setSignInPin}
        onSignIn={handleSignIn}
        onSignOut={handleSignOut}
        onForget={handleForgetEverything}
      />
    </div>
  );
}
