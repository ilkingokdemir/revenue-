import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Target } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Bar = ({ label, actual, target, pct, unit }) => {
  if (pct === null) return null;
  const color = pct >= 100 ? "emerald" : pct >= 60 ? "amber" : "rose";
  const cls = { emerald: "bg-emerald-500 text-emerald-600", amber: "bg-amber-500 text-amber-600", rose: "bg-rose-500 text-rose-600" }[color];
  return (
    <div data-testid={`target-bar-${label}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-black uppercase text-stone-500">{label}</span>
        <span className={`text-xs font-black ${cls.split(" ")[1]}`}>
          {unit === "£" ? `£${actual.toLocaleString("en-GB")} / £${target.toLocaleString("en-GB")}` : `%${actual} / %${target}`} · %{pct}
        </span>
      </div>
      <div className="h-2.5 bg-stone-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${cls.split(" ")[0]}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
    </div>
  );
};

export const MonthlyTargetsCard = ({ propertyId }) => {
  const pid = !propertyId || propertyId === "all" ? "aldgate-flats" : propertyId;
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ revenue_target: "", occupancy_target: "" });

  const load = useCallback(() => {
    axios.get(`${API}/revenue/targets/${pid}`).then(({ data: d }) => {
      setData(d);
      setForm({ revenue_target: d.revenue_target || "", occupancy_target: d.occupancy_target || "" });
    }).catch(() => {});
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      await axios.put(`${API}/revenue/targets/${pid}`, {
        revenue_target: Number(form.revenue_target) || 0,
        occupancy_target: Number(form.occupancy_target) || 0,
      });
      toast.success("Aylık hedefler kaydedildi");
      setEditing(false);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };

  if (!data) return null;
  const hasTargets = data.revenue_target > 0 || data.occupancy_target > 0;

  return (
    <div className="bg-white border border-stone-200 rounded-2xl p-4 mb-4" data-testid="monthly-targets-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-black text-stone-800 flex items-center gap-2">
          <Target className="w-4 h-4 text-teal-600" /> Aylık Hedef Panosu <span className="text-[10px] font-semibold text-stone-400">({data.month})</span>
        </h3>
        <button onClick={() => setEditing((v) => !v)} data-testid="targets-edit-btn"
          className="text-[10px] font-bold text-stone-600 bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-1.5 hover:bg-stone-100">
          {editing ? "Vazgeç" : "Hedefleri Düzenle"}
        </button>
      </div>
      {editing && (
        <div className="flex flex-wrap items-end gap-3 mb-4 bg-stone-50 border border-stone-100 rounded-xl p-3">
          <div>
            <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Oda geliri hedefi (£/ay)</label>
            <input type="number" value={form.revenue_target} onChange={(e) => setForm({ ...form, revenue_target: e.target.value })}
              data-testid="targets-revenue-input" className="w-32 border border-stone-200 rounded-lg px-2 py-1.5 text-sm bg-white" />
          </div>
          <div>
            <label className="text-[10px] font-bold uppercase text-stone-500 block mb-1">Doluluk hedefi (%)</label>
            <input type="number" min="0" max="100" value={form.occupancy_target} onChange={(e) => setForm({ ...form, occupancy_target: e.target.value })}
              data-testid="targets-occupancy-input" className="w-24 border border-stone-200 rounded-lg px-2 py-1.5 text-sm bg-white" />
          </div>
          <button onClick={save} data-testid="targets-save-btn"
            className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold">Kaydet</button>
        </div>
      )}
      {hasTargets ? (
        <div className="grid md:grid-cols-2 gap-4">
          <Bar label="Oda Geliri" actual={data.current.revenue} target={data.revenue_target} pct={data.revenue_progress_pct} unit="£" />
          <Bar label="Doluluk" actual={data.current.occupancy_pct} target={data.occupancy_target} pct={data.occupancy_progress_pct} unit="%" />
        </div>
      ) : (
        <p className="text-[11px] text-stone-400">Hedef belirleyin — bu ayın gerçekleşmesi renkli çubuklarda izlensin (yeşil ≥%100, sarı ≥%60, kırmızı altı).</p>
      )}
    </div>
  );
};
