import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Briefcase, Lightning } from "@phosphor-icons/react";
import { Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RevPAMPanel({ propertyId }) {
  const pid = propertyId && propertyId !== "all" ? propertyId : "default";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/revpam/${pid}?days=14`);
      setData(d);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const applyAll = async (sp) => {
    setApplying(sp.id);
    try {
      const { data: r } = await axios.post(`${API}/revpam/${pid}/apply`, {
        space_id: sp.id,
        overrides: sp.days.map((d) => ({ date: d.date, rate_per_unit: d.suggested_rate })),
      });
      toast.success(`${r.applied} günlük dinamik fiyat uygulandı`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Uygulanamadı"); }
    finally { setApplying(null); }
  };

  if (loading) return <div className="p-10 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-stone-400" /></div>;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="revpam-panel">
      <div>
        <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
          <Briefcase size={22} weight="fill" className="text-indigo-600" /> Toplantı Salonu RevPAM
        </h1>
        <p className="text-sm text-stone-500 mt-0.5">
          Salon fiyatlarını doluluk + haftagünü talebine göre dinamikleştirin.
          RevPASH = 30 günlük gelir / mevcut koltuk-saat. Uygulanan fiyatlar rezervasyon motoruna anında yansır.
        </p>
      </div>

      {data?.summary && (
        <div className="grid grid-cols-3 gap-3">
          <div className="p-4 rounded-2xl bg-indigo-50 border border-indigo-200" data-testid="revpam-revenue-card">
            <div className="text-[10px] uppercase font-bold text-indigo-600">Salon geliri (30g)</div>
            <div className="text-lg font-black text-indigo-900">{data.summary.total_revenue_30d}</div>
          </div>
          <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="revpam-util-card">
            <div className="text-[10px] uppercase font-bold text-stone-400">Ø doluluk</div>
            <div className="text-lg font-black text-stone-900">%{data.summary.avg_utilization_pct}</div>
          </div>
          <div className="p-4 rounded-2xl bg-white border border-stone-200" data-testid="revpam-rooms-card">
            <div className="text-[10px] uppercase font-bold text-stone-400">Toplantı salonu</div>
            <div className="text-lg font-black text-stone-900">{data.summary.meeting_rooms}</div>
          </div>
        </div>
      )}

      {data?.hint && <p className="text-sm text-stone-500 bg-amber-50 border border-amber-200 rounded-xl p-4" data-testid="revpam-hint">{data.hint}</p>}

      {(data?.spaces || []).map((sp) => (
        <div key={sp.id} className="bg-white border border-stone-200 rounded-2xl p-5 space-y-3" data-testid={`revpam-space-${sp.id}`}>
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h2 className="text-sm font-black text-stone-900">{sp.name}</h2>
              <p className="text-[11px] text-stone-500">
                {sp.capacity} kişi · baz {sp.rate_per_unit}/saat · 30g gelir {sp.revenue_30d} ·
                doluluk %{sp.utilization_pct} · <span className="font-bold text-indigo-700">RevPASH {sp.revpash}</span>
              </p>
            </div>
            <button onClick={() => applyAll(sp)} disabled={applying === sp.id} data-testid={`revpam-apply-${sp.id}`}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold disabled:opacity-50">
              {applying === sp.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Lightning size={14} weight="fill" />}
              14 günü dinamik fiyata geçir
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs" data-testid={`revpam-days-${sp.id}`}>
              <thead className="bg-stone-50 text-stone-500 uppercase text-[10px]">
                <tr>
                  <th className="px-2 py-1.5 text-left">Tarih</th>
                  <th className="px-2 py-1.5 text-right">Dolu saat</th>
                  <th className="px-2 py-1.5 text-right">Doluluk</th>
                  <th className="px-2 py-1.5 text-right">Çarpan</th>
                  <th className="px-2 py-1.5 text-right">Önerilen /saat</th>
                  <th className="px-2 py-1.5 text-right">Uygulanan</th>
                </tr>
              </thead>
              <tbody>
                {sp.days.map((d) => (
                  <tr key={d.date} className="border-t border-stone-100">
                    <td className="px-2 py-1 font-semibold text-stone-800">{d.date} <span className="text-stone-400">{d.dow}</span></td>
                    <td className="px-2 py-1 text-right">{d.booked_hours}</td>
                    <td className="px-2 py-1 text-right">%{d.util_pct}</td>
                    <td className={`px-2 py-1 text-right font-bold ${d.multiplier > 1 ? "text-emerald-700" : d.multiplier < 1 ? "text-amber-700" : "text-stone-600"}`}>×{d.multiplier}</td>
                    <td className="px-2 py-1 text-right font-black text-indigo-700">{d.suggested_rate}</td>
                    <td className="px-2 py-1 text-right text-stone-500">{d.current_override ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
