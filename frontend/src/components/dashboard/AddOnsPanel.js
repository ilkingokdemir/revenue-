import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plus, Trash, Car, Coffee, Briefcase, Sparkle, Heart, Baby, Package,
  ArrowsClockwise, ToggleLeft, ToggleRight, CurrencyGbp,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { API } from "./config";

const ADDON_CATEGORIES = [
  { id: "transport", label: "Transport", icon: Car },
  { id: "dining", label: "Food & Drink", icon: Coffee },
  { id: "experience", label: "Experiences", icon: Sparkle },
  { id: "business", label: "Business", icon: Briefcase },
  { id: "wellness", label: "Wellness", icon: Heart },
  { id: "family", label: "Family", icon: Baby },
  { id: "other", label: "Other", icon: Package },
];

const PRICE_TYPES = [
  { id: "per_stay", label: "Per Stay" },
  { id: "per_night", label: "Per Night" },
  { id: "per_person", label: "Per Person" },
  { id: "per_person_per_night", label: "Per Person / Night" },
];

const AddOnsPanel = ({ properties }) => {
  const [selectedProperty, setSelectedProperty] = useState(properties?.filter(p => p.id !== "default")[0]?.id || "");
  const [addons, setAddons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", category: "experience", price: 0, price_type: "per_stay", icon: "" });

  const fetchAddons = useCallback(async () => {
    if (!selectedProperty) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/add-ons`, { params: { property_id: selectedProperty } });
      setAddons(data);
    } catch (e) { toast.error("Failed to load add-ons"); }
    finally { setLoading(false); }
  }, [selectedProperty]);

  useEffect(() => { fetchAddons(); }, [fetchAddons]);

  const handleCreate = async () => {
    if (!form.name.trim()) { toast.error("Name is required"); return; }
    try {
      await axios.post(`${API}/add-ons`, { ...form, property_id: selectedProperty });
      toast.success(`Add-on "${form.name}" created`);
      setShowCreate(false);
      setForm({ name: "", description: "", category: "experience", price: 0, price_type: "per_stay", icon: "" });
      fetchAddons();
    } catch (e) { toast.error("Failed to create"); }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API}/add-ons/${id}`);
      toast.success("Add-on deleted");
      fetchAddons();
    } catch (e) { toast.error("Failed to delete"); }
  };

  const handleToggle = async (id) => {
    try {
      const { data } = await axios.put(`${API}/add-ons/${id}/toggle`);
      toast.success(data.is_active ? "Add-on activated" : "Add-on deactivated");
      fetchAddons();
    } catch (e) { toast.error("Failed to toggle"); }
  };

  const getCategoryIcon = (cat) => {
    const c = ADDON_CATEGORIES.find(ac => ac.id === cat);
    return c ? c.icon : Package;
  };

  return (
    <div className="p-5" data-testid="add-ons-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800">Add-on Services</h2>
          <p className="text-sm text-stone-500 mt-0.5">Upsell extras to boost revenue per booking</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={selectedProperty} onChange={e => setSelectedProperty(e.target.value)}
            className="text-xs border border-stone-200 rounded-lg px-2.5 py-1.5 bg-white text-stone-700 font-medium"
            data-testid="addons-property-select">
            {properties?.filter(p => p.id !== "default").map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <button onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1.5 px-3 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800"
            data-testid="create-addon-btn">
            <Plus size={13} /> New Add-on
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="bg-white border border-stone-200 rounded-lg p-5 mb-5" data-testid="addon-create-form">
          <h3 className="text-sm font-semibold text-stone-700 mb-4">Create Add-on Service</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Service Name *</label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Airport Transfer" data-testid="addon-name-input" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Category</label>
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="addon-category-select">
                {ADDON_CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="text-xs font-medium text-stone-600 mb-1 block">Description</label>
              <Input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Brief description of the service" data-testid="addon-desc-input" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Price (£)</label>
              <Input type="number" min={0} value={form.price} onChange={e => setForm(f => ({ ...f, price: parseFloat(e.target.value) || 0 }))} data-testid="addon-price-input" />
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Price Type</label>
              <select value={form.price_type} onChange={e => setForm(f => ({ ...f, price_type: e.target.value }))}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="addon-price-type">
                {PRICE_TYPES.map(pt => <option key={pt.id} value={pt.id}>{pt.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setShowCreate(false)} className="px-3 py-2 text-xs text-stone-600 border border-stone-200 rounded-lg hover:bg-stone-50">Cancel</button>
            <button onClick={handleCreate} className="px-4 py-2 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800" data-testid="addon-submit-btn">Create Add-on</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-12"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>
      ) : addons.length === 0 ? (
        <div className="text-center py-12 bg-white border border-stone-200 rounded-lg">
          <Package size={36} className="mx-auto text-stone-300 mb-2" />
          <p className="text-sm text-stone-500">No add-on services yet</p>
          <p className="text-xs text-stone-400 mt-1">Create extras like airport transfers, breakfast, spa to upsell</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {addons.map(addon => {
            const CatIcon = getCategoryIcon(addon.category);
            return (
              <div key={addon.id} className="bg-white border border-stone-200 rounded-lg p-4 flex items-start gap-3" data-testid={`addon-${addon.id}`}>
                <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center flex-shrink-0">
                  <CatIcon size={18} className="text-amber-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-stone-800 text-sm">{addon.name}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${addon.is_active ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-stone-500"}`}>
                      {addon.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  {addon.description && <p className="text-xs text-stone-500 mt-0.5">{addon.description}</p>}
                  <div className="flex gap-2 mt-1 text-xs">
                    <span className="font-semibold text-stone-700">£{addon.price}</span>
                    <span className="text-stone-400">{PRICE_TYPES.find(pt => pt.id === addon.price_type)?.label || addon.price_type}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button onClick={() => handleToggle(addon.id)} className="p-1.5 rounded hover:bg-stone-50" data-testid={`toggle-addon-${addon.id}`}>
                    {addon.is_active ? <ToggleRight size={18} weight="fill" className="text-emerald-600" /> : <ToggleLeft size={18} className="text-stone-400" />}
                  </button>
                  <button onClick={() => handleDelete(addon.id)} className="p-1.5 text-stone-400 hover:text-red-600 rounded hover:bg-red-50" data-testid={`delete-addon-${addon.id}`}>
                    <Trash size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export { AddOnsPanel };
