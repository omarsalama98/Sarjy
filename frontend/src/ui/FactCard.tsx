/**
 * The fact card -- the deep dive's document. Every value is the SAME string
 * the gate would substitute into a spoken segment (app.tools.card renders
 * both from one function). This component only arranges what's already true.
 *
 * Three shapes: refusal (no source covers this pair), empty-but-covered,
 * and populated. `quoted` rows get a pill; `sourced` rows do not -- the
 * card's provenance footer already names the source for the whole card.
 */

import type { FactCardMessage } from "../protocol";

export function FactCard({ card }: { card: FactCardMessage }): JSX.Element {
  const header = (
    <h3 className="fact-card-pair">
      {card.passport_name} → {card.destination_name}
    </h3>
  );

  const degradedBadge = card.degraded && <span className="card-degraded">fallback source</span>;

  const provenance: JSX.Element[] = [];
  if (card.source_name) {
    provenance.push(
      <span key="source">
        {card.source_url ? (
          <a href={card.source_url} target="_blank" rel="noreferrer">
            {card.source_name}
          </a>
        ) : (
          card.source_name
        )}
      </span>,
    );
  }
  if (card.source_date) provenance.push(<span key="date">{card.source_date}</span>);
  if (card.retrieved) provenance.push(<span key="retrieved">retrieved {card.retrieved}</span>);
  if (card.layer) provenance.push(<span key="layer">{card.layer}</span>);

  const footer = (provenance.length > 0 || degradedBadge) && (
    <p className="card-provenance">
      {degradedBadge}
      {provenance.map((el, i) => (
        <span key={i}>
          {(i > 0 || degradedBadge) && " · "}
          {el}
        </span>
      ))}
    </p>
  );

  if (!card.covered) {
    return (
      <article className="fact-card fact-card-refusal">
        {header}
        <p className="fact-refusal-line">No source covers this pair.</p>
        {card.embassy_url && (
          <p>
            <a className="embassy-link" href={card.embassy_url} target="_blank" rel="noreferrer">
              {card.destination_name} embassy listing
            </a>
          </p>
        )}
      </article>
    );
  }

  if (card.facts.length === 0) {
    return (
      <article className={`fact-card${card.degraded ? " fact-card-degraded" : ""}`}>
        {header}
        <p>Nothing to show for this pair.</p>
        {footer}
      </article>
    );
  }

  return (
    <article className={`fact-card${card.degraded ? " fact-card-degraded" : ""}`}>
      {header}
      <dl className="fact-rows">
        {card.facts.map((f) => (
          <div key={f.path} className="fact-row">
            <dt className="fact-label">{f.label}</dt>
            <dd className="fact-value">
              {f.value}
              {f.kind === "quoted" && <span className="pill-quoted">quoted</span>}
            </dd>
          </div>
        ))}
      </dl>
      {footer}
    </article>
  );
}
