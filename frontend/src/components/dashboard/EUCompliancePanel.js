import React, { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Download,
  FileText,
  CheckCircle,
  ArrowsClockwise,
  Globe,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * EUCompliancePanel — Pan-European country-specific compliance.
 * Renders a card grid of 7 countries, each with 1-2 actions (invoice + optional police).
 * One-click: select dates → download XML bundle or TXT/CSV file.
 */
export default function EUCompliancePanel({ propertyId, hotelName }) {
  const [catalog, setCatalog] = useState({});
  const [history, setHistory] = useState([]);
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const [from, setFrom] = useState(weekAgo);
  const [to, setTo] = useState(today);
  const [busy, setBusy] = useState("");

  const load = React.useCallback(async () => {
    try {
      const [c, h] = await Promise.all([
        axios.get(`${API}/api/eu-compliance/catalog`),
        axios.get(`${API}/api/eu-compliance/${propertyId}/history`),
      ]);
      setCatalog(c.data.countries || {});
      setHistory(h.data.history || []);
    } catch (_) { /* silent */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const doExport = async (country, kind) => {
    const key = `${country}-${kind}`;
    setBusy(key);
    try {
      const { data } = await axios.post(`${API}/api/eu-compliance/export`, {
        property_id: propertyId,
        country, kind,
        from_date: from, to_date: to,
      });
      // Invoice returns files[]; police returns content
      if (kind === "invoice") {
        if (!data.files?.length) {
          toast.info("Bu aralıkta fatura üretilebilecek rezervasyon yok.");
        } else {
          // Bundle as a single file concatenated with clear separators
          const bundle = data.files.map(f => `<!-- ${f.filename} -->\n${f.content}`).join("\n\n");
          downloadText(bundle, `eu_${country}_invoices_${from}_${to}.xml`, "application/xml");
          toast.success(`${data.file_count} fatura (${data.total_amount}) indirildi`);
        }
      } else {
        if (!data.content) {
          toast.info("Bu aralıkta polis bildirimine uygun kayıt yok.");
        } else {
          const mime = data.format === "txt" ? "text/plain" : "text/csv";
          downloadText(data.content, data.filename, mime);
          toast.success(`${data.row_count} kayıt indirildi`);
        }
      }
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Export başarısız");
    }
    setBusy("");
  };

  const downloadText = (text, filename, mime) => {
    const blob = new Blob([text], { type: `${mime};charset=utf-8` });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="eu-compliance-panel">
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Globe size={12} weight="fill" className="text-sky-500" />
          <span>EU & MX Resmi Bildirim</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">
          Avrupa Uyum Merkezi · {hotelName || "Property"}
        </h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          7 ülke için e-fatura ve polis bildirim dosyaları. Dosya tipi ülke/evrak ayrı — tek tıkla indirin, ilgili portala yükleyin.
        </p>
      </div>

      {/* Date range selector */}
      <div className="flex flex-wrap items-center gap-3 p-3 rounded-xl bg-white border border-stone-200 mb-5">
        <label className="flex flex-col text-xs gap-1">
          <span className="text-stone-500">Başlangıç</span>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            className="px-2 py-1 rounded border border-stone-300 text-sm"
            data-testid="eu-from" />
        </label>
        <label className="flex flex-col text-xs gap-1">
          <span className="text-stone-500">Bitiş</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="px-2 py-1 rounded border border-stone-300 text-sm"
            data-testid="eu-to" />
        </label>
        <button onClick={load}
          className="ml-auto p-2 rounded text-stone-500 hover:text-stone-800"
          data-testid="eu-reload">
          <ArrowsClockwise size={14} />
        </button>
      </div>

      {/* Country grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-7">
        {Object.entries(catalog).map(([code, meta]) => (
          <div key={code} className="p-4 rounded-xl bg-white border border-stone-200"
            data-testid={`eu-country-${code}`}>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-2xl">{meta.flag}</span>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-stone-900 truncate">{meta.name}</div>
                <div className="text-[10px] uppercase tracking-wider text-stone-500 font-mono">{code}</div>
              </div>
            </div>
            <div className="space-y-2">
              {meta.invoice && (
                <ActionRow
                  label="e-Fatura"
                  scheme={meta.invoice.scheme}
                  onClick={() => doExport(code, "invoice")}
                  busy={busy === `${code}-invoice`}
                  testId={`eu-${code}-invoice`}
                />
              )}
              {meta.police && (
                <ActionRow
                  label="Polis Bildirim"
                  scheme={meta.police.scheme}
                  onClick={() => doExport(code, "police")}
                  busy={busy === `${code}-police`}
                  testId={`eu-${code}-police`}
                />
              )}
              {!meta.police && (
                <div className="text-[10px] text-stone-400 italic">Polis bildirimi gerektirmez</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* History */}
      <div className="p-4 rounded-xl bg-white border border-stone-200">
        <h3 className="text-sm font-semibold text-stone-900 mb-3">Son Aktarımlar</h3>
        {history.length === 0 && (
          <div className="text-xs text-stone-500 py-4 text-center">Henüz aktarım yok.</div>
        )}
        <div className="divide-y divide-stone-100">
          {history.slice(0, 15).map((h) => {
            const meta = catalog[h.country] || {};
            return (
              <div key={h.id} className="flex items-center gap-3 py-2.5 text-sm">
                <span className="text-xl">{meta.flag || "🌍"}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-stone-900 truncate">
                    {meta.name || h.country} · <span className="capitalize text-stone-600">{h.kind}</span>
                  </div>
                  <div className="text-xs text-stone-500 mt-0.5">
                    {h.from_date} → {h.to_date} · {h.file_count || h.row_count} adet
                    {h.total_amount ? ` · €${h.total_amount.toLocaleString("en-GB")}` : ""}
                  </div>
                </div>
                <span className="text-[10px] text-stone-500">{h.created_at?.slice(0, 10)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ActionRow({ label, scheme, onClick, busy, testId }) {
  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-stone-50 hover:bg-stone-100 transition">
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-stone-900">{label}</div>
        <div className="text-[10px] text-stone-500 truncate">{scheme}</div>
      </div>
      <button
        onClick={onClick}
        disabled={busy}
        data-testid={testId}
        className="px-2.5 py-1.5 bg-sky-600 text-white rounded-md text-xs font-medium hover:bg-sky-700 disabled:opacity-50 flex items-center gap-1.5"
      >
        {busy ? (
          <ArrowsClockwise size={12} className="animate-spin" />
        ) : (
          <Download size={12} />
        )}
        {busy ? "…" : "İndir"}
      </button>
    </div>
  );
}
