import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { formatDuration, formatPace } from "../format";
import { averagePace, monthDistanceM } from "../runnerStats";
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
      <div className="runner-rank">
        {card?.rank ? (
          <>
            <RankMedal rank={card.rank.rank} size={96} />
            <strong>{card.rank.rank}</strong>
            <span className="muted small">{card.rank.age_grade.toFixed(1)}% age grade</span>
          </>
        ) : (
          <>
            <Unranked />
            <strong>Unranked</strong>
            <Link to="/account" className="small">Add age and sex</Link>
          </>
        )}
      </div>
      <div className="runner-body">
        <h2 className="runner-name">
          {card?.name ?? <Link to="/account">Add your name</Link>}
        </h2>
        <div className="runner-stats">
          <Stat label="Average pace" value={pace === null ? "–" : formatPace(pace)} />
          <Stat label={`${MONTH} distance`} value={`${(month / 1000).toFixed(1)} km`} />
        </div>
        {card && card.bests.length > 0 && (
          <div className="runner-bests" aria-label="Personal bests">
            {card.bests.map((b) => (
              <Link key={b.name} to={`/runs/${b.run_id}`} className="runner-best" title={`Set on ${b.date}`}>
                <span className="tile-label">{b.name}</span>
                <span className="runner-best-time">{formatDuration(b.time_s)}</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="tile-label">{label}</div>
      <div className="runner-stat-value">{value}</div>
    </div>
  );
}

/** A dashed placeholder where the rank badge goes until there's a rank. */
function Unranked() {
  return (
    <svg width="96" height="96" viewBox="0 0 64 64" role="img" aria-label="No rank yet">
      <path d="M8 34 L32 20 L56 34 L56 40 L32 26 L8 40 Z" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeDasharray="3 3" />
    </svg>
  );
}
