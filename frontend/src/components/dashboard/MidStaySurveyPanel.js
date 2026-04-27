/**
 * Mid-stay Survey Panel
 * Front-of-house view of pulse survey invites + responses + low-score recovery.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, RefreshCw, Send, Star, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function MidStaySurveyPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("responses");
  const [invites, setInvites] = useState({ items: [], count: 0, responded: 0, response_rate: 0 });
  const [responses, setResponses] = useState({ items: [], count: 0, avg_score: 0, by_category: {}, low_count: 0 });
  const [loading, setLoading] = useState(false);
  const [sweeping, setSweeping] = useState(false);

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: i }, { data: r }] = await Promise.all([
        axios.get(`${API}/mid-stay/${propertyId}/invites?days=14`),
        axios.get(`${API}/mid-stay/${propertyId}/responses?days=30`),
      ]);
      setInvites(i);
      setResponses(r);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); }, [refresh]);

  const sweep = async () => {
    setSweeping(true);
    try {
      const { data } = await axios.post(`${API}/mid-stay/sweep`, { property_id: propertyId });
      toast.success(`Enrolled ${data.enrolled} new invites (${data.scanned} scanned)`);
      refresh();
    } catch { toast.error("Sweep failed"); }
    setSweeping(false);
  };

  const previewLink = (invite) => `${window.location.origin}/mid-stay/${invite.id}`;

  return (
    <div className="space-y-6" data-testid="mid-stay-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Mid-stay Pulse Survey</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Catch issues on day 2–3 of a stay before they become a 1-star online review.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat label="Invites (14d)" value={invites.count} />
        <Stat label="Responded" value={invites.responded} />
        <Stat label="Response rate" value={`${invites.response_rate}%`} highlight={invites.response_rate >= 30} />
        <Stat label="Avg score" value={responses.avg_score} highlight={responses.avg_score >= 4.2} />
        <Stat label="Low scores (≤3)" value={responses.low_count} highlight={responses.low_count > 0} />
      </div>

      <div className="flex flex-wrap gap-2">
        <button data-testid="ms-sweep-btn" onClick={sweep} disabled={sweeping} className="text-sm px-3 py-2 rounded bg-cyan-500/20 border border-cyan-500/40 text-cyan-200 flex items-center gap-2">
          {sweeping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Sweep & enroll due bookings
        </button>
        <button onClick={refresh} className="text-sm px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-300 flex items-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} Refresh
        </button>
        <div className="ml-auto flex gap-2">
          {["responses", "invites"].map((t) => (
            <button key={t} data-testid={`ms-tab-${t}`} onClick={() => setTab(t)} className={`text-xs px-3 py-1 rounded border ${tab === t ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-200" : "bg-stone-800 border-stone-700 text-stone-300"}`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {tab === "responses" ? (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-3 py-2">When</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">Room</th><th className="px-3 py-2">Score</th><th className="px-3 py-2">Category</th><th className="px-3 py-2">Comment</th></tr>
            </thead>
            <tbody>
              {responses.items.map((r) => (
                <tr key={r.id} className={`border-t border-stone-800/60 ${r.score <= 3 ? "bg-rose-500/5" : ""}`} data-testid="ms-response-row">
                  <td className="px-3 py-2 text-stone-400 text-xs">{(r.submitted_at || "").slice(0, 16)}</td>
                  <td className="px-3 py-2 text-stone-200">{r.guest_name}</td>
                  <td className="px-3 py-2 text-stone-300">{r.room_number}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map((i) => <Star key={i} className={`w-3 h-3 ${i <= r.score ? "fill-amber-300 text-amber-300" : "text-stone-700"}`} />)}
                      {r.score <= 3 && <AlertTriangle className="w-3 h-3 ml-1 text-rose-300" />}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-xs text-stone-300">{r.category}</td>
                  <td className="px-3 py-2 text-xs text-stone-400 italic max-w-md truncate">{r.comment}</td>
                </tr>
              ))}
              {responses.items.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-stone-500">No responses yet.</td></tr>}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
              <tr><th className="px-3 py-2">Sent</th><th className="px-3 py-2">Guest</th><th className="px-3 py-2">Room</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Survey link</th></tr>
            </thead>
            <tbody>
              {invites.items.map((i) => (
                <tr key={i.id} className="border-t border-stone-800/60" data-testid="ms-invite-row">
                  <td className="px-3 py-2 text-stone-400 text-xs">{(i.sent_at || "").slice(0, 16)}</td>
                  <td className="px-3 py-2 text-stone-200">{i.guest_name}</td>
                  <td className="px-3 py-2 text-stone-300">{i.room_number}</td>
                  <td className="px-3 py-2">
                    <span className={`text-[10px] px-2 py-0.5 rounded border ${i.responded ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-200" : "bg-stone-800 border-stone-700 text-stone-300"}`}>{i.responded ? "responded" : "pending"}</span>
                  </td>
                  <td className="px-3 py-2 text-xs">
                    <code className="text-cyan-300">{previewLink(i)}</code>
                  </td>
                </tr>
              ))}
              {invites.items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-stone-500">No invites sent. Click "Sweep" to enroll bookings on day 2+.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
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
