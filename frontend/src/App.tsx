import { lazy, Suspense, type ReactNode } from "react";
import { BrowserRouter, Link, Navigate, NavLink, Route, Routes } from "react-router-dom";

import { AuthProvider, RequireAuth, signOut, useAuth } from "./auth";
import ErrorBoundary from "./components/ErrorBoundary";
import Login from "./pages/Login";
import Runs from "./pages/Runs";
import Welcome from "./pages/Welcome";

// Pages with charts pull in Chart.js; load them only when opened.
const RunDetail = lazy(() => import("./pages/RunDetail"));
const Trends = lazy(() => import("./pages/Trends"));
const Goals = lazy(() => import("./pages/Goals"));
const StravaCallback = lazy(() => import("./pages/StravaCallback"));
const Account = lazy(() => import("./pages/Account"));
const Rank = lazy(() => import("./pages/Rank"));

const loading = <main><p className="muted">Loading…</p></main>;

// Tab icons, shown on phones where the tabs sit along the bottom of the screen.
const ICONS = {
  runs: "M4 6h16M4 12h16M4 18h10",
  trends: "M4 18l5-6 4 3 7-9",
  rank: "M5 14l7-5 7 5M5 19l7-5 7 5M5 9l7-5 7 5",
  goals: "M6 21V4M6 4h11l-2 4 2 4H6",
  profile: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c1.5-4 4.5-6 8-6s6.5 2 8 6",
};

function Tab({ to, label, icon, end, className = "nav-tab" }: { to: string; label: string; icon: string; end?: boolean; className?: string }) {
  return (
    <NavLink to={to} end={end} className={className}>
      <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d={icon} />
      </svg>
      {label}
    </NavLink>
  );
}

function Nav() {
  const { session, demo } = useAuth();
  if (!session && !demo) return null;
  const email = session?.user.email ?? "";
  return (
    <>
      <nav className="nav" aria-label="Main">
        <Link to="/" className="brand">
          <img src="/favicon.svg" alt="" width="26" height="26" />
          Pacer
        </Link>
        <div className="nav-tabs">
          <Tab to="/" end label="Runs" icon={ICONS.runs} />
          <Tab to="/trends" label="Trends" icon={ICONS.trends} />
          <Tab to="/rank" label="Rank" icon={ICONS.rank} />
          <Tab to="/goals" label="Goals" icon={ICONS.goals} />
          <Tab to="/account" label="Profile" icon={ICONS.profile} className="nav-tab nav-tab-profile" />
        </div>
        <NavLink
          to="/account"
          className="nav-avatar"
          aria-label="My Profile"
          title={demo ? "My Profile (demo)" : `My Profile (${email})`}
        >
          {demo ? "D" : (email[0] ?? "?").toUpperCase()}
        </NavLink>
      </nav>
      {demo && (
        <p className="demo-banner" role="status">
          You're viewing a demo with sample runs; nothing here can be changed.{" "}
          <Link to="/login?mode=signup" onClick={() => signOut()}>Sign up</Link> to use your own runs, or{" "}
          <button className="link" onClick={() => signOut()}>leave the demo</button>.
        </p>
      )}
    </>
  );
}

const protect = (page: ReactNode) => (
  <RequireAuth>
    <Suspense fallback={loading}>{page}</Suspense>
  </RequireAuth>
);

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Nav />
          <Routes>
            <Route path="/welcome" element={<Welcome />} />
            <Route path="/login" element={<Login />} />
            <Route path="/" element={protect(<Runs />)} />
            <Route path="/runs/:id" element={protect(<RunDetail />)} />
            <Route path="/trends" element={protect(<Trends />)} />
            <Route path="/goals" element={protect(<Goals />)} />
            <Route path="/strava/callback" element={protect(<StravaCallback />)} />
            <Route path="/account" element={protect(<Account />)} />
            <Route path="/rank" element={protect(<Rank />)} />
            {/* Old links: feedback now lives at the bottom of My Profile */}
            <Route path="/feedback" element={<Navigate to="/account#feedback" replace />} />
            <Route path="*" element={<main><p>Page not found. <Link to="/">Go to your runs</Link></p></main>} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
