import { useEffect, useRef, useState } from "react";

// A small reusable modal that replaces the browser's native prompt()/confirm().
// Two modes:
//   - "text"    → a single text input (create / rename)
//   - "confirm" → a yes/no confirmation (delete)
//
// It's driven by a plain descriptor object and resolves a promise, so callers
// read like `const name = await ask({ mode: "text", ... })` — see Dashboard.
// Enter confirms, Escape cancels; the input autofocuses.
export default function Dialog({ spec, onClose }) {
  const isText = spec.mode === "text";
  const [value, setValue] = useState(spec.initial || "");
  const inputRef = useRef(null);

  useEffect(() => {
    if (isText) inputRef.current?.select();
  }, [isText]);

  const confirm = () => {
    if (isText && !value.trim()) return;
    onClose(isText ? value.trim() : true);
  };

  return (
    <div className="modal-backdrop" onClick={() => onClose(null)}>
      <div
        className="modal small"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Enter" && isText) confirm();
          if (e.key === "Escape") onClose(null);
        }}
      >
        <h2>{spec.title}</h2>
        {spec.message && <p className="dialog-msg">{spec.message}</p>}
        {isText && (
          <input
            ref={inputRef}
            value={value}
            placeholder={spec.placeholder}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
          />
        )}
        <div className="modal-actions">
          <button className="btn ghost" onClick={() => onClose(null)}>Cancel</button>
          <button
            className={`btn ${spec.danger ? "danger-solid" : "primary"}`}
            onClick={confirm}
          >
            {spec.confirmLabel || (isText ? "Save" : "Confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
