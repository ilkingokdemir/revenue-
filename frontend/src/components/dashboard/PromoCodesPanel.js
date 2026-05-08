import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Tag, Plus, Trash, Lightning, ToggleLeft, ToggleRight,
  ArrowsClockwise, Percent, CurrencyGbp,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { API } from "./config";

const PromoCodesPanel = ({ properties }) => {
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ code: "", description: "", discount_type: "percentage", discount_value: 10, property_id: "", min_nights: 0, max_uses: 0, valid_from: "", valid_until: "" });

  const fetchCodes = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/promo-codes`);
      setCodes(data);
    } catch (e) { toast.error("Failed to load promo codes"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchCodes(); }, [fetchCodes]);

  const handleCreate = async () => {
    if (!form.code.trim()) { toast.error("Code is required"); return; }
    try {
      await axios.post(`${API}/promo-codes`, form);
      toast.success(`Promo code ${form.code.toUpperCase()} created`);
      setShowCreate(false);
      setForm({ code: "", description: "", discount_type: "percentage", discount_value: 10, property_id: "", min_nights: 0, max_uses: 0, valid_from: "", valid_until: "" });
      fetchCodes();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to create"); }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API}/promo-codes/${id}`);
      toast.success("Promo code deleted");
      fetchCodes();
    } catch (e) { toast.error("Failed to delete"); }
  };

  const handleToggle = async (id) => {
    try {
      const { data } = await axios.put(`${API}/promo-codes/${id}/toggle`);
      toast.success(data.is_active ? "Code activated" : "Code deactivated");
      fetchCodes();
    } catch (e) { toast.error("Failed to toggle"); }
  };

  return (
    <div className="p-5" data-testid="promo-codes-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800">Promo Codes</h2>
          <p className="text-sm text-stone-500 mt-0.5">Create discount codes to drive direct bookings</p>
        </div>
        <button onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-1.5 px-3 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800"
          data-testid="create-promo-btn">
          <Plus size={13} /> New Code
        </button>
      </div>

      {showCreate && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 mb-5" data-testid="promo-create-form">
          <h3 className="text-sm font-semibold text-stone-700 mb-4">Create Promo Code</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Code *</label>
              <Input value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))} placeholder="e.g. SUMMER25" data-testid="promo-code-input" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Description</label>
              <Input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="e.g. 25% summer discount" data-testid="promo-desc-input" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Discount Type</label>
              <select value={form.discount_type} onChange={e => setForm(f => ({ ...f, discount_type: e.target.value }))}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="promo-type-select">
                <option value="percentage">Percentage (%)</option>
                <option value="fixed">Fixed Amount</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">
                Discount Value {form.discount_type === "percentage" ? "(%)" : "(£)"}
              </label>
              <Input type="number" min={0} value={form.discount_value} onChange={e => setForm(f => ({ ...f, discount_value: parseFloat(e.target.value) || 0 }))} data-testid="promo-value-input" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Property (optional)</label>
              <select value={form.property_id} onChange={e => setForm(f => ({ ...f, property_id: e.target.value }))}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="promo-property-select">
                <option value="">All properties</option>
                {properties?.filter(p => p.id !== "default").map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Min Nights</label>
              <Input type="number" min={0} value={form.min_nights} onChange={e => setForm(f => ({ ...f, min_nights: parseInt(e.target.value) || 0 }))} data-testid="promo-min-nights" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Max Uses (0 = unlimited)</label>
              <Input type="number" min={0} value={form.max_uses} onChange={e => setForm(f => ({ ...f, max_uses: parseInt(e.target.value) || 0 }))} data-testid="promo-max-uses" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Valid From</label>
              <Input type="date" value={form.valid_from} onChange={e => setForm(f => ({ ...f, valid_from: e.target.value }))} data-testid="promo-valid-from" />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setShowCreate(false)} className="px-3 py-2 text-xs text-stone-600 border border-stone-200 rounded-lg hover:bg-stone-50">Cancel</button>
            <button onClick={handleCreate} className="px-4 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800" data-testid="promo-submit-btn">Create Code</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>
      ) : codes.length === 0 ? (
        <div className="text-center py-12 bg-white border border-stone-200 rounded-lg">
          <Tag size={36} className="mx-auto text-stone-300 mb-2" />
          <p className="text-sm text-stone-500">No promo codes yet</p>
          <p className="text-xs text-stone-400 mt-1">Create your first promo code to attract direct bookings</p>
        </div>
      ) : (
        <div className="space-y-2">
          {codes.map(code => (
            <div key={code.id} className="bg-white border border-stone-200 rounded-lg p-4 flex items-center gap-4" data-testid={`promo-${code.code}`}>
              <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-emerald-50">
                {code.discount_type === "percentage" ? <Percent size={18} className="text-emerald-600" /> : <CurrencyGbp size={18} className="text-emerald-600" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-stone-800 text-sm">{code.code}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${code.is_active ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                    {code.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
                <p className="text-xs text-stone-500 mt-0.5">{code.description || `${code.discount_value}${code.discount_type === "percentage" ? "%" : "£"} off`}</p>
                <div className="flex gap-3 mt-1 text-[10px] text-stone-400">
                  {code.min_nights > 0 && <span>Min {code.min_nights} nights</span>}
                  {code.max_uses > 0 && <span>Used {code.used_count}/{code.max_uses}</span>}
                  {code.property_id && <span>Property: {code.property_id}</span>}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => handleToggle(code.id)} className="p-2 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-50" data-testid={`toggle-promo-${code.code}`}>
                  {code.is_active ? <ToggleRight size={20} weight="fill" className="text-emerald-600" /> : <ToggleLeft size={20} />}
                </button>
                <button onClick={() => handleDelete(code.id)} className="p-2 text-stone-400 hover:text-red-600 rounded-lg hover:bg-red-50" data-testid={`delete-promo-${code.code}`}>
                  <Trash size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { PromoCodesPanel };
