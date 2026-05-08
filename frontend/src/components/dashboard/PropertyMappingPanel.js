import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { ArrowsClockwise, Buildings, Info } from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { API, formatApiErrorDetail } from "./config";

const PropertyMappingPanel = ({ user }) => {
  const [properties, setProperties] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ external_id: "", external_name: "", external_system: "myhotelbox" });

  const fetchProperties = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await axios.get(`${API}/properties`);
      setProperties(data);
    } catch (e) {
      toast.error("Failed to load properties");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchProperties(); }, [fetchProperties]);

  const handleSaveMapping = async (propertyId) => {
    try {
      await axios.put(`${API}/properties/${propertyId}/mapping`, editForm);
      toast.success("Property mapping saved!");
      setEditingId(null);
      fetchProperties();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to save mapping");
    }
  };

  const startEdit = (prop) => {
    setEditingId(prop.id);
    setEditForm({
      external_id: prop.external_id || "",
      external_name: prop.external_name || "",
      external_system: prop.external_system || "myhotelbox"
    });
  };

  return (
    <div className="p-5" data-testid="property-mapping-panel">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-800" data-testid="mapping-title">Property Mapping</h2>
          <p className="text-sm text-stone-500 mt-0.5">Link Review Hub properties to your MyHotelBox.com branches</p>
        </div>
      </div>

      {/* Info Card */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Info size={16} className="text-emerald-700" />
          <h3 className="text-sm font-medium text-emerald-800">How Property Mapping Works</h3>
        </div>
        <div className="text-xs text-emerald-700 space-y-1">
          <p>Map each Review Hub property to a MyHotelBox branch ID. When reviews arrive via the inbound webhook with a matching <code className="bg-emerald-100 px-1 rounded">property_id</code>, they'll automatically route to the correct property.</p>
          <p>Example: Map "Default Hotel" &rarr; MyHotelBox branch "ALDGATE FLATS" (ID: <code className="bg-emerald-100 px-1 rounded">aldgate-flats-001</code>)</p>
        </div>
      </div>

      {/* Properties List */}
      {isLoading ? (
        <div className="flex justify-center py-12"><ArrowsClockwise size={24} className="animate-spin text-stone-400" /></div>
      ) : (
        <div className="space-y-3" data-testid="properties-mapping-list">
          {properties.map((prop) => (
            <div key={prop.id} className="bg-white border border-stone-200 rounded-lg p-4" data-testid={`property-${prop.id}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-stone-100 flex items-center justify-center">
                    <Buildings size={16} className="text-stone-600" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-stone-800">{prop.name}</h3>
                    <p className="text-[10px] text-stone-400">{prop.property_type} &middot; ID: {prop.id}</p>
                  </div>
                </div>
                {prop.external_id ? (
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium">Mapped</span>
                    {user?.role === "admin" && (
                      <button onClick={() => startEdit(prop)} className="text-xs text-stone-400 hover:text-stone-600" data-testid={`edit-mapping-${prop.id}`}>Edit</button>
                    )}
                  </div>
                ) : (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 font-medium">Not mapped</span>
                )}
              </div>

              {/* Current Mapping */}
              {prop.external_id && editingId !== prop.id && (
                <div className="bg-stone-50 rounded-lg p-3 grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <span className="text-stone-400 block mb-0.5">External System</span>
                    <span className="text-stone-700 font-medium capitalize">{prop.external_system || "myhotelbox"}</span>
                  </div>
                  <div>
                    <span className="text-stone-400 block mb-0.5">External ID</span>
                    <code className="text-stone-700 font-mono text-[11px]">{prop.external_id}</code>
                  </div>
                  <div>
                    <span className="text-stone-400 block mb-0.5">External Name</span>
                    <span className="text-stone-700">{prop.external_name || "—"}</span>
                  </div>
                </div>
              )}

              {/* Edit Form */}
              {(editingId === prop.id || (!prop.external_id && user?.role === "admin")) && (
                <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} className="border-t border-stone-100 pt-3 mt-2">
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="text-[10px] text-stone-500 block mb-1">External System</label>
                      <select
                        value={editForm.external_system}
                        onChange={(e) => setEditForm(p => ({ ...p, external_system: e.target.value }))}
                        className="w-full text-xs border border-stone-200 rounded-lg px-2 py-1.5 bg-white"
                        data-testid={`system-select-${prop.id}`}
                      >
                        <option value="myhotelbox">MyHotelBox</option>
                        <option value="cloudbeds">Cloudbeds</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] text-stone-500 block mb-1">External ID</label>
                      <Input
                        value={editForm.external_id}
                        onChange={(e) => setEditForm(p => ({ ...p, external_id: e.target.value }))}
                        placeholder="e.g., aldgate-flats-001"
                        className="text-xs h-8"
                        data-testid={`external-id-${prop.id}`}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-stone-500 block mb-1">External Name</label>
                      <Input
                        value={editForm.external_name}
                        onChange={(e) => setEditForm(p => ({ ...p, external_name: e.target.value }))}
                        placeholder="e.g., ALDGATE FLATS"
                        className="text-xs h-8"
                        data-testid={`external-name-${prop.id}`}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => handleSaveMapping(prop.id)}
                      className="px-3 py-1.5 bg-emerald-700 text-white text-xs font-medium rounded-lg hover:bg-emerald-800"
                      data-testid={`save-mapping-${prop.id}`}
                    >Save Mapping</button>
                    {editingId === prop.id && (
                      <button onClick={() => setEditingId(null)} className="px-3 py-1.5 border border-stone-300 text-stone-600 text-xs rounded-lg hover:bg-stone-50">Cancel</button>
                    )}
                  </div>
                </motion.div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { PropertyMappingPanel };
