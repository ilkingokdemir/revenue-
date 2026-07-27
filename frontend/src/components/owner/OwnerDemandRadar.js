/** Owner Demand Radar — 90 gün pazar zekâsı: talep/fiyat/arz timeline, pickup, AI brief, rezervasyon davranışı, fırsat haritası */
import { useEffect, useState } from "react";
import { ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, Legend, Cell, ScatterChart, Scatter, ZAxis, AreaChart, Area } from "recharts";

const OPP_COLORS = { underpriced: "#22c55e", overpriced: "#ef4444", peak: "#f59e0b", fair: "#94a3b8" };

export default function OwnerDemandRadar({ ax }) {
  const [d, setD] = useState(null);
  const [bb, setBb] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    Promise.all([
      ax().get("/owner-pulse/portal/demand-radar"),
      ax().get("/owner-pulse/portal/booking-behavior"),
    ]).then(([r1, r2]) => { setD(r1.data); setBb(r2.data); })
      .catch(e => setErr(e?.response?.data?.detail || "Yüklenemedi"));
  }, [ax]);
  if (err) return <div className="text-center py-12 text-rose-500 text-sm" data-testid="op-radar-error">{err}</div>;
  if (!d || !bb) return <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>;
  const cur = d.property_currency || "GBP";
  const c = cur === "GBP" ? "£" : cur === "EUR" ? "€" : cur === "TRY" ? "₺" : cur === "USD" ? "$" : cur + " ";
  const k = d.kpis || {};

  return (
    <div className="space-y-5" data-testid="owner-demand-radar">
      <div className="bg-stone-900 text-white rounded-xl p-4 flex items-center justify-between flex-wrap gap-3" data-testid="op-radar-banner">
        <div>
          <div className="text-sm font-semibold">{d.status_text}</div>
          <div className="text-[11px] text-stone-400 mt-0.5">90 gün ileriye dönük pazar zekâsı{d.scan_city ? ` · ${d.scan_city}` : ""}</div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">{k.avg_demand ?? "—"}<span className="text-sm text-stone-400">/100</span></div>
          <div className="text-[10px] uppercase text-stone-400">mutlak talep seviyesi</div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-center">
        {[["Ort. Talep", k.avg_demand != null ? `${k.avg_demand}/100` : "—"], ["Ort. WAP", `${c}${k.avg_wap ?? "—"}`],
          ["Ort. Arz", k.avg_supply ?? "—"], ["Güçlü Günler", k.high_demand_days ?? 0],
          ["Zirve Tarih", k.peak_date ? k.peak_date.slice(5) : "—"], ["En Sakin", k.quietest_date ? k.quietest_date.slice(5) : "—"]].map(([l, v]) => (
          <div key={l} className="bg-white border border-stone-200 rounded-lg p-3">
            <div className="text-[9px] uppercase tracking-wider text-stone-400">{l}</div>
            <div className="text-base font-bold text-stone-800 mt-0.5">{v}</div>
          </div>
        ))}
      </div>

      {(d.insights || []).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2" data-testid="op-radar-insights">
          {d.insights.map((ins, i) => (
            <div key={i} className={`border-l-4 rounded-lg bg-white border border-stone-200 p-3 ${ins.type === "opportunity" ? "border-l-emerald-500" : ins.type === "warning" ? "border-l-amber-500" : "border-l-sky-500"}`}>
              <div className="text-xs font-semibold text-stone-800">{ins.title}</div>
              <div className="text-[11px] text-stone-500 mt-0.5">{ins.desc}</div>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl p-4">
        <div className="text-sm font-semibold text-stone-800">Talep Zaman Çizelgesi</div>
        <div className="text-[11px] text-stone-400 mb-2">Talep (bar) + pazar fiyatı (çizgi) — etkinlik günleri turkuaz</div>
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={d.daily}>
            <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(v) => v.slice(5)} interval={13} />
            <YAxis yAxisId="l" tick={{ fontSize: 9 }} domain={[0, 100]} />
            <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 9 }} />
            <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v, n) => [n === "WAP" ? `${c}${v}` : v, n]} labelFormatter={(l) => { const row = d.daily.find(x => x.date === l); return row?.event ? `${l} · ${row.event}` : l; }} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Bar yAxisId="l" dataKey="demand" name="Talep">
              {d.daily.map((row) => <Cell key={row.date} fill={row.event ? "#2dd4bf" : "#a8a29e"} />)}
            </Bar>
            <Line yAxisId="r" dataKey="wap" name="WAP" stroke="#0f172a" strokeWidth={1.5} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4">
        <div className="text-sm font-semibold text-stone-800">Son Pickup (7 gün)</div>
        <div className="text-[11px] text-stone-400 mb-2">Her tarihin 7 gün önceye göre dolum hızı — yeşil: hızlanıyor, turuncu: soğuyor</div>
        <ResponsiveContainer width="100%" height={140}>
          <ComposedChart data={d.pickup_change}>
            <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(v) => v.slice(5)} interval={13} />
            <YAxis tick={{ fontSize: 9 }} />
            <Tooltip contentStyle={{ fontSize: 11 }} />
            <Bar dataKey="demand_change" name="Δ talep">
              {d.pickup_change.map((row) => <Cell key={row.date} fill={row.demand_change >= 0 ? "#22c55e" : "#fb923c"} />)}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <DistCard title="Lead Time Dağılımı" sub={`${bb.total_bookings} rezervasyondan · ort. ${bb.lead_time.avg_lead_time} gün · last-minute %${bb.lead_time.last_minute_pct}`} items={bb.lead_time.distribution} testId="op-leadtime" />
        <DistCard title="Konaklama Süresi (LOS)" sub={`Ort. ${bb.length_of_stay.avg_los} gece · 3+ gece %${bb.length_of_stay.long_stay_pct}`} items={bb.length_of_stay.distribution} testId="op-los" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="op-demand-by-lt">
          <div className="text-sm font-semibold text-stone-800 mb-3">Lead Time'a Göre Talep</div>
          <div className="space-y-3">
            {bb.demand_by_lead_time.map((w) => (
              <div key={w.label} className="border-l-4 pl-3" style={{ borderColor: w.color }}>
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-stone-700">{w.label} <span className="text-[9px] px-1.5 py-0.5 rounded bg-stone-100 text-stone-500 ml-1">{w.tag}</span></span>
                  <span className="flex gap-4 text-stone-600">
                    <span><b className="text-stone-900">{w.avg_demand ?? "—"}%</b> talep</span>
                    <span><b className="text-stone-900">{c}{w.avg_wap}</b> WAP</span>
                    <span><b className="text-stone-900">{w.avg_supply ?? "—"}</b> arz</span>
                    {w.hot_dates > 0 && <span className="text-amber-600 font-semibold">{w.hot_dates} hot</span>}
                  </span>
                </div>
                <div className="h-1.5 bg-stone-100 rounded-full mt-1.5"><div className="h-1.5 rounded-full bg-teal-400" style={{ width: `${Math.min(100, w.avg_demand || 0)}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="text-sm font-semibold text-stone-800 mb-1">Haftanın Günü Desenleri</div>
          <ResponsiveContainer width="100%" height={170}>
            <ComposedChart data={bb.dow_patterns}>
              <XAxis dataKey="label" tick={{ fontSize: 10 }} />
              <YAxis yAxisId="l" tick={{ fontSize: 9 }} />
              <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Bar yAxisId="l" dataKey="avg_demand" name="Talep" fill="#2dd4bf" radius={[3, 3, 0, 0]} />
              <Line yAxisId="r" dataKey="avg_wap" name="Fiyat" stroke="#0f172a" strokeWidth={1.5} dot />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="op-opportunity-map">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <div className="text-sm font-semibold text-stone-800">Pazar Nerede Yanlış Fiyatlanmış?</div>
            <div className="text-[11px] text-stone-400">Her nokta bir check-in tarihi — pazar yoğunluğu (→) vs fiyat (↑)</div>
          </div>
          <div className="flex gap-3 text-[10px]">
            {[["Düşük fiyatlı (yükselt)", "#22c55e"], ["Aşırı fiyatlı", "#ef4444"], ["Zirve", "#f59e0b"], ["Dengeli", "#94a3b8"]].map(([l, col]) => (
              <span key={l} className="flex items-center gap-1 text-stone-500"><span className="w-2 h-2 rounded-full" style={{ background: col }} /> {l}</span>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={230}>
          <ScatterChart margin={{ top: 15, right: 15 }}>
            <XAxis dataKey="demand" name="Talep" unit="%" tick={{ fontSize: 9 }} domain={[0, 100]} type="number" />
            <YAxis dataKey="price" name="Fiyat" tick={{ fontSize: 9 }} type="number" />
            <ZAxis range={[35, 36]} />
            <Tooltip contentStyle={{ fontSize: 11 }} cursor={{ strokeDasharray: "3 3" }} formatter={(v, n) => [n === "Fiyat" ? `${c}${v}` : `${v}%`, n]} />
            <Scatter data={d.opportunity_map}>
              {d.opportunity_map.map((p, i) => <Cell key={i} fill={OPP_COLORS[p.color] || "#94a3b8"} />)}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {(d.supply_dynamics || []).length > 0 && (
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="text-sm font-semibold text-stone-800">Arz Dinamikleri</div>
          <div className="text-[11px] text-stone-400 mb-2">Check-in tarihine göre satıştaki tesis sayısı — düşüşler compression, sıçramalar arz fazlası sinyali</div>
          <ResponsiveContainer width="100%" height={130}>
            <AreaChart data={d.supply_dynamics}>
              <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(v) => v.slice(5)} interval={13} />
              <YAxis tick={{ fontSize: 9 }} />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Area dataKey="available" name="Müsait tesis" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.15} strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function DistCard({ title, sub, items, testId }) {
  const max = Math.max(...items.map((x) => x.pct), 1);
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid={testId}>
      <div className="text-sm font-semibold text-stone-800">{title}</div>
      <div className="text-[11px] text-stone-400 mb-3">{sub}</div>
      <div className="flex items-end gap-3 h-28">
        {items.map((x) => (
          <div key={x.label} className="flex-1 flex flex-col items-center justify-end h-full">
            <div className="text-[10px] font-bold" style={{ color: x.color }}>{x.pct}%</div>
            <div className="w-full max-w-[46px] rounded-t" style={{ height: `${Math.max(4, (x.pct / max) * 80)}%`, background: x.color }} />
            <div className="text-[9px] text-stone-500 mt-1">{x.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
