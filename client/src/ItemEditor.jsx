import { useEffect, useState } from "react";
import { api } from "./api.js";
import Combobox from "./Combobox.jsx";
import MultiCombobox from "./MultiCombobox.jsx";

// Maps file extensions to (format, highlight.js language) for uploaded files.
const EXT_MAP = {
  py: ["code", "python"], js: ["code", "javascript"], jsx: ["code", "javascript"],
  ts: ["code", "typescript"], tsx: ["code", "typescript"], java: ["code", "java"],
  c: ["code", "c"], h: ["code", "c"], cpp: ["code", "cpp"], cc: ["code", "cpp"],
  go: ["code", "go"], rs: ["code", "rust"], rb: ["code", "ruby"], sql: ["code", "sql"],
  sh: ["code", "bash"], kt: ["code", "kotlin"], swift: ["code", "swift"],
  md: ["markdown", null], markdown: ["markdown", null], txt: ["text", null],
};

const parseTags = (s) => (s ? s.split(",").map((t) => t.trim()).filter(Boolean) : []);

let KEY = 1; // stable React keys for the editable solution rows
const blankSolution = () => ({ _key: KEY++, format: "code", language: "python", content: "", source_filename: null });

// A modal for creating or editing an item. Category is typed, tags are a typed
// multi-select, and an item can carry several solutions.
export default function ItemEditor({ item, onClose, onSaved }) {
  const editing = !!item;
  const [taxonomy, setTaxonomy] = useState([]);
  const [category, setCategory] = useState(item?.category_name || "");
  const [labels, setLabels] = useState(item?.labels?.length ? item.labels : parseTags(item?.tags));
  const [title, setTitle] = useState(item?.title || "");
  const [link, setLink] = useState(item?.link || "");
  const [source, setSource] = useState(item?.source || "");
  const [description, setDescription] = useState(item?.description || "");
  const [solutions, setSolutions] = useState(
    item?.solutions?.length
      ? item.solutions.map((s) => ({ _key: KEY++, ...s }))
      : [blankSolution()]
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.taxonomy().then(setTaxonomy); }, []);

  const categoryNames = Array.isArray(taxonomy) ? taxonomy.map((c) => c.name) : taxonomy.categories || [];
  const labelNames = Array.isArray(taxonomy)
    ? [...new Set(taxonomy.flatMap((c) => c.topics || []))]
    : taxonomy.labels || [];

  const patchSolution = (i, patch) =>
    setSolutions((arr) => arr.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const addSolution = () => setSolutions((arr) => [...arr, blankSolution()]);
  const removeSolution = (i) => setSolutions((arr) => arr.filter((_, j) => j !== i));

  // Upload a file into a specific solution row, inferring its format/language.
  function onFile(i, e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const ext = file.name.split(".").pop()?.toLowerCase();
    const [fmt, lang] = EXT_MAP[ext] || ["code", null];
    const reader = new FileReader();
    reader.onload = () => {
      patchSolution(i, {
        content: String(reader.result),
        format: fmt,
        language: lang || (fmt === "code" ? "" : null),
        source_filename: file.name,
      });
      if (!title.trim()) setTitle(file.name.replace(/\.[^.]+$/, ""));
    };
    reader.readAsText(file);
  }

  const valid = title.trim() && category.trim();

  async function save() {
    if (!valid) return;
    setBusy(true);
    const payload = {
      category, labels, title,
      link: link.trim() || null,
      source: source.trim() || null,
      description,
      solutions: solutions.map((s) => ({
        format: s.format,
        language: s.format === "code" ? s.language : null,
        content: s.content,
        source_filename: s.source_filename,
      })),
    };
    try {
      if (editing) await api.updateItem(item.id, payload);
      else await api.addItem(payload);
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{editing ? "Edit item" : "New item"}</h2>

        <div className="row">
          <label className="field">
            <span>Category</span>
            <Combobox value={category} onChange={(v) => { setCategory(v); }} options={categoryNames} placeholder="e.g. leetcode" />
          </label>
          <label className="field">
            <span>Tags</span>
            <MultiCombobox value={labels} onChange={setLabels} options={labelNames} placeholder="e.g. dfs, tree" allowCreate />
          </label>
        </div>

        <label className="field">
          <span>Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Container With Most Water" autoFocus />
        </label>

        {/* Source + link are one concept in the UI: the source name, made
            clickable when a link is supplied. */}
        <div className="row">
          <label className="field">
            <span>Source (optional)</span>
            <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="e.g. NeetCode 150" />
          </label>
          <label className="field">
            <span>Link (optional — makes the source clickable)</span>
            <input value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://leetcode.com/problems/…" type="url" />
          </label>
        </div>

        <label className="field">
          <span>Problem description — the card front (markdown)</span>
          <textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder="What's the problem? This is what you'll see before revealing the solution." />
        </label>

        {/* Solutions — one item may hold several (different languages, notes…). */}
        <div className="solutions-head">
          <span>Solutions</span>
          <button type="button" className="btn sm" onClick={addSolution}>+ Add solution</button>
        </div>
        {solutions.map((s, i) => (
          <div className="solution-edit" key={s._key}>
            <div className="solution-bar">
              <select value={s.format} onChange={(e) => patchSolution(i, { format: e.target.value })}>
                <option value="code">Code</option>
                <option value="markdown">Markdown</option>
                <option value="text">Text</option>
              </select>
              {s.format === "code" && (
                <input className="lang-input" value={s.language || ""} placeholder="language"
                  onChange={(e) => patchSolution(i, { language: e.target.value })} />
              )}
              <input type="file" className="sol-file" onChange={(e) => onFile(i, e)} />
              <div className="spacer" />
              {solutions.length > 1 && (
                <button type="button" className="btn xs danger" onClick={() => removeSolution(i)}>remove</button>
              )}
            </div>
            <textarea className="code-input" rows={10} value={s.content}
              onChange={(e) => patchSolution(i, { content: e.target.value })}
              placeholder={s.source_filename ? `from ${s.source_filename}` : "Paste solution code or notes…"} />
          </div>
        ))}

        <div className="modal-actions">
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={save} disabled={busy || !valid}>
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
