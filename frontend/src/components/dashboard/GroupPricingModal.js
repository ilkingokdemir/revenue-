/**
 * GroupPricingModal — Grup talebi için displacement analysis + AI rate recommendation.
 * IDeaS/Flyr signature feature.
 */
import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { X, Users, Loader2, CheckCircle2, XCircle, MessageSquare } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function GroupPricingModal({ propertyId, onClose }) {
  const today = new Date();
  const defaultCi = new Date(today.getTime() + 14 * 86400000).toISOString().slice(0, 10);
  const defaultCo = new Date(today.getTime() + 17 * 86400000).toISOString().slice(0, 10);

  const [checkIn, setCheckIn] = useState(defaultCi);
  const [checkOut, setCheckOut] = useState(defaultCo);
  const [rooms, setRooms] = useState(5);
  const [requestedRate, setRequestedRate] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    if (!checkIn || !checkOut || rooms < 1) {
      toast.error("Tüm alanları doldur");
      return;
    }
    setLoading(true);
    try {
      const { data } = await axios.post(`${API}/rms-pro/group-pricing-quote`, {
        property_id: propertyId,
        check_in: checkIn,
        check_out: checkOut,
        rooms_requested: rooms,
        requested_rate: requestedRate ? parseFloat(requestedRate) : 0,
      });
      setResult(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hesaplama başarısız");
    }
    setLoading(false);
  };

  const DecisionBadge = ({ d }) => {
    if (d === "ACCEPT") return (
      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-200 border border-emerald-500/40 text-xs font-black">
        <CheckCircle2 className="w-3.5 h-3.5" /> KABUL ET
      </span>
    );
    if (d === "DECLINE") return (
      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-rose-500/20 text-rose-200 border border-rose-500/40 text-xs font-black">
        <XCircle className="w-3.5 h-3.5" /> REDDET
      </span>
    );
    return (
      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-amber-500/20 text-amber-200 border border-amber-500/40 text-xs font-black">
        <MessageSquare className="w-3.5 h-3.5" /> PAZARLIK
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 bg-stone-950/85 backdrop-blur-sm flex items-center justify-center p-4" data-testid="group-pricing-modal">
      <div className="bg-stone-900 border border-violet-500/40 rounded-2xl max-w-3xl w-full max-h-[92vh] overflow-y-auto shadow-2xl">
        <div className="flex items-start justify-between gap-3 p-5 border-b border-stone-800 bg-gradient-to-r from-violet-950/30 to-purple-950/30">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br from-violet-500/30 to-purple-500/30">
              <Users className="w-5 h-5 text-violet-200" />
            </div>
            <div>
              <h2 className="text-sm font-black text-violet-200">Grup Fiyat Optimizer</h2>
              <p className="text-[11px] text-stone-400 mt-0.5">Displacement cost analizi + AI rate recommendation</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-stone-800 text-stone-400" data-testid="group-modal-x">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className="text-[10px] text-stone-500 font-bold uppercase tracking-widest">Giriş</label>
              <input type="date" value={checkIn} onChange={e => setCheckIn(e.target.value)}
                className="w-full mt-1 px-3 py-2 bg-stone-950/60 border border-stone-700 rounded-lg text-xs text-stone-200" data-testid="group-checkin" />
            </div>
            <div>
              <label className="text-[10px] text-stone-500 font-bold uppercase tracking-widest">Çıkış</label>
              <input type="date" value={checkOut} onChange={e => setCheckOut(e.target.value)}
                className="w-full mt-1 px-3 py-2 bg-stone-950/60 border border-stone-700 rounded-lg text-xs text-stone-200" data-testid="group-checkout" />
            </div>
            <div>
              <label className="text-[10px] text-stone-500 font-bold uppercase tracking-widest">Oda Sayısı</label>
              <input type="number" min="1" value={rooms} onChange={e => setRooms(parseInt(e.target.value) || 1)}
                className="w-full mt-1 px-3 py-2 bg-stone-950/60 border border-stone-700 rounded-lg text-xs text-stone-200" data-testid="group-rooms" />
            </div>
            <div>
              <label className="text-[10px] text-stone-500 font-bold uppercase tracking-widest">Talep Edilen £</label>
              <input type="number" min="0" step="5" placeholder="opsiyonel" value={requestedRate} onChange={e => setRequestedRate(e.target.value)}
                className="w-full mt-1 px-3 py-2 bg-stone-950/60 border border-stone-700 rounded-lg text-xs text-stone-200" data-testid="group-rate" />
            </div>
          </div>

          <button onClick={calculate} disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-violet-500/30 hover:bg-violet-500/50 text-violet-100 text-xs font-black transition disabled:opacity-50"
            data-testid="group-calculate">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Users className="w-4 h-4" />}
            Hesapla
          </button>

          {result && (
            <div className="bg-stone-950/40 border border-stone-800 rounded-xl p-4 space-y-3" data-testid="group-result">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <DecisionBadge d={result.decision} />
                <p className="text-[10px] text-stone-400 italic">{result.decision_reason}</p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <GroupKpi label="Önerilen £/gece" value={`£${result.recommended_rate_per_night}`} tone="emerald" testid="group-rec-rate" />
                <GroupKpi label="Toplam Öneri" value={`£${result.recommended_total}`} tone="emerald" testid="group-rec-total" />
                <GroupKpi label="Displacement" value={`£${result.total_displacement_cost}`} tone="amber" testid="group-displacement" />
                <GroupKpi label="Oda × Gece" value={`${result.rooms_requested} × ${result.nights}`} testid="group-units" />
              </div>
              <div className="overflow-x-auto max-h-64 rounded-lg border border-stone-800/50">
                <table className="w-full text-[11px]">
                  <thead className="bg-stone-950/80 sticky top-0">
                    <tr className="text-[9px] text-stone-400 uppercase tracking-widest">
                      <th className="text-left py-2 pl-3 pr-1 font-bold">Tarih</th>
                      <th className="text-right px-1 font-bold">Boş Oda</th>
                      <th className="text-right px-1 font-bold">Mevcut £</th>
                      <th className="text-right px-1 font-bold">Pazar £</th>
                      <th className="text-right px-1 font-bold">Yerinden Olan</th>
                      <th className="text-right pr-3 pl-1 font-bold">Maliyet</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.per_day.map(d => (
                      <tr key={d.date} className="border-b border-stone-800/30 hover:bg-violet-500/5">
                        <td className="py-2 pl-3 pr-1 text-stone-200">{d.date}</td>
                        <td className="text-right px-1 text-stone-300 tabular-nums">{d.available}</td>
                        <td className="text-right px-1 text-stone-300 tabular-nums">£{d.current_rate}</td>
                        <td className="text-right px-1 text-stone-400 tabular-nums">{d.market_avg ? `£${d.market_avg}` : "—"}</td>
                        <td className="text-right px-1 tabular-nums font-bold text-amber-300">{d.displaced_units}</td>
                        <td className="text-right pr-3 pl-1 text-amber-400 tabular-nums">£{d.displacement_cost}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function GroupKpi({ label, value, tone, testid }) {
  const toneClass = tone === "emerald" ? "text-emerald-300" : tone === "amber" ? "text-amber-300" : "text-stone-100";
  return (
    <div className="bg-stone-900/60 rounded-lg p-2.5 border border-stone-800/50" data-testid={testid}>
      <p className="text-[9px] uppercase tracking-widest text-stone-500 font-bold">{label}</p>
      <p className={`text-base font-black mt-0.5 ${toneClass} tabular-nums`}>{value}</p>
    </div>
  );
}
