import { createContext, useContext, useState, useCallback } from "react";
import translations, { SUPPORTED_LANGUAGES, RTL_LANGUAGES } from "./translations";

const LanguageContext = createContext();

export function LanguageProvider({ children, defaultLang }) {
  const [lang, setLangState] = useState(() => {
    // Check URL param first, then localStorage, then default
    const params = new URLSearchParams(window.location.search);
    const urlLang = params.get("lang");
    if (urlLang && translations[urlLang]) return urlLang;
    const stored = localStorage.getItem("booking_lang");
    if (stored && translations[stored]) return stored;
    return defaultLang || "en";
  });

  const setLang = useCallback((code) => {
    if (translations[code]) {
      setLangState(code);
      localStorage.setItem("booking_lang", code);
      // Update URL param without reload
      const url = new URL(window.location);
      url.searchParams.set("lang", code);
      window.history.replaceState({}, "", url);
    }
  }, []);

  const t = useCallback((key, params) => {
    let text = translations[lang]?.[key] || translations.en[key] || key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(`{${k}}`, v);
      });
    }
    return text;
  }, [lang]);

  const isRTL = RTL_LANGUAGES.includes(lang);

  return (
    <LanguageContext.Provider value={{ lang, setLang, t, isRTL, languages: SUPPORTED_LANGUAGES }}>
      {children}
    </LanguageContext.Provider>
  );
}

export const useLanguage = () => {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within a LanguageProvider");
  return ctx;
};
