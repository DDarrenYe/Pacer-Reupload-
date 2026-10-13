import { useEffect, useState, type FormEvent } from "react";

import { api } from "../api";
import type { Profile, Sex } from "../types";

const THIS_YEAR = new Date().getFullYear();

/** My Profile: your name (for the runner card), and year of birth and sex (for "How you compare" on Trends). */
export default function ProfileDetailsCard({ readOnly = false }: { readOnly?: boolean }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [year, setYear] = useState("");
  const [sex, setSex] = useState<Sex | "">("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.profile().then((p) => {
      setProfile(p);
      setName(p.display_name ?? "");
      setYear(p.birth_year ? String(p.birth_year) : "");
      setSex(p.sex ?? "");
    }, (e: Error) => setError(e.message));
  }, []);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const saved = await api.saveProfile({
        display_name: name.trim() || null,
        birth_year: year ? Number(year) : null,
        sex: sex || null,
      });
      setProfile(saved);
      setMessage(saved.age !== null && saved.sex ? "Saved. See how you compare on the Trends page." : "Saved.");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!profile) return error ? <section className="card"><p className="error">{error}</p></section> : null;

  return (
    <section className="card stack">
      <h2>Your details</h2>
      <p className="muted">
        Your name appears on your runner card. Your year of birth and sex are used only to compare your times with
        runners like you on the Trends page; leave them blank to skip that.
      </p>
      <form className="stack" onSubmit={save}>
        <label>
          Name
          <input
            value={name}
            maxLength={60}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            autoComplete="name"
            disabled={readOnly}
          />
        </label>
        <div className="row">
          <label>
            Year of birth
            <input
              type="number"
              inputMode="numeric"
              min="1920"
              max={THIS_YEAR - 5}
              value={year}
              onChange={(e) => setYear(e.target.value)}
              placeholder="1995"
              disabled={readOnly}
            />
          </label>
          <label>
            Sex
            <select value={sex} onChange={(e) => setSex(e.target.value as Sex | "")} disabled={readOnly}>
              <option value="">Not set</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
          </label>
        </div>
        <p className="muted small">
          The published age-grading standards only exist for women and men, so those are the two options.
        </p>
        {message && <p className="info" role="status">{message}</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {!readOnly && (
          <div className="actions">
            <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save details"}</button>
          </div>
        )}
      </form>
    </section>
  );
}
