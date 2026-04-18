import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  ShieldCheck, Search, Plus, X, RefreshCw, Copy, Trash2, Edit,
  ChevronDown, ChevronRight, ArrowLeft, Save, Users, Crown, Grid3X3,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Gradient tints for template tiles — mirrors the competitor but crisper
const TEMPLATE_TINTS = {
  receptionist:  "from-amber-100 to-amber-50 border-amber-200",
  housekeeper:   "from-emerald-100 to-emerald-50 border-emerald-200",
  manager:       "from-violet-100 to-violet-50 border-violet-200",
  accountant:    "from-yellow-100 to-yellow-50 border-yellow-200",
  laundry_staff: "from-rose-100 to-rose-50 border-rose-200",
  maintenance:   "from-sky-100 to-sky-50 border-sky-200",
};

export const RolesPermissionsPanel = ({ user, propertyId }) => {
  const [view, setView] = useState("list"); // list | create | edit
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

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => {
    axios.get(`${API}/rbac/catalog`).then(r => setCatalog(r.data)).catch(() => {});
  }, []);

  const cloneRole = async (role) => {
    const newKey = window.prompt(`Clone "${role.key}" — enter new key (lowercase_underscores):`, `${role.key}_copy`);
    if (!newKey) return;
    try {
      await axios.post(`${API}/rbac/roles/${role.id}/clone`, { new_key: newKey });
      toast.success(`Cloned as ${newKey}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Clone failed");
    }
  };

  const deleteRole = async (role) => {
    if (!window.confirm(`Delete role "${role.key}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API}/rbac/roles/${role.id}`);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
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
      {/* Hero */}
      <div className="bg-gradient-to-br from-slate-900 via-indigo-900 to-slate-800 rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-white/5 rounded-full -translate-y-40 translate-x-40 blur-3xl" />
        <div className="relative flex items-start justify-between gap-6 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="w-5 h-5" />
              <span className="text-[11px] font-bold uppercase tracking-widest opacity-80">Roles & Permissions</span>
            </div>
            <h2 className="text-3xl font-black mb-1" data-testid="roles-title">Give every teammate exactly the access they need.</h2>
            <p className="text-sm opacity-85">
              {data.total_permissions_available}+ granular permissions across 15 categories. Quick-start templates, clone-and-tweak, global admin, state transitions.
            </p>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <KPI label="Roles" value={data.total} />
            <KPI label="Permissions" value={data.total_permissions_available} />
            {isAdmin && (
              <Button size="sm" className="bg-white text-slate-900 hover:bg-stone-100 font-bold" onClick={() => setView("create")} data-testid="new-role-btn">
                <Plus className="w-4 h-4 mr-1" />New Role
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Search roles by key or display name..." className="pl-9 h-9" data-testid="roles-search" />
        </div>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>

      {/* List */}
      <div className="bg-white rounded-2xl border border-stone-200 overflow-hidden" data-testid="roles-list">
        {loading && !data.roles.length && (
          <div className="py-16 text-center text-stone-400"><RefreshCw className="w-5 h-5 animate-spin inline mr-2" />Loading...</div>
        )}
        {!loading && !data.roles.length && (
          <div className="py-20 text-center" data-testid="roles-empty">
            <ShieldCheck className="w-12 h-12 mx-auto mb-3 text-stone-300" />
            <p className="font-semibold text-stone-600 mb-1">No custom roles yet</p>
            <p className="text-xs text-stone-400">Quick-start with a template and tune from there.</p>
            {isAdmin && <Button className="mt-4" size="sm" onClick={() => setView("create")}>
              <Plus className="w-4 h-4 mr-1" />Create the first role
            </Button>}
          </div>
        )}
        <ul className="divide-y divide-stone-100">
          {data.roles.map(r => (
            <li key={r.id} className="px-4 py-3 hover:bg-stone-50 flex items-center gap-3" data-testid={`role-row-${r.id}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold ${r.is_global_admin ? "bg-gradient-to-br from-amber-500 to-rose-600" : "bg-slate-800"}`}>
                {r.is_global_admin ? <Crown className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-semibold text-stone-800 text-sm">{r.display_name || r.key}</p>
                  <code className="text-[10px] font-mono bg-stone-100 text-stone-600 px-1.5 py-0.5 rounded">{r.key}</code>
                  {r.is_global_admin && <Badge className="text-[9px] bg-amber-100 text-amber-800 border-amber-200">GLOBAL ADMIN</Badge>}
                  {r.template_used && <Badge className="text-[9px] bg-indigo-100 text-indigo-800 border-indigo-200">from template · {r.template_used}</Badge>}
                </div>
                <div className="flex items-center gap-3 mt-0.5 text-[11px] text-stone-500">
                  <span className="flex items-center gap-1"><Grid3X3 className="w-3 h-3" />{r.permissions?.length || 0} permissions</span>
                  <span>·</span>
                  <span className="flex items-center gap-1"><Users className="w-3 h-3" />{r.assigned_users || 0} user(s)</span>
                  {r.property_name && <>
                    <span>·</span>
                    <span>{r.property_name}</span>
                  </>}
                </div>
              </div>
              {isAdmin && (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button size="sm" variant="ghost" onClick={() => { setEditingRoleId(r.id); setView("edit"); }} data-testid={`role-edit-${r.id}`}>
                    <Edit className="w-3.5 h-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => cloneRole(r)} data-testid={`role-clone-${r.id}`} title="Clone role">
                    <Copy className="w-3.5 h-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => deleteRole(r)} data-testid={`role-delete-${r.id}`} className="text-red-600 hover:bg-red-50">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

const KPI = ({ label, value }) => (
  <div>
    <p className="text-2xl font-black">{value}</p>
    <p className="text-[10px] opacity-80 uppercase tracking-wider">{label}</p>
  </div>
);

// ====================== Role Builder (Create + Edit) ======================

const RoleBuilder = ({ catalog, propertyId, roleId, onCancel, onSaved }) => {
  const [form, setForm] = useState({
    key: "",
    display_name: "",
    template: null,
    permissions: new Set(),
    is_global_admin: false,
  });
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(new Set(["bookings", "operations"])); // initial expanded cats
  const [loading, setLoading] = useState(!!roleId);

  const isEdit = !!roleId;

  useEffect(() => {
    if (!roleId) return;
    axios.get(`${API}/rbac/roles/${roleId}`).then(r => {
      const d = r.data;
      setForm({
        key: d.key,
        display_name: d.display_name || "",
        template: d.template_used,
        permissions: new Set(d.permissions || []),
        is_global_admin: !!d.is_global_admin,
      });
      setLoading(false);
    }).catch(() => { toast.error("Could not load role"); onCancel(); });
  }, [roleId]);

  const allKeys = catalog?.all_permission_keys || [];
  const templates = catalog?.templates || [];
  const categories = catalog?.catalog || [];

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
      ...form,
      template: t.key,
      permissions: perms,
      key: form.key || t.key,
      display_name: form.display_name || t.label,
    });
    toast.success(`Template '${t.label}' loaded — ${perms.size} permissions`);
  };

  const toggleCategory = (catKey) => {
    const n = new Set(expanded);
    n.has(catKey) ? n.delete(catKey) : n.add(catKey);
    setExpanded(n);
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
          key,
          display_name: form.display_name || null,
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

  return (
    <div className="space-y-5 max-w-5xl mx-auto" data-testid="role-builder">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button size="sm" variant="ghost" onClick={onCancel} data-testid="role-back-btn">
          <ArrowLeft className="w-4 h-4 mr-1" />Back to Roles
        </Button>
      </div>
      <h2 className="text-3xl font-black text-slate-900" data-testid="role-builder-title">
        {isEdit ? `Edit Role · ${form.key}` : "Create New Role"}
      </h2>

      {/* Basic Info card */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-5">
        <h3 className="text-lg font-bold text-stone-800">Basic Information</h3>

        {!isEdit && (
          <div>
            <p className="text-xs font-semibold text-stone-600 mb-3">Quick start with a template:</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3" data-testid="template-grid">
              {templates.map(t => {
                const picked = form.template === t.key;
                return (
                  <button key={t.key}
                          onClick={() => applyTemplate(t)}
                          className={`p-4 rounded-xl border-2 transition text-left bg-gradient-to-br ${TEMPLATE_TINTS[t.key] || "from-stone-50 to-white border-stone-200"} ${picked ? "ring-2 ring-offset-2 ring-indigo-500 scale-[0.98]" : "hover:shadow-md"}`}
                          data-testid={`template-${t.key}`}>
                    <div className="w-10 h-10 rounded-full bg-white/80 flex items-center justify-center text-xl mb-2 shadow-sm">
                      {t.emoji}
                    </div>
                    <p className="font-bold text-sm text-stone-900">{t.label}</p>
                    <p className="text-[11px] text-stone-600">{t.description}</p>
                    {picked && <p className="text-[10px] text-indigo-700 font-bold mt-1">✓ SELECTED</p>}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {propertyId && (
          <div className="bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 text-sm text-stone-700">
            <span className="text-[10px] font-bold uppercase tracking-wider text-stone-500 mr-2">Branch:</span>
            {propertyId}
          </div>
        )}

        <div>
          <label className="text-xs font-semibold text-stone-700">Role Name *</label>
          <Input
            value={form.key}
            onChange={e => setForm({ ...form, key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })}
            placeholder="e.g., manager, night_receptionist"
            disabled={isEdit}
            className="mt-1 font-mono text-sm"
            data-testid="role-key-input"
          />
          <p className="text-[10px] text-stone-500 mt-1">
            Use lowercase letters and underscores. This is the <b>internal name</b> and {isEdit ? "cannot be changed." : "cannot be changed later."}
          </p>
        </div>

        <div>
          <label className="text-xs font-semibold text-stone-700">Display Name</label>
          <Input
            value={form.display_name}
            onChange={e => setForm({ ...form, display_name: e.target.value })}
            placeholder="e.g., Night Receptionist, Senior Manager"
            className="mt-1"
            data-testid="role-display-input"
          />
          <p className="text-[10px] text-stone-500 mt-1">Optional. This is the name shown to users. Can be changed anytime.</p>
        </div>

        <label className="flex items-start gap-3 bg-gradient-to-br from-amber-50 to-rose-50 border border-amber-200 rounded-xl p-3 cursor-pointer">
          <Switch checked={form.is_global_admin} onCheckedChange={v => setForm({ ...form, is_global_admin: v })} data-testid="role-global-admin" />
          <div className="flex-1">
            <p className="text-sm font-bold text-amber-900 flex items-center gap-1">
              <Crown className="w-3.5 h-3.5" />Global Admin
            </p>
            <p className="text-[11px] text-amber-800">Bypasses all permission checks. Use only for trusted super-admins.</p>
          </div>
        </label>
      </div>

      {/* Permissions */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-stone-800">Permissions</h3>
            <p className="text-xs text-stone-500">{form.permissions.size} of {allKeys.length} selected</p>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <button className="text-indigo-600 font-semibold hover:underline" data-testid="select-all-perms"
                    onClick={() => setForm({ ...form, permissions: new Set(allKeys), template: null })}>Select All</button>
            <span className="text-stone-300">|</span>
            <button className="text-stone-600 font-semibold hover:underline" data-testid="deselect-all-perms"
                    onClick={() => setForm({ ...form, permissions: new Set(), template: null })}>Deselect All</button>
          </div>
        </div>

        <div className="space-y-2" data-testid="permission-tree">
          {categories.map(cat => {
            const allCatKeys = cat.sub_groups.flatMap(sg => sg.permissions.map(p => p.key));
            const selectedInCat = allCatKeys.filter(k => form.permissions.has(k)).length;
            const isExpanded = expanded.has(cat.key);
            return (
              <div key={cat.key} className="border border-stone-200 rounded-xl overflow-hidden" data-testid={`cat-${cat.key}`}>
                <div className="flex items-center justify-between px-4 py-3 bg-stone-50 hover:bg-stone-100 transition cursor-pointer"
                     onClick={() => toggleCategory(cat.key)}>
                  <div className="flex items-center gap-2 flex-1">
                    {isExpanded ? <ChevronDown className="w-4 h-4 text-stone-500" /> : <ChevronRight className="w-4 h-4 text-stone-500" />}
                    <span className="font-semibold text-sm text-stone-800">{cat.label}</span>
                    <Badge className="text-[9px] bg-stone-200 text-stone-700 border-stone-300">{selectedInCat}/{allCatKeys.length}</Badge>
                  </div>
                  <button className="text-indigo-600 text-xs font-semibold hover:underline"
                          onClick={(e) => { e.stopPropagation(); toggleMany(allCatKeys, selectedInCat !== allCatKeys.length); }}
                          data-testid={`cat-select-all-${cat.key}`}>
                    {selectedInCat === allCatKeys.length ? "Deselect All" : "Select All"}
                  </button>
                </div>

                {isExpanded && (
                  <div className="p-4 space-y-3">
                    {cat.sub_groups.map(sg => {
                      const keys = sg.permissions.map(p => p.key);
                      const selected = keys.filter(k => form.permissions.has(k)).length;
                      return (
                        <div key={sg.key} className="border border-stone-100 rounded-lg p-3 bg-white">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-stone-700">{sg.label}</span>
                              <Badge className="text-[9px] bg-stone-100 text-stone-600 border-stone-200">{selected}/{keys.length}</Badge>
                            </div>
                            <button className="text-indigo-600 text-[11px] font-semibold hover:underline"
                                    onClick={() => toggleMany(keys, selected !== keys.length)}
                                    data-testid={`sg-select-${sg.key}`}>
                              {selected === keys.length ? "Deselect" : "Select"}
                            </button>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {sg.permissions.map(p => {
                              const checked = form.permissions.has(p.key);
                              return (
                                <label key={p.key}
                                       className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md border text-xs cursor-pointer transition
                                         ${checked ? "bg-indigo-50 border-indigo-300 text-indigo-900" : "bg-white border-stone-200 text-stone-700 hover:border-stone-300"}
                                         ${p.missing ? "opacity-50" : ""}`}
                                       data-testid={`perm-${p.key}`}>
                                  <Checkbox checked={checked} onCheckedChange={() => togglePerm(p.key)} disabled={p.missing} />
                                  <span>{p.label}</span>
                                  {p.menu && <Badge className="text-[8px] h-4 px-1 bg-violet-100 text-violet-700 border-violet-200">MENU</Badge>}
                                  {p.missing && <Badge className="text-[8px] h-4 px-1 bg-amber-100 text-amber-700 border-amber-200">MISSING</Badge>}
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

      {/* Sticky save bar */}
      <div className="flex items-center justify-end gap-2 sticky bottom-0 bg-white border-t border-stone-200 py-3 -mx-6 px-6">
        <Button variant="outline" onClick={onCancel}>Cancel</Button>
        <Button onClick={save} disabled={saving} className="bg-indigo-700 hover:bg-indigo-800 text-white font-bold" data-testid="role-save-btn">
          <Save className="w-3.5 h-3.5 mr-1" />{isEdit ? "Save Changes" : "Create Role"}
        </Button>
      </div>
    </div>
  );
};
