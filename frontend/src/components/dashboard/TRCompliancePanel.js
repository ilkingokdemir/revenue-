import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Download,
  FileText,
  CheckCircle,
  ArrowsClockwise,
  PaperPlaneTilt,
  Receipt,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * TRCompliancePanel — Türkiye-specific compliance:
 *   • KBS (Kimlik Bildirim Sistemi) — police arrival reporting export
 *   • e-Arşiv / e-Fatura — UBL-TR 2.1 invoice builder
 *
 * Two-tab clean UI; everything one click away.
 */
export default function TRCompliancePanel({ propertyId, hotelName, initialTab = "kbs" }) {
  const [tab, setTab] = useState(initialTab);
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="tr-compliance-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <span className="text-rose-600">🇹🇷</span>
          <span>Türkiye Resmi Bildirim</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Yasal Uyum · {hotelName || "Property"}
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Kimlik Bildirim Sistemi (1774 sayılı kanun) ve e-Arşiv/e-Fatura (GİB UBL-TR 2.1) için
          tek tıkla dışa aktarım.
        </p>
      </div>

      <div className="flex gap-2 mb-5 border-b border-stone-200">
        <TabBtn active={tab === "kbs"} onClick={() => setTab("kbs")} testId="tr-tab-kbs">
          KBS · Kimlik Bildirim
        </TabBtn>
        <TabBtn active={tab === "efatura"} onClick={() => setTab("efatura")} testId="tr-tab-efatura">
          e-Arşiv / e-Fatura
        </TabBtn>
      </div>

      {tab === "kbs" && <KbsBlock propertyId={propertyId} defaultFrom={weekAgo} defaultTo={today} />}
      {tab === "efatura" && <EFaturaBlock propertyId={propertyId} />}
    </div>
  );
}

