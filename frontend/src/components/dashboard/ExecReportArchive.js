import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Archive, CaretUp, CaretDown, Minus, Camera } from "@phosphor-icons/react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (v) => `£${Number(v || 0).toLocaleString("tr-TR", { maximumFractionDigits: 0 })}`;

export default function ExecReportArchive({ propertyId }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/revenue-brain/${propertyId}/exec-reports`, { withCredentials: true });
      setItems(r.data.items || []);
    } catch { /* */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const snapshot = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/revenue-brain/${propertyId}/exec-reports/snapshot`, {}, { withCredentials: true });
      toast.success(`${r.data.week} haftası arşivlendi`);
      load();
    } catch { toast.error("Arşivleme başarısız"); } finally { setBusy(false); }
  };

  const delta = (idx, path) => {
    if (idx >= items.length - 1) return null;
    const cur = get(items[idx], path), prev = get(items[idx + 1], path);
    if (cur == null || prev == null) return null;
    return cur - prev;
  };

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4 mt-4" data-testid="exec-report-archive">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <div className="text-sm font-semibold text-stone-900 flex items-center gap-2">
          <Archive size={16} weight="fill" className="text-emerald-600" /> Rapor Arşivi
          <span className="text-[10px] text-stone-400 font-normal">— haftalık yönetici raporları, hafta hafta karşılaştırma</span>
        </div>
        <button onClick={snapshot} disabled={busy} data-testid="exec-archive-snapshot-btn"
          className="px-2.5 py-1.5 text-[11px] font-bold rounded-md bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 inline-flex items-center gap-1">
          <Camera size={12} weight="fill" /> {busy ? "Arşivleniyor…" : "Bu Haftayı Arşivle"}
        </button>
      </div>
      <p className="text-[11px] text-stone-500 mb-3">Her pazartesi otomatik arşivlenir; istediğiniz an manuel anlık görüntü de alabilirsiniz.</p>
      {items.length >= 2 && (
        <div className="h-44 mb-4" data-testid="exec-archive-chart">
          <div className="text-[10px] font-bold uppercase text-stone-400 mb-1">Haftalık Katkı Trendi</div>
          <ResponsiveContainer width="100%" height="88%">
            <LineChart data={[...items].reverse().map((it) => ({ week: it.week, katki: get(it, "impact.est_total_contribution") || 0 }))}
              margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" />
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: "#a8a29e" }} />
              <YAxis tick={{ fontSize: 10, fill: "#a8a29e" }} tickFormatter={(v) => `£${Number(v).toLocaleString("tr-TR")}`} width={70} />
              <Tooltip formatter={(v) => [fmt(v), "Robot katkısı"]} labelStyle={{ fontSize: 11 }} contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <ReferenceLine y={0} stroke="#d6d3d1" />
              <Line type="monotone" dataKey="katki" stroke="#059669" strokeWidth={2.5} dot={{ r: 3, fill: "#059669" }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {items.length === 0 ? (
        <div className="text-xs text-stone-500 py-4 text-center">Henüz arşivlenmiş rapor yok — ilk kayıt bu pazartesi otomatik oluşacak veya "Bu Haftayı Arşivle" ile hemen başlayın.</div>
      ) : (
        <table className="w-full text-xs">
          <thead><tr className="text-left text-stone-400 border-b border-stone-100">
            <th className="py-1.5">Hafta</th>
            <th className="text-right">Robot Katkısı</th>
            <th className="text-right">Δ önceki hafta</th>
            <th className="text-right">Ölçülen Karar</th>
            <th className="text-right">Başarı</th>
            <th className="text-right">Ay içi Gelir</th>
            <th className="text-right">Hedef İlerleme</th>
          </tr></thead>
          <tbody>
            {items.map((it, idx) => {
              const d = delta(idx, "impact.est_total_contribution");
              return (
                <tr key={it.week} className="border-b border-stone-50" data-testid={`exec-archive-row-${it.week}`}>
                  <td className="py-2 font-bold text-stone-800">{it.week}
                    <span className="text-stone-400 font-normal ml-1.5">{(it.created_at || "").slice(0, 10)}</span></td>
                  <td className={`text-right font-black ${(get(it, "impact.est_total_contribution") || 0) >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
                    {fmt(get(it, "impact.est_total_contribution"))}</td>
                  <td className="text-right"><Delta v={d} money /></td>
                  <td className="text-right text-stone-700">{get(it, "impact.outcomes_measured") ?? "—"}</td>
                  <td className="text-right text-stone-700">{get(it, "impact.success_rate") != null ? `%${get(it, "impact.success_rate")}` : "—"}</td>
                  <td className="text-right text-stone-700">{fmt(get(it, "goal.mtd_revenue"))}</td>
                  <td className="text-right text-stone-700">{get(it, "goal.progress_pct") != null ? `%${get(it, "goal.progress_pct")}` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function get(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}

function Delta({ v, money }) {
  if (v == null) return <span className="text-stone-300">—</span>;
  if (Math.abs(v) < 0.01) return <span className="text-stone-400 inline-flex items-center gap-0.5"><Minus size={10} /> 0</span>;
  const up = v > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 font-bold ${up ? "text-emerald-600" : "text-rose-600"}`}>
      {up ? <CaretUp size={10} weight="fill" /> : <CaretDown size={10} weight="fill" />}
      {money ? fmt(Math.abs(v)) : Math.abs(v)}
    </span>
  );
}
