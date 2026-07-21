import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ClockCounterClockwise, GridFour } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const CH_TR = {
  booking_com: "Booking.com", airbnb: "Airbnb", expedia: "Expedia", agoda: "Agoda",
  hotels_com: "Hotels.com", trip_com: "Trip.com", google_hotels: "Google Hotels", trivago: "Trivago",
};
const STATUS_CLS = {
  succeeded: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  failed: "bg-rose-100 text-rose-700",
  dead_letter: "bg-rose-200 text-rose-800",
};
const fmtT = (iso) => iso ? new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

function cellCls(age) {
  if (age === null || age === undefined) return "bg-stone-100 text-stone-400";
  if (age <= 24) return "bg-emerald-200 text-emerald-900";
  if (age <= 72) return "bg-amber-200 text-amber-900";
  return "bg-rose-200 text-rose-900";
}

export default function ChannelPushHistory({ propertyId }) {
  const [hist, setHist] = useState(null);
  const [fresh, setFresh] = useState(null);
  const [channel, setChannel] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [h, f] = await Promise.all([
        axios.get(`${API}/api/push-history/${propertyId}?channel=${channel}&days=7&limit=60`),
        axios.get(`${API}/api/push-history/${propertyId}/freshness?days=14`),
      ]);
      setHist(h.data);
      setFresh(f.data);
    } catch { toast.error("Push geçmişi yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, channel]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="push-history-loading">Yükleniyor…</div>;

  return (
    <div className="space-y-5" data-testid="push-history-section">
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="freshness-matrix">
        <div className="px-4 py-3 border-b border-stone-100 flex items-center gap-2">
          <GridFour size={15} className="text-stone-400" />
          <div>
            <h3 className="text-sm font-semibold text-stone-900">Tazelik matrisi — kanal × tarih (14 gün)</h3>
            <p className="text-[10px] text-stone-400">Her hücre o tarihin ilgili kanala en son ne zaman push'landığını gösterir. <span className="text-emerald-600">●≤24s</span> <span className="text-amber-600">●≤72s</span> <span className="text-rose-600">●eski</span> <span className="text-stone-400">●hiç</span></p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="text-[10px] border-collapse">
            <thead>
              <tr>
                <th className="text-left px-3 py-1.5 text-stone-400 font-medium sticky left-0 bg-white">Kanal</th>
                {fresh?.dates.map((d) => (
                  <th key={d} className="px-1 py-1.5 text-stone-400 font-medium whitespace-nowrap">{d.slice(8)}/{d.slice(5, 7)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fresh?.matrix.map((row) => (
                <tr key={row.channel}>
                  <td className="px-3 py-1 font-medium text-stone-700 whitespace-nowrap sticky left-0 bg-white">{CH_TR[row.channel] || row.channel}</td>
                  {row.cells.map((c) => (
                    <td key={c.date} className="p-0.5">
                      <div title={c.last_pushed_at ? `Son push: ${fmtT(c.last_pushed_at)} (${c.age_hours}s önce)` : "Hiç push'lanmadı"}
                        className={`h-5 w-9 rounded flex items-center justify-center font-medium ${cellCls(c.age_hours)}`}>
                        {c.age_hours === null ? "—" : c.age_hours <= 24 ? "✓" : `${Math.round(c.age_hours)}s`}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {hist?.stats?.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="push-stats">
          {hist.stats.map((s) => (
            <div key={s.channel} className="bg-white border border-stone-200 rounded-xl p-3">
              <div className="text-xs font-semibold text-stone-800">{CH_TR[s.channel] || s.channel}</div>
              <div className="text-[11px] text-stone-500 mt-1">
                {s.succeeded}/{s.total} başarılı · {s.failed} hata
                {s.avg_latency_sec !== null && <> · ort. {s.avg_latency_sec}sn</>}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="push-timeline">
        <div className="px-4 py-3 border-b border-stone-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ClockCounterClockwise size={15} className="text-stone-400" />
            <h3 className="text-sm font-semibold text-stone-900">Push zaman çizelgesi (son 7 gün)</h3>
          </div>
          <select value={channel} onChange={(e) => setChannel(e.target.value)} data-testid="push-channel-filter"
            className="text-xs border border-stone-200 rounded-lg px-2 py-1.5 bg-white">
            <option value="all">Tüm kanallar</option>
            {Object.entries(CH_TR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        {hist?.timeline.length === 0 ? (
          <div className="px-4 py-6 text-xs text-stone-400">Bu dönemde push kaydı yok — fiyat/müsaitlik güncellemeleri yapıldıkça burada listelenecek.</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wide text-stone-400 border-b border-stone-100">
                <th className="text-left px-4 py-2 font-medium">Zaman</th>
                <th className="text-left px-2 py-2 font-medium">Kanal</th>
                <th className="text-left px-2 py-2 font-medium">Tür</th>
                <th className="text-left px-2 py-2 font-medium">Hedef tarih</th>
                <th className="text-right px-2 py-2 font-medium">Değer</th>
                <th className="text-right px-2 py-2 font-medium">Gecikme</th>
                <th className="text-right px-4 py-2 font-medium">Durum</th>
              </tr>
            </thead>
            <tbody>
              {hist.timeline.map((t) => (
                <tr key={t.id} className="border-b border-stone-50 last:border-0">
                  <td className="px-4 py-2 text-xs text-stone-500">{fmtT(t.created_at)}</td>
                  <td className="px-2 py-2 text-xs font-medium text-stone-800">{CH_TR[t.channel] || t.channel}</td>
                  <td className="px-2 py-2 text-xs text-stone-600">{t.kind === "rate" ? "Fiyat" : t.kind === "availability" ? "Müsaitlik" : t.kind}</td>
                  <td className="px-2 py-2 text-xs text-stone-600">{t.date || "—"}</td>
                  <td className="px-2 py-2 text-right text-xs font-medium text-stone-800">{t.rate !== undefined && t.rate !== null ? `£${t.rate}` : t.availability !== undefined && t.availability !== null ? t.availability : "—"}</td>
                  <td className="px-2 py-2 text-right text-xs text-stone-500">{t.latency_sec !== null ? `${t.latency_sec}sn` : "—"}</td>
                  <td className="px-4 py-2 text-right">
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${STATUS_CLS[t.status] || "bg-stone-100 text-stone-500"}`}>{t.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
