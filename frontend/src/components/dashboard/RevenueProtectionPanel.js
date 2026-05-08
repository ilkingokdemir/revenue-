/**
 * Revenue Protection Panel — Insurance + Parity Defender + Webhooks
 * -----------------------------------------------------------------
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, ShieldCheck, Cloud, Plus, Trash2, RefreshCw, Send, Webhook } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RevenueProtectionPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("insurance");
  return (
    <div className="space-y-6" data-testid="rev-protection-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Revenue Protection</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Insurance upsell · OTA parity defender · outbound webhooks.</p>
      </div>
      <div className="flex gap-2">
        <Tab active={tab === "insurance"} onClick={() => setTab("insurance")} testId="rp-tab-ins" icon={ShieldCheck}>Insurance</Tab>
        <Tab active={tab === "parity"} onClick={() => setTab("parity")} testId="rp-tab-parity" icon={Cloud}>Parity Defender</Tab>
        <Tab active={tab === "webhooks"} onClick={() => setTab("webhooks")} testId="rp-tab-wh" icon={Webhook}>Webhooks</Tab>
      </div>
      {tab === "insurance" && <InsuranceTab propertyId={propertyId} />}
      {tab === "parity" && <ParityTab propertyId={propertyId} />}
      {tab === "webhooks" && <WebhooksTab propertyId={propertyId} />}
    </div>
  );
}

function Tab({ active, onClick, icon: Icon, testId, children }) {
  return (
    <button data-testid={testId} onClick={onClick}
      className={`px-3 py-2 rounded-lg text-sm border flex items-center gap-2 ${active
        ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200"
        : "bg-stone-800 border-stone-700 text-stone-300 hover:bg-stone-700"}`}>
      <Icon className="w-4 h-4" />{children}
    </button>
  );
}

function InsuranceTab({ propertyId }) {
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [quote, setQuote] = useState(null);
  const [testTotal, setTestTotal] = useState(250);
  const load = useCallback(async () => {
    const { data } = await axios.get(`${API}/insurance/${propertyId}/config`);
    setCfg(data);
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  const save = async () => {
    setSaving(true);
    try { await axios.post(`${API}/insurance/${propertyId}/config`, cfg); toast.success("Saved"); }
    catch { toast.error("Save failed"); }
    setSaving(false);
  };
  const tryQuote = async () => {
    const { data } = await axios.post(`${API}/insurance/quote`, { property_id: propertyId, total: testTotal });
    setQuote(data);
  };
  if (!cfg) return <Loader2 className="w-5 h-5 animate-spin text-stone-500" />;
  return (
    <div className="space-y-4 rounded-xl border border-stone-800 bg-stone-900/60 p-4" data-testid="rp-insurance-tab">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
        <Field label="Enabled"><Toggle v={cfg.enabled} onChange={(v) => setCfg({ ...cfg, enabled: v })} /></Field>
        <Field label="Label"><input value={cfg.label} onChange={(e) => setCfg({ ...cfg, label: e.target.value })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" /></Field>
        <Field label="Rate %"><input type="number" step="0.1" value={cfg.rate_pct} onChange={(e) => setCfg({ ...cfg, rate_pct: parseFloat(e.target.value) || 0 })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" /></Field>
        <Field label="Currency"><input value={cfg.currency} onChange={(e) => setCfg({ ...cfg, currency: e.target.value })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" /></Field>
        <Field label="Min premium"><input type="number" step="0.01" value={cfg.min_premium} onChange={(e) => setCfg({ ...cfg, min_premium: parseFloat(e.target.value) || 0 })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" /></Field>
        <Field label="Max premium"><input type="number" step="0.01" value={cfg.max_premium} onChange={(e) => setCfg({ ...cfg, max_premium: parseFloat(e.target.value) || 0 })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" /></Field>
      </div>
      <button data-testid="rp-ins-save" onClick={save} disabled={saving}
        className="px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm flex items-center gap-2">
        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} Save
      </button>
      <div className="flex items-center gap-2 text-sm pt-2 border-t border-stone-800">
        <span className="text-stone-400">Quote test:</span>
        <input type="number" value={testTotal} onChange={(e) => setTestTotal(parseFloat(e.target.value) || 0)}
          className="w-24 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" />
        <button onClick={tryQuote} className="px-2 py-1 rounded bg-stone-800 text-stone-300 border border-stone-700 text-xs">Quote</button>
        {quote && (quote.available
          ? <span className="text-emerald-300 text-sm">{quote.label}: {quote.currency} {quote.premium}</span>
          : <span className="text-rose-300 text-sm">{quote.reason}</span>
        )}
      </div>
    </div>
  );
}

function ParityTab({ propertyId }) {
  const [cfg, setCfg] = useState(null);
  const [rec, setRec] = useState(null);
  const load = useCallback(async () => {
    const [c, r] = await Promise.all([
      axios.get(`${API}/parity-defender/${propertyId}/config`),
      axios.get(`${API}/parity-defender/${propertyId}/recommendation`),
    ]);
    setCfg(c.data); setRec(r.data);
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  const save = async () => {
    try { await axios.post(`${API}/parity-defender/${propertyId}/config`, cfg); toast.success("Saved"); load(); }
    catch { toast.error("Save failed"); }
  };
  if (!cfg) return <Loader2 className="w-5 h-5 animate-spin text-stone-500" />;
  return (
    <div className="space-y-4" data-testid="rp-parity-tab">
      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 gap-3 text-sm">
        <Field label="Enabled"><Toggle v={cfg.enabled} onChange={(v) => setCfg({ ...cfg, enabled: v })} /></Field>
        <Field label="Show savings badge"><Toggle v={cfg.show_savings_badge} onChange={(v) => setCfg({ ...cfg, show_savings_badge: v })} /></Field>
        <Field label="Undercut %"><input type="number" step="0.5" value={cfg.undercut_pct} onChange={(e) => setCfg({ ...cfg, undercut_pct: parseFloat(e.target.value) || 0 })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" /></Field>
        <Field label="Floor % of base"><input type="number" step="1" value={cfg.floor_pct_of_base} onChange={(e) => setCfg({ ...cfg, floor_pct_of_base: parseFloat(e.target.value) || 0 })} className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" /></Field>
      </div>
      <button data-testid="rp-parity-save" onClick={save} className="px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">Save</button>
      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
        <div className="text-stone-100 font-semibold mb-2">Recommendations from latest parity scan</div>
        {!rec || rec.recommendations.length === 0 ? (
          <div className="text-sm text-stone-500">No parity snapshots yet — run the rate scraper first.</div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-2 py-1">Date</th><th className="px-2 py-1">Lowest OTA</th><th className="px-2 py-1">Channel</th><th className="px-2 py-1 text-right">Direct</th><th className="px-2 py-1 text-right">Save</th></tr>
            </thead>
            <tbody>
              {rec.recommendations.slice(0, 14).map((r) => (
                <tr key={r.date} className="border-t border-stone-800/60 text-stone-200">
                  <td className="px-2 py-1 text-stone-400 text-xs">{r.date}</td>
                  <td className="px-2 py-1">£{r.lowest_ota.toFixed(2)}</td>
                  <td className="px-2 py-1 text-stone-400 text-xs">{r.lowest_ota_channel}</td>
                  <td className="px-2 py-1 text-right text-emerald-300">£{r.recommended_direct.toFixed(2)}</td>
                  <td className="px-2 py-1 text-right text-cyan-300">{r.savings_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function WebhooksTab({ propertyId }) {
  const [list, setList] = useState({ items: [], supported_events: [] });
  const [logs, setLogs] = useState([]);
  const [adding, setAdding] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const [newEvents, setNewEvents] = useState([]);
  const load = useCallback(async () => {
    const [a, b] = await Promise.all([
      axios.get(`${API}/webhooks/${propertyId}`),
      axios.get(`${API}/webhooks/${propertyId}/log`),
    ]);
    setList(a.data); setLogs(b.data);
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  const subscribe = async () => {
    if (!newUrl.startsWith("https://")) return toast.error("HTTPS URL required");
    setAdding(true);
    try {
      await axios.post(`${API}/webhooks/${propertyId}`, { url: newUrl, events: newEvents });
      toast.success("Subscribed");
      setNewUrl(""); setNewEvents([]); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Save failed"); }
    setAdding(false);
  };
  const remove = async (id) => {
    if (!window.confirm("Delete webhook?")) return;
    await axios.delete(`${API}/webhooks/${propertyId}/${id}`); toast.success("Deleted"); load();
  };
  const test = async (id) => {
    try {
      const { data } = await axios.post(`${API}/webhooks/${propertyId}/test/${id}`);
      toast[data.success ? "success" : "warning"](`HTTP ${data.status_code} · ${data.duration_ms}ms`);
      load();
    } catch { toast.error("Test failed"); }
  };
  return (
    <div className="space-y-4" data-testid="rp-webhooks-tab">
      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
        <div className="text-stone-100 font-semibold">Subscribe a new webhook</div>
        <input data-testid="rp-wh-url" placeholder="https://your-server.com/webhook" value={newUrl} onChange={(e) => setNewUrl(e.target.value)}
          className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
        <div className="flex flex-wrap gap-1">
          {list.supported_events.map((ev) => (
            <button key={ev} onClick={() => setNewEvents(newEvents.includes(ev) ? newEvents.filter((x) => x !== ev) : [...newEvents, ev])}
              className={`px-2 py-0.5 rounded text-[11px] border ${newEvents.includes(ev) ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200" : "bg-stone-800 border-stone-700 text-stone-400"}`}>
              {ev}
            </button>
          ))}
        </div>
        <button data-testid="rp-wh-add" onClick={subscribe} disabled={adding}
          className="flex items-center gap-2 px-3 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm">
          {adding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Subscribe
        </button>
      </div>

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
        <div className="text-stone-100 font-semibold mb-2">Active webhooks ({list.items.length})</div>
        {list.items.length === 0 ? <div className="text-sm text-stone-500">None.</div> : (
          <div className="space-y-2">
            {list.items.map((w) => (
              <div key={w.id} data-testid="rp-wh-row" className="border border-stone-800 rounded p-2 bg-stone-800/40">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-stone-100 text-sm truncate">{w.url}</div>
                    <div className="text-[10px] text-stone-500 mt-0.5">{w.events.join(" · ") || "(no events)"} · fires {w.fire_count} ({w.fail_count} fails)</div>
                  </div>
                  <button onClick={() => test(w.id)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-1">
                    <Send className="w-3 h-3" /> Test
                  </button>
                  <button onClick={() => remove(w.id)} className="p-1.5 rounded text-stone-500 hover:text-rose-400">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {logs.length > 0 && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4">
          <div className="text-stone-100 font-semibold mb-2">Recent fires</div>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {logs.map((l) => (
              <div key={l.id} className="flex items-center justify-between bg-stone-800/40 rounded px-2 py-1 text-xs">
                <span className="text-stone-300">{l.event}</span>
                <span className={l.success ? "text-emerald-300" : "text-rose-300"}>HTTP {l.status_code} · {l.duration_ms}ms</span>
                <span className="text-stone-500">{new Date(l.fired_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-stone-400">{label}</span>
      {children}
    </label>
  );
}
function Toggle({ v, onChange }) {
  return (
    <button onClick={() => onChange(!v)}
      className={`w-12 h-6 rounded-full relative transition ${v ? "bg-emerald-500/40" : "bg-stone-700"}`}>
      <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-stone-100 transition ${v ? "left-6" : "left-0.5"}`} />
    </button>
  );
}
