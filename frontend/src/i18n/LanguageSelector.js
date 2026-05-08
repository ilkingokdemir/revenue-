import { useState, useRef, useEffect } from "react";
import { GlobeSimple, CaretDown, Check } from "@phosphor-icons/react";
import { useLanguage } from "./LanguageContext";

export function LanguageSelector({ variant = "header" }) {
  const { lang, setLang, languages } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const current = languages.find((l) => l.code === lang) || languages[0];

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  if (variant === "minimal") {
    return (
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1.5 text-sm font-medium px-2 py-1 rounded-md hover:bg-white/10 transition-colors"
          data-testid="language-selector"
          aria-label="Select language"
        >
          <GlobeSimple size={16} />
          <span>{current.code.toUpperCase()}</span>
          <CaretDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-xl border border-gray-200 py-1 min-w-[180px] z-50 max-h-[320px] overflow-y-auto" data-testid="language-dropdown">
            {languages.map((l) => (
              <button
                key={l.code}
                onClick={() => { setLang(l.code); setOpen(false); }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${l.code === lang ? "bg-gray-50 font-semibold" : ""}`}
                data-testid={`lang-option-${l.code}`}
              >
                <span className="text-base">{l.flag}</span>
                <span className="text-slate-800 flex-1 text-left">{l.label}</span>
                {l.code === lang && <Check size={14} weight="bold" className="text-emerald-600" />}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Default header variant
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-sm px-2.5 py-1.5 rounded-lg border border-white/20 hover:bg-white/10 transition-colors"
        data-testid="language-selector"
        aria-label="Select language"
      >
        <GlobeSimple size={15} />
        <span className="hidden sm:inline">{current.label}</span>
        <span className="sm:hidden">{current.code.toUpperCase()}</span>
        <CaretDown size={12} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-xl border border-gray-200 py-1 min-w-[200px] z-50 max-h-[360px] overflow-y-auto" data-testid="language-dropdown">
          {languages.map((l) => (
            <button
              key={l.code}
              onClick={() => { setLang(l.code); setOpen(false); }}
              className={`w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm hover:bg-gray-50 transition-colors ${l.code === lang ? "bg-blue-50 font-semibold" : ""}`}
              data-testid={`lang-option-${l.code}`}
            >
              <span className="text-base">{l.flag}</span>
              <span className="text-slate-800 flex-1 text-left">{l.label}</span>
              {l.code === lang && <Check size={14} weight="bold" className="text-blue-600" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
