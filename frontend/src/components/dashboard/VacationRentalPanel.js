/**
 * VacationRentalPanel — Eviivo + Lighthouse-style dedicated dashboard for
 * short-term rental / apartment-style properties.
 *
 * Shows VR-focused KPIs (occupancy, ADR, RevPAR), per-unit performance,
 * and a calendar heatmap for the next N days.
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { House, CalendarBlank, ChartLineUp } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/vacation-rental`;

export default function VacationRentalPanel() {
  const [year, setYear] = useState(new Date().getFullYear().toString());
  const [summary, setSummary] = useState(null);
  const [calendar, setCalendar] = useState(null);
  const [days, setDays] = useState(14);

  const reload = useCallback(async () => {
    try {
      const s = await axios.get(`${API}/summary?year=${year}`, { withCredentials: true });
      setSummary(s.data);
      const c = await axios.get(`${API}/calendar?days=${days}`, { withCredentials: true });
      setCalendar(c.data);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [year, days]);

  useEffect(() => { reload(); }, [reload]);

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="vacation-rental-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">Vacation Rental Suite</div>
          <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
            <House size={22} weight="fill" className="text-teal-600" /> Apart & Kısa-Dönem Kiralama
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            Apartman tipi mülklere odaklanmış birleşik gösterge paneli (Eviivo + Lighthouse parity).
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <select value={year} onChange={e => setYear(e.target.value)} data-testid="vr-year-select"
                  className="px-3 py-1.5 text-sm border border-stone-300 rounded-lg bg-white">
            {[0,-1,-2].map(d => {
              const y = (new Date().getFullYear()+d).toString();
              return <option key={y} value={y}>{y}</option>;
            })}
          </select>
          <select value={days} onChange={e => setDays(parseInt(e.target.value))} data-testid="vr-days-select"
                  className="px-3 py-1.5 text-sm border border-stone-300 rounded-lg bg-white">
            <option value={7}>7 gün</option>
            <option value={14}>14 gün</option>
            <option value={30}>30 gün</option>
          </select>
        </div>
      </div>

      {summary?.kpis && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-5">
          <KPI label="Mülk Sayısı" value={summary.kpis.property_count} />
          <KPI label="Birim Sayısı" value={summary.kpis.unit_count} />
          <KPI label="Toplam Gelir" value={`£${(summary.kpis.total_revenue||0).toLocaleString("tr-TR")}`} color="text-emerald-600" />
          <KPI label="Doluluk" value={`%${summary.kpis.occupancy_percent}`} />
          <KPI label="ADR" value={`£${summary.kpis.adr}`} />
          <KPI label="RevPAR" value={`£${summary.kpis.revpar}`} color="text-teal-600" />
          <KPI label="Rezervasyon" value={summary.kpis.booking_count} />
        </div>
      )}

      {summary?.properties && summary.properties.length > 0 && (
        <div className="mb-5 bg-white border border-stone-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold mb-2 inline-flex items-center gap-1.5">
            <ChartLineUp size={14} weight="fill" className="text-teal-600" /> VR Mülk Listesi
          </h3>
          <div className="flex flex-wrap gap-2">
            {summary.properties.map(p => (
              <span key={p.id} className="text-xs px-3 py-1.5 bg-teal-50 border border-teal-200 text-teal-800 rounded-lg">
                {p.name} <span className="text-stone-400">· {p.city}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold inline-flex items-center gap-1.5">
          <CalendarBlank size={14} weight="fill" /> {days} Günlük Takvim Görünümü
        </div>
        {!calendar ? (
          <div className="px-4 py-8 text-center text-stone-400 text-xs">Yükleniyor…</div>
        ) : calendar.rooms.length === 0 ? (
          <div className="px-4 py-8 text-center text-stone-400 text-xs">
            Apart tipinde mülk bulunamadı (property_type='apartment').
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs" data-testid="vr-calendar-table">
              <thead className="bg-stone-50 text-[10px] uppercase tracking-wider text-stone-500 sticky top-0">
                <tr>
                  <th className="px-2 py-2 text-left sticky left-0 bg-stone-50 z-10 min-w-[180px]">Birim</th>
                  {calendar.dates.map(d => (
                    <th key={d} className="px-1 py-2 text-center min-w-[36px]">
                      <div>{d.slice(8, 10)}</div>
                      <div className="text-[8px] text-stone-400">{d.slice(5, 7)}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {calendar.rooms.map(r => (
                  <tr key={r.room_id} className="border-t border-stone-100" data-testid={`vr-row-${r.room_id}`}>
                    <td className="px-2 py-1.5 sticky left-0 bg-white z-10">
                      <div className="font-medium">{r.room_number}</div>
                      <div className="text-[10px] text-stone-500">{r.property_name}</div>
                    </td>
                    {r.cells.map((c, i) => (
                      <td key={i} className="px-0.5 py-1">
                        <div title={c.guest_name || c.status}
                             className={`h-7 rounded ${
                               c.status === "booked"
                                 ? "bg-teal-500"
                                 : "bg-stone-100 border border-stone-200"
                             }`} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function KPI({ label, value, color }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">{label}</div>
      <div className={`text-lg font-semibold mt-1 ${color || "text-stone-900"}`}>{value}</div>
    </div>
  );
}
