/**
 * The fact card -- the deep dive's only visible output (D15 in
 * docs/plans/blocks/A-grounded-answers.md; painted here per Block C).
 *
 * Renders exactly three shapes (Contract 2, docs/plans/blocks/C-demoable.md):
 * a refusal card (no source covers this pair), an empty-but-covered card
 * (the layer resolved, but nothing on it maps to a known field), and the
 * populated card. Every value on this card is the SAME string the gate
 * would substitute into a spoken segment -- app.tools.card renders both
 * from one function, so the card and the answer cannot contradict each
 * other by construction. This component only arranges what's already true.
 */

import type { FactCardMessage } from "../protocol";

export function FactCard({ card }: { card: FactCardMessage }): JSX.Element {
  const header = (
    <h3>
      {card.passport_name} → {card.destination_name}
    </h3>
  );

  // F-FC2: a degraded answer must never look identical to a live one --
  // this badge is the visible half of that invariant.
  const degradedBadge = card.degraded && <span className="card-degraded">fallback source</span>;

  // Provenance footer, in this exact order, omitting any null field
  // (Contract 2). `source_url` wraps `source_name` when both are present.
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
          {i > 0 && " · "}
          {el}
        </span>
      ))}
    </p>
  );

  // F-FC1: covered=false is the refusal card -- never an empty box.
  if (!card.covered) {
    return (
      <div className="fact-card fact-card-refusal">
        {header}
        <p>No source covers this pair.</p>
        {card.embassy_url && (
          <p>
            <a href={card.embassy_url} target="_blank" rel="noreferrer">
              Embassy page
            </a>
          </p>
        )}
      </div>
    );
  }

  // F-FC3: covered but no facts resolved on this layer -- header and
  // footer still render; no empty <ul>.
  if (card.facts.length === 0) {
    return (
      <div className="fact-card">
        {header}
        <p>Nothing to show for this pair.</p>
        {footer}
      </div>
    );
  }

  return (
    <div className="fact-card">
      {header}
      <ul className="fact-card-facts">
        {card.facts.map((f) => (
          <li key={f.path}>
            <span className={`segment-kind fact-kind-${f.kind}`}>[{f.kind}]</span> {f.label} — {f.value}
          </li>
        ))}
      </ul>
      {footer}
    </div>
  );
}
