import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { UserFocus, ArrowsClockwise } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/noshow-risk`;

export default function NoShowRiskPanel({ propertyId = "default" }) {
  const [data, setData] = useState(null);
  const [day, setDay] = useState("");
  const [loading, setLoading] = useState(false);
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async (d) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/${pid}${d ? `?day=${d}` : ""}`);
      setData(r.data);
      if (!d) setDay(r.data.date);
    } catch { toast.error("No-show riski yüklenemedi"); }
    setLoading(false);
  }, [pid]);
  useEffect(() => { load(""); }, [load]);

  const levelBadge = (l) =>
    l === "high" ? <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 text-xs font-bold">YÜKSEK</span>
    : l === "medium" ? <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-bold">ORTA</span>
    : <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-xs font-bold">DÜŞÜK</span>;

  return (
    <div className="p-5 max-w-[1050px] mx-auto space-y-4" data-testid="noshow-risk-panel">
      <div className="bg-gradient-to-br from-stone-900 via-rose-950 to-pink-950 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-rose-300">
              <UserFocus size={14} /> No-Show Prediction
            </div>
            <h1 className="text-2xl font-bold mt-1">No-Show Riski</h1>
            <p className="text-sm text-stone-300 mt-1">
              Yarınki girişler risk faktörleriyle puanlanır (iletişim eksikliği, ödeme, OTA, geçmiş no-show…).
              Yüksek riskliler öğleden sonra otomatik bildirimle işaretlenir.
            </p>
          </div>
          <div className="flex gap-2 items-center">
            <input type="date" value={day} onChange={(e) => { setDay(e.target.value); load(e.target.value); }}
              className="rounded-lg px-2 py-1.5 text-sm text-stone-900" data-testid="noshow-date-input" />
            <button onClick={() => load(day)} disabled={loading} data-testid="noshow-refresh-btn"
              className="px-4 py-2 rounded-full bg-rose-500 hover:bg-rose-400 text-white text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
              <ArrowsClockwise size={16} className={loading ? "animate-spin" : ""} /> Yenile
            </button>
          </div>
        </div>
        {data && (
          <div className="grid grid-cols-3 gap-3 mt-5">
            <div className="bg-white/10 rounded-xl p-3" data-testid="noshow-stat-total">
              <div className="text-2xl font-bold">{data.summary.total}</div>
              <div className="text-xs text-stone-300">Giriş ({data.date})</div>
            </div>
            <div className="bg-white/10 rounded-xl p-3" data-testid="noshow-stat-high">
              <div className={`text-2xl font-bold ${data.summary.high > 0 ? "text-rose-300" : "text-emerald-300"}`}>{data.summary.high}</div>
              <div className="text-xs text-stone-300">Yüksek risk</div>
            </div>
            <div className="bg-white/10 rounded-xl p-3">
              <div className="text-2xl font-bold text-amber-300">{data.summary.medium}</div>
              <div className="text-xs text-stone-300">Orta risk</div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Riskli Girişler</h2>
        {!data || data.items.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="noshow-empty">Bu tarih için bekleyen giriş yok.</p>
        ) : (
          <table className="w-full text-sm" data-testid="noshow-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Misafir</th><th>Oda</th><th>Kanal</th><th>Tutar</th><th>Skor</th><th>Risk</th><th>Nedenler</th><th>Öneri</th>
            </tr></thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.booking_id} className={`border-b border-stone-100 ${r.level === "high" ? "bg-rose-50" : r.level === "medium" ? "bg-amber-50/50" : ""}`}
                  data-testid={`noshow-row-${r.booking_id}`}>
                  <td className="py-2 font-medium">{r.guest_name}<div className="text-[10px] text-stone-400">{r.booking_ref}</div></td>
                  <td className="text-xs">{r.room_type || "—"}</td>
                  <td className="text-xs capitalize">{r.channel}</td>
                  <td className="text-xs">£{r.total_price}</td>
                  <td className="font-bold">{r.score}</td>
                  <td>{levelBadge(r.level)}</td>
                  <td className="text-xs text-stone-500">{r.reasons.join(", ") || "—"}</td>
                  <td className="text-xs font-medium text-indigo-700">{r.suggestion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
