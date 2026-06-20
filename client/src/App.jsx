import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "./api.js";

// Shared layout: a compact, tool-like navbar (brand left; Dashboard + Study
// right) over the page content. The aggregate stats no longer live in the bar —
// they read as dashboard data, so we fetch them here and hand them down via the
// router Outlet context for the Dashboard to render as stat cards. The Study
// button still needs the due count, so it stays in the bar as a small pill.
export default function App() {
  const [stats, setStats] = useState(null);
  const location = useLocation();

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
  }, [location.pathname]);

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="mark">M</span>
          My Journey
        </Link>
        <nav className="nav">
          <NavLink to="/" end className="navlink">Dashboard</NavLink>
          <NavLink to="/study" className="navlink primary">
            Study
            {stats?.dueCount ? <span className="pill">{stats.dueCount}</span> : null}
          </NavLink>
        </nav>
      </header>
      <main className="main">
        <Outlet context={{ stats }} />
      </main>
    </div>
  );
}
