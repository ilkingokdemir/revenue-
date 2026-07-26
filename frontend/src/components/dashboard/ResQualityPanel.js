import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldCheck, Wrench, Warning } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/res-quality`;

const SEV_CLS = {
  high: "bg-rose-50 text-rose-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-stone-100 text-stone-600",
};

export default function ResQualityPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(14);
  const [fixing, setFixing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${propertyId}?days=${days}`);
      setData(r.data);
    } catch { toast.error("Kalite taraması yüklenemedi"); }
  }, [propertyId, days]);
  useEffect(() => { load(); }, [load]);

  async function autofix() {
    setFixing(true);
    try {
      const r = await axios.post(`${API}/${propertyId}/autofix`);
      toast.success(`Otomatik düzeltme: ${r.data.fixed_email} e-posta + ${r.data.fixed_phone} telefon profillerden tamamlandı`);
      load();
    } catch { toast.error("Autofix çalıştırılamadı"); }
    setFixing(false);
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-4" data-testid="res-quality-panel">
      <div className="bg-gradient-to-br from-stone-900 via-indigo-950 to-blue-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-blue-300">
              <ShieldCheck size={14} /> Quality Check
            </div>
            <h1 className="text-2xl font-bold mt-1">Rezervasyon Kalite Kontrolü</h1>
            <p className="text-sm text-stone-300 mt-1">Misafir gelmeden rezervasyon hatalarını yakala: eksik iletişim, atanmamış oda, sıfır fiyat, çift kayıt.</p>
          </div>
          <div className="flex items-center gap-2">
            <select value={days} onChange={e => setDays(Number(e.target.value))} data-testid="rq-days-select"
              className="px-2 py-2 text-xs rounded-lg bg-white/10 border border-white/20 text-white">
              <option value={7} className="text-stone-900">7 gün</option>
              <option value={14} className="text-stone-900">14 gün</option>
              <option value={30} className="text-stone-900">30 gün</option>
            </select>
            <button onClick={autofix} disabled={fixing} data-testid="rq-autofix-btn"
              className="px-4 py-2 bg-blue-400 hover:bg-blue-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2 disabled:opacity-60">
              <Wrench size={16} /> {fixing ? "Düzeltiliyor…" : "Otomatik Düzelt"}
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
          <Stat label="Taranan varış" value={data.scanned} testid="rq-stat-scanned" />
          <Stat label="Temiz" value={data.clean} testid="rq-stat-clean" />
          <Stat label="Sorunlu" value={data.with_issues} warn={data.with_issues > 0} testid="rq-stat-issues" />
          <Stat label="Kalite skoru" value={`%${data.quality_score}`} testid="rq-stat-score" />
        </div>
      </div>

      {(data.by_code || []).length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="rq-by-code">
          {data.by_code.map(b => (
            <span key={b.code} className={`text-xs px-3 py-1.5 rounded-full font-semibold ${SEV_CLS[b.severity]}`}>
              {b.label}: {b.count}
            </span>
          ))}
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="text-left px-4 py-2">Misafir</th><th className="text-left px-2 py-2">Varış</th>
            <th className="text-left px-2 py-2">Oda</th><th className="text-left px-2 py-2">Tesis</th>
            <th className="text-left px-2 py-2">Sorunlar</th>
          </tr></thead>
          <tbody>
            {(data.issues || []).map(i => (
              <tr key={i.booking_id} className="border-b border-stone-50" data-testid={`rq-issue-${i.booking_id}`}>
                <td className="px-4 py-2">
                  <div className="font-medium text-stone-800">{i.guest_name || "—"}</div>
                  <div className="text-[10px] text-stone-400 font-mono">{i.booking_ref || i.booking_id.slice(0, 8)}</div>
                </td>
                <td className="px-2 py-2 font-mono text-xs">{i.check_in}</td>
                <td className="px-2 py-2 text-xs">{i.room}</td>
                <td className="px-2 py-2 text-xs text-stone-500">{i.property_id}</td>
                <td className="px-2 py-2">
                  <div className="flex flex-wrap gap-1">
                    {i.problems.map(p => (
                      <span key={p.code} className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${SEV_CLS[p.severity]}`}>
                        {p.severity === "high" && <Warning size={9} className="inline mr-0.5" />}{p.label}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
            {(!data.issues || data.issues.length === 0) && (
              <tr><td colSpan={5} className="px-4 py-10 text-center text-emerald-600 text-sm font-medium" data-testid="rq-all-clean">
                ✓ Harika — yaklaşan tüm rezervasyonlar temiz!
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, warn, testid }) {
  return (
    <div className={`rounded-xl p-3 ${warn ? "bg-rose-500/20" : "bg-white/10"}`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
    </div>
  );
}
