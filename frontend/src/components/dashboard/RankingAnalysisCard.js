/**
 * Ranking Analysis Card
 *
 * Shows WHERE WE RANK on Booking.com vs configured competitors, computed from
 * already-scraped data (our own + competitors). Three axes: price, value, review.
 */
import { useState, useEffect, useMemo, useCallback } from "react";
import axios from "axios";
import {
  Trophy, TrendingDown, TrendingUp, Minus, Star, Banknote, Sparkles,
  ArrowUp, ArrowDown, Info,
} from "lucide-react";
import { makeCurrencyFormatter } from "../../lib/currency";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const shortDate = (iso) => iso ? new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" }) : "";

const RankBadge = ({ rank, total, label, icon: Icon, color }) => {
  if (!rank) return (
    <div className="flex-1 min-w-[80px] bg-stone-50 border border-stone-200 rounded-lg p-2 text-center" data-testid={`rank-${label.toLowerCase()}-empty`}>
      <div className="flex items-center gap-1 justify-center text-[9px] font-bold uppercase text-stone-400">
        <Icon className="w-3 h-3" /> {label}
      </div>
      <div className="text-base font-black text-stone-300 mt-0.5">—</div>
    </div>
  );
  const pct = rank / total;
  const accent = pct <= 0.33 ? "emerald" : pct <= 0.66 ? "amber" : "rose";
  return (
    <div className={`flex-1 min-w-[80px] bg-${accent}-50 border border-${accent}-200 rounded-lg p-2 text-center`} data-testid={`rank-${label.toLowerCase()}`}>
      <div className={`flex items-center gap-1 justify-center text-[9px] font-bold uppercase text-${accent}-700`}>
        <Icon className="w-3 h-3" /> {label}
      </div>
      <div className={`text-base font-black text-${accent}-800 mt-0.5 tabular-nums`}>
        #{rank}<span className="text-[10px] text-stone-400 font-normal">/{total}</span>
      </div>
    </div>
  );
};

const DeltaPill = ({ value }) => {
  if (!value) return null;
  if (value > 0) return <span className="inline-flex items-center gap-0.5 text-[10px] font-bold text-emerald-700"><ArrowUp className="w-2.5 h-2.5" />+{value}</span>;
  if (value < 0) return <span className="inline-flex items-center gap-0.5 text-[10px] font-bold text-rose-700"><ArrowDown className="w-2.5 h-2.5" />{value}</span>;
  return <span className="inline-flex items-center gap-0.5 text-[10px] font-bold text-stone-500"><Minus className="w-2.5 h-2.5" />0</span>;
};

