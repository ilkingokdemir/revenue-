/**
 * Concierge Inbox — admin view of all guest chats with the AI Concierge.
 * Lets reception read transcripts, flag bad AI replies for review, and
 * write a corrected reply that the next QA pass can learn from.
 *
 * NOTE: this is a feedback-loop workspace, NOT a live chat. The actual
 * conversation is between guest and GPT-5.2; reception annotates after.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  MessageCircle, Loader2, Flag, RefreshCw, Sparkles, Clock, AlertCircle, Check, BarChart3,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fmtTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
};

export default function ConciergeInboxPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeId, setActiveId] = useState(null);
  const [thread, setThread] = useState(null);
  const [filter, setFilter] = useState("all");  // all | flagged
  const [topics, setTopics] = useState(null);
  const [topicsLoading, setTopicsLoading] = useState(false);

  const loadTopics = useCallback(async () => {
    if (!propertyId) return;
    setTopicsLoading(true);
    try {
      const { data } = await axios.get(`${API}/concierge/admin/${propertyId}/topics?days=30`);
      setTopics(data);
    } catch { /* noop */ }
    setTopicsLoading(false);
  }, [propertyId]);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/concierge/admin/${propertyId}/sessions`);
      setData(data);
    } catch { toast.error("Failed to load"); }
    setLoading(false);
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { setActiveId(null); setThread(null); setTopics(null); }, [propertyId]);

  const openThread = async (sid) => {
    setActiveId(sid);
    setThread(null);
    try {
      const { data } = await axios.get(`${API}/concierge/admin/${propertyId}/session/${sid}`);
      setThread(data);
    } catch { toast.error("Failed to load thread"); }
  };

  const flag = async (msg, reason = "") => {
    try {
      await axios.post(`${API}/concierge/admin/messages/${msg.id}/flag`, { reason });
      toast.success("Flagged for review");
      openThread(activeId); load();
    } catch { toast.error("Failed"); }
  };

  const unflag = async (msg) => {
    try {
      await axios.post(`${API}/concierge/admin/messages/${msg.id}/unflag`);
      toast.success("Cleared flag");
      openThread(activeId); load();
    } catch { toast.error("Failed"); }
  };

  const sessions = data?.sessions || [];
  const filtered = filter === "flagged" ? sessions.filter(s => s.flagged > 0) : sessions;

  return (
    <div className="p-5 h-full flex flex-col" data-testid="concierge-inbox-panel">
      {/* Header + Stats */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-bold text-stone-100 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-violet-400" />Concierge Inbox
            {hotelName && <><span className="text-stone-500 mx-1">·</span><span className="text-violet-400">{hotelName}</span></>}
          </h2>
          <p className="text-xs text-stone-400">Read what guests asked the AI · flag wrong replies for the next review pass</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setFilter(filter === "flagged" ? "all" : "flagged")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border ${filter === "flagged" ? "bg-rose-500/20 text-rose-300 border-rose-500/40" : "bg-stone-800 text-stone-300 border-stone-700"}`}
            data-testid="ci-filter-flagged">
            <Flag className="w-3.5 h-3.5" />{filter === "flagged" ? "Flagged only" : "All sessions"}
          </button>
          <button onClick={load} disabled={loading} data-testid="ci-refresh"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-white text-xs font-bold">
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
        <Stat icon={MessageCircle} label="Total sessions"  value={data?.total_sessions ?? 0} color="text-cyan-300" />
        <Stat icon={Clock}          label="Total messages"  value={data?.total_messages ?? 0} color="text-violet-300" />
        <Stat icon={Flag}           label="Flagged"         value={data?.flagged_messages ?? 0} color="text-rose-300" />
      </div>

      {/* Most-asked topics (GPT-clustered) */}
      <div className="bg-gradient-to-br from-violet-900/20 to-stone-900/40 border border-violet-500/20 rounded-2xl p-4 mb-4" data-testid="ci-topics">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-stone-100 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-violet-400" />Most-asked topics · last 30 days
          </h3>
          <button onClick={loadTopics} disabled={topicsLoading} data-testid="ci-topics-load"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-[11px] font-bold disabled:opacity-50">
            {topicsLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
            {topics ? "Refresh" : "Analyse with AI"}
          </button>
        </div>
        {topics ? (
          topics.topics?.length > 0 ? (
            <div className="space-y-1.5">
              {topics.topics.slice(0, 8).map((t, i) => {
                const pct = Math.round((t.count / Math.max(1, topics.samples)) * 100);
                return (
                  <div key={i} className="flex items-center gap-3" data-testid={`ci-topic-${i}`}>
                    <div className="text-xs font-bold text-stone-200 w-44 truncate">{t.topic}</div>
                    <div className="flex-1 h-2 bg-stone-800 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500" style={{ width: `${Math.min(100, pct * 2)}%` }} />
                    </div>
                    <div className="text-xs font-bold text-violet-300 tabular-nums w-14 text-right">{t.count}× · {pct}%</div>
                  </div>
                );
              })}
              <p className="text-[10px] text-stone-500 mt-2">{topics.fallback ? "Heuristic clustering" : "GPT-5.2 clustered"} · {topics.samples} guest questions</p>
            </div>
          ) : (
            <p className="text-xs text-stone-500">No questions in the last {topics.window_days} days yet.</p>
          )
        ) : (
          <p className="text-xs text-stone-500">Click <strong>Analyse with AI</strong> to see what guests keep asking.</p>
        )}
      </div>

      {/* Two-column: sessions list + thread detail */}
      <div className="grid grid-cols-1 md:grid-cols-[340px_1fr] gap-4 flex-1 min-h-[500px]">
        {/* Sessions list */}
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl overflow-hidden flex flex-col" data-testid="ci-sessions">
          <div className="overflow-y-auto flex-1">
            {filtered.length === 0 && !loading && (
              <div className="p-8 text-center text-stone-500 text-sm">
                <MessageCircle className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p>No {filter === "flagged" ? "flagged " : ""}sessions yet.</p>
              </div>
            )}
            {filtered.map(s => {
              const isActive = activeId === s.session_id;
              return (
                <button key={s.session_id} onClick={() => openThread(s.session_id)}
                  data-testid={`ci-session-${s.session_id}`}
                  className={`w-full text-left p-3 border-b border-stone-800/60 transition ${isActive ? "bg-violet-500/10" : "hover:bg-stone-800/40"}`}>
                  <div className="flex items-baseline justify-between gap-2 mb-1">
                    <p className="text-xs font-mono text-stone-300 truncate">{s.session_id.slice(0, 14)}…</p>
                    <span className="text-[10px] text-stone-500 flex-shrink-0">{fmtTime(s.last_at)}</span>
                  </div>
                  <p className="text-xs text-stone-400 line-clamp-2 mb-1.5">
                    <span className={`text-[9px] font-bold uppercase mr-1 ${s.last_role === "user" ? "text-cyan-400" : "text-violet-400"}`}>{s.last_role}</span>
                    {s.last_preview}
                  </p>
                  <div className="flex items-center gap-2 text-[10px] text-stone-500">
                    <span>{s.messages} msg(s)</span>
                    {s.flagged > 0 && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                        <Flag className="w-2.5 h-2.5" />{s.flagged}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Thread detail */}
        <div className="bg-stone-900/60 border border-stone-800 rounded-2xl flex flex-col overflow-hidden">
          {!activeId ? (
            <div className="flex-1 flex items-center justify-center text-stone-500 text-sm">
              <div className="text-center">
                <MessageCircle className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>Select a session to view the conversation</p>
              </div>
            </div>
          ) : !thread ? (
            <div className="flex-1 flex items-center justify-center text-stone-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
          ) : (
            <>
              <div className="px-4 py-2.5 border-b border-stone-800 flex items-center justify-between">
                <p className="text-[11px] font-mono text-stone-400">Session · {thread.session_id.slice(0, 18)}…</p>
                <p className="text-[10px] text-stone-500">{thread.messages?.length || 0} messages</p>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3" data-testid="ci-thread">
                {(thread.messages || []).map(m => {
                  const out = m.role === "user";
                  const isAI = m.role === "assistant";
                  return (
                    <div key={m.id} className={`flex ${out ? "justify-end" : "justify-start"}`}>
                      <div className={`max-w-[75%] ${out ? "" : "flex flex-col"}`}>
                        <div className={`rounded-2xl px-3 py-2 text-sm shadow-sm whitespace-pre-wrap leading-relaxed
                          ${out ? "bg-cyan-700 text-white rounded-br-sm" : m.flagged ? "bg-rose-900/30 border border-rose-500/40 text-stone-100 rounded-bl-sm" : "bg-stone-800 text-stone-100 rounded-bl-sm"}`}>
                          <div className="flex items-center gap-2 text-[9px] uppercase font-bold tracking-widest mb-1 opacity-70">
                            <span>{m.role}</span>
                            <span className="text-[9px] normal-case opacity-80">· {fmtTime(m.created_at)}</span>
                            {m.flagged && (<><Flag className="w-2.5 h-2.5 ml-1 text-rose-300" />flagged</>)}
                          </div>
                          {m.content}
                          {m.corrected_reply && (
                            <div className="mt-2 pt-2 border-t border-rose-400/30 text-[11px]">
                              <div className="text-rose-300 font-bold uppercase tracking-widest text-[9px] mb-1">Reception correction</div>
                              <p>{m.corrected_reply}</p>
                            </div>
                          )}
                        </div>
                        {isAI && (
                          <div className="flex gap-1.5 mt-1.5">
                            {m.flagged ? (
                              <button onClick={() => unflag(m)} data-testid={`ci-unflag-${m.id}`}
                                className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30 flex items-center gap-1">
                                <Check className="w-2.5 h-2.5" />Clear flag
                              </button>
                            ) : (
                              <button onClick={() => {
                                const reason = window.prompt("Why is this reply wrong?");
                                if (reason !== null) flag(m, reason);
                              }} data-testid={`ci-flag-${m.id}`}
                                className="text-[10px] px-2 py-0.5 rounded bg-stone-800 hover:bg-rose-500/20 text-stone-400 hover:text-rose-300 border border-stone-700 hover:border-rose-500/40 flex items-center gap-1">
                                <AlertCircle className="w-2.5 h-2.5" />Flag
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, color }) {
  return (
    <div className="bg-stone-900/60 border border-stone-800 rounded-2xl p-3">
      <div className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-1 flex items-center gap-1">
        <Icon className="w-3 h-3" />{label}
      </div>
      <div className={`text-2xl font-black tabular-nums ${color}`}>{value}</div>
    </div>
  );
}
