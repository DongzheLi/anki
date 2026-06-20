import { useEffect, useState } from "react";
import { api } from "./api.js";
import Content from "./Content.jsx";

// The core practice interaction, shared by the single-item view and the review
// session. Flow: read the prompt (title + description) → attempt it on your own
// → Reveal the stored solution(s) → grade how it felt. The grade drives SM-2 on
// the server; the four buttons preview the resulting interval.
//
// "Minutes taken" is a manual, optional field you fill in yourself — there is no
// live stopwatch (it would only ever measure time spent staring at this tab,
// since you solve elsewhere). It is recorded for your own history only and does
// NOT affect scheduling — SM-2 looks at the grade alone.
export default function PracticePanel({ item, onGraded }) {
  const [revealed, setRevealed] = useState(false);
  const [activeSol, setActiveSol] = useState(0);
  const [minutes, setMinutes] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  // Reset when the item changes (review session advances without unmounting).
  useEffect(() => {
    setRevealed(false);
    setActiveSol(0);
    setMinutes("");
    setNotes("");
  }, [item.id]);

  async function grade(feeling) {
    setBusy(true);
    let time = null;
    if (minutes.trim() !== "") {
      const secs = Math.round(parseFloat(minutes) * 60);
      time = Number.isFinite(secs) ? secs : null;
    }
    try {
      await api.practice(item.id, { feeling, time_taken_seconds: time, notes: notes.trim() || null });
      onGraded(feeling);
    } finally {
      setBusy(false);
    }
  }

  const days = (n) => (n >= 1 ? `${n}d` : "<1d");

  return (
    <div className="practice">
      <div className="prompt">
        <div className="prompt-title">
          <h1>{item.title}</h1>
          {item.link && (
            <a className="problem-link" href={item.link} target="_blank" rel="noreferrer">
              ↗ open problem
            </a>
          )}
        </div>
        <label className="time-field">
          <span>minutes</span>
          <input
            className="min-input"
            type="number"
            min="0"
            step="1"
            placeholder="—"
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
            title="Optional: how long it took you, in minutes"
          />
        </label>
      </div>

      {/* The card FRONT: the problem statement, always visible. */}
      {item.description ? (
        <Content format="markdown" content={item.description} />
      ) : (
        <p className="muted">No problem description.</p>
      )}

      {!revealed ? (
        // Revealing is deliberately one-way: there is no button to hide the
        // solution again. Once you've seen it, you grade honestly.
        <button className="btn primary big reveal" onClick={() => setRevealed(true)}>
          Reveal solution
        </button>
      ) : (
        <>
          <div className="back-label">{item.solutions.length > 1 ? "Solutions" : "Solution"}</div>
          {item.solutions.length === 0 ? (
            <p className="muted">No solution saved.</p>
          ) : (
            <>
              {item.solutions.length > 1 && (
                <div className="sol-tabs">
                  {item.solutions.map((s, i) => (
                    <button
                      key={s.id ?? i}
                      className={`sol-tab ${i === activeSol ? "active" : ""}`}
                      onClick={() => setActiveSol(i)}
                    >
                      {s.language || s.format}
                    </button>
                  ))}
                </div>
              )}
              {(() => {
                const s = item.solutions[Math.min(activeSol, item.solutions.length - 1)];
                return <Content format={s.format} language={s.language} content={s.content} />;
              })()}
            </>
          )}

          <label className="field">
            <span>Notes (optional)</span>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="What tripped you up?" />
          </label>

          <div className="grades">
            <button className="btn grade again" disabled={busy} onClick={() => grade("again")}>
              Again<small>{days(item.intervals.again)}</small>
            </button>
            <button className="btn grade hard" disabled={busy} onClick={() => grade("hard")}>
              Hard<small>{days(item.intervals.hard)}</small>
            </button>
            <button className="btn grade good" disabled={busy} onClick={() => grade("good")}>
              Good<small>{days(item.intervals.good)}</small>
            </button>
            <button className="btn grade easy" disabled={busy} onClick={() => grade("easy")}>
              Easy<small>{days(item.intervals.easy)}</small>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
