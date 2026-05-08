/**
 * Guest Preferences Panel
 * -----------------------
 * Today's arrivals list with each guest's saved preferences (pillow firmness,
 * floor, dietary, allergies, occasion etc.). Click a row → edit prefs +
 * one-click "Apply to booking" (copies into booking notes & tags).
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Heart, RefreshCw, Sparkles, X, CheckCircle2, Star } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const FIELD_LABELS = {
  pillow_firmness: "Pillow",
  floor_preference: "Floor",
  bed_type: "Bed",
  smoking: "Smoking",
  ac_temperature: "AC °C",
  wake_up_call: "Wake-up",
  newspaper: "Newspaper",
  extra_blanket: "Extra blanket",
  dietary: "Dietary",
  allergies: "Allergies",
  favourite_room: "Fav room",
  occasion: "Occasion",
  occasion_date: "Occasion date",
  language: "Language",
  transport: "Transport",
  notes: "Notes",
};

export default function GuestPrefsPanel({ propertyId, hotelName = "" }) {
  const [arrivals, setArrivals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/guest-prefs/${propertyId}/today-arrivals`);
      setArrivals(data.items || []);
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setArrivals([]); }, [propertyId]);

  const apply = async (booking_id) => {
    try {
      const { data } = await axios.post(`${API}/guest-prefs/apply-to-booking/${booking_id}`);
      if (data.applied) toast.success(`Applied ${data.lines?.length || 0} preferences to booking notes`);
      else toast.info(data.reason || "Nothing to apply");
      load();
    } catch { toast.error("Apply failed"); }
  };

  return (
    <div className="space-y-6" data-testid="guest-prefs-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Heart className="w-5 h-5 text-pink-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Guest Preferences</h2>
            <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-pink-500/15 text-pink-300 rounded">VIP memory</span>
          </div>
          <p className="text-sm text-stone-400 mt-1">
            {hotelName ? `${hotelName} · ` : ""}Today's arrivals — saved preferences auto-flow to housekeeping & front desk.
          </p>
        </div>
        <button data-testid="prefs-refresh-btn" onClick={load}
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-stone-500"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : arrivals.length === 0 ? (
        <div className="text-center text-stone-500 py-12">No arrivals today.</div>
      ) : (
        <div className="space-y-2">
          {arrivals.map((a) => (
            <div key={a.booking_id} data-testid="pref-arrival-row"
              className="rounded-lg border border-stone-800 bg-stone-900/60 p-3">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="text-stone-100 font-semibold">{a.guest_name || "—"}</div>
                    {a.room_number && <span className="text-xs text-stone-400">· Room {a.room_number}</span>}
                    {a.has_prefs && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-pink-500/15 text-pink-300 border border-pink-500/40">
                        <Sparkles className="w-3 h-3 inline mr-1" />{a.pref_count} prefs
                      </span>
                    )}
                  </div>
                  {a.has_prefs && (
                    <div className="flex flex-wrap gap-1 text-[11px]">
                      {Object.entries(a.prefs).filter(([, v]) => v).map(([k, v]) => (
                        <span key={k} className="px-2 py-0.5 rounded bg-stone-800 text-stone-300 border border-stone-700">
                          <span className="text-stone-500">{FIELD_LABELS[k] || k}:</span>{" "}{String(v)}
                        </span>
                      ))}
                    </div>
                  )}
                  {!a.has_prefs && a.guest_id && (
                    <div className="text-xs text-stone-500">No preferences set yet</div>
                  )}
                  {!a.guest_id && (
                    <div className="text-xs text-stone-500 italic">No linked guest profile</div>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  {a.guest_id && (
                    <button data-testid="pref-edit-btn" onClick={() => setEditing(a)}
                      className="px-2 py-1 rounded bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-700 text-xs">
                      Edit prefs
                    </button>
                  )}
                  {a.has_prefs && (
                    <button data-testid="pref-apply-btn" onClick={() => apply(a.booking_id)}
                      className="px-2 py-1 rounded bg-pink-500/20 border border-pink-500/40 text-pink-200 text-xs hover:bg-pink-500/30">
                      Apply to booking
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <PrefsEditModal arrival={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
    </div>
  );
}

function PrefsEditModal({ arrival, onClose, onSaved }) {
  const [prefs, setPrefs] = useState(arrival.prefs || {});
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setPrefs({ ...prefs, [k]: v });
  const save = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/guest-prefs/${arrival.guest_id}`, { prefs });
      toast.success("Preferences saved");
      onSaved();
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-stone-900 border border-stone-800 rounded-xl max-w-lg w-full p-5 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-stone-100 font-semibold">{arrival.guest_name}</div>
            <div className="text-xs text-stone-500">Preferences carry over to every future stay</div>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-stone-800 text-stone-500"><X className="w-4 h-4" /></button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
          <Sel label="Pillow firmness" v={prefs.pillow_firmness} onChange={(v) => set("pillow_firmness", v)} options={["", "soft", "medium", "firm"]} />
          <Sel label="Floor preference" v={prefs.floor_preference} onChange={(v) => set("floor_preference", v)} options={["", "low", "mid", "high"]} />
          <Sel label="Bed type" v={prefs.bed_type} onChange={(v) => set("bed_type", v)} options={["", "king", "twin", "double"]} />
          <Sel label="Smoking" v={prefs.smoking} onChange={(v) => set("smoking", v)} options={["", "smoking", "non_smoking"]} />
          <Inp label="AC °C" type="number" v={prefs.ac_temperature || ""} onChange={(v) => set("ac_temperature", v ? parseInt(v, 10) : "")} />
          <Inp label="Wake-up call" placeholder="07:30" v={prefs.wake_up_call || ""} onChange={(v) => set("wake_up_call", v)} />
          <Inp label="Dietary" placeholder="vegan / halal" v={prefs.dietary || ""} onChange={(v) => set("dietary", v)} />
          <Inp label="Allergies" placeholder="nuts / gluten" v={prefs.allergies || ""} onChange={(v) => set("allergies", v)} />
          <Inp label="Favourite room" v={prefs.favourite_room || ""} onChange={(v) => set("favourite_room", v)} />
          <Inp label="Occasion" placeholder="Anniversary" v={prefs.occasion || ""} onChange={(v) => set("occasion", v)} />
          <Inp label="Occasion date" type="date" v={prefs.occasion_date || ""} onChange={(v) => set("occasion_date", v)} />
          <Inp label="Language" placeholder="en, tr, fr" v={prefs.language || ""} onChange={(v) => set("language", v)} />
          <label className="flex items-center gap-2 col-span-2">
            <input type="checkbox" checked={!!prefs.extra_blanket} onChange={(e) => set("extra_blanket", e.target.checked)} />
            <span className="text-stone-300">Extra blanket</span>
          </label>
          <div className="col-span-2">
            <label className="block text-[10px] uppercase tracking-wider text-stone-400 mb-1">Notes</label>
            <textarea rows={2} value={prefs.notes || ""} onChange={(e) => set("notes", e.target.value)}
              className="w-full px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1.5 rounded bg-stone-800 text-stone-300 text-sm">Cancel</button>
          <button data-testid="prefs-save-btn" onClick={save} disabled={saving}
            className="flex items-center gap-2 px-3 py-1.5 rounded bg-pink-500/20 border border-pink-500/40 text-pink-200 text-sm">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Save preferences
          </button>
        </div>
      </div>
    </div>
  );
}

function Sel({ label, v, onChange, options }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-stone-400">{label}</span>
      <select value={v || ""} onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100">
        {options.map((o) => <option key={o} value={o}>{o || "—"}</option>)}
      </select>
    </label>
  );
}
function Inp({ label, v, onChange, type = "text", placeholder = "" }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wider text-stone-400">{label}</span>
      <input type={type} value={v} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="px-3 py-2 rounded bg-stone-800 border border-stone-700 text-stone-100" />
    </label>
  );
}
