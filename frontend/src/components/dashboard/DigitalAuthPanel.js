import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { LockKey, Copy, Plus } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/digital-auth`;

const STATUS_CLS = {
  pending: "bg-amber-50 text-amber-700",
  authorized: "bg-emerald-50 text-emerald-700",
  charged: "bg-teal-50 text-teal-700",
  voided: "bg-stone-100 text-stone-500",
  expired: "bg-rose-50 text-rose-600",
};
const STATUS_TR = { pending: "Bekliyor", authorized: "Yetkilendirildi", charged: "Tahsil edildi", voided: "İptal", expired: "Süresi doldu" };
const PURPOSES = [
  ["room_charge", "Konaklama ücreti"], ["deposit", "Depozito"],
  ["no_show_guarantee", "No-show garantisi"], ["incidentals", "Ekstra harcamalar"], ["third_party", "3. şahıs ödemesi"],
];

export default function DigitalAuthPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ payer_name: "", payer_email: "", amount: "", purpose: "room_charge", note: "" });
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/${propertyId}`); setData(r.data); }
    catch { toast.error("Talepler yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.payer_email.includes("@") || !form.amount) { toast.error("E-posta ve tutar gerekli"); return; }
    setCreating(true);
    try {
      const r = await axios.post(`${API}/requests`, { ...form, amount: parseFloat(form.amount), property_id: propertyId === "all" ? "aldgate-flats" : propertyId });
      toast.success(r.data.email_status === "mock" ? "Talep oluşturuldu (e-posta MOCK) — linki kopyalayıp gönderebilirsiniz" : "Talep oluşturuldu ve e-posta gönderildi");
      setForm({ payer_name: "", payer_email: "", amount: "", purpose: "room_charge", note: "" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Oluşturulamadı"); }
    setCreating(false);
  };

  const act = async (id, action) => {
    try {
      const r = await axios.post(`${API}/${id}/${action}`);
      toast.success(action === "charge" ? `✓ £${r.data.amount} tahsil edildi (mock)` : "Talep iptal edildi");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  };

  const copyLink = (link) => { navigator.clipboard.writeText(link); toast.success("Form linki kopyalandı"); };

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const s = data.stats || {};

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-4" data-testid="digital-auth-panel">
      <div className="bg-gradient-to-br from-stone-900 via-slate-900 to-stone-800 rounded-2xl p-6 text-white">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-300">
          <LockKey size={14} weight="fill" /> Digital Authorizations
        </div>
        <h1 className="text-2xl font-bold mt-1">Dijital Ödeme Yetkilendirme</h1>
        <p className="text-sm text-stone-300 mt-1">Faks/PDF kart formları yerine güvenli link: kurumsal ve 3. şahıs ödemeleri PCI uyumlu formla yetkilendirilir (tam kart no saklanmaz).</p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5">
          <Stat label="Bekleyen" value={s.pending || 0} testid="da-stat-pending" />
          <Stat label="Yetkilendirilen" value={s.authorized || 0} testid="da-stat-authorized" />
          <Stat label="Tahsil edilen" value={s.charged || 0} testid="da-stat-charged" />
          <Stat label="Yetkili tutar" value={`£${(data.authorized_total || 0).toLocaleString()}`} testid="da-stat-auth-total" />
          <Stat label="Tahsilat" value={`£${(data.charged_total || 0).toLocaleString()}`} testid="da-stat-charged-total" />
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-4">
        <div className="text-[11px] uppercase tracking-wider text-stone-500 mb-2 flex items-center gap-1.5"><Plus size={12} /> Yeni yetkilendirme talebi</div>
        <div className="grid grid-cols-1 md:grid-cols-6 gap-2">
          <input placeholder="Ödeyen adı / şirket" value={form.payer_name} data-testid="da-input-name"
            onChange={e => setForm(f => ({ ...f, payer_name: e.target.value }))}
            className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          <input placeholder="E-posta" value={form.payer_email} data-testid="da-input-email"
            onChange={e => setForm(f => ({ ...f, payer_email: e.target.value }))}
            className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          <input placeholder="Tutar (£)" type="number" value={form.amount} data-testid="da-input-amount"
            onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
            className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          <select value={form.purpose} onChange={e => setForm(f => ({ ...f, purpose: e.target.value }))}
            className="px-2 py-2 text-sm border border-stone-300 rounded-lg" data-testid="da-input-purpose">
            {PURPOSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <input placeholder="Not (rez. no vb.)" value={form.note} data-testid="da-input-note"
            onChange={e => setForm(f => ({ ...f, note: e.target.value }))}
            className="px-3 py-2 text-sm border border-stone-300 rounded-lg" />
          <button onClick={create} disabled={creating} data-testid="da-create-btn"
            className="px-3 py-2 text-sm font-bold text-white bg-stone-900 rounded-lg hover:bg-stone-800 disabled:opacity-50">
            {creating ? "…" : "Link Oluştur & Gönder"}
          </button>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="text-[11px] uppercase text-stone-400 border-b border-stone-100">
            <th className="text-left px-4 py-2">Ödeyen</th><th className="text-left px-2 py-2">Amaç</th>
            <th className="text-right px-2 py-2">Tutar</th><th className="text-left px-2 py-2">Durum</th>
            <th className="text-left px-2 py-2">Kart</th><th className="text-right px-4 py-2">Aksiyon</th>
          </tr></thead>
          <tbody>
            {(data.requests || []).map(r => (
              <tr key={r.id} className="border-b border-stone-50" data-testid={`da-row-${r.id}`}>
                <td className="px-4 py-2.5">
                  <div className="font-medium text-stone-800">{r.payer_name || "—"}</div>
                  <div className="text-[10px] text-stone-400">{r.payer_email}</div>
                </td>
                <td className="px-2 py-2.5 text-xs">{r.purpose_label}<div className="text-[10px] text-stone-400">{r.note}</div></td>
                <td className="px-2 py-2.5 text-right font-mono font-bold">£{Number(r.amount).toLocaleString()}</td>
                <td className="px-2 py-2.5"><span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${STATUS_CLS[r.status]}`}>{STATUS_TR[r.status]}</span></td>
                <td className="px-2 py-2.5 text-xs font-mono">{r.card_last4 ? `${r.card_brand} •••• ${r.card_last4}` : "—"}
                  {r.signature && <div className="text-[9px] italic text-stone-400">imza: {r.signature}</div>}</td>
                <td className="px-4 py-2.5 text-right">
                  <div className="flex gap-1.5 justify-end">
                    {r.status === "pending" && (
                      <button onClick={() => copyLink(r.link)} title="Linki kopyala" data-testid={`da-copy-${r.id}`}
                        className="p-1.5 text-stone-400 hover:text-stone-800 border border-stone-200 rounded-lg"><Copy size={13} /></button>
                    )}
                    {r.status === "authorized" && (
                      <button onClick={() => act(r.id, "charge")} data-testid={`da-charge-${r.id}`}
                        className="text-[11px] px-2.5 py-1 bg-emerald-600 text-white rounded-lg font-bold hover:bg-emerald-700">Tahsil Et</button>
                    )}
                    {["pending", "authorized"].includes(r.status) && (
                      <button onClick={() => act(r.id, "void")} data-testid={`da-void-${r.id}`}
                        className="text-[11px] px-2.5 py-1 border border-stone-200 text-stone-500 rounded-lg hover:bg-stone-50">İptal</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {(!data.requests || data.requests.length === 0) && (
              <tr><td colSpan={6} className="px-4 py-10 text-center text-stone-400 text-sm">Henüz yetkilendirme talebi yok.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, testid }) {
  return (
    <div className="bg-white/10 rounded-xl p-3" data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
    </div>
  );
}
