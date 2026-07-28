import { useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { House, TrendUp, Percent, Broadcast, ArrowsClockwise } from "@phosphor-icons/react";
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;

export default function StrMarketView({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scan, setScan] = useState(null);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/str-market/${propertyId}/overview?days=60`, { withCredentials: true });
      setData(r.data);
    } catch (e) {
      toast.error("STR pazar verisi yüklenemedi");
    } finally { setLoading(false); }
  }, [propertyId]);

  const pollStatus = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/str-market/${propertyId}/scan/status`, { withCredentials: true });
      setScan(r.data);
      if (r.data.status === "done") {
        clearInterval(pollRef.current);
        pollRef.current = null;
        toast.success(`Canlı tarama bitti: ${r.data.live_ok}/${r.data.total} tarih Booking.com'dan alındı`);
        load();
      }
    } catch (e) { /* noop */ }
  }, [propertyId, load]);

  useEffect(() => {
    load();
    pollStatus();
    return () => pollRef.current && clearInterval(pollRef.current);
  }, [load, pollStatus]);

  const startScan = async () => {
    try {
      const r = await axios.post(`${API}/api/str-market/${propertyId}/scan?days=14`, {}, { withCredentials: true });
      toast.info(`Booking.com STR taraması başladı (${r.data.dates_to_scan} tarih)…`);
      setScan({ status: "running", scanned: 0, total: r.data.dates_to_scan, live_ok: 0 });
      if (!pollRef.current) pollRef.current = setInterval(pollStatus, 3000);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Tarama başlatılamadı");
    }
  };

  if (loading || !data) return <div className="py-10 text-center text-sm text-stone-400" data-testid="str-market-loading">Yükleniyor…</div>;

  const s = data.summary;
  const scanning = scan?.status === "running";
  return (
    <div className="space-y-4" data-testid="str-market-view">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-stone-500" data-testid="str-source-info">
          {s.live_dates > 0
            ? <>Kaynak: <span className="font-semibold text-emerald-600">{s.live_dates} gün Booking.com canlı</span> + {s.simulated_dates} gün simülasyon{s.last_scan_at ? ` · Son tarama: ${new Date(s.last_scan_at).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}` : ""}</>
            : <>Kaynak: simülasyon — gerçek pazar verisi için canlı tarama başlatın</>}
        </div>
        <button onClick={startScan} disabled={scanning} data-testid="str-scan-btn"
          className="px-3 py-2 text-xs rounded-md bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-60 inline-flex items-center gap-1.5 font-medium">
          {scanning
            ? <><ArrowsClockwise size={13} className="animate-spin" /> Taranıyor {scan.scanned}/{scan.total}…</>
            : <><Broadcast size={13} weight="fill" /> Booking.com'dan Canlı Tara</>}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi icon={House} color="rose" label="Aktif STR İlanı" value={s.listings_total}
          sub={s.live_dates > 0 ? "Canlı ortalama" : `%${s.entire_home_pct} tüm ev`} testId="str-kpi-listings" />
        <Kpi icon={TrendUp} color="blue" label="STR Medyan Fiyat" value={`£${s.median_rate_avg}`} sub={`Hafta sonu +%${s.weekend_uplift_pct}`} testId="str-kpi-median" />
        <Kpi icon={Percent} color={s.hotel_vs_str_gap_pct >= 0 ? "emerald" : "amber"} label="Otel vs STR Farkı"
          value={`${s.hotel_vs_str_gap_pct >= 0 ? "+" : ""}${s.hotel_vs_str_gap_pct}%`} sub={`Otel baz £${s.hotel_base_rate}`} testId="str-kpi-gap" />
        <Kpi icon={Broadcast} color={s.live_dates > 0 ? "emerald" : "violet"} label="Veri Kaynağı"
          value={s.live_dates > 0 ? `${s.live_dates} gün canlı` : "Simülasyon"}
          sub={s.live_dates > 0 ? "Booking.com STR" : "Canlı tarama bekliyor"} testId="str-kpi-source" />
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
              <Tooltip labelFormatter={(l) => {
                const row = data.rows.find((r) => r.date === l);
                return `${l} · ${row?.source === "booking-live" ? "🔴 Canlı (Booking.com)" : "Simülasyon"}`;
              }} />
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
