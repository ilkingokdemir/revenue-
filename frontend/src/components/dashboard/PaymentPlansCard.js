import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const W = { withCredentials: true };
const ST = { scheduled: ["Otomatik planlı", "bg-emerald-100 text-emerald-700"], failed: ["Başarısız", "bg-rose-100 text-rose-700"], manual: ["Manuel / link", "bg-stone-100 text-stone-600"] };

export default function PaymentPlansCard({ propertyId }) {
  const [d, setD] = useState(null);
  const [be, setBe] = useState(null);
  const load = useCallback(async () => {
    if (!propertyId || propertyId === "all") return;
    try { const [a, b] = await Promise.all([axios.get(`${API}/booking/payment-schedules/${propertyId}`, W), axios.get(`${API}/booking/be-settings/${propertyId}`)]); setD(a.data); setBe(b.data); } catch { toast.error("Ödeme planları yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  const saveSettings = async (patch) => { try { const r = await axios.put(`${API}/booking/payment-schedules/${propertyId}/settings`, { ...d.settings, ...patch }, W); setD((x) => ({ ...x, settings: r.data })); toast.success("Kaydedildi"); } catch { toast.error("Kaydedilemedi"); } };
  const savePrice = async (patch) => { try { const r = await axios.put(`${API}/booking/be-settings/${propertyId}`, { ...patch }, W); setBe((x) => ({ ...x, ...r.data, ...patch })); toast.success("Fiyat gösterimi kaydedildi"); } catch { toast.error("Kaydedilemedi"); } };
  const run = async () => { try { const r = await axios.post(`${API}/booking/payment-schedules/${propertyId}/run`, {}, W); toast.success(`Çalıştı: ${r.data.charged} tahsil, ${r.data.failed} başarısız, ${r.data.reminded} hatırlatma`); load(); } catch { toast.error("Çalıştırılamadı"); } };
  const charge = async (b) => { try { const r = await axios.post(`${API}/booking/payment-schedules/${propertyId}/${b.id}/charge`, {}, W); toast[r.data.ok ? "success" : "error"](r.data.ok ? "Tahsil edildi" : `Başarısız: ${r.data.error || r.data.reason}`); load(); } catch { toast.error("Tahsilat hatası"); } };

  if (!propertyId || propertyId === "all") return <div className="text-sm text-stone-500 py-8 text-center" data-testid="payplans-select-property">Üstten bir tesis seçin.</div>;
  if (!d) return null;
  const s = d.settings;
  return (
    <div className="space-y-4" data-testid="payment-plans-card">
      <div className="bg-white rounded-2xl border border-stone-200 p-4">
        <h3 className="font-semibold text-stone-900 mb-2">Ödeme Planı Otomasyonu</h3>
        <div className="flex flex-wrap gap-4 text-xs text-stone-700">
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={s.balance_auto_charge_enabled} onChange={(e) => saveSettings({ balance_auto_charge_enabled: e.target.checked })} data-testid="payplan-auto-charge" />Kalan bakiyeyi kayıtlı karttan otomatik tahsil et</label>
          <label className="flex items-center gap-1.5">Varıştan <input type="number" min={0} max={60} defaultValue={s.balance_charge_days_before} onBlur={(e) => saveSettings({ balance_charge_days_before: Number(e.target.value) })} className="w-14 border border-stone-300 rounded px-1 py-0.5" data-testid="payplan-charge-days" /> gün önce tahsil</label>
          <label className="flex items-center gap-1.5">Hatırlatma: <input type="number" min={0} max={90} defaultValue={s.balance_reminder_days_before} onBlur={(e) => saveSettings({ balance_reminder_days_before: Number(e.target.value) })} className="w-14 border border-stone-300 rounded px-1 py-0.5" data-testid="payplan-reminder-days" /> gün önce</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={s.split_pay_enabled} onChange={(e) => saveSettings({ split_pay_enabled: e.target.checked })} data-testid="payplan-split" />Grup "ödemeyi bölüş" linkleri</label>
          <button onClick={run} className="ml-auto px-3 py-1.5 rounded-lg bg-stone-900 text-white font-bold" data-testid="payplan-run">▶ Planı şimdi çalıştır</button>
        </div>
        <div className="flex gap-2 mt-3 text-[11px] font-bold" data-testid="payplan-counts">
          <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">{d.counts.scheduled} otomatik</span>
          <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700">{d.counts.failed} başarısız</span>
          <span className="px-2 py-0.5 rounded-full bg-stone-100 text-stone-600">{d.counts.manual} manuel</span>
        </div>
        {!d.items.length && <div className="text-xs text-stone-400 mt-3" data-testid="payplan-empty">Bekleyen bakiye yok.</div>}
        <div className="mt-2 space-y-1">
          {d.items.map((b) => { const [lbl, cls] = ST[b.balance_status] || ST.manual; return (
            <div key={b.id} className="flex flex-wrap items-center gap-2 text-xs bg-stone-50 rounded-lg px-2 py-1.5" data-testid={`payplan-row-${b.booking_ref}`}>
              <span className="font-bold">{b.booking_ref}</span><span>{b.guest_name}</span><span className="text-stone-500">giriş {b.check_in}</span>
              <span className="text-stone-500">ödenen {b.currency} {Number(b.deposit_paid || 0).toFixed(0)} · kalan <b className="text-stone-900">{b.currency} {Number(b.balance_due).toFixed(0)}</b>{b.balance_due_date ? ` · vade ${b.balance_due_date}` : ""}</span>
              <span className={`px-1.5 py-0.5 rounded-full font-bold ${cls}`} data-testid={`payplan-status-${b.booking_ref}`}>{lbl}</span>
              {b.balance_last_error && <span className="text-rose-600 truncate max-w-[200px]">{b.balance_last_error}</span>}
              {b.card_on_file && <button onClick={() => charge(b)} className="ml-auto px-2 py-1 rounded-md bg-emerald-600 text-white font-bold" data-testid={`payplan-charge-${b.booking_ref}`}>Şimdi tahsil et</button>}
            </div>); })}
        </div>
      </div>
      {be && (
        <div className="bg-white rounded-2xl border border-stone-200 p-4" data-testid="price-display-card">
          <h3 className="font-semibold text-stone-900 mb-1">Fiyat Gösterim Modu</h3>
          <p className="text-xs text-stone-500 mb-2">AB/İngiltere/Türkiye'de vergiler dahil gösterim zorunlu; ABD/Kanada pazarında vergi hariç alışılmış. "Toplam fiyat şeffaflığı" her planda tüm vergiler dahil toplamı gösterir.</p>
          <div className="flex flex-wrap gap-4 text-xs text-stone-700">
            <label className="flex items-center gap-1.5">Mod
              <select value={be.price_display_mode || "auto_by_market"} onChange={(e) => savePrice({ price_display_mode: e.target.value })} className="border border-stone-300 rounded px-2 py-1" data-testid="price-display-mode">
                <option value="auto_by_market">Pazara göre otomatik</option><option value="tax_inclusive">Her zaman vergiler dahil</option><option value="tax_exclusive">Her zaman vergi hariç</option>
              </select>
            </label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={be.total_price_transparency !== false} onChange={(e) => savePrice({ total_price_transparency: e.target.checked })} data-testid="price-display-transparency" />Toplam fiyat şeffaflığı</label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={be.installments_enabled !== false} onChange={(e) => savePrice({ installments_enabled: e.target.checked })} data-testid="installments-enabled" />Taksit</label>
            <label className="flex items-center gap-1.5"><input type="number" min={2} max={12} defaultValue={be.installments_count || 3} onBlur={(e) => savePrice({ installments_count: Number(e.target.value) })} className="w-12 border border-stone-300 rounded px-1 py-0.5" data-testid="installments-count" /> taksit, min tutar <input type="number" min={0} defaultValue={be.installments_min_amount ?? 500} onBlur={(e) => savePrice({ installments_min_amount: Number(e.target.value) })} className="w-20 border border-stone-300 rounded px-1 py-0.5" data-testid="installments-min" /></label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={be.loyalty_show_points !== false} onChange={(e) => savePrice({ loyalty_show_points: e.target.checked })} data-testid="loyalty-show-points" />Puan göster (<input type="number" min={1} max={100} defaultValue={be.loyalty_points_per_unit ?? 10} onBlur={(e) => savePrice({ loyalty_points_per_unit: Number(e.target.value) })} className="w-12 border border-stone-300 rounded px-1 py-0.5" data-testid="loyalty-ppu" /> puan / para birimi)</label>
            <label className="flex items-center gap-1.5">Vergi hariç pazarlar <input defaultValue={(be.tax_exclusive_markets || ["US", "CA", "en-US"]).join(", ")} onBlur={(e) => savePrice({ tax_exclusive_markets: e.target.value.split(/[,\s]+/).filter(Boolean) })} className="w-40 border border-stone-300 rounded px-2 py-1" data-testid="price-display-markets" /></label>
          </div>
        </div>
      )}
    </div>
  );
}
