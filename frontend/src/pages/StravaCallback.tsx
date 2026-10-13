import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../api";
import { checkStravaState, describeSync } from "../strava";
import { useTitle } from "../useTitle";

/** Strava sends the browser back here after the user approves (or declines) access. */
export default function StravaCallback() {
  useTitle("Connecting Strava");
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [step, setStep] = useState("Connecting your Strava account…");
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    // React's dev mode runs effects twice; a Strava code only works once.
    if (started.current) return;
    started.current = true;
    const code = params.get("code");
    if (params.get("error") || !code) {
      setError("Strava access wasn't granted, so nothing was connected.");
      return;
    }
    if (!checkStravaState(params.get("state"))) {
      setError("This link didn't come from your own Connect click, so it was ignored. Try connecting again.");
      return;
    }
    (async () => {
      try {
        await api.stravaConnect(code, params.get("scope") ?? "");
        setStep("Connected. Importing your runs…");
        const result = await api.stravaSync();
        navigate("/", { replace: true, state: { notice: `Strava connected. ${describeSync(result)}` } });
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [params, navigate]);

  return (
    <main className="narrow">
      {error ? (
        <>
          <p className="error" role="alert">{error}</p>
          <p><Link to="/account">Back to My Profile</Link></p>
        </>
      ) : (
        <p className="muted" role="status">{step}</p>
      )}
    </main>
  );
}
