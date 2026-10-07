import { lazy, Suspense } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { AuthProvider, RequireAuth, useAuth } from "./auth";
import Login from "./pages/Login";
import Runs from "./pages/Runs";
import { supabase } from "./supabase";

// The run page pulls in Chart.js; load it only when a run is opened.
const RunDetail = lazy(() => import("./pages/RunDetail"));

function Nav() {
  const { session } = useAuth();
  if (!session) return null;
  return (
    <nav className="nav">
      <Link to="/" className="brand">Pacer</Link>
      <span className="muted nav-email">{session.user.email}</span>
      <button className="link" onClick={() => supabase.auth.signOut()}>Sign out</button>
    </nav>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Nav />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<RequireAuth><Runs /></RequireAuth>} />
          <Route
            path="/runs/:id"
            element={
              <RequireAuth>
                <Suspense fallback={<main><p className="muted">Loading…</p></main>}>
                  <RunDetail />
                </Suspense>
              </RequireAuth>
            }
          />
          <Route path="*" element={<main><p>Page not found. <Link to="/">Go to your runs</Link></p></main>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
