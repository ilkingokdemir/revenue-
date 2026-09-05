import { useEffect, useState } from "react";
import axios from "axios";
import { X, Tag, Cookie } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function ExitIntentPopup({ t, propertyId, active, onApply }) {
  const { t: tr } = useLanguage();
  const [cfg, setCfg] = useState(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    axios.get(`${API}/booking/exit-intent/${propertyId}`).then(({ data }) => data.enabled && setCfg(data)).catch(() => {});
  }, [propertyId]);

  useEffect(() => {
    if (!cfg || !active) return;
    let armed = false;
    const timer = setTimeout(() => { armed = true; }, (cfg.delay_sec || 8) * 1000);
    const fire = () => {
      if (!armed || sessionStorage.getItem("mhb_exit_shown")) return;
      sessionStorage.setItem("mhb_exit_shown", "1");
      setShow(true);
      axios.post(`${API}/booking/exit-intent/${propertyId}/shown`).catch(() => {});
    };
    const onLeave = (e) => { if (e.clientY <= 0) fire(); };
    const onVis = () => { if (document.visibilityState === "hidden") fire(); };
    document.addEventListener("mouseout", onLeave);
    document.addEventListener("visibilitychange", onVis);
    return () => { clearTimeout(timer); document.removeEventListener("mouseout", onLeave); document.removeEventListener("visibilitychange", onVis); };
  }, [cfg, active, propertyId]);

  if (!show || !cfg) return null;
  const body = (cfg.body || "").replace("{pct}", cfg.discount_pct);
  return (
    <div className="fixed inset-0 z-[80] bg-black/60 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="exit-title" data-testid="exit-intent-popup">
      <div className="bg-white max-w-md w-full overflow-hidden relative animate-in zoom-in-95" style={{ borderRadius: t.borderRadius }}>
        <button onClick={() => setShow(false)} className="absolute top-3 right-3 p-1.5 rounded-full bg-white/80 text-slate-500 hover:text-slate-900 z-10" aria-label="close" data-testid="exit-intent-close"><X size={18} /></button>
        <div className="p-8 text-white text-center" style={{ background: t.colors.primary }}>
          <Tag size={40} weight="fill" className="mx-auto mb-3" style={{ color: t.colors.accent }} />
          <h3 id="exit-title" className="text-2xl font-bold" style={{ fontFamily: t.fonts.heading }}>{cfg.title}</h3>
          <p className="text-sm opacity-80 mt-2">{body}</p>
        </div>
        <div className="p-6 text-center">
          <div className="text-xs uppercase tracking-widest text-slate-400 mb-2">{tr("exit.yourCode")}</div>
          <code className="inline-block text-2xl font-mono font-bold px-5 py-2 rounded-lg border-2 border-dashed" style={{ borderColor: t.colors.accent, color: t.colors.accent }} data-testid="exit-intent-code">{cfg.code}</code>
          <button onClick={() => { onApply(cfg.code); setShow(false); }} className="mt-5 w-full py-3 rounded-lg font-bold text-white text-sm" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="exit-intent-apply">
            {tr("exit.apply", { pct: cfg.discount_pct })}
          </button>
          <button onClick={() => setShow(false)} className="mt-2 text-xs text-slate-400 hover:underline">{tr("exit.noThanks")}</button>
        </div>
      </div>
    </div>
  );
}

export function CookieBanner({ accent = "#0f172a", radius = "12px" }) {
  const [show, setShow] = useState(() => { try { return !localStorage.getItem("mhb_cookie_consent"); } catch { return false; } });
  const { t: tr } = useLanguage();
  const set = (v) => { try { localStorage.setItem("mhb_cookie_consent", v); } catch { /* ignore */ } setShow(false); };
  if (!show) return null;
  return (
    <div className="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-6 sm:max-w-sm z-[60] bg-white border border-gray-200 shadow-2xl p-4 flex gap-3" role="region" aria-label="cookie consent" data-testid="cookie-banner" style={{ borderRadius: radius }}>
      <Cookie size={28} className="flex-shrink-0 text-amber-500" weight="fill" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-slate-600 leading-relaxed">{tr("cookie.text")}</p>
        <div className="flex gap-2 mt-3">
          <button onClick={() => set("all")} className="px-3 py-1.5 text-xs font-bold text-white rounded-lg" style={{ background: accent, borderRadius: radius }} data-testid="cookie-accept">{tr("cookie.accept")}</button>
          <button onClick={() => set("essential")} className="px-3 py-1.5 text-xs font-semibold text-slate-600 border border-gray-200 rounded-lg" style={{ borderRadius: radius }} data-testid="cookie-essential">{tr("cookie.essential")}</button>
        </div>
      </div>
    </div>
  );
}
