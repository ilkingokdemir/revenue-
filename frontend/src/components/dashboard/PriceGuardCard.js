import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Shield } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const PriceGuardCard = ({ propertyId }) => {
  const pid = !propertyId || propertyId === "all" ? "aldgate-flats" : propertyId;
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({ max_single_pct: 10, max_72h_pct: 25 });

  const load = useCallback(() => {
    axios.get(`${API}/price-guard/${pid}`).then(({ data }) => {
      setCfg(data);
      setForm({ max_single_pct: data.max_single_pct, max_72h_pct: data.max_72h_pct });
    }).catch(() => {});
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const save = async (extra = {}) => {
    try {
      await axios.put(`${API}/price-guard/${pid}`, {
        max_single_pct: Number(form.max_single_pct), max_72h_pct: Number(form.max_72h_pct), ...extra,
      });
      toast.success("Güvenlik sınırları kaydedildi");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };

  if (!cfg) return null;

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-4 mb-4" data-testid="price-guard-card">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-black text-stone-800 flex items-center gap-2">
          <Shield className="w-4 h-4 text-indigo-600" /> Fiyat Güvenlik Sınırları
        </h3>
        <button onClick={() => save({ enabled: !cfg.enabled })} data-testid="price-guard-toggle"
          className={`flex items-center gap-1.5 text-[10px] font-bold rounded-lg px-2.5 py-1.5 border ${cfg.enabled ? "text-emerald-700 bg-emerald-50 border-emerald-300" : "text-stone-500 bg-white border-stone-200"}`}>
          <span className={`w-2 h-2 rounded-full ${cfg.enabled ? "bg-emerald-500" : "bg-stone-300"}`} />
          {cfg.enabled ? "AKTİF" : "KAPALI"}
        </button>
        <div className="flex items-center gap-1.5 text-[11px] text-stone-600">
          Tek hamlede max %
          <input type="number" value={form.max_single_pct} onChange={(e) => setForm({ ...form, max_single_pct: e.target.value })}
            data-testid="price-guard-single-input" className="w-14 border border-stone-200 rounded-lg px-1.5 py-1 text-xs" />
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-stone-600">
          72 saatte max %
          <input type="number" value={form.max_72h_pct} onChange={(e) => setForm({ ...form, max_72h_pct: e.target.value })}
            data-testid="price-guard-72h-input" className="w-14 border border-stone-200 rounded-lg px-1.5 py-1 text-xs" />
        </div>
        <button onClick={() => save()} data-testid="price-guard-save"
          className="text-[10px] font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg px-3 py-1.5">Kaydet</button>
        <span className="ml-auto text-[10px] text-stone-400">
          Kilitli gecelere dokunulmaz · Son 20 yazımda {cfg.recent_clamps} kırpma
        </span>
      </div>
      {cfg.recent_log?.length > 0 && (
        <div className="mt-3 space-y-1" data-testid="price-guard-log">
          {cfg.recent_log.slice(0, 3).map((l) => (
            <div key={l.id} className="text-[10px] text-stone-500 flex items-center gap-2">
              <span className="font-semibold text-stone-700">{l.date}</span>
              £{l.old_rate} → £{l.final_rate}
              {l.clamped && <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 font-bold">KIRPILDI (istenilen £{l.requested_rate})</span>}
              <span className="ml-auto">{l.actor}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
