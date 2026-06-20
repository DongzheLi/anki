import { useEffect, useRef, useState } from "react";

export default function MultiCombobox({ value, onChange, options, placeholder, allowCreate = false }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hi, setHi] = useState(0);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const selected = new Set(value);
  const q = query.trim().toLowerCase();
  const filtered = options.filter((o) => !selected.has(o) && (!q || o.toLowerCase().includes(q)));
  const exact = options.some((o) => o.toLowerCase() === q) || value.some((o) => o.toLowerCase() === q);
  const createOption = allowCreate && query.trim() && !exact ? query.trim() : null;
  const visible = createOption ? [createOption, ...filtered].slice(0, 20) : filtered.slice(0, 20);

  const choose = (option) => {
    if (!option) return;
    onChange(value.includes(option) ? value : [...value, option]);
    setQuery("");
    setHi(0);
    setOpen(true);
  };
  const remove = (option) => onChange(value.filter((v) => v !== option));

  function onKey(e) {
    if (e.key === "Escape") return setOpen(false);
    if (e.key === "Backspace" && !query && value.length) {
      e.preventDefault();
      return onChange(value.slice(0, -1));
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      return setHi((h) => Math.min(h + 1, visible.length - 1));
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      return setHi((h) => Math.max(h - 1, 0));
    }
    if (e.key === "Enter" && open) {
      e.preventDefault();
      return choose(visible[hi]);
    }
  }

  return (
    <div className="multi-select" ref={ref}>
      <div className="multi-input" onMouseDown={() => setOpen(true)}>
        {value.map((v) => (
          <button key={v} type="button" className="multi-chip" onClick={(e) => { e.stopPropagation(); remove(v); }}>
            {v}<span aria-hidden="true">x</span>
          </button>
        ))}
        <input
          value={query}
          placeholder={value.length ? "" : placeholder}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setHi(0); }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
        />
      </div>
      {open && visible.length > 0 && (
        <ul className="combo-list multi-list">
          {visible.map((o, i) => (
            <li
              key={`${o}-${i}`}
              className={`combo-opt ${i === hi ? "hi" : ""} ${createOption && i === 0 ? "create" : ""}`}
              onMouseEnter={() => setHi(i)}
              onMouseDown={(e) => { e.preventDefault(); choose(o); }}
            >
              {createOption && i === 0 ? `Create "${o}"` : o}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