export default function RankingAnalysisCard({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    axios.get(`${API}/revenue/market-robot/${propertyId}/ranking?days=7`)
      .then(r => setData(r.data))
      .finally(() => setLoading(false));
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const cur = useMemo(() => makeCurrencyFormatter(data?.currency || data?.city || ""), [data]);

  if (loading) return <div className="bg-white border border-stone-200 rounded-2xl p-5 text-sm text-stone-400">Loading ranking analysis…</div>;
  if (!data) return null;

  const rows = data.rankings || [];
  const today = rows[0];
  const delta = data.today_rank_delta_vs_previous_snapshot;
  const hasData = today && today.price_rank;
  const totalSet = today?.total_in_set || 0;

  return (
    <div className="bg-gradient-to-br from-violet-50 via-fuchsia-50 to-white border border-violet-200 rounded-2xl p-5 shadow-sm" data-testid="ranking-analysis-card">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-600 to-fuchsia-600 text-white flex items-center justify-center flex-shrink-0 shadow">
          <Trophy className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-base font-black text-stone-900">Ranking Analysis</h3>
            <span className="px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 text-[10px] font-bold uppercase tracking-wider">
              vs {totalSet > 0 ? totalSet - 1 : 0} competitors
            </span>
          </div>
          <p className="text-[11px] text-stone-500 mt-0.5">
            Where <b className="text-stone-800">{data.property_name || "your hotel"}</b> ranks on Booking.com — derived from live scraped prices & reviews.
          </p>
        </div>
      </div>

      {!hasData && (
        <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-[12px] text-amber-900">
          Insufficient data. Need at least:
          <ul className="mt-1 ml-4 list-disc text-[11px]">
            <li>Our own Booking.com scrape complete (see the card above)</li>
            <li>At least one competitor with scraped prices (Competitor Hotels tab → Scan)</li>
          </ul>
        </div>
      )}

      {hasData && (
        <>
          {/* Today's headline ranks */}
          <div className="flex items-stretch gap-2 mb-4">
            <RankBadge rank={today.price_rank} total={totalSet} label="Price" icon={Banknote} />
            <RankBadge rank={today.value_rank} total={totalSet} label="Value" icon={Sparkles} />
            <RankBadge rank={today.review_rank} total={totalSet} label="Review" icon={Star} />
          </div>

          {/* Insight strip */}
          <div className="bg-white/70 backdrop-blur border border-stone-200 rounded-lg p-3 mb-3 flex items-start gap-2 text-[12px] text-stone-700">
            <Info className="w-3.5 h-3.5 text-violet-500 flex-shrink-0 mt-0.5" />
            <span>
              <b>Today ({shortDate(today.date)}):</b> you're at <b className="text-stone-900">{cur.format(today.our_price)}</b>
              {" "}vs market median <b className="text-stone-900">{cur.format(today.market_median_price)}</b>
              {today.price_delta_pct != null && (
                <span className={today.price_delta_pct > 0 ? "text-rose-600 font-bold" : "text-emerald-600 font-bold"}>
                  {" "}({today.price_delta_pct > 0 ? "+" : ""}{today.price_delta_pct.toFixed(1)}% vs median)
                </span>
              )}
              {today.cheapest_competitor && (
                <>. Cheapest right now: <b className="text-stone-900">{today.cheapest_competitor}</b> @ {cur.format(today.cheapest_competitor_price)}.</>
              )}
              {delta && (
                <span className="ml-1">
                  Since last snapshot: Price <DeltaPill value={delta.price_rank} /> · Value <DeltaPill value={delta.value_rank} /> · Review <DeltaPill value={delta.review_rank} />
                </span>
              )}
            </span>
          </div>

          {/* 7-day outlook */}
          <div className="overflow-x-auto -mx-5 px-5">
            <table className="w-full text-xs" data-testid="ranking-table">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-stone-400 border-b border-stone-200">
                  <th className="text-left py-2 px-2 font-bold">Date</th>
                  <th className="text-right py-2 px-2 font-bold">Our Price</th>
                  <th className="text-right py-2 px-2 font-bold">Median</th>
                  <th className="text-right py-2 px-2 font-bold">Δ%</th>
                  <th className="text-center py-2 px-2 font-bold">Price</th>
                  <th className="text-center py-2 px-2 font-bold">Value</th>
                  <th className="text-center py-2 px-2 font-bold">Review</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const rank = r.price_rank;
                  const total = r.total_in_set || 1;
                  const rankClass = !rank ? "text-stone-300" : rank / total <= 0.33 ? "text-emerald-600" : rank / total <= 0.66 ? "text-amber-600" : "text-rose-600";
                  return (
                    <tr key={r.date} className={`border-b border-stone-100 hover:bg-violet-50/50 ${i === 0 ? "bg-violet-50/30" : ""}`}>
                      <td className="py-2 px-2 font-medium text-stone-700">{shortDate(r.date)}{i === 0 && <span className="ml-1 text-[9px] text-violet-500">TODAY</span>}</td>
                      <td className="text-right py-2 px-2 tabular-nums font-bold text-stone-900">{r.our_price ? cur.format(r.our_price) : "—"}</td>
                      <td className="text-right py-2 px-2 tabular-nums text-stone-500">{r.market_median_price ? cur.format(r.market_median_price) : "—"}</td>
                      <td className={`text-right py-2 px-2 tabular-nums font-bold ${r.price_delta_pct > 0 ? "text-rose-600" : r.price_delta_pct < 0 ? "text-emerald-600" : "text-stone-400"}`}>
                        {r.price_delta_pct != null ? `${r.price_delta_pct > 0 ? "+" : ""}${r.price_delta_pct.toFixed(0)}%` : "—"}
                      </td>
                      <td className={`text-center py-2 px-2 font-black tabular-nums ${rankClass}`}>{rank ? `#${rank}` : "—"}</td>
                      <td className={`text-center py-2 px-2 font-black tabular-nums ${r.value_rank ? rankClass : "text-stone-300"}`}>{r.value_rank ? `#${r.value_rank}` : "—"}</td>
                      <td className={`text-center py-2 px-2 font-black tabular-nums ${r.review_rank ? (r.review_rank === 1 ? "text-emerald-600" : rankClass) : "text-stone-300"}`}>{r.review_rank ? `#${r.review_rank}` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <p className="mt-3 text-[10px] text-stone-400">
            ℹ️ Rankings computed from live-scraped data. Not Booking's opaque search rank (which depends on user, paid placements, cookies).
            Price rank: cheapest = #1 · Value rank: review÷price = #1 · Review rank: highest score = #1.
          </p>
        </>
      )}
    </div>
  );
}
