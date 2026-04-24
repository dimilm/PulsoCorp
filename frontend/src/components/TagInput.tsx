import { KeyboardEvent, useMemo, useRef, useState } from "react";
import { tagColorClass } from "../lib/tagColor";

interface TagInputProps {
  value: string[];
  onChange: (next: string[]) => void;
  suggestions?: { name: string; count?: number }[];
  placeholder?: string;
  id?: string;
}

function normalizeTag(raw: string): string {
  return raw.trim().toLowerCase().slice(0, 32);
}

export function TagInput({
  value,
  onChange,
  suggestions = [],
  placeholder = "Tag hinzufügen…",
  id,
}: TagInputProps) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const query = text.trim();

  const filteredSuggestions = useMemo(() => {
    const q = query.toLowerCase();
    const selected = new Set(value);
    return suggestions
      .filter((s) => !selected.has(s.name))
      .filter((s) => (q ? s.name.includes(q) : true))
      .slice(0, 8);
  }, [query, value, suggestions]);

  function addTag(raw: string) {
    const norm = normalizeTag(raw);
    if (!norm) return;
    if (value.includes(norm)) {
      setText("");
      return;
    }
    onChange([...value, norm]);
    setText("");
    setActiveIndex(0);
  }

  function removeTag(name: string) {
    onChange(value.filter((t) => t !== name));
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === "," || e.key === "Tab") {
      if ((e.key === "Enter" || e.key === "Tab") && focused && filteredSuggestions.length > 0 && query) {
        e.preventDefault();
        addTag(filteredSuggestions[activeIndex]?.name ?? query);
        return;
      }
      if (query) {
        e.preventDefault();
        addTag(query);
      }
      return;
    }
    if (e.key === "Backspace" && text === "" && value.length > 0) {
      e.preventDefault();
      removeTag(value[value.length - 1]);
      return;
    }
    if (e.key === "ArrowDown") {
      if (filteredSuggestions.length === 0) return;
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % filteredSuggestions.length);
      return;
    }
    if (e.key === "ArrowUp") {
      if (filteredSuggestions.length === 0) return;
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + filteredSuggestions.length) % filteredSuggestions.length);
      return;
    }
    if (e.key === "Escape") {
      setText("");
    }
  }

  const showSuggestions = focused && (filteredSuggestions.length > 0 || query.length > 0);

  return (
    <div
      className={`tag-input-wrap ${focused ? "is-focused" : ""}`.trim()}
      onClick={() => inputRef.current?.focus()}
    >
      {value.map((t) => (
        <span key={t} className={`tag-pill ${tagColorClass(t)}`.trim()}>
          {t}
          <button
            type="button"
            className="tag-pill-remove"
            aria-label={`Tag ${t} entfernen`}
            onClick={(e) => {
              e.stopPropagation();
              removeTag(t);
            }}
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        id={id}
        className="tag-input-field"
        value={text}
        placeholder={value.length === 0 ? placeholder : ""}
        onChange={(e) => {
          setText(e.target.value);
          setActiveIndex(0);
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 120)}
        onKeyDown={onKeyDown}
        autoComplete="off"
      />
      {showSuggestions && (
        <div className="tag-suggestions" role="listbox">
          <div className="tag-suggestions-hint">
            {query
              ? "Bestehende Tags waehlen oder mit Enter neuen Tag erstellen"
              : "Vorschlaege: Pfeiltasten nutzen, mit Enter oder Tab uebernehmen"}
          </div>
          {filteredSuggestions.map((s, idx) => (
            <button
              key={s.name}
              type="button"
              role="option"
              aria-selected={idx === activeIndex}
              className={`tag-suggestion ${idx === activeIndex ? "tag-suggestion-active" : ""}`.trim()}
              onMouseDown={(e) => {
                e.preventDefault();
                addTag(s.name);
              }}
              onMouseEnter={() => setActiveIndex(idx)}
            >
              <span className={`tag-pill tag-pill-sm ${tagColorClass(s.name)}`}>{s.name}</span>
              {typeof s.count === "number" && s.count > 0 && (
                <span className="tag-suggestion-count">{s.count}</span>
              )}
            </button>
          ))}
          {filteredSuggestions.length === 0 && query && (
            <div className="tag-suggestion-empty">
              Kein passender Tag gefunden. Mit Enter wird "{query}" neu erstellt.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default TagInput;
