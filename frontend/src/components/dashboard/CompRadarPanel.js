import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Crosshair, ArrowsClockwise, TrendUp, TrendDown, PaperPlaneTilt, CheckCircle, X } from "@phosphor-icons/react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend } from "recharts";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt0 = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

export default function CompRadarPanel({ propertyId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [pushing, setPushing] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/comp-radar/${propertyId}?days=14`);
      setData(r.data);
    } catch { toast.error("Rakip radarı yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const scan = async () => {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/api/comp-radar/scan`, { property_id: propertyId });
      toast.success(`Tarama tamam: ${r.data.scans} fiyat noktası, ${r.data.findings} bulgu`);
      await load();
    } catch { toast.error("Tarama başarısız"); }
    finally { setScanning(false); }
  };

  const applyPush = async () => {
    if (!confirm) return;
    setPushing(true);
    try {
      const r = await axios.post(`${API}/api/comp-radar/apply`, {
        property_id: confirm.property_id, date: confirm.date,
      });
      toast.success(`£${r.data.new_rate} fiyatı ${r.data.channels_succeeded}/${r.data.channels_total} kanala push'landı`);
      setConfirm(null);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Push başarısız");
    } finally { setPushing(false); }
  };

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="comp-radar-loading">Yükleniyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const s = data.summary;
  const chart = data.series.map((p) => ({ ...p, label: `${p.date.slice(8)}/${p.date.slice(5, 7)}` }));

  return (
    <div className="space-y-5" data-testid="comp-radar-panel">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Crosshair size={12} weight="fill" className="text-indigo-600" />
            <span>Rakip Fiyat Radarı</span>
          </div>
          <h2 className="text-xl font-semibold text-stone-900">Fiyatınız pazara göre nerede?</h2>
          <p className="text-xs text-stone-500 mt-1">
            {data.last_scanned_at ? `Son tarama: ${new Date(data.last_scanned_at).toLocaleString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}` : "Henüz tarama yapılmadı"} — motor her gece rakip fiyatlarını tarayıp fırsatları işaretler.
          </p>
        </div>
        <button onClick={scan} disabled={scanning} data-testid="comp-radar-scan-btn"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-white bg-stone-900 rounded-lg px-4 py-2 hover:bg-stone-800 disabled:opacity-50">
          <ArrowsClockwise size={14} className={scanning ? "animate-spin" : ""} />
          {scanning ? "Taranıyor…" : "Şimdi tara"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="radar-underpriced">
          <div className="flex items-center gap-1.5 text-emerald-600"><TrendUp size={16} weight="fill" /><span className="text-2xl font-bold">{s.underpriced}</span></div>
          <div className="text-[11px] text-stone-500 mt-1">Fiyat artış fırsatı (pazar altındasınız)</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="radar-overpriced">
          <div className="flex items-center gap-1.5 text-rose-600"><TrendDown size={16} weight="fill" /><span className="text-2xl font-bold">{s.overpriced}</span></div>
          <div className="text-[11px] text-stone-500 mt-1">Doluluk riski (pazar üstündesiniz)</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="radar-total">
          <div className="flex items-center gap-1.5 text-stone-700"><Crosshair size={16} weight="fill" /><span className="text-2xl font-bold">{s.total}</span></div>
          <div className="text-[11px] text-stone-500 mt-1">Toplam bulgu (14 gün)</div>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="radar-chart">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Bizim fiyat vs rakip medyanı (14 gün)</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chart}>
            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `£${v}`} />
            <Tooltip formatter={(v) => fmt0(v)} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="own" name="Bizim fiyat" stroke="#292524" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="comp_median" name="Rakip medyanı" stroke="#6366f1" strokeWidth={2} strokeDasharray="5 3" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="radar-findings">
        <div className="px-4 py-3 border-b border-stone-100">
          <h3 className="text-sm font-semibold text-stone-900">Bulgular & öneriler ({data.findings.length})</h3>
        </div>
        {data.findings.length === 0 ? (
          <div className="px-4 py-6 text-xs text-stone-400">Bulgu yok — fiyatlarınız pazar bandında. "Şimdi tara" ile güncel tarama yapabilirsiniz.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-stone-400 border-b border-stone-100">
                <th className="text-left px-4 py-2 font-medium">Tarih</th>
                <th className="text-right px-2 py-2 font-medium">Bizim</th>
                <th className="text-right px-2 py-2 font-medium">Rakip medyan</th>
                <th className="text-right px-2 py-2 font-medium">Fark</th>
                <th className="text-right px-2 py-2 font-medium">Önerilen</th>
                <th className="text-left px-4 py-2 font-medium">Öneri</th>
                <th className="text-right px-4 py-2 font-medium">Aksiyon</th>
              </tr>
            </thead>
            <tbody>
              {data.findings.map((f, i) => (
                <tr key={i} className="border-b border-stone-50 last:border-0" data-testid={`finding-${f.date}`}>
                  <td className="px-4 py-2 text-xs font-medium text-stone-800">{f.date}</td>
                  <td className="px-2 py-2 text-right text-xs font-medium">{fmt0(f.own_rate)}</td>
                  <td className="px-2 py-2 text-right text-xs text-stone-600">{fmt0(f.comp_median)} <span className="text-stone-400">({f.comp_count} rakip)</span></td>
                  <td className={`px-2 py-2 text-right text-xs font-bold ${f.type === "underpriced" ? "text-emerald-600" : "text-rose-600"}`}>%{f.gap_pct}</td>
                  <td className="px-2 py-2 text-right text-xs font-bold text-indigo-600">{fmt0(f.suggested_rate)}</td>
                  <td className="px-4 py-2 text-xs text-stone-600">{f.message.split(": ").slice(1).join(": ")}</td>
                  <td className="px-4 py-2 text-right">
                    {f.applied ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 rounded-full px-2.5 py-1" data-testid={`applied-badge-${f.date}`}>
                        <CheckCircle size={12} weight="fill" /> Push'landı £{Number(f.applied_rate).toFixed(0)}
                      </span>
                    ) : (
                      <button onClick={() => setConfirm(f)} data-testid={`apply-push-btn-${f.date}`}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg px-2.5 py-1.5 transition-colors">
                        <PaperPlaneTilt size={12} weight="fill" /> Uygula & Push
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {confirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => !pushing && setConfirm(null)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()} data-testid="apply-push-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-stone-900">Fiyatı Uygula & OTA'lara Push'la</h3>
              <button onClick={() => setConfirm(null)} disabled={pushing}><X size={16} /></button>
            </div>
            <div className="text-xs text-stone-500 mb-3">{confirm.date} — {confirm.type === "underpriced" ? "fiyat artış fırsatı" : "doluluk riski, fiyat indirimi"}</div>
            <div className="flex items-center justify-center gap-4 bg-stone-50 rounded-xl p-4 mb-4">
              <div className="text-center">
                <div className="text-[10px] uppercase tracking-wide text-stone-400 mb-1">Mevcut</div>
                <div className="text-xl font-bold text-stone-500 line-through" data-testid="confirm-old-rate">{fmt0(confirm.own_rate)}</div>
              </div>
              <div className="text-stone-300 text-xl">→</div>
              <div className="text-center">
                <div className="text-[10px] uppercase tracking-wide text-indigo-400 mb-1">Yeni</div>
                <div className={`text-xl font-bold ${confirm.type === "underpriced" ? "text-emerald-600" : "text-rose-600"}`} data-testid="confirm-new-rate">{fmt0(confirm.suggested_rate)}</div>
              </div>
            </div>
            <p className="text-[11px] text-stone-500 mb-4">
              Yeni fiyat sync kuyruğuna eklenir ve bağlı tüm OTA kanallarına anında push'lanır. Sonuç, Kanal Push Geçmişi'nde görünür.
            </p>
            <div className="flex gap-2">
              <button onClick={() => setConfirm(null)} disabled={pushing}
                className="flex-1 py-2 text-sm text-stone-600 border border-stone-300 rounded-lg" data-testid="confirm-cancel-btn">Vazgeç</button>
              <button onClick={applyPush} disabled={pushing} data-testid="confirm-push-btn"
                className="flex-1 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 inline-flex items-center justify-center gap-1.5">
                <PaperPlaneTilt size={14} weight="fill" className={pushing ? "animate-pulse" : ""} />
                {pushing ? "Push'lanıyor…" : "Onayla & Push'la"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
