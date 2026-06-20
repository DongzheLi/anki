import { useEffect, useRef, useState } from "react";

// A real dropdown combobox: click to open the full list, type to filter, click
// an option to pick it — and if what you've typed isn't an existing option, a
// "Create …" row lets you add it. This replaces the native <datalist>, whose
// behaviour and styling we couldn't control.
export default function Combobox({ value, onChange, options, placeholder }) {
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0); // highlighted index
  const ref = useRef(null);

  // Close when clicking outside the component.
  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  // Filter by the current text. An exact match shows the full list (so you can
  // still switch away after selecting); otherwise we substring-filter.
  const q = value.trim().toLowerCase();
  const exact = options.some((o) => o.toLowerCase() === q);
  const filtered = !q || exact ? options : options.filter((o) => o.toLowerCase().includes(q));
  const showCreate = value.trim() && !exact;

  const choose = (val) => { onChange(val); setOpen(false); };

  function onKey(e) {
    if (e.key === "Escape") return setOpen(false);
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setHi((h) => Math.min(h + 1, filtered.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    if (e.key === "Enter" && open) {
      e.preventDefault();
      if (filtered[hi]) choose(filtered[hi]);
      else setOpen(false);
    }
  }

  return (
    <div className="combobox" ref={ref}>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => { onChange(e.target.value); setOpen(true); setHi(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
      />
      <button type="button" className="combo-caret" tabIndex={-1} onClick={() => setOpen((o) => !o)}>▾</button>
      {open && (filtered.length > 0 || showCreate) && (
        <ul className="combo-list">
          {filtered.map((o, i) => (
            <li
              key={o}
              className={`combo-opt ${i === hi ? "hi" : ""} ${o === value ? "sel" : ""}`}
              onMouseEnter={() => setHi(i)}
              onMouseDown={(e) => { e.preventDefault(); choose(o); }}
            >
              {o}
            </li>
          ))}
          {showCreate && (
            <li className="combo-opt create" onMouseDown={(e) => { e.preventDefault(); choose(value.trim()); }}>
              Create “{value.trim()}”
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
