import { createContext, useContext, useState, useEffect, useCallback } from "react";
import en from "./en.json";
import tr from "./tr.json";
import es from "./es.json";
import ru from "./ru.json";
import ar from "./ar.json";
import fr from "./fr.json";
import de from "./de.json";

const translations = { en, tr, es, ru, ar, fr, de };

export const LANGUAGES = [
  { code: "en", name: "English", flag: "🇬🇧", dir: "ltr" },
  { code: "tr", name: "Türkçe", flag: "🇹🇷", dir: "ltr" },
  { code: "es", name: "Español", flag: "🇪🇸", dir: "ltr" },
  { code: "ru", name: "Русский", flag: "🇷🇺", dir: "ltr" },
  { code: "ar", name: "العربية", flag: "🇸🇦", dir: "rtl" },
  { code: "fr", name: "Français", flag: "🇫🇷", dir: "ltr" },
  { code: "de", name: "Deutsch", flag: "🇩🇪", dir: "ltr" },
];

const LanguageContext = createContext();

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem("mhb_lang") || "en");

  const changeLang = useCallback((code) => {
    setLang(code);
    localStorage.setItem("mhb_lang", code);
    const l = LANGUAGES.find(l => l.code === code);
    if (l) document.documentElement.dir = l.dir;
  }, []);

  useEffect(() => {
    const l = LANGUAGES.find(l => l.code === lang);
    if (l) document.documentElement.dir = l.dir;
  }, [lang]);

  const t = useCallback((key, params) => {
    const dict = translations[lang] || translations.en;
    let text = dict[key] || translations.en[key] || key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(`{${k}}`, v);
      });
    }
    return text;
  }, [lang]);

  return (
    <LanguageContext.Provider value={{ lang, setLang: changeLang, t, LANGUAGES }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  return useContext(LanguageContext);
}
