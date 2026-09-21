/**
 * The trip file: pair, visa, places, memory. Accumulates across turns so
 * the reviewer sees a working document, not a log.
 */
import type { FormEvent } from "react";
import type { FactCardMessage, MemoryMessage, PlaceCard } from "../protocol";

export function TripDossier({
  memory,
  latestCard,
  places,
  signInName,
  signInPin,
  onSignInName,
  onSignInPin,
  onSignIn,
  onSignOut,
  onForget,
}: {
  memory: MemoryMessage | null;
  latestCard: FactCardMessage | null;
  places: PlaceCard[];
  signInName: string;
  signInPin: string;
  onSignInName: (v: string) => void;
  onSignInPin: (v: string) => void;
  onSignIn: (e: FormEvent) => void;
  onSignOut: () => void;
  onForget: () => void;
}): JSX.Element {
  const visaType = latestCard?.facts.find((f) => f.path === "visa.type");

  return (
    <aside className="rail trip-dossier" aria-live="polite">
      <h2>The trip</h2>

      {latestCard ? (
        <section className="dossier-pair">
          <p className="dossier-route">
            {latestCard.passport_name} → {latestCard.destination_name}
          </p>
          {visaType && <p className="dossier-visa">{visaType.value}</p>}
          <p className="dossier-source">
            {latestCard.degraded && <span className="card-degraded">fallback</span>}
            {latestCard.source_name ?? "no live source"}
            {latestCard.layer && <> · {latestCard.layer}</>}
          </p>
          {latestCard.embassy_url && !latestCard.covered && (
            <p>
              <a className="embassy-link" href={latestCard.embassy_url} target="_blank" rel="noreferrer">
                {latestCard.destination_name} embassy listing
              </a>
            </p>
          )}
        </section>
      ) : (
        <p className="hint">No visa pair yet — ask her about a destination.</p>
      )}

      {places.length > 0 && (
        <section>
          <h3>Places</h3>
          <ul className="dossier-places">
            {places.map((p) => (
              <li key={p.name}>{p.ok ? p.name : `${p.name} (no photo)`}</li>
            ))}
          </ul>
        </section>
      )}

      <h3>What she remembers</h3>
      {!memory && <p className="hint">Connecting…</p>}
      {memory && (
        <>
          <p className="memory-tier">
            {memory.tier === "signed_in"
              ? `Signed in as ${memory.name}`
              : "This session only — sign in to keep these"}
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
            <button onClick={onSignOut}>Sign out</button>
          ) : (
            <form onSubmit={onSignIn} className="sign-in-form">
              <input
                type="text"
                placeholder="Name"
                value={signInName}
                onChange={(e) => onSignInName(e.target.value)}
                maxLength={32}
                required
              />
              <input
                type="password"
                inputMode="numeric"
                placeholder="4-digit PIN"
                value={signInPin}
                onChange={(e) => onSignInPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
                maxLength={4}
                pattern="\d{4}"
                required
              />
              <button type="submit">Sign in</button>
            </form>
          )}

          <button onClick={onForget} disabled={memory.facts.length === 0}>
            Forget everything
          </button>
        </>
      )}
    </aside>
  );
}
