import { lazy, Suspense, type ReactNode } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";

import { AuthProvider, RequireAuth, signOut, useAuth } from "./auth";
import ErrorBoundary from "./components/ErrorBoundary";
import Login from "./pages/Login";
import Runs from "./pages/Runs";
import Welcome from "./pages/Welcome";

// Pages with charts pull in Chart.js; load them only when opened.
const RunDetail = lazy(() => import("./pages/RunDetail"));
const Trends = lazy(() => import("./pages/Trends"));
const Account = lazy(() => import("./pages/Account"));
const Feedback = lazy(() => import("./pages/Feedback"));

const loading = <main><p className="muted">Loading…</p></main>;

function Nav() {
  const { session, demo } = useAuth();
  const location = useLocation();
  if (!session && !demo) return null;
  return (
    <>
      <nav className="nav">
        <Link to="/" className="brand">Pacer</Link>
        <Link to="/">Runs</Link>
        <Link to="/trends">Trends</Link>
        <Link to="/feedback" state={{ from: location.pathname }}>Feedback</Link>
        <Link to="/account" className="nav-email">{demo ? "Demo" : session?.user.email}</Link>
        <button className="link" onClick={() => signOut()}>{demo ? "Leave demo" : "Sign out"}</button>
      </nav>
      {demo && (
        <p className="demo-banner" role="status">
          You're viewing a demo with sample runs; nothing here can be changed.{" "}
          <Link to="/login?mode=signup" onClick={() => signOut()}>Sign up</Link> to use your own runs.
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
            <Route path="/account" element={protect(<Account />)} />
            <Route path="/feedback" element={protect(<Feedback />)} />
            <Route path="*" element={<main><p>Page not found. <Link to="/">Go to your runs</Link></p></main>} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
