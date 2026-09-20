/**
 * Sarjy. One screen.
 *
 * Two state machines, deliberately separate (docs/plans/blocks/01-skeleton-deploy.md):
 * connection state (client-owned: connecting/ready/rotating/reconnecting/
 * offline/stale) and conversation state (server-owned: idle/listening/
 * thinking/speaking). Conflating them is the classic mistake -- a reconnect
 * would then look like the assistant started thinking. Block 1 only ever
 * shows "idle" for the conversation state; the rest is reserved space for
 * Block 2, kept real by being wired up now rather than promised later.
 */

import { useEffect, useRef, useState } from "react";
import type { ConnectionCallbacks, ConnectionState } from "./net/connection";
import { Connection } from "./net/connection";
import type { ConversationState } from "./protocol";

const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws`;

export function App() {
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [conversationState, setConversationState] = useState<ConversationState>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [connectionN, setConnectionN] = useState(0);
  const [notice, setNotice] = useState("");
  const [lastRttMs, setLastRttMs] = useState<number | null>(null);
  const connectionRef = useRef<Connection | null>(null);

  useEffect(() => {
    const callbacks: ConnectionCallbacks = {
      onConnectionState: setConnectionState,
      onConversationState: setConversationState,
      onReady: (info) => {
        setSessionId(info.sessionId);
        setConnectionN(info.connectionN);
      },
      onPong: setLastRttMs,
      onNotice: setNotice,
    };
    const conn = new Connection(WS_URL, callbacks);
    connectionRef.current = conn;
    conn.connect();
    return () => conn.dispose();
  }, []);

  return (
    <main>
      <h1>Sarjy</h1>

      <p className="conversation-state" aria-live="polite">
        {conversationState}
      </p>

      <button disabled title="Voice arrives in Block 2 -- not a dead control, a placeholder">
        Voice (coming in Block 2)
      </button>

      <div className="status-line" aria-live="polite">
        <span>connection: {connectionState}</span>
        {sessionId && <span> · session {sessionId.slice(0, 8)}</span>}
        {connectionN > 0 && <span> · #{connectionN}</span>}
        {lastRttMs !== null && <span> · {lastRttMs}ms</span>}
      </div>

      {notice && <p className="notice">{notice}</p>}

      <button onClick={() => connectionRef.current?.sendPing()}>Ping</button>
      {connectionState === "offline" && (
        <button onClick={() => connectionRef.current?.retry()}>Retry</button>
      )}
    </main>
  );
}
