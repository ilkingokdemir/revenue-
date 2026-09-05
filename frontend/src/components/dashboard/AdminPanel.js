import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import PermissionMatrixCard from "./PermissionMatrixCard";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Shield, Users, Settings, Plus, Trash2, Save, ChevronDown, ChevronRight, Check, X, Package, FileText, ShoppingCart, CreditCard, BarChart3, MessageSquare, Star, UserCheck, Zap, LayoutDashboard, ClipboardList, Truck, Activity, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODULE_META = {
  dashboard: { icon: LayoutDashboard, label: "Dashboard", color: "#1C1917" },
  reviews: { icon: Star, label: "Reviews", color: "#D4A373" },
  bookings: { icon: ClipboardList, label: "Bookings", color: "#1E40AF" },
  pos: { icon: ShoppingCart, label: "Point of Sale", color: "#2C4C3B" },
  payments: { icon: CreditCard, label: "Payments", color: "#6B21A8" },
  accounting: { icon: BarChart3, label: "Accounting", color: "#065F46" },
  stock: { icon: Package, label: "Stock / F&B", color: "#92400E" },
  messaging: { icon: MessageSquare, label: "Messaging", color: "#0EA5E9" },
  surveys: { icon: FileText, label: "Surveys", color: "#DC2626" },
  guest_profiles: { icon: UserCheck, label: "Guest Profiles", color: "#7C3AED" },
  campaigns: { icon: Zap, label: "Campaigns", color: "#EA580C" },
  staff_performance: { icon: Users, label: "Staff Performance", color: "#0D9488" },
  automation: { icon: Zap, label: "Automation", color: "#4F46E5" },
  settings: { icon: Settings, label: "Settings", color: "#78716C" },
};

const ACTION_LABELS = { view: "View", create: "Create", edit: "Edit", delete: "Delete", export: "Export", manage_settings: "Settings" };

