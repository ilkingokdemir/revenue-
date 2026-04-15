import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const roleColors = { admin: "bg-red-50 text-red-700", manager: "bg-blue-50 text-blue-700", receptionist: "bg-emerald-50 text-emerald-700", housekeeper: "bg-violet-50 text-violet-700", maintenance: "bg-amber-50 text-amber-700" };

/* ── USER TABLE ── */
const UsersTab = ({ properties }) => {
  const [users, setUsers] = useState([]);
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "receptionist", department: "front_desk", property_access: [], branch_payments: {}, color: "#3b82f6" });

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/admin/users`); setUsers(data); } catch { toast.error("Failed to load users"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = users.filter(u => (!roleFilter || u.role === roleFilter) && (!search || u.name?.toLowerCase().includes(search.toLowerCase()) || u.email?.toLowerCase().includes(search.toLowerCase())));

  const createUser = async () => {
    if (!form.name || !form.email || !form.password) { toast.error("Name, email and password required"); return; }
    try {
      await axios.post(`${API}/auth/register`, { name: form.name, email: form.email, password: form.password, role: form.role, department: form.department });
      toast.success("User created");
      // Update branch_payments if set
      const newUsers = await axios.get(`${API}/admin/users`);
      const created = newUsers.data.find(u => u.email === form.email.toLowerCase());
      if (created && (Object.keys(form.branch_payments).length > 0 || form.property_access.length > 0)) {
        await axios.put(`${API}/admin/users/${created.id}/permissions`, {
          property_access: form.property_access, branch_payments: form.branch_payments, color: form.color,
        });
      }
      setShowCreate(false);
      setForm({ name: "", email: "", password: "", role: "receptionist", department: "front_desk", property_access: [], branch_payments: {}, color: "#3b82f6" });
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  const saveEdit = async () => {
    if (!editUser) return;
    try {
      await axios.put(`${API}/admin/users/${editUser.id}/permissions`, {
        name: form.name, role: form.role, department: form.department,
        property_access: form.property_access, branch_payments: form.branch_payments, color: form.color,
      });
      toast.success("User updated"); setEditUser(null); load();
    } catch { toast.error("Failed"); }
  };

  const openEdit = (u) => {
    setForm({
      name: u.name || "", email: u.email || "", password: "", role: u.role || "receptionist",
      department: u.department || "front_desk", property_access: u.property_access || [],
      branch_payments: u.branch_payments || {}, color: u.color || "#3b82f6",
    });
    setEditUser(u);
  };

  const deleteUser = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    try { await axios.delete(`${API}/users/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };

  const toggleBranch = (pid) => {
    const access = [...(form.property_access || [])];
    if (access.includes(pid)) {
      setForm({ ...form, property_access: access.filter(p => p !== pid) });
    } else {
      setForm({ ...form, property_access: [...access, pid] });
    }
  };

  const setBranchPay = (pid, field, val) => {
    const bp = { ...(form.branch_payments || {}) };
    bp[pid] = { ...(bp[pid] || { type: "daily", rate: 0 }), [field]: field === "rate" ? parseFloat(val) || 0 : val };
    setForm({ ...form, branch_payments: bp });
  };

  const UserFormDialog = ({ isEdit }) => (
    <Dialog open={isEdit ? !!editUser : showCreate} onOpenChange={isEdit ? () => setEditUser(null) : setShowCreate}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid={isEdit ? "edit-user-dialog" : "create-user-dialog"}>
        <DialogHeader><DialogTitle>{isEdit ? `Edit: ${form.name}` : "Create New User"}</DialogTitle></DialogHeader>
        <div className="space-y-5 mt-3">
          <div>
            <h4 className="text-sm font-bold text-stone-700 mb-3 flex items-center gap-2"><svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"/></svg>Account</h4>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-stone-500 mb-1 block">Display Name</label>
                <Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="John Doe" data-testid="user-form-name" /></div>
              <div><label className="text-xs text-stone-500 mb-1 block">Email</label>
                <Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder="john@example.com" disabled={isEdit} data-testid="user-form-email" /></div>
            </div>
            <div className="grid grid-cols-3 gap-3 mt-3">
              <div><label className="text-xs text-stone-500 mb-1 block">Color (for shifts)</label>
                <div className="flex items-center gap-2">
                  <input type="color" value={form.color} onChange={e => setForm({...form, color: e.target.value})} className="w-8 h-8 rounded border-0 cursor-pointer" data-testid="user-form-color" />
                  <span className="text-xs text-stone-400">{form.color}</span>
                </div></div>
              <div><label className="text-xs text-stone-500 mb-1 block">Role</label>
                <Select value={form.role} onValueChange={v => setForm({...form, role: v})}>
                  <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Admin</SelectItem><SelectItem value="manager">Manager</SelectItem>
                    <SelectItem value="receptionist">Receptionist</SelectItem><SelectItem value="housekeeper">Housekeeper</SelectItem>
                    <SelectItem value="maintenance">Maintenance</SelectItem>
                  </SelectContent>
                </Select></div>
              <div><label className="text-xs text-stone-500 mb-1 block">Department</label>
                <Select value={form.department} onValueChange={v => setForm({...form, department: v})}>
                  <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="front_desk">Front Desk</SelectItem><SelectItem value="management">Management</SelectItem>
                    <SelectItem value="housekeeping">Housekeeping</SelectItem><SelectItem value="maintenance">Maintenance</SelectItem>
                    <SelectItem value="food_beverage">Food & Beverage</SelectItem>
                  </SelectContent>
                </Select></div>
            </div>
            {!isEdit && <div className="mt-3"><label className="text-xs text-stone-500 mb-1 block">Password</label>
              <Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} placeholder="Min 6 characters" data-testid="user-form-password" /></div>}
          </div>

          <div className="border-t pt-4">
            <h4 className="text-sm font-bold text-stone-700 mb-3 flex items-center gap-2"><svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a1 1 0 110 2h-3a1 1 0 01-1-1v-2a1 1 0 00-1-1H9a1 1 0 00-1 1v2a1 1 0 01-1 1H4a1 1 0 110-2V4z"/></svg>Branches & Payment</h4>
            <div className="space-y-2">
              {properties.map(p => {
                const isSelected = (form.property_access || []).includes(p.id);
                const bp = (form.branch_payments || {})[p.id] || {};
                return (
                  <div key={p.id} className={`border rounded-lg p-3 transition-all ${isSelected ? "border-blue-300 bg-blue-50/30" : "border-stone-200"}`} data-testid={`branch-row-${p.id}`}>
                    <div className="flex items-center justify-between">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked={isSelected} onChange={() => toggleBranch(p.id)} className="rounded border-stone-300" data-testid={`branch-check-${p.id}`} />
                        <span className="text-sm font-medium text-stone-700">{p.name}</span>
                      </label>
                      {isSelected && (
                        <div className="flex items-center gap-2">
                          <Select value={bp.type || "daily"} onValueChange={v => setBranchPay(p.id, "type", v)}>
                            <SelectTrigger className="w-24 h-8 text-xs"><SelectValue /></SelectTrigger>
                            <SelectContent><SelectItem value="daily">Daily</SelectItem><SelectItem value="hourly">Hourly</SelectItem></SelectContent>
                          </Select>
                          <div className="flex items-center gap-1"><span className="text-xs text-stone-400">£</span>
                            <Input type="number" value={bp.rate || 0} onChange={e => setBranchPay(p.id, "rate", e.target.value)} className="w-20 h-8 text-xs" data-testid={`pay-rate-${p.id}`} />
                            <span className="text-[10px] text-stone-400">/{bp.type === "hourly" ? "hr" : "day"}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <button onClick={isEdit ? saveEdit : createUser} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700" data-testid="user-form-save">
            {isEdit ? "Save Changes" : "Create User"}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );

  return (
    <div data-testid="staff-users-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">User Management</h2><p className="text-sm text-stone-500">Manage system users and their permissions</p></div>
        <button onClick={() => { setForm({ name: "", email: "", password: "", role: "receptionist", department: "front_desk", property_access: [], branch_payments: {}, color: "#3b82f6" }); setShowCreate(true); }}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="add-user-btn">+ Add User</button>
      </div>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-1 text-xs font-medium text-stone-500">
          FILTER BY ROLE
          {["", "admin", "housekeeper", "maintenance", "receptionist"].map(r => (
            <button key={r} onClick={() => setRoleFilter(r)}
              className={`px-2.5 py-1 rounded-md ${roleFilter === r ? "bg-blue-500 text-white" : "text-stone-500 hover:bg-stone-100"}`} data-testid={`user-role-filter-${r || "all"}`}>{r || "All"}</button>
          ))}
        </div>
        <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search users..." className="w-48 h-8 text-xs ml-auto" data-testid="user-search" />
      </div>

      <div className="border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-stone-50 border-b">
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">User</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Email</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Roles</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Branches</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Payment</th>
            <th className="px-4 py-2.5 text-right text-xs font-semibold text-stone-500 uppercase">Actions</th>
          </tr></thead>
          <tbody>{filtered.length === 0 ? (
            <tr><td colSpan={6} className="text-center py-12 text-stone-400 text-sm">No users found</td></tr>
          ) : filtered.map(u => (
            <tr key={u.id || u.email} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`user-row-${u.id}`}>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold" style={{ backgroundColor: u.color || "#6b7280" }}>
                    {(u.name || "?")[0]?.toUpperCase()}
                  </div>
                  <span className="font-medium text-stone-800">{u.name}</span>
                </div>
              </td>
              <td className="px-4 py-3 text-stone-500 text-xs">{u.email}</td>
              <td className="px-4 py-3"><Badge className={`text-[10px] ${roleColors[u.role] || "bg-stone-100 text-stone-600"}`}>{u.role}</Badge></td>
              <td className="px-4 py-3">
                {(u.property_access || []).length > 0 ? (
                  <div className="flex flex-wrap gap-1">{u.property_access.map(pid => {
                    const p = properties.find(pr => pr.id === pid);
                    return <span key={pid} className="text-[10px] bg-stone-100 text-stone-600 px-1.5 py-0.5 rounded">{p?.name || pid}</span>;
                  })}</div>
                ) : <span className="text-xs text-stone-400">All</span>}
              </td>
              <td className="px-4 py-3">
                {u.branch_payments && Object.keys(u.branch_payments).length > 0 ? (
                  <div className="space-y-1">{Object.entries(u.branch_payments).map(([pid, bp]) => {
                    const p = properties.find(pr => pr.id === pid);
                    return <div key={pid} className="text-[10px]"><span className="font-medium text-stone-600">{p?.name?.split(" ")[0] || pid}</span> <Badge className="text-[8px] bg-blue-50 text-blue-600 capitalize">{bp.type || "Daily"}</Badge> £{bp.rate || 0}/{bp.type === "hourly" ? "hr" : "day"}</div>;
                  })}</div>
                ) : <span className="text-xs text-stone-400">—</span>}
              </td>
              <td className="px-4 py-3 text-right">
                <button onClick={() => openEdit(u)} className="text-xs text-blue-600 hover:underline mr-2" data-testid={`edit-user-${u.id}`}>Edit</button>
                <button onClick={() => deleteUser(u.id)} className="text-xs text-red-500 hover:underline" data-testid={`delete-user-${u.id}`}>Delete</button>
              </td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="text-xs text-stone-400 mt-2">Showing {filtered.length} of {users.length} users</p>

      <UserFormDialog isEdit={false} />
      <UserFormDialog isEdit={true} />
    </div>
  );
};

/* ── MY SHIFTS (Staff Self-Service) ── */
const MyShiftsTab = ({ user }) => {
  const [shifts, setShifts] = useState([]);
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - d.getDay() + 1);
    return d.toISOString().split("T")[0];
  });

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/admin/my-shifts?week_start=${weekStart}`); setShifts(data); } catch { /* silent */ }
  }, [weekStart]);
  useEffect(() => { load(); }, [load]);

  const navWeek = (dir) => {
    const d = new Date(weekStart + "T00:00:00");
    d.setDate(d.getDate() + (dir * 7));
    setWeekStart(d.toISOString().split("T")[0]);
  };

  const getDays = () => {
    const days = [];
    const start = new Date(weekStart + "T00:00:00");
    for (let i = 0; i < 7; i++) {
      const d = new Date(start); d.setDate(start.getDate() + i);
      days.push({ date: d.toISOString().split("T")[0], day: d.toLocaleDateString("en", { weekday: "short" }), num: d.getDate(), month: d.toLocaleDateString("en", { month: "short" }) });
    }
    return days;
  };

  const days = getDays();
  const statusColors = { planned: "bg-blue-500", published: "bg-emerald-500", completed: "bg-amber-500", approved: "bg-violet-500" };

  return (
    <div data-testid="my-shifts-tab">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-stone-800">My Shifts</h2>
          <p className="text-sm text-stone-500">Your weekly shift schedule — {user?.name}</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => navWeek(-1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="my-shift-prev">
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"/></svg>
          </button>
          <span className="text-sm font-semibold text-stone-700 bg-stone-100 px-4 py-1.5 rounded-lg" data-testid="my-shift-week">
            {days[0]?.num} {days[0]?.month} — {days[6]?.num} {days[6]?.month}
          </span>
          <button onClick={() => navWeek(1)} className="p-2 hover:bg-stone-100 rounded-lg text-stone-500" data-testid="my-shift-next">
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"/></svg>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-3">
        {days.map(d => {
          const dayShifts = shifts.filter(s => s.date === d.date);
          const isToday = d.date === new Date().toISOString().split("T")[0];
          return (
            <motion.div key={d.date} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className={`border rounded-xl p-4 min-h-[120px] transition-all ${isToday ? "border-emerald-300 bg-emerald-50/30 ring-1 ring-emerald-200" : "border-stone-200 bg-white"}`} data-testid={`my-shift-day-${d.date}`}>
              <div className="text-center mb-3">
                <div className={`text-xs font-bold uppercase ${isToday ? "text-emerald-600" : "text-stone-400"}`}>{d.day}</div>
                <div className={`text-lg font-bold ${isToday ? "text-emerald-700" : "text-stone-800"}`}>{d.num}</div>
                <div className="text-[10px] text-stone-400">{d.month}</div>
              </div>
              {dayShifts.length === 0 ? (
                <div className="text-center py-2"><span className="text-xs text-stone-300">No shift</span></div>
              ) : dayShifts.map(s => (
                <div key={s.id} className={`${statusColors[s.status] || "bg-stone-400"} text-white rounded-lg p-2 mb-1`} data-testid={`my-shift-entry-${s.id}`}>
                  <div className="text-sm font-bold">{s.start_time} — {s.end_time}</div>
                  <div className="text-[10px] opacity-80 capitalize">{s.status}</div>
                  {s.notes && <div className="text-[10px] opacity-70 mt-0.5">{s.notes}</div>}
                </div>
              ))}
            </motion.div>
          );
        })}
      </div>

      {shifts.length > 0 && (
        <div className="mt-6 bg-white border border-stone-200 rounded-xl p-4">
          <h3 className="text-sm font-bold text-stone-700 mb-2">This Week Summary</h3>
          <div className="flex gap-6 text-sm">
            <div><span className="text-stone-400">Total Shifts:</span> <span className="font-bold text-stone-800">{shifts.length}</span></div>
            <div><span className="text-stone-400">Total Hours:</span> <span className="font-bold text-stone-800">{shifts.reduce((acc, s) => {
              try { const st = new Date(`2000-01-01T${s.start_time}`); const en = new Date(`2000-01-01T${s.end_time}`); return acc + (en - st) / 3600000; } catch { return acc + 8; }
            }, 0).toFixed(1)}h</span></div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ── ROLES & PERMISSIONS ── */
const RolesTab = ({ properties }) => {
  const [roles, setRoles] = useState([]);
  const [users, setUsers] = useState([]);

  const load = useCallback(async () => {
    try {
      const [{ data: r }, { data: u }] = await Promise.all([
        axios.get(`${API}/admin/roles`),
        axios.get(`${API}/admin/users`),
      ]);
      setRoles(r.roles || []); setUsers(u);
    } catch { toast.error("Failed"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const getRoleUsers = (roleId) => users.filter(u => u.role === roleId).length;
  const getRolePerms = (role) => {
    const perms = role.permissions || {};
    return Object.values(perms).reduce((a, acts) => a + (Array.isArray(acts) ? acts.length : 0), 0);
  };

  return (
    <div data-testid="roles-permissions-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Roles & Permissions</h2><p className="text-sm text-stone-500">Manage user roles and their permissions</p></div>
      </div>
      <div className="border border-stone-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-stone-50 border-b">
            <th className="px-4 py-2.5 text-left text-xs font-semibold text-stone-500 uppercase">Role Name</th>
            <th className="px-4 py-2.5 text-center text-xs font-semibold text-stone-500 uppercase">Users</th>
            <th className="px-4 py-2.5 text-center text-xs font-semibold text-stone-500 uppercase">Permissions</th>
            <th className="px-4 py-2.5 text-center text-xs font-semibold text-stone-500 uppercase">Type</th>
          </tr></thead>
          <tbody>{roles.map(r => (
            <tr key={r.id} className="border-b border-stone-100 hover:bg-stone-50/50" data-testid={`role-row-${r.id}`}>
              <td className="px-4 py-3">
                <div className="font-medium text-stone-800 capitalize">{r.name}</div>
                {r.description && <div className="text-[10px] text-stone-400">{r.description}</div>}
              </td>
              <td className="px-4 py-3 text-center"><span className="text-sm text-stone-600">{getRoleUsers(r.id)} users</span></td>
              <td className="px-4 py-3 text-center"><Badge className="bg-emerald-50 text-emerald-600 text-[10px]">{getRolePerms(r)} permissions</Badge></td>
              <td className="px-4 py-3 text-center"><span className={`text-[10px] ${r.is_builtin ? "text-stone-400" : "text-blue-600"}`}>{r.is_builtin ? "Built-in" : "Custom"}</span></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p className="text-xs text-stone-400 mt-2">Showing {roles.length} roles</p>
    </div>
  );
};

/* ── MAIN PANEL ── */
const staffTabs = [
  { id: "users", label: "Users" },
  { id: "my-shifts", label: "My Shifts" },
  { id: "roles", label: "Roles & Permissions" },
];

export const StaffManagementPanel = ({ properties, user, activePropertyId }) => {
  const [tab, setTab] = useState("users");

  return (
    <div className="p-5" data-testid="staff-management-panel">
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1 border-b border-stone-200">
        {staffTabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all border-b-2 -mb-[1px] ${
              tab === t.id ? "text-emerald-700 border-emerald-500 bg-emerald-50/50" : "text-stone-400 border-transparent hover:text-stone-600"
            }`} data-testid={`staff-tab-${t.id}`}>{t.label}</button>
        ))}
      </div>
      {tab === "users" && <UsersTab properties={properties} />}
      {tab === "my-shifts" && <MyShiftsTab user={user} />}
      {tab === "roles" && <RolesTab properties={properties} />}
    </div>
  );
};
