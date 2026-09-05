/**
 * Accounting Export — QuickBooks Online / Xero CSV downloader.
 * Saves accountants 4-8h/month. Most small PMSes lack this.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import AccountingConnectorsCard from "./AccountingConnectorsCard";
import JournalCalendarCard from "./JournalCalendarCard";
import {
  Download, RefreshCw, Loader2, FileSpreadsheet, Calendar, Calculator, Settings, X, Check,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cur = (v) => `£${Number(v || 0).toLocaleString("en-GB", { maximumFractionDigits: 2 })}`;

const FORMATS = [
  { id: "quickbooks", label: "QuickBooks Online (Journal CSV)" },
  { id: "xero",       label: "Xero (Sales Invoice CSV)" },
];

export default function AccountingExportPanel({ propertyId, hotelName = "" }) {
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";
  const [from, setFrom] = useState(firstOfMonth);
  const [to, setTo] = useState(today);
  const [format, setFormat] = useState("quickbooks");
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(null);
  const [showMapping, setShowMapping] = useState(false);
  const [mapping, setMapping] = useState(null);
  const [savingMap, setSavingMap] = useState(false);

  const openMapping = async () => {
    try {
      const { data } = await axios.get(`${API}/accounting/mapping/${propertyId}`);
      setMapping(data);
      setShowMapping(true);
    } catch { toast.error("Failed to load mapping"); }
  };

  const saveMapping = async () => {
    setSavingMap(true);
    try {
      await axios.post(`${API}/accounting/mapping/${propertyId}`, mapping);
      toast.success("Mapping saved");
      setShowMapping(false);
    } catch { toast.error("Save failed"); }
    setSavingMap(false);
  };

  const loadSummary = useCallback(async () => {
    if (!propertyId || !from || !to) return;
    setLoading(true);
    try {
      const { data } = await axios.get(
        `${API}/accounting/export/${propertyId}/summary?from_=${from}&to=${to}`
      );
      setSummary(data);
    } catch { toast.error("Failed to load summary"); }
    setLoading(false);
  }, [propertyId, from, to]);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  const download = async (kind) => {
    setDownloading(kind);
    try {
      const url = `${API}/accounting/export/${propertyId}/${kind}?from_=${from}&to=${to}&format=${format}`;
      const r = await axios.get(url, { responseType: "blob" });
      const blob = new Blob([r.data], { type: "text/csv" });
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `${kind}_${propertyId}_${from}_to_${to}_${format}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(objectUrl);
      toast.success(`${kind} CSV downloaded`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Download failed");
    }
    setDownloading(null);
  };

  return (
    <div className="p-5 space-y-5" data-testid="accounting-export-panel">
      <AccountingConnectorsCard propertyId={propertyId} />
      <JournalCalendarCard propertyId={propertyId} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Calculator className="w-5 h-5 text-emerald-400" />Accounting Export
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">Download QuickBooks / Xero CSVs for offline import</p>
        </div>
        <button onClick={openMapping} data-testid="ae-mapping-open"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-white text-xs font-bold">
          <Settings className="w-3.5 h-3.5" />Account mapping
        </button>
      </div>

      {/* Filters */}
      <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-4 space-y-3" data-testid="ae-filters">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1 flex items-center gap-1">
              <Calendar className="w-3 h-3" />From
            </label>
            <input type="date" value={from} onChange={e => setFrom(e.target.value)}
              className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-sm rounded-lg px-3 py-2"
              data-testid="ae-from" />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1 flex items-center gap-1">
              <Calendar className="w-3 h-3" />To
            </label>
            <input type="date" value={to} onChange={e => setTo(e.target.value)}
              className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-sm rounded-lg px-3 py-2"
              data-testid="ae-to" />
          </div>
          <div>
            <label className="block text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">Format</label>
            <select value={format} onChange={e => setFormat(e.target.value)}
              className="w-full bg-stone-800 border border-stone-700 text-stone-100 text-sm rounded-lg px-3 py-2"
              data-testid="ae-format">
              {FORMATS.map(f => <option key={f.id} value={f.id}>{f.label}</option>)}
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={loadSummary} disabled={loading} data-testid="ae-refresh"
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-stone-700 hover:bg-stone-600 text-white text-sm font-bold">
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh
            </button>
          </div>
        </div>

        {/* Summary tiles */}
        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2" data-testid="ae-summary">
            <Tile label="Bookings"        value={summary.bookings_count ?? 0}        color="text-cyan-300" />
            <Tile label="Total revenue"   value={cur(summary.total_revenue)}         color="text-emerald-300" />
            <Tile label="Payments"        value={summary.payments_count ?? 0}        color="text-violet-300" />
          </div>
        )}
      </div>

      {/* Download cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="ae-downloads">
        <DownloadCard
          icon={FileSpreadsheet} title="Sales / Revenue"
          subtitle="Bookings as journal entries (DR AR / CR Revenue) or sales invoices"
          onClick={() => download("sales")}
          loading={downloading === "sales"}
          testId="ae-download-sales"
        />
        <DownloadCard
          icon={FileSpreadsheet} title="Payments / Receipts"
          subtitle="Captured payments as cash receipts (DR Cash / CR AR)"
          onClick={() => download("payments")}
          loading={downloading === "payments"}
          testId="ae-download-payments"
        />
      </div>

      <div className="text-[11px] text-stone-500 text-center">
        Format: <strong className="text-stone-300">{FORMATS.find(f => f.id === format)?.label}</strong> ·
        {" "}Window: {from} → {to}
      </div>

      {/* Mapping modal */}
      {showMapping && mapping && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setShowMapping(false)}>
          <div onClick={e => e.stopPropagation()} className="bg-stone-900 border border-stone-700 rounded-2xl p-5 w-full max-w-lg" data-testid="ae-mapping-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-stone-100">Account-code mapping</h3>
              <button onClick={() => setShowMapping(false)} className="text-stone-400 hover:text-white"><X className="w-4 h-4" /></button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {[
                ["ar_account",          "QB · A/R account"],
                ["revenue_account",     "QB · Revenue account"],
                ["cash_account",        "QB · Cash account"],
                ["xero_revenue_code",   "Xero · Revenue code"],
                ["xero_payment_code",   "Xero · Payment code"],
                ["xero_tax_type",       "Xero · Tax type"],
              ].map(([k, label]) => (
                <div key={k}>
                  <label className="block text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">{label}</label>
                  <input value={mapping[k] || ""} onChange={e => setMapping({ ...mapping, [k]: e.target.value })}
                    className="w-full bg-stone-800 border border-stone-700 text-stone-100 rounded-lg px-2.5 py-1.5"
                    data-testid={`ae-mapping-${k}`} />
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowMapping(false)} className="px-3 py-1.5 rounded-lg bg-stone-700 text-stone-200 text-xs font-bold">Cancel</button>
              <button onClick={saveMapping} disabled={savingMap} data-testid="ae-mapping-save"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold">
                {savingMap ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Tile({ label, value, color }) {
  return (
    <div className="bg-stone-800/40 rounded-xl p-3">
      <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1">{label}</div>
      <div className={`text-2xl font-black tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function DownloadCard({ icon: Icon, title, subtitle, onClick, loading, testId }) {
  return (
    <button onClick={onClick} disabled={loading} data-testid={testId}
      className="bg-stone-900/60 border border-stone-800 hover:border-emerald-500/40 hover:bg-emerald-500/5 rounded-2xl p-4 text-left transition disabled:opacity-50">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-lg bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center">
          <Icon className="w-5 h-5 text-emerald-300" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-stone-100">{title}</h3>
          <p className="text-[11px] text-stone-400">{subtitle}</p>
        </div>
      </div>
      <div className="flex items-center justify-end text-emerald-300 text-xs font-bold gap-1">
        {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
        {loading ? "Generating…" : "Download CSV"}
      </div>
    </button>
  );
}
