/**
 * GapAnalyzerWidget — Finds dates where the competitor market is highly occupied
 * but our hotel is under-booked. Uses /geo-supply (neighborhood) as data source
 * and highlights revenue-loss opportunities with concrete actions.
 */
import { useMemo } from "react";
import { AlertCircle, TrendingUp, Zap } from "lucide-react";
import { makeCurrencyFormatter } from "../../lib/currency";

export default function GapAnalyzerWidget({ snapshots = [], propertyId, cityHint }) {
  const currency = useMemo(() => {
    const hint = cityHint || (snapshots[0] && snapshots[0].location) || "";
    return makeCurrencyFormatter(hint);
  }, [cityHint, snapshots]);
  const cur = (v) => currency.format(v, 0);
  const curShort = currency.short;
  const gaps = useMemo(() => {
    if (!snapshots.length) return [];
    const out = [];
    for (const s of snapshots) {
      const marketDemand = s.unavailable_pct || 0;
      const ourOcc = s.our_occupancy_pct;
      if (ourOcc == null || s.our_avg_rate == null) continue;
      // Gap = market busy (≥70%) AND we're under-booked (<30%)
      if (marketDemand >= 70 && ourOcc < 30) {
        const marketAvg = s.avg_price || 0;
        const ourRate = s.our_avg_rate || 0;
        const priceGap = marketAvg > 0 ? ((ourRate - marketAvg) / marketAvg) * 100 : 0;
        // Action recommendation
        let action, severity;
        if (priceGap > 10) {
          action = `Fiyatı %${Math.abs(priceGap).toFixed(0)} düşür → Pazar ort. ${curShort(marketAvg)}`;
          severity = "high";
        } else if (priceGap < -5) {
          action = `Booking promosyon aç (rate zaten düşük, görünürlük arttır)`;
          severity = "medium";
        } else {
          action = `Last-minute deal + Genius 10% aktive et`;
          severity = "medium";
        }
        out.push({
          date: s.date,
          marketDemand,
          ourOcc,
          marketAvg,
          ourRate,
          priceGap: Math.round(priceGap * 10) / 10,
          gap: Math.round(marketDemand - ourOcc),
          action,
          severity,
        });
      }
    }
    // Sort by gap size (biggest opportunity first)
    return out.sort((a, b) => b.gap - a.gap);
  }, [snapshots]);

  // Calculate potential revenue leak: gap × avg rooms × days × our_rate
  const estimatedLeak = useMemo(() => {
    if (!gaps.length || !snapshots[0]?.our_total_rooms) return 0;
    const totalRooms = snapshots[0].our_total_rooms;
    // gap percentage points → rooms we could have sold
    return gaps.reduce((sum, g) => {
      const lostRooms = Math.round((g.gap / 100) * totalRooms);
      return sum + (lostRooms * (g.ourRate || 0));
    }, 0);
  }, [gaps, snapshots]);

  if (!snapshots.length) return null;

  if (!gaps.length) {
    return (
      <div className="bg-emerald-500/5 border border-emerald-500/30 rounded-2xl p-4 flex items-start gap-3" data-testid="gap-analyzer-empty">
        <div className="w-9 h-9 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h4 className="text-sm font-black text-emerald-300">Gap Analyzer · Hazır</h4>
          <p className="text-xs text-stone-400 mt-1">Önümüzdeki günlerde pazar talebi yüksek olup sizin doluluğunuz düşük olan tarih yok — iyi iş çıkarıyorsunuz. İlk boşluk çıkarsa burada otomatik uyarı göreceksiniz.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gradient-to-r from-rose-500/10 to-amber-500/10 border border-rose-500/30 rounded-2xl p-5 space-y-4" data-testid="gap-analyzer">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-rose-500/20 flex items-center justify-center">
            <AlertCircle className="w-5 h-5 text-rose-400" />
          </div>
          <div>
            <h3 className="text-sm font-black text-rose-200">Gap Analyzer · {gaps.length} kayıp fırsat</h3>
            <p className="text-[11px] text-stone-400 mt-0.5">
              Pazar talebi ≥%70 ama bizim doluluk &lt;%30 olan günler — bunlarda fiyat/görünürlük aksiyonu al
            </p>
          </div>
        </div>
        {estimatedLeak > 0 && (
          <div className="bg-rose-950/50 border border-rose-500/40 rounded-lg px-3 py-2" data-testid="gap-leak">
            <p className="text-[9px] font-bold uppercase tracking-widest text-rose-300">Tahmini Kayıp Gelir</p>
            <p className="text-lg font-black text-rose-200 tabular-nums">{cur(estimatedLeak)}</p>
            <p className="text-[9px] text-stone-400">bu {gaps.length} günde</p>
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-rose-500/20">
        <table className="w-full text-xs">
          <thead className="bg-rose-950/30 text-rose-200">
            <tr className="border-b border-rose-500/30 text-[10px] uppercase tracking-widest">
              <th className="text-left py-2.5 pl-3 pr-2 font-bold">Tarih</th>
              <th className="text-center px-2 font-bold">Pazar Talep</th>
              <th className="text-center px-2 font-bold">Bizim Doluluk</th>
              <th className="text-center px-2 font-bold">Gap</th>
              <th className="text-right px-2 font-bold">Pazar Ort. {currency.info.symbol.trim()}</th>
              <th className="text-right px-2 font-bold">Bizim {currency.info.symbol.trim()}</th>
              <th className="text-right px-2 font-bold">Δ</th>
              <th className="text-left pl-2 pr-3 font-bold">Önerilen Aksiyon</th>
            </tr>
          </thead>
          <tbody>
            {gaps.slice(0, 20).map((g, idx) => (
              <tr key={g.date + idx} className="border-b border-rose-500/10 hover:bg-rose-500/5">
                <td className="py-2.5 pl-3 pr-2 text-stone-100 font-semibold tabular-nums">{g.date}</td>
                <td className="text-center px-2">
                  <span className="inline-block px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-200 font-bold">{g.marketDemand}%</span>
                </td>
                <td className="text-center px-2">
                  <span className="inline-block px-1.5 py-0.5 rounded bg-stone-700/40 text-stone-300 font-bold">{g.ourOcc}%</span>
                </td>
                <td className="text-center px-2">
                  <span className="text-amber-300 font-black tabular-nums">-{g.gap} puan</span>
                </td>
                <td className="text-right px-2 text-amber-300 tabular-nums">{cur(g.marketAvg)}</td>
                <td className="text-right px-2 text-violet-300 tabular-nums">{cur(g.ourRate)}</td>
                <td className={`text-right px-2 font-bold tabular-nums ${g.priceGap > 0 ? "text-rose-300" : "text-emerald-300"}`}>
                  {g.priceGap > 0 ? "+" : ""}{g.priceGap}%
                </td>
                <td className="pl-2 pr-3 py-2">
                  <div className="flex items-center gap-1.5 text-[11px] text-cyan-200">
                    <Zap className={`w-3 h-3 ${g.severity === "high" ? "text-rose-400" : "text-amber-400"}`} />
                    {g.action}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {gaps.length > 20 && (
          <div className="text-center py-2 text-[10px] text-stone-500 bg-rose-950/20">+ {gaps.length - 20} daha</div>
        )}
      </div>
    </div>
  );
}
