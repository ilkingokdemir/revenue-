/** Owner Compset Intel — segment kıyası, sıralamalar, günlük drill-down, pazar konumu */
import { useEffect, useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend } from "recharts";

export default function OwnerCompsetIntel({ ax }) {
  const [d, setD] = useState(null);
  const [pf, setPf] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    ax().get("/owner-pulse/portal/compset").then(r => setD(r.data)).catch(e => setErr(e?.response?.data?.detail || "Yüklenemedi"));
    ax().get("/owner-pulse/portal/portfolio").then(r => setPf(r.data)).catch(() => {});
  }, [ax]);
  if (err) return <div className="text-center py-12 text-rose-500 text-sm" data-testid="op-compset-error">{err}</div>;
  if (!d) return <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>;
  const k = d.kpis;
  const dc = d.currency || "GBP";
  const cs = dc === "GBP" ? "£" : dc === "EUR" ? "€" : dc === "TRY" ? "₺" : dc === "USD" ? "$" : dc + " ";
  const mc = d.market_context || {};
  const maxTier = Math.max(...(d.tier_distribution || []).map(t => t.count), 1);

  return (
    <div className="space-y-5" data-testid="owner-compset-intel">
      {pf && pf.count > 1 && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="op-portfolio-summary">
          <div className="px-4 py-2.5 border-b border-stone-200 flex items-center justify-between">
            <div className="text-sm font-semibold text-stone-800">Portföy Rekabet Özeti</div>
            <span className="text-[10px] text-stone-400">{pf.count} tesis</span>
          </div>
          <table className="w-full text-xs">
            <thead className="text-[9px] uppercase text-stone-400 bg-stone-50">
              <tr><th className="text-left px-4 py-2">Tesis</th><th className="text-right px-2">Occ</th><th className="text-right px-2 text-stone-300">Seg.</th><th className="text-right px-2">ADR</th><th className="text-right px-2 text-stone-300">Seg.</th><th className="text-right px-2">RevPAR</th><th className="text-right px-2 text-stone-300">Seg.</th><th className="text-right px-4">Sıra</th></tr>
            </thead>
            <tbody>
              {pf.items.map((p) => {
                const pcs = p.currency === "GBP" ? "£" : p.currency === "EUR" ? "€" : p.currency === "USD" ? "$" : p.currency + " ";
                return (
                  <tr key={p.property_id} className="border-t border-stone-100" data-testid={`op-pf-row-${p.property_id}`}>
                    <td className="px-4 py-1.5 font-medium text-stone-700">{p.name}</td>
                    <td className={`text-right px-2 font-semibold ${p.occ >= p.comp_occ ? "text-emerald-600" : "text-stone-700"}`}>{p.occ}%</td>
                    <td className="text-right px-2 text-stone-400">{p.comp_occ}%</td>
                    <td className={`text-right px-2 font-semibold ${p.adr >= p.comp_adr ? "text-emerald-600" : "text-stone-700"}`}>{pcs}{Math.round(p.adr)}</td>
                    <td className="text-right px-2 text-stone-400">{pcs}{Math.round(p.comp_adr)}</td>
                    <td className={`text-right px-2 font-semibold ${p.revpar >= p.comp_revpar ? "text-emerald-600" : "text-stone-700"}`}>{pcs}{Math.round(p.revpar)}</td>
                    <td className="text-right px-2 text-stone-400">{pcs}{Math.round(p.comp_revpar)}</td>
                    <td className="text-right px-4"><span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">#{p.occ_rank}/{p.segment_size}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
        <KpiCard label="Doluluk" mine={`${k.my_occupancy}%`} seg={`${k.comp_occupancy}%`} rank={k.occ_rank} size={k.segment_size} testId="op-kpi-occ" />
        <KpiCard label="ADR" mine={`${cs}${k.my_adr}`} seg={`${cs}${k.comp_adr}`} rank={k.adr_rank} size={k.segment_size} testId="op-kpi-adr" />
        <KpiCard label="RevPAR" mine={`${cs}${k.my_revpar}`} seg={`${cs}${k.comp_revpar}`} rank={k.revpar_rank} size={k.segment_size} testId="op-kpi-revpar" />
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4" data-testid="op-sentinel">
          <div className="text-[10px] uppercase tracking-wider text-emerald-700 font-semibold">Sentinel İçgörüsü</div>
          <div className="text-sm text-stone-800 mt-2">{d.sentinel_insight}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 space-y-3">
          <div className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="text-sm font-semibold text-stone-800">Pazara Karşı Performans</div>
            <div className="text-[11px] text-stone-400 mb-2">Oteliniz vs segment ortalaması (doluluk)</div>
            <ResponsiveContainer width="100%" height={210}>
              <LineChart data={d.daily}>
                <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(v) => v.slice(5)} interval={4} />
                <YAxis tick={{ fontSize: 9 }} domain={[0, 100]} />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Line dataKey="my_occ" name="Benim Doluluğum" stroke="#0d9488" strokeWidth={2} dot={false} />
                <Line dataKey="comp_occ" name="Segment Occ" stroke="#a8a29e" strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="op-compset-drilldown">
            <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold text-stone-800">Günlük Performans Detayı</div>
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="text-[9px] uppercase text-stone-400 bg-stone-50 sticky top-0">
                  <tr><th className="text-left px-4 py-2">Tarih</th><th className="text-right px-2">Benim Occ</th><th className="text-right px-2 text-amber-600">Comp Occ</th><th className="text-right px-2">Benim ADR</th><th className="text-right px-4 text-amber-600">Comp ADR</th></tr>
                </thead>
                <tbody>
                  {d.daily.map((r) => (
                    <tr key={r.date} className="border-t border-stone-100">
                      <td className="px-4 py-1.5 text-stone-600">{r.date.slice(5)} <span className="text-stone-400">{r.dow}</span></td>
                      <td className={`text-right px-2 font-semibold ${r.my_occ >= r.comp_occ ? "text-emerald-600" : "text-stone-700"}`}>{r.my_occ}%</td>
                      <td className="text-right px-2 text-stone-500">{r.comp_occ}%</td>
                      <td className={`text-right px-2 font-semibold ${r.my_adr >= r.comp_adr ? "text-emerald-600" : "text-stone-700"}`}>{cs}{Math.round(r.my_adr)}</td>
                      <td className="text-right px-4 text-stone-500">{cs}{Math.round(r.comp_adr)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="text-[10px] uppercase tracking-wider text-stone-400 font-semibold mb-3">Pazar Bağlamı</div>
            <div className="grid grid-cols-2 gap-3">
              {[["Segment Oteli", mc.segment_hotels], ["Segment Odası", mc.segment_rooms], ["Pazar Oteli", mc.market_hotels], ["Pazar Odası", mc.market_rooms]].map(([l, v]) => (
                <div key={l}><div className="text-lg font-bold text-stone-800">{(v || 0).toLocaleString()}</div><div className="text-[10px] text-stone-400">{l}</div></div>
              ))}
            </div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="op-market-position">
            <div className="text-[10px] uppercase tracking-wider text-stone-400 font-semibold mb-3">Pazar Konumu</div>
            {[["Doluluk", k.occ_rank], ["ADR", k.adr_rank], ["RevPAR", k.revpar_rank]].map(([l, rank]) => (
              <div key={l} className="mb-3">
                <div className="flex justify-between text-xs"><span className="text-stone-600">{l}</span><span className="font-bold text-stone-800">#{rank} / {k.segment_size}</span></div>
                <div className="h-1.5 bg-stone-100 rounded-full mt-1"><div className="h-1.5 rounded-full bg-teal-500" style={{ width: `${Math.round((1 - (rank - 1) / k.segment_size) * 100)}%` }} /></div>
              </div>
            ))}
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4">
            <div className="text-[10px] uppercase tracking-wider text-stone-400 font-semibold mb-3">Tier Dağılımı</div>
            {(d.tier_distribution || []).map((t) => (
              <div key={t.tier} className="flex items-center gap-2 mb-2 text-xs">
                <span className="w-24 text-stone-600">{t.tier}</span>
                <div className="flex-1 h-1.5 bg-stone-100 rounded-full"><div className="h-1.5 rounded-full bg-stone-400" style={{ width: `${(t.count / maxTier) * 100}%` }} /></div>
                <span className="w-6 text-right text-stone-500">{t.count}</span>
              </div>
            ))}
          </div>
          <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="op-neighbourhoods">
            <div className="text-[10px] uppercase tracking-wider text-stone-400 font-semibold mb-2">Semtler</div>
            <table className="w-full text-xs">
              <thead className="text-[9px] uppercase text-stone-400"><tr><th className="text-left py-1">Bölge</th><th className="text-right">Otel</th></tr></thead>
              <tbody>
                {(d.neighbourhoods || []).slice(0, 8).map((n) => (
                  <tr key={n.area} className="border-t border-stone-100"><td className="py-1.5 text-stone-600">{n.area}</td><td className="text-right font-medium text-stone-700">{n.hotels}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ label, mine, seg, rank, size, testId }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid={testId}>
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-wider text-stone-400">{label}</div>
        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">#{rank}</span>
      </div>
      <div className="flex items-end justify-between mt-2">
        <div><div className="text-2xl font-bold text-stone-900">{mine}</div><div className="text-[10px] text-stone-400">Benim Otelim</div></div>
        <div className="text-right"><div className="text-base font-semibold text-stone-400">{seg}</div><div className="text-[10px] text-stone-400">Segment Ort.</div></div>
      </div>
    </div>
  );
}
