/**
 * Public API Developer Portal Panel
 * Issue keys, see usage, copy curl examples for the public sandbox.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, KeyRound, Copy, Plus, RotateCw, Trash2, RefreshCw, BookOpen } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const AVAILABLE_SCOPES = ["read:availability", "read:bookings", "read:rates", "read:reviews"];

export default function PublicApiPortalPanel({ propertyId, hotelName = "" }) {
  const [keys, setKeys] = useState([]);
  const [usage, setUsage] = useState(null);
  const [spec, setSpec] = useState(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: "", scopes: ["read:availability", "read:bookings"], rate_per_min: 60 });
  const [revealed, setRevealed] = useState(null);
  const [testKey, setTestKey] = useState("");
  const [testResult, setTestResult] = useState(null);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: k }, { data: u }, { data: s }] = await Promise.all([
        axios.get(`${API}/developer/keys?property_id=${propertyId}`),
        axios.get(`${API}/developer/usage/${propertyId}?days=30`),
        axios.get(`${API}/developer/spec`),
      ]);
      setKeys(k.items || []);
      setUsage(u);
      setSpec(s);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const issue = async () => {
    if (!form.name) return toast.error("Name required");
    try {
      const { data } = await axios.post(`${API}/developer/keys`, { property_id: propertyId, ...form });
      setRevealed({ secret: data.secret, prefix: data.key.secret_prefix, name: data.key.name });
      setAdding(false);
      toast.success("Key issued — copy the secret, it won't be shown again");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const rotate = async (k) => {
    if (!window.confirm(`Rotate "${k.name}"? Old secret will stop working.`)) return;
    try {
      const { data } = await axios.post(`${API}/developer/keys/${k.id}/rotate`, {});
      setRevealed({ secret: data.secret, prefix: data.secret.slice(0, 8), name: k.name + " (rotated)" });
      toast.success("Rotated. Update integrations.");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const revoke = async (k) => {
    if (!window.confirm(`Revoke key "${k.name}"?`)) return;
    try {
      await axios.delete(`${API}/developer/keys/${k.id}`);
      toast.success("Revoked");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const toggleScope = (s) => {
    setForm((f) => ({ ...f, scopes: f.scopes.includes(s) ? f.scopes.filter((x) => x !== s) : [...f.scopes, s] }));
  };

  const copy = (val) => { navigator.clipboard.writeText(val); toast.success("Copied"); };

  const runEcho = async () => {
    if (!testKey) return toast.error("Paste a secret");
    try {
      const { data } = await axios.post(`${API}/developer/sandbox/echo`,
        { message: "hello from portal", at: new Date().toISOString() },
        { headers: { "X-API-Key": testKey } });
      setTestResult(data);
      toast.success("Echo OK");
    } catch (e) {
      setTestResult({ error: e.response?.data?.detail || e.message });
      toast.error("Echo failed");
    }
  };

  return (
    <div className="space-y-6" data-testid="public-api-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Developer Portal · Public API</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Issue scoped API keys for partner integrations. Built-in sandbox + OpenAPI docs.</p>
      </div>

      {usage && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Active keys" value={keys.filter((k) => k.active).length} />
          <Stat label="Calls (30d)" value={usage.calls} />
          <Stat label="Errors" value={usage.errors} highlight={usage.errors > 0} />
          <Stat label="Endpoints used" value={Object.keys(usage.by_endpoint || {}).length} />
        </div>
      )}

      <div className="flex gap-2">
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
        <a href={`${API}/docs`} target="_blank" rel="noreferrer" className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          <BookOpen className="w-4 h-4" /> OpenAPI docs
        </a>
        <button data-testid="apikey-add-btn" onClick={() => setAdding(true)} className="ml-auto text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2">
          <Plus className="w-4 h-4" /> Issue key
        </button>
      </div>

      {adding && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
          <input data-testid="apikey-name-input" placeholder="Key name (e.g. My Channel Manager)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <div className="flex flex-wrap gap-2">
            {AVAILABLE_SCOPES.map((s) => (
              <label key={s} className={`text-xs px-2 py-1 rounded border cursor-pointer ${form.scopes.includes(s) ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>
                <input type="checkbox" className="hidden" checked={form.scopes.includes(s)} onChange={() => toggleScope(s)} />{s}
              </label>
            ))}
          </div>
          <div className="flex gap-2">
            <input type="number" placeholder="Rate per minute" value={form.rate_per_min} onChange={(e) => setForm({ ...form, rate_per_min: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs w-32" />
            <button data-testid="apikey-issue-btn" onClick={issue} className="ml-auto px-3 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-xs">Issue</button>
            <button onClick={() => setAdding(false)} className="px-3 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 text-xs">Cancel</button>
          </div>
        </div>
      )}

      {revealed && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 space-y-2" data-testid="apikey-reveal-box">
          <div className="text-xs uppercase tracking-wider text-amber-200">⚠ Copy this secret now — it cannot be retrieved later.</div>
          <div className="text-sm font-medium text-stone-100">{revealed.name}</div>
          <div className="flex gap-2">
            <code className="flex-1 px-3 py-2 rounded bg-stone-950 border border-stone-700 text-cyan-300 text-xs break-all">{revealed.secret}</code>
            <button onClick={() => copy(revealed.secret)} className="px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-xs flex items-center gap-1"><Copy className="w-3 h-3" /> Copy</button>
          </div>
          <button onClick={() => setRevealed(null)} className="text-xs text-stone-400 hover:text-stone-200">Dismiss</button>
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">Name</th><th className="px-3 py-2">Prefix</th><th className="px-3 py-2">Scopes</th><th className="px-3 py-2 text-right">Calls</th><th className="px-3 py-2">Last used</th><th className="px-3 py-2">Status</th><th className="px-3 py-2"></th></tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k.id} className="border-t border-stone-800/60 text-stone-200" data-testid="apikey-row">
                <td className="px-3 py-2"><KeyRound className="w-3 h-3 inline mr-1 text-stone-400" />{k.name}</td>
                <td className="px-3 py-2 font-mono text-xs text-stone-400">{k.secret_prefix}…</td>
                <td className="px-3 py-2 text-xs text-stone-400">{(k.scopes || []).join(", ")}</td>
                <td className="px-3 py-2 text-right">{k.calls_total || 0}</td>
                <td className="px-3 py-2 text-xs text-stone-400">{k.last_used_at ? k.last_used_at.slice(0, 16) : "—"}</td>
                <td className="px-3 py-2"><span className={`text-[10px] px-2 py-0.5 rounded border ${k.active ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>{k.active ? "active" : "revoked"}</span></td>
                <td className="px-3 py-2 text-right">
                  {k.active && (
                    <div className="flex gap-1 justify-end">
                      <button onClick={() => rotate(k)} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 text-xs flex items-center gap-1"><RotateCw className="w-3 h-3" /> Rotate</button>
                      <button data-testid="apikey-revoke-btn" onClick={() => revoke(k)} className="px-2 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200 text-xs flex items-center gap-1"><Trash2 className="w-3 h-3" /> Revoke</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {keys.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-stone-500">No API keys issued.</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Sandbox tester */}
      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
        <div className="text-xs uppercase tracking-wider text-stone-400">Sandbox echo (test auth)</div>
        <div className="flex gap-2">
          <input data-testid="sandbox-key-input" placeholder="Paste API secret (hk_...)" value={testKey} onChange={(e) => setTestKey(e.target.value)} className="flex-1 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm font-mono" />
          <button data-testid="sandbox-echo-btn" onClick={runEcho} className="px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 text-sm">Echo</button>
        </div>
        {testResult && (
          <pre className="text-xs bg-stone-950 border border-stone-800 rounded p-2 overflow-x-auto text-stone-300">{JSON.stringify(testResult, null, 2)}</pre>
        )}
      </div>

      {/* Spec / examples */}
      {spec && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-3">
          <div className="text-xs uppercase tracking-wider text-stone-400">Available sandbox endpoints</div>
          <div className="space-y-1 text-xs">
            {(spec.sandbox_endpoints || []).map((e, i) => (
              <div key={i} className="flex gap-2 items-center"><span className="font-mono px-2 py-0.5 rounded bg-stone-800 border border-stone-700 text-cyan-300">{e.method}</span><span className="text-stone-200">{e.path}</span></div>
            ))}
          </div>
          <pre className="text-xs bg-stone-950 border border-stone-800 rounded p-2 overflow-x-auto text-emerald-300">{spec.examples?.curl_echo}</pre>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-amber-500/10 border-amber-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-amber-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
