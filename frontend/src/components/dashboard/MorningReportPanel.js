import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { MoonStars, Warning, Play } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const Card = ({ label, value, sub, testId }) => (
  <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid={testId}>
    <div className="text-[11px] uppercase tracking-[0.15em] text-stone-500 font-bold">{label}</div>
    <div className="text-2xl font-black text-stone-900 mt-1">{value}</div>
    {sub && <div className="text-[11px] text-stone-500 mt-1">{sub}</div>}
  </div>
);

export default function MorningReportPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [audits, setAudits] = useState([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/morning-report/${pid}?limit=7`, { withCredentials: true });
      setAudits(r.data.audits || []); setNote(r.data.note || "");
    } catch { toast.error("Gün sonu raporları yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const runNow = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/morning-report/${pid}/run`, {}, { withCredentials: true });
      const a = r.data.audit;
      toast.success((a?.anomalies?.length ?? 0) ? `Denetim tamamlandı — ${a.anomalies.length} anomali bulundu` : "Denetim tamamlandı — anomali yok");
      load();
    } catch { toast.error("Denetim çalıştırılamadı"); } finally { setBusy(false); }
  };

  const last = audits[0];

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-6" data-testid="morning-report-panel">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <MoonStars size={13} weight="fill" className="text-indigo-500" /><span>Gece Denetim Robotu</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Gün Sonu Raporları</h1>
          <p className="text-sm text-stone-500 mt-1">{note}</p>
        </div>
        <button onClick={runNow} disabled={busy} data-testid="mr-run-btn" className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-bold disabled:opacity-50 flex items-center gap-1.5"><Play size={14} weight="fill" /> Dünü Şimdi Denetle</button>
      </div>

      {last && (
        <section data-testid="mr-last-section">
          <h2 className="text-base font-bold text-stone-800 mb-2">Son Denetim — {last.date}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card testId="mr-occ" label="Doluluk" value={`%${last.occupancy_pct ?? 0}`} sub={`${last.occupied ?? 0}/${last.total_rooms ?? 0} oda · 7g ort. %${last.avg7_occupancy_pct ?? 0}`} />
            <Card testId="mr-rev" label="Oda Geliri" value={`₺${(last.room_revenue ?? 0).toLocaleString("tr-TR")}`} sub={`7g ort. ₺${(last.avg7_revenue ?? 0).toLocaleString("tr-TR")}`} />
            <Card testId="mr-adr" label="ADR" value={`₺${last.adr ?? 0}`} sub={`7g ort. ₺${last.avg7_adr ?? 0}`} />
            <Card testId="mr-moves" label="Giriş / Çıkış" value={`${last.arrivals} / ${last.departures}`} sub="dünkü hareket" />
          </div>
          <div className={`mt-3 rounded-xl border p-3.5 ${(last.anomalies?.length ?? 0) ? "bg-rose-50 border-rose-200" : "bg-emerald-50 border-emerald-200"}`} data-testid="mr-anomalies">
            {(last.anomalies?.length ?? 0) === 0 ? (
              <span className="text-sm font-bold text-emerald-800">✅ Anomali yok — her şey yolunda</span>
            ) : (
              <div>
                <div className="flex items-center gap-1.5 text-sm font-black text-rose-800 mb-1"><Warning size={15} weight="fill" /> {last.anomalies.length} anomali</div>
                <ul className="list-disc ml-5 space-y-0.5">
                  {last.anomalies.map((a, i) => <li key={i} className="text-[13px] text-rose-700" data-testid={`mr-anomaly-${i}`}>{a}</li>)}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      <section data-testid="mr-history-section">
        <h2 className="text-base font-bold text-stone-800 mb-2">Denetim Geçmişi</h2>
        {audits.length === 0 ? (
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-sm text-stone-500" data-testid="mr-empty">Henüz denetim yok — "Dünü Şimdi Denetle" ile başlatın. Robot her sabah otomatik çalışır.</div>
        ) : (
          <div className="bg-white border border-stone-200 rounded-xl overflow-x-auto">
            <table className="w-full text-sm" data-testid="mr-history-table">
              <thead><tr className="text-left text-[11px] text-stone-400 border-b border-stone-100">
                <th className="p-2.5">Tarih</th><th className="p-2.5">Doluluk</th><th className="p-2.5">Gelir</th><th className="p-2.5">ADR</th><th className="p-2.5">Giriş/Çıkış</th><th className="p-2.5">Anomali</th>
              </tr></thead>
              <tbody>
                {audits.map((a, i) => (
                  <tr key={a.date || i} className="border-t border-stone-100" data-testid={`mr-row-${a.date}`}>
                    <td className="p-2.5 font-bold">{a.date}</td>
                    <td className="p-2.5">%{a.occupancy_pct ?? 0}</td>
                    <td className="p-2.5">₺{(a.room_revenue ?? 0).toLocaleString("tr-TR")}</td>
                    <td className="p-2.5">₺{a.adr ?? 0}</td>
                    <td className="p-2.5">{a.arrivals ?? 0}/{a.departures ?? 0}</td>
                    <td className="p-2.5">
                      {(a.anomalies?.length ?? 0) ? <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 text-[11px] font-bold">{a.anomalies.length} ⚠</span>
                        : <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[11px] font-bold">Temiz</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
