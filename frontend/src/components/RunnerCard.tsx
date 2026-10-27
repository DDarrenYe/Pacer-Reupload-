import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { formatDuration, formatPace } from "../format";
import { averagePace, monthDistanceM } from "../runnerStats";
import { TITLE_DESCRIPTIONS } from "../titles";
import type { Run, RunnerCard as Card } from "../types";
import RankMedal from "./RankMedal";

const MONTH = new Date().toLocaleDateString(undefined, { month: "long" });

/** Runs page: your rank, name, average pace, personal bests and this month's distance. */
export default function RunnerCard({ runs }: { runs: Run[] }) {
  const [card, setCard] = useState<Card | null>(null);

  useEffect(() => {
    api.runnerCard().then(setCard, () => setCard(null));
  }, [runs.length]); // refresh after an upload or import changes the list

  const pace = averagePace(runs);
  const month = monthDistanceM(runs);

  return (
    <section className="card runner-card" aria-label="Runner card">
      <div className="runner-id">
        {card?.rank ? <RankMedal rank={card.rank.rank} size={64} /> : <Unranked />}
        <div className="runner-heading">
          <h2 className="runner-name">{card?.name ?? <Link to="/account">Add your name</Link>}</h2>
          <p className="runner-sub">
            {card?.title && !card.title.locked && <TitleBadge name={card.title.name} reason={card.title.reason} />}
            {card?.rank ? (
              <Link to="/rank" className="runner-rank-link">
                {card.rank.label} · {card.rank.age_grade.toFixed(1)}% age grade
              </Link>
            ) : (
              <Link to="/account">Unranked: add your age and sex</Link>
            )}
          </p>
          {card?.title?.locked && (
            <p className="muted small">
              Your runner title unlocks after {card.title.needed} runs with km splits ({card.title.runs_considered} so far).
            </p>
          )}
        </div>
      </div>
      <dl className="stat-strip runner-stats">
        <Stat label={MONTH} value={`${(month / 1000).toFixed(1)} km`} />
        <Stat label="Avg pace" value={pace === null ? "–" : formatPace(pace)} />
        {card?.bests.map((b) => (
          <div key={b.name}>
            <dt>Best {b.name === "Half marathon" ? "half" : b.name.toLowerCase()}</dt>
            <dd>
              <Link to={`/runs/${b.run_id}`} title={`Set on ${b.date}`}>{formatDuration(b.time_s)}</Link>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** The title pill; click it to open what the archetype means and why you got it. */
function TitleBadge({ name, reason }: { name: string; reason: string }) {
  const [open, setOpen] = useState(false);
  const about = TITLE_DESCRIPTIONS[name];
  return (
    <span className="runner-title-wrap">
      <button
        className="runner-title"
        aria-expanded={open}
        aria-controls="runner-title-about"
        onClick={() => setOpen(!open)}
        title={open ? undefined : reason}
      >
        {name}
        <span aria-hidden="true">{open ? " ▴" : " ▾"}</span>
      </button>
      {open && (
        <span id="runner-title-about" className="runner-title-about" role="note">
          {about && (
            <>
              <span className="tile-label">{about.group}</span>
              <span>{about.description}</span>
            </>
          )}
          <span className="muted small">
            <strong>Why you:</strong> {reason}
          </span>
        </span>
      )}
    </span>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

/** A dashed placeholder where the rank badge goes until there's a rank. */
function Unranked() {
  return (
    <svg width="64" height="64" viewBox="0 0 64 64" role="img" aria-label="No rank yet">
      <path d="M8 34 L32 20 L56 34 L56 40 L32 26 L8 40 Z" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeDasharray="3 3" />
    </svg>
  );
}
