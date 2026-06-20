import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "./api.js";
import PracticePanel from "./PracticePanel.jsx";

// The focused review session: walk the due queue one item at a time. We snapshot
// the queue once at the start (from /api/due) so grading — which pushes an
// item's due date into the future — doesn't reshuffle the list mid-session.
// Each item's full body is fetched lazily as we reach it.
export default function Review() {
  const [queue, setQueue] = useState(null); // array of due summaries
  const [index, setIndex] = useState(0);
  const [current, setCurrent] = useState(null); // full item for `index`
  const [done, setDone] = useState(0);

  useEffect(() => {
    api.due().then((rows) => setQueue(rows));
  }, []);

  // Load the full item whenever the cursor moves.
  useEffect(() => {
    if (!queue || index >= queue.length) return;
    api.item(queue[index].id).then(setCurrent);
  }, [queue, index]);

  if (!queue) return <p className="muted">Loading…</p>;

  if (queue.length === 0) {
    return (
      <div className="review-done">
        <h1>Nothing due 🎉</h1>
        <p className="muted">Add items or come back when cards are scheduled.</p>
        <Link to="/" className="btn primary">Back to dashboard</Link>
      </div>
    );
  }

  if (index >= queue.length) {
    return (
      <div className="review-done">
        <h1>Session complete 🎉</h1>
        <p className="muted">{done} item{done === 1 ? "" : "s"} reviewed.</p>
        <Link to="/" className="btn primary">Back to dashboard</Link>
      </div>
    );
  }

  return (
    <div className="review">
      <div className="progress">
        <div className="bar" style={{ width: `${(index / queue.length) * 100}%` }} />
        <span className="progress-label">{index + 1} / {queue.length}</span>
      </div>
      <div className="crumb muted">
        {queue[index].category_name}
        {queue[index].labels?.length ? ` › ${queue[index].labels.join(", ")}` : ""}
      </div>
      {current && current.id === queue[index].id ? (
        <PracticePanel
          item={current}
          onGraded={() => {
            setDone((d) => d + 1);
            setIndex((i) => i + 1);
          }}
        />
      ) : (
        <p className="muted">Loading…</p>
      )}
    </div>
  );
}
