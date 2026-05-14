import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ChartBar, Clock, Lightning } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/automation/v2/analytics`;

export default function AutomationAnalyticsPanel() {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [selectedRule, setSelectedRule] = useState(null);
  const [detail, setDetail] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}?days=${days}`, { withCredentials: true });
      setData(r.data);
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, [days]);

  useEffect(() => { reload(); }, [reload]);

  async function loadDetail(ruleId) {
    setSelectedRule(ruleId);
    try {
      const r = await axios.get(`${API}/${ruleId}?days=90`, { withCredentials: true });
      setDetail(r.data);
    } catch (e) { toast.error("Detay yüklenemedi"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="automation-analytics-panel">
      <div className="mb-4 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <ChartBar size={12} weight="fill" className="text-violet-500" />
            <span>Automation ROI</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Otomasyon Analitiği</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Her kuralın çalışma sayısı, başarı oranı ve tasarruf edilen tahmini personel saatleri.
          </p>
        </div>
        <select value={days} onChange={e => setDays(Number(e.target.value))}
                className="px-3 py-1.5 text-xs border border-stone-300 rounded-lg" data-testid="aa-period-select">
          <option value={7}>Son 7 gün</option>
          <option value={30}>Son 30 gün</option>
          <option value={90}>Son 90 gün</option>
        </select>
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            <KPI label="Toplam Kural" value={data.total_rules} icon={Lightning} color="text-violet-500" />
            <KPI label="Çalıştırma" value={data.total_runs} icon={ChartBar} color="text-sky-500" />
            <KPI label="Saat Kazancı" value={`${data.total_hours_saved}sa`} icon={Clock} color="text-emerald-500" />
            <KPI label="Dakika Kazancı" value={data.total_minutes_saved} icon={Clock} color="text-amber-500" />
          </div>

          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold">Kural Sıralaması (en çok çalışan üstte)</div>
            {data.rules.length === 0 ? (
              <div className="text-center py-12 text-stone-400 text-sm" data-testid="aa-empty">Bu periyotta çalışan kural yok.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                  <tr>
                    <th className="px-4 py-2 text-left">Kural</th>
                    <th className="px-4 py-2 text-left">Tetik</th>
                    <th className="px-4 py-2 text-right">Çalışma</th>
                    <th className="px-4 py-2 text-right">Başarı %</th>
                    <th className="px-4 py-2 text-right">Saat Kazancı</th>
                    <th className="px-4 py-2 text-left">Durum</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rules.map(r => (
                    <tr key={r.id} onClick={() => loadDetail(r.id)}
                        className={`border-t border-stone-100 cursor-pointer hover:bg-stone-50 ${selectedRule === r.id ? "bg-violet-50" : ""}`}
                        data-testid={`aa-row-${r.id}`}>
                      <td className="px-4 py-2 font-medium">{r.name}</td>
                      <td className="px-4 py-2 text-xs">{r.trigger}</td>
                      <td className="px-4 py-2 text-right">{r.runs_count}</td>
                      <td className="px-4 py-2 text-right">{Math.round((r.success_rate || 0) * 100)}%</td>
                      <td className="px-4 py-2 text-right font-medium text-emerald-600">{r.hours_saved}sa</td>
                      <td className="px-4 py-2">{r.enabled ? <span className="text-emerald-600 text-xs">Aktif</span> : <span className="text-stone-400 text-xs">Pasif</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {detail && (
            <div className="mt-5 bg-white border border-stone-200 rounded-xl p-4" data-testid="aa-detail">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-base font-semibold">{detail.rule?.name}</h3>
                  <p className="text-xs text-stone-500">Son 90 gün: {detail.total_runs} çalışma</p>
                </div>
                <button onClick={() => { setDetail(null); setSelectedRule(null); }} className="text-stone-400 text-xs">Kapat</button>
              </div>
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-wider text-stone-500">Son Çalıştırmalar</div>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {(detail.recent_runs || []).map(run => (
                    <div key={run.id} className="flex items-center gap-2 text-xs">
                      <span className={`w-2 h-2 rounded-full ${run.ok ? "bg-emerald-500" : "bg-rose-500"}`}></span>
                      <span className="text-stone-500">{new Date(run.created_at).toLocaleString("tr-TR")}</span>
                      <span className="ml-auto text-stone-600">{(run.actions || []).length} aksiyon</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function KPI({ label, value, icon: Icon, color }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-3">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-stone-500">
        <Icon size={12} weight="fill" className={color} />
        {label}
      </div>
      <div className="text-xl font-semibold mt-1">{value}</div>
    </div>
  );
}
