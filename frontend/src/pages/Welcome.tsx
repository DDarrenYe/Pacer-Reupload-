import { Link, Navigate } from "react-router-dom";

import { useAuth } from "../auth";
import DemoButton from "../components/DemoButton";
import { useTitle } from "../useTitle";

export default function Welcome() {
  useTitle("Welcome");
  const { session, demo } = useAuth();
  if (session || demo) return <Navigate to="/" replace />;

  return (
    <main className="welcome">
      <header className="hero">
        <h1>Pacer</h1>
        <p className="lead">See what your runs say about you: splits, how much you fade, your best efforts, and predicted race times.</p>
        <div className="actions">
          <Link className="button" to="/login?mode=signup">Create an account</Link>
          <Link className="button secondary" to="/login">Sign in</Link>
          <DemoButton />
        </div>
        <p className="muted small">The demo uses sample runs; nothing you do there is saved.</p>
      </header>

      <section className="card">
        <h2>How it works</h2>
        <ol className="steps">
          <li><strong>Export a run</strong> from Strava or Garmin as a GPX file.</li>
          <li><strong>Upload it</strong>, or enter a treadmill run by hand (distance and time).</li>
          <li><strong>See the analysis:</strong> km splits, pace drift, best efforts, weekly trends and race predictions.</li>
        </ol>
      </section>

      <section className="card" id="export">
        <h2>Getting your runs out of Strava or Garmin</h2>
        <ul>
          <li><strong>Strava</strong> (website, not the app): open a run → the <strong>⋯</strong> button on the left → <strong>Export GPX</strong>.</li>
          <li><strong>Garmin Connect</strong> (website): open a run → the gear icon at the top right → <strong>Export to GPX</strong>.</li>
          <li><strong>Treadmill, no watch?</strong> Use <strong>Enter manually</strong> on the Runs page.</li>
        </ul>
      </section>

      <section className="card">
        <h2>Your data</h2>
        <p>
          Your runs are private to you. Original files are kept so the analysis can be improved later, and you can
          delete any run, or your whole account and everything in it, at any time.
        </p>
      </section>
    </main>
  );
}
