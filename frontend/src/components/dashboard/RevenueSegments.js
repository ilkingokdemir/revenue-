import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, Info } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EXAMPLE_SEGMENTS = [
  { code: "MOBILE", desc: "Reservations from mobile app" },
  { code: "CORPORATE", desc: "Corporate customers" },
  { code: "MEMBER", desc: "Loyalty members" },
  { code: "GENIUS", desc: "Booking.com Genius members" },
  { code: "GEO_US", desc: "Reservations from US" },
  { code: "LONG_STAY", desc: "Extended stay reservations" },
];

export const RevenueSegments = ({ propertyId }) => {
  const [items, setItems] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", description: "", priority: 1 });

  const load = async () => {
    try {
      const { data } = await axios.get(`${API}/revenue/segments/${propertyId}`);
      setItems(data.items);
    } catch { toast.error("Failed"); }
  };
  useEffect(() => { load(); }, [propertyId]);

  const create = async () => {
    if (!form.code || !form.name) { toast.error("Code and Name required"); return; }
    try {
      await axios.post(`${API}/revenue/segments/${propertyId}`, form);
      toast.success("Segment created");
      setShowForm(false);
      setForm({ code: "", name: "", description: "", priority: 1 });
      load();
    } catch { toast.error("Failed"); }
  };

  const remove = async (id) => {
    try {
      await axios.delete(`${API}/revenue/segments/${id}`);
      toast.success("Deleted");
      load();
    } catch { toast.error("Failed"); }
  };

  return (
    <div className="space-y-6" data-testid="rev-segments">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Revenue Segments</h2>
          <p className="text-sm text-stone-500">Manage customer profiles (MOBILE, CORPORATE, MEMBER, GENIUS etc.). Used for pricing and targeting.</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium" data-testid="rev-new-segment">
          <Plus className="w-4 h-4" /> New Segment
        </button>
      </div>

      {/* Info box */}
      <div className="bg-blue-50 border-l-4 border-blue-400 rounded-r-xl p-4">
        <div className="flex items-start gap-2">
          <Info className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-800">
            <p className="font-semibold mb-1">Revenue Segments</p>
            <p>Revenue Segments represent customer profiles for pricing, targeting, and analysis.</p>
            <p className="mt-2 font-semibold">Example Segments:</p>
            <ul className="mt-1 space-y-0.5">
              {EXAMPLE_SEGMENTS.map(s => (
                <li key={s.code} className="text-xs"><strong>{s.code}</strong> - {s.desc}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="bg-white border border-stone-200 rounded-2xl p-5">
          <h3 className="font-bold text-stone-800 mb-4">New Segment</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <Input placeholder="Code (e.g. MOBILE)" value={form.code} onChange={e => setForm(p => ({ ...p, code: e.target.value }))} data-testid="rev-seg-code" />
            <Input placeholder="Name" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} data-testid="rev-seg-name" />
            <Input placeholder="Description" value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} />
            <div className="flex gap-2">
              <Input type="number" min={1} max={10} placeholder="Priority" value={form.priority} onChange={e => setForm(p => ({ ...p, priority: Number(e.target.value) }))} className="w-24" />
              <button onClick={create} className="bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-xl text-sm font-medium flex-1" data-testid="rev-seg-create">Create</button>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="border-b bg-stone-50/50">
            <th className="px-4 py-3 text-left text-xs font-semibold text-stone-500 cursor-pointer hover:text-stone-700">Code</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-stone-500">Name</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-stone-500">Description</th>
            <th className="px-4 py-3 text-center text-xs font-semibold text-stone-500">Priority</th>
            <th className="px-4 py-3 text-center text-xs font-semibold text-stone-500">Status</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-stone-500">Actions</th>
          </tr></thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-12 text-stone-400 text-sm">
                No segments configured. Click "New Segment" to create one.
              </td></tr>
            ) : items.map(item => (
              <tr key={item.id} className="border-b border-stone-50 hover:bg-stone-50/50" data-testid={`rev-seg-row-${item.id}`}>
                <td className="px-4 py-3 font-mono font-bold text-stone-800">{item.code}</td>
                <td className="px-4 py-3 text-stone-700">{item.name}</td>
                <td className="px-4 py-3 text-stone-500 text-xs">{item.description}</td>
                <td className="px-4 py-3 text-center text-stone-600">{item.priority}</td>
                <td className="px-4 py-3 text-center">
                  <Badge className="text-[10px] bg-emerald-100 text-emerald-700">{item.status}</Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => remove(item.id)} className="text-red-400 hover:text-red-600 p-1" data-testid={`rev-seg-delete-${item.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
