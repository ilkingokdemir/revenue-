import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Pulse, Wrench, ArrowsClockwise } from "@phosphor-icons/react";
import { Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const SEV = {
  critical: { bg: "bg-rose-50 border-rose-200", chip: "bg-rose-100 text-rose-700", label: "Kritik" },
  warning: { bg: "bg-amber-50 border-amber-200", chip: "bg-amber-100 text-amber-700", label: "Uyarı" },
  info: { bg: "bg-sky-50 border-sky-200", chip: "bg-sky-100 text-sky-700", label: "Bilgi" },
};

export default function DataQualityPanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fixing, setFixing] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/data-quality/${pid}`);
      setData(d);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const fix = async (type) => {
    setFixing(type);
    try {
      const { data: r } = await axios.post(`${API}/data-quality/${pid}/fix/${type}`);
      toast.success(`${r.removed} kayıt temizlendi`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Düzeltilemedi"); }
    finally { setFixing(null); }
  };

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-stone-400" /></div>;
  if (!data) return null;
  const scoreColor = data.health_score >= 80 ? "text-emerald-600" : data.health_score >= 50 ? "text-amber-600" : "text-rose-600";

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5" data-testid="data-quality-panel">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
            <Pulse size={22} weight="fill" className="text-indigo-600" /> Data Quality Autopilot
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">
            Fiyat motorunu besleyen verideki sessiz hataları tespit eder: mapping drift, bayat envanter,
            birim hatası, mükerrer rezervasyon.
          </p>
        </div>
        <button onClick={load} data-testid="dq-rescan-btn"
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-stone-900 hover:bg-stone-700 text-white text-xs font-bold">
          <ArrowsClockwise size={14} /> Yeniden tara
        </button>
      </div>

      <div className="flex items-center gap-5 bg-white border border-stone-200 rounded-2xl p-5" data-testid="dq-score-card">
        <div className={`text-4xl font-black ${scoreColor}`}>{data.health_score}</div>
        <div>
          <p className="text-sm font-bold text-stone-800">Veri Sağlık Skoru</p>
          <p className="text-[11px] text-stone-400">{data.issues.length} sorun bulundu · son tarama: {data.history?.[0] ? new Date(data.history[0].run_at).toLocaleString("tr-TR") : "-"}</p>
        </div>
      </div>

      {data.issues.length === 0 && (
        <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-2xl p-5 text-center font-bold" data-testid="dq-clean">
          ✓ Veri kalitesi temiz — motoru besleyen tüm kaynaklar sağlıklı görünüyor.
        </p>
      )}

      <div className="space-y-2" data-testid="dq-issues">
        {data.issues.map((it) => {
          const sv = SEV[it.severity] || SEV.info;
          return (
            <div key={it.type} className={`rounded-2xl border p-4 ${sv.bg}`} data-testid={`dq-issue-${it.type}`}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex-1 min-w-[240px]">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${sv.chip}`}>{sv.label}</span>
                    <span className="text-[10px] text-stone-400 font-mono">{it.type}</span>
                  </div>
                  <p className="text-sm font-bold text-stone-800">{it.message}</p>
                  <p className="text-[11px] text-stone-500 mt-0.5">{it.suggestion}</p>
                </div>
                {it.auto_fixable && (
                  <button onClick={() => fix(it.type)} disabled={fixing === it.type} data-testid={`dq-fix-${it.type}`}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold disabled:opacity-50">
                    {fixing === it.type ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wrench size={13} weight="fill" />}
                    Güvenli düzelt
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
