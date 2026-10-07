import type { Session } from "@supabase/supabase-js";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { DEMO_EVENT, demoToken, endDemo } from "./demo";
import { supabase } from "./supabase";

interface AuthState {
  session: Session | null;
  /** Browsing the read-only demo account (no Supabase login). */
  demo: boolean;
  loading: boolean;
}

const AuthContext = createContext<AuthState>({ session: null, demo: false, loading: true });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ session: null, demo: false, loading: true });

  useEffect(() => {
    const update = (session: Session | null) =>
      setState({ session, demo: !session && demoToken() !== null, loading: false });
    supabase.auth.getSession().then(({ data }) => update(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) endDemo(); // signing in for real leaves the demo
      update(session);
    });
    const onDemo = () => supabase.auth.getSession().then(({ data }) => update(data.session));
    window.addEventListener(DEMO_EVENT, onDemo);
    return () => {
      data.subscription.unsubscribe();
      window.removeEventListener(DEMO_EVENT, onDemo);
    };
  }, []);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);

/** "local" only clears this browser, e.g. after deleting the account, when there's no
 *  login left on the server to sign out of. */
export async function signOut(scope: "global" | "local" = "global") {
  endDemo();
  await supabase.auth.signOut({ scope });
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { session, demo, loading } = useAuth();
  const location = useLocation();
  if (loading) return <main><p className="muted">Loading…</p></main>;
  if (!session && !demo) return <Navigate to="/welcome" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
