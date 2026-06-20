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
  const [user, setUser] = useState({ username: "guest", email: "" });
  const location = useLocation();

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser({ username: "guest", email: "" }));
  }, []);

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
  }, [location.pathname]);

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand" title={user.email || user.username}>
          <span className="mark">{user.username.slice(0, 1).toUpperCase()}</span>
          {user.username}
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