export function AdminPanel({ properties, user, activePropertyId }) {
  const [tab, setTab] = useState("roles");
  const [roles, setRoles] = useState([]);
  const [modules, setModules] = useState([]);
  const [actions, setActions] = useState([]);
  const [users, setUsers] = useState([]);
  const [moduleSettings, setModuleSettings] = useState({});
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNewRole, setShowNewRole] = useState(false);
  const [newRole, setNewRole] = useState({ id: "", name: "", description: "", permissions: {} });
  const [editingUser, setEditingUser] = useState(null);
  const [editingModule, setEditingModule] = useState(null);
  const [expandedRole, setExpandedRole] = useState(null);
  const [generatingPO, setGeneratingPO] = useState(false);

  const propertyId = (activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchRoles = useCallback(async () => { const { data } = await axios.get(`${API}/admin/roles`); setRoles(data.roles); setModules(data.modules); setActions(data.actions); }, []);
  const fetchUsers = useCallback(async () => { const { data } = await axios.get(`${API}/admin/users`); setUsers(data); }, []);
  const fetchModuleSettings = useCallback(async () => { const { data } = await axios.get(`${API}/admin/module-settings-all/${propertyId}`); setModuleSettings(data); }, [propertyId]);
  const fetchPOs = useCallback(async () => { const { data } = await axios.get(`${API}/admin/purchase-orders/${propertyId}`); setPurchaseOrders(data); }, [propertyId]);

  useEffect(() => { setLoading(true); Promise.all([fetchRoles(), fetchUsers()]).then(() => setLoading(false)); }, [fetchRoles, fetchUsers]);
  useEffect(() => { if (tab === "module-settings") fetchModuleSettings(); }, [tab, fetchModuleSettings]);
  useEffect(() => { if (tab === "purchase-orders") fetchPOs(); }, [tab, fetchPOs]);

  const createRole = async () => {
    if (!newRole.name) return toast.error("Role name required");
    try {
      await axios.post(`${API}/admin/roles`, { ...newRole, id: newRole.id || newRole.name.toLowerCase().replace(/\s+/g, "_") });
      toast.success("Role created"); setShowNewRole(false); setNewRole({ id: "", name: "", description: "", permissions: {} }); fetchRoles();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const deleteRole = async (roleId) => {
    if (!confirm(`Delete role "${roleId}"?`)) return;
    try { await axios.delete(`${API}/admin/roles/${roleId}`); toast.success("Role deleted"); fetchRoles(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const togglePermission = async (roleId, module, action) => {
    const role = roles.find(r => r.id === roleId);
    if (!role || role.is_builtin) return toast.error("Cannot modify built-in roles");
    const perms = { ...role.permissions };
    if (!perms[module]) perms[module] = [];
    if (perms[module].includes(action)) perms[module] = perms[module].filter(a => a !== action);
    else perms[module] = [...perms[module], action];
    try {
      await axios.put(`${API}/admin/roles/${roleId}`, { permissions: perms });
      fetchRoles();
    } catch (e) { toast.error("Failed to update"); }
  };

  const updateUserRole = async (userId, role) => {
    try { await axios.put(`${API}/admin/users/${userId}/permissions`, { role }); toast.success("Role updated"); fetchUsers(); }
    catch (e) { toast.error("Failed"); }
  };
  const saveUserField = async (userId, patch) => {
    try { await axios.put(`${API}/admin/users/${userId}/permissions`, patch); toast.success(patch.phone !== undefined ? "Telefon kaydedildi" : "Güncellendi"); fetchUsers(); }
    catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };

  const saveModuleSettings = async (module) => {
    try {
      await axios.put(`${API}/admin/module-settings/${module}/${propertyId}`, moduleSettings[module]);
      toast.success(`${MODULE_META[module]?.label || module} settings saved`);
    } catch (e) { toast.error("Failed to save"); }
  };

  const tabs = [
    { id: "roles", label: "Roles & Permissions", icon: Shield },
    { id: "users", label: "Team Members", icon: Users },
    { id: "module-settings", label: "Module Settings", icon: Settings },
    { id: "purchase-orders", label: "Purchase Orders", icon: Truck },
    { id: "system-health", label: "Sistem Sağlığı", icon: Activity },
    { id: "certifications", label: "Canlıya Geçiş", icon: Shield },
    { id: "matrix", label: "Yetki Matrisi", icon: Shield },
  ];

  if (loading) return <div className="flex items-center justify-center h-96"><div className="w-8 h-8 border-3 border-stone-300 border-t-[#2C4C3B] rounded-full animate-spin" /></div>;

  return (
    <div className="h-full flex flex-col" data-testid="admin-panel">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#2C4C3B] flex items-center justify-center"><Shield size={18} className="text-white" /></div>
          <div><h2 className="text-lg font-bold text-stone-900" style={{ fontFamily: "Outfit, sans-serif" }}>Admin Panel</h2><p className="text-[11px] text-stone-500">Roles, Permissions, Module Settings</p></div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 bg-white px-6 flex gap-1 flex-shrink-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-[3px] transition-all ${tab === t.id ? "border-[#2C4C3B] text-[#2C4C3B]" : "border-transparent text-stone-400 hover:text-stone-600"}`}
            data-testid={`admin-tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto bg-stone-50 p-6">
        {/* ========== ROLES & PERMISSIONS ========== */}
        {tab === "roles" && (
          <div className="max-w-5xl mx-auto space-y-4" data-testid="roles-tab">
            <div className="flex items-center justify-between">
              <div><h3 className="text-base font-bold text-stone-900">Roles & Permissions</h3><p className="text-xs text-stone-500">Define what each role can access across modules</p></div>
              <button onClick={() => setShowNewRole(true)} className="text-xs px-4 py-2 bg-[#2C4C3B] text-white rounded-xl font-bold hover:bg-[#1A3025] flex items-center gap-1" data-testid="new-role-btn"><Plus size={12} /> New Role</button>
            </div>

            {roles.map(role => (
              <div key={role.id} className="bg-white rounded-2xl border border-stone-200 overflow-hidden shadow-sm" data-testid={`role-${role.id}`}>
                <button onClick={() => setExpandedRole(expandedRole === role.id ? null : role.id)}
                  className="w-full px-5 py-4 flex items-center justify-between hover:bg-stone-50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${role.is_builtin ? "bg-stone-100" : "bg-[#2C4C3B]/10"}`}>
                      <Shield size={16} className={role.is_builtin ? "text-stone-600" : "text-[#2C4C3B]"} />
                    </div>
                    <div className="text-left">
                      <div className="text-sm font-bold text-stone-900 flex items-center gap-2">{role.name}
                        {role.is_builtin && <Badge className="text-[8px] bg-stone-100 text-stone-500">Built-in</Badge>}
                      </div>
                      <div className="text-[11px] text-stone-500">{role.description}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-stone-400">{Object.values(role.permissions || {}).flat().length} permissions</span>
                    {!role.is_builtin && <span role="button" tabIndex={0} onClick={(e) => { e.stopPropagation(); deleteRole(role.id); }} className="text-stone-300 hover:text-red-500 transition-colors cursor-pointer" data-testid={`delete-role-${role.id}`}><Trash2 size={14} /></span>}
                    {expandedRole === role.id ? <ChevronDown size={14} className="text-stone-400" /> : <ChevronRight size={14} className="text-stone-400" />}
                  </div>
                </button>
                {expandedRole === role.id && (
                  <div className="border-t border-stone-100 p-4">
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-stone-100">
                            <th className="text-left py-2 px-3 font-semibold text-stone-500 w-40">Module</th>
                            {actions.map(a => <th key={a} className="text-center py-2 px-2 font-semibold text-stone-500 w-20">{ACTION_LABELS[a]}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {modules.map(mod => {
                            const meta = MODULE_META[mod] || {};
                            const Icon = meta.icon || Settings;
                            const perms = role.permissions?.[mod] || [];
                            return (
                              <tr key={mod} className="border-b border-stone-50 hover:bg-stone-50">
                                <td className="py-2 px-3 flex items-center gap-2"><Icon size={12} style={{ color: meta.color }} /><span className="font-medium text-stone-700">{meta.label}</span></td>
                                {actions.map(a => (
                                  <td key={a} className="text-center py-2 px-2">
                                    <button onClick={() => !role.is_builtin && togglePermission(role.id, mod, a)}
                                      className={`w-6 h-6 rounded-md flex items-center justify-center mx-auto transition-all ${
                                        perms.includes(a) ? "bg-[#2C4C3B] text-white" : "bg-stone-100 text-stone-300 hover:bg-stone-200"
                                      } ${role.is_builtin ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}>
                                      {perms.includes(a) && <Check size={10} strokeWidth={3} />}
                                    </button>
                                  </td>
                                ))}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* New Role Dialog */}
            <Dialog open={showNewRole} onOpenChange={setShowNewRole}>
              <DialogContent className="max-w-md" data-testid="new-role-dialog">
                <DialogHeader><DialogTitle>Create Custom Role</DialogTitle></DialogHeader>
                <div className="space-y-3">
                  <Input value={newRole.name} onChange={e => setNewRole(p => ({...p, name: e.target.value, id: e.target.value.toLowerCase().replace(/\s+/g, "_")}))} placeholder="Role name (e.g. Night Auditor)" data-testid="role-name-input" />
                  <Input value={newRole.description} onChange={e => setNewRole(p => ({...p, description: e.target.value}))} placeholder="Description" />
                  <p className="text-[10px] text-stone-400">You can set permissions after creating the role.</p>
                  <button onClick={createRole} className="w-full bg-[#2C4C3B] text-white py-2.5 rounded-xl text-sm font-bold" data-testid="create-role-btn">Create Role</button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        )}

        {/* ========== TEAM MEMBERS ========== */}
        {tab === "users" && (
          <div className="max-w-5xl mx-auto space-y-4" data-testid="users-tab">
            <OrganizationsCard />
            <h3 className="text-base font-bold text-stone-900">Team Members</h3>
            <div className="space-y-2">
              {users.map(u => (
                <div key={u.id || u.email} className="bg-white rounded-2xl border border-stone-200 p-4 flex items-center justify-between shadow-sm" data-testid={`user-${u.id}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#2C4C3B] to-[#D4A373] flex items-center justify-center text-white text-sm font-bold">
                      {u.name?.charAt(0)?.toUpperCase() || "U"}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-stone-900">{u.name}</div>
                      <div className="text-[11px] text-stone-500">{u.email}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 flex-wrap justify-end">
                    <div className="flex items-center gap-1.5" title="WhatsApp bildirimleri (Sabah Karnesi, bordro) için E.164 formatı: +447700900123">
                      <Input defaultValue={u.phone || ""} placeholder="+44 7700 900123" data-testid={`phone-input-${u.id}`}
                        className="h-8 text-xs w-40 border-stone-200"
                        onBlur={e => { const v = e.target.value.trim(); if (v !== (u.phone || "")) saveUserField(u.id, { phone: v }); }} />
                      <label className="flex items-center gap-1 text-[10px] text-stone-500 whitespace-nowrap">
                        <Switch checked={u.karne_whatsapp !== false} onCheckedChange={v => saveUserField(u.id, { karne_whatsapp: v })} data-testid={`karne-wa-switch-${u.id}`} />
                        Karne WA
                      </label>
                    </div>
                    <PropertyRoleEditor u={u} onSaved={fetchUsers} />
                    <Select value={u.role} onValueChange={v => updateUserRole(u.id, v)}>
                      <SelectTrigger className="h-8 text-xs w-40 border-stone-200" data-testid={`role-select-${u.id}`}><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {roles.map(r => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Badge className={`text-[9px] font-bold ${u.role === "admin" ? "bg-red-100 text-red-700" : u.role === "manager" ? "bg-blue-100 text-blue-700" : "bg-stone-100 text-stone-600"}`}>{u.role}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ========== MODULE SETTINGS ========== */}
        {tab === "module-settings" && (
          <div className="max-w-4xl mx-auto space-y-4" data-testid="module-settings-tab">
            <h3 className="text-base font-bold text-stone-900">Module Settings</h3>
            <p className="text-xs text-stone-500">Configure settings for each module. Changes apply to the selected property.</p>
            <div className="space-y-3">
              {modules.filter(m => m !== "settings" && m !== "dashboard").map(mod => {
                const meta = MODULE_META[mod] || {};
                const Icon = meta.icon || Settings;
                const s = moduleSettings[mod] || {};
                const isOpen = editingModule === mod;
                return (
                  <div key={mod} className="bg-white rounded-2xl border border-stone-200 overflow-hidden shadow-sm" data-testid={`module-${mod}`}>
                    <button onClick={() => setEditingModule(isOpen ? null : mod)}
                      className="w-full px-5 py-4 flex items-center justify-between hover:bg-stone-50 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${meta.color}15` }}>
                          <Icon size={16} style={{ color: meta.color }} />
                        </div>
                        <span className="text-sm font-bold text-stone-900">{meta.label}</span>
                      </div>
                      {isOpen ? <ChevronDown size={14} className="text-stone-400" /> : <ChevronRight size={14} className="text-stone-400" />}
                    </button>
                    {isOpen && (
                      <div className="border-t border-stone-100 p-5 space-y-3">
                        {mod === "pos" && <POSSettings settings={s} onChange={v => setModuleSettings(p => ({...p, [mod]: {...p[mod], ...v}}))} />}
                        {mod === "bookings" && <BookingSettings settings={s} onChange={v => setModuleSettings(p => ({...p, [mod]: {...p[mod], ...v}}))} />}
                        {mod === "accounting" && <AccountingSettings settings={s} onChange={v => setModuleSettings(p => ({...p, [mod]: {...p[mod], ...v}}))} />}
                        {mod === "messaging" && <MessagingSettings settings={s} onChange={v => setModuleSettings(p => ({...p, [mod]: {...p[mod], ...v}}))} />}
                        {mod === "reviews" && <ReviewSettings settings={s} onChange={v => setModuleSettings(p => ({...p, [mod]: {...p[mod], ...v}}))} />}
                        {mod === "stock" && <StockSettings settings={s} onChange={v => setModuleSettings(p => ({...p, [mod]: {...p[mod], ...v}}))} />}
                        {mod === "surveys" && <SurveySettings settings={s} onChange={v => setModuleSettings(p => ({...p, [mod]: {...p[mod], ...v}}))} />}
                        {!["pos","bookings","accounting","messaging","reviews","stock","surveys"].includes(mod) && (
                          <p className="text-xs text-stone-400">Settings available for this module.</p>
                        )}
                        <button onClick={() => saveModuleSettings(mod)} className="px-4 py-2 bg-[#2C4C3B] text-white text-xs rounded-xl font-bold hover:bg-[#1A3025]" data-testid={`save-${mod}-settings`}>
                          <Save size={12} className="inline mr-1" /> Save {meta.label} Settings
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ========== SİSTEM SAĞLIĞI (iter 379) ========== */}
        {tab === "system-health" && <SystemHealthTab />}
        {tab === "certifications" && <CertificationGuideTab />}
        {tab === "matrix" && <PermissionMatrixCard />}

        {/* ========== PURCHASE ORDERS ========== */}
        {tab === "purchase-orders" && (
          <div className="max-w-5xl mx-auto space-y-4" data-testid="purchase-orders-tab">
            <div className="flex items-center justify-between">
              <div><h3 className="text-base font-bold text-stone-900">Auto Purchase Orders</h3><p className="text-xs text-stone-500">Auto-generate POs for items below reorder level</p></div>
              <button onClick={async () => {
                setGeneratingPO(true);
                try { const { data } = await axios.post(`${API}/admin/auto-purchase-orders/${propertyId}`); toast.success(data.message); fetchPOs(); }
                catch (e) { toast.error("Failed"); } finally { setGeneratingPO(false); }
              }} disabled={generatingPO}
                className="text-xs px-4 py-2 bg-[#2C4C3B] text-white rounded-xl font-bold hover:bg-[#1A3025] disabled:opacity-50 flex items-center gap-1" data-testid="generate-po-btn">
                <Truck size={12} /> {generatingPO ? "Generating..." : "Generate POs"}
              </button>
            </div>
            {purchaseOrders.length === 0 ? (
              <div className="bg-white rounded-2xl border border-stone-200 p-10 text-center"><Truck size={32} className="mx-auto text-stone-300 mb-3" /><p className="text-sm text-stone-500">No purchase orders yet</p><p className="text-xs text-stone-400 mt-1">Click "Generate POs" to auto-create orders for low stock items</p></div>
            ) : (
              <div className="space-y-3">
                {purchaseOrders.map(po => (
                  <div key={po.id} className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm" data-testid={`po-${po.id}`}>
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="text-sm font-bold text-stone-900">{po.po_number}</div>
                        <div className="text-[11px] text-stone-500">{po.supplier} · {po.total_items} items · £{po.total_cost?.toFixed(2)}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={`text-[9px] font-bold ${po.status === "received" ? "bg-emerald-100 text-emerald-700" : po.status === "approved" ? "bg-blue-100 text-blue-700" : po.status === "cancelled" ? "bg-red-100 text-red-600" : "bg-amber-100 text-amber-700"}`}>{po.status}</Badge>
                        {po.status === "draft" && (
                          <button onClick={async () => { await axios.put(`${API}/admin/purchase-orders/${po.id}/status`, { status: "approved" }); fetchPOs(); toast.success("PO approved"); }}
                            className="text-[10px] px-2 py-1 bg-blue-50 text-blue-700 rounded-lg font-bold hover:bg-blue-100" data-testid={`approve-${po.id}`}>Approve</button>
                        )}
                        {po.status === "approved" && (
                          <button onClick={async () => { await axios.put(`${API}/admin/purchase-orders/${po.id}/status`, { status: "received" }); fetchPOs(); toast.success("Stock received & updated!"); }}
                            className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-700 rounded-lg font-bold hover:bg-emerald-100" data-testid={`receive-${po.id}`}>Mark Received</button>
                        )}
                      </div>
                    </div>
                    <div className="space-y-1">
                      {po.items?.map((item, i) => (
                        <div key={i} className="flex items-center justify-between text-xs bg-stone-50 rounded-lg px-3 py-2">
                          <span className="font-medium text-stone-700">{item.product_name}</span>
                          <div className="flex items-center gap-3 text-stone-500">
                            <span>Stock: {item.current_stock}</span>
                            <span className="font-bold text-[#2C4C3B]">Order: {item.quantity_to_order} {item.unit}</span>
                            <span>£{item.estimated_cost?.toFixed(2)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ==================== MODULE SETTINGS COMPONENTS ====================

const SettingRow = ({ label, description, children }) => (
  <div className="flex items-start justify-between gap-4 py-2">
    <div className="flex-1"><div className="text-xs font-semibold text-stone-700">{label}</div>{description && <div className="text-[10px] text-stone-400 mt-0.5">{description}</div>}</div>
    <div className="flex-shrink-0">{children}</div>
  </div>
);

const POSSettings = ({ settings: s, onChange }) => (
  <div className="space-y-1 divide-y divide-stone-100">
    <SettingRow label="Tax Rate (%)" description="Default VAT/tax rate for POS items"><Input type="number" value={s.tax_rate || 20} onChange={e => onChange({ tax_rate: parseFloat(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Service Charge (%)" description="Automatic service charge added to orders"><Input type="number" value={s.service_charge_pct || 0} onChange={e => onChange({ service_charge_pct: parseFloat(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Max Discount (%)" description="Maximum discount staff can apply"><Input type="number" value={s.max_discount_pct || 50} onChange={e => onChange({ max_discount_pct: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Allow Discounts"><Switch checked={s.allow_discounts !== false} onCheckedChange={v => onChange({ allow_discounts: v })} /></SettingRow>
    <SettingRow label="Kitchen Display"><Switch checked={s.kitchen_display_enabled !== false} onCheckedChange={v => onChange({ kitchen_display_enabled: v })} /></SettingRow>
    <SettingRow label="Auto-Print Receipt"><Switch checked={s.auto_print_receipt} onCheckedChange={v => onChange({ auto_print_receipt: v })} /></SettingRow>
    <SettingRow label="Require Table Number"><Switch checked={s.require_table_number} onCheckedChange={v => onChange({ require_table_number: v })} /></SettingRow>
    <SettingRow label="Receipt Header"><Input value={s.receipt_header || ""} onChange={e => onChange({ receipt_header: e.target.value })} placeholder="Header text" className="h-8 w-48 text-xs" /></SettingRow>
    <SettingRow label="Receipt Footer"><Input value={s.receipt_footer || ""} onChange={e => onChange({ receipt_footer: e.target.value })} placeholder="Footer text" className="h-8 w-48 text-xs" /></SettingRow>
    <SettingRow label="Order Prefix"><Input value={s.order_numbering_prefix || "POS"} onChange={e => onChange({ order_numbering_prefix: e.target.value })} className="h-8 w-24 text-xs" /></SettingRow>
  </div>
);

const BookingSettings = ({ settings: s, onChange }) => (
  <div className="space-y-1 divide-y divide-stone-100">
    <SettingRow label="Check-in Time"><Input value={s.check_in_time || "15:00"} onChange={e => onChange({ check_in_time: e.target.value })} className="h-8 w-24 text-xs" type="time" /></SettingRow>
    <SettingRow label="Check-out Time"><Input value={s.check_out_time || "11:00"} onChange={e => onChange({ check_out_time: e.target.value })} className="h-8 w-24 text-xs" type="time" /></SettingRow>
    <SettingRow label="Cancellation Window (hours)" description="Hours before check-in guest can cancel free"><Input type="number" value={s.cancellation_hours || 24} onChange={e => onChange({ cancellation_hours: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Deposit (%)" description="Deposit required at booking"><Input type="number" value={s.deposit_pct || 0} onChange={e => onChange({ deposit_pct: parseFloat(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Overbooking Buffer" description="Extra rooms allowed beyond capacity"><Input type="number" value={s.overbooking_buffer || 0} onChange={e => onChange({ overbooking_buffer: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Min Stay (nights)"><Input type="number" value={s.min_stay || 1} onChange={e => onChange({ min_stay: parseInt(e.target.value) || 1 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Auto-Confirm Bookings"><Switch checked={s.auto_confirm !== false} onCheckedChange={v => onChange({ auto_confirm: v })} /></SettingRow>
    <SettingRow label="Send Confirmation Email"><Switch checked={s.send_confirmation_email !== false} onCheckedChange={v => onChange({ send_confirmation_email: v })} /></SettingRow>
    <SettingRow label="Pre-Arrival Email (hours before)"><Input type="number" value={s.pre_arrival_hours || 24} onChange={e => onChange({ pre_arrival_hours: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
  </div>
);

const AccountingSettings = ({ settings: s, onChange }) => (
  <div className="space-y-1 divide-y divide-stone-100">
    <SettingRow label="Financial Year Start"><Input value={s.financial_year_start || "01-01"} onChange={e => onChange({ financial_year_start: e.target.value })} placeholder="MM-DD" className="h-8 w-24 text-xs" /></SettingRow>
    <SettingRow label="Default Currency"><Select value={s.default_currency || "GBP"} onValueChange={v => onChange({ default_currency: v })}><SelectTrigger className="h-8 w-24 text-xs"><SelectValue /></SelectTrigger><SelectContent>{["GBP","USD","EUR","TRY","AED"].map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></SettingRow>
    <SettingRow label="Tax Rate (%)"><Input type="number" value={s.tax_rate || 20} onChange={e => onChange({ tax_rate: parseFloat(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Auto-Post POS Sales" description="Automatically create income entries from POS"><Switch checked={s.auto_post_pos !== false} onCheckedChange={v => onChange({ auto_post_pos: v })} /></SettingRow>
    <SettingRow label="Auto-Post Bookings" description="Automatically create income entries from bookings"><Switch checked={s.auto_post_bookings !== false} onCheckedChange={v => onChange({ auto_post_bookings: v })} /></SettingRow>
    <SettingRow label="Invoice Prefix"><Input value={s.invoice_prefix || "INV"} onChange={e => onChange({ invoice_prefix: e.target.value })} className="h-8 w-24 text-xs" /></SettingRow>
    <SettingRow label="Invoice Due Days"><Input type="number" value={s.invoice_due_days || 30} onChange={e => onChange({ invoice_due_days: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
  </div>
);

const MessagingSettings = ({ settings: s, onChange }) => (
  <div className="space-y-1 divide-y divide-stone-100">
    <SettingRow label="Auto-Reply" description="Send automatic reply outside business hours"><Switch checked={s.auto_reply_enabled} onCheckedChange={v => onChange({ auto_reply_enabled: v })} /></SettingRow>
    <SettingRow label="Auto-Reply Message"><Input value={s.auto_reply_message || ""} onChange={e => onChange({ auto_reply_message: e.target.value })} className="h-8 w-64 text-xs" /></SettingRow>
    <SettingRow label="Business Hours Start"><Input value={s.business_hours_start || "08:00"} onChange={e => onChange({ business_hours_start: e.target.value })} type="time" className="h-8 w-28 text-xs" /></SettingRow>
    <SettingRow label="Business Hours End"><Input value={s.business_hours_end || "22:00"} onChange={e => onChange({ business_hours_end: e.target.value })} type="time" className="h-8 w-28 text-xs" /></SettingRow>
    <SettingRow label="Response Target (minutes)"><Input type="number" value={s.response_time_target_minutes || 15} onChange={e => onChange({ response_time_target_minutes: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Auto-Translate Messages"><Switch checked={s.auto_translate} onCheckedChange={v => onChange({ auto_translate: v })} /></SettingRow>
  </div>
);

const ReviewSettings = ({ settings: s, onChange }) => (
  <div className="space-y-1 divide-y divide-stone-100">
    <SettingRow label="Auto-Respond to Reviews"><Switch checked={s.auto_respond} onCheckedChange={v => onChange({ auto_respond: v })} /></SettingRow>
    <SettingRow label="Review Request Delay (hours)" description="Wait time after checkout before requesting review"><Input type="number" value={s.review_request_delay_hours || 24} onChange={e => onChange({ review_request_delay_hours: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Low Rating Alert" description="Alert when review rating is at or below"><Input type="number" value={s.minimum_rating_alert || 3} onChange={e => onChange({ minimum_rating_alert: parseInt(e.target.value) || 1 })} className="h-8 w-20 text-xs" min={1} max={5} /></SettingRow>
    <SettingRow label="Request Review on Checkout"><Switch checked={s.request_review_on_checkout !== false} onCheckedChange={v => onChange({ request_review_on_checkout: v })} /></SettingRow>
  </div>
);

const StockSettings = ({ settings: s, onChange }) => (
  <div className="space-y-1 divide-y divide-stone-100">
    <SettingRow label="Low Stock Alerts"><Switch checked={s.low_stock_alert_enabled !== false} onCheckedChange={v => onChange({ low_stock_alert_enabled: v })} /></SettingRow>
    <SettingRow label="Auto-Reorder" description="Automatically generate purchase orders"><Switch checked={s.auto_reorder_enabled} onCheckedChange={v => onChange({ auto_reorder_enabled: v })} /></SettingRow>
    <SettingRow label="Wastage Tracking"><Switch checked={s.wastage_tracking !== false} onCheckedChange={v => onChange({ wastage_tracking: v })} /></SettingRow>
    <SettingRow label="Default Par Level"><Input type="number" value={s.default_par_level || 30} onChange={e => onChange({ default_par_level: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Default Reorder Level"><Input type="number" value={s.default_reorder_level || 5} onChange={e => onChange({ default_reorder_level: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Stock Count Frequency"><Select value={s.stock_count_frequency || "weekly"} onValueChange={v => onChange({ stock_count_frequency: v })}><SelectTrigger className="h-8 w-28 text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="daily">Daily</SelectItem><SelectItem value="weekly">Weekly</SelectItem><SelectItem value="monthly">Monthly</SelectItem></SelectContent></Select></SettingRow>
  </div>
);

const SurveySettings = ({ settings: s, onChange }) => (
  <div className="space-y-1 divide-y divide-stone-100">
    <SettingRow label="Auto-Send on Checkout"><Switch checked={s.auto_send_on_checkout} onCheckedChange={v => onChange({ auto_send_on_checkout: v })} /></SettingRow>
    <SettingRow label="Send Delay (hours)" description="Wait after checkout before sending survey"><Input type="number" value={s.send_delay_hours || 2} onChange={e => onChange({ send_delay_hours: parseInt(e.target.value) || 0 })} className="h-8 w-20 text-xs" /></SettingRow>
    <SettingRow label="Send Reminder"><Switch checked={s.reminder_enabled} onCheckedChange={v => onChange({ reminder_enabled: v })} /></SettingRow>
    <SettingRow label="Allow Anonymous"><Switch checked={s.anonymous_allowed !== false} onCheckedChange={v => onChange({ anonymous_allowed: v })} /></SettingRow>
  </div>
);

/* ========== Sistem Sağlığı Sekmesi (iter 379) ========== */
const SystemHealthTab = () => {
  const [health, setHealth] = useState(null);
  const [tasks, setTasks] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [h, t] = await Promise.all([
        axios.get(`${API}/health`),
        axios.get(`${API}/admin/diagnostics/tasks`),
      ]);
      setHealth(h.data);
      setTasks(t.data);
    } catch (e) { toast.error("Sağlık verisi alınamadı"); }
    setRefreshing(false);
  }, []);
  useEffect(() => { load(); }, [load]);

  const taskCount = tasks?.total_tasks ?? 0;
  const taskStatus = taskCount < 100 ? { label: "Sağlıklı", cls: "bg-emerald-50 text-emerald-700 border-emerald-200" }
    : taskCount < 500 ? { label: "Yüksek", cls: "bg-amber-50 text-amber-700 border-amber-200" }
    : { label: "Kritik", cls: "bg-red-50 text-red-700 border-red-200" };

  return (
    <div className="max-w-4xl mx-auto space-y-4" data-testid="system-health-tab">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-stone-900">Sistem Sağlığı</h3>
          <p className="text-xs text-stone-500">Backend durumu ve asyncio görev envanteri — anormal artış performans sorununun erken işaretidir</p>
        </div>
        <button onClick={load} disabled={refreshing} data-testid="health-refresh-btn"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-stone-200 rounded-lg hover:bg-stone-50 disabled:opacity-50">
          <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} /> Yenile
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="health-status-card">
          <div className="text-xs text-stone-500 mb-1">Backend</div>
          <div className={`text-lg font-bold ${health?.status === "ok" ? "text-emerald-600" : "text-red-600"}`}>
            {health?.status === "ok" ? "● Çalışıyor" : "● Sorun"}
          </div>
          <div className="text-[10px] text-stone-400 mt-1">v{health?.version || "-"} · uptime {Math.floor((health?.uptime_sec || 0) / 60)} dk</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="health-tasks-card">
          <div className="text-xs text-stone-500 mb-1">Aktif Görev Sayısı</div>
          <div className="text-lg font-bold text-stone-900">{taskCount}</div>
          <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${taskStatus.cls}`}>{taskStatus.label}</span>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-4">
          <div className="text-xs text-stone-500 mb-1">Farklı Görev Tipi</div>
          <div className="text-lg font-bold text-stone-900">{tasks ? Object.keys(tasks.by_coro || {}).length : "-"}</div>
          <div className="text-[10px] text-stone-400 mt-1">arkaplan worker + istek görevleri</div>
        </div>
      </div>

      {tasks && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 bg-stone-50 text-xs font-semibold text-stone-600 border-b border-stone-200">Görev Dağılımı</div>
          <div className="divide-y divide-stone-100">
            {Object.entries(tasks.by_coro || {}).slice(0, 15).map(([name, count]) => (
              <div key={name} className="flex items-center justify-between px-4 py-2 text-xs">
                <span className="font-mono text-stone-600 truncate mr-4">{name}</span>
                <span className={`font-bold ${count > 50 ? "text-red-600" : "text-stone-800"}`}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};


function OrganizationsCard() {
  const [orgs, setOrgs] = useState([]);
  const [form, setForm] = useState({ name: "", allowed_domains: "", google_hd: "", ms_tid: "", default_role: "receptionist" });
  const load = async () => { try { const r = await axios.get(`${API}/orgs`); setOrgs(r.data.items || []); } catch { setOrgs([]); } };
  useEffect(() => { load(); }, []);
  const create = async () => {
    if (!form.name.trim()) return toast.error("Organizasyon adı gerekli");
    try {
      await axios.post(`${API}/orgs`, { ...form, allowed_domains: form.allowed_domains.split(",").map(x => x.trim()).filter(Boolean), sso_provider: form.google_hd ? "google" : form.ms_tid ? "microsoft" : "" });
      toast.success("Organizasyon oluşturuldu"); setForm({ name: "", allowed_domains: "", google_hd: "", ms_tid: "", default_role: "receptionist" }); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Oluşturulamadı"); }
  };
  return (
    <div className="bg-white rounded-2xl border border-stone-200 p-4 mb-4" data-testid="organizations-card">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
        <h3 className="font-semibold text-stone-800">🏢 Organizasyonlar (tenant) & SSO</h3>
        <span className="text-[11px] text-stone-400">E-posta alanı / Workspace hd / Entra tenant → otomatik kullanıcı açma; tesise özel roller kullanıcı satırından</span>
      </div>
      <div className="grid md:grid-cols-6 gap-2 text-xs">
        <Input placeholder="Ad" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} data-testid="org-name-input" className="h-8 text-xs" />
        <Input placeholder="İzinli alanlar (virgül)" value={form.allowed_domains} onChange={e => setForm({ ...form, allowed_domains: e.target.value })} data-testid="org-domains-input" className="h-8 text-xs" />
        <Input placeholder="Google hd (ör. otel.com)" value={form.google_hd} onChange={e => setForm({ ...form, google_hd: e.target.value })} data-testid="org-hd-input" className="h-8 text-xs" />
        <Input placeholder="Entra tenant id" value={form.ms_tid} onChange={e => setForm({ ...form, ms_tid: e.target.value })} data-testid="org-tid-input" className="h-8 text-xs" />
        <select value={form.default_role} onChange={e => setForm({ ...form, default_role: e.target.value })} data-testid="org-role-select" className="h-8 text-xs border border-stone-200 rounded-md px-2">
          {["receptionist", "manager", "housekeeper", "staff", "viewer"].map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <button onClick={create} data-testid="org-create-btn" className="h-8 rounded-md bg-stone-900 text-white text-xs px-3">Oluştur</button>
      </div>
      <div className="mt-3 divide-y divide-stone-100">
        {orgs.length === 0 && <p className="text-xs text-stone-400">Henüz organizasyon yok — tek tesisli kurulumlarda gerekmez.</p>}
        {orgs.map(o => (
          <div key={o.id} className="py-1.5 flex items-center justify-between text-xs" data-testid={`org-row-${o.id}`}>
            <span className="font-medium text-stone-800">{o.name} <span className="text-stone-400">· {(o.allowed_domains || []).join(", ") || "alan yok"}{o.sso?.google_hd ? ` · Google ${o.sso.google_hd}` : ""}{o.sso?.ms_tid ? " · Entra" : ""}</span></span>
            <span className="text-stone-500">{o.property_count} tesis · {o.user_count} kullanıcı · varsayılan rol {o.sso?.default_role}</span>
          </div>
        ))}
      </div>
    </div>
  );
}


function PropertyRoleEditor({ u, onSaved }) {
  const [open, setOpen] = useState(false);
  const [props, setProps] = useState([]);
  const [pid, setPid] = useState("");
  const [role, setRole] = useState("manager");
  const pr = u.property_roles || {};
  useEffect(() => { if (open && props.length === 0) axios.get(`${API}/properties`).then(r => setProps(Array.isArray(r.data) ? r.data : (r.data.properties || r.data.items || []))).catch(() => {}); }, [open, props.length]);
  const save = async (next) => {
    try { await axios.put(`${API}/orgs/users/${u.id}/property-roles`, { property_roles: next }); toast.success("Tesis rolleri kaydedildi"); onSaved(); }
    catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };
  const n = Object.keys(pr).length;
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} data-testid={`prop-roles-btn-${u.id}`}
        className={`h-8 px-2 rounded-lg border text-[11px] ${n ? "border-emerald-300 bg-emerald-50 text-emerald-800" : "border-stone-200 text-stone-500"}`}>
        Tesis rolleri{n ? ` (${n})` : ""}
      </button>
      {open && (
        <div className="absolute right-0 top-9 z-20 w-80 bg-white border border-stone-200 rounded-xl shadow-lg p-3 text-xs" data-testid={`prop-roles-popover-${u.id}`}>
          <div className="font-semibold text-stone-800 mb-1">Tesise özel roller</div>
          <p className="text-[10px] text-stone-400 mb-2">Etkin rol: tesis rolü varsa o, yoksa genel rol (<b>{u.role}</b>).</p>
          {Object.entries(pr).map(([p, r]) => (
            <div key={p} className="flex items-center justify-between py-1 border-b border-stone-100" data-testid={`prop-role-row-${u.id}-${p}`}>
              <span>{props.find(x => x.id === p)?.name || p} → <b>{r}</b> <span className="text-stone-400">(etkin)</span></span>
              <button onClick={() => { const next = { ...pr }; delete next[p]; save(next); }} className="text-red-600">kaldır</button>
            </div>
          ))}
          <div className="flex gap-1 mt-2">
            <select value={pid} onChange={e => setPid(e.target.value)} data-testid={`prop-role-pid-${u.id}`} className="flex-1 h-7 border border-stone-200 rounded px-1">
              <option value="">Tesis seç…</option>
              {props.map(p => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
            </select>
            <select value={role} onChange={e => setRole(e.target.value)} data-testid={`prop-role-role-${u.id}`} className="h-7 border border-stone-200 rounded px-1">
              {["admin", "manager", "receptionist", "housekeeper", "staff", "viewer"].map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <button disabled={!pid} onClick={() => save({ ...pr, [pid]: role })} data-testid={`prop-role-add-${u.id}`} className="h-7 px-2 rounded bg-stone-900 text-white disabled:opacity-40">Ekle</button>
          </div>
          {pid && <p className="text-[10px] text-emerald-700 mt-1.5" data-testid={`prop-role-preview-${u.id}`}>Önizleme: {props.find(x => x.id === pid)?.name || pid} tesisinde etkin rol → <b>{role}</b></p>}
        </div>
      )}
    </div>
  );
}

function CertificationGuideTab() {
  const [g, setG] = useState(null);
  const [openId, setOpenId] = useState("");
  useEffect(() => { axios.get(`${API}/certifications/guide`).then(r => setG(r.data)).catch(() => setG(null)); }, []);
  if (!g) return <div className="p-6 text-sm text-stone-400">Yükleniyor…</div>;
  return (
    <div className="max-w-4xl mx-auto space-y-3" data-testid="certification-guide">
      <div className="bg-white rounded-2xl border border-stone-200 p-4">
        <div className="flex items-center justify-between"><h3 className="font-semibold text-stone-800">Canlıya Geçiş Rehberi — sertifika & anahtar checklist</h3>
          <span className="text-sm font-bold text-emerald-700" data-testid="cert-progress">{g.done}/{g.total} · %{g.progress_pct}</span></div>
        <div className="h-2 bg-stone-100 rounded-full mt-2"><div className="h-2 bg-emerald-600 rounded-full" style={{ width: `${g.progress_pct}%` }} /></div>
        <p className="text-[11px] text-stone-400 mt-2">Kod tarafı hazır; her madde bir dış başvuru/anahtar gerektirir. Anahtar geldiğinde backend .env'e eklenir ve durum otomatik ✓ olur.</p>
      </div>
      {g.items.map(it => (
        <div key={it.id} className={`bg-white rounded-2xl border p-4 ${it.done ? "border-emerald-200" : "border-stone-200"}`} data-testid={`cert-item-${it.id}`}>
          <button className="w-full flex items-center justify-between text-left" onClick={() => setOpenId(openId === it.id ? "" : it.id)} data-testid={`cert-toggle-${it.id}`}>
            <span className="font-medium text-stone-800">{it.done ? "✅" : "⬜"} {it.title} <span className="text-[11px] text-stone-400">· {it.eta}</span></span>
            <span className="text-xs text-stone-400">{openId === it.id ? "▲" : "▼"}</span>
          </button>
          {openId === it.id && (
            <div className="mt-3 text-xs text-stone-600 space-y-1">
              <ol className="list-decimal ml-4 space-y-1">{it.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              <p className="text-[11px] text-stone-400 mt-2">ENV: {it.env.join(", ")}{it.note ? ` · ${it.note}` : ""}</p>
              <a href={it.url} target="_blank" rel="noreferrer" className="text-[11px] text-sky-700 underline">Başvuru sayfası ↗</a>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
