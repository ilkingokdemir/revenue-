import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import {
  ShieldCheck, Search, Plus, X, RefreshCw, Copy, Trash2, Edit,
  ChevronDown, ChevronRight, ArrowLeft, Save, Users, Crown, Grid3X3,
  Sparkles, AlertTriangle, Info, Zap, Command, Eye, Wand2,
  Check as CheckIcon, CircleAlert,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TEMPLATE_TINTS = {
  receptionist:  "from-amber-200 via-amber-100 to-white border-amber-300",
  housekeeper:   "from-emerald-200 via-emerald-100 to-white border-emerald-300",
  manager:       "from-violet-200 via-violet-100 to-white border-violet-300",
  accountant:    "from-yellow-200 via-yellow-100 to-white border-yellow-300",
  laundry_staff: "from-rose-200 via-rose-100 to-white border-rose-300",
  maintenance:   "from-sky-200 via-sky-100 to-white border-sky-300",
};

const RISK_META = {
  critical: { label: "Critical", cls: "bg-rose-100 text-rose-800 border-rose-300", dot: "bg-rose-500", icon: AlertTriangle },
  high:     { label: "High",     cls: "bg-amber-100 text-amber-800 border-amber-300", dot: "bg-amber-500", icon: AlertTriangle },
  medium:   { label: "Medium",   cls: "bg-sky-100 text-sky-800 border-sky-300", dot: "bg-sky-500", icon: Info },
  low:      null, // not shown
};

export const RolesPermissionsPanel = ({ user, propertyId }) => {
  const [view, setView] = useState("list");
  const [data, setData] = useState({ roles: [], total: 0, total_permissions_available: 0 });
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [editingRoleId, setEditingRoleId] = useState(null);
  const [catalog, setCatalog] = useState(null);

  const isAdmin = user?.role === "admin";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (propertyId) params.set("property_id", propertyId);
      const { data: d } = await axios.get(`${API}/rbac/roles?${params}`);
      setData(d);
    } catch {/* silent */}
    setLoading(false);
  }, [q, propertyId]);

  useEffect(() => { const t = setTimeout(load, q ? 250 : 0); return () => clearTimeout(t); }, [load]);
  useEffect(() => { axios.get(`${API}/rbac/catalog`).then(r => setCatalog(r.data)).catch(() => {}); }, []);

  const cloneRole = async (role) => {
    const newKey = window.prompt(`Clone "${role.key}" — enter new key (lowercase_underscores):`, `${role.key}_copy`);
    if (!newKey) return;
    try {
      await axios.post(`${API}/rbac/roles/${role.id}/clone`, { new_key: newKey });
      toast.success(`Cloned as ${newKey}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Clone failed"); }
  };

  const deleteRole = async (role) => {
    if (!window.confirm(`Delete role "${role.key}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API}/rbac/roles/${role.id}`);
      toast.success("Deleted");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Delete failed"); }
  };

  if (view === "create" || view === "edit") {
    return (
      <RoleBuilder
        catalog={catalog}
        propertyId={propertyId}
        roleId={view === "edit" ? editingRoleId : null}
        onCancel={() => { setView("list"); setEditingRoleId(null); }}
        onSaved={() => { setView("list"); setEditingRoleId(null); load(); }}
      />
    );
  }

  return (
    <div className="space-y-5" data-testid="roles-panel">
      {/* Premium hero with grain + glass */}
      <div className="relative rounded-2xl overflow-hidden shadow-2xl">
        <div className="absolute inset-0 bg-gradient-to-br from-[#1a1332] via-[#3a1a5b] to-[#0f172a]" />
        <div className="absolute inset-0 opacity-30"
             style={{ backgroundImage: "radial-gradient(circle at 25% 30%, rgba(236,72,153,0.4), transparent 50%), radial-gradient(circle at 80% 70%, rgba(59,130,246,0.3), transparent 50%)" }} />
        <div className="absolute inset-0 opacity-[0.15]"
             style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.9'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E\")" }} />

        <div className="relative p-7 text-white">
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-8 h-8 rounded-lg bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-80">Roles & Permissions · RBAC</span>
              </div>
              <h2 className="text-4xl font-black mb-2 leading-tight" data-testid="roles-title">
                Precision access control,<br/>
                <span className="bg-gradient-to-r from-pink-300 to-amber-200 bg-clip-text text-transparent">with AI co-pilot.</span>
              </h2>
              <p className="text-sm opacity-80 max-w-xl">
                {data.total_permissions_available} granular permissions · Risk-scored · Dependency-aware · GPT-5.2 can design the whole role from a sentence.
              </p>
            </div>
            <div className="flex flex-col items-end gap-3">
              <div className="flex items-center gap-5">
                <Stat label="Roles" value={data.total} />
                <div className="h-10 w-px bg-white/20" />
                <Stat label="Permissions" value={data.total_permissions_available} />
              </div>
              {isAdmin && (
                <Button size="sm" onClick={() => setView("create")}
                        className="bg-white text-slate-900 hover:bg-white/90 font-bold h-10 px-5 shadow-lg shadow-black/20"
                        data-testid="new-role-btn">
                  <Plus className="w-4 h-4 mr-1.5" />New Role
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search roles by key or display name..." className="pl-9 h-10" data-testid="roles-search" />
        </div>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>

      {/* List */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden" data-testid="roles-list">
        {loading && !data.roles.length && (
          <div className="py-16 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</div>
        )}
        {!loading && !data.roles.length && (
          <div className="py-24 text-center" data-testid="roles-empty">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center">
              <ShieldCheck className="w-8 h-8 text-indigo-600" />
            </div>
            <p className="font-bold text-stone-700 mb-1 text-lg">No custom roles yet</p>
            <p className="text-sm text-stone-500 max-w-md mx-auto mb-5">Start from a template, describe what you need in plain English, or tick permissions by hand.</p>
            {isAdmin && <Button onClick={() => setView("create")} className="bg-indigo-700 hover:bg-indigo-800">
              <Sparkles className="w-4 h-4 mr-1.5" />Design your first role
            </Button>}
          </div>
        )}
        <ul className="divide-y divide-stone-100">
          {data.roles.map(r => (
            <li key={r.id} className="px-5 py-4 hover:bg-stone-50 flex items-center gap-3 group transition" data-testid={`role-row-${r.id}`}>
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center text-white font-bold shadow-sm ${r.is_global_admin ? "bg-gradient-to-br from-amber-500 to-rose-600" : "bg-gradient-to-br from-slate-700 to-slate-900"}`}>
                {r.is_global_admin ? <Crown className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-bold text-stone-900">{r.display_name || r.key}</p>
                  <code className="text-[10px] font-mono bg-stone-100 text-stone-600 px-1.5 py-0.5 rounded">{r.key}</code>
                  {r.is_global_admin && <Badge className="text-[9px] bg-gradient-to-r from-amber-100 to-rose-100 text-amber-900 border-amber-300">GLOBAL ADMIN</Badge>}
                  {r.template_used && <Badge className="text-[9px] bg-indigo-50 text-indigo-800 border-indigo-200">from · {r.template_used}</Badge>}
                </div>
                <div className="flex items-center gap-3 mt-1 text-[11px] text-stone-500">
                  <span className="flex items-center gap-1"><Grid3X3 className="w-3 h-3" />{r.permissions?.length || 0} permissions</span>
                  <span className="text-stone-300">·</span>
                  <span className="flex items-center gap-1"><Users className="w-3 h-3" />{r.assigned_users || 0} user(s)</span>
                  {r.property_name && <><span className="text-stone-300">·</span><span>{r.property_name}</span></>}
                </div>
              </div>
              {isAdmin && (
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition">
                  <Button size="sm" variant="ghost" onClick={() => { setEditingRoleId(r.id); setView("edit"); }} data-testid={`role-edit-${r.id}`}><Edit className="w-3.5 h-3.5" /></Button>
                  <Button size="sm" variant="ghost" onClick={() => cloneRole(r)} data-testid={`role-clone-${r.id}`} title="Clone"><Copy className="w-3.5 h-3.5" /></Button>
                  <Button size="sm" variant="ghost" onClick={() => deleteRole(r)} data-testid={`role-delete-${r.id}`} className="text-red-600 hover:bg-red-50"><Trash2 className="w-3.5 h-3.5" /></Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

const Stat = ({ label, value }) => (
  <div>
    <p className="text-3xl font-black tabular-nums">{value}</p>
    <p className="text-[10px] opacity-70 uppercase tracking-wider font-semibold">{label}</p>
  </div>
);

// ====================== Role Builder (Create + Edit) ======================

const RoleBuilder = ({ catalog, propertyId, roleId, onCancel, onSaved }) => {
  const [form, setForm] = useState({
    key: "", display_name: "", template: null,
    permissions: new Set(), is_global_admin: false,
  });
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(new Set()); // all collapsed by default; expand on search
  const [loading, setLoading] = useState(!!roleId);
  const [search, setSearch] = useState("");
  const [aiOpen, setAiOpen] = useState(false);
  const [aiDesc, setAiDesc] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const searchRef = useRef(null);

  const isEdit = !!roleId;
  const allKeys = catalog?.all_permission_keys || [];
  const templates = catalog?.templates || [];
  const categories = catalog?.catalog || [];

  useEffect(() => {
    if (!roleId) return;
    axios.get(`${API}/rbac/roles/${roleId}`).then(r => {
      const d = r.data;
      setForm({
        key: d.key, display_name: d.display_name || "",
        template: d.template_used, permissions: new Set(d.permissions || []),
        is_global_admin: !!d.is_global_admin,
      });
      setLoading(false);
    }).catch(() => { toast.error("Could not load role"); onCancel(); });
  }, [roleId]);

  // Keyboard: / focuses search, Esc clears
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
        e.preventDefault(); searchRef.current?.focus();
      } else if (e.key === "Escape" && search) {
        setSearch("");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [search]);

  const togglePerm = (key) => {
    const n = new Set(form.permissions);
    n.has(key) ? n.delete(key) : n.add(key);
    setForm({ ...form, permissions: n, template: null });
  };

  const toggleMany = (keys, on) => {
    const n = new Set(form.permissions);
    keys.forEach(k => on ? n.add(k) : n.delete(k));
    setForm({ ...form, permissions: n, template: null });
  };

  const applyTemplate = (t) => {
    const perms = t.permissions === "__ALL__" ? new Set(allKeys) : new Set(t.permissions);
    setForm({
      ...form, template: t.key, permissions: perms,
      key: form.key || t.key, display_name: form.display_name || t.label,
    });
    toast.success(`${t.emoji} ${t.label} loaded · ${perms.size} permissions`);
  };

  const toggleCategory = (catKey) => {
    const n = new Set(expanded);
    n.has(catKey) ? n.delete(catKey) : n.add(catKey);
    setExpanded(n);
  };

  // Filter categories by search — match on label, key, or permission label
  const visibleCategories = useMemo(() => {
    if (!search.trim()) return categories;
    const q = search.toLowerCase();
    return categories
      .map(cat => {
        const filteredSubs = cat.sub_groups.map(sg => {
          const filteredPerms = sg.permissions.filter(p =>
            p.label.toLowerCase().includes(q) ||
            p.key.toLowerCase().includes(q) ||
            sg.label.toLowerCase().includes(q) ||
            cat.label.toLowerCase().includes(q)
          );
          return { ...sg, permissions: filteredPerms };
        }).filter(sg => sg.permissions.length > 0);
        return { ...cat, sub_groups: filteredSubs };
      })
      .filter(cat => cat.sub_groups.length > 0);
  }, [categories, search]);

  // Auto-expand categories that have search hits
  useEffect(() => {
    if (search.trim()) {
      setExpanded(new Set(visibleCategories.map(c => c.key)));
    }
  }, [search, visibleCategories.length]);

  // Stats
  const stats = useMemo(() => {
    let critical = 0, high = 0, medium = 0;
    let menuCount = 0;
    const missingDeps = [];
    for (const cat of categories) {
      for (const sg of cat.sub_groups) {
        for (const p of sg.permissions) {
          if (form.permissions.has(p.key)) {
            if (p.risk === "critical") critical++;
            else if (p.risk === "high") high++;
            else if (p.risk === "medium") medium++;
            if (p.menu) menuCount++;
            // Check implies
            for (const dep of (p.implies || [])) {
              if (!form.permissions.has(dep)) {
                missingDeps.push({ perm: p.key, perm_label: p.label, dep });
              }
            }
          }
        }
      }
    }
    return { critical, high, medium, menuCount, missingDeps };
  }, [form.permissions, categories]);

  const runAI = async () => {
    if (aiDesc.trim().length < 10) { toast.error("Describe the role in a sentence or two"); return; }
    setAiBusy(true); setAiResult(null);
    try {
      const { data } = await axios.post(`${API}/rbac/ai-suggest`, {
        description: aiDesc,
        existing_permissions: Array.from(form.permissions),
      });
      setAiResult(data);
      toast.success(`GPT-5.2 picked ${data.total_suggested} permissions`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "AI suggestion failed");
    }
    setAiBusy(false);
  };

  const applyAI = () => {
    if (!aiResult) return;
    setForm({
      ...form,
      permissions: new Set(aiResult.permissions),
      template: null,
      key: form.key || aiResult.role_name_suggestion || form.key,
      display_name: form.display_name || aiResult.display_name_suggestion || form.display_name,
    });
    setAiOpen(false);
    toast.success("Applied AI suggestion");
  };

  const fixMissingDeps = () => {
    const n = new Set(form.permissions);
    stats.missingDeps.forEach(d => n.add(d.dep));
    setForm({ ...form, permissions: n });
    toast.success(`Added ${stats.missingDeps.length} missing dependencies`);
  };

  const save = async () => {
    const key = form.key.trim().toLowerCase();
    if (!key || !/^[a-z][a-z0-9_]{1,49}$/.test(key)) {
      toast.error("Key must be lowercase letters, digits and underscores (2-50 chars, starts with letter)");
      return;
    }
    setSaving(true);
    try {
      if (isEdit) {
        await axios.put(`${API}/rbac/roles/${roleId}`, {
          display_name: form.display_name || null,
          permissions: Array.from(form.permissions),
          is_global_admin: form.is_global_admin,
        });
      } else {
        await axios.post(`${API}/rbac/roles`, {
          key, display_name: form.display_name || null,
          property_id: propertyId || null,
          permissions: Array.from(form.permissions),
          is_global_admin: form.is_global_admin,
        });
      }
      toast.success(isEdit ? "Role updated" : "Role created");
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
    setSaving(false);
  };

  if (loading) {
    return <div className="py-20 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</div>;
  }

  const selectedCount = form.permissions.size;
  const pct = allKeys.length ? Math.round(100 * selectedCount / allKeys.length) : 0;

  return (
    <div className="pb-28" data-testid="role-builder">
      {/* Top bar */}
      <div className="max-w-6xl mx-auto space-y-5">
        <div className="flex items-center gap-3">
          <Button size="sm" variant="ghost" onClick={onCancel} data-testid="role-back-btn" className="text-stone-600 hover:text-stone-900">
            <ArrowLeft className="w-4 h-4 mr-1" />Back to Roles
          </Button>
        </div>

        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-4xl font-black text-slate-900 leading-tight" data-testid="role-builder-title">
              {isEdit ? <>Edit · <code className="text-2xl font-mono text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">{form.key}</code></> : "Create New Role"}
            </h2>
            <p className="text-sm text-stone-500 mt-1">{selectedCount} of {allKeys.length} permissions selected · {pct}% coverage</p>
          </div>
          <Button
            onClick={() => setAiOpen(true)}
            className="bg-gradient-to-r from-indigo-600 via-fuchsia-600 to-rose-500 hover:opacity-90 text-white font-bold shadow-lg shadow-fuchsia-500/30"
            data-testid="ai-designer-btn"
          >
            <Wand2 className="w-4 h-4 mr-1.5" />AI Role Designer
            <Badge className="ml-2 bg-white/20 text-white text-[9px] border-white/30">GPT-5.2</Badge>
          </Button>
        </div>

        {/* Basic info */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-5 shadow-sm">
          <h3 className="text-sm font-bold text-stone-500 uppercase tracking-wider">Basic Info</h3>

          {!isEdit && (
            <div>
              <p className="text-xs font-semibold text-stone-600 mb-3">Or quick-start with a template:</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3" data-testid="template-grid">
                {templates.map(t => {
                  const picked = form.template === t.key;
                  return (
                    <button key={t.key} onClick={() => applyTemplate(t)}
                            className={`relative p-4 rounded-xl border-2 transition text-left bg-gradient-to-br ${TEMPLATE_TINTS[t.key] || "from-stone-100 to-white border-stone-200"} ${picked ? "ring-2 ring-offset-2 ring-indigo-600 scale-[0.97]" : "hover:shadow-lg hover:-translate-y-0.5"}`}
                            data-testid={`template-${t.key}`}>
                      <div className="text-2xl mb-2">{t.emoji}</div>
                      <p className="font-bold text-sm text-stone-900">{t.label}</p>
                      <p className="text-[10px] text-stone-600 leading-tight mt-0.5">{t.description}</p>
                      {picked && <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center"><CheckIcon className="w-3 h-3" /></div>}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Role Name *</label>
              <Input value={form.key} disabled={isEdit}
                     onChange={e => setForm({ ...form, key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })}
                     placeholder="e.g., night_receptionist" className="mt-1 font-mono text-sm" data-testid="role-key-input" />
              <p className="text-[10px] text-stone-500 mt-1">Internal name · immutable {isEdit && "(locked)"}</p>
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Display Name</label>
              <Input value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })}
                     placeholder="e.g., Night Receptionist" className="mt-1" data-testid="role-display-input" />
              <p className="text-[10px] text-stone-500 mt-1">Shown to users · changeable anytime</p>
            </div>
          </div>

          <label className="flex items-start gap-3 bg-gradient-to-br from-amber-50 to-rose-50 border border-amber-200 rounded-xl p-4 cursor-pointer">
            <Switch checked={form.is_global_admin} onCheckedChange={v => setForm({ ...form, is_global_admin: v })} data-testid="role-global-admin" />
            <div className="flex-1">
              <p className="text-sm font-bold text-amber-900 flex items-center gap-1.5">
                <Crown className="w-4 h-4" />Global Admin
              </p>
              <p className="text-[11px] text-amber-800">Bypasses all permission checks across every property. Trusted super-admins only.</p>
            </div>
          </label>
        </div>

        {/* Capability summary */}
        {selectedCount > 0 && (
          <CapabilitySummary form={form} categories={categories} stats={stats} />
        )}

        {/* Dependency warning */}
        {stats.missingDeps.length > 0 && (
          <div className="bg-amber-50 border border-amber-300 rounded-xl p-4 flex items-start gap-3" data-testid="dep-warning">
            <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-bold text-amber-900">{stats.missingDeps.length} missing dependenc{stats.missingDeps.length === 1 ? "y" : "ies"}</p>
              <p className="text-[11px] text-amber-800 mt-0.5">
                Some granted permissions need others to function. E.g., <code className="bg-amber-100 px-1 rounded">{stats.missingDeps[0].perm}</code> needs <code className="bg-amber-100 px-1 rounded">{stats.missingDeps[0].dep}</code>.
              </p>
            </div>
            <Button size="sm" onClick={fixMissingDeps} className="bg-amber-600 hover:bg-amber-700 text-white font-bold flex-shrink-0" data-testid="fix-deps-btn">
              <Zap className="w-3.5 h-3.5 mr-1" />Fix all
            </Button>
          </div>
        )}

        {/* Permission tree */}
        <div className="bg-white border border-stone-200 rounded-2xl shadow-sm">
          <div className="sticky top-0 bg-white z-10 p-5 border-b border-stone-100 rounded-t-2xl">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div>
                <h3 className="text-sm font-bold text-stone-500 uppercase tracking-wider">Permissions</h3>
                <div className="mt-1 flex items-center gap-2">
                  <span className="text-2xl font-black text-stone-900 tabular-nums">{selectedCount}</span>
                  <span className="text-sm text-stone-500">/ {allKeys.length}</span>
                  {stats.critical > 0 && <Badge className="bg-rose-100 text-rose-800 border-rose-300"><AlertTriangle className="w-3 h-3 mr-1" />{stats.critical} critical</Badge>}
                  {stats.high > 0 && <Badge className="bg-amber-100 text-amber-800 border-amber-300">{stats.high} high</Badge>}
                  {stats.menuCount > 0 && <Badge className="bg-violet-100 text-violet-800 border-violet-300">{stats.menuCount} sidebar</Badge>}
                </div>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <button className="text-indigo-700 font-semibold hover:underline" data-testid="select-all-perms"
                        onClick={() => setForm({ ...form, permissions: new Set(allKeys), template: null })}>Select all</button>
                <span className="text-stone-300">·</span>
                <button className="text-stone-600 font-semibold hover:underline" data-testid="deselect-all-perms"
                        onClick={() => setForm({ ...form, permissions: new Set(), template: null })}>Clear</button>
              </div>
            </div>

            {/* Search */}
            <div className="relative">
              <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <Input ref={searchRef} value={search} onChange={e => setSearch(e.target.value)}
                     placeholder="Search permissions... (press / to focus)" className="pl-9 pr-16 h-10" data-testid="perm-search" />
              <kbd className="hidden sm:inline-flex absolute right-3 top-1/2 -translate-y-1/2 items-center gap-0.5 text-[10px] text-stone-400 font-mono bg-stone-100 px-1.5 py-0.5 rounded">
                <Command className="w-3 h-3" />/
              </kbd>
              {search && (
                <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-600">
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>

          <div className="p-5 space-y-2" data-testid="permission-tree">
            {visibleCategories.length === 0 && (
              <div className="py-12 text-center text-stone-400 text-sm">
                No permissions match <code className="bg-stone-100 px-1 rounded">{search}</code>
              </div>
            )}
            {visibleCategories.map(cat => {
              const allCatKeys = cat.sub_groups.flatMap(sg => sg.permissions.map(p => p.key));
              const selectedInCat = allCatKeys.filter(k => form.permissions.has(k)).length;
              const isExpanded = expanded.has(cat.key);
              const ringPct = allCatKeys.length ? (selectedInCat / allCatKeys.length) * 100 : 0;
              return (
                <div key={cat.key} className="border border-stone-200 rounded-xl overflow-hidden transition" data-testid={`cat-${cat.key}`}>
                  <div className={`flex items-center justify-between px-4 py-3 cursor-pointer transition ${isExpanded ? "bg-indigo-50/40" : "bg-stone-50 hover:bg-stone-100"}`}
                       onClick={() => toggleCategory(cat.key)}>
                    <div className="flex items-center gap-2.5 flex-1">
                      <div className="relative w-8 h-8">
                        <svg className="w-8 h-8 -rotate-90" viewBox="0 0 32 32">
                          <circle cx="16" cy="16" r="13" fill="none" stroke="#e7e5e4" strokeWidth="3" />
                          <circle cx="16" cy="16" r="13" fill="none"
                                  stroke={selectedInCat === allCatKeys.length ? "#10b981" : "#4f46e5"}
                                  strokeWidth="3" strokeDasharray={`${(ringPct * 81.68) / 100} 82`} strokeLinecap="round" />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-stone-700">{selectedInCat}</div>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-stone-900">{cat.label}</span>
                          <span className="text-[10px] text-stone-500">{selectedInCat}/{allCatKeys.length}</span>
                        </div>
                      </div>
                      {isExpanded ? <ChevronDown className="w-4 h-4 text-stone-400" /> : <ChevronRight className="w-4 h-4 text-stone-400" />}
                    </div>
                    <button className="ml-3 text-indigo-700 text-xs font-semibold hover:underline flex-shrink-0"
                            onClick={(e) => { e.stopPropagation(); toggleMany(allCatKeys, selectedInCat !== allCatKeys.length); }}
                            data-testid={`cat-select-all-${cat.key}`}>
                      {selectedInCat === allCatKeys.length ? "Clear" : "Select all"}
                    </button>
                  </div>

                  {isExpanded && (
                    <div className="p-4 space-y-3 bg-white">
                      {cat.sub_groups.map(sg => {
                        const keys = sg.permissions.map(p => p.key);
                        const selected = keys.filter(k => form.permissions.has(k)).length;
                        return (
                          <div key={sg.key} className="border border-stone-100 rounded-lg p-3 bg-stone-50/50">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-stone-700 uppercase tracking-wide">{sg.label}</span>
                                <Badge className="text-[9px] bg-white text-stone-600 border-stone-200">{selected}/{keys.length}</Badge>
                              </div>
                              <button className="text-indigo-700 text-[11px] font-semibold hover:underline"
                                      onClick={() => toggleMany(keys, selected !== keys.length)}
                                      data-testid={`sg-select-${sg.key}`}>
                                {selected === keys.length ? "Clear" : "Select"}
                              </button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {sg.permissions.map(p => {
                                const checked = form.permissions.has(p.key);
                                const risk = RISK_META[p.risk];
                                const depMissing = checked && (p.implies || []).some(d => !form.permissions.has(d));
                                return (
                                  <label key={p.key}
                                         title={p.key + (p.implies?.length ? `\n\nRequires: ${p.implies.join(", ")}` : "")}
                                         className={`group/p flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs cursor-pointer transition select-none
                                           ${checked ? "bg-indigo-50 border-indigo-300 text-indigo-900 shadow-sm" : "bg-white border-stone-200 text-stone-700 hover:border-stone-300 hover:bg-stone-50"}
                                           ${p.missing ? "opacity-40 cursor-not-allowed" : ""}
                                           ${depMissing ? "ring-1 ring-amber-300" : ""}`}
                                         data-testid={`perm-${p.key}`}>
                                    <Checkbox checked={checked} onCheckedChange={() => togglePerm(p.key)} disabled={p.missing}
                                              className="data-[state=checked]:bg-indigo-600 data-[state=checked]:border-indigo-600" />
                                    <span>{p.label}</span>
                                    {p.menu && <Badge className="text-[8px] h-4 px-1 bg-violet-100 text-violet-700 border-violet-200">MENU</Badge>}
                                    {risk && <Badge className={`text-[8px] h-4 px-1 ${risk.cls}`} title={`Risk: ${risk.label}`}>
                                      <span className={`w-1 h-1 rounded-full ${risk.dot} mr-0.5`} />{risk.label.toUpperCase()}
                                    </Badge>}
                                    {p.missing && <Badge className="text-[8px] h-4 px-1 bg-amber-100 text-amber-700 border-amber-200">MISSING</Badge>}
                                    {depMissing && <CircleAlert className="w-3 h-3 text-amber-600" title="Missing dependency" />}
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Sticky save bar */}
      <div className="fixed bottom-0 left-0 right-0 lg:left-56 bg-white/90 backdrop-blur-lg border-t border-stone-200 px-6 py-3 z-40 shadow-[0_-8px_30px_-10px_rgba(0,0,0,0.1)]">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
          <div className="text-xs text-stone-500">
            <span className="font-bold text-stone-800 tabular-nums">{selectedCount}</span> / {allKeys.length} selected
            {stats.missingDeps.length > 0 && <span className="text-amber-700 ml-3">⚠ {stats.missingDeps.length} missing deps</span>}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={onCancel}>Cancel</Button>
            <Button onClick={save} disabled={saving} className="bg-indigo-700 hover:bg-indigo-800 text-white font-bold px-6" data-testid="role-save-btn">
              <Save className="w-3.5 h-3.5 mr-1.5" />{isEdit ? "Save Changes" : "Create Role"}
            </Button>
          </div>
        </div>
      </div>

      {/* AI Designer sheet */}
      {aiOpen && (
        <AIDesigner aiDesc={aiDesc} setAiDesc={setAiDesc} aiBusy={aiBusy} aiResult={aiResult}
                    onRun={runAI} onApply={applyAI} onClose={() => { setAiOpen(false); setAiResult(null); }} />
      )}
    </div>
  );
};

// ====================== Capability Summary (plain-English) ======================

const CapabilitySummary = ({ form, categories, stats }) => {
  // Plain-English groupings
  const can = [];
  const cannot = [];
  for (const cat of categories) {
    const catKeys = cat.sub_groups.flatMap(sg => sg.permissions.map(p => p.key));
    const selectedInCat = catKeys.filter(k => form.permissions.has(k)).length;
    if (selectedInCat === 0) cannot.push(cat.label);
    else if (selectedInCat === catKeys.length) can.push(`full access to ${cat.label}`);
    else can.push(`${cat.label} (${selectedInCat}/${catKeys.length})`);
  }

  return (
    <div className="bg-gradient-to-br from-indigo-50 via-white to-violet-50 border border-indigo-200 rounded-2xl p-5 shadow-sm" data-testid="capability-summary">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center flex-shrink-0">
          <Eye className="w-5 h-5 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wider text-indigo-700">What this role can do</p>
          <p className="text-sm text-stone-800 mt-1 leading-relaxed">
            {can.length
              ? <>Users with this role get <b>{can.join(", ")}</b>.</>
              : <>No permissions granted yet.</>}
          </p>
          {cannot.length > 0 && (
            <p className="text-xs text-stone-500 mt-2">
              <span className="font-semibold">Blocked from:</span> {cannot.slice(0, 5).join(", ")}{cannot.length > 5 ? `, +${cannot.length - 5} more` : ""}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

// ====================== AI Designer Sheet ======================

const AIDesigner = ({ aiDesc, setAiDesc, aiBusy, aiResult, onRun, onApply, onClose }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm" onClick={onClose}>
    <div onClick={e => e.stopPropagation()}
         className="bg-white rounded-2xl shadow-2xl max-w-xl w-full max-h-[90vh] overflow-y-auto"
         data-testid="ai-designer">
      <div className="relative overflow-hidden rounded-t-2xl bg-gradient-to-br from-indigo-600 via-fuchsia-600 to-rose-500 text-white p-6">
        <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "radial-gradient(circle at 80% 20%, white, transparent 40%)" }} />
        <div className="relative flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-8 h-8 rounded-lg bg-white/20 backdrop-blur-md flex items-center justify-center"><Wand2 className="w-4 h-4" /></div>
              <span className="text-[10px] font-bold uppercase tracking-widest opacity-90">AI Role Designer</span>
              <Badge className="text-[9px] bg-white/20 text-white border-white/30">GPT-5.2</Badge>
            </div>
            <h3 className="text-2xl font-black">Describe. We'll pick.</h3>
            <p className="text-sm opacity-90 mt-0.5">Tell it what this role should do — we pick the permissions.</p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-white/10 rounded"><X className="w-4 h-4" /></button>
        </div>
      </div>

      <div className="p-6 space-y-4">
        <div>
          <label className="text-[10px] font-bold uppercase tracking-wider text-stone-500">Role description</label>
          <Textarea value={aiDesc} onChange={e => setAiDesc(e.target.value)} rows={4}
                    placeholder='e.g. "A night shift receptionist who checks in guests, handles petty cash reconciliation, views rates but cannot edit them, and should not see payroll."'
                    className="mt-1" data-testid="ai-desc" />
          <p className="text-[10px] text-stone-400 mt-1">The more specific, the better. Mention what they should NOT be able to do.</p>
        </div>

        <Button onClick={onRun} disabled={aiBusy || aiDesc.trim().length < 10}
                className="w-full bg-gradient-to-r from-indigo-600 to-fuchsia-600 hover:opacity-90 text-white font-bold h-11" data-testid="ai-run">
          {aiBusy ? <><RefreshCw className="w-4 h-4 mr-1.5 animate-spin" />GPT-5.2 is thinking...</> : <><Sparkles className="w-4 h-4 mr-1.5" />Design with GPT-5.2</>}
        </Button>

        {aiResult && (
          <div className="space-y-3" data-testid="ai-result">
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 mb-1 flex items-center gap-1">
                <CheckIcon className="w-3 h-3" />GPT-5.2 picked {aiResult.total_suggested} permissions
                {aiResult.invalid_dropped > 0 && <span className="text-amber-600 ml-1">· {aiResult.invalid_dropped} invalid dropped</span>}
              </p>
              {aiResult.display_name_suggestion && (
                <p className="text-xs text-emerald-900">
                  <span className="font-semibold">Suggested name:</span> {aiResult.display_name_suggestion} <code className="text-[10px] bg-emerald-100 px-1 rounded">{aiResult.role_name_suggestion}</code>
                </p>
              )}
              <p className="text-sm text-stone-700 mt-2 leading-relaxed">{aiResult.reasoning}</p>
            </div>

            <Button onClick={onApply} className="w-full bg-slate-900 hover:bg-slate-800 text-white font-bold h-11" data-testid="ai-apply">
              <Zap className="w-4 h-4 mr-1.5" />Apply to this role
            </Button>
          </div>
        )}
      </div>
    </div>
  </div>
);
