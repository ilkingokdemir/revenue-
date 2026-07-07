/**
 * ScheduleCheckoutWidget — Guest-facing self-service check-out (iter 367)
 * -----------------------------------------------------------------------
 * Drops into KioskPWA / guest portal.  The guest picks a time slot and
 * hits "Onayla" — the booking is queued for automatic check-out at that
 * exact moment.  Zero staff interaction required.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Clock, CheckCircle2, Loader2, XCircle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Generate half-hour slots between hourFrom (default now+1h floored) and hourTo (default 14:00 tomorrow). */
function useTimeSlots() {
  return useState(() => {
    const slots = [];
    const now = new Date();
    // Start at next half-hour; leave at least 60 min for staff prep
    const first = new Date(now);
    first.setMinutes(now.getMinutes() < 30 ? 60 : 90, 0, 0);
    // End at 14:00 tomorrow (typical late-checkout window)
    const end = new Date(now);
    end.setDate(now.getDate() + 1);
    end.setHours(14, 0, 0, 0);
    const cursor = new Date(first);
    while (cursor <= end) {
      slots.push(new Date(cursor));
      cursor.setMinutes(cursor.getMinutes() + 30);
    }
    return slots;
  })[0];
}

export default function ScheduleCheckoutWidget({ bookingId, guestEmail = "", onSuccess }) {
  const slots = useTimeSlots();
  const [selected, setSelected] = useState(null);
  const [notes, setNotes] = useState("");
  const [existing, setExisting] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!bookingId) return;
    axios.get(`${API}/checkout/schedule/${bookingId}`)
      .then((r) => setExisting(r.data && r.data.status === "pending" ? r.data : null))
      .catch(() => {});
  }, [bookingId]);

  const submit = async () => {
    if (!selected) {
      toast.error("Bir saat seçin");
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/checkout/schedule`, {
        booking_id: bookingId,
        checkout_at: selected.toISOString(),
        notes: notes.trim() || null,
        guest_email: guestEmail || null,
      });
      const r = await axios.get(`${API}/checkout/schedule/${bookingId}`);
      setExisting(r.data);
      toast.success("Check-out zamanı planlandı");
      onSuccess?.(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Planlama başarısız");
    }
    setSubmitting(false);
  };

  const cancel = async () => {
    if (!window.confirm("Planlı check-out'u iptal et?")) return;
    try {
      await axios.delete(`${API}/checkout/schedule/${bookingId}`);
      setExisting(null);
      toast.success("İptal edildi");
    } catch { toast.error("İptal başarısız"); }
  };

  if (existing?.status === "pending") {
    return (
      <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/5 p-5" data-testid="schedule-checkout-existing">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="w-8 h-8 text-emerald-400" />
          <div className="flex-1">
            <div className="text-lg font-bold text-emerald-100">Check-out planlandı</div>
            <div className="text-emerald-200/80 text-sm">
              {new Date(existing.checkout_at).toLocaleString("tr-TR", {
                dateStyle: "medium", timeStyle: "short",
              })}
            </div>
            {existing.notes && <div className="text-xs text-emerald-200/60 mt-1 italic">&quot;{existing.notes}&quot;</div>}
          </div>
          <button
            onClick={cancel}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-semibold"
            data-testid="schedule-checkout-cancel"
          >
            <XCircle className="w-3.5 h-3.5" /> İptal
          </button>
        </div>
        <p className="text-xs text-emerald-200/60 mt-3">
          Odayı yalnızca terk etmeniz yeter. Resepsiyona uğramanıza gerek yok — fatura e-postanıza gönderilecek.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-stone-700 bg-stone-900/70 p-5 space-y-3" data-testid="schedule-checkout-widget">
      <div className="flex items-center gap-2">
        <Clock className="w-5 h-5 text-amber-400" />
        <h3 className="text-lg font-bold text-stone-100">Check-out zamanınızı seçin</h3>
      </div>
      <p className="text-xs text-stone-400">
        Odayı zamanında terk edin — resepsiyona uğramaya gerek yok.
        Fatura e-postanıza otomatik gönderilir.
      </p>

      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 max-h-56 overflow-y-auto pr-1" data-testid="schedule-checkout-slots">
        {slots.map((s) => {
          const active = selected && s.getTime() === selected.getTime();
          const isTomorrow = s.getDate() !== new Date().getDate();
          return (
            <button
              key={s.toISOString()}
              onClick={() => setSelected(s)}
              data-testid={`slot-${s.toISOString()}`}
              className={`px-2 py-2 rounded-lg text-sm border transition ${
                active
                  ? "bg-amber-500 border-amber-400 text-black font-bold"
                  : "bg-stone-800/60 border-stone-700 text-stone-200 hover:border-amber-400/50"
              }`}
            >
              <div className="text-[10px] uppercase opacity-75">
                {isTomorrow ? "Yarın" : "Bugün"}
              </div>
              <div className="font-bold">
                {s.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
            </button>
          );
        })}
      </div>

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value.slice(0, 500))}
        placeholder="Not (isteğe bağlı): erken taksi çağrıldı, bavul çıkarıldı, vs."
        rows={2}
        className="w-full bg-stone-800/60 border border-stone-700 rounded-lg px-3 py-2 text-sm text-stone-100 placeholder-stone-500"
        data-testid="schedule-checkout-notes"
      />

      <button
        onClick={submit}
        disabled={!selected || submitting}
        data-testid="schedule-checkout-submit"
        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold"
      >
        {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
        {selected
          ? `${selected.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} için Onayla`
          : "Bir saat seçin"}
      </button>
    </div>
  );
}
