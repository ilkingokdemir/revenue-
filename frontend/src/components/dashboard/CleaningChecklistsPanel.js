/**
 * Cleaning Checklists Panel
 * -------------------------
 * Manage per-room-type templates + view today's runs + per-cleaner stats.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, ListChecks, Plus, RefreshCw, Trophy, Trash2, X, CheckCircle2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CleaningChecklistsPanel({ propertyId, hotelName = "" }) {
  const [templates, setTemplates] = useState([]);
  const [runs, setRuns] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [t, r, s] = await Promise.all([
        axios.get(`${API}/cleaning-checklists/${propertyId}/templates`),
        axios.get(`${API}/cleaning-checklists/${propertyId}/runs?days=7`),
        axios.get(`${API}/cleaning-checklists/${propertyId}/stats?days=30`),
      ]);
      setTemplates(t.data.items || []);
      setRuns(r.data || []);
      setStats(s.data);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setTemplates([]); setRuns([]); setStats(null); }, [propertyId]);

  const removeTpl = async (id) => {
    if (!window.confirm("Delete template?")) return;
    try { await axios.delete(`${API}/cleaning-checklists/${propertyId}/templates/${id}`); toast.success("Deleted"); load(); }
    catch { toast.error("Delete failed"); }
  };

  return (
    <div className="space-y-6" data-testid="cleaning-checklists-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ListChecks className="w-5 h-5 text-emerald-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Cleaning Checklists</h2>
          </div>
          <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Per-room-type checklists, photo evidence, supervisor sign-off.</p>
        </div>
        <div className="flex gap-2">
          <button data-testid="checklist-refresh-btn" onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button data-testid="checklist-new-template-btn"
            onClick={() => setEditing({ name: "Custom checklist", room_type_id: "", items: [] })}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 text-sm">
            <Plus className="w-4 h-4" /> New template
          </button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="Runs (30d)" value={stats.total} />
          <Stat label="Completed" value={stats.completed} />
          <Stat label="Avg score" value={`${stats.avg_score_pct}%`} highlight={stats.avg_score_pct >= 90} />
          <Stat label="Avg duration" value={`${stats.avg_duration_min}m`} />
          <Stat label="Sup. pass rate" value={`${stats.supervisor_pass_rate}%`} />
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12 text-stone-500"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : (
        <>
          <div>
            <div className="text-stone-100 font-semibold mb-2">Templates</div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {templates.map((t) => (
                <div key={t.id} data-testid="checklist-template-card"
                  className="rounded-lg border border-stone-800 bg-stone-900/60 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-stone-100 font-medium">{t.name}</div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => setEditing(t)} className="text-xs px-2 py-0.5 rounded bg-stone-800 text-stone-300 border border-stone-700">Edit</button>
                      <button onClick={() => removeTpl(t.id)} className="p-1 rounded text-stone-500 hover:text-rose-400">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="text-xs text-stone-400 mb-1">
                    {t.room_type_id ? `Room type: ${t.room_type_id}` : "Property default"} · {(t.items || []).length} items
                  </div>
                  <div className="flex flex-wrap gap-1 max-h-16 overflow-hidden">
                    {(t.items || []).slice(0, 6).map((i) => (
                      <span key={i.key} className="text-[10px] px-2 py-0.5 rounded bg-stone-800 text-stone-300 border border-stone-700">
                        {i.label}
                      </span>
                    ))}
                    {(t.items || []).length > 6 && <span className="text-stone-500 text-[10px] self-center">+{t.items.length - 6}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {stats?.by_cleaner?.length > 0 && (
            <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
              <div className="text-stone-100 font-semibold mb-3 flex items-center gap-2"><Trophy className="w-4 h-4 text-amber-400" />Top cleaners (30d)</div>
              <div className="space-y-1">
                {stats.by_cleaner.map((c) => (
                  <div key={c.name} className="flex items-center justify-between text-sm bg-stone-800/40 rounded px-2 py-1">
                    <span className="text-stone-200">{c.name}</span>
                    <span className="text-stone-400 text-xs">{c.runs} runs · avg {c.avg_score}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="text-stone-100 font-semibold mb-2">Recent runs (7d)</div>
            {runs.length === 0 ? (
              <div className="text-sm text-stone-500">No runs yet.</div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-stone-800 bg-stone-900/60">
                <table className="min-w-full text-sm">
                  <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
                    <tr>
                      <th className="px-3 py-2">Started</th>
                      <th className="px-3 py-2">Room</th>
                      <th className="px-3 py-2">Cleaner</th>
                      <th className="px-3 py-2 text-right">Score</th>
                      <th className="px-3 py-2 text-right">Duration</th>
                      <th className="px-3 py-2">Sup.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r) => (
                      <tr key={r.id} className="border-t border-stone-800/60 text-stone-200" data-testid="checklist-run-row">
                        <td className="px-3 py-2 text-xs text-stone-400">{new Date(r.started_at).toLocaleString()}</td>
                        <td className="px-3 py-2">{r.room_number || "—"}</td>
                        <td className="px-3 py-2">{r.completed_by || r.started_by}</td>
                        <td className={`px-3 py-2 text-right ${r.score_pct >= 90 ? "text-emerald-300" : r.score_pct >= 70 ? "text-amber-300" : "text-rose-300"}`}>{r.score_pct || 0}%</td>
                        <td className="px-3 py-2 text-right text-stone-400">{r.duration_min}m</td>
                        <td className="px-3 py-2">
                          {r.supervisor_passed
                            ? <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300">passed</span>
                            : <span className="text-[10px] text-stone-500">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {editing && (
        <TemplateEditor propertyId={propertyId} template={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
    </div>
  );
}

function Stat({ label, value, highlight }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-emerald-500/10 border-emerald-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-emerald-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}

function TemplateEditor({ propertyId, template, onClose, onSaved }) {
  const [name, setName] = useState(template.name || "");
  const [roomTypeId, setRoomTypeId] = useState(template.room_type_id || "");
  const [items, setItems] = useState(template.items?.length ? template.items : []);
  const [saving, setSaving] = useState(false);
  const addItem = () => setItems([...items, { key: `item_${items.length + 1}`, label: "", section: "general" }]);
  const updateItem = (i, patch) => setItems(items.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  const removeItem = (i) => setItems(items.filter((_, idx) => idx !== i));
  const save = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/cleaning-checklists/${propertyId}/templates`, {
        ...template, name, room_type_id: roomTypeId, items,
      });
      toast.success("Template saved");
      onSaved();
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-stone-900 border border-stone-800 rounded-xl max-w-2xl w-full p-5 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div className="text-stone-100 font-semibold">{template.id ? "Edit template" : "New template"}</div>
          <button onClick={onClose} className="p-1 rounded hover:bg-stone-800 text-stone-500"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-3 text-sm">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Template name"
            className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <input value={roomTypeId} onChange={(e) => setRoomTypeId(e.target.value)} placeholder="Room type ID (blank = property-wide default)"
            className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
          <div className="text-[10px] uppercase tracking-wider text-stone-400">Items</div>
          {items.map((it, i) => (
            <div key={i} className="flex items-center gap-2">
              <input value={it.label} onChange={(e) => updateItem(i, { label: e.target.value })} placeholder="Label"
                className="flex-1 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
              <input value={it.section || "general"} onChange={(e) => updateItem(i, { section: e.target.value })} placeholder="section"
                className="w-28 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
              <button onClick={() => removeItem(i)} className="p-1 rounded text-stone-500 hover:text-rose-400"><Trash2 className="w-3.5 h-3.5" /></button>
            </div>
          ))}
          <button onClick={addItem} className="text-xs px-2 py-1 rounded bg-stone-800 text-stone-300 border border-stone-700 flex items-center gap-1">
            <Plus className="w-3 h-3" /> Add item
          </button>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
          <button data-testid="checklist-save-template-btn" onClick={save} disabled={saving}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
