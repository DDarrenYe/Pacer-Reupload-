import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth";
import DemoButton from "../components/DemoButton";
import { useTitle } from "../useTitle";
import { supabase } from "../supabase";

export default function Login() {
  const { session } = useAuth();
  const location = useLocation();
  const [params] = useSearchParams();
  const [mode, setMode] = useState<"signin" | "signup">(params.get("mode") === "signup" ? "signup" : "signin");
  useTitle(mode === "signin" ? "Sign in" : "Create an account");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "error" | "info"; text: string } | null>(null);

  if (session) {
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    const { data, error } =
      mode === "signin"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setBusy(false);
    if (error) setMessage({ kind: "error", text: error.message });
    else if (mode === "signup" && !data.session)
      setMessage({ kind: "info", text: "Check your email to confirm your account, then sign in." });
  }

  return (
    <main className="narrow">
      <h1><Link to="/welcome" className="brand-link">Pacer</Link></h1>
      <p className="muted">Upload your runs and see splits, pace drift and best efforts.</p>
      <form className="card stack" onSubmit={submit}>
        <h2>{mode === "signin" ? "Sign in" : "Create an account"}</h2>
        <label>
          Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={6}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {message && <p className={message.kind === "error" ? "error" : "info"} role="status">{message.text}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(mode === "signin" ? "signup" : "signin");
            setMessage(null);
          }}
        >
          {mode === "signin" ? "New here? Create an account" : "Already have an account? Sign in"}
        </button>
      </form>
      <div className="stack center">
        <p className="muted">Just looking?</p>
        <DemoButton />
      </div>
    </main>
  );
}
