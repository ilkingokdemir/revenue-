/**
 * Loyalty Auto-Tier Panel
 * Configure thresholds, run sweep, view recent upgrades.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Crown, RefreshCw, ArrowUp, ArrowDown, Save } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const TIERS = ["bronze", "silver", "gold", "platinum"];

export default function LoyaltyAutoPanel({ propertyId, hotelName = "" }) {
  const [cfg, setCfg] = useState(null);
  const [log, setLog] = useState({ items: [], count: 0, upgrades: 0, downgrades: 0 });
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: c }, { data: l }] = await Promise.all([
        axios.get(`${API}/loyalty-auto/${propertyId}/config`),
        axios.get(`${API}/loyalty-auto/${propertyId}/upgrades?days=60`),
      ]);
      setCfg(c);
      setLog(l);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const updateTier = (idx, field, val) => {
    const tiers = [...cfg.tiers];
    tiers[idx] = { ...tiers[idx], [field]: parseFloat(val) || 0 };
    setCfg({ ...cfg, tiers });
  };

  const saveCfg = async () => {
    try {
      await axios.post(`${API}/loyalty-auto/config`, { property_id: propertyId, tiers: cfg.tiers });
      toast.success("Config saved");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const sweep = async () => {
    setRunning(true);
    try {
      const { data } = await axios.post(`${API}/loyalty-auto/sweep`, { property_id: propertyId });
      toast.success(`Scanned ${data.scanned}: ${data.upgraded}↑ / ${data.downgraded}↓ / ${data.unchanged} unchanged`);
      refresh();
    } catch { toast.error("Sweep failed"); }
    setRunning(false);
  };

  return (
    <div className="space-y-6" data-testid="loyalty-auto-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Loyalty Tier Auto-Upgrade</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Promote returning guests automatically when they cross your tier thresholds.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Stat label="Recent upgrades (60d)" value={log.upgrades} highlight />
        <Stat label="Downgrades" value={log.downgrades} />
        <Stat label="Total tier changes" value={log.count} />
      </div>

      {cfg && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-3">
          <div className="text-xs uppercase tracking-wider text-stone-400">Tier thresholds</div>
          <div className="space-y-2">
            {cfg.tiers.map((t, i) => (
              <div key={t.tier} className="flex gap-2 items-center" data-testid="loyalty-tier-row">
                <Crown className={`w-4 h-4 ${t.tier === "platinum" ? "text-violet-300" : t.tier === "gold" ? "text-amber-300" : t.tier === "silver" ? "text-stone-300" : "text-orange-400"}`} />
                <div className="w-20 text-sm text-stone-200 capitalize">{t.tier}</div>
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <label className="text-xs flex items-center gap-2"><span className="text-stone-500 w-24">Min stays</span>
                    <input type="number" min={0} value={t.min_stays} onChange={(e) => updateTier(i, "min_stays", e.target.value)} className="flex-1 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
                  </label>
                  <label className="text-xs flex items-center gap-2"><span className="text-stone-500 w-24">Min lifetime £</span>
                    <input type="number" min={0} value={t.min_lifetime} onChange={(e) => updateTier(i, "min_lifetime", e.target.value)} className="flex-1 px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs" />
                  </label>
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button data-testid="loyalty-save-cfg-btn" onClick={saveCfg} className="text-sm px-3 py-1 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 flex items-center gap-2"><Save className="w-3 h-3" /> Save thresholds</button>
            <button data-testid="loyalty-sweep-btn" onClick={sweep} disabled={running} className="text-sm px-3 py-1 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2">
              {running ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />} Run sweep now
            </button>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">When</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">From</th><th className="px-3 py-2">To</th><th className="px-3 py-2 text-right">Stays</th><th className="px-3 py-2 text-right">Lifetime</th><th className="px-3 py-2"></th></tr>
          </thead>
          <tbody>
            {log.items.map((r) => (
              <tr key={r.id} className="border-t border-stone-800/60 text-stone-200" data-testid="loyalty-log-row">
                <td className="px-3 py-2 text-xs text-stone-400">{(r.changed_at || "").slice(0, 16)}</td>
                <td className="px-3 py-2"><div>{r.guest_name || "—"}</div><div className="text-[10px] text-stone-500">{r.guest_email}</div></td>
                <td className="px-3 py-2 capitalize text-stone-400">{r.from_tier}</td>
                <td className="px-3 py-2 capitalize text-stone-100">{r.to_tier}</td>
                <td className="px-3 py-2 text-right">{r.stays}</td>
                <td className="px-3 py-2 text-right">£{r.lifetime}</td>
                <td className="px-3 py-2">{r.action === "upgrade" ? <ArrowUp className="w-3 h-3 text-emerald-300" /> : <ArrowDown className="w-3 h-3 text-rose-300" />}</td>
              </tr>
            ))}
            {log.items.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-stone-500">No tier changes yet. Click "Run sweep" to recompute now.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, highlight = false }) {
  return (
    <div className={`p-3 rounded-lg border ${highlight ? "bg-emerald-500/10 border-emerald-500/40" : "bg-stone-800/60 border-stone-800"}`}>
      <div className="text-[10px] uppercase tracking-wider text-stone-400 mb-1">{label}</div>
      <div className={`text-lg font-semibold ${highlight ? "text-emerald-200" : "text-stone-100"}`}>{value}</div>
    </div>
  );
}
