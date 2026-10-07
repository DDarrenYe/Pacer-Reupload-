import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api";
import { useSlowNotice } from "../useSlowNotice";

export default function DemoButton({ className = "secondary" }: { className?: string }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const slow = useSlowNotice(busy);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      await api.startDemo();
      navigate("/");
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className={className} onClick={start} disabled={busy}>
        {busy ? "Opening the demo…" : "Try the demo"}
      </button>
      {slow && <p className="info">Waking up the server; this can take up to a minute.</p>}
      {error && <p className="error">{error}</p>}
    </>
  );
}
