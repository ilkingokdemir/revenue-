import { useState, useRef, useEffect } from "react";
import { useTranslation, LANGUAGES } from "@/i18n";

export function LanguageSwitcher({ compact = false }) {
  const { lang, setLang, t } = useTranslation();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const current = LANGUAGES.find(l => l.code === lang) || LANGUAGES[0];

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div className="relative" ref={ref} data-testid="language-switcher">
      <button
        onClick={() => setOpen(!open)}
        className={compact
          ? "flex items-center gap-1.5 px-2 py-1 rounded-lg hover:bg-stone-700/50 transition text-stone-300 text-xs"
          : "flex items-center gap-2 px-3 py-2 rounded-xl border border-stone-200 hover:bg-stone-50 transition text-sm text-stone-700"
        }
        data-testid="language-switcher-btn"
      >
        <span className="text-base">{current.flag}</span>
        {!compact && <span className="font-medium">{current.name}</span>}
        <svg className={`w-3 h-3 transition-transform ${open ? "rotate-180" : ""} ${compact ? "text-stone-400" : "text-stone-500"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
      </button>

      {open && (
        <div className={`absolute z-[100] mt-1 ${compact ? "left-0 bottom-full mb-1" : "right-0"} bg-white rounded-xl shadow-xl border border-stone-200 py-1 min-w-[180px] max-h-[300px] overflow-y-auto`} data-testid="language-dropdown">
          {LANGUAGES.map(l => (
            <button
              key={l.code}
              onClick={() => { setLang(l.code); setOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2 text-sm hover:bg-stone-50 transition ${lang === l.code ? "bg-stone-50 font-semibold text-stone-800" : "text-stone-600"}`}
              data-testid={`lang-option-${l.code}`}
            >
              <span className="text-lg">{l.flag}</span>
              <span>{l.name}</span>
              {lang === l.code && (
                <svg className="w-4 h-4 text-emerald-500 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