function TabBtn({ active, onClick, children, testId }) {
  return (
    <button
      onClick={onClick}
      data-testid={testId}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition ${
        active
          ? "border-rose-500 text-rose-600"
          : "border-transparent text-stone-500 hover:text-stone-700"
      }`}
    >
      {children}
    </button>
  );
}

function KbsBlock({ propertyId, defaultFrom, defaultTo }) {
  const [from, setFrom] = useState(defaultFrom);
  const [to, setTo] = useState(defaultTo);
  const [unsentOnly, setUnsentOnly] = useState(true);
  const [history, setHistory] = useState([]);
  const [pending, setPending] = useState(0);
  const [building, setBuilding] = useState(false);
  const [lastBuilt, setLastBuilt] = useState(null);

  const reload = React.useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/tr-compliance/kbs/${propertyId}/history`);
      setHistory(data.history || []);
      setPending(data.pending_count || 0);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  const buildExport = async () => {
    setBuilding(true);
    try {
      const { data } = await axios.post(`${API}/api/tr-compliance/kbs/export`, {
        property_id: propertyId,
        from_date: from,
        to_date: to,
        only_unsent: unsentOnly,
      });
      setLastBuilt(data);
      toast.success(`${data.row_count} satır KBS dosyası oluşturuldu`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "KBS export başarısız");
    }
    setBuilding(false);
  };

  const downloadTxt = (txt, filename) => {
    const blob = new Blob([txt], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename || "kbs.txt"; a.click();
    URL.revokeObjectURL(url);
  };

  const markSent = async (id) => {
    try {
      await axios.post(`${API}/api/tr-compliance/kbs/export/${id}/mark-sent`);
      toast.success("KBS portalına gönderildi olarak işaretlendi");
      reload();
    } catch (_) { toast.error("İşlem başarısız"); }
  };

  return (
    <div className="space-y-5" data-testid="tr-kbs-block">
      {/* Status banner */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Stat label="Bekleyen bildirim" value={pending} accent={pending ? "rose" : "emerald"} />
        <Stat label="Toplam dışa aktarım" value={history.length} />
        <Stat
          label="Son aktarım"
          value={history[0] ? `${history[0].row_count} satır` : "—"}
          subtitle={history[0]?.created_at?.slice(0, 10)}
        />
      </div>

      {/* Build form */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Yeni KBS Dosyası Oluştur</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
          <div>
            <label className="text-xs text-stone-500">Başlangıç</label>
            <input
              type="date" value={from} onChange={(e) => setFrom(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm"
              data-testid="tr-kbs-from"
            />
          </div>
          <div>
            <label className="text-xs text-stone-500">Bitiş</label>
            <input
              type="date" value={to} onChange={(e) => setTo(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm"
              data-testid="tr-kbs-to"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-stone-700">
            <input
              type="checkbox" checked={unsentOnly}
              onChange={(e) => setUnsentOnly(e.target.checked)}
              data-testid="tr-kbs-unsent-only"
            />
            Yalnızca gönderilmemiş
          </label>
          <button
            onClick={buildExport}
            disabled={building}
            className="px-4 py-2 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700 disabled:opacity-50 flex items-center justify-center gap-2"
            data-testid="tr-kbs-build"
          >
            <FileText size={14} />
            {building ? "Oluşturuluyor…" : "TXT Oluştur"}
          </button>
        </div>

        {lastBuilt && (
          <div className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center gap-3">
            <CheckCircle size={18} className="text-emerald-600 shrink-0" />
            <div className="flex-1 text-sm">
              <div className="font-medium text-emerald-900">
                {lastBuilt.row_count} satır oluşturuldu
              </div>
              {lastBuilt.skipped?.length > 0 && (
                <div className="text-xs text-amber-700">
                  ⚠ {lastBuilt.skipped.length} kayıt atlandı (TC/Pasaport eksik)
                </div>
              )}
            </div>
            <button
              onClick={() => downloadTxt(lastBuilt.txt, lastBuilt.filename)}
              className="px-3 py-1.5 bg-emerald-600 text-white rounded-md text-xs font-medium hover:bg-emerald-700 flex items-center gap-1.5"
              data-testid="tr-kbs-download"
            >
              <Download size={12} /> İndir
            </button>
          </div>
        )}
      </div>

      {/* History */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-stone-900">Geçmiş Aktarımlar</h3>
          <button onClick={reload} className="p-1.5 text-stone-500 hover:text-stone-800" data-testid="tr-kbs-reload">
            <ArrowsClockwise size={14} />
          </button>
        </div>
        {history.length === 0 && (
          <div className="text-xs text-stone-500 py-4 text-center">Henüz aktarım yok.</div>
        )}
        <div className="divide-y divide-stone-100">
          {history.map((h) => (
            <div key={h.id} className="flex items-center gap-3 py-2.5 text-sm">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-stone-900">
                  {h.from_date} → {h.to_date}
                </div>
                <div className="text-xs text-stone-500 mt-0.5">
                  {h.row_count} satır · {h.created_at?.slice(0, 10)}
                  {h.skipped_count > 0 && (
                    <span className="ml-2 text-amber-600">⚠ {h.skipped_count} atlandı</span>
                  )}
                </div>
              </div>
              {h.sent_to_kbs_at ? (
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                  ✓ Gönderildi
                </span>
              ) : (
                <button
                  onClick={() => markSent(h.id)}
                  className="text-xs px-2.5 py-1 rounded-md bg-stone-100 hover:bg-stone-200 text-stone-700"
                  data-testid={`tr-kbs-mark-sent-${h.id}`}
                >
                  Gönderildi olarak işaretle
                </button>
              )}
              <a
                href={`${API}/api/tr-compliance/kbs/export/${h.id}/download`}
                className="p-1.5 text-stone-500 hover:text-stone-800"
                title="TXT indir"
              >
                <Download size={14} />
              </a>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function EFaturaBlock({ propertyId }) {
  const [bookingId, setBookingId] = useState("");
  const [bookings, setBookings] = useState([]);
  const [list, setList] = useState([]);
  const [stats, setStats] = useState({});
  const [building, setBuilding] = useState(false);
  const [lastBuilt, setLastBuilt] = useState(null);
  const [type, setType] = useState("earsiv");
  const [settings, setSettings] = useState(null);
  const [presets, setPresets] = useState([]);
  const [integrators, setIntegrators] = useState([]);
  const [apiKey, setApiKey] = useState("");
  const [savingSt, setSavingSt] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [bulkMonth, setBulkMonth] = useState(new Date().toISOString().slice(0, 7));
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);
  const [vknCheck, setVknCheck] = useState(null);

  const reload = React.useCallback(async () => {
    try {
      const [b, l, st] = await Promise.all([
        axios.get(`${API}/api/bookings?property_id=${propertyId}&limit=20`).catch(() => ({ data: { bookings: [] } })),
        axios.get(`${API}/api/tr-compliance/efatura/${propertyId}/list`),
        axios.get(`${API}/api/tr-compliance/efatura/${propertyId}/settings`).catch(() => null),
      ]);
      setBookings(b?.data?.bookings || b?.data || []);
      setList(l.data.invoices || []);
      setStats({ total_count: l.data.total_count, total_amount: l.data.total_amount, by_status: l.data.by_status || {} });
      if (st?.data) { setSettings(st.data.settings); setPresets(st.data.vat_presets || []); setIntegrators(st.data.integrators || []); }
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  const saveSettings = async () => {
    setSavingSt(true);
    try {
      const body = { ...settings };
      if (apiKey) body.api_key = apiKey;
      const { data } = await axios.put(`${API}/api/tr-compliance/efatura/${propertyId}/settings`, body);
      setSettings(data.settings); setApiKey("");
      toast.success("e-Fatura ayarları kaydedildi");
    } catch (e) { toast.error(e?.response?.data?.detail || "Ayarlar kaydedilemedi"); }
    setSavingSt(false);
  };

  const checkVkn = async (v) => {
    if (!v) { setVknCheck(null); return; }
    try { const { data } = await axios.post(`${API}/api/tr-compliance/validate-id`, { value: v }); setVknCheck(data); } catch (_) { /* silent */ }
  };

  const onPreset = (id) => {
    const pr = presets.find((p) => p.id === id);
    setSettings((s) => ({ ...s, vat_preset: id, ...(pr && pr.rate !== null ? { vat_rate: pr.rate, tax_label: pr.tax_label, tax_region: pr.region } : { tax_region: "custom" }) }));
  };

  const build = async () => {
    if (!bookingId) { toast.error("Önce bir rezervasyon seçin"); return; }
    setBuilding(true);
    try {
      const { data } = await axios.post(`${API}/api/tr-compliance/efatura/build`, { booking_id: bookingId, invoice_type: type });
      setLastBuilt(data);
      toast.success(`Fatura ${data.invoice_no} oluşturuldu`);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Fatura oluşturulamadı"); }
    setBuilding(false);
  };

  const bulk = async () => {
    setBulkBusy(true); setBulkResult(null);
    try {
      const { data } = await axios.post(`${API}/api/tr-compliance/efatura/bulk`, { property_id: propertyId, month: bulkMonth, invoice_type: type });
      setBulkResult(data);
      toast.success(`${data.created} fatura oluşturuldu${data.failed ? `, ${data.failed} başarısız` : ""}`);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Toplu üretim başarısız"); }
    setBulkBusy(false);
  };

  const downloadXml = (xml, filename) => {
    const blob = new Blob([xml], { type: "application/xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const submit = async (id) => {
    try {
      const { data } = await axios.post(`${API}/api/tr-compliance/efatura/${id}/submit`);
      toast.success(`GİB'e gönderildi${data.simulated ? " (simülasyon)" : ""} · ETTN ${data.ettn.slice(0, 8)}…`);
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Gönderim başarısız"); }
  };

  const cancel = async (id) => {
    const reason = window.prompt("İptal nedeni:");
    if (!reason) return;
    try { await axios.post(`${API}/api/tr-compliance/efatura/${id}/cancel`, { reason }); toast.success("Fatura iptal edildi"); reload(); }
    catch (e) { toast.error(e?.response?.data?.detail || "İptal başarısız"); }
  };

  const preview = async (id) => {
    try {
      const { data } = await axios.get(`${API}/api/tr-compliance/efatura/${id}/html`, { responseType: "text" });
      const w = window.open("", "_blank"); w.document.write(data); w.document.close();
    } catch (_) { toast.error("Önizleme açılamadı"); }
  };

  const statusCls = { sent: "bg-sky-100 text-sky-700", submitted: "bg-sky-100 text-sky-700", accepted: "bg-emerald-100 text-emerald-700", rejected: "bg-red-100 text-red-700", cancelled: "bg-stone-200 text-stone-500 line-through" };
  const statusTr = { built: "oluşturuldu", sent: "GİB'e gönderildi", submitted: "gönderildi", accepted: "kabul", rejected: "red", cancelled: "iptal" };
  const inp = "w-full px-3 py-2 rounded-lg border border-stone-300 text-sm bg-white";
  const cur = settings?.tax_region === "uk" ? "£" : settings?.tax_region === "eu" ? "€" : settings?.tax_region === "us" ? "$" : "₺";

  return (
    <div className="space-y-5" data-testid="tr-efatura-block">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Toplam fatura" value={stats.total_count || 0} icon={Receipt} />
        <Stat label="Toplam tutar" value={`${cur}${(stats.total_amount || 0).toLocaleString("tr-TR")}`} accent="emerald" />
        <Stat label="GİB gönderilmiş" value={(stats.by_status?.sent || 0) + (stats.by_status?.submitted || 0) + (stats.by_status?.accepted || 0)} accent="sky" />
        <Stat label="KDV oranı" value={settings ? `%${settings.vat_rate}` : "—"} subtitle={settings ? `${settings.tax_label} · ${(settings.tax_region || "tr").toUpperCase()} · ${integrators.find((i) => i.id === settings.integrator)?.label || "—"}` : ""} accent="rose" />
      </div>

      {/* Settings */}
      <div className="p-4 rounded-xl bg-white border border-stone-200" data-testid="tr-efatura-settings">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-stone-900">Entegratör & KDV Ayarları</h3>
          <button onClick={() => setShowSettings((v) => !v)} className="text-xs text-stone-600 underline" data-testid="tr-efatura-settings-toggle">{showSettings ? "Gizle" : "Düzenle"}</button>
        </div>
        {settings && !showSettings && (
          <p className="text-xs text-stone-500 mt-1">
            {settings.auto_issue_on_checkout ? <b className="text-emerald-700" data-testid="tr-efatura-auto-on">⚡ Check-out'ta otomatik fatura açık{settings.email_guest_copy !== false ? " + misafire e-posta" : ""}</b> : <span data-testid="tr-efatura-auto-off">Otomatik fatura kapalı</span>} · {integrators.find((i) => i.id === settings.integrator)?.label} · {settings.mode === "live" ? "Canlı" : "Test"} modu · {settings.api_key_masked ? `Anahtar ${settings.api_key_masked}` : "API anahtarı yok → gönderimler simüle edilir"} · {presets.find((p) => p.id === settings.vat_preset)?.label || `Özel %${settings.vat_rate}`}
          </p>
        )}
        {settings && showSettings && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
            <div>
              <label className="text-xs text-stone-500">Entegratör</label>
              <select value={settings.integrator} onChange={(e) => setSettings({ ...settings, integrator: e.target.value })} className={inp} data-testid="tr-efatura-integrator">
                {integrators.map((i) => <option key={i.id} value={i.id}>{i.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-stone-500">Mod</label>
              <select value={settings.mode} onChange={(e) => setSettings({ ...settings, mode: e.target.value })} className={inp} data-testid="tr-efatura-mode">
                <option value="test">Test</option><option value="live">Canlı</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-stone-500">API anahtarı {settings.api_key_masked && <span className="text-stone-400">(kayıtlı {settings.api_key_masked})</span>}</label>
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={settings.api_key_masked ? "Değiştirmek için yeni anahtar" : "Entegratör API anahtarı"} className={inp} data-testid="tr-efatura-apikey" />
            </div>
            <div className="md:col-span-2">
              <label className="text-xs text-stone-500">KDV / VAT bölgesi & oranı</label>
              <select value={settings.vat_preset || "custom"} onChange={(e) => onPreset(e.target.value)} className={inp} data-testid="tr-efatura-vat-preset">
                {["tr", "uk", "eu", "us", "custom"].map((r) => (
                  <optgroup key={r} label={{ tr: "🇹🇷 Türkiye", uk: "🇬🇧 United Kingdom", eu: "🇪🇺 Europe", us: "🇺🇸 United States", custom: "Özel" }[r]}>
                    {presets.filter((p) => p.region === r).map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
                  </optgroup>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-stone-500">Oran %</label>
                <input type="number" min="0" max="60" step="0.5" value={settings.vat_rate} disabled={settings.vat_preset !== "custom"} onChange={(e) => setSettings({ ...settings, vat_rate: e.target.value })} className={`${inp} disabled:bg-stone-50`} data-testid="tr-efatura-vat-rate" />
              </div>
              <div>
                <label className="text-xs text-stone-500">Vergi etiketi</label>
                <input value={settings.tax_label} disabled={settings.vat_preset !== "custom"} onChange={(e) => setSettings({ ...settings, tax_label: e.target.value })} className={`${inp} disabled:bg-stone-50`} data-testid="tr-efatura-tax-label" />
              </div>
            </div>
            <div>
              <label className="text-xs text-stone-500">Satıcı VKN / TCKN</label>
              <input value={settings.sender_vkn || ""} onChange={(e) => { setSettings({ ...settings, sender_vkn: e.target.value }); checkVkn(e.target.value); }} className={`${inp} ${vknCheck ? (vknCheck.valid ? "border-emerald-400" : "border-red-400") : ""}`} placeholder="10 haneli VKN veya 11 haneli TCKN" data-testid="tr-efatura-vkn" />
              {vknCheck && <div className={`text-[10px] mt-0.5 ${vknCheck.valid ? "text-emerald-600" : "text-red-600"}`} data-testid="tr-efatura-vkn-check">{vknCheck.valid ? `✓ Geçerli ${vknCheck.type.toUpperCase()}` : "✗ Geçersiz numara"}</div>}
            </div>
            <div>
              <label className="text-xs text-stone-500">Satıcı ünvanı</label>
              <input value={settings.sender_name || ""} onChange={(e) => setSettings({ ...settings, sender_name: e.target.value })} className={inp} data-testid="tr-efatura-sender-name" />
            </div>
            <div>
              <label className="text-xs text-stone-500">Satıcı adresi</label>
              <input value={settings.sender_address || ""} onChange={(e) => setSettings({ ...settings, sender_address: e.target.value })} className={inp} data-testid="tr-efatura-sender-address" />
            </div>
            <div className="md:col-span-3 rounded-lg bg-stone-50 border border-stone-200 p-3 grid grid-cols-1 md:grid-cols-4 gap-2 items-center" data-testid="tr-efatura-auto-box">
              <label className="text-xs font-semibold text-stone-800 flex items-center gap-2"><input type="checkbox" checked={!!settings.auto_issue_on_checkout} onChange={(e) => setSettings({ ...settings, auto_issue_on_checkout: e.target.checked })} data-testid="tr-efatura-auto-toggle" /> Check-out'ta otomatik fatura</label>
              <label className={`text-xs flex items-center gap-2 ${settings.auto_issue_on_checkout ? "text-stone-700" : "text-stone-400"}`}><input type="checkbox" disabled={!settings.auto_issue_on_checkout} checked={settings.auto_submit !== false} onChange={(e) => setSettings({ ...settings, auto_submit: e.target.checked })} data-testid="tr-efatura-auto-submit" /> GİB'e otomatik gönder</label>
              <label className={`text-xs flex items-center gap-2 ${settings.auto_issue_on_checkout ? "text-stone-700" : "text-stone-400"}`}><input type="checkbox" disabled={!settings.auto_issue_on_checkout} checked={settings.email_guest_copy !== false} onChange={(e) => setSettings({ ...settings, email_guest_copy: e.target.checked })} data-testid="tr-efatura-auto-email" /> Misafire e-posta kopyası</label>
              <select value={settings.auto_invoice_type || "earsiv"} disabled={!settings.auto_issue_on_checkout} onChange={(e) => setSettings({ ...settings, auto_invoice_type: e.target.value })} className="px-2 py-1.5 rounded-lg border border-stone-300 text-xs bg-white disabled:bg-stone-100" data-testid="tr-efatura-auto-type">
                <option value="earsiv">e-Arşiv (B2C)</option><option value="efatura">e-Fatura (B2B)</option>
              </select>
            </div>
            <div className="md:col-span-3 flex items-center justify-between">
              <span className="text-[11px] text-stone-500">API anahtarı olmadan gönderimler <b>simüle</b> edilir (ETTN üretilir, outbox'a yazılır). Anahtar eklendiğinde entegratöre iletilir.</span>
              <button onClick={saveSettings} disabled={savingSt} className="px-4 py-2 bg-stone-900 text-white rounded-lg text-sm font-medium disabled:opacity-50" data-testid="tr-efatura-settings-save">{savingSt ? "Kaydediliyor…" : "Ayarları kaydet"}</button>
            </div>
          </div>
        )}
      </div>

      {/* Build form */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Yeni Fatura Oluştur (UBL-TR 2.1)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div className="md:col-span-2">
            <label className="text-xs text-stone-500">Rezervasyon</label>
            <select value={bookingId} onChange={(e) => setBookingId(e.target.value)} className={inp} data-testid="tr-efatura-booking-select">
              <option value="">— Rezervasyon seçin —</option>
              {bookings.slice(0, 50).map((b) => (
                <option key={b.id} value={b.id}>{`${b.guest_name} · ${b.check_in} → ${b.check_out} · ${b.total_price}${b.tr_invoice_no ? ` · ✓ ${b.tr_invoice_no}` : ""}`}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-stone-500">Tür</label>
            <select value={type} onChange={(e) => setType(e.target.value)} className={inp} data-testid="tr-efatura-type">
              <option value="earsiv">e-Arşiv (B2C)</option>
              <option value="efatura">e-Fatura (B2B / VKN)</option>
            </select>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button onClick={build} disabled={building || !bookingId} className="px-4 py-2 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700 disabled:opacity-50 flex items-center gap-2" data-testid="tr-efatura-build">
            <FileText size={14} />{building ? "Oluşturuluyor…" : "Fatura XML Oluştur"}
          </button>
          <span className="text-xs text-stone-400 mx-1">veya</span>
          <input type="month" value={bulkMonth} onChange={(e) => setBulkMonth(e.target.value)} className="px-3 py-2 rounded-lg border border-stone-300 text-sm bg-white" data-testid="tr-efatura-bulk-month" />
          <button onClick={bulk} disabled={bulkBusy} className="px-4 py-2 bg-stone-900 text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2" data-testid="tr-efatura-bulk">
            <ArrowsClockwise size={14} className={bulkBusy ? "animate-spin" : ""} />{bulkBusy ? "Üretiliyor…" : "Aylık toplu fatura"}
          </button>
          {bulkResult && <span className="text-xs text-stone-600" data-testid="tr-efatura-bulk-result">{bulkResult.month}: <b>{bulkResult.created}</b> oluşturuldu{bulkResult.failed ? `, ${bulkResult.failed} başarısız` : ""}</span>}
        </div>

        {lastBuilt && (
          <div className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center gap-3">
            <CheckCircle size={18} className="text-emerald-600 shrink-0" />
            <div className="flex-1 text-sm">
              <div className="font-medium text-emerald-900">{lastBuilt.invoice_no}</div>
              <div className="text-xs text-emerald-800 mt-0.5">{lastBuilt.type} · {lastBuilt.total} {lastBuilt.currency} (vergi {lastBuilt.tax_total})</div>
            </div>
            <button onClick={() => downloadXml(lastBuilt.xml, lastBuilt.filename)} className="px-3 py-1.5 bg-emerald-600 text-white rounded-md text-xs font-medium hover:bg-emerald-700 flex items-center gap-1.5" data-testid="tr-efatura-download">
              <Download size={12} /> XML İndir
            </button>
          </div>
        )}
      </div>

      {/* List */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Fatura Listesi</h3>
        {list.length === 0 && <div className="text-xs text-stone-500 py-4 text-center">Henüz fatura yok.</div>}
        <div className="divide-y divide-stone-100">
          {list.map((inv) => (
            <div key={inv.id} className="flex items-center gap-3 py-2.5 text-sm" data-testid={`tr-efatura-row-${inv.id}`}>
              <div className="flex-1 min-w-0">
                <div className="font-medium text-stone-900 font-mono text-xs">{inv.invoice_no}{inv.auto_issued && <span className="ml-1.5 text-[9px] px-1 py-0.5 rounded bg-emerald-100 text-emerald-700 font-bold" data-testid={`tr-efatura-auto-badge-${inv.id}`}>OTO</span>}{inv.ettn && <span className="ml-2 text-[10px] text-stone-400 font-normal">ETTN {inv.ettn.slice(0, 8)}…{inv.simulated ? " · sim" : ""}</span>}</div>
                <div className="text-xs text-stone-500 mt-0.5">{inv.recipient_name} · {inv.type} · {inv.total} {inv.currency || "TRY"} · %{inv.tax_rate ?? "-"} {inv.tax_label || "KDV"} · {inv.issue_date}</div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full ${statusCls[inv.status] || "bg-stone-100 text-stone-700"}`} data-testid={`tr-efatura-status-${inv.id}`}>{statusTr[inv.status] || inv.status}</span>
              <button onClick={() => preview(inv.id)} className="text-xs px-2 py-1 rounded-md bg-stone-100 hover:bg-stone-200 text-stone-700" data-testid={`tr-efatura-preview-${inv.id}`}>Önizle</button>
              {inv.status === "built" && (
                <button onClick={() => submit(inv.id)} className="text-xs px-2 py-1 rounded-md bg-sky-600 text-white hover:bg-sky-700 flex items-center gap-1" data-testid={`tr-efatura-submit-${inv.id}`}>
                  <PaperPlaneTilt size={11} /> GİB'e Gönder
                </button>
              )}
              {inv.status !== "cancelled" && (
                <button onClick={() => cancel(inv.id)} className="text-xs px-2 py-1 rounded-md text-red-600 hover:bg-red-50" data-testid={`tr-efatura-cancel-${inv.id}`}>İptal</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, subtitle, icon: Icon, accent }) {
  const accentMap = { emerald: "text-emerald-700", rose: "text-rose-600", sky: "text-sky-700" };
  return (
    <div className="p-4 rounded-xl bg-white border border-stone-200">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-stone-500 mb-1">
        {Icon && <Icon size={11} />}
        <span>{label}</span>
      </div>
      <div className={`text-2xl font-bold ${accent ? accentMap[accent] : "text-stone-900"}`}>
        {value}
      </div>
      {subtitle && <div className="text-xs text-stone-500 mt-0.5">{subtitle}</div>}
    </div>
  );
}
