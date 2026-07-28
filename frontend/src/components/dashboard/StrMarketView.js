import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { House, TrendUp, Percent, UsersThree } from "@phosphor-icons/react";
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;

export default function StrMarketView({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/str-market/${propertyId}/overview?days=60`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("STR pazar verisi yüklenemedi");
    } finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  if (loading || !data) return <div className="py-10 text-center text-sm text-stone-400" data-testid="str-market-loading">Yükleniyor…</div>;

  const s = data.summary;
  return (
    <div className="space-y-4" data-testid="str-market-view">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi icon={House} color="rose" label="Aktif STR İlanı" value={s.listings_total} sub={`%${s.entire_home_pct} tüm ev`} testId="str-kpi-listings" />
        <Kpi icon={TrendUp} color="blue" label="STR Medyan Fiyat" value={`£${s.median_rate_avg}`} sub={`Hafta sonu +%${s.weekend_uplift_pct}`} testId="str-kpi-median" />
        <Kpi icon={Percent} color={s.hotel_vs_str_gap_pct >= 0 ? "emerald" : "amber"} label="Otel vs STR Farkı"
          value={`${s.hotel_vs_str_gap_pct >= 0 ? "+" : ""}${s.hotel_vs_str_gap_pct}%`} sub={`Otel baz £${s.hotel_base_rate}`} testId="str-kpi-gap" />
        <Kpi icon={UsersThree} color="violet" label="Veri Kaynağı" value="Simülasyon" sub="Gerçek scraper P2" testId="str-kpi-source" />
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="str-market-chart">
        <div className="text-sm font-semibold text-stone-900 mb-2">STR Medyan Fiyat & Doluluk Sinyali (60 gün)</div>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data.rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="strFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#E11D48" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#E11D48" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} interval={6} />
              <YAxis yAxisId="l" tick={{ fontSize: 10 }} width={44} />
              <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 10 }} width={36} domain={[0, 100]} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area yAxisId="l" type="monotone" dataKey="median_rate" name="STR Medyan (£)" stroke="#E11D48" strokeWidth={1.5} fill="url(#strFill)" />
              <Line yAxisId="r" type="monotone" dataKey="occupancy_proxy" name="Doluluk Sinyali (%)" stroke="#7C3AED" strokeWidth={1.5} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="str-market-findings">
        <div className="text-sm font-semibold text-stone-900 mb-2">Bulgular</div>
        <ul className="space-y-1.5">
          {data.findings.map((f, i) => (
            <li key={i} className="text-xs text-stone-600 flex gap-2">
              <span className="text-rose-500 font-bold">•</span>{f}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Kpi({ icon: Icon, color, label, value, sub, testId }) {
  const colors = {
    rose: "text-rose-600 bg-rose-50", blue: "text-blue-600 bg-blue-50",
    emerald: "text-emerald-600 bg-emerald-50", amber: "text-amber-600 bg-amber-50",
    violet: "text-violet-600 bg-violet-50",
  };
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-3.5 flex items-center gap-3" data-testid={testId}>
      <div className={`w-9 h-9 rounded-md flex items-center justify-center ${colors[color]}`}>
        <Icon size={18} weight="fill" />
      </div>
      <div>
        <div className="text-base font-bold text-stone-900 leading-tight">{value}</div>
        <div className="text-[11px] text-stone-500">{label}{sub ? ` · ${sub}` : ""}</div>
      </div>
    </div>
  );
}
