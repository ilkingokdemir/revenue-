import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Shield, Search, Download, Trash2, AlertTriangle, Clock, UserX, RefreshCw,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const GdprPanel = ({ user }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [exportBundle, setExportBundle] = useState(null);
  const [erasureFor, setErasureFor] = useState(null);
  const [reason, setReason] = useState("");
  const [log, setLog] = useState([]);
  const [loadingLog, setLoadingLog] = useState(false);

  const loadLog = async () => {
    setLoadingLog(true);
    try {
      const { data } = await axios.get(`${API}/gdpr/log?limit=50`);
      setLog(data || []);
    } catch (e) { /* silent */ }
    finally { setLoadingLog(false); }
  };
  useEffect(() => { loadLog(); }, []);

  const search = async () => {
    if (!query || query.length < 2) return toast.error("Enter at least 2 characters");
    setSearching(true);
    try {
      const { data } = await axios.get(`${API}/gdpr/search`, { params: { q: query } });
      setResults(data || []);
      if (!data?.length) toast.info("No guests match");
    } catch (e) { toast.error("Search failed"); }
    finally { setSearching(false); }
  };

  const doExport = async (email) => {
    try {
      const { data } = await axios.post(`${API}/gdpr/export`, { email, reason });
      setExportBundle(data);
      loadLog();
      toast.success("Export generated");
    } catch (e) { toast.error("Export failed"); }
  };

  const downloadBundle = () => {
    if (!exportBundle) return;
    const blob = new Blob([JSON.stringify(exportBundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gdpr-export-${exportBundle.guest_email}-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const doErasure = async () => {
    if (!erasureFor) return;
    try {
      const { data } = await axios.post(`${API}/gdpr/erasure`, { email: erasureFor, reason });
      toast.success(`Erased PII across ${Object.keys(data.affected || {}).length} collections`);
      setErasureFor(null);
      setReason("");
      setResults([]);
      setQuery("");
      loadLog();
    } catch (e) { toast.error("Erasure failed"); }
  };

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto" data-testid="gdpr-panel">
      <div className="bg-gradient-to-br from-rose-50 via-red-50 to-white border border-rose-100 rounded-2xl p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-rose-700">
              <Shield className="w-4 h-4" />GDPR · Article 17 &amp; 20
            </div>
            <h1 className="text-3xl font-black text-stone-900 mt-1">Data Rights Centre</h1>
            <p className="text-sm text-stone-600 mt-1">
              Fulfil guest data-portability and right-to-erasure requests. Every action is logged to an immutable audit trail.
            </p>
          </div>
        </div>
        <div className="mt-4 flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <div>
            <b>Important:</b> Erasure pseudonymises personal fields ([REDACTED]) while preserving primary keys and financial totals for
            tax &amp; AML legal retention (typically 6-10 years). Only a Data Protection Officer should trigger this action.
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="bg-white border border-stone-200 rounded-xl p-6">
        <h2 className="text-sm font-bold text-stone-800 mb-3 flex items-center gap-2"><Search className="w-4 h-4" />Find Guest</h2>
        <div className="flex gap-2">
          <input value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && search()}
            placeholder="Email or name (≥2 chars)"
            data-testid="gdpr-search-input"
            className="flex-1 border border-stone-200 rounded-lg px-3 py-2 text-sm" />
          <button onClick={search} disabled={searching} data-testid="gdpr-search-btn"
            className="px-4 py-2 bg-rose-600 hover:bg-rose-700 disabled:bg-stone-300 text-white rounded-lg text-sm font-semibold flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5" />{searching ? "Searching…" : "Search"}
          </button>
        </div>
        {results.length > 0 && (
          <div className="mt-4 space-y-2">
            {results.map(r => (
              <div key={r.email} data-testid={`gdpr-row-${r.email}`}
                className="flex items-center justify-between p-3 bg-stone-50 border border-stone-200 rounded-lg">
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-stone-800">{r.name || "(no name)"}</div>
                  <div className="text-xs text-stone-500">{r.email}{r.phone ? ` · ${r.phone}` : ""}</div>
                </div>
                <div className="flex gap-2">
                  <input placeholder="Reason (optional, logged)" value={reason} onChange={e => setReason(e.target.value)}
                    className="w-56 border border-stone-200 rounded-md px-2 py-1.5 text-xs" />
                  <button onClick={() => doExport(r.email)} data-testid={`gdpr-export-${r.email}`}
                    className="px-3 py-1.5 bg-sky-600 hover:bg-sky-700 text-white rounded-md text-xs font-semibold flex items-center gap-1">
                    <Download className="w-3 h-3" />Export
                  </button>
                  <button onClick={() => setErasureFor(r.email)} data-testid={`gdpr-erase-${r.email}`}
                    className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-md text-xs font-semibold flex items-center gap-1">
                    <UserX className="w-3 h-3" />Erase
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Export preview */}
      {exportBundle && (
        <div className="bg-white border border-sky-200 rounded-xl p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold text-sky-800 flex items-center gap-2"><Download className="w-4 h-4" />Export Ready · {exportBundle.guest_email}</h2>
            <div className="flex gap-2">
              <button onClick={downloadBundle} data-testid="gdpr-download-json"
                className="px-3 py-1.5 bg-sky-600 hover:bg-sky-700 text-white rounded-md text-xs font-semibold">Download JSON</button>
              <button onClick={() => setExportBundle(null)} className="px-3 py-1.5 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-md text-xs">Close</button>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(exportBundle.collections || {}).map(([coll, rows]) => (
              <div key={coll} className="p-3 bg-stone-50 rounded-lg">
                <div className="text-[10px] uppercase text-stone-400 font-bold">{coll}</div>
                <div className="text-xl font-black text-sky-700">{rows.length}</div>
                <div className="text-[10px] text-stone-500">record{rows.length === 1 ? "" : "s"}</div>
              </div>
            ))}
            {Object.keys(exportBundle.collections || {}).length === 0 && (
              <div className="col-span-4 text-xs text-stone-400 py-4 text-center">No personal data found.</div>
            )}
          </div>
        </div>
      )}

      {/* Audit log */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-stone-200 bg-stone-50">
          <h2 className="text-sm font-bold text-stone-800 flex items-center gap-2"><Clock className="w-4 h-4" />Audit Log</h2>
          <button onClick={loadLog} className="text-xs text-stone-500 hover:text-stone-800 flex items-center gap-1">
            <RefreshCw className={`w-3 h-3 ${loadingLog ? "animate-spin" : ""}`} />Refresh
          </button>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-[10px] uppercase text-stone-500">
            <tr>
              <th className="p-3 text-left">When</th>
              <th className="p-3 text-left">Action</th>
              <th className="p-3 text-left">Email</th>
              <th className="p-3 text-left">By</th>
              <th className="p-3 text-left">Details</th>
            </tr>
          </thead>
          <tbody>
            {log.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-stone-400">No GDPR actions logged yet.</td></tr>}
            {log.map(l => (
              <tr key={l.id} className="border-t border-stone-100" data-testid={`gdpr-log-${l.id}`}>
                <td className="p-3 text-xs text-stone-500">{l.performed_at?.slice(0, 19).replace("T", " ")}</td>
                <td className="p-3">
                  <span className={`inline-block px-2 py-0.5 text-[10px] font-bold uppercase rounded-full ${
                    l.action === "erasure" ? "bg-rose-100 text-rose-700" : "bg-sky-100 text-sky-700"
                  }`}>{l.action}</span>
                </td>
                <td className="p-3 text-xs font-mono">{l.email}</td>
                <td className="p-3 text-xs text-stone-500">{l.performed_by}</td>
                <td className="p-3 text-xs text-stone-500">
                  {l.action === "erasure"
                    ? Object.entries(l.affected || {}).map(([k, v]) => `${k}:${v}`).join(" · ")
                    : `${l.rows_exported || 0} rows · ${l.reason || "—"}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Erasure confirm modal */}
      {erasureFor && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setErasureFor(null)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 text-rose-700 mb-3">
              <UserX className="w-6 h-6" />
              <h2 className="text-lg font-black">Confirm Erasure</h2>
            </div>
            <p className="text-sm text-stone-700 mb-2">
              You are about to pseudonymise all personal data for:
            </p>
            <p className="p-2 bg-stone-100 rounded font-mono text-sm mb-3 break-all">{erasureFor}</p>
            <p className="text-xs text-stone-500 mb-3">
              This is <b>irreversible</b>. Fields like name, email, phone, passport number, signature, message bodies will be
              replaced with <code>[REDACTED]</code>. Financial totals and audit trails remain intact.
            </p>
            <input placeholder="Reason (required)" value={reason} onChange={e => setReason(e.target.value)}
              data-testid="gdpr-erase-reason"
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm mb-4" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setErasureFor(null)} className="px-4 py-2 text-sm">Cancel</button>
              <button onClick={doErasure} disabled={!reason} data-testid="gdpr-erase-confirm"
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 disabled:bg-stone-300 text-white rounded-lg text-sm font-semibold flex items-center gap-1.5">
                <Trash2 className="w-3.5 h-3.5" />Erase now
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GdprPanel;
