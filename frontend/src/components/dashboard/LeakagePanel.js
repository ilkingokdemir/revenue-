import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Drop, ArrowsClockwise, Wallet, Lightning, UserMinus, WarningCircle } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const ICONS = { unpaid_folio: Wallet, missing_upsell: Lightning, noshow_uncharged: UserMinus, zero_rate: WarningCircle };
const fmt = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;

export default function LeakagePanel({ propertyId }) {
  const [data, setData] = useState(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/revenue/leakage/${propertyId}?days=${days}`);
      setData(r.data);
    } catch { toast.error("Sızıntı raporu yüklenemedi"); }
    finally { setLoading(false); }
  }, [propertyId, days]);
  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-8 text-stone-400 text-sm" data-testid="leakage-loading">Taranıyor…</div>;
  if (!data) return <div className="p-8 text-stone-400 text-sm">Veri yok</div>;

  return (
    <div className="space-y-6" data-testid="leakage-panel">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Drop size={12} weight="fill" className="text-rose-500" />
            <span>Gelir Sızıntısı Denetçisi</span>
          </div>
          <h2 className="text-xl font-semibold text-stone-900">Nerelerden para sızıyor?</h2>
        </div>
        <div className="flex items-center gap-2">
          {[30, 90, 180].map((d) => (
            <button key={d} onClick={() => setDays(d)} data-testid={`leak-days-${d}`}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${days === d ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-300"}`}>
              {d} gün
            </button>
          ))}
          <button onClick={load} data-testid="leak-refresh-btn"
            className="inline-flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 border border-stone-200 rounded-lg px-3 py-1.5 bg-white transition-colors">
            <ArrowsClockwise size={14} /> Yenile
          </button>
        </div>
      </div>

      <div className="bg-stone-900 text-white rounded-2xl p-6 flex flex-wrap items-center gap-8">
        <div>
          <div className="text-3xl font-semibold text-rose-400" data-testid="leak-total">{fmt(data.total_leaked)}</div>
          <div className="text-xs text-stone-400 mt-1">Toplam tespit edilen sızıntı (son {data.days} gün)</div>
        </div>
        <div>
          <div className="text-xl font-semibold">{data.total_items}</div>
          <div className="text-xs text-stone-400 mt-1">İşlem gerektiren kayıt</div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {data.rows.map((r) => {
          const Icon = ICONS[r.key] || WarningCircle;
          const isOpen = open === r.key;
          return (
            <div key={r.key} className="bg-white border border-stone-200 rounded-xl p-5" data-testid={`leak-row-${r.key}`}>
              <button onClick={() => setOpen(isOpen ? null : r.key)} className="w-full flex items-start justify-between gap-3 text-left"
                data-testid={`leak-toggle-${r.key}`}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-rose-50 border border-rose-100 flex items-center justify-center">
                    <Icon size={20} className="text-rose-500" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-stone-900">{r.name}</div>
                    <div className="text-xs text-stone-500 mt-0.5">{r.desc}</div>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-lg font-semibold ${r.count > 0 ? "text-rose-600" : "text-emerald-600"}`}>{fmt(r.leaked)}</div>
                  <div className="text-[11px] text-stone-400">{r.count} kayıt</div>
                </div>
              </button>
              {isOpen && r.items.length > 0 && (
                <div className="mt-4 border-t border-stone-100 pt-3 space-y-2" data-testid={`leak-items-${r.key}`}>
                  {r.items.map((it, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-stone-600 truncate">
                        {it.ref || it.booking_id?.slice(0, 8)} · {it.guest_name || "—"} <span className="text-stone-400">· {it.detail}</span>
                      </span>
                      <span className="font-semibold text-stone-800 shrink-0 ml-3">{fmt(it.amount)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
