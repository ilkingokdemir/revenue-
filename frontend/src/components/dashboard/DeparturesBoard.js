/**
 * DeparturesBoard — Scheduled Check-outs Today (iter 367)
 * ---------------------------------------------------------
 * Shows the departures scheduled by guests via portal/kiosk with a live
 * countdown until each check-out. Staff can force-execute early or reveal
 * booking details. Ticker refreshes every 30s so overdue rows glow red.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { DoorOpen, Clock, Loader2, RefreshCw, PlayCircle, User, BedDouble } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function DeparturesBoard({ propertyId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    try {
      const p = propertyId && propertyId !== "all" ? `?property_id=${propertyId}` : "";
      const r = await axios.get(`${API}/checkout/scheduled/today${p}`);
      setItems(r.data.items || []);
    } catch {
      // silent
    }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  const execute = async (bookingId, name) => {
    if (!window.confirm(`${name || "Misafir"} için check-out'ı hemen tamamla?`)) return;
    setBusyId(bookingId);
    try {
      await axios.post(`${API}/checkout/scheduled/${bookingId}/execute-now`);
      toast.success("Check-out tamamlandı");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Başarısız");
    }
    setBusyId(null);
  };

  const dueSoon = items.filter((i) => !i.is_overdue && i.minutes_left <= 60).length;
  const overdue = items.filter((i) => i.is_overdue).length;

  return (
    <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-3" data-testid="departures-board">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DoorOpen className="w-5 h-5 text-amber-400" />
          <h3 className="text-sm font-semibold text-stone-100">Planlı Çıkışlar · Bugün</h3>
          <span className="text-xs text-stone-500">({items.length})</span>
        </div>
        <button
          onClick={load}
          className="p-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300"
          data-testid="departures-refresh"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {(dueSoon > 0 || overdue > 0) && (
        <div className="flex gap-2 text-[11px]">
          {overdue > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-rose-500/15 border border-rose-500/40 text-rose-300 font-semibold">
              {overdue} geçmiş süre
            </span>
          )}
          {dueSoon > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-300 font-semibold">
              {dueSoon} · 1 saat içinde
            </span>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-6 text-stone-500">
          <Loader2 className="w-4 h-4 animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-6 text-stone-500 text-sm" data-testid="departures-empty">
          Bugün için planlı check-out yok.
        </div>
      ) : (
        <div className="space-y-2 max-h-72 overflow-y-auto">
          {items.map((i) => (
            <div
              key={i.booking_id}
              data-testid="departure-row"
              className={`flex items-center gap-3 px-3 py-2 rounded-lg border ${
                i.is_overdue
                  ? "bg-rose-500/10 border-rose-500/40"
                  : i.minutes_left <= 60
                    ? "bg-amber-500/10 border-amber-500/30"
                    : "bg-stone-800/40 border-stone-800"
              }`}
            >
              <div className="text-2xl font-bold text-stone-100 min-w-[60px]">
                {new Date(i.checkout_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-stone-100 font-medium truncate flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-stone-400" />
                  {i.guest_name || "—"}
                </div>
                <div className="text-xs text-stone-400 flex items-center gap-2 truncate">
                  <span className="flex items-center gap-1"><BedDouble className="w-3 h-3" />{i.room_number || "—"}</span>
                  <span className="text-stone-600">·</span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {i.is_overdue
                      ? `${Math.abs(i.minutes_left)}dk geç`
                      : `${i.minutes_left}dk kaldı`}
                  </span>
                  {i.notes ? <span className="text-stone-500 italic truncate">· {i.notes}</span> : null}
                </div>
              </div>
              <button
                onClick={() => execute(i.booking_id, i.guest_name)}
                disabled={busyId === i.booking_id}
                className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-bold"
                data-testid={`departure-execute-${i.booking_id}`}
              >
                {busyId === i.booking_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <PlayCircle className="w-3 h-3" />}
                Şimdi
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="text-[10px] text-stone-600 flex items-center gap-1">
        <Clock className="w-3 h-3" /> Otomatik her 30 sn yenilenir · Cron her 5dk `tick` çalıştırır
      </div>
    </div>
  );
}
