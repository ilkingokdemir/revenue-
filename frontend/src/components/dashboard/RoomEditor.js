import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plus, Trash, ArrowUp, ArrowDown, X, Image, Bed, Users, CurrencyGbp,
  FloppyDisk, ArrowsClockwise,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { AmenityPicker } from "./AmenityPicker";
import { API } from "./config";

const RoomEditor = ({ room, onSave, onCancel }) => {
  const [form, setForm] = useState({
    name: "", description: "", max_guests: 2, bed_type: "double", size_sqm: 0,
    amenities: [], photos: [], base_price: 0, currency: "GBP",
    total_rooms: 1, free_cancellation: true, breakfast_included: false,
    property_id: "", is_active: true,
    ...room,
  });
  const [photoUrl, setPhotoUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState("details");

  const update = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const addPhoto = () => {
    if (!photoUrl.trim()) return;
    update("photos", [...form.photos, photoUrl.trim()]);
    setPhotoUrl("");
  };

  const removePhoto = (idx) => update("photos", form.photos.filter((_, i) => i !== idx));

  const movePhoto = (idx, dir) => {
    const arr = [...form.photos];
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= arr.length) return;
    [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]];
    update("photos", arr);
  };

  const handleSave = async () => {
    if (!form.name || !form.property_id) { toast.error("Room name and property are required"); return; }
    setSaving(true);
    try {
      await onSave(form);
      toast.success(room?.id ? "Room updated" : "Room created");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const tabs = [
    { id: "details", label: "Details" },
    { id: "photos", label: `Photos (${form.photos.length})` },
    { id: "amenities", label: `Amenities (${form.amenities.length})` },
    { id: "pricing", label: "Pricing & Inventory" },
  ];

  return (
    <div className="bg-white border border-stone-200 rounded-lg" data-testid="room-editor">
      {/* Tabs */}
      <div className="flex border-b border-stone-200">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-xs font-medium transition-colors ${
              activeTab === tab.id ? "text-emerald-700 border-b-2 border-emerald-600 bg-emerald-50/50" : "text-stone-500 hover:text-stone-700"
            }`}
            data-testid={`tab-${tab.id}`}>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="p-5">
        {/* Details Tab */}
        {activeTab === "details" && (
          <div className="space-y-4" data-testid="tab-details-content">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Room Name *</label>
                <Input value={form.name} onChange={e => update("name", e.target.value)} placeholder="e.g. Deluxe King Room" data-testid="room-name-input" />
              </div>
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Bed Type</label>
                <select value={form.bed_type} onChange={e => update("bed_type", e.target.value)}
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="room-bed-type">
                  {["single", "double", "twin", "queen", "king", "super king", "bunk", "sofa bed", "suite"].map(b =>
                    <option key={b} value={b}>{b.charAt(0).toUpperCase() + b.slice(1)}</option>
                  )}
                </select>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-stone-600 mb-1 block">Description</label>
              <textarea value={form.description} onChange={e => update("description", e.target.value)}
                placeholder="Describe the room — what makes it special, views, layout, etc."
                rows={4} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm resize-none" data-testid="room-description" />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Max Guests</label>
                <div className="flex items-center gap-2">
                  <Users size={14} className="text-stone-400" />
                  <Input type="number" min={1} max={20} value={form.max_guests} onChange={e => update("max_guests", parseInt(e.target.value) || 1)} data-testid="room-max-guests" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Size (m²)</label>
                <Input type="number" min={0} value={form.size_sqm} onChange={e => update("size_sqm", parseInt(e.target.value) || 0)} data-testid="room-size" />
              </div>
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Total Rooms</label>
                <Input type="number" min={1} value={form.total_rooms} onChange={e => update("total_rooms", parseInt(e.target.value) || 1)} data-testid="room-total" />
              </div>
            </div>
          </div>
        )}

        {/* Photos Tab */}
        {activeTab === "photos" && (
          <div data-testid="tab-photos-content">
            <p className="text-xs text-stone-500 mb-3">Add unlimited photos. The first photo is the cover image. Drag to reorder.</p>
            {/* Add Photo Input */}
            <div className="flex gap-2 mb-4">
              <Input value={photoUrl} onChange={e => setPhotoUrl(e.target.value)}
                placeholder="Paste photo URL (e.g. https://images.unsplash.com/...)"
                className="flex-1" onKeyDown={e => e.key === "Enter" && addPhoto()} data-testid="photo-url-input" />
              <button onClick={addPhoto} className="px-4 py-2 bg-emerald-700 text-white rounded-lg text-xs font-medium hover:bg-emerald-800 flex items-center gap-1.5" data-testid="add-photo-btn">
                <Plus size={12} /> Add Photo
              </button>
            </div>
            {/* Photo Grid */}
            {form.photos.length === 0 ? (
              <div className="border-2 border-dashed border-stone-200 rounded-lg p-10 text-center">
                <Image size={36} className="mx-auto text-stone-300 mb-2" />
                <p className="text-sm text-stone-400">No photos added yet</p>
                <p className="text-xs text-stone-300 mt-1">Paste image URLs to add room photos</p>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-3">
                {form.photos.map((url, idx) => (
                  <div key={idx} className="relative group rounded-lg overflow-hidden border border-stone-200" data-testid={`photo-${idx}`}>
                    <img src={url} alt={`Room photo ${idx + 1}`} className="w-full h-32 object-cover" />
                    {idx === 0 && (
                      <span className="absolute top-1.5 left-1.5 text-[9px] font-bold bg-emerald-600 text-white px-1.5 py-0.5 rounded">COVER</span>
                    )}
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100">
                      <button onClick={() => movePhoto(idx, -1)} disabled={idx === 0}
                        className="w-7 h-7 bg-white rounded-full flex items-center justify-center text-stone-700 hover:bg-stone-100 disabled:opacity-30"
                        data-testid={`photo-move-up-${idx}`}>
                        <ArrowUp size={12} weight="bold" />
                      </button>
                      <button onClick={() => movePhoto(idx, 1)} disabled={idx === form.photos.length - 1}
                        className="w-7 h-7 bg-white rounded-full flex items-center justify-center text-stone-700 hover:bg-stone-100 disabled:opacity-30"
                        data-testid={`photo-move-down-${idx}`}>
                        <ArrowDown size={12} weight="bold" />
                      </button>
                      <button onClick={() => removePhoto(idx)}
                        className="w-7 h-7 bg-red-500 rounded-full flex items-center justify-center text-white hover:bg-red-600"
                        data-testid={`photo-remove-${idx}`}>
                        <Trash size={12} weight="bold" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p className="text-[10px] text-stone-400 mt-2">{form.photos.length} photo{form.photos.length !== 1 ? "s" : ""} — no limit</p>
          </div>
        )}

        {/* Amenities Tab */}
        {activeTab === "amenities" && (
          <div data-testid="tab-amenities-content">
            <p className="text-xs text-stone-500 mb-3">Select from 160+ amenities or add custom ones. These will be displayed on your booking page.</p>
            <AmenityPicker selected={form.amenities} onChange={a => update("amenities", a)} mode="room" />
          </div>
        )}

        {/* Pricing Tab */}
        {activeTab === "pricing" && (
          <div className="space-y-4" data-testid="tab-pricing-content">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Base Price per Night</label>
                <div className="relative">
                  <CurrencyGbp size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
                  <Input type="number" min={0} step={1} value={form.base_price} onChange={e => update("base_price", parseFloat(e.target.value) || 0)} className="pl-9" data-testid="room-price" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-stone-600 mb-1 block">Currency</label>
                <select value={form.currency} onChange={e => update("currency", e.target.value)}
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="room-currency">
                  {["GBP", "USD", "EUR", "AED", "SAR", "CHF", "AUD", "CAD", "INR", "JPY"].map(c =>
                    <option key={c} value={c}>{c}</option>
                  )}
                </select>
              </div>
            </div>
            <div className="space-y-3 pt-2">
              {[
                { field: "free_cancellation", label: "Free Cancellation", desc: "Guests can cancel free of charge" },
                { field: "breakfast_included", label: "Breakfast Included", desc: "Breakfast is included in the rate" },
                { field: "is_active", label: "Active", desc: "Room is visible and bookable" },
              ].map(({ field, label, desc }) => (
                <div key={field} className="flex items-center justify-between py-2 border-b border-stone-100 last:border-0">
                  <div>
                    <span className="text-sm font-medium text-stone-700">{label}</span>
                    <p className="text-[11px] text-stone-400">{desc}</p>
                  </div>
                  <Switch checked={form[field]} onCheckedChange={v => update(field, v)} data-testid={`toggle-${field}`} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 mt-6 pt-4 border-t border-stone-200">
          <button onClick={onCancel} className="px-4 py-2 text-sm text-stone-600 border border-stone-200 rounded-lg hover:bg-stone-50" data-testid="room-cancel-btn">Cancel</button>
          <button onClick={handleSave} disabled={saving}
            className="px-5 py-2 bg-emerald-700 text-white rounded-lg text-sm font-medium hover:bg-emerald-800 flex items-center gap-1.5 disabled:opacity-50"
            data-testid="room-save-btn">
            {saving ? <ArrowsClockwise size={14} className="animate-spin" /> : <FloppyDisk size={14} />}
            {saving ? "Saving..." : (room?.id ? "Update Room" : "Create Room")}
          </button>
        </div>
      </div>
    </div>
  );
};

export { RoomEditor };
