import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import TrialConversionPanel from "./TrialConversionPanel";

const API = process.env.REACT_APP_BACKEND_URL;
const cfg = { withCredentials: true };
const PLANS = ["basic", "rms", "cm", "pro", "full"];
const API_DOCS = [
  ["POST /api/public-keys/{pid}", "API anahtarı üret (admin)"],
  ["GET /api/public/v1/bookings", "Rezervasyonları listele — Header: X-API-Key"],
  ["POST /api/public/v1/bookings", "Rezervasyon oluştur {guest_name, check_in, check_out, total_price}"],
  ["GET /api/public/v1/rates?days=N", "Oda tipi bazlı fiyatlar"],
  ["GET /api/public/v1/guests", "Misafir listesi"],
  ["POST /api/webhook-subs/{pid}", "Webhook aboneliği {url, events:[booking.created, payment.completed]}"],
  ["POST /api/payments/checkout", "Ödeme linki {amount, currency, booking_id, origin_url}"],
];

export default function PlatformAdminPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [tenants, setTenants] = useState([]);
  const [plans, setPlans] = useState({});
  const [mrr, setMrr] = useState(0);
  const [keys, setKeys] = useState([]);
  const [newKey, setNewKey] = useState(null);
  const [txs, setTxs] = useState([]);
  const [payAmount, setPayAmount] = useState("100");
  const [payBooking, setPayBooking] = useState("");
  const [payLink, setPayLink] = useState(null);
  const [migResult, setMigResult] = useState(null);
  const [migKind, setMigKind] = useState("guests");

  const load = useCallback(async () => {
    try {
      const [h, k, t] = await Promise.all([
        axios.get(`${API}/api/super-admin/health-scores`, cfg),
        axios.get(`${API}/api/public-keys/${pid}`, cfg),
        axios.get(`${API}/api/payments/tx-log/${pid}`, cfg),
      ]);
      setTenants(h.data.tenants); setPlans(h.data.plans); setMrr(h.data.mrr || 0);
      setKeys(k.data.keys); setTxs(t.data.transactions.slice(0, 8));
    } catch { toast.error("Platform verileri yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const setPlan = async (tid, plan) => {
    try {
      await axios.post(`${API}/api/super-admin/tenants/${tid}/plan`, { plan }, cfg);
      toast.success(`Plan güncellendi: ${plan.toUpperCase()}`); load();
    } catch { toast.error("Plan değiştirilemedi"); }
  };
  const suspend = async (tid, s) => {
    try {
      await axios.post(`${API}/api/super-admin/tenants/${tid}/suspend`, { suspended: s }, cfg);
      toast.success(s ? "Hesap askıya alındı" : "Hesap aktifleştirildi"); load();
    } catch { toast.error("İşlem başarısız"); }
  };
  const createKey = async () => {
    try {
      const r = await axios.post(`${API}/api/public-keys/${pid}`, { name: "panel" }, cfg);
      setNewKey(r.data.key); toast.success("API anahtarı üretildi — bir kez gösterilir, kopyalayın!"); load();
    } catch { toast.error("Anahtar üretilemedi"); }
  };
  const createPayLink = async () => {
    try {
      const r = await axios.post(`${API}/api/payments/checkout`,
        { amount: +payAmount, currency: "gbp", property_id: pid, booking_id: payBooking, origin_url: window.location.origin }, cfg);
      setPayLink(r.data.checkout_url);
      navigator.clipboard?.writeText(r.data.checkout_url).catch(() => {});
      toast.success("💳 Ödeme linki üretildi ve panoya kopyalandı — misafire gönderin"); load();
    } catch { toast.error("Link üretilemedi"); }
  };
  const importCsv = async (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f);
    try {
      const r = await axios.post(`${API}/api/migration/import/${pid}/${migKind}`, fd, cfg);
      setMigResult(r.data);
      toast.success(`${r.data.imported} kayıt içe aktarıldı${r.data.errors.length ? `, ${r.data.errors.length} hata` : ""}`);
    } catch (err) { toast.error(err.response?.data?.detail || "Import başarısız"); }
    e.target.value = "";
  };

  const Card = ({ title, children, tid }) => (
    <section className="bg-white border border-stone-200 rounded-2xl p-4" data-testid={tid}>
      <h2 className="text-sm font-black text-stone-800 mb-3">{title}</h2>{children}
    </section>
  );

  return (
    <div className="p-5 max-w-[1200px] mx-auto space-y-4" data-testid="platform-admin-panel">
      <h1 className="text-2xl font-semibold text-stone-900">👑 Platform Yönetimi</h1>

      <TrialConversionPanel />

      <Card title="🏨 Müşteri Otelleri — plan, sağlık skoru, askıya alma" tid="pa-tenants">
        <div className="space-y-1.5 max-h-72 overflow-auto">
          {tenants.map((t) => (
            <div key={t.id} className="flex flex-wrap items-center gap-3 bg-stone-50 border border-stone-200 rounded-xl px-3 py-2" data-testid={`pa-tenant-${t.id}`}>
              <span className="flex-1 min-w-[140px] text-sm font-bold text-stone-700">{t.name || t.id}{t.suspended && <span className="text-rose-600 text-[10px] ml-2">⛔ ASKIDA</span>}</span>
              <div className="w-32 flex items-center gap-1.5" title={t.missing.join(", ") || "Kurulum tam"}>
                <div className="flex-1 h-2 bg-stone-200 rounded-full overflow-hidden">
                  <div className={`h-full ${t.score >= 80 ? "bg-emerald-500" : t.score >= 40 ? "bg-amber-500" : "bg-rose-500"}`} style={{ width: `${t.score}%` }} />
                </div>
                <span className="text-[10px] font-black text-stone-600" data-testid={`pa-score-${t.id}`}>%{t.score}</span>
              </div>
              <select value={t.plan || "full"} onChange={(e) => setPlan(t.id, e.target.value)} data-testid={`pa-plan-${t.id}`}
                className="border border-stone-300 rounded-lg px-2 py-1 text-xs font-bold">
                {PLANS.map((p) => <option key={p} value={p}>{p.toUpperCase()}</option>)}
              </select>
              <button onClick={() => suspend(t.id, !t.suspended)} data-testid={`pa-suspend-${t.id}`}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold ${t.suspended ? "bg-emerald-600 text-white" : "border border-rose-300 text-rose-600"}`}>
                {t.suspended ? "Aktifleştir" : "Askıya Al"}
              </button>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-stone-400 mt-2">{Object.entries(plans).map(([k, v]) => `${k.toUpperCase()}: ${v}`).join(" · ")}</p>
      </Card>

      <Card title="💳 Faturalama — plan ücretleri ve aktif indirimler" tid="pa-billing">
        <div className="flex items-center gap-2 mb-2 bg-stone-50 border border-stone-200 rounded-xl px-3 py-2">
          <span className="text-xs font-bold text-stone-600">Aylık Tekrarlayan Gelir (MRR)</span>
          <span className="text-lg font-black text-emerald-600" data-testid="pa-mrr">£{mrr.toLocaleString("tr-TR")}</span>
          <span className="text-[10px] text-stone-400">askıya alınanlar hariç · indirimler düşülmüş</span>
        </div>
        <div className="space-y-1.5 max-h-64 overflow-auto">
          {tenants.map((t) => (
            <div key={t.id} className="flex flex-wrap items-center gap-2 bg-stone-50 border border-stone-200 rounded-xl px-3 py-1.5" data-testid={`pa-billing-${t.id}`}>
              <span className="flex-1 min-w-[140px] text-xs font-bold text-stone-700">{t.name || t.id}</span>
              <span className="text-[10px] font-black text-stone-500 uppercase">{(t.plan || "full")}</span>
              {t.promo_active ? (
                <>
                  <span className="text-[11px] text-stone-400 line-through">£{t.list_price}</span>
                  <span className="text-sm font-black text-emerald-600" data-testid={`pa-billed-${t.id}`}>£{t.billed_price}<span className="text-[10px] text-stone-400 font-medium">/ay</span></span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-300 text-emerald-700 text-[9px] font-black" data-testid={`pa-promo-${t.id}`}>
                    🎉 %{t.promo_pct} İNDİRİM · bitiş {(t.promo_until || "").slice(0, 10)}
                  </span>
                </>
              ) : (
                <span className="text-sm font-black text-stone-700" data-testid={`pa-billed-${t.id}`}>£{t.list_price}<span className="text-[10px] text-stone-400 font-medium">/ay</span></span>
              )}
              {t.suspended && <span className="text-rose-600 text-[9px] font-black">⛔ ASKIDA — faturalanmaz</span>}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="💳 Ödeme Linki Üret (Stripe)" tid="pa-payments">
          <div className="flex gap-2 mb-2">
            <input value={payAmount} onChange={(e) => setPayAmount(e.target.value)} type="number" placeholder="Tutar £" data-testid="pa-pay-amount" className="w-24 border border-stone-300 rounded-lg px-2 py-1.5 text-sm" />
            <input value={payBooking} onChange={(e) => setPayBooking(e.target.value)} placeholder="Rezervasyon no (ops.)" data-testid="pa-pay-booking" className="flex-1 border border-stone-300 rounded-lg px-2 py-1.5 text-sm" />
            <button onClick={createPayLink} data-testid="pa-pay-create" className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-bold">Link Üret</button>
          </div>
          {payLink && <a href={payLink} target="_blank" rel="noreferrer" className="text-[11px] text-indigo-600 break-all" data-testid="pa-pay-link">{payLink.slice(0, 80)}…</a>}
          <div className="mt-2 space-y-1 max-h-32 overflow-auto">
            {txs.map((t) => (
              <div key={t.id} className="flex justify-between text-[11px] bg-stone-50 rounded-lg px-2 py-1">
                <span>{t.booking_id || "—"} · £{t.amount}</span>
                <span className={t.payment_status === "paid" ? "text-emerald-600 font-bold" : "text-amber-600"}>{t.payment_status}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="🔑 Public API Anahtarları" tid="pa-keys">
          <button onClick={createKey} data-testid="pa-key-create" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-xs font-bold mb-2">+ Anahtar Üret</button>
          {newKey && <div className="text-[11px] bg-amber-50 border border-amber-200 rounded-lg p-2 mb-2 break-all font-mono" data-testid="pa-key-new">{newKey}</div>}
          <div className="space-y-1">
            {keys.map((k) => (
              <div key={k.id} className="flex justify-between text-[11px] bg-stone-50 rounded-lg px-2 py-1">
                <span className="font-mono">{k.key}</span><span className="text-stone-400">{k.calls || 0} çağrı</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="📦 Veri Göçü (CSV Import)" tid="pa-migration">
          <div className="flex gap-2 items-center mb-2">
            <select value={migKind} onChange={(e) => setMigKind(e.target.value)} data-testid="pa-mig-kind" className="border border-stone-300 rounded-lg px-2 py-1.5 text-xs font-bold">
              <option value="guests">Misafirler</option><option value="bookings">Rezervasyonlar</option><option value="room_types">Oda Tipleri</option>
            </select>
            <label className="px-3 py-1.5 rounded-lg bg-sky-600 text-white text-xs font-bold cursor-pointer">
              CSV Yükle<input type="file" accept=".csv" onChange={importCsv} className="hidden" data-testid="pa-mig-file" />
            </label>
          </div>
          {migResult && <div className="text-[11px] text-stone-600" data-testid="pa-mig-result">✓ {migResult.imported} içe aktarıldı{migResult.errors?.length > 0 && ` · ${migResult.errors.length} hatalı satır (örn. satır ${migResult.errors[0]?.row}: ${migResult.errors[0]?.error})`}</div>}
          <p className="text-[10px] text-stone-400 mt-1">Başlıklar — misafir: name,email,phone,country,notes · rezervasyon: guest_name,check_in,check_out,room_type_name,total_price,status</p>
        </Card>

        <Card title="📖 API Dokümantasyonu (Public API v1)" tid="pa-docs">
          <div className="space-y-1 text-[11px]">
            {API_DOCS.map(([ep, d]) => (
              <div key={ep} className="bg-stone-50 rounded-lg px-2 py-1"><code className="font-mono font-bold text-indigo-700">{ep}</code><span className="text-stone-500"> — {d}</span></div>
            ))}
          </div>
          <p className="text-[10px] text-stone-400 mt-2">Kimlik doğrulama: <code>X-API-Key: hbx_...</code> header'ı. Webhook imzası: <code>X-Webhook-Secret</code>.</p>
        </Card>
      </div>
    </div>
  );
}
