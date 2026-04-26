/**
 * Group Rooming List CSV Import
 * -----------------------------
 * Pastes / uploads CSV, previews matched bookings, commits as group children.
 */
import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, FileSpreadsheet, Upload, CheckCircle2, AlertTriangle, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SAMPLE = `guest_name,email,phone,room_type,arrival,departure,rate_override,notes
Jane Doe,jane@acme.com,+447700900111,Double,2026-05-01,2026-05-03,,Late arrival
John Smith,john@acme.com,,Suite,2026-05-01,2026-05-03,180,VIP`;

export default function GroupRoomingImportPanel({ propertyId, hotelName = "" }) {
  const [groups, setGroups] = useState([]);
  const [groupId, setGroupId] = useState("");
  const [csvText, setCsvText] = useState("");
  const [preview, setPreview] = useState(null);
  const [committing, setCommitting] = useState(false);
  const [committed, setCommitted] = useState([]);

  useEffect(() => {
    if (!propertyId) return;
    axios.get(`${API}/groups/?property_id=${propertyId}`).then((r) => setGroups(r.data || []))
      .catch(() => setGroups([]));
  }, [propertyId]);

  useEffect(() => { if (groupId) loadCommitted(groupId); }, [groupId]);

  const loadCommitted = async (gid) => {
    try {
      const { data } = await axios.get(`${API}/group-rooming/${gid}`);
      setCommitted(data.items || []);
    } catch { /* swallow */ }
  };

  const onPreview = async () => {
    if (!groupId) return toast.error("Pick a group");
    if (!csvText.trim()) return toast.error("Paste CSV first");
    try {
      const { data } = await axios.post(`${API}/group-rooming/preview`, { group_id: groupId, csv_text: csvText });
      setPreview(data);
      if (data.warnings?.length) toast.warning(`${data.warnings.length} warning(s)`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Preview failed"); }
  };

  const onCommit = async () => {
    if (!preview?.rows?.length) return;
    setCommitting(true);
    try {
      const { data } = await axios.post(`${API}/group-rooming/commit`, { group_id: groupId, rows: preview.rows });
      toast.success(`${data.created} bookings created`);
      setPreview(null); setCsvText("");
      loadCommitted(groupId);
    } catch (e) { toast.error(e?.response?.data?.detail || "Commit failed"); }
    setCommitting(false);
  };

  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => setCsvText(String(reader.result || ""));
    reader.readAsText(f);
  };

  return (
    <div className="space-y-6" data-testid="group-rooming-panel">
      <div>
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-5 h-5 text-orange-400" />
          <h2 className="text-2xl font-semibold text-stone-100">Group Rooming List Import</h2>
        </div>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Bulk-create group bookings from a spreadsheet.</p>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-5 space-y-3">
        <select data-testid="group-rooming-pick" value={groupId} onChange={(e) => setGroupId(e.target.value)}
          className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm">
          <option value="">— Pick a group booking —</option>
          {groups.map((g) => (
            <option key={g.id} value={g.id}>{g.client_name || g.name} · {g.check_in} → {g.check_out}</option>
          ))}
        </select>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 px-3 py-2 rounded bg-stone-800 hover:bg-stone-700 border border-stone-700 cursor-pointer text-sm text-stone-100">
            <Upload className="w-4 h-4" /> Upload .csv
            <input data-testid="group-rooming-file" type="file" accept=".csv" onChange={onFile} className="hidden" />
          </label>
          <button onClick={() => setCsvText(SAMPLE)} className="text-xs px-2 py-1 rounded bg-stone-800 text-stone-300 border border-stone-700">
            Use sample
          </button>
        </div>
        <textarea data-testid="group-rooming-csv" rows={6} value={csvText} onChange={(e) => setCsvText(e.target.value)}
          placeholder="Paste CSV here (guest_name,email,phone,room_type,arrival,departure,rate_override,notes)"
          className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs font-mono" />
        <button data-testid="group-rooming-preview-btn" onClick={onPreview}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-orange-500/20 border border-orange-500/40 text-orange-200 text-sm">
          <CheckCircle2 className="w-4 h-4" /> Preview
        </button>
      </div>

      {preview && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-stone-100 font-semibold">{preview.row_count} row(s) parsed</div>
            <button data-testid="group-rooming-commit-btn" onClick={onCommit} disabled={committing}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
              {committing ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Create {preview.row_count} bookings
            </button>
          </div>
          {preview.warnings?.length > 0 && (
            <div className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-200">
              <div className="flex items-center gap-1 font-medium mb-1"><AlertTriangle className="w-3 h-3" /> Warnings</div>
              {preview.warnings.map((w, i) => <div key={i}>• {w}</div>)}
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                <tr>
                  <th className="px-2 py-1">Guest</th><th className="px-2 py-1">Type</th>
                  <th className="px-2 py-1">In</th><th className="px-2 py-1">Out</th>
                  <th className="px-2 py-1 text-right">Rate</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((r, i) => (
                  <tr key={i} className="border-t border-stone-800/60 text-stone-200">
                    <td className="px-2 py-1">{r.guest_name}</td>
                    <td className="px-2 py-1">{r.room_type_name || <span className="text-rose-400">—</span>}</td>
                    <td className="px-2 py-1 text-stone-400">{r.check_in}</td>
                    <td className="px-2 py-1 text-stone-400">{r.check_out}</td>
                    <td className="px-2 py-1 text-right">£{(r.rate || 0).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {committed.length > 0 && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-stone-100 font-semibold">Group bookings on file ({committed.length})</div>
            <button onClick={() => loadCommitted(groupId)} className="text-xs px-2 py-1 rounded bg-stone-800 text-stone-300 border border-stone-700 flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> Reload
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
            {committed.slice(0, 30).map((b) => (
              <div key={b.id} className="bg-stone-800/40 rounded px-2 py-1 flex items-center justify-between text-xs">
                <span className="text-stone-200">{b.guest_name}</span>
                <span className="text-stone-500">{b.booking_ref}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
