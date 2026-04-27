/**
 * Birthday Auto-Discount Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Cake, RefreshCw, Save, Send } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function BirthdayPanel({ propertyId, hotelName = "" }) {
  const [cfg, setCfg] = useState(null);
  const [upcoming, setUpcoming] = useState([]);
  const [dispatches, setDispatches] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: c }, { data: u }, { data: d }] = await Promise.all([
        axios.get(`${API}/birthday/${propertyId}/config`),
        axios.get(`${API}/birthday/${propertyId}/upcoming?days=30`),
        axios.get(`${API}/birthday/${propertyId}/dispatches?days=60`),
      ]);
      setCfg(c); setUpcoming(u.items || []); setDispatches(d.items || []);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const save = async () => {
    try {
      await axios.post(`${API}/birthday/config`, { property_id: propertyId, ...cfg });
      toast.success("Config saved"); refresh();
    } catch { toast.error("Failed"); }
  };

  const sweep = async () => {
    try {
      const { data } = await axios.post(`${API}/birthday/sweep`, { property_id: propertyId });
      toast.success(`${data.issued} vouchers issued · ${data.skipped_duplicates} duplicates`);
      refresh();
    } catch { toast.error("Sweep failed"); }
  };

  return (
    <div className="space-y-6" data-testid="birthday-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Birthday Auto-Discount</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Auto-issue a birthday voucher to past guests in the next N days.</p>
      </div>

      {cfg && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
          <label className="flex items-center gap-2 mt-4 text-stone-300"><input type="checkbox" checked={!!cfg.enabled} onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} /> Enabled</label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Lookahead days</span><input type="number" value={cfg.lookahead_days} onChange={(e) => setCfg({ ...cfg, lookahead_days: parseInt(e.target.value, 10) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Discount %</span><input type="number" value={cfg.discount_pct} onChange={(e) => setCfg({ ...cfg, discount_pct: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <label className="flex flex-col gap-1"><span className="text-stone-500">Max £ off</span><input type="number" value={cfg.max_amount_off} onChange={(e) => setCfg({ ...cfg, max_amount_off: parseFloat(e.target.value) })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100" /></label>
          <button data-testid="bd-save-cfg-btn" onClick={save} className="px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 mt-4 flex items-center justify-center gap-1"><Save className="w-3 h-3" /> Save</button>
        </div>
      )}

      <div className="flex gap-2">
        <button data-testid="bd-sweep-btn" onClick={sweep} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2"><Send className="w-4 h-4" /> Issue vouchers now</button>
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">{loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh</button>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-stone-800 bg-stone-900/60">
          <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400 flex items-center gap-2"><Cake className="w-3 h-3" /> Upcoming birthdays ({upcoming.length})</div>
          <table className="min-w-full text-xs">
            <thead className="text-left text-[10px] text-stone-500 border-b border-stone-800"><tr><th className="px-3 py-2">In</th><th className="px-3 py-2">Date</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">Tier</th></tr></thead>
            <tbody>
              {upcoming.map((u, i) => (
                <tr key={i} className="border-t border-stone-800/60 text-stone-300" data-testid="bd-upcoming-row">
                  <td className="px-3 py-1">{u.days_until}d</td>
                  <td className="px-3 py-1">{u.next_birthday}</td>
                  <td className="px-3 py-1"><div className="text-stone-100">{u.guest_name}</div><div className="text-[10px] text-stone-500">{u.guest_email}</div></td>
                  <td className="px-3 py-1 capitalize">{u.loyalty_tier}</td>
                </tr>
              ))}
              {upcoming.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-stone-500">No birthdays in window. Make sure guest_profiles have date_of_birth set.</td></tr>}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-stone-800 bg-stone-900/60">
          <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400">Dispatches ({dispatches.length})</div>
          <table className="min-w-full text-xs">
            <thead className="text-left text-[10px] text-stone-500 border-b border-stone-800"><tr><th className="px-3 py-2">Sent</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">Code</th><th className="px-3 py-2">Status</th></tr></thead>
            <tbody>
              {dispatches.map((d) => (
                <tr key={d.id} className="border-t border-stone-800/60 text-stone-300" data-testid="bd-dispatch-row">
                  <td className="px-3 py-1">{(d.scheduled_for || "").slice(0, 16)}</td>
                  <td className="px-3 py-1">{d.guest_name}</td>
                  <td className="px-3 py-1 font-mono text-cyan-300">{d.voucher_code}</td>
                  <td className="px-3 py-1">{d.status}</td>
                </tr>
              ))}
              {dispatches.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-center text-stone-500">No dispatches yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
