import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  Search, RefreshCw, Download, Grid3X3, PoundSterling, Users,
  Building2, Clock, Calendar, X, Save, Split as SplitIcon, Power,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ROLES = ["admin", "manager", "receptionist", "housekeeper", "maintenance"];
const fmt$ = (n) => `£${(Number(n) || 0).toFixed(2)}`;

export const PayrollRateMatrix = ({ user }) => {
  const [data, setData] = useState({ users: [], properties: [], total_users: 0, total_configured_cells: 0, total_possible_cells: 0 });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [propFilter, setPropFilter] = useState("");
  const [edit, setEdit] = useState(null); // { userId, propertyId, user, property, cell }
  const [busy, setBusy] = useState(null);

  const isAdmin = user?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (roleFilter) params.set("role", roleFilter);
      if (propFilter) params.set("property_id", propFilter);
      const { data: d } = await axios.get(`${API}/payroll-matrix?${params}`);
      setData(d);
    } catch { /* silent */ }
    setLoading(false);
  }, [q, roleFilter, propFilter]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load]);

  const openCell = (u, p) => {
    const cell = (u.branch_payments || {})[p.id] || {
      payment_type: "hourly", rate: 0, split: false, active: true,
    };
    setEdit({ userId: u.id, propertyId: p.id, user: u, property: p,
              cell: { ...cell } });
  };

  const saveCell = async () => {
    if (!edit) return;
    setBusy("save");
    try {
      await axios.put(`${API}/payroll-matrix/${edit.userId}/${edit.propertyId}`, edit.cell);
      toast.success(`${edit.user.name} · ${edit.property.name} saved`);
      setEdit(null);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
    setBusy(null);
  };

  const deleteCell = async () => {
    if (!edit || !window.confirm(`Remove rate for ${edit.user.name} at ${edit.property.name}?`)) return;
    setBusy("del");
    try {
      await axios.delete(`${API}/payroll-matrix/${edit.userId}/${edit.propertyId}`);
      toast.success("Rate removed");
      setEdit(null);
      load();
    } catch (e) { toast.error("Failed"); }
    setBusy(null);
  };

  const exportCSV = () => {
    const rows = [["Staff", "Email", "Role", ...data.properties.map(p => p.name)]];
    data.users.forEach(u => {
      const row = [u.name, u.email, u.role];
      data.properties.forEach(p => {
        const c = (u.branch_payments || {})[p.id];
        if (!c || !c.rate) row.push("");
        else {
          const unit = c.payment_type === "daily" ? "/day" : "/h";
          row.push(`${c.active === false ? "[inactive] " : ""}£${Number(c.rate).toFixed(2)}${unit}${c.split ? " (split)" : ""}`);
        }
      });
      rows.push(row);
    });
    const csv = rows.map(r => r.map(x => `"${String(x).replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `payroll-rate-matrix-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(a.href);
  };

  // Cell renderer for a given user/property combination
  const Cell = ({ u, p }) => {
    const c = (u.branch_payments || {})[p.id];
    const configured = c && Number(c.rate) > 0;
    const isInactive = configured && c.active === false;
    return (
      <button
        onClick={() => isAdmin && openCell(u, p)}
        disabled={!isAdmin}
        className={`w-full min-h-[56px] px-2 py-1.5 text-left transition group border border-transparent
          ${configured
            ? (isInactive
                ? "bg-stone-100 hover:border-amber-300"
                : "bg-emerald-50 hover:bg-emerald-100 hover:border-emerald-300")
            : "bg-white hover:bg-stone-50 hover:border-stone-300"}
          ${isAdmin ? "cursor-pointer" : "cursor-default"}`}
        data-testid={`cell-${u.id}-${p.id}`}
      >
        {configured ? (
          <div className="space-y-0.5">
            <div className="flex items-center gap-1">
              <span className={`text-xs font-bold ${isInactive ? "line-through text-stone-500" : "text-emerald-800"}`}>
                {fmt$(c.rate)}
              </span>
              <span className="text-[9px] text-stone-500 font-medium">
                {c.payment_type === "daily" ? "/day" : "/h"}
              </span>
            </div>
            <div className="flex items-center gap-1">
              {c.split && <Badge className="text-[8px] h-4 px-1 bg-indigo-100 text-indigo-700 border-indigo-200">SPLIT</Badge>}
              {isInactive && <Badge className="text-[8px] h-4 px-1 bg-amber-100 text-amber-700 border-amber-200">OFF</Badge>}
              {!isInactive && !c.split && <span className="text-[9px] text-emerald-600">active</span>}
            </div>
          </div>
        ) : (
          <span className="text-[10px] text-stone-300">{isAdmin ? "+ add" : "—"}</span>
        )}
      </button>
    );
  };

  return (
    <div className="space-y-5" data-testid="payroll-matrix">
      {/* Hero */}
      <div className="bg-gradient-to-br from-amber-700 via-rose-700 to-slate-900 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/5 rounded-full -translate-y-24 translate-x-24 blur-3xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Grid3X3 className="w-5 h-5" />
              <span className="text-[11px] font-bold uppercase tracking-widest opacity-80">Payroll Rate Matrix</span>
            </div>
            <h2 className="text-3xl font-black mb-1" data-testid="matrix-title">Every rate. Every branch. One grid.</h2>
            <p className="text-sm opacity-85">Set hourly or daily rates per staff member per property — with split-across-branches and per-branch active toggles.</p>
          </div>
          <div className="flex items-center gap-4">
            <div>
              <p className="text-2xl font-black" data-testid="matrix-configured">{data.total_configured_cells}</p>
              <p className="text-[10px] opacity-80 uppercase tracking-wider">Rates set</p>
            </div>
            <div className="h-10 w-px bg-white/20" />
            <div>
              <p className="text-2xl font-black">{data.total_possible_cells}</p>
              <p className="text-[10px] opacity-80 uppercase tracking-wider">Possible cells</p>
            </div>
            <Button size="sm" onClick={exportCSV} className="bg-white text-slate-900 hover:bg-stone-100 font-semibold" data-testid="matrix-export">
              <Download className="w-4 h-4 mr-1" />CSV
            </Button>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search staff by name or email..." className="pl-9 h-9" data-testid="matrix-search" />
        </div>
        <Select value={roleFilter || "all"} onValueChange={v => setRoleFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-44 h-9" data-testid="matrix-role-filter"><SelectValue placeholder="All roles" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            {ROLES.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={propFilter || "all"} onValueChange={v => setPropFilter(v === "all" ? "" : v)}>
          <SelectTrigger className="w-56 h-9" data-testid="matrix-prop-filter"><SelectValue placeholder="All properties" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All properties</SelectItem>
            {data.properties.map(p => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>

      {/* Matrix Table */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="matrix-table">
            <thead className="bg-stone-50">
              <tr>
                <th className="sticky left-0 bg-stone-50 z-10 px-4 py-3 text-left text-[10px] uppercase tracking-wider text-stone-500 font-semibold border-r border-stone-200 min-w-[220px]">Staff member</th>
                {data.properties.map(p => (
                  <th key={p.id} className="px-2 py-3 text-left text-[10px] uppercase tracking-wider text-stone-500 font-semibold min-w-[130px]">
                    <div className="flex items-center gap-1.5">
                      <Building2 className="w-3 h-3 text-stone-400" />
                      <span className="truncate" title={p.name}>{p.name}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {loading && !data.users.length && (
                <tr><td colSpan={data.properties.length + 1} className="py-12 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</td></tr>
              )}
              {!loading && !data.users.length && (
                <tr><td colSpan={data.properties.length + 1} className="py-16 text-center text-stone-400" data-testid="matrix-empty">
                  <Users className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p>No staff match these filters.</p>
                </td></tr>
              )}
              {data.users.map(u => (
                <tr key={u.id} className="hover:bg-stone-50/50 transition" data-testid={`row-${u.id}`}>
                  <td className="sticky left-0 bg-white group-hover:bg-stone-50 z-10 px-4 py-2 border-r border-stone-200">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                           style={{ backgroundColor: u.color || "#64748b" }}>
                        {(u.name || "?").slice(0, 2).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-stone-800 text-xs truncate">{u.name}</p>
                        <p className="text-[10px] text-stone-500 capitalize">{u.role}</p>
                      </div>
                    </div>
                  </td>
                  {data.properties.map(p => (
                    <td key={p.id} className="p-0 align-middle">
                      <Cell u={u} p={p} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-[11px] text-stone-500 flex-wrap">
        <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-emerald-50 border border-emerald-200 rounded" /> Active rate</div>
        <div className="flex items-center gap-1.5"><div className="w-3 h-3 bg-stone-100 rounded" /> Inactive</div>
        <div className="flex items-center gap-1.5"><Badge className="text-[8px] h-4 px-1 bg-indigo-100 text-indigo-700 border-indigo-200">SPLIT</Badge>Rate divided by branches worked that day</div>
        {isAdmin && <span className="ml-auto text-stone-400">Tip: click any cell to edit the rate for that staff × branch pairing.</span>}
      </div>

      {/* Edit dialog */}
      {edit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={() => setEdit(null)}>
          <div onClick={e => e.stopPropagation()} className="bg-white rounded-2xl shadow-2xl max-w-md w-full" data-testid="cell-editor">
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 text-white rounded-t-2xl p-5">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest opacity-70">Edit rate</p>
                  <h3 className="text-lg font-black">{edit.user.name}</h3>
                  <p className="text-[11px] opacity-80 flex items-center gap-1"><Building2 className="w-3 h-3" />{edit.property.name}</p>
                </div>
                <button onClick={() => setEdit(null)} className="p-1 hover:bg-white/10 rounded"><X className="w-4 h-4" /></button>
              </div>
            </div>
            <div className="p-5 space-y-4">
              {/* Payment type */}
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-2">Payment type</p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "hourly", label: "Hourly", icon: Clock },
                    { id: "daily",  label: "Daily",  icon: Calendar },
                  ].map(opt => {
                    const picked = edit.cell.payment_type === opt.id;
                    return (
                      <button key={opt.id}
                              onClick={() => setEdit({ ...edit, cell: { ...edit.cell, payment_type: opt.id, split: opt.id === "hourly" ? false : edit.cell.split } })}
                              className={`flex items-center justify-center gap-2 px-3 py-2 rounded-lg border text-xs font-semibold transition ${picked ? "bg-amber-50 border-amber-300 text-amber-800" : "bg-white border-stone-200 text-stone-600 hover:border-stone-300"}`}
                              data-testid={`pt-${opt.id}`}>
                        <opt.icon className="w-3.5 h-3.5" />{opt.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Rate */}
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mb-1">
                  Rate ({edit.cell.payment_type === "daily" ? "£ per day" : "£ per hour"})
                </p>
                <div className="relative">
                  <PoundSterling className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <Input type="number" step="0.01" value={edit.cell.rate}
                         onChange={e => setEdit({ ...edit, cell: { ...edit.cell, rate: e.target.value } })}
                         className="pl-9" data-testid="cell-rate" />
                </div>
              </div>

              {/* Split — only relevant for daily */}
              {edit.cell.payment_type === "daily" && (
                <label className="flex items-start gap-2 bg-indigo-50 border border-indigo-200 rounded-xl p-3 cursor-pointer">
                  <Switch checked={!!edit.cell.split}
                          onCheckedChange={v => setEdit({ ...edit, cell: { ...edit.cell, split: v } })}
                          data-testid="cell-split" />
                  <div className="flex-1">
                    <p className="text-xs font-bold text-indigo-900 flex items-center gap-1"><SplitIcon className="w-3 h-3" />Split daily rate across branches</p>
                    <p className="text-[10px] text-indigo-700 mt-0.5">When on, payroll divides this daily rate by the number of branches worked that day.</p>
                  </div>
                </label>
              )}

              {/* Active */}
              <label className="flex items-start gap-2 bg-stone-50 border border-stone-200 rounded-xl p-3 cursor-pointer">
                <Switch checked={edit.cell.active !== false}
                        onCheckedChange={v => setEdit({ ...edit, cell: { ...edit.cell, active: v } })}
                        data-testid="cell-active" />
                <div className="flex-1">
                  <p className="text-xs font-bold text-stone-800 flex items-center gap-1"><Power className="w-3 h-3" />Active at this branch</p>
                  <p className="text-[10px] text-stone-500 mt-0.5">Uncheck to exclude this branch from payroll without deleting the rate.</p>
                </div>
              </label>
            </div>
            <div className="flex items-center justify-between gap-2 p-4 border-t bg-stone-50 rounded-b-2xl">
              <Button variant="outline" size="sm" onClick={deleteCell} disabled={busy === "del"} className="text-red-600 hover:bg-red-50" data-testid="cell-delete">Remove</Button>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => setEdit(null)}>Cancel</Button>
                <Button size="sm" onClick={saveCell} disabled={busy === "save"} className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold" data-testid="cell-save">
                  <Save className="w-3.5 h-3.5 mr-1" />Save
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
