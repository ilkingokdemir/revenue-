import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  MagnifyingGlass, Plus, X, Check, CaretDown, CaretRight,
} from "@phosphor-icons/react";
import { API } from "./config";

const AmenityPicker = ({ selected = [], onChange, mode = "room" }) => {
  const [catalog, setCatalog] = useState({});
  const [search, setSearch] = useState("");
  const [expandedCat, setExpandedCat] = useState(null);
  const [customInput, setCustomInput] = useState("");

  useEffect(() => {
    const endpoint = mode === "facility" ? "facilities/catalog" : "amenities/catalog";
    axios.get(`${API}/${endpoint}`).then(r => setCatalog(r.data)).catch(() => {});
  }, [mode]);

  const toggleItem = (item) => {
    const next = selected.includes(item) ? selected.filter(a => a !== item) : [...selected, item];
    onChange(next);
  };

  const addCustom = () => {
    if (!customInput.trim() || selected.includes(customInput.trim())) return;
    onChange([...selected, customInput.trim()]);
    setCustomInput("");
  };

  const filteredCatalog = Object.entries(catalog).map(([catKey, cat]) => ({
    key: catKey,
    label: cat.label,
    items: cat.items.filter(item =>
      !search || item.toLowerCase().includes(search.toLowerCase())
    ),
  })).filter(c => c.items.length > 0);

  return (
    <div data-testid="amenity-picker">
      {/* Selected Tags */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3" data-testid="selected-amenities">
          {selected.map(a => (
            <span key={a} className="inline-flex items-center gap-1 text-xs bg-emerald-50 text-emerald-800 pl-2.5 pr-1 py-1 rounded-full border border-emerald-200">
              {a}
              <button onClick={() => toggleItem(a)} className="w-4 h-4 rounded-full hover:bg-emerald-200 flex items-center justify-center" data-testid={`remove-amenity-${a}`}>
                <X size={10} weight="bold" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search */}
      <div className="relative mb-3">
        <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder={`Search ${mode === "facility" ? "facilities" : "amenities"}...`}
          className="w-full border border-stone-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
          data-testid="amenity-search" />
      </div>

      {/* Categories */}
      <div className="border border-stone-200 rounded-lg overflow-hidden max-h-72 overflow-y-auto" data-testid="amenity-categories">
        {filteredCatalog.map(cat => (
          <div key={cat.key} className="border-b border-stone-100 last:border-0">
            <button onClick={() => setExpandedCat(expandedCat === cat.key ? null : cat.key)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-stone-700 bg-stone-50 hover:bg-stone-100 transition-colors"
              data-testid={`category-${cat.key}`}>
              <span>{cat.label} <span className="text-stone-400 font-normal">({cat.items.length})</span></span>
              {expandedCat === cat.key ? <CaretDown size={12} /> : <CaretRight size={12} />}
            </button>
            {(expandedCat === cat.key || search) && (
              <div className="px-2 py-1.5 grid grid-cols-2 gap-0.5">
                {cat.items.map(item => (
                  <label key={item} className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs cursor-pointer transition-colors ${
                    selected.includes(item) ? "bg-emerald-50 text-emerald-800" : "text-stone-600 hover:bg-stone-50"
                  }`} data-testid={`amenity-option-${item}`}>
                    <div className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
                      selected.includes(item) ? "bg-emerald-600 border-emerald-600" : "border-stone-300"
                    }`}>
                      {selected.includes(item) && <Check size={10} weight="bold" className="text-white" />}
                    </div>
                    <span className="truncate">{item}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Custom Amenity */}
      <div className="flex gap-2 mt-3">
        <input value={customInput} onChange={e => setCustomInput(e.target.value)}
          placeholder={`Add custom ${mode === "facility" ? "facility" : "amenity"}...`}
          className="flex-1 border border-stone-200 rounded-lg px-3 py-2 text-sm"
          onKeyDown={e => e.key === "Enter" && addCustom()}
          data-testid="custom-amenity-input" />
        <button onClick={addCustom} className="px-3 py-2 bg-stone-800 text-white rounded-lg text-xs font-medium hover:bg-stone-900 flex items-center gap-1" data-testid="add-custom-amenity-btn">
          <Plus size={12} /> Add
        </button>
      </div>

      <p className="text-[10px] text-stone-400 mt-1.5">{selected.length} selected</p>
    </div>
  );
};

export { AmenityPicker };
