import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, type Account as AccountInfo } from "../api";
import { signOut, useAuth } from "../auth";
import FeedbackCard from "../components/FeedbackCard";
import ProfileDetailsCard from "../components/ProfileDetailsCard";
import RankMedal from "../components/RankMedal";
import StravaCard from "../components/StravaCard";
import type { OverallRank } from "../types";
import { useTitle } from "../useTitle";

export default function Account() {
  useTitle("My Profile");
  const { session, demo } = useAuth();
  const navigate = useNavigate();
  const [info, setInfo] = useState<AccountInfo | null>(null);
  const [rank, setRank] = useState<OverallRank | null>(null);
  const [confirmText, setConfirmText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.account().then(setInfo, (e: Error) => setError(e.message));
    // The rank is a nice extra: if it can't load, the page simply doesn't show it.
    api.comparison().then((c) => setRank(c.overall), () => setRank(null));
  }, []);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteAccount();
      await signOut("local");
      navigate("/welcome", { replace: true });
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>My Profile</h1>
      <section className="card stack">
        <p>
          {demo ? "You're browsing the demo account." : <>Signed in as <strong>{session?.user.email}</strong>.</>}
          {info && ` ${info.run_count} run${info.run_count === 1 ? "" : "s"} saved.`}
        </p>
        {rank && (
          <Link to="/rank" className="rank-badge" title="See your rank and how you compare">
            <RankMedal rank={rank.rank} size={36} />
            <span>
              {rank.label}
              <span className="muted small"> · {rank.age_grade.toFixed(1)}% age grade</span>
            </span>
          </Link>
        )}
        <button className="secondary" onClick={() => signOut().then(() => navigate("/welcome"))}>
          {demo ? "Leave the demo" : "Sign out"}
        </button>
      </section>

      <ProfileDetailsCard readOnly={demo} />

      {!demo && <StravaCard />}

      {!demo && (
        <section className="card stack danger-zone">
          <h2>Delete my account</h2>
          <p>
            This permanently deletes all your runs, their original files, your goals, your details, any feedback
            you've sent, your Strava connection, and your login. It can't be undone.
          </p>
          <label>
            Type DELETE to confirm
            <input value={confirmText} onChange={(e) => setConfirmText(e.target.value)} autoComplete="off" />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <div className="actions">
            <button className="danger" onClick={remove} disabled={confirmText !== "DELETE" || busy}>
              {busy ? "Deleting…" : "Delete my account"}
            </button>
          </div>
        </section>
      )}

      <FeedbackCard />
    </main>
  );
}
