import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { DeviceMobile, Bell, EnvelopeSimple } from "@phosphor-icons/react";

const B = process.env.REACT_APP_BACKEND_URL;
const STATUS_TR = { pending_revenue: "Revenue onayı", pending_sales: "Satış onayı" };

export default function MobileApprovalsPanel({ propertyId = "default" }) {
  const pid = propertyId === "all" ? "default" : propertyId;
  const [quotes, setQuotes] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [weekly, setWeekly] = useState(null);
  const [notifPerm, setNotifPerm] = useState(
    typeof Notification !== "undefined" ? Notification.permission : "denied");

  const load = useCallback(async () => {
    try {
      const [g, f, w] = await Promise.all([
        axios.get(`${B}/api/group-approval/${pid}`),
        axios.get(`${B}/api/function-space/${pid}/proposals`),
        axios.get(`${B}/api/owner-weekly/history`),
      ]);
      setQuotes((g.data.quotes || []).filter((q) => q.status?.startsWith("pending")));
      setProposals((f.data.proposals || []).filter((p) => p.status === "sent"));
      setWeekly(w.data);
    } catch { toast.error("Onay verileri yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function askNotif() {
    if (typeof Notification === "undefined") { toast.error("Tarayıcı bildirim desteklemiyor"); return; }
    const p = await Notification.requestPermission();
    setNotifPerm(p);
    if (p === "granted") {
      new Notification("🔔 Bildirimler açık", { body: "Bekleyen fiyat onayları telefonunuza düşecek.", icon: "/favicon.ico" });
      toast.success("Anlık bildirimler etkin");
    }
  }

  async function actQuote(q, action) {
    try {
      if (action === "approve") {
        await axios.post(`${B}/api/group-approval/${pid}/quotes/${q.id}/approve`, { role: q.status.replace("pending_", "") });
      } else {
        await axios.post(`${B}/api/group-approval/${pid}/quotes/${q.id}/reject`, {});
      }
      toast.success(action === "approve" ? "Onaylandı" : "Reddedildi"); load();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  }

  async function actProposal(p, action) {
    try {
      await axios.post(`${B}/api/function-space/${pid}/proposals/${p.id}/${action}`, {});
      toast.success(action === "accept" ? "Teklif kabul edildi" : "Reddedildi"); load();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  }

  async function sendWeekly() {
    try {
      const r = await axios.post(`${B}/api/owner-weekly/send-now`);
      toast.success(`Haftalık özet gönderildi: ${(r.data.sent_to || []).length} alıcı (Resend anahtarı yoksa MOCK)`); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Gönderilemedi (sadece admin)"); }
  }

  return (
    <div className="p-4 max-w-[680px] mx-auto space-y-4 pb-24" data-testid="mobile-approvals-panel">
      <div className="bg-stone-950 rounded-2xl p-5 text-white">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <DeviceMobile size={20} className="text-emerald-400" /> Mobil Onay Merkezi
        </h1>
        <p className="text-xs text-stone-400 mt-1">Telefondan tek dokunuşla fiyat/grup onayı. Uygulamayı ana ekrana ekleyin, bildirimleri açın.</p>
        {notifPerm !== "granted" && (
          <button onClick={askNotif} data-testid="notif-enable-btn"
            className="mt-3 px-4 py-2 rounded-full bg-emerald-500 text-stone-950 text-xs font-bold flex items-center gap-1.5">
            <Bell size={14} /> Anlık Bildirimleri Aç
          </button>
        )}
        {notifPerm === "granted" && <p className="mt-2 text-xs text-emerald-400" data-testid="notif-enabled-badge">🔔 Bildirimler etkin</p>}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-4" data-testid="mobile-quotes-card">
        <h2 className="text-base font-bold mb-2">Bekleyen Grup Teklifleri ({quotes.length})</h2>
        {quotes.length === 0 ? <p className="text-sm text-stone-400" data-testid="mobile-quotes-empty">Bekleyen onay yok ✓</p> : quotes.map((q) => (
          <div key={q.id} className="border border-stone-200 rounded-xl p-3 mb-2" data-testid={`mobile-quote-${q.id}`}>
            <div className="flex justify-between items-baseline">
              <b>{q.group_name}</b>
              <span className="text-[10px] font-bold text-amber-600">{STATUS_TR[q.status] || q.status}</span>
            </div>
            <div className="text-xs text-stone-500 mt-0.5">{q.rooms} oda × {q.nights} gece · Wish £{q.wish_price} / Walk £{q.walk_price} · {q.check_in}</div>
            <div className="flex gap-2 mt-2">
              <button onClick={() => actQuote(q, "approve")} data-testid={`mobile-approve-${q.id}`}
                className="flex-1 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-bold">✓ Onayla</button>
              <button onClick={() => actQuote(q, "reject")} data-testid={`mobile-reject-${q.id}`}
                className="flex-1 py-2.5 rounded-xl border border-rose-300 text-rose-600 text-sm font-bold">✗ Reddet</button>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-4" data-testid="mobile-proposals-card">
        <h2 className="text-base font-bold mb-2">Bekleyen Salon Teklifleri ({proposals.length})</h2>
        {proposals.length === 0 ? <p className="text-sm text-stone-400">Bekleyen teklif yok ✓</p> : proposals.map((p) => (
          <div key={p.id} className="border border-stone-200 rounded-xl p-3 mb-2">
            <b>{p.client_name}</b> — {p.space_name}
            <div className="text-xs text-stone-500">{p.date} · {p.attendees} kişi · £{p.total}</div>
            <div className="flex gap-2 mt-2">
              <button onClick={() => actProposal(p, "accept")} className="flex-1 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-bold">✓ Kabul</button>
              <button onClick={() => actProposal(p, "reject")} className="flex-1 py-2.5 rounded-xl border border-rose-300 text-rose-600 text-sm font-bold">✗ Red</button>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-4" data-testid="owner-weekly-card">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold flex items-center gap-1.5"><EnvelopeSimple size={16} /> Yönetici Haftalık Özeti</h2>
          <button onClick={sendWeekly} data-testid="owner-weekly-send-btn"
            className="px-3 py-1.5 rounded-full bg-stone-900 text-white text-xs font-bold">Şimdi Gönder</button>
        </div>
        <p className="text-xs text-stone-400 mt-1">GOPPAR ligi + RMS uplift raporu her Pazartesi sabahı yöneticilere otomatik e-postalanır.</p>
        {weekly?.sends?.slice(0, 3).map((s) => (
          <div key={s.id} className="text-xs text-stone-500 border-t border-stone-100 py-1 mt-1" data-testid={`owner-weekly-send-${s.week_key}`}>
            {s.week_key} → {(s.sent_to || []).length} alıcı {s.forced ? "(manuel)" : "(otomatik)"} · portföy GOPPAR £{s.summary?.portfolio_goppar}
          </div>
        ))}
      </div>
    </div>
  );
}
