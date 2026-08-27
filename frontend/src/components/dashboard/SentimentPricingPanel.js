import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Heart } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;

export default function SentimentPricingPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [themes, setThemes] = useState(null);
  const [themesBusy, setThemesBusy] = useState(false);

  async function analyzeThemes() {
    setThemesBusy(true);
    try {
      const r = await axios.post(`${B}/api/sentiment-pricing/${pid}/analyze-themes`);
      setThemes(r.data);
      toast.success(`${r.data.reviews_analyzed} yorum tema bazında analiz edildi`);
    } catch (e) { toast.error(e.response?.data?.detail || "Tema analizi başarısız"); }
    setThemesBusy(false);
  }

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${B}/api/sentiment-pricing/${pid}`);
      setData(r.data);
    } catch { toast.error("Sentiment verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function apply() {
    if (!window.confirm(`${data.suggested_adj_pct > 0 ? "+" : ""}${data.suggested_adj_pct}% sentiment ayarı önümüzdeki 30 güne uygulanacak. Onaylıyor musunuz?`)) return;
    setBusy(true);
    try {
      const r = await axios.post(`${B}/api/sentiment-pricing/${pid}/apply`, {});
      toast.success(`Uygulandı — ${r.data.written} hücre yazıldı, ${r.data.skipped} korundu`); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Uygulanamadı"); }
    setBusy(false);
  }

  if (!data) return <p className="p-5 text-sm text-stone-400" data-testid="sentiment-loading">Yorum duyarlılığı hesaplanıyor…</p>;
  const idx = data.index;

  return (
    <div className="p-5 max-w-[1000px] mx-auto space-y-4" data-testid="sentiment-pricing-panel">
      <div className="bg-gradient-to-br from-rose-950 via-stone-900 to-stone-950 rounded-2xl p-6 text-white">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Heart size={22} className="text-rose-400" /> Sosyal Sentiment Fiyat Katmanı
        </h1>
        <p className="text-sm text-stone-300 mt-1">Misafir yorumlarının duyarlılığı talep sinyali olarak fiyat motoruna beslenir (Duetto paritesi).</p>
        {idx == null ? <p className="mt-4 text-sm text-stone-400" data-testid="sentiment-empty">Son 90 günde yorum verisi yok.</p> : (
          <div className="flex flex-wrap items-center gap-8 mt-4">
            <div data-testid="sentiment-index">
              <div className={`text-4xl font-black ${idx >= 70 ? "text-emerald-400" : idx >= 45 ? "text-amber-300" : "text-rose-400"}`}>{idx}</div>
              <div className="text-xs text-stone-400">sentiment endeksi / 100</div>
            </div>
            <div>
              <div className="text-2xl font-bold">{data.avg_rating}★ <span className={`text-sm ${data.trend >= 0 ? "text-emerald-400" : "text-rose-400"}`}>{data.trend >= 0 ? "▲" : "▼"} {Math.abs(data.trend)}</span></div>
              <div className="text-xs text-stone-400">{data.reviews_90d} yorum (90g) · {data.reviews_30d} son 30g</div>
            </div>
            <div data-testid="sentiment-signal" className="flex-1 min-w-[220px]">
              <div className="text-sm font-semibold text-rose-200">{data.signal}</div>
              {data.suggested_adj_pct !== 0 && (
                <button onClick={apply} disabled={busy} data-testid="sentiment-apply-btn"
                  className="mt-2 px-4 py-2 rounded-full bg-rose-500 text-white text-xs font-bold disabled:opacity-50">
                  {data.suggested_adj_pct > 0 ? "+" : ""}{data.suggested_adj_pct}% Fiyata Uygula (30 gün)
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="sentiment-themes-card">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">🧠 AI Tema Analizi (temizlik · personel · konum...)</h2>
          <button onClick={analyzeThemes} disabled={themesBusy} data-testid="sentiment-themes-btn"
            className="px-4 py-1.5 rounded-full bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">
            {themesBusy ? "Analiz ediliyor…" : "AI ile Analiz Et"}
          </button>
        </div>
        {themes && (
          <div className="mt-3" data-testid="sentiment-themes-result">
            <div className="flex flex-wrap gap-2">
              {themes.themes.map((t, i) => (
                <div key={i} data-testid={`sentiment-theme-${t.theme}`}
                  className={`rounded-xl border px-3 py-2 ${t.score >= 70 ? "bg-emerald-50 border-emerald-200" : t.score >= 45 ? "bg-amber-50 border-amber-200" : "bg-rose-50 border-rose-200"}`}>
                  <div className="text-xs font-bold capitalize">{t.theme} <span className="font-black">{t.score}</span>/100</div>
                  <div className="text-[10px] text-stone-500">{t.mentions} bahis · {t.summary}</div>
                </div>
              ))}
            </div>
            <p className="text-xs text-indigo-700 bg-indigo-50 rounded-lg p-2.5 mt-3" data-testid="sentiment-pricing-note">💡 {themes.pricing_note}</p>
          </div>
        )}
        {!themes && <p className="text-xs text-stone-400 mt-2">Son 90 günün yorum metinleri yapay zekâ ile tema bazında puanlanır ve fiyat gücüne etkisi yorumlanır.</p>}
      </div>

      {data.risk_reviews?.length > 0 && (        <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="sentiment-risk-card">
          <h2 className="text-base font-semibold mb-2">⚠️ Fiyat gücünü zayıflatan son yorumlar</h2>
          {data.risk_reviews.map((r, i) => (
            <div key={i} className="border-t border-stone-100 py-2 text-sm">
              <b>{r.rating}★ {r.guest}</b> <span className="text-[10px] text-stone-400">{r.platform}</span>
              <p className="text-stone-500 text-xs mt-0.5">{r.text}</p>
            </div>
          ))}
        </div>
      )}

      {data.applies?.length > 0 && (
        <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="sentiment-applies-card">
          <h2 className="text-base font-semibold mb-2">Uygulama geçmişi</h2>
          {data.applies.map((a) => (
            <div key={a.id} className="text-xs text-stone-500 py-1 border-t border-stone-100">
              {a.created_at?.slice(0, 16).replace("T", " ")} — endeks {a.index}, {a.adj_pct > 0 ? "+" : ""}{a.adj_pct}% · {a.written} hücre · {a.by}
            </div>
          ))}
        </div>
      )}
      <p className="text-[11px] text-stone-400">{data.note}</p>
    </div>
  );
}
