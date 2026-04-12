import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Shield, Users, Settings, Plus, Trash2, Save, ChevronDown, ChevronRight, Check, X, Package, FileText, ShoppingCart, CreditCard, BarChart3, MessageSquare, Star, UserCheck, Zap, LayoutDashboard, ClipboardList, Truck } from "lucide-react";

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
                    {!role.is_builtin && <button onClick={(e) => { e.stopPropagation(); deleteRole(role.id); }} className="text-stone-300 hover:text-red-500 transition-colors"><Trash2 size={14} /></button>}
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
            <h3 className="text-base font-bold text-stone-900">Team Members</h3>
            <div className="space-y-2">
              {users.map(u => (
                <div key={u.id} className="bg-white rounded-2xl border border-stone-200 p-4 flex items-center justify-between shadow-sm" data-testid={`user-${u.id}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#2C4C3B] to-[#D4A373] flex items-center justify-center text-white text-sm font-bold">
                      {u.name?.charAt(0)?.toUpperCase() || "U"}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-stone-900">{u.name}</div>
                      <div className="text-[11px] text-stone-500">{u.email}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
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
