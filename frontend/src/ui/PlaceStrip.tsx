/**
 * Sarjy's picks -- her choice is judgement; the photo and words are sourced
 * from Wikipedia (title, lead sentence, revision date). A failed lookup
 * keeps the note as text with a visible reason, never a broken <img>.
 */

import { useState } from "react";
import type { PlaceCard } from "../protocol";

const REASON_COPY: Record<string, string> = {
  not_found: "no Wikipedia article",
  disambiguation: "name was ambiguous",
  no_image: "article has no lead image",
  timeout: "lookup timed out",
  http_error: "Wikipedia didn't answer",
};

export function PlaceStrip({ places }: { places: PlaceCard[] }): JSX.Element {
  return (
    <section className="place-strip">
      <h2>Her pick, sourced photo</h2>
      <ul className="place-cards">
        {places.map((p) => (
          <li key={p.name} className={`place-card${p.ok && p.image_url ? "" : " place-card-failed"}`}>
            {p.ok && p.image_url ? <PlacePhoto card={p} /> : <PlaceFallback card={p} />}
            <div className="place-meta">
              <p className="place-title">{p.title ?? p.name}</p>
              {p.description && <p className="place-desc">{p.description}</p>}
              <p className="place-source">
                {p.ok && p.page_url ? (
                  <a href={p.page_url} target="_blank" rel="noreferrer">
                    Wikipedia
                  </a>
                ) : (
                  "Wikipedia"
                )}
                {p.revision_date && <> · {p.revision_date.slice(0, 10)}</>}
                {!p.ok && p.reason && <> · couldn&apos;t source a photo ({REASON_COPY[p.reason] ?? p.reason})</>}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function PlacePhoto({ card }: { card: PlaceCard }): JSX.Element {
  const [broken, setBroken] = useState(false);
  if (broken || !card.image_url) return <div className="place-photo place-photo-empty" />;
  return (
    <div className="place-photo">
      <img
        src={card.image_url}
        alt=""
        referrerPolicy="no-referrer"
        onError={() => setBroken(true)}
      />
    </div>
  );
}

function PlaceFallback({ card }: { card: PlaceCard }): JSX.Element {
  return (
    <div className="place-photo place-photo-empty">
      <span>{card.ok ? "No photo" : "Couldn't source a photo"}</span>
    </div>
  );
}
