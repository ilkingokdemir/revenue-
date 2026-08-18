/**
 * Booking Source Attribution Panel
 * --------------------------------
 * Displays first-click / last-click / linear / channel-native breakdowns of
 * which marketing sources drove bookings in the last 30 days.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, BarChart3, RefreshCw, Download, Zap } from "lucide-react";
import RoasCalculator from "./RoasCalculator";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODELS = [
  { key: "first_click", label: "First click", desc: "Awareness — what brought them" },
  { key: "last_click", label: "Last click", desc: "Conversion — what closed the sale" },
  { key: "linear", label: "Linear", desc: "Equal share across each touch" },
  { key: "channel_native", label: "Native channel", desc: "From booking.channel field" },
];

export default function AttributionPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [days, setDays] = useState(30);
  const [model, setModel] = useState("last_click");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [r, f] = await Promise.all([
        axios.get(`${API}/attribution/${propertyId}/report?days=${days}`),
        axios.get(`${API}/attribution/${propertyId}/funnel?days=${days}`),
      ]);
      setData(r.data); setFunnel(f.data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId, days]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setData(null); setFunnel(null); }, [propertyId]);

  const rows = data?.[model] || [];
  const totalRev = rows.reduce((s, r) => s + (r.revenue || 0), 0);

  return (
    <div className="space-y-6" data-testid="attribution-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-violet-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Source Attribution</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Multi-touch booking attribution — UTM-based + channel-native.</p>
        </div>
        <div className="flex gap-2">
          <select data-testid="attr-days" value={days} onChange={(e) => setDays(parseInt(e.target.value, 10))}
            className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
            {[7, 14, 30, 60, 90].map((d) => <option key={d} value={d}>{`${d}d`}</option>)}
          </select>
          <button data-testid="attr-refresh-btn" onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button
            onClick={async () => {
              try {
                const r = await axios.get(`${API}/attribution/${propertyId}/export.csv?days=90`, { responseType: "blob" });
                const url = URL.createObjectURL(r.data);
                const a = document.createElement("a");
                a.href = url; a.download = `google_ads_conversions_${propertyId}.csv`; a.click();
                URL.revokeObjectURL(url);
                toast.success("Google Ads CSV indirildi");
              } catch { toast.error("Export failed"); }
            }}
            data-testid="attr-google-csv-btn"
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold"
            title="Google Ads Offline Conversions için CSV indir (son 90 gün gclid'li rezervasyonlar)"
          >
            <Download className="w-4 h-4" /> Google Ads CSV
          </button>
          <button
            onClick={async () => {
              if (!window.confirm("5 örnek attribution kaydı oluşturulsun mu?")) return;
              try {
                const samples = [
                  { utm_source: "google-ads", utm_medium: "cpc", utm_campaign: "london-hotels-summer", gclid: "Cj0KCQjw" + Math.random().toString(36).slice(2, 12), value: 245 },
                  { utm_source: "google-ads", utm_medium: "cpc", utm_campaign: "brand-camden",         gclid: "Cj0KCQjw" + Math.random().toString(36).slice(2, 12), value: 180 },
                  { utm_source: "facebook",   utm_medium: "social", utm_campaign: "retargeting-may",   value: 320 },
                  { utm_source: "direct",     value: 210 },
                  { utm_source: "booking.com",utm_medium: "referral", value: 175 },
                ];
                for (const s of samples) {
                  // Write to both attribution stores so:
                  //  (a) legacy marketing panel (/report + /funnel) picks it up
                  //  (b) Google Ads CSV export (/export.csv) also has the row
                  const bookingId = `demo-${Math.random().toString(36).slice(2, 10)}`;
                  await axios.post(`${API}/attribution/log`, {
                    property_id: propertyId,
                    session_id: `sess-${bookingId}`,
                    fingerprint: `fp-${bookingId}`,
                    event: "booking",
                    booking_id: bookingId,
                    utm_source:   s.utm_source || "",
                    utm_medium:   s.utm_medium || "",
                    utm_campaign: s.utm_campaign || "",
                    referrer: "",
                    landing_page: "/rooms",
                  }).catch(() => {});
                  await axios.post(`${API}/attribution/track`, {
                    booking_id: bookingId, property_id: propertyId,
                    ...s, currency: "GBP",
                  }).catch(() => {});
                }
                toast.success("5 örnek attribution + Google Ads gclid oluşturuldu — CSV indirmeye hazır");
                load();
              } catch { toast.error("Seed failed"); }
            }}
            data-testid="attr-seed-demo"
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-fuchsia-600 hover:bg-fuchsia-700 text-white text-sm font-bold"
          >
            <Zap className="w-4 h-4" /> Demo Seed
          </button>
        </div>
      </div>

      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Bookings" value={data.total_bookings} />
          <Stat label="Sessions" value={data.total_sessions} />
          <Stat label="Attributed" value={data.attributed_sessions} />
          <Stat label="Attributed revenue" value={`£${(data.attributed_revenue || 0).toFixed(2)}`} highlight />
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {MODELS.map((m) => (
          <button key={m.key} data-testid={`attr-model-${m.key}`} onClick={() => setModel(m.key)}
            className={`px-3 py-2 rounded-lg text-sm border ${model === m.key
              ? "bg-violet-500/20 border-violet-500/40 text-violet-200"
              : "bg-stone-800 border-stone-700 text-stone-300 hover:bg-stone-700"}`}>
            <div className="font-medium">{m.label}</div>
            <div className="text-[10px] opacity-70">{m.desc}</div>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-stone-500"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : rows.length === 0 ? (
        <div className="text-center text-stone-500 py-12">
          No attributed touches yet — pass <code>?utm_source=google&amp;utm_medium=cpc</code> to your booking widget links to start tracking.
        </div>
      ) : (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="space-y-2">
            {rows.map((r) => {
              const pct = totalRev > 0 ? Math.round((r.revenue / totalRev) * 100) : 0;
              return (
                <div key={r.source} data-testid="attr-row">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-stone-200 font-medium">{r.source || "(direct)"}</span>
                    <span className="text-stone-400 text-xs">{r.bookings} bookings · £{r.revenue.toFixed(2)} · {pct}%</span>
                  </div>
                  <div className="h-2 bg-stone-800 rounded">
                    <div className="h-full bg-violet-500/60 rounded" style={{ width: `${Math.max(2, pct)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {funnel?.events?.length > 0 && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="text-stone-100 font-semibold mb-2">Touchpoint events</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            {funnel.events.map((e) => (
              <div key={e.event} className="bg-stone-800/40 rounded px-2 py-1 flex items-center justify-between">
                <span className="text-stone-300">{e.event}</span><span className="text-stone-500">{e.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <RoasCalculator propertyId={propertyId} />
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-violet-500/10 border-violet-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-violet-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
