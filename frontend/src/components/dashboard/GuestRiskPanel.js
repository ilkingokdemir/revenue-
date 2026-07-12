import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ShieldWarning, ArrowsClockwise, CalendarBlank } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
const LEVEL = {
  high: { label: "YÜKSEK", cls: "bg-rose-100 text-rose-700 border-rose-200", bar: "bg-rose-500" },
  medium: { label: "ORTA", cls: "bg-amber-100 text-amber-700 border-amber-200", bar: "bg-amber-500" },
  low: { label: "DÜŞÜK", cls: "bg-emerald-100 text-emerald-700 border-emerald-200", bar: "bg-emerald-500" },
};

export default function GuestRiskPanel({ propertyId }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(14);
  const [loading, setLoading] = useState(true);
  const [showLow, setShowLow] = useState(false);
  const [busy, setBusy] = useState("");

  const requestDeposit = async (id) => {
    setBusy(id);
    try {
      const r = await axios.post(`${API}/api/guests/risk/${id}/request-deposit`);
      toast.success(`Depozito talebi gönderildi (£${r.data.amount})`);
      load();
    } catch { toast.error("Depozito talebi başarısız"); }
    finally { setBusy(""); }
  };

  const checkDeposit = async (id) => {
    setBusy(id);
    try {
      const r = await axios.post(`${API}/api/guests/risk/${id}/deposit-status`);
      if (r.data.status === "paid") { toast.success(`Depozito ödendi (£${r.data.amount}) — folyoya işlendi`); load(); }
      else toast.info("Ödeme henüz yapılmadı");
    } catch { toast.error("Durum sorgulanamadı"); }
    finally { setBusy(""); }
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/guests/risk/arrivals/${propertyId}?days_ahead=${days}`);
      setData(r.data);
    } catch { toast.error("Risk verisi yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, days]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="guest-risk-loading">Analiz ediliyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  const rows = data.rows.filter((r) => showLow || r.level !== "low");

  return (
    <div className="space-y-6" data-testid="guest-risk-panel">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <ShieldWarning size={12} weight="fill" className="text-amber-500" />
            <span>Misafir Risk Radarı</span>
          </div>
          <h2 className="text-xl font-semibold text-stone-900">Yaklaşan varışlarda riskli misafirler</h2>
          <p className="text-xs text-stone-500 mt-1">Yüksek riskli (skor ≥60) varışlara depozito talebi her gün 12:00'de otomatik gönderilir — orta riskliler manuel kararınıza bırakılır.</p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 14, 30].map((d) => (
            <button key={d} onClick={() => setDays(d)} data-testid={`risk-days-${d}`}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${days === d ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-300"}`}>
              {d} gün
            </button>
          ))}
          <button onClick={load} data-testid="risk-refresh-btn"
            className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-1.5 bg-white transition-colors">
            <ArrowsClockwise size={14} /> Yenile
          </button>
        </div>
      </div>

      <div className="bg-stone-900 text-white rounded-2xl p-6 flex flex-wrap items-center gap-8">
        <div>
          <div className="text-3xl font-semibold text-rose-400" data-testid="risk-high-count">{data.summary.high}</div>
          <div className="text-xs text-stone-400 mt-1">Yüksek riskli varış</div>
        </div>
        <div>
          <div className="text-xl font-semibold text-amber-400">{data.summary.medium}</div>
          <div className="text-xs text-stone-400 mt-1">Orta riskli</div>
        </div>
        <div>
          <div className="text-xl font-semibold">{fmt(data.value_at_risk)}</div>
          <div className="text-xs text-stone-400 mt-1">Risk altındaki rezervasyon değeri</div>
        </div>
        <label className="ml-auto flex items-center gap-2 text-xs text-stone-400 cursor-pointer">
          <input type="checkbox" checked={showLow} onChange={(e) => setShowLow(e.target.checked)} data-testid="risk-show-low" />
          Düşük riskleri de göster ({data.summary.low})
        </label>
      </div>

      {rows.length === 0 ? (
        <div className="text-sm text-stone-500 bg-emerald-50 border border-emerald-100 rounded-xl p-5" data-testid="risk-empty">
          Önümüzdeki {data.days_ahead} günde riskli varış yok ✓
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((r) => {
            const L = LEVEL[r.level];
            return (
              <div key={r.id} className="bg-white border border-stone-200 rounded-xl p-4 flex flex-wrap items-center gap-4"
                data-testid={`risk-row-${r.id}`}>
                <div className="min-w-[180px]">
                  <div className="text-sm font-semibold text-stone-900">{r.guest_name || r.guest_email || "—"}</div>
                  <div className="text-xs text-stone-400 flex items-center gap-1 mt-0.5">
                    <CalendarBlank size={12} /> {r.check_in} · {r.room_type_name || "oda"} · {fmt(r.total_price)}
                  </div>
                </div>
                <div className="flex-1 min-w-[160px]">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${L.cls}`}>{L.label} · {r.score}</span>
                    <span className="text-xs text-stone-500">{r.reasons.join(" · ") || "Geçmiş yok"}</span>
                  </div>
                  <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${L.bar}`} style={{ width: `${r.score}%` }} />
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="text-xs font-medium text-stone-700 bg-stone-50 border border-stone-200 rounded-lg px-3 py-2">
                    {r.action}
                  </div>
                  {r.level !== "low" && (
                    r.deposit_paid ? (
                      <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2" data-testid={`deposit-paid-${r.id}`}>
                        Depozito alındı ✓
                      </span>
                    ) : r.deposit_requested ? (
                      <button onClick={() => checkDeposit(r.id)} disabled={busy === r.id} data-testid={`deposit-check-${r.id}`}
                        className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 hover:bg-amber-100 disabled:opacity-60 rounded-lg px-3 py-2 transition-colors">
                        {busy === r.id ? "…" : "İstendi · Durumu kontrol et"}
                      </button>
                    ) : (
                      <button onClick={() => requestDeposit(r.id)} disabled={busy === r.id} data-testid={`deposit-request-${r.id}`}
                        className="text-xs font-semibold text-white bg-stone-900 hover:bg-stone-700 disabled:opacity-60 rounded-lg px-3 py-2 transition-colors">
                        {busy === r.id ? "Gönderiliyor…" : "Depozito İste"}
                      </button>
                    )
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
