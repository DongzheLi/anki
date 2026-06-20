import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "./api.js";
import ItemEditor from "./ItemEditor.jsx";
import Dialog from "./Dialog.jsx";
import MultiCombobox from "./MultiCombobox.jsx";

// Relative-time helper for "last practiced". Kept inline rather than pulling in
// a date library.
function ago(iso) {
  if (!iso) return "never";
  const secs = (Date.now() - new Date(iso + "Z").getTime()) / 1000;
  const day = 86400;
  if (secs < 3600) return `${Math.max(1, Math.round(secs / 60))}m`;
  if (secs < day) return `${Math.round(secs / 3600)}h`;
  return `${Math.round(secs / day)}d`;
}
const FEELING_EMOJI = { again: "😵", hard: "😬", good: "🙂", easy: "😎" };
const DIFFICULTIES = ["again", "hard", "good", "easy"]; // the four grades, fixed order
const parseTags = (s) => (s ? s.split(",").map((t) => t.trim()).filter(Boolean) : []);

// The dashboard is a single flat, filterable table of every item. You filter by
// free-text name plus typed multi-selects for category, tags, source, and
// difficulty. All filtering is client-side over the full item list.
export default function Dashboard() {
  const { stats } = useOutletContext();
  const [items, setItems] = useState([]);
  const [editor, setEditor] = useState(null); // { item } | { item: null }
  const [dialog, setDialog] = useState(null);

  // Filter state.
  const [q, setQ] = useState("");
  const [fCats, setFCats] = useState([]);
  const [fTopicTags, setFTopicTags] = useState([]);
  const [fSources, setFSources] = useState([]);
  const [fDiffs, setFDiffs] = useState([]);
  const [dueOnly, setDueOnly] = useState(false);

  const refresh = () => api.items().then(setItems);
  useEffect(() => { refresh(); }, []);

  // Distinct option lists, derived from the data. Topic options narrow to the
  // selected category so the two dropdowns stay coherent.
  const opts = useMemo(() => {
    const cats = [...new Set(items.map((i) => i.category_name))].sort();
    const selectedCats = new Set(fCats);
    const scopedItems = fCats.length ? items.filter((i) => selectedCats.has(i.category_name)) : items;
    const sources = [...new Set(items.map((i) => i.source).filter(Boolean))].sort();
    const topicTags = [...new Set(scopedItems.flatMap((i) => i.labels?.length ? i.labels : [i.topic_name, ...parseTags(i.tags)]).filter(Boolean))].sort();
    return { cats, topicTags, sources };
  }, [items, fCats]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return items.filter((it) => {
      if (dueOnly && !it.is_due) return false;
      if (fCats.length && !fCats.includes(it.category_name)) return false;
      if (fTopicTags.length) {
        const itemTopicTags = new Set(it.labels?.length ? it.labels : [it.topic_name, ...parseTags(it.tags)]);
        if (!fTopicTags.some((v) => itemTopicTags.has(v))) return false;
      }
      if (fSources.length && !fSources.includes(it.source || "")) return false;
      if (fDiffs.length && !fDiffs.includes(it.last_feeling || "")) return false;
      if (needle && !it.title.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [items, q, fCats, fTopicTags, fSources, fDiffs, dueOnly]);

  const clearFilters = () => {
    setQ("");
    setFCats([]);
    setFTopicTags([]);
    setFSources([]);
    setFDiffs([]);
    setDueOnly(false);
  };
  const anyFilter = q || fCats.length || fTopicTags.length || fSources.length || fDiffs.length || dueOnly;

  async function deleteItem(it) {
    const ok = await new Promise((resolve) =>
      setDialog({ spec: { mode: "confirm", title: `Delete "${it.title}"?`, danger: true, confirmLabel: "Delete" }, resolve: (v) => { setDialog(null); resolve(v); } })
    );
    if (ok) { await api.deleteItem(it.id); refresh(); }
  }

  const cards = [
    { l: "Due today", v: stats?.dueCount, cls: "due" },
    { l: "Reviews today", v: stats?.reviewsToday },
    { l: "Streak", v: stats != null ? `${stats.streak}d` : undefined },
    { l: "Total items", v: stats?.totalItems },
  ];

  return (
    <div className="dashboard">
      <div className="stat-strip">
        {cards.map((c) => (
          <span key={c.l} className={`stat ${c.cls || ""}`}>
            <b>{c.v ?? "—"}</b> {c.l}
          </span>
        ))}
      </div>

      {/* Filter bar — the SQL-GUI controls. */}
      <div className="filters">
        <input className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search items…" />
        <MultiCombobox value={fCats} onChange={(v) => { setFCats(v); setFTopicTags([]); }} options={opts.cats} placeholder="Categories" />
        <MultiCombobox value={fTopicTags} onChange={setFTopicTags} options={opts.topicTags} placeholder="Tags" />
        <MultiCombobox value={fSources} onChange={setFSources} options={opts.sources} placeholder="Sources" />
        <MultiCombobox value={fDiffs} onChange={setFDiffs} options={DIFFICULTIES} placeholder="Difficulty" />
        <label className="toggle">
          <input type="checkbox" checked={dueOnly} onChange={(e) => setDueOnly(e.target.checked)} /> Due only
        </label>
        {anyFilter && <button className="btn ghost sm" onClick={clearFilters}>Clear</button>}
        <div className="spacer" />
        <button className="btn primary" onClick={() => setEditor({ item: null })}>+ Item</button>
      </div>

      <div className="result-count">{rows.length} of {items.length} item{items.length === 1 ? "" : "s"}</div>

      <div className="table-wrap">
        <table className="data-table">
          <colgroup>
            <col className="col-item" />
            <col className="col-category" />
            <col className="col-topic-tags" />
            <col className="col-source" />
            <col className="col-due" />
            <col className="col-practiced" />
            <col className="col-difficulty" />
            <col className="col-last" />
            <col className="col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th>Item</th><th>Category</th><th>Tags</th><th>Source</th>
              <th>Due</th>
              <th className="num" title="number of times you've practiced this">Practiced</th>
              <th title="how it felt on your most recent review">Difficulty</th>
              <th title="when you last reviewed this">Last</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((it) => (
              <tr key={it.id} className={it.is_due ? "due" : ""}>
                <td className="cell-title">
                  <Link to={`/item/${it.id}`}>
                    {it.is_due && <span className="dot" title="due" />}
                    <span className="cell-title-text">{it.title}</span>
                  </Link>
                </td>
                <td className="muted">{it.category_name}</td>
                <td className="cell-topic-tags">
                  <div className="tag-list">
                    {(() => {
                      const ts = it.labels?.length ? it.labels : [it.topic_name, ...parseTags(it.tags)].filter(Boolean);
                      const shown = ts.slice(0, 3);
                      const extra = ts.length - shown.length;
                      return (
                        <>
                          {shown.map((t, i) => (
                            <button key={t} className={`tag-chip ${i === 0 ? "topic-chip" : ""}`} title={`filter by ${t}`} onClick={() => addUnique(setFTopicTags, t)}>{t}</button>
                          ))}
                          {extra > 0 && (
                            <span className="tag-more" title={ts.slice(3).join(", ")}>+{extra}</span>
                          )}
                        </>
                      );
                    })()}
                  </div>
                </td>
                <td className="muted cell-source">
                  {it.link ? (
                    <a href={it.link} target="_blank" rel="noreferrer" title={it.link}>
                      {it.source || "link"} ↗
                    </a>
                  ) : (
                    <span>{it.source || "—"}</span>
                  )}
                </td>
                <td className="muted">
                  {it.is_due ? <span className="due-now">due</span> : (it.due_date || "—")}
                </td>
                <td className="num muted">{it.practice_count}</td>
                <td className="cell-diff">
                  {it.last_feeling ? (
                    <button
                      className={`diff-chip ${it.last_feeling}`}
                      title={`filter by ${it.last_feeling}`}
                      onClick={() => addUnique(setFDiffs, it.last_feeling)}
                    >
                      {FEELING_EMOJI[it.last_feeling]} {it.last_feeling}
                    </button>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td className="muted cell-last">
                  {it.last_practiced ? `${ago(it.last_practiced)} ago` : "never"}
                </td>
                <td className="cell-actions">
                  <button className="btn xs ghost" onClick={() => setEditor({ item: it })}>edit</button>
                  <button className="btn xs danger" onClick={() => deleteItem(it)}>✕</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={9} className="empty-row muted">
                {items.length === 0 ? "No items yet — add one with + Item." : "No items match these filters."}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {editor && (
        <ItemEditor
          item={editor.item}
          onClose={() => setEditor(null)}
          onSaved={() => { setEditor(null); refresh(); }}
        />
      )}
      {dialog && <Dialog spec={dialog.spec} onClose={dialog.resolve} />}
    </div>
  );
}

function addUnique(setter, value) {
  if (!value) return;
  setter((arr) => arr.includes(value) ? arr : [...arr, value]);
}
