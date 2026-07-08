import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CalendarCheck, Sparkle, UsersThree, ArrowsClockwise, MagicWand } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const dayLabel = (ds) => {
  const d = new Date(ds + "T12:00:00");
  return d.toLocaleDateString("tr-TR", { weekday: "short", day: "numeric", month: "short" });
};

export default function PredictiveHkPanel({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState("");
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/housekeeping/predictive/${propertyId}?days=7`);
      setData(res.data);
      setSelected((prev) => prev || res.data.forecast?.[0]?.date || null);
    } catch (e) {
      toast.error("Tahmin verisi yüklenemedi");
    } finally {
      setLoading(false);
    }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const generate = async (date) => {
    setGenerating(date);
    try {
      const res = await axios.post(`${API}/api/housekeeping/predictive/${propertyId}/generate`, { date });
      toast.success(`${res.data.created} görev oluşturuldu${res.data.skipped_duplicates ? `, ${res.data.skipped_duplicates} kopya atlandı` : ""}`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Görev üretimi başarısız");
    } finally {
      setGenerating("");
    }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="predictive-hk-loading">Tahmin hesaplanıyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const maxLoad = Math.max(...data.forecast.map((d) => d.workload_minutes), 1);
  const sel = data.forecast.find((d) => d.date === selected);

  return (
    <div className="space-y-5" data-testid="predictive-hk-panel">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 bg-white border border-stone-200 rounded-lg px-4 py-2.5">
          <CalendarCheck size={18} className="text-cyan-600" />
          <div>
            <div className="text-lg font-semibold text-stone-900" data-testid="predictive-total-hours">{data.total_workload_hours} saat</div>
            <div className="text-[11px] text-stone-500">7 günlük toplam iş yükü</div>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-white border border-stone-200 rounded-lg px-4 py-2.5">
          <Sparkle size={18} className="text-amber-500" />
          <div>
            <div className="text-lg font-semibold text-stone-900">{data.peak_day ? dayLabel(data.peak_day) : "—"}</div>
            <div className="text-[11px] text-stone-500">En yoğun gün</div>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-white border border-stone-200 rounded-lg px-4 py-2.5">
          <UsersThree size={18} className="text-emerald-600" />
          <div>
            <div className="text-lg font-semibold text-stone-900">{data.housekeeper_count}</div>
            <div className="text-[11px] text-stone-500">Aktif kat görevlisi</div>
          </div>
        </div>
        <button onClick={load} data-testid="predictive-refresh-btn"
          className="ml-auto inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-2 bg-white transition-colors">
          <ArrowsClockwise size={14} /> Yenile
        </button>
      </div>

      <div className="grid grid-cols-7 gap-2">
        {data.forecast.map((d) => {
          const active = d.date === selected;
          const pct = Math.round((d.workload_minutes / maxLoad) * 100);
          return (
            <button key={d.date} onClick={() => setSelected(d.date)} data-testid={`predictive-day-${d.date}`}
              className={`rounded-lg border p-3 text-left transition-all ${active ? "border-cyan-500 bg-cyan-50" : "border-stone-200 bg-white hover:border-stone-300"}`}>
              <div className="text-[11px] font-medium text-stone-500">{dayLabel(d.date)}</div>
              <div className="text-lg font-semibold text-stone-900">{d.workload_hours}s</div>
              <div className="h-1.5 bg-stone-100 rounded-full mt-1.5 overflow-hidden">
                <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${pct}%` }} />
              </div>
              <div className="mt-1.5 text-[10px] text-stone-500">
                {d.departure_count}↑ {d.arrival_count}↓ {d.stayover_count}⟳
              </div>
              <div className="text-[10px] font-medium text-emerald-700 mt-0.5">{d.staff_needed} personel</div>
            </button>
          );
        })}
      </div>

      {sel && (
        <div className="bg-white border border-stone-200 rounded-lg p-5" data-testid="predictive-day-detail">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-stone-900">{dayLabel(sel.date)} — Görev Planı</h3>
              <p className="text-xs text-stone-500 mt-0.5">
                {sel.departure_count} check-out temizliği (45dk) · {sel.stayover_count} tazeleme (20dk) · {sel.arrival_count} varış kontrolü (10dk)
                {sel.existing_auto_tasks > 0 && <span className="text-emerald-600"> · {sel.existing_auto_tasks} otomatik görev mevcut</span>}
              </p>
            </div>
            <button onClick={() => generate(sel.date)} disabled={generating === sel.date || propertyId === "all"}
              data-testid="predictive-generate-btn"
              className="inline-flex items-center gap-1.5 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-xs font-medium rounded-lg px-4 py-2 transition-colors">
              <MagicWand size={14} />
              {generating === sel.date ? "Oluşturuluyor…" : "Görevleri Otomatik Oluştur"}
            </button>
          </div>
          <div className="grid md:grid-cols-3 gap-4">
            {[["Check-out Temizliği", sel.departures, "text-rose-600"],
              ["Varış Kontrolü", sel.arrivals, "text-emerald-600"],
              ["Konaklama Tazeleme", sel.stayovers, "text-amber-600"]].map(([title, items, color]) => (
              <div key={title}>
                <div className={`text-[11px] font-semibold uppercase tracking-wide ${color} mb-2`}>{title} ({items.length})</div>
                {items.length === 0 ? (
                  <div className="text-xs text-stone-400">Yok</div>
                ) : (
                  <ul className="space-y-1.5">
                    {items.slice(0, 8).map((it) => (
                      <li key={it.booking_id} className="text-xs text-stone-700 flex justify-between gap-2">
                        <span className="font-medium truncate">{it.room || "Atanmamış"}</span>
                        <span className="text-stone-400 truncate">{it.guest}</span>
                      </li>
                    ))}
                    {items.length > 8 && <li className="text-[11px] text-stone-400">+{items.length - 8} daha</li>}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
