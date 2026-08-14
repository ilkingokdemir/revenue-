import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Broadcast, Megaphone, ArrowsClockwise } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function MarketingRadarPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [data, setData] = useState(null);
  const [hist, setHist] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actDates, setActDates] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/marketing-radar/${pid}?days=60`, { withCredentials: true });
      setData(r.data);
      const h = await axios.get(`${API}/api/marketing-radar/${pid}/history`, { withCredentials: true });
      setHist(h.data);
    } catch { toast.error("Radar taraması başarısız"); } finally { setBusy(false); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const activate = async (w) => {
    setActDates(w.start);
    try {
      const r = await axios.post(`${API}/api/marketing-radar/${pid}/activate`, { dates: w.dates }, { withCredentials: true });
      toast.success(`${r.data.campaign_dates.length} gece için kampanya aktifleşti — etki otomatik ölçülecek`);
    } catch { toast.error("Kampanya açılamadı"); } finally { setActDates(""); }
  };

  return (
    <div className="p-5 max-w-[1200px] mx-auto" data-testid="marketing-radar-panel">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-5">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Broadcast size={13} weight="fill" className="text-rose-500" /><span>Revenue × Pazarlama</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Pazarlama Fırsat Radarı</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">Önümüzdeki 60 günde düşük talepli tarih pencerelerini bulur, kampanya önerisi ve beklenen gelir etkisiyle pazarlamaya hazır iş çıkarır.</p>
        </div>
        <button onClick={load} disabled={busy} data-testid="mkt-radar-scan-btn"
          className="px-3 py-2 text-xs rounded-md bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50 inline-flex items-center gap-1.5 font-medium">
          <ArrowsClockwise size={13} className={busy ? "animate-spin" : ""} /> {busy ? "Taranıyor…" : "Yeniden Tara"}
        </button>
      </div>

      {data && (
        <>
          <div className="text-xs text-stone-500 mb-4" data-testid="mkt-radar-summary">
            {data.scanned_days} gün tarandı · {data.low_dates} düşük talepli gece · {data.windows.length} fırsat penceresi
          </div>
          {data.windows.length === 0 ? (
            <div className="bg-white border border-stone-200 rounded-xl p-8 text-center text-sm text-stone-500">Düşük talepli pencere bulunamadı — talep sağlıklı görünüyor. 🎉</div>
          ) : (
            <div className="space-y-3">
              {data.windows.map((w) => (
                <div key={w.start} className="bg-white border border-stone-200 rounded-xl p-4 flex flex-wrap items-center gap-4" data-testid={`mkt-window-${w.start}`}>
                  <div className="min-w-[160px]">
                    <div className="text-sm font-bold text-stone-900">{w.start}{w.nights > 1 ? ` → ${w.end}` : ""}</div>
                    <div className="text-[11px] text-stone-500">{w.nights} gece · ort. doluluk %{w.avg_occ} · {w.weekend ? "hafta sonu içerir" : "hafta içi"}</div>
                  </div>
                  <div className="flex-1 min-w-[240px] text-xs text-stone-700 flex items-start gap-1.5">
                    <Megaphone size={14} className="text-rose-500 shrink-0 mt-0.5" /> {w.suggested_campaign}
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-black text-emerald-700">+£{Number(w.est_revenue_roi).toLocaleString("tr-TR")}</div>
                    <div className="text-[10px] text-stone-400">beklenen gelir etkisi</div>
                  </div>
                  <button onClick={() => activate(w)} disabled={actDates === w.start} data-testid={`mkt-activate-${w.start}`}
                    className="px-3 py-2 text-xs font-bold rounded-lg bg-stone-900 text-white hover:bg-stone-700 disabled:opacity-50">
                    {actDates === w.start ? "Açılıyor…" : "Kampanyayı Aç"}
                  </button>
                </div>
              ))}
            </div>
          )}
          <p className="text-[10px] text-stone-400 mt-4">{data.note}</p>

          {hist && (
            <div className="bg-white border border-stone-200 rounded-xl p-4 mt-5" data-testid="radar-history">
              <div className="text-sm font-semibold text-stone-900 mb-1">Radar Geçmişi</div>
              <div className="text-[11px] text-stone-500 mb-3">
                {hist.scans.length} haftalık tarama · {hist.campaigns.length} radar kampanyası ·
                {" "}{hist.measured_count} ölçüldü{hist.total_pickup_gain > 0 ? ` · toplam +${hist.total_pickup_gain} oda pickup` : ""}
              </div>
              {hist.scans.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {hist.scans.map((s) => (
                    <span key={s.week} data-testid={`radar-scan-${s.week}`}
                      className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${s.windows > 0 ? "bg-rose-50 border-rose-200 text-rose-700" : "bg-emerald-50 border-emerald-200 text-emerald-700"}`}>
                      {s.week}: {s.windows > 0 ? `${s.windows} pencere` : "temiz"}
                    </span>
                  ))}
                </div>
              )}
              {hist.campaigns.length === 0 ? (
                <div className="text-[11px] text-stone-400">Radar üzerinden açılmış kampanya yok.</div>
              ) : (
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-stone-400 border-b border-stone-100">
                    <th className="py-1.5">Gece</th><th>Açılış</th><th className="text-right">OTB (açılışta)</th>
                    <th className="text-right">Sonuç</th>
                  </tr></thead>
                  <tbody>
                    {hist.campaigns.slice(0, 15).map((c) => (
                      <tr key={c.date} className="border-b border-stone-50" data-testid={`radar-camp-${c.date}`}>
                        <td className="py-1.5 font-semibold text-stone-700">{c.date}</td>
                        <td className="text-stone-500">{(c.applied_at || "").slice(0, 10)}</td>
                        <td className="text-right">{c.otb_at_apply ?? "—"}</td>
                        <td className="text-right">
                          {c.measured ? (
                            <span className={`font-bold ${(c.pickup_gain || 0) > 0 ? "text-emerald-700" : "text-stone-500"}`}>
                              {(c.pickup_gain || 0) > 0 ? `+${c.pickup_gain} oda` : "etkisiz"}
                            </span>
                          ) : <span className="text-stone-400">ölçülüyor…</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
