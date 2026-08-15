import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Coins, MoonStars, UsersThree, TrendUp } from "@phosphor-icons/react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer, Legend } from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;

const MetricCard = ({ label, value, sub, testId }) => (
  <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid={testId}>
    <div className="text-[11px] uppercase tracking-[0.15em] text-stone-500 font-bold">{label}</div>
    <div className="text-2xl font-black text-stone-900 mt-1">{value}</div>
    <div className="text-[11px] text-stone-500 mt-1">{sub}</div>
  </div>
);

export default function LosWashMetricsPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [los, setLos] = useState(null);
  const [wash, setWash] = useState(null);
  const [mm, setMm] = useState(null);
  const [trend, setTrend] = useState(null);
  const [fence, setFence] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showTgt, setShowTgt] = useState(false);
  const [tgtT, setTgtT] = useState("");
  const [tgtG, setTgtG] = useState("");

  const load = useCallback(async () => {
    try {
      const [l, w, m, t, f] = await Promise.all([
        axios.get(`${API}/api/los-pricing/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/group-wash/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/modern-metrics/${pid}`, { withCredentials: true }),
        axios.get(`${API}/api/modern-metrics/${pid}/trend?months=6`, { withCredentials: true }),
        axios.get(`${API}/api/los-pricing/${pid}/fences`, { withCredentials: true }),
      ]);
      setLos(l.data); setWash(w.data); setMm(m.data); setTrend(t.data); setFence(f.data);
    } catch { toast.error("Veriler yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const applyLos = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/los-pricing/${pid}/apply`, { tiers: los?.suggested_tiers }, { withCredentials: true });
      setFence({ ...r.data, property_id: pid });
      toast.success("LOS indirimleri booking widget'ta aktifleşti");
    } catch { toast.error("Uygulanamadı"); } finally { setBusy(false); }
  };

  const deactivateLos = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/los-pricing/${pid}/deactivate`, {}, { withCredentials: true });
      setFence((f) => ({ ...f, active: false }));
      toast.success("LOS indirimleri kapatıldı");
    } catch { toast.error("Kapatılamadı"); } finally { setBusy(false); }
  };

  const saveTargets = async () => {
    setBusy(true);
    try {
      const body = {};
      if (tgtT !== "") body.target_trevpor = +tgtT;
      if (tgtG !== "") body.target_goppar = +tgtG;
      await axios.put(`${API}/api/modern-metrics/${pid}/targets`, body, { withCredentials: true });
      toast.success("Hedefler kaydedildi");
      setShowTgt(false);
      const t = await axios.get(`${API}/api/modern-metrics/${pid}/trend?months=6`, { withCredentials: true });
      setTrend(t.data);
    } catch { toast.error("Hedefler kaydedilemedi"); } finally { setBusy(false); }
  };

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-6" data-testid="los-wash-metrics-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Coins size={13} weight="fill" className="text-amber-500" /><span>Kârlılık Zekâsı</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">LOS Fiyatlama · Grup Wash · Modern Metrikler</h1>
        <p className="text-sm text-stone-500 mt-1">Konaklama süresi teşvikleri, grup bloklarında erime projeksiyonu ve TRevPOR/RevPAG/GOPPAR paketi.</p>
      </div>

      {mm && (
        <section data-testid="modern-metrics-section">
          <div className="flex items-center gap-2 mb-2"><TrendUp size={16} className="text-emerald-600" /><h2 className="text-base font-bold text-stone-800">Modern Metrik Paketi — {mm.month}</h2></div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <MetricCard testId="mm-trevpor" label="TRevPOR" value={`₺${mm.trevpor}`} sub="Toplam gelir / dolu oda-gece" />
            <MetricCard testId="mm-revpag" label="RevPAG" value={`₺${mm.revpag}`} sub="Toplam gelir / misafir" />
            <MetricCard testId="mm-goppar" label="GOPPAR" value={`₺${mm.goppar}`} sub="Brüt işletme kârı / müsait oda" />
            <MetricCard testId="mm-total-rev" label="Toplam Gelir" value={`₺${mm.total_revenue.toLocaleString("tr-TR")}`} sub={`Oda: ₺${mm.room_revenue.toLocaleString("tr-TR")} · Yan gelir: ₺${mm.ancillary_revenue.toLocaleString("tr-TR")}`} />
            <MetricCard testId="mm-room-nights" label="Oda-Gece" value={mm.room_nights} sub="Bu ay satılan gece" />
            <MetricCard testId="mm-guests" label="Misafir" value={mm.guests} sub="Bu ay ağırlanan yetişkin" />
          </div>
          <p className="text-[11px] text-stone-400 mt-2">{mm.note}</p>
          {trend && trend.months?.length > 0 && (
            <div className="bg-white border border-stone-200 rounded-xl p-4 mt-3" data-testid="mm-trend-chart">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <h3 className="text-sm font-bold text-stone-700">Aylık Trend — TRevPOR & GOPPAR (6 ay)</h3>
                <div className="flex items-center gap-2 flex-wrap">
                  {(() => {
                    const last = trend.months[trend.months.length - 1];
                    const badge = (val, tgt, label) => {
                      const ratio = tgt ? val / tgt : 0;
                      const cls = ratio >= 1 ? "bg-emerald-100 text-emerald-700" : ratio >= 0.9 ? "bg-amber-100 text-amber-700" : "bg-rose-100 text-rose-700";
                      const gap = tgt ? ((val - tgt) / tgt * 100).toFixed(0) : 0;
                      return <span key={label} className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${cls}`} data-testid={`mm-target-${label}`}>{label}: {gap >= 0 ? "+" : ""}{gap}% hedefe göre</span>;
                    };
                    return [badge(last.trevpor, trend.target_trevpor, "TRevPOR"), badge(last.goppar, trend.target_goppar, "GOPPAR")];
                  })()}
                  <button onClick={() => { setShowTgt((s) => !s); setTgtT(trend.target_trevpor); setTgtG(trend.target_goppar); }} data-testid="mm-target-edit-btn" className="px-2 py-0.5 rounded-full border border-stone-300 text-[11px] font-bold text-stone-600">⚙ Hedefleri Ayarla</button>
                </div>
              </div>
              {showTgt && (
                <div className="flex flex-wrap items-end gap-2 mb-3 bg-stone-50 border border-stone-200 rounded-lg p-2.5" data-testid="mm-target-form">
                  <label className="text-[11px] text-stone-500 font-bold">TRevPOR hedefi
                    <input type="number" value={tgtT} onChange={(e) => setTgtT(e.target.value)} data-testid="mm-target-trevpor-input" className="block border border-stone-300 rounded-md px-2 py-1 text-sm w-28 mt-0.5" />
                  </label>
                  <label className="text-[11px] text-stone-500 font-bold">GOPPAR hedefi
                    <input type="number" value={tgtG} onChange={(e) => setTgtG(e.target.value)} data-testid="mm-target-goppar-input" className="block border border-stone-300 rounded-md px-2 py-1 text-sm w-28 mt-0.5" />
                  </label>
                  <button onClick={saveTargets} disabled={busy} data-testid="mm-target-save-btn" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[12px] font-bold disabled:opacity-50">Kaydet</button>
                  {trend.targets_custom && <span className="text-[11px] text-emerald-600 font-bold">Özel hedefler aktif</span>}
                </div>
              )}
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trend.months} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => `₺${v}`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <ReferenceLine y={trend.target_trevpor} stroke="#7c3aed" strokeDasharray="4 4" label={{ value: "TRevPOR hedef", fontSize: 10, fill: "#7c3aed" }} />
                  <ReferenceLine y={trend.target_goppar} stroke="#059669" strokeDasharray="4 4" label={{ value: "GOPPAR hedef", fontSize: 10, fill: "#059669" }} />
                  <Line type="monotone" dataKey="trevpor" name="TRevPOR" stroke="#7c3aed" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="goppar" name="GOPPAR" stroke="#059669" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}

      {los && (
        <section data-testid="los-pricing-section">
          <div className="flex items-center gap-2 mb-2"><MoonStars size={16} className="text-violet-600" /><h2 className="text-base font-bold text-stone-800">LOS Bazlı Fiyatlama (son 180 gün · {los.sample_bookings} rezervasyon)</h2></div>
          <div className="grid md:grid-cols-2 gap-3">
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="text-xs font-bold text-stone-500 mb-2">GECE KOVASI ANALİZİ</div>
              <table className="w-full text-sm" data-testid="los-buckets-table">
                <thead><tr className="text-left text-[11px] text-stone-400"><th className="pb-1">Gece</th><th className="pb-1">Rezervasyon</th><th className="pb-1">Gecelik ADR</th></tr></thead>
                <tbody>
                  {los.buckets.map((b) => (
                    <tr key={b.bucket} className="border-t border-stone-100">
                      <td className="py-1.5 font-bold">{b.bucket}</td>
                      <td className="py-1.5">{b.bookings}</td>
                      <td className="py-1.5">₺{b.adr}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="space-y-2" data-testid="los-tiers">
              <div className={`rounded-xl p-3 border flex items-center justify-between ${fence?.active ? "bg-emerald-50 border-emerald-200" : "bg-stone-50 border-stone-200"}`} data-testid="los-fence-status">
                <span className={`text-sm font-bold ${fence?.active ? "text-emerald-800" : "text-stone-600"}`}>
                  {fence?.active ? "✅ LOS indirimleri booking widget'ta AKTİF" : "LOS indirimleri henüz uygulanmadı"}
                </span>
                {fence?.active ? (
                  <button onClick={deactivateLos} disabled={busy} data-testid="los-deactivate-btn" className="px-3 py-1.5 rounded-lg bg-stone-200 text-stone-700 text-[12px] font-bold disabled:opacity-50">Kapat</button>
                ) : (
                  <button onClick={applyLos} disabled={busy || !los} data-testid="los-apply-btn" className="px-3 py-1.5 rounded-lg bg-violet-600 text-white text-[12px] font-bold disabled:opacity-50">Tek Tıkla Uygula</button>
                )}
              </div>
              {los.suggested_tiers.map((t) => (
                <div key={t.min_nights} className="bg-violet-50 border border-violet-200 rounded-xl p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-black text-violet-900">{t.min_nights}+ gece</span>
                    <span className="text-sm font-black text-violet-700" data-testid={`los-tier-${t.min_nights}`}>−%{t.discount_pct}</span>
                  </div>
                  <p className="text-[12px] text-violet-800 mt-1">{t.why}</p>
                </div>
              ))}
              <p className="text-[11px] text-stone-400">{los.note}</p>
            </div>
          </div>
        </section>
      )}

      {wash && (
        <section data-testid="group-wash-section">
          <div className="flex items-center gap-2 mb-2"><UsersThree size={16} className="text-rose-600" /><h2 className="text-base font-bold text-stone-800">Grup Wash Projeksiyonu — tarihsel wash %{wash.historical_wash_pct} ({wash.measured_blocks} blok ölçüldü)</h2></div>
          {wash.active_blocks.length === 0 ? (
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500" data-testid="wash-empty">Aktif grup bloğu yok. Yeni blok açıldığında beklenen erime burada projeksiyonlanır.</div>
          ) : (
            <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
              <table className="w-full text-sm" data-testid="wash-table">
                <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100">
                  <th className="p-2.5">Blok</th><th className="p-2.5">Tarih</th><th className="p-2.5">Tahsis</th><th className="p-2.5">Pickup</th><th className="p-2.5">Beklenen Pickup</th><th className="p-2.5">Şimdi Salınabilir</th><th className="p-2.5">Tavsiye</th>
                </tr></thead>
                <tbody>
                  {wash.active_blocks.map((b, i) => (
                    <tr key={i} className="border-t border-stone-100" data-testid={`wash-row-${i}`}>
                      <td className="p-2.5 font-bold">{b.name}<div className="text-[10px] text-stone-400">{b.code}</div></td>
                      <td className="p-2.5 text-[12px]">{b.from_date} → {b.to_date}</td>
                      <td className="p-2.5">{b.allocated}</td>
                      <td className="p-2.5">{b.picked_up}</td>
                      <td className="p-2.5">{b.expected_pickup}</td>
                      <td className={`p-2.5 font-black ${b.releasable_now >= 1 ? "text-rose-600" : "text-emerald-600"}`}>{b.releasable_now}</td>
                      <td className="p-2.5 text-[12px] text-stone-600">{b.advice}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-[11px] text-stone-400 mt-2">{wash.note}</p>
        </section>
      )}
    </div>
  );
}
