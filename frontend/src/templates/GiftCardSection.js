import { useEffect, useState } from "react";
import axios from "axios";
import { Gift, X, Copy, CheckCircle } from "@phosphor-icons/react";
import { useLanguage } from "../i18n/LanguageContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function GiftCardSection({ t, propertyId }) {
  const { t: tr } = useLanguage();
  const [cfg, setCfg] = useState(null);
  const [amount, setAmount] = useState(100);
  const [f, setF] = useState({ purchaser_name: "", purchaser_email: "", recipient_name: "", recipient_email: "", message: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    axios.get(`${API}/booking/gift-cards/config/${propertyId}`).then(({ data }) => { setCfg(data); setAmount(data.presets?.[1] || 100); }).catch(() => {});
    const p = new URLSearchParams(window.location.search);
    if (p.get("gift") === "success" && p.get("gift_id")) {
      axios.get(`${API}/booking/gift-cards/status/${p.get("gift_id")}?session_id=${p.get("session_id") || ""}`).then(({ data }) => setResult(data)).catch(() => {});
    }
  }, [propertyId]);

  if (!cfg?.enabled) return null;
  const sym = cfg.currency === "TRY" ? "₺" : cfg.currency === "EUR" ? "€" : cfg.currency === "USD" ? "$" : "£";
  const buy = async () => {
    setBusy(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/booking/gift-cards/purchase`, { property_id: propertyId, amount, ...f, origin_url: window.location.origin });
      if (data.url) window.location.href = data.url;
    } catch (e) { setErr(e.response?.data?.detail || "Hata"); } finally { setBusy(false); }
  };
  const inp = "w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:border-transparent";

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12" data-testid="gift-card-section" id="gift-cards">
      <div className="grid lg:grid-cols-[1fr_1.2fr] gap-8 items-start">
        <div>
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest mb-3" style={{ color: t.colors.accent }}><Gift size={16} weight="fill" /> {tr("gift.eyebrow")}</div>
          <h2 className="text-2xl sm:text-3xl font-semibold text-slate-900 mb-3" style={{ fontFamily: t.fonts.heading }}>{tr("gift.title", { name: cfg.property_name })}</h2>
          <p className="text-slate-600 text-sm leading-relaxed">{tr("gift.desc", { days: Math.round(cfg.expires_days / 30) })}</p>
          <div className="mt-6 p-6 text-white relative overflow-hidden" style={{ background: t.colors.primary, borderRadius: t.borderRadius }} aria-hidden="true">
            <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full opacity-20" style={{ background: t.colors.accent }} />
            <div className="text-xs uppercase tracking-widest opacity-70">{tr("gift.card")}</div>
            <div className="text-4xl font-bold mt-2">{sym}{amount}</div>
            <div className="text-sm mt-4 opacity-80">{cfg.property_name}</div>
            <div className="text-[11px] mt-1 opacity-60 font-mono">MHB-XXXX-XXXX-XXXX</div>
          </div>
        </div>
        <div className="bg-white border border-gray-200 p-6" style={{ borderRadius: t.borderRadius }}>
          <label className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 block">{tr("gift.amount")}</label>
          <div className="flex flex-wrap gap-2 mb-3">
            {cfg.presets.map((p) => (
              <button key={p} type="button" onClick={() => setAmount(p)} className="px-4 py-2 rounded-lg text-sm font-semibold border-2 transition-colors" style={{ borderColor: amount === p ? t.colors.accent : "#e5e7eb", background: amount === p ? `${t.colors.accent}10` : "transparent", color: amount === p ? t.colors.accent : "#334155", borderRadius: t.borderRadius }} data-testid={`gift-preset-${p}`}>{sym}{p}</button>
            ))}
            <input type="number" min={cfg.min} max={cfg.max} value={amount} onChange={(e) => setAmount(Number(e.target.value))} className="w-28 border border-gray-300 rounded-lg px-3 py-2 text-sm" aria-label={tr("gift.amount")} data-testid="gift-amount-input" />
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            <input className={inp} placeholder={tr("gift.yourName")} value={f.purchaser_name} onChange={(e) => setF({ ...f, purchaser_name: e.target.value })} data-testid="gift-purchaser-name" />
            <input className={inp} type="email" placeholder={tr("gift.yourEmail")} value={f.purchaser_email} onChange={(e) => setF({ ...f, purchaser_email: e.target.value })} data-testid="gift-purchaser-email" />
            <input className={inp} placeholder={tr("gift.recipientName")} value={f.recipient_name} onChange={(e) => setF({ ...f, recipient_name: e.target.value })} data-testid="gift-recipient-name" />
            <input className={inp} type="email" placeholder={tr("gift.recipientEmail")} value={f.recipient_email} onChange={(e) => setF({ ...f, recipient_email: e.target.value })} data-testid="gift-recipient-email" />
            <textarea className={`${inp} sm:col-span-2`} rows={2} placeholder={tr("gift.message")} value={f.message} onChange={(e) => setF({ ...f, message: e.target.value })} />
          </div>
          {err && <p className="text-xs text-red-500 mt-2" role="alert">{err}</p>}
          <button type="button" onClick={buy} disabled={busy || !f.purchaser_email} className="mt-4 w-full py-3 rounded-lg font-bold text-white text-sm disabled:opacity-50 flex items-center justify-center gap-2" style={{ background: t.colors.accent, borderRadius: t.borderRadius }} data-testid="gift-buy-btn">
            <Gift size={18} weight="fill" /> {tr("gift.buy", { amount: `${sym}${amount}` })}
          </button>
          <p className="text-[11px] text-slate-400 mt-2 text-center">{tr("gift.secure")}</p>
        </div>
      </div>
      {result && <GiftResultModal t={t} result={result} sym={sym} onClose={() => { setResult(null); window.history.replaceState({}, "", `${window.location.pathname}?property=${propertyId}`); }} />}
    </section>
  );
}

function GiftResultModal({ t, result, sym, onClose }) {
  const { t: tr } = useLanguage();
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard?.writeText(result.code || ""); setCopied(true); };
  return (
    <div className="fixed inset-0 z-[70] bg-black/50 flex items-center justify-center p-4" role="dialog" aria-modal="true" data-testid="gift-result-modal">
      <div className="bg-white max-w-md w-full p-8 text-center relative" style={{ borderRadius: t.borderRadius }}>
        <button onClick={onClose} className="absolute top-3 right-3 p-1 text-slate-400 hover:text-slate-700" aria-label="close" data-testid="gift-result-close"><X size={18} /></button>
        <CheckCircle size={48} weight="fill" className="mx-auto mb-3" style={{ color: t.colors.success }} />
        <h3 className="text-xl font-bold text-slate-900" style={{ fontFamily: t.fonts.heading }}>{result.status === "active" || result.status === "redeemed" ? tr("gift.ready") : tr("gift.pending")}</h3>
        <p className="text-sm text-slate-500 mt-1">{sym}{result.amount} {result.recipient_name ? `· ${result.recipient_name}` : ""}</p>
        {result.code && (
          <div className="mt-5 flex items-center justify-center gap-2">
            <code className="text-lg font-mono font-bold px-4 py-2 rounded-lg bg-slate-100" data-testid="gift-result-code">{result.code}</code>
            <button onClick={copy} className="p-2 rounded-lg border border-gray-200 hover:bg-slate-50" aria-label="copy" data-testid="gift-copy-btn">{copied ? <CheckCircle size={18} style={{ color: t.colors.success }} /> : <Copy size={18} />}</button>
          </div>
        )}
        <p className="text-xs text-slate-400 mt-4">{tr("gift.emailed")}</p>
      </div>
    </div>
  );
}
