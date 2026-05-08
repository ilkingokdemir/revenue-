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
export default function TRCompliancePanel({ propertyId, hotelName }) {
  const [tab, setTab] = useState("kbs");
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

  const reload = React.useCallback(async () => {
    try {
      const [b, l] = await Promise.all([
        axios.get(`${API}/api/bookings?property_id=${propertyId}&limit=20`).catch(() => ({ data: { bookings: [] } })),
        axios.get(`${API}/api/tr-compliance/efatura/${propertyId}/list`),
      ]);
      setBookings(b?.data?.bookings || b?.data || []);
      setList(l.data.invoices || []);
      setStats({ total_count: l.data.total_count, total_amount: l.data.total_amount, by_status: l.data.by_status || {} });
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  const build = async () => {
    if (!bookingId) { toast.error("Önce bir rezervasyon seçin"); return; }
    setBuilding(true);
    try {
      const { data } = await axios.post(`${API}/api/tr-compliance/efatura/build`, {
        booking_id: bookingId,
        invoice_type: type,
      });
      setLastBuilt(data);
      toast.success(`Fatura ${data.invoice_no} oluşturuldu`);
      reload();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Fatura oluşturulamadı");
    }
    setBuilding(false);
  };

  const downloadXml = (xml, filename) => {
    const blob = new Blob([xml], { type: "application/xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  const markSubmitted = async (id) => {
    try {
      await axios.post(`${API}/api/tr-compliance/efatura/${id}/mark-submitted`);
      toast.success("GİB'e gönderildi olarak işaretlendi");
      reload();
    } catch (_) { toast.error("İşlem başarısız"); }
  };

  return (
    <div className="space-y-5" data-testid="tr-efatura-block">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Stat label="Toplam fatura" value={stats.total_count || 0} icon={Receipt} />
        <Stat label="Toplam tutar" value={`₺${(stats.total_amount || 0).toLocaleString("tr-TR")}`} accent="emerald" />
        <Stat label="GİB gönderilmiş" value={stats.by_status?.submitted || 0} accent="sky" />
      </div>

      {/* Build form */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Yeni Fatura Oluştur (UBL-TR 2.1)</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
          <div className="md:col-span-2">
            <label className="text-xs text-stone-500">Rezervasyon</label>
            <select
              value={bookingId}
              onChange={(e) => setBookingId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm bg-white"
              data-testid="tr-efatura-booking-select"
            >
              <option value="">— Rezervasyon seçin —</option>
              {bookings.slice(0, 50).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.guest_name} · {b.check_in} → {b.check_out} · ₺{b.total_price}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-stone-500">Tür</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-stone-300 text-sm bg-white"
              data-testid="tr-efatura-type"
            >
              <option value="earsiv">e-Arşiv (B2C)</option>
              <option value="efatura">e-Fatura (B2B / VKN)</option>
            </select>
          </div>
        </div>
        <div className="mt-3">
          <button
            onClick={build}
            disabled={building || !bookingId}
            className="px-4 py-2 bg-rose-600 text-white rounded-lg text-sm font-medium hover:bg-rose-700 disabled:opacity-50 flex items-center gap-2"
            data-testid="tr-efatura-build"
          >
            <FileText size={14} />
            {building ? "Oluşturuluyor…" : "Fatura XML Oluştur"}
          </button>
        </div>

        {lastBuilt && (
          <div className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center gap-3">
            <CheckCircle size={18} className="text-emerald-600 shrink-0" />
            <div className="flex-1 text-sm">
              <div className="font-medium text-emerald-900">
                {lastBuilt.invoice_no}
              </div>
              <div className="text-xs text-emerald-800 mt-0.5">
                {lastBuilt.type} · ₺{lastBuilt.total} (KDV ₺{lastBuilt.tax_total})
              </div>
            </div>
            <button
              onClick={() => downloadXml(lastBuilt.xml, lastBuilt.filename)}
              className="px-3 py-1.5 bg-emerald-600 text-white rounded-md text-xs font-medium hover:bg-emerald-700 flex items-center gap-1.5"
              data-testid="tr-efatura-download"
            >
              <Download size={12} /> XML İndir
            </button>
          </div>
        )}
      </div>

      {/* List */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Fatura Listesi</h3>
        {list.length === 0 && (
          <div className="text-xs text-stone-500 py-4 text-center">Henüz fatura yok.</div>
        )}
        <div className="divide-y divide-stone-100">
          {list.map((inv) => (
            <div key={inv.id} className="flex items-center gap-3 py-2.5 text-sm">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-stone-900 font-mono text-xs">
                  {inv.invoice_no}
                </div>
                <div className="text-xs text-stone-500 mt-0.5">
                  {inv.recipient_name} · {inv.type} · ₺{inv.total} · {inv.issue_date}
                </div>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                inv.status === "submitted" ? "bg-sky-100 text-sky-700" :
                inv.status === "accepted" ? "bg-emerald-100 text-emerald-700" :
                "bg-stone-100 text-stone-700"
              }`}>
                {inv.status}
              </span>
              {inv.status === "built" && (
                <button
                  onClick={() => markSubmitted(inv.id)}
                  className="text-xs px-2 py-1 rounded-md bg-stone-100 hover:bg-stone-200 text-stone-700 flex items-center gap-1"
                  data-testid={`tr-efatura-submit-${inv.id}`}
                >
                  <PaperPlaneTilt size={11} />
                  GİB'e Gönder
                </button>
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
