/**
 * DashboardSharePage (iter 370)
 * -----------------------------
 * Public read-only view of a Custom Dashboard.  Accessed via
 * `/dashboard-share/:token`.  No auth — token is the secret.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { Loader2, Lock, Eye, Clock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function DashboardSharePage() {
  const parts = window.location.pathname.split("/");
  const token = parts[parts.length - 1];
  const [dash, setDash] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get(`${API}/dashboards/public/${token}`)
      .then((r) => setDash(r.data))
      .catch((e) => setError(e?.response?.data?.detail || "Bu link geçersiz"))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-fuchsia-400" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="min-h-screen bg-stone-950 flex items-center justify-center p-6">
        <div className="text-center max-w-md space-y-3">
          <Lock className="w-14 h-14 text-stone-700 mx-auto" />
          <h1 className="text-xl font-bold text-stone-100">{error}</h1>
          <p className="text-sm text-stone-500">Dashboard sahibi link'i iptal etmiş veya süresi dolmuş olabilir.</p>
        </div>
      </div>
    );
  }

  const isExpiring = dash.share_expires_at && new Date(dash.share_expires_at) < new Date(Date.now() + 3 * 86400_000);

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <header className="border-b border-stone-800 bg-stone-900/70 backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/logos/myhotelbox_icon.png" alt="MyHotelBox" className="w-8 h-8 rounded-lg" />
            <div>
              <div className="text-[10px] uppercase tracking-wider text-stone-500">Public Dashboard</div>
              <h1 className="text-lg font-bold">{dash.name}</h1>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-fuchsia-500/15 text-fuchsia-300">
              <Eye className="w-3 h-3" /> Read-only
            </span>
            {dash.share_expires_at && (
              <span className={`flex items-center gap-1 px-2.5 py-1 rounded-full ${isExpiring ? "bg-amber-500/15 text-amber-300" : "bg-stone-800 text-stone-400"}`}>
                <Clock className="w-3 h-3" /> {new Date(dash.share_expires_at).toLocaleDateString("tr-TR")}'e kadar
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6">
        {dash.widgets?.length === 0 ? (
          <div className="text-center py-16 text-stone-500">Bu dashboard'da henüz widget yok.</div>
        ) : (
          <div className="grid grid-cols-12 gap-3 auto-rows-[70px]">
            {dash.widgets.map((w) => (
              <PublicWidget key={w.id} widget={w} token={token} />
            ))}
          </div>
        )}
      </main>

      <footer className="text-center py-6 text-xs text-stone-600">
        Powered by MyHotelBox &amp; ReveniQ · Bu bir salt-okunur paylaşımlı dashboard'dur
      </footer>
    </div>
  );
}

function PublicWidget({ widget, token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [restricted, setRestricted] = useState(false);
  useEffect(() => {
    axios.get(`${API}/dashboards/public/widget-data/${token}/${widget.type}`)
      .then((r) => setData(r.data))
      .catch((e) => { if (e?.response?.status === 403) setRestricted(true); })
      .finally(() => setLoading(false));
  }, [widget.type, token]);

  const style = {
    gridColumn: `span ${Math.min(12, widget.w || 3)} / span ${Math.min(12, widget.w || 3)}`,
    gridRow:    `span ${widget.h || 2} / span ${widget.h || 2}`,
  };
  return (
    <div style={style} className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
      {loading ? <Loader2 className="w-4 h-4 animate-spin text-stone-500" />
       : restricted ? <div className="text-xs text-stone-500 italic">Bu widget public share'de gizlenmiş</div>
       : data ? <SimpleWidget data={data} type={widget.type} />
       : <div className="text-xs text-stone-500">—</div>}
    </div>
  );
}

function SimpleWidget({ data, type }) {
  if (type.startsWith("kpi_")) {
    const val = data.value ?? "—";
    const fmt = data.unit === "%" ? `${val}%` : data.unit === "GBP" ? `£${val}` : val;
    return (
      <div className="h-full flex flex-col justify-between">
        <div className="text-[10px] uppercase tracking-wider text-stone-500">{data.label}</div>
        <div className="text-3xl font-black">{fmt}</div>
        {data.delta_pct != null && (
          <div className={`text-xs ${data.delta_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            {data.delta_pct >= 0 ? "+" : ""}{data.delta_pct}% dün
          </div>
        )}
      </div>
    );
  }
  if (type === "spark_revenue") {
    const series = data.series || [];
    const max = Math.max(1, ...series.map((s) => Number(s.revenue) || 0));
    return (
      <div className="h-full flex flex-col">
        <div className="text-[10px] uppercase tracking-wider text-stone-500 mb-1">Son 7 Gün Gelir</div>
        <div className="flex-1 flex items-end gap-1 min-h-[40px]">
          {series.map((s) => (
            <div key={s.date}
              className="flex-1 bg-gradient-to-t from-fuchsia-500 to-fuchsia-400 rounded-t"
              style={{ height: `${(Number(s.revenue) || 0) / max * 100}%` }} />
          ))}
        </div>
      </div>
    );
  }
  return <pre className="text-xs text-stone-500">{JSON.stringify(data, null, 2)}</pre>;
}
