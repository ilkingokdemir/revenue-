import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CreditCard, Plus, Lightning } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TerminalPanel({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [readers, setReaders] = useState([]);
  const [payments, setPayments] = useState([]);
  const [amount, setAmount] = useState("");
  const [bookingId, setBookingId] = useState("");
  const [selReader, setSelReader] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [{ data: r }, { data: p }] = await Promise.all([
        axios.get(`${API}/terminal/${pid}/readers`),
        axios.get(`${API}/terminal/${pid}/payments`),
      ]);
      setReaders(r.readers || []);
      setPayments(p.payments || []);
      if (r.readers?.length && !selReader) setSelReader(r.readers[0].id);
    } catch (e) { toast.error(e.response?.data?.detail || "Stripe Terminal'e ulaşılamadı"); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const addSimulated = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/terminal/${pid}/readers/register`, { registration_code: "simulated-wpe", label: "Simüle Resepsiyon Cihazı" });
      toast.success("Simüle cihaz eklendi (test modu)");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Eklenemedi"); }
    setBusy(false);
  };

  const charge = async () => {
    if (!parseFloat(amount) || !selReader) { toast.error("Tutar ve cihaz seçin"); return; }
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/terminal/${pid}/charge`,
        { amount: parseFloat(amount), reader_id: selReader, booking_id: bookingId });
      toast.success(`Ödeme ${data.payment.status === "succeeded" ? "TAMAMLANDI ✅" : `cihaza gönderildi (${data.payment.status})`} — £${amount}`);
      if (data.folio_posted) toast.success("Folyoya otomatik işlendi — çift kayıt gerekmez");
      setAmount(""); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Ödeme başarısız"); }
    setBusy(false);
  };

  const inputCls = "rounded-lg border border-stone-200 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-600";

  return (
    <div className="p-6 max-w-3xl" data-testid="terminal-panel">
      <div className="mb-5">
        <h2 className="text-xl font-bold text-stone-800">Ödeme Terminali (Stripe Terminal)</h2>
        <p className="text-xs text-stone-500 mt-1">Yüz yüze kartlı ödemeler. Test modunda simüle cihazla deneyin; gerçek cihazda ekrandaki kayıt kodunu girin.</p>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm mb-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-stone-800">Cihazlar</h3>
          <button onClick={addSimulated} disabled={busy} data-testid="terminal-add-sim-btn"
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-stone-900 text-white text-[10px] font-bold hover:bg-stone-700 disabled:opacity-50">
            <Plus size={11} weight="bold" /> Simüle Cihaz Ekle
          </button>
        </div>
        {readers.length === 0 && <p className="text-[11px] text-stone-400">Kayıtlı cihaz yok.</p>}
        <div className="space-y-1.5">
          {readers.map((r) => (
            <label key={r.id} className="flex items-center gap-2 text-xs bg-stone-50 rounded-lg px-3 py-2 cursor-pointer" data-testid={`terminal-reader-${r.id}`}>
              <input type="radio" checked={selReader === r.id} onChange={() => setSelReader(r.id)} className="accent-indigo-600" />
              <CreditCard size={14} className="text-indigo-600" />
              <span className="flex-1 font-semibold">{r.label}</span>
              <span className="text-[9px] text-stone-400">{r.device_type}</span>
              <span className={`text-[9px] font-bold uppercase ${r.status === "online" ? "text-emerald-600" : "text-stone-400"}`}>{r.status}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm mb-4">
        <h3 className="text-sm font-bold text-stone-800 mb-3">Tahsilat</h3>
        <div className="flex gap-2">
          <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Tutar (£)" className={`${inputCls} w-28`} data-testid="terminal-amount-input" />
          <input value={bookingId} onChange={(e) => setBookingId(e.target.value)} placeholder="Rezervasyon ID (opsiyonel)" className={`${inputCls} flex-1`} data-testid="terminal-booking-input" />
          <button onClick={charge} disabled={busy} data-testid="terminal-charge-btn"
            className="flex items-center gap-1 px-4 py-2 rounded-lg bg-[#635BFF] text-white text-xs font-bold hover:bg-[#5349f0] disabled:opacity-50">
            <Lightning size={13} weight="fill" /> Cihaza Gönder
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm" data-testid="terminal-payments-log">
        <h3 className="text-sm font-bold text-stone-800 mb-3">Son Terminal Ödemeleri</h3>
        {payments.length === 0 && <p className="text-[11px] text-stone-400">Henüz ödeme yok.</p>}
        <div className="space-y-1.5">
          {payments.map((p) => (
            <div key={p.id} className="flex items-center gap-2 text-xs bg-stone-50 rounded-lg px-3 py-2">
              <span className="font-mono font-bold">£{p.amount}</span>
              <span className="flex-1 text-stone-500 truncate">{p.booking_id || p.payment_intent}</span>
              <span className={`text-[9px] font-bold uppercase ${p.status === "succeeded" ? "text-emerald-600" : "text-amber-600"}`}>{p.status}</span>
              <span className="text-[9px] text-stone-400">{(p.created_at || "").slice(0, 16).replace("T", " ")}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
