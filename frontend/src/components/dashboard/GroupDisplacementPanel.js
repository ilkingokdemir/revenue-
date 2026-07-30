import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Scale, Loader2, CheckCircle2, AlertTriangle, XCircle, Users } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const REC_STYLES = {
  accept: { bg: "bg-emerald-50 border-emerald-300", text: "text-emerald-800", icon: CheckCircle2, label: "KABUL ET" },
  negotiate: { bg: "bg-amber-50 border-amber-300", text: "text-amber-800", icon: AlertTriangle, label: "PAZARLIK ET" },
  reject: { bg: "bg-rose-50 border-rose-300", text: "text-rose-800", icon: XCircle, label: "REDDET" },
};

export function GroupDisplacementPanel({ activePropertyId }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : "default";
  const today = new Date();
  const iso = (d) => d.toISOString().slice(0, 10);
  const [form, setForm] = useState({
    group_name: "", check_in: iso(new Date(today.getTime() + 14 * 864e5)),
    check_out: iso(new Date(today.getTime() + 17 * 864e5)), rooms_requested: 10, offered_rate: 90,
  });
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/group-displacement/history/${pid}`);
      setHistory(data || []);
    } catch { /* silent */ }
  }, [pid]);
  useEffect(() => { loadHistory(); }, [loadHistory]);

  const analyze = async () => {
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/group-displacement/analyze`, {
        property_id: pid, ...form,
        rooms_requested: parseInt(form.rooms_requested) || 1,
        offered_rate: parseFloat(form.offered_rate) || 0,
      });
      setResult(data);
      loadHistory();
    } catch (e) { toast.error(e?.response?.data?.detail || "Analiz başarısız"); }
    finally { setLoading(false); }
  };

  const rec = result ? REC_STYLES[result.recommendation] : null;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="group-displacement-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
          <Scale size={22} className="text-violet-600" />
          Grup Displacement Analizi
        </h1>
        <p className="text-sm text-stone-500 mt-0.5">
          Duetto BlockBuster tarzı: grup teklifi transient (bireysel) talebi ne kadar yerinden ediyor?
          Kabul / pazarlık / red kararını veriyle verin.
        </p>
      </div>

      {/* Form */}
      <div className="bg-white border border-stone-200 rounded-2xl p-5 grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
        <div className="col-span-2">
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Grup adı</label>
          <input value={form.group_name} onChange={e => setForm({ ...form, group_name: e.target.value })}
            placeholder="ör. Tur operatörü X" data-testid="gd-group-name"
            className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Giriş</label>
          <input type="date" value={form.check_in} onChange={e => setForm({ ...form, check_in: e.target.value })}
            data-testid="gd-check-in" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Çıkış</label>
          <input type="date" value={form.check_out} onChange={e => setForm({ ...form, check_out: e.target.value })}
            data-testid="gd-check-out" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Oda sayısı</label>
          <input type="number" min="1" value={form.rooms_requested} onChange={e => setForm({ ...form, rooms_requested: e.target.value })}
            data-testid="gd-rooms" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Teklif (gecelik)</label>
          <input type="number" min="0" value={form.offered_rate} onChange={e => setForm({ ...form, offered_rate: e.target.value })}
            data-testid="gd-rate" className="w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
        </div>
        <button onClick={analyze} disabled={loading} data-testid="gd-analyze-btn"
          className="col-span-2 md:col-span-6 flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-br from-violet-600 to-purple-700 hover:from-violet-500 hover:to-purple-600 text-white text-sm font-bold disabled:opacity-50 shadow">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scale className="w-4 h-4" />}
          Analiz Et
        </button>
      </div>

      {/* Result */}
      {result && rec && (
        <div className="space-y-4" data-testid="gd-result">
          <div className={`border-2 rounded-2xl p-5 flex items-start gap-4 ${rec.bg}`} data-testid="gd-recommendation">
            <rec.icon className={`w-8 h-8 flex-shrink-0 ${rec.text}`} />
            <div>
              <div className={`text-lg font-black ${rec.text}`}>{rec.label}</div>
              <p className={`text-sm mt-0.5 ${rec.text}`}>{result.reason}</p>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Kpi label="Grup geliri" value={result.total_group_revenue} testId="gd-kpi-revenue" />
            <Kpi label="Yerinden edilen oda" value={result.total_displaced_rooms} plain testId="gd-kpi-displaced" />
            <Kpi label="Displacement maliyeti" value={result.total_displacement_cost} negative testId="gd-kpi-cost" />
            <Kpi label="Net değer" value={result.net_value} highlight testId="gd-kpi-net" />
            <Kpi label="Önerilen min fiyat" value={result.suggested_min_rate} testId="gd-kpi-minrate" />
          </div>
          <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
            <table className="w-full text-xs" data-testid="gd-night-table">
              <thead className="bg-stone-50 text-stone-500 uppercase text-[10px]">
                <tr>
                  <th className="px-3 py-2 text-left">Gece</th>
                  <th className="px-3 py-2 text-right">Dolu</th>
                  <th className="px-3 py-2 text-right">Beklenen pickup</th>
                  <th className="px-3 py-2 text-right">Gruba müsait</th>
                  <th className="px-3 py-2 text-right">Yerinden edilen</th>
                  <th className="px-3 py-2 text-right">Transient ADR</th>
                  <th className="px-3 py-2 text-right">Net</th>
                </tr>
              </thead>
              <tbody>
                {result.per_night.map(n => (
                  <tr key={n.date} className="border-t border-stone-100">
                    <td className="px-3 py-2 font-semibold text-stone-800">{n.date}</td>
                    <td className="px-3 py-2 text-right">{n.booked}/{n.capacity}</td>
                    <td className="px-3 py-2 text-right">{n.expected_pickup}</td>
                    <td className="px-3 py-2 text-right">{n.available_for_group}</td>
                    <td className={`px-3 py-2 text-right font-bold ${n.displaced_rooms > 0 ? "text-rose-600" : "text-emerald-600"}`}>{n.displaced_rooms}</td>
                    <td className="px-3 py-2 text-right">{n.transient_adr}</td>
                    <td className={`px-3 py-2 text-right font-bold ${n.net_value >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{n.net_value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* History */}
      {history.length > 0 && (
        <div className="bg-white border border-stone-200 rounded-2xl p-5" data-testid="gd-history">
          <h2 className="text-sm font-black text-stone-900 flex items-center gap-2 mb-3">
            <Users size={15} className="text-stone-400" /> Son analizler
          </h2>
          <div className="space-y-1.5">
            {history.map(h => {
              const r = REC_STYLES[h.recommendation];
              return (
                <div key={h.id} className="flex items-center gap-3 text-xs py-1.5 border-b border-stone-50 last:border-0">
                  <span className={`px-2 py-0.5 rounded-full border text-[9px] font-bold ${r.bg} ${r.text}`}>{r.label}</span>
                  <span className="font-semibold text-stone-800">{h.group_name || "İsimsiz grup"}</span>
                  <span className="text-stone-500">{h.check_in} → {h.check_out} · {h.rooms_requested} oda @ {h.offered_rate}</span>
                  <span className={`ml-auto font-bold ${h.net_value >= 0 ? "text-emerald-700" : "text-rose-700"}`}>net {h.net_value}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

const Kpi = ({ label, value, negative, highlight, plain, testId }) => (
  <div className={`p-3 rounded-xl border ${highlight ? "bg-violet-50 border-violet-200" : "bg-white border-stone-200"}`} data-testid={testId}>
    <div className="text-[9px] uppercase font-bold text-stone-400">{label}</div>
    <div className={`text-lg font-black ${negative ? "text-rose-700" : highlight ? "text-violet-800" : "text-stone-900"}`}>
      {plain ? value : Number(value).toLocaleString()}
    </div>
  </div>
);
