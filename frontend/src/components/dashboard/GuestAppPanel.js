import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  MapPin, WifiHigh, Clock, Phone, Envelope, Star,
  ArrowsClockwise, PencilSimple, Plus, Trash,
  MapTrifold, Bed, ForkKnife, Heartbeat, Car,
  Bell, Info,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATEGORY_ICONS = {
  dining: ForkKnife,
  wellness: Heartbeat,
  services: Bell,
  transport: Car,
};

export function GuestAppPanel({ properties, activePropertyId }) {
  const [directory, setDirectory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState({});

  const propertyId = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "city-gate");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/guest-app/directory/${propertyId}`);
      setDirectory(res.data);
      setEditData(res.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const saveDirectory = async () => {
    await axios.put(`${API}/guest-app/directory/${propertyId}`, editData);
    setEditing(false);
    fetchData();
  };

  const guestAppUrl = `${process.env.REACT_APP_BACKEND_URL}/api/guest-app/public/${propertyId}`;

  if (loading) return <div className="p-6 flex justify-center py-20"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="guest-app-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="guest-app-title">
            <MapPin size={22} className="text-rose-500" weight="fill" />
            Guest App & Directory
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Digital guest directory — WiFi, services, recommendations</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setEditing(!editing)}
            className={`text-xs px-3 py-1.5 rounded-lg font-medium ${editing ? "bg-stone-200 text-stone-700" : "bg-rose-50 text-rose-700 hover:bg-rose-100"}`}
            data-testid="edit-directory-btn">
            <PencilSimple size={12} className="inline mr-1" /> {editing ? "Cancel" : "Edit"}
          </button>
          {editing && (
            <button onClick={saveDirectory} className="text-xs px-3 py-1.5 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 font-medium" data-testid="save-directory-btn">
              Save
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left: Editor / Info */}
        <div className="space-y-4">
          {/* Welcome & WiFi */}
          <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-3" data-testid="wifi-section">
            <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5"><WifiHigh size={15} className="text-blue-500" /> WiFi & Welcome</h3>
            {editing ? (
              <>
                <Textarea placeholder="Welcome message" value={editData.welcome_message || ""} onChange={e => setEditData(p => ({...p, welcome_message: e.target.value}))} rows={2} />
                <div className="grid grid-cols-2 gap-2">
                  <Input placeholder="WiFi Name" value={editData.wifi_name || ""} onChange={e => setEditData(p => ({...p, wifi_name: e.target.value}))} />
                  <Input placeholder="WiFi Password" value={editData.wifi_password || ""} onChange={e => setEditData(p => ({...p, wifi_password: e.target.value}))} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Input placeholder="Check-in Time" value={editData.checkin_time || ""} onChange={e => setEditData(p => ({...p, checkin_time: e.target.value}))} />
                  <Input placeholder="Checkout Time" value={editData.checkout_time || ""} onChange={e => setEditData(p => ({...p, checkout_time: e.target.value}))} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Input placeholder="Front Desk Phone" value={editData.front_desk_phone || ""} onChange={e => setEditData(p => ({...p, front_desk_phone: e.target.value}))} />
                  <Input placeholder="Front Desk Email" value={editData.front_desk_email || ""} onChange={e => setEditData(p => ({...p, front_desk_email: e.target.value}))} />
                </div>
              </>
            ) : (
              <>
                <p className="text-xs text-stone-600">{directory?.welcome_message || "No welcome message set"}</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-blue-50 rounded-lg p-2.5">
                    <div className="text-[10px] text-blue-500 uppercase font-semibold">WiFi</div>
                    <div className="text-xs font-bold text-stone-800">{directory?.wifi_name || "Not set"}</div>
                    <div className="text-[10px] text-stone-500">Password: {directory?.wifi_password || "—"}</div>
                  </div>
                  <div className="bg-stone-50 rounded-lg p-2.5">
                    <div className="text-[10px] text-stone-500 uppercase font-semibold">Hours</div>
                    <div className="text-xs text-stone-700">Check-in: {directory?.checkin_time || "15:00"}</div>
                    <div className="text-xs text-stone-700">Checkout: {directory?.checkout_time || "11:00"}</div>
                  </div>
                </div>
                {(directory?.front_desk_phone || directory?.front_desk_email) && (
                  <div className="flex gap-3 text-xs text-stone-500">
                    {directory.front_desk_phone && <span className="flex items-center gap-1"><Phone size={12} /> {directory.front_desk_phone}</span>}
                    {directory.front_desk_email && <span className="flex items-center gap-1"><Envelope size={12} /> {directory.front_desk_email}</span>}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Services */}
          <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="services-section">
            <h3 className="text-sm font-semibold text-stone-800 mb-3 flex items-center gap-1.5"><Bell size={15} className="text-amber-500" /> Services ({directory?.services?.length || 0})</h3>
            <div className="space-y-2">
              {(directory?.services || []).map((s, i) => {
                const SIcon = CATEGORY_ICONS[s.category] || Info;
                return (
                  <div key={i} className="flex items-start gap-2.5 p-2 bg-stone-50 rounded-lg">
                    <div className="w-7 h-7 rounded-lg bg-amber-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <SIcon size={14} className="text-amber-600" />
                    </div>
                    <div className="flex-1">
                      <div className="text-xs font-semibold text-stone-800">{s.name}</div>
                      <div className="text-[10px] text-stone-500">{s.description}</div>
                      {s.hours && <div className="text-[10px] text-stone-400 mt-0.5 flex items-center gap-0.5"><Clock size={10} /> {s.hours}</div>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right: Guest App Preview + Recommendations */}
        <div className="space-y-4">
          {/* Guest App Preview */}
          <div className="bg-gradient-to-br from-rose-50 to-orange-50 border border-rose-200 rounded-xl p-4" data-testid="guest-app-preview">
            <div className="text-[10px] text-rose-500 uppercase font-semibold mb-2">Guest App Preview</div>
            <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-sm">
              <div className="text-center mb-3">
                <div className="text-base font-bold text-stone-800">{propertyId.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</div>
                <div className="text-[10px] text-stone-400">Digital Guest Directory</div>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center mb-3">
                <div className="bg-blue-50 rounded-lg p-2"><WifiHigh size={16} className="text-blue-500 mx-auto" /><div className="text-[9px] mt-1">WiFi</div></div>
                <div className="bg-amber-50 rounded-lg p-2"><Bell size={16} className="text-amber-500 mx-auto" /><div className="text-[9px] mt-1">Services</div></div>
                <div className="bg-emerald-50 rounded-lg p-2"><MapTrifold size={16} className="text-emerald-500 mx-auto" /><div className="text-[9px] mt-1">Explore</div></div>
              </div>
              <div className="text-[10px] text-stone-400 text-center">
                Public URL: <span className="text-blue-500 underline">.../guest-app/public/{propertyId}</span>
              </div>
            </div>
          </div>

          {/* Local Recommendations */}
          <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="recommendations-section">
            <h3 className="text-sm font-semibold text-stone-800 mb-3 flex items-center gap-1.5">
              <MapTrifold size={15} className="text-emerald-500" /> Local Recommendations ({directory?.local_recommendations?.length || 0})
            </h3>
            <div className="space-y-2">
              {(directory?.local_recommendations || []).map((r, i) => (
                <div key={i} className="flex items-start gap-2.5 p-2 bg-stone-50 rounded-lg">
                  <div className="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Star size={14} className="text-emerald-600" weight="fill" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold text-stone-800">{r.name}</div>
                      <span className="text-[9px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">{r.type}</span>
                    </div>
                    <div className="text-[10px] text-stone-500">{r.description}</div>
                    {r.distance && <div className="text-[10px] text-stone-400 mt-0.5 flex items-center gap-0.5"><MapPin size={10} /> {r.distance}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
