/** Owner Pulse — Genel Bakış (aylık kartlar + YoY, 90g doluluk & pickup, son rezervasyonlar, yıllık tablo) */
import { useEffect, useState } from "react";
import { ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, Legend } from "recharts";

export default function OwnerPulseDashboard({ ax }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    ax().get("/owner-pulse/portal/dashboard").then(r => setD(r.data)).catch(e => setErr(e?.response?.data?.detail || "Yüklenemedi"));
  }, [ax]);
  if (err) return <div className="text-center py-12 text-rose-500 text-sm" data-testid="op-dash-error">{err}</div>;
  if (!d) return <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>;
  const c = d.currency === "GBP" ? "£" : d.currency === "EUR" ? "€" : d.currency === "TRY" ? "₺" : d.currency === "USD" ? "$" : d.currency + " ";
  const fmt = (n) => (n || 0).toLocaleString("tr-TR", { maximumFractionDigits: 0 });

  return (
    <div className="space-y-5" data-testid="owner-pulse-dashboard">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {d.month_cards.map((m) => (
          <div key={m.label} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`op-month-card-${m.tag}`}>
            <div className="flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-wider text-stone-500">{m.label} <span className="text-stone-400">· {m.month} ({m.tag})</span></div>
              {m.yoy_pct != null && (
                <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${m.yoy_pct >= 0 ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-600"}`}>
                  {m.yoy_pct >= 0 ? "▲" : "▼"} YoY {m.yoy_pct >= 0 ? "+" : ""}{m.yoy_pct}%
                </span>
              )}
            </div>
            <div className="text-3xl font-bold text-stone-900 mt-2">{c}{fmt(m.revenue)}</div>
            <div className="text-[10px] uppercase text-stone-400 mb-3">Toplam Gelir</div>
            <div className="text-xs space-y-1">
              <div className="flex justify-between text-stone-500"><span></span><span className="flex gap-4"><span className="w-16 text-right font-medium text-stone-600">Bu yıl</span><span className="w-16 text-right">Geçen yıl</span></span></div>
              {[["Gelir", `${c}${fmt(m.revenue)}`, `${c}${fmt(m.ly_revenue)}`], ["Doluluk", `${m.occ}%`, `${m.ly_occ}%`], ["ADR", `${c}${m.adr}`, `${c}${m.ly_adr}`]].map(([l, a, b]) => (
                <div key={l} className="flex justify-between"><span className="text-stone-500">{l}</span><span className="flex gap-4"><span className="w-16 text-right font-semibold text-stone-800">{a}</span><span className="w-16 text-right text-stone-400">{b}</span></span></div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="op-pace-strip">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-stone-800">Önümüzdeki 14 Gün — Dolum Hızı (Pace)</div>
            <div className="text-[11px] text-stone-400">Son 7 günde her tarihe eklenen oda geceleri {d.pace_source === "snapshot" ? "· günlük OTB arşivinden" : "· rezervasyon akışından"}</div>
          </div>
        </div>
        <div className="grid grid-cols-7 gap-1.5 mt-3">
          {d.occ_series.slice(0, 14).map((s) => (
            <div key={s.date} className={`rounded-lg border p-1.5 text-center ${s.pace > 0 ? "bg-emerald-50 border-emerald-200" : s.pace < 0 ? "bg-orange-50 border-orange-200" : "bg-stone-50 border-stone-200"}`}>
              <div className="text-[9px] text-stone-500">{s.date.slice(5)}</div>
              <div className={`text-sm font-bold ${s.pace > 0 ? "text-emerald-600" : s.pace < 0 ? "text-orange-500" : "text-stone-400"}`}>
                {s.pace > 0 ? "▲" : s.pace < 0 ? "▼" : "–"}{s.pace !== 0 ? Math.abs(s.pace) : ""}
              </div>
              <div className="text-[9px] text-stone-400">{s.occ}%</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 bg-white border border-stone-200 rounded-xl p-4">
          <div className="text-sm font-semibold text-stone-800">90 Günlük Doluluk & Pickup</div>
          <div className="text-[11px] text-stone-400 mb-2">Doluluk trendi + son 7 günde gelen rezervasyon yoğunluğu</div>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={d.occ_series}>
              <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(v) => v.slice(5)} interval={13} />
              <YAxis yAxisId="l" tick={{ fontSize: 9 }} domain={[0, 100]} />
              <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 9 }} allowDecimals={false} />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Bar yAxisId="l" dataKey="occ" name="Doluluk %" fill="#a8a29e" radius={[2, 2, 0, 0]} />
              <Bar yAxisId="r" dataKey="pickup_7d" name="7g Pickup" fill="#0ea5e9" radius={[2, 2, 0, 0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="op-recent-bookings">
          <div className="text-sm font-semibold text-stone-800 mb-2">Son Rezervasyonlar <span className="text-[10px] font-normal text-stone-400">· son 7 gün</span></div>
          <table className="w-full text-xs">
            <thead className="text-[9px] uppercase text-stone-400"><tr><th className="text-left py-1">Tarih</th><th className="text-right">Rez.</th><th className="text-right">Gece</th><th className="text-right">ADR</th><th className="text-right">Gelir</th></tr></thead>
            <tbody>
              {d.recent_bookings.map((r) => (
                <tr key={r.date} className="border-t border-stone-100">
                  <td className="py-1.5 text-stone-600">{r.dow} {r.date.slice(8)} {["","Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"][parseInt(r.date.slice(5,7),10)]}</td>
                  <td className="text-right font-semibold text-stone-800">{r.bookings}</td>
                  <td className="text-right text-stone-500">{r.room_nights}</td>
                  <td className="text-right text-stone-500">{c}{Math.round(r.adr)}</td>
                  <td className="text-right font-medium text-stone-700">{c}{fmt(r.revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto" data-testid="op-annual-table">
        <div className="px-4 py-3 border-b border-stone-200">
          <div className="text-sm font-semibold text-stone-800">Yıllık Performans — Tüm Metrikler</div>
          <div className="text-[11px] text-stone-400">{d.annual.prev_year} vs {d.annual.cur_year} · ADR, Doluluk & Gelir karşılaştırması</div>
        </div>
        <table className="w-full text-xs min-w-[720px]">
          <thead className="text-[9px] uppercase text-stone-400 bg-stone-50">
            <tr>
              <th className="text-left px-4 py-2">Ay</th>
              <th className="text-right px-2">{d.annual.prev_year} Occ</th><th className="text-right px-2">ADR</th><th className="text-right px-2">Gelir</th>
              <th className="text-right px-2 border-l border-stone-200">{d.annual.cur_year} Occ</th><th className="text-right px-2">ADR</th><th className="text-right px-2">Gelir</th>
              <th className="text-right px-2 border-l border-stone-200">Δ %</th><th className="text-right px-4">Δ {c}</th>
            </tr>
          </thead>
          <tbody>
            {d.annual.rows.map((r) => (
              <tr key={r.month} className={`border-t border-stone-100 ${r.mtd ? "bg-sky-50/50" : ""}`}>
                <td className="px-4 py-1.5 font-medium text-stone-700">{r.month}{r.mtd && <span className="ml-1 text-[8px] px-1 py-0.5 bg-sky-100 text-sky-700 rounded">MTD</span>}</td>
                <td className="text-right px-2 text-stone-500">{r.p_occ}%</td><td className="text-right px-2 text-stone-500">{c}{Math.round(r.p_adr)}</td><td className="text-right px-2 text-stone-500">{c}{fmt(r.p_rev)}</td>
                <td className="text-right px-2 border-l border-stone-100 text-stone-700">{r.c_occ}%</td><td className="text-right px-2 text-stone-700">{c}{Math.round(r.c_adr)}</td><td className="text-right px-2 font-medium text-stone-800">{c}{fmt(r.c_rev)}</td>
                <td className={`text-right px-2 border-l border-stone-100 font-semibold ${r.delta_pct == null ? "text-stone-300" : r.delta_pct >= 0 ? "text-emerald-600" : "text-rose-500"}`}>{r.delta_pct == null ? "—" : `${r.delta_pct >= 0 ? "+" : ""}${r.delta_pct}%`}</td>
                <td className={`text-right px-4 ${r.delta_abs >= 0 ? "text-emerald-600" : "text-rose-500"}`}>{r.delta_abs >= 0 ? "+" : "−"}{c}{fmt(Math.abs(r.delta_abs))}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-stone-200 font-semibold bg-stone-50">
              <td className="px-4 py-2 text-stone-800">Yıllık Toplam</td>
              <td colSpan={2}></td><td className="text-right px-2 text-stone-600">{c}{fmt(d.annual.totals.p_rev)}</td>
              <td colSpan={2}></td><td className="text-right px-2 text-stone-800">{c}{fmt(d.annual.totals.c_rev)}</td>
              <td className={`text-right px-2 ${d.annual.totals.delta_pct >= 0 ? "text-emerald-600" : "text-rose-500"}`}>{d.annual.totals.delta_pct == null ? "—" : `${d.annual.totals.delta_pct >= 0 ? "+" : ""}${d.annual.totals.delta_pct}%`}</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
