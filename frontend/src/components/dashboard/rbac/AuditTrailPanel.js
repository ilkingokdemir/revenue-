import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  Shield, ShieldAlert, Search, RefreshCw, AlertTriangle, CheckCircle2,
  User, Globe, Clock, KeyRound, ChevronRight, Trash2, Filter,
  ShieldCheck, Ban, TrendingUp, Users, Activity,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const METHOD_CLS = {
  GET:    "bg-sky-100 text-sky-800 border-sky-200",
  POST:   "bg-emerald-100 text-emerald-800 border-emerald-200",
  PUT:    "bg-amber-100 text-amber-800 border-amber-200",
  PATCH:  "bg-amber-100 text-amber-800 border-amber-200",
  DELETE: "bg-rose-100 text-rose-800 border-rose-200",
};

const ROLE_DOT = {
  admin:        "bg-emerald-500",
  manager:      "bg-indigo-500",
  receptionist: "bg-sky-500",
  housekeeper:  "bg-amber-500",
  maintenance:  "bg-stone-500",
  accountant:   "bg-purple-500",
  laundry_staff:"bg-rose-400",
};

const fmtAgo = (iso) => {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
};

export const AuditTrailPanel = ({ user }) => {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);

  const [q, setQ] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [pathFilter, setPathFilter] = useState("");
  const [resultFilter, setResultFilter] = useState("");
  const [windowDays, setWindowDays] = useState("7");
  const [detail, setDetail] = useState(null);

  const isAdmin = user?.role === "admin";

  const load = useCallback(async () => {
    if (!isAdmin) return;
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (emailFilter) p.set("user_email", emailFilter);
      if (pathFilter) p.set("path_contains", pathFilter);
      if (resultFilter) p.set("result", resultFilter);
      if (windowDays) p.set("days", windowDays);
      p.set("limit", "250");
      const { data } = await axios.get(`${API}/audit-trail?${p}`);
      setRows(data || []);
    } catch (e) {
      toast.error("Failed to load audit trail");
    }
    setLoading(false);
  }, [emailFilter, pathFilter, resultFilter, windowDays, isAdmin]);

  const loadStats = useCallback(async () => {
    if (!isAdmin) return;
    setStatsLoading(true);
    try {
      const { data } = await axios.get(`${API}/audit-trail/stats?days=${windowDays || 7}`);
      setStats(data);
    } catch (e) {
      /* silent */
    }
    setStatsLoading(false);
  }, [windowDays, isAdmin]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadStats(); }, [loadStats]);

  const filtered = useMemo(() => {
    if (!q.trim()) return rows;
    const s = q.toLowerCase();
    return rows.filter((r) =>
      (r.user_email || "").toLowerCase().includes(s) ||
      (r.path || "").toLowerCase().includes(s) ||
      (r.user_name || "").toLowerCase().includes(s) ||
      (r.missing_perms || []).join(",").toLowerCase().includes(s)
    );
  }, [rows, q]);

  const maxTrend = Math.max(1, ...((stats?.trend || []).map((t) => t.count)));

  const onPurge = async () => {
    if (!window.confirm("Purge audit entries older than 90 days? This cannot be undone.")) return;
    try {
      const { data } = await axios.delete(`${API}/audit-trail/purge?older_than_days=90`);
      toast.success(`Purged ${data.deleted} old entries`);
      load(); loadStats();
    } catch {
      toast.error("Purge failed");
    }
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-96 text-stone-500" data-testid="audit-trail-no-access">
        <div className="text-center">
          <ShieldAlert className="w-12 h-12 mx-auto mb-3 text-rose-400" />
          <div className="font-semibold text-stone-700">Admin access required</div>
          <div className="text-sm">The audit trail is restricted to administrators.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="audit-trail-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-rose-500 via-red-600 to-rose-700 flex items-center justify-center shadow-lg shadow-rose-200">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-stone-900">Audit Trail</h1>
            <p className="text-sm text-stone-500">Every permission-denied request — who, what, when, why.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={windowDays} onValueChange={setWindowDays}>
            <SelectTrigger className="w-36" data-testid="audit-window-select"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Last 24 hours</SelectItem>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={() => { load(); loadStats(); }} data-testid="audit-refresh-btn">
            <RefreshCw className="w-4 h-4 mr-1.5" /> Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={onPurge} className="text-rose-600 hover:bg-rose-50" data-testid="audit-purge-btn">
            <Trash2 className="w-4 h-4 mr-1.5" /> Purge &gt; 90d
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <KpiCard
          testId="kpi-total"
          icon={Activity}
          label="Total audit events"
          value={statsLoading ? "…" : (stats?.total_events ?? 0).toLocaleString()}
          accent="from-stone-500 to-stone-700"
        />
        <KpiCard
          testId="kpi-denied"
          icon={Ban}
          label="Denied attempts"
          value={statsLoading ? "…" : (stats?.denied_events ?? 0).toLocaleString()}
          accent="from-rose-500 to-red-700"
          urgent={(stats?.denied_events ?? 0) > 0}
        />
        <KpiCard
          testId="kpi-users"
          icon={Users}
          label="Distinct blocked users"
          value={statsLoading ? "…" : (stats?.top_users?.length ?? 0)}
          accent="from-indigo-500 to-violet-700"
        />
        <KpiCard
          testId="kpi-trend"
          icon={TrendingUp}
          label="Peak day denials"
          value={statsLoading ? "…" : maxTrend.toLocaleString()}
          accent="from-amber-500 to-orange-600"
        />
      </div>

      {/* Top offenders + Top paths + Missing perms */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-stone-200 overflow-hidden" data-testid="audit-top-users">
          <div className="px-4 py-3 border-b border-stone-100 flex items-center gap-2">
            <User className="w-4 h-4 text-rose-600" />
            <h3 className="font-semibold text-stone-800 text-sm">Top offenders</h3>
            <span className="ml-auto text-xs text-stone-400">by denial count</span>
          </div>
          <div className="divide-y divide-stone-100 max-h-72 overflow-auto">
            {(stats?.top_users || []).length === 0 && !statsLoading && (
              <div className="p-6 text-center text-sm text-stone-400">No denied attempts yet</div>
            )}
            {(stats?.top_users || []).map((u, i) => (
              <div key={i} className="px-4 py-2.5 flex items-center gap-3 hover:bg-rose-50/40 cursor-pointer"
                   onClick={() => setEmailFilter(u.email)}>
                <span className={`w-2 h-2 rounded-full ${ROLE_DOT[u.role] || "bg-stone-400"}`}></span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-stone-800 truncate">{u.name || u.email}</div>
                  <div className="text-[11px] text-stone-500 truncate">{u.email} · {u.role}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold text-rose-600">{u.count}</div>
                  <div className="text-[10px] text-stone-400">{fmtAgo(u.last_attempt)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-stone-200 overflow-hidden" data-testid="audit-top-paths">
          <div className="px-4 py-3 border-b border-stone-100 flex items-center gap-2">
            <Globe className="w-4 h-4 text-indigo-600" />
            <h3 className="font-semibold text-stone-800 text-sm">Top blocked endpoints</h3>
          </div>
          <div className="divide-y divide-stone-100 max-h-72 overflow-auto">
            {(stats?.top_paths || []).length === 0 && !statsLoading && (
              <div className="p-6 text-center text-sm text-stone-400">No blocked endpoints</div>
            )}
            {(stats?.top_paths || []).map((p, i) => (
              <div key={i} className="px-4 py-2.5 flex items-center gap-3 hover:bg-indigo-50/40 cursor-pointer"
                   onClick={() => setPathFilter(p.path)}>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-mono text-stone-800 truncate">{p.path}</div>
                  <div className="text-[10px] text-stone-500">{p.unique_users} user{p.unique_users === 1 ? "" : "s"}</div>
                </div>
                <Badge variant="secondary" className="bg-indigo-100 text-indigo-800 text-xs">{p.count}</Badge>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-stone-200 overflow-hidden" data-testid="audit-top-perms">
          <div className="px-4 py-3 border-b border-stone-100 flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-amber-600" />
            <h3 className="font-semibold text-stone-800 text-sm">Most missing permissions</h3>
          </div>
          <div className="divide-y divide-stone-100 max-h-72 overflow-auto">
            {(stats?.top_missing_perms || []).length === 0 && !statsLoading && (
              <div className="p-6 text-center text-sm text-stone-400">No missing perms recorded</div>
            )}
            {(stats?.top_missing_perms || []).map((p, i) => {
              const pct = Math.round((p.count / Math.max(1, stats?.denied_events || 1)) * 100);
              return (
                <div key={i} className="px-4 py-2.5">
                  <div className="flex items-center justify-between mb-1">
                    <code className="text-xs font-medium text-stone-700">{p.perm}</code>
                    <span className="text-xs font-bold text-amber-700">{p.count}</span>
                  </div>
                  <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-amber-400 to-orange-500" style={{ width: `${pct}%` }}></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Trend sparkline */}
      {(stats?.trend || []).length > 0 && (
        <div className="bg-white rounded-xl border border-stone-200 p-4" data-testid="audit-trend">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-rose-600" />
            <h3 className="font-semibold text-stone-800 text-sm">Daily denial trend</h3>
          </div>
          <div className="flex items-end gap-1.5 h-24">
            {stats.trend.map((d) => (
              <div key={d.date} className="flex-1 flex flex-col items-center gap-1 group">
                <div className="flex-1 w-full relative flex items-end">
                  <div
                    className="w-full bg-gradient-to-t from-rose-600 to-rose-300 rounded-t transition-all hover:from-rose-700 hover:to-rose-400"
                    style={{ height: `${(d.count / maxTrend) * 100}%`, minHeight: "4px" }}
                  />
                  <div className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] font-bold text-stone-700 opacity-0 group-hover:opacity-100">
                    {d.count}
                  </div>
                </div>
                <div className="text-[9px] text-stone-400">{d.date.slice(5)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter bar */}
      <div className="bg-white rounded-xl border border-stone-200 p-3 flex flex-wrap items-center gap-2" data-testid="audit-filters">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <Input placeholder="Search user, path, permission…" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" data-testid="audit-search" />
        </div>
        <Input placeholder="Email contains…" value={emailFilter} onChange={(e) => setEmailFilter(e.target.value)} className="w-48" data-testid="audit-email-filter" />
        <Input placeholder="Path contains…" value={pathFilter} onChange={(e) => setPathFilter(e.target.value)} className="w-48" data-testid="audit-path-filter" />
        <Select value={resultFilter || "all"} onValueChange={(v) => setResultFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-36" data-testid="audit-result-filter"><SelectValue placeholder="Result" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All results</SelectItem>
            <SelectItem value="denied">Denied only</SelectItem>
          </SelectContent>
        </Select>
        {(emailFilter || pathFilter || resultFilter || q) && (
          <Button variant="ghost" size="sm" onClick={() => { setEmailFilter(""); setPathFilter(""); setResultFilter(""); setQ(""); }} data-testid="audit-clear-filters">
            Clear
          </Button>
        )}
      </div>

      {/* Log table */}
      <div className="bg-white rounded-xl border border-stone-200 overflow-hidden" data-testid="audit-table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-50 border-b border-stone-200">
              <tr>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-stone-600 uppercase tracking-wider">When</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-stone-600 uppercase tracking-wider">User</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Action</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Endpoint</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Missing</th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-stone-600 uppercase tracking-wider">Result</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {loading && (
                <tr><td colSpan={7} className="p-8 text-center text-stone-400">
                  <RefreshCw className="w-5 h-5 mx-auto mb-2 animate-spin" /> Loading…
                </td></tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={7} className="p-10 text-center">
                  <ShieldCheck className="w-10 h-10 mx-auto mb-2 text-emerald-400" />
                  <div className="font-semibold text-stone-700">All clear</div>
                  <div className="text-xs text-stone-500">No audit entries match your filters.</div>
                </td></tr>
              )}
              {!loading && filtered.map((r, i) => (
                <tr key={i} className="hover:bg-rose-50/40 cursor-pointer" onClick={() => setDetail(r)} data-testid={`audit-row-${i}`}>
                  <td className="px-4 py-2.5 text-xs whitespace-nowrap">
                    <div className="text-stone-800 font-medium">{fmtAgo(r.ts)}</div>
                    <div className="text-[10px] text-stone-400">{r.ts?.slice(11, 19)}</div>
                  </td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className={`w-1.5 h-1.5 rounded-full ${ROLE_DOT[r.user_role] || "bg-stone-400"}`}></span>
                      <div>
                        <div className="text-xs font-medium text-stone-800">{r.user_email}</div>
                        <div className="text-[10px] text-stone-500">{r.user_role || r.user_role_key || "—"}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge variant="outline" className={`text-[10px] font-mono ${METHOD_CLS[r.method] || "bg-stone-100 text-stone-700"}`}>
                      {r.method}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5">
                    <code className="text-xs text-stone-700">{r.path}</code>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {(r.missing_perms || []).slice(0, 2).map((p) => (
                        <Badge key={p} variant="outline" className="text-[10px] bg-amber-50 text-amber-800 border-amber-200">{p}</Badge>
                      ))}
                      {(r.missing_perms || []).length > 2 && (
                        <span className="text-[10px] text-stone-500">+{r.missing_perms.length - 2}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge className="bg-rose-600 text-white text-[10px]">
                      <Ban className="w-3 h-3 mr-0.5" /> DENIED
                    </Badge>
                  </td>
                  <td className="px-2"><ChevronRight className="w-4 h-4 text-stone-300" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 py-2 border-t border-stone-100 text-[11px] text-stone-500 flex items-center justify-between">
          <span>{filtered.length} of {rows.length} entries</span>
          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Window: last {windowDays} days</span>
        </div>
      </div>

      {/* Detail drawer */}
      {detail && (
        <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/40 backdrop-blur-sm" onClick={() => setDetail(null)}>
          <div className="bg-white rounded-t-2xl md:rounded-2xl w-full md:max-w-xl shadow-2xl max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()} data-testid="audit-detail">
            <div className="p-5 border-b border-stone-100 flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-rose-500 to-rose-700 flex items-center justify-center">
                <Ban className="w-5 h-5 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-stone-900">Denied Request</h3>
                <p className="text-xs text-stone-500">{detail.ts}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setDetail(null)}>×</Button>
            </div>
            <div className="p-5 space-y-3 text-sm">
              <DetailRow label="User">
                <div className="font-semibold text-stone-800">{detail.user_name || "—"}</div>
                <div className="text-xs text-stone-500">{detail.user_email} · {detail.user_role || detail.user_role_key}</div>
              </DetailRow>
              <DetailRow label="Request">
                <Badge className={`${METHOD_CLS[detail.method] || "bg-stone-100"} font-mono text-[10px] mr-2`}>{detail.method}</Badge>
                <code className="text-xs">{detail.path}</code>
                {detail.query && <div className="text-[11px] text-stone-400 mt-1">?{detail.query}</div>}
              </DetailRow>
              <DetailRow label="Required permissions">
                <div className="flex flex-wrap gap-1 mt-1">
                  {(detail.required_perms || []).map((p) => (
                    <Badge key={p} variant="outline" className="bg-indigo-50 text-indigo-800 border-indigo-200 text-[10px]">{p}</Badge>
                  ))}
                </div>
                <div className="text-[10px] text-stone-400 mt-1">mode: <code>{detail.mode}</code></div>
              </DetailRow>
              <DetailRow label="Missing">
                <div className="flex flex-wrap gap-1 mt-1">
                  {(detail.missing_perms || []).map((p) => (
                    <Badge key={p} className="bg-rose-600 text-white text-[10px]">{p}</Badge>
                  ))}
                </div>
              </DetailRow>
              <DetailRow label="User's current perms">
                <span className="text-stone-600">{detail.user_perms_count ?? 0} permission{detail.user_perms_count === 1 ? "" : "s"}</span>
              </DetailRow>
              <DetailRow label="Client">
                <div className="text-xs text-stone-600">{detail.client_ip || "—"}</div>
                <div className="text-[10px] text-stone-400 truncate">{detail.user_agent || "—"}</div>
              </DetailRow>
            </div>
            <div className="p-4 border-t border-stone-100 bg-stone-50 flex items-center justify-between">
              <span className="text-[11px] text-stone-500">
                <AlertTriangle className="w-3 h-3 inline mr-1 text-amber-500" />
                Grant the missing perm via Roles & Permissions to resolve.
              </span>
              <Button size="sm" onClick={() => setDetail(null)}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const KpiCard = ({ icon: Icon, label, value, accent, urgent, testId }) => (
  <div className="bg-white rounded-xl border border-stone-200 p-4 relative overflow-hidden" data-testid={testId}>
    <div className={`absolute top-0 right-0 w-24 h-24 rounded-full bg-gradient-to-br ${accent} opacity-10 -mr-8 -mt-8`}></div>
    <div className="flex items-center gap-2 mb-2 relative">
      <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${accent} flex items-center justify-center`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <span className="text-[11px] font-medium text-stone-500 uppercase tracking-wider">{label}</span>
    </div>
    <div className={`text-3xl font-black ${urgent ? "text-rose-600" : "text-stone-900"}`}>{value}</div>
  </div>
);

const DetailRow = ({ label, children }) => (
  <div>
    <div className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold mb-0.5">{label}</div>
    <div>{children}</div>
  </div>
);

export default AuditTrailPanel;
