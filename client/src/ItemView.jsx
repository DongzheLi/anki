import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "./api.js";
import PracticePanel from "./PracticePanel.jsx";

const FEELING_EMOJI = { again: "😵", hard: "😬", good: "🙂", easy: "😎" };

// Single-item practice page: practice the item, then see its full history below.
// Unlike the review session this stays on one item — useful for drilling a
// specific problem on demand regardless of whether it's due.
export default function ItemView() {
  const { id } = useParams();
  const [item, setItem] = useState(null);
  const [flash, setFlash] = useState(null);
  const [me, setMe] = useState("");

  const load = () => api.item(id).then(setItem);
  useEffect(() => { load(); }, [id]);
  useEffect(() => { api.me().then((u) => setMe(u.email)).catch(() => {}); }, []);

  if (!item) return <p className="muted">Loading…</p>;

  // You can open another person's item to read it and its history, but only the
  // owner may practice it (practicing reschedules the card).
  const owned = !item.user_email || item.user_email === me;

  return (
    <div className="item-view">
      <Link to="/" className="back">← Dashboard</Link>

      {flash && <div className="flash">Logged · next due in {flash}d</div>}

      {owned ? (
        <PracticePanel
          item={item}
          onGraded={async () => {
            // Re-fetch to refresh the schedule preview + history, and surface the
            // new interval we just earned.
            const updated = await api.item(id);
            setItem(updated);
            setFlash(updated.interval);
            setTimeout(() => setFlash(null), 2500);
          }}
        />
      ) : (
        <div className="readonly-note muted">Read-only — this item belongs to someone else.</div>
      )}

      <section className="history">
        <h3>History ({item.history.length})</h3>
        {item.history.length === 0 ? (
          <p className="muted">No practices yet.</p>
        ) : (
          <table>
            <thead>
              <tr><th>When</th><th>Felt</th><th>Time</th><th>Interval</th><th>Notes</th></tr>
            </thead>
            <tbody>
              {item.history.map((h) => (
                <tr key={h.id}>
                  <td>{new Date(h.practiced_at + "Z").toLocaleString()}</td>
                  <td>{FEELING_EMOJI[h.feeling]} {h.feeling}</td>
                  <td>{h.time_taken_seconds != null ? `${Math.round(h.time_taken_seconds / 60)}m` : "—"}</td>
                  <td>{h.prev_interval}→{h.new_interval}d</td>
                  <td className="notes">{h.notes || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
