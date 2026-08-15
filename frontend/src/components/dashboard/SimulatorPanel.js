import React, { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { FlagCheckered, Rewind } from "@phosphor-icons/react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;
const PNAMES = { robot: "🤖 Robot", fixed: "Sabit Fiyat", yesterday_plus: "Dün+%X" };

export default function SimulatorPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [form, setForm] = useState({ days: 14, base_rate: 100, daily_drift_pct: 2 });
  const [sim, setSim] = useState(null);
  const [rp, setRp] = useState(null);
  const [rpDate, setRpDate] = useState("");
  const [bp, setBp] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadBid = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/simulator/${pid}/bid-price?days=14`, { withCredentials: true });
      setBp(r.data);
      toast.success("Bid-price ağı hesaplandı");
    } catch (e) { toast.error(e.response?.data?.detail || "Bid-price hesaplanamadı"); } finally { setBusy(false); }
  };

  const runSim = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/simulator/${pid}/run`, form, { withCredentials: true });
      setSim(r.data);
      toast.success(`Simülasyon bitti — kazanan: ${PNAMES[r.data.winner]}`);
    } catch { toast.error("Simülasyon başarısız"); } finally { setBusy(false); }
  };

  const runReplay = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/simulator/${pid}/replay${rpDate ? `?date=${rpDate}` : ""}`, { withCredentials: true });
      setRp(r.data);
      toast.success("Replay tamamlandı");
    } catch (e) { toast.error(e.response?.data?.detail || "Replay başarısız"); } finally { setBusy(false); }
  };

  return (
    <div className="p-5 max-w-[1150px] mx-auto space-y-7" data-testid="simulator-panel">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <FlagCheckered size={13} weight="fill" className="text-emerald-500" /><span>Talep Simülatörü & Replay Backtest</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Robotu Yarıştır · Geçmişi Yeniden Oynat</h1>
        <p className="text-sm text-stone-500 mt-1">Sentetik pazarda 3 politika yarışır; replay ile "o gün robot ne derdi" bilgi sızıntısız ölçülür.</p>
      </div>

      <section data-testid="sim-section">
        <div className="flex flex-wrap items-end gap-2 mb-3 bg-white border border-stone-200 rounded-xl p-3">
          <label className="text-[11px] text-stone-500 font-bold">Gün<input type="number" min={7} max={60} value={form.days} onChange={(e) => setForm((f) => ({ ...f, days: +e.target.value }))} data-testid="sim-days" className="block border border-stone-300 rounded-lg px-2 py-1.5 text-sm w-20 mt-0.5" /></label>
          <label className="text-[11px] text-stone-500 font-bold">Baz fiyat<input type="number" min={20} value={form.base_rate} onChange={(e) => setForm((f) => ({ ...f, base_rate: +e.target.value }))} data-testid="sim-rate" className="block border border-stone-300 rounded-lg px-2 py-1.5 text-sm w-24 mt-0.5" /></label>
          <label className="text-[11px] text-stone-500 font-bold">Dün+% artış<input type="number" min={0} max={10} step={0.5} value={form.daily_drift_pct} onChange={(e) => setForm((f) => ({ ...f, daily_drift_pct: +e.target.value }))} data-testid="sim-drift" className="block border border-stone-300 rounded-lg px-2 py-1.5 text-sm w-24 mt-0.5" /></label>
          <button onClick={runSim} disabled={busy} data-testid="sim-run-btn" className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-bold disabled:opacity-50">🏁 Yarıştır</button>
          <a href={`${API}/api/simulator/${pid}/report-pdf?days=${form.days}&base_rate=${form.base_rate}`} target="_blank" rel="noreferrer" data-testid="sim-pdf-btn" className="px-4 py-2 rounded-lg border border-emerald-300 text-emerald-700 text-sm font-bold">📄 PDF Rapor</a>
        </div>
        {sim && (
          <div className="grid md:grid-cols-3 gap-3" data-testid="sim-results">
            {Object.entries(sim.policies).map(([k, p]) => (
              <div key={k} className={`rounded-xl border p-4 ${k === sim.winner ? "bg-emerald-50 border-emerald-300" : "bg-white border-stone-200"}`} data-testid={`sim-policy-${k}`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-black text-stone-800">{PNAMES[k]}</span>
                  {k === sim.winner && <span className="px-2 py-0.5 rounded-full bg-emerald-600 text-white text-[10px] font-black" data-testid="sim-winner-badge">KAZANAN</span>}
                </div>
                <div className="text-2xl font-black text-stone-900 mt-1">₺{p.total_revenue.toLocaleString("tr-TR")}</div>
                <div className="text-[11px] text-stone-500 mt-1">Doluluk %{p.occupancy_pct} · ADR ₺{p.adr} · RevPAR ₺{p.revpar}</div>
              </div>
            ))}
            <div className="md:col-span-3 bg-white border border-stone-200 rounded-xl p-3">
              <div className="text-xs font-bold text-stone-500 mb-1">GÜNLÜK GELİR KARŞILAŞTIRMASI <span className="ml-2 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-black" data-testid="sim-uplift">Robot vs Sabit: {sim.robot_uplift_vs_fixed_pct > 0 ? "+" : ""}{sim.robot_uplift_vs_fixed_pct}%</span></div>
              <ResponsiveContainer width="100%" height={190}>
                <BarChart data={sim.daily.map((d) => ({ day: `G${d.day}`, Robot: d.robot.rev, Sabit: d.fixed.rev, "Dün+%": d.yesterday_plus.rev }))}>
                  <XAxis dataKey="day" tick={{ fontSize: 9 }} /><YAxis tick={{ fontSize: 10 }} /><Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Robot" fill="#059669" /><Bar dataKey="Sabit" fill="#a8a29e" /><Bar dataKey="Dün+%" fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] text-stone-400">{sim.note}</p>
            </div>
          </div>
        )}
      </section>

      <section data-testid="bidprice-section">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <h2 className="text-base font-bold text-stone-800">🕸 Bid-Price Ağı — displacement + MinLOS/CTA/CTD tek çerçevede</h2>
          <button onClick={loadBid} disabled={busy} data-testid="bidprice-btn" className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">Ağı Hesapla</button>
        </div>
        {bp && (
          <div data-testid="bidprice-results">
            <p className="text-[12px] text-stone-500 mb-2">Referans ADR: ₺{bp.ref_adr} · {bp.note}</p>
            <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
              <table className="w-full text-sm" data-testid="bidprice-table">
                <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100">
                  <th className="p-2">Tarih</th><th className="p-2">Net Doluluk</th><th className="p-2">Bid Price</th><th className="p-2">MinLOS</th><th className="p-2">CTA</th><th className="p-2">CTD</th><th className="p-2">Gerekçe</th>
                </tr></thead>
                <tbody>
                  {bp.rows.map((r) => (
                    <tr key={r.date} className={`border-t border-stone-100 ${r.cta || r.ctd ? "bg-indigo-50" : ""}`} data-testid={`bidprice-row-${r.date}`}>
                      <td className="p-2 font-bold">{r.date}</td>
                      <td className="p-2">%{r.net_occupancy_pct}</td>
                      <td className="p-2 font-black text-indigo-700">₺{r.bid_price}</td>
                      <td className="p-2">{r.min_los}</td>
                      <td className="p-2">{r.cta ? <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 text-[10px] font-black">KAPALI</span> : "—"}</td>
                      <td className="p-2">{r.ctd ? <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-black">KAPALI</span> : "—"}</td>
                      <td className="p-2 text-[11px] text-stone-500 max-w-[300px]">{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      <section data-testid="replay-section">
        <div className="flex items-center gap-2 mb-2"><Rewind size={16} className="text-sky-600" /><h2 className="text-base font-bold text-stone-800">Replay Backtest — geçmiş bir günü yeniden oynat</h2></div>
        <div className="flex flex-wrap items-end gap-2 mb-3 bg-white border border-stone-200 rounded-xl p-3">
          <label className="text-[11px] text-stone-500 font-bold">Konaklama tarihi (geçmiş)<input type="date" value={rpDate} onChange={(e) => setRpDate(e.target.value)} data-testid="replay-date" className="block border border-stone-300 rounded-lg px-2 py-1.5 text-sm mt-0.5" /></label>
          <button onClick={runReplay} disabled={busy} data-testid="replay-run-btn" className="px-4 py-2 rounded-lg bg-sky-600 text-white text-sm font-bold disabled:opacity-50">⏪ Yeniden Oynat</button>
        </div>
        {rp && (
          <div className="grid md:grid-cols-3 gap-3" data-testid="replay-results">
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="text-[11px] uppercase text-stone-500 font-bold">O An (snapshot {rp.snapshot_date})</div>
              <div className="text-xl font-black text-stone-900 mt-1">%{rp.asof.occupancy_pct} OTB</div>
              <div className="text-[11px] text-stone-500">{rp.asof.otb_rooms} oda · konaklamaya {rp.asof.days_to_stay} gün vardı</div>
            </div>
            <div className="bg-sky-50 border border-sky-200 rounded-xl p-4">
              <div className="text-[11px] uppercase text-sky-700 font-bold">Robot O Gün Derdi ki</div>
              <div className="text-xl font-black text-sky-900 mt-1" data-testid="replay-robot-rate">₺{rp.robot_would_say.rate}</div>
              <div className="text-[11px] text-sky-700">{rp.robot_would_say.logic}</div>
            </div>
            <div className="bg-white border border-stone-200 rounded-xl p-4">
              <div className="text-[11px] uppercase text-stone-500 font-bold">Gerçekleşen</div>
              <div className="text-xl font-black text-stone-900 mt-1">%{rp.realized.occupancy_pct} · ₺{rp.realized.adr}</div>
              <div className="text-[11px] text-stone-500">{rp.realized.rooms_sold} oda satıldı</div>
            </div>
            <div className="md:col-span-3 bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm font-bold text-amber-800" data-testid="replay-verdict">⚖ {rp.verdict}<p className="text-[10px] font-normal text-amber-600 mt-1">{rp.note}</p></div>
          </div>
        )}
      </section>
    </div>
  );
}
