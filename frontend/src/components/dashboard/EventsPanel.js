import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const RoomsTab = ({ propertyId }) => {
  const [rooms, setRooms] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", capacity: 0, floor: "", hourly_rate: 0, half_day_rate: 0, full_day_rate: 0, equipment: "", amenities: "" });

  const load = useCallback(async () => { try { const { data } = await axios.get(`${API}/events/rooms/${propertyId}`); setRooms(data); } catch { toast.error("Failed"); } }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      await axios.post(`${API}/events/rooms`, { ...form, property_id: propertyId, equipment: form.equipment.split(",").map(s=>s.trim()).filter(Boolean), amenities: form.amenities.split(",").map(s=>s.trim()).filter(Boolean) });
      toast.success("Room created"); setShowCreate(false); load();
    } catch { toast.error("Failed"); }
  };

  const del = async (id) => { try { await axios.delete(`${API}/events/rooms/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  return (
    <div data-testid="event-rooms-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Meeting Rooms</h2><p className="text-sm text-stone-500">Manage event & meeting spaces</p></div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-room-btn">+ Add Room</button>
      </div>
      {rooms.length === 0 ? <div className="text-center py-16 text-stone-400"><p className="font-medium">No meeting rooms</p><p className="text-sm mt-1">Create your first meeting room</p></div> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">{rooms.map(r => (
          <motion.div key={r.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            className="border border-stone-200 rounded-xl p-5 bg-white hover:shadow-lg transition-all" data-testid={`event-room-${r.id}`}>
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-bold text-stone-800 text-base">{r.name}</h3>
                <p className="text-xs text-stone-400">{r.floor ? `Floor ${r.floor}` : ""} &middot; Capacity: {r.capacity} people</p>
              </div>
              <Badge className={`text-[10px] ${r.status === "available" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>{r.status}</Badge>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-3">
              <div className="bg-blue-50 rounded-lg p-2 text-center"><div className="text-[10px] text-blue-500 font-medium">Hourly</div><div className="text-sm font-bold text-blue-700">£{r.hourly_rate}</div></div>
              <div className="bg-violet-50 rounded-lg p-2 text-center"><div className="text-[10px] text-violet-500 font-medium">Half Day</div><div className="text-sm font-bold text-violet-700">£{r.half_day_rate}</div></div>
              <div className="bg-emerald-50 rounded-lg p-2 text-center"><div className="text-[10px] text-emerald-500 font-medium">Full Day</div><div className="text-sm font-bold text-emerald-700">£{r.full_day_rate}</div></div>
            </div>
            {r.equipment?.length > 0 && <div className="flex flex-wrap gap-1 mb-2">{r.equipment.map((e, i) => <span key={i} className="text-[9px] bg-stone-100 text-stone-500 px-1.5 py-0.5 rounded">{e}</span>)}</div>}
            <button onClick={() => del(r.id)} className="text-xs text-red-500 hover:underline mt-2" data-testid={`delete-room-${r.id}`}>Delete</button>
          </motion.div>
        ))}</div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md" data-testid="room-dialog"><DialogHeader><DialogTitle>Add Meeting Room</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Room name (e.g. Boardroom A)" data-testid="room-name" />
            <div className="grid grid-cols-2 gap-3">
              <Input type="number" value={form.capacity} onChange={e => setForm({...form, capacity: parseInt(e.target.value)||0})} placeholder="Capacity" data-testid="room-capacity" />
              <Input value={form.floor} onChange={e => setForm({...form, floor: e.target.value})} placeholder="Floor" data-testid="room-floor" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div><label className="text-xs text-stone-500 mb-1 block">Hourly £</label><Input type="number" value={form.hourly_rate} onChange={e => setForm({...form, hourly_rate: parseFloat(e.target.value)||0})} data-testid="room-hourly" /></div>
              <div><label className="text-xs text-stone-500 mb-1 block">Half Day £</label><Input type="number" value={form.half_day_rate} onChange={e => setForm({...form, half_day_rate: parseFloat(e.target.value)||0})} data-testid="room-halfday" /></div>
              <div><label className="text-xs text-stone-500 mb-1 block">Full Day £</label><Input type="number" value={form.full_day_rate} onChange={e => setForm({...form, full_day_rate: parseFloat(e.target.value)||0})} data-testid="room-fullday" /></div>
            </div>
            <Input value={form.equipment} onChange={e => setForm({...form, equipment: e.target.value})} placeholder="Equipment (comma-separated: Projector, Whiteboard)" data-testid="room-equipment" />
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="room-save">Add Room</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const BookingsTab = ({ propertyId }) => {
  const [bookings, setBookings] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [catering, setCatering] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ room_id: "", event_name: "", organizer: "", contact_email: "", date: "", start_time: "09:00", end_time: "17:00", attendees: 0, setup_type: "theater", catering: "none", total_cost: 0 });

  const load = useCallback(async () => {
    try {
      const [{ data: b }, { data: r }, { data: c }] = await Promise.all([
        axios.get(`${API}/events/bookings/${propertyId}`),
        axios.get(`${API}/events/rooms/${propertyId}`),
        axios.get(`${API}/events/catering`),
      ]);
      setBookings(b); setRooms(r); setCatering(c);
    } catch { toast.error("Failed"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    const room = rooms.find(r => r.id === form.room_id);
    try {
      await axios.post(`${API}/events/bookings`, { ...form, property_id: propertyId, room_name: room?.name || "" });
      toast.success("Event booked"); setShowCreate(false); load();
    } catch { toast.error("Failed"); }
  };

  const updateStatus = async (id, status) => { try { await axios.put(`${API}/events/bookings/${id}`, { status }); toast.success("Updated"); load(); } catch { toast.error("Failed"); } };
  const del = async (id) => { try { await axios.delete(`${API}/events/bookings/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); } };

  const setupIcons = { theater: "Rows", classroom: "Desks", boardroom: "Table", cocktail: "Standing", banquet: "Rounds", ushape: "U-Shape" };
  const statusColors = { confirmed: "bg-emerald-100 text-emerald-700", tentative: "bg-amber-100 text-amber-700", cancelled: "bg-red-100 text-red-700", completed: "bg-blue-100 text-blue-700" };

  return (
    <div data-testid="event-bookings-tab">
      <div className="flex items-center justify-between mb-6">
        <div><h2 className="text-lg font-bold text-stone-800">Event Bookings</h2><p className="text-sm text-stone-500">Manage meetings, conferences and events</p></div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="new-event-btn">+ Book Event</button>
      </div>
      {bookings.length === 0 ? <div className="text-center py-16 text-stone-400"><p className="font-medium">No event bookings</p></div> : (
        <div className="space-y-3">{bookings.map(b => (
          <div key={b.id} className="border border-stone-200 rounded-xl p-4 bg-white hover:shadow-md transition-all" data-testid={`event-booking-${b.id}`}>
            <div className="flex items-start justify-between">
              <div>
                <h4 className="font-bold text-stone-800">{b.event_name}</h4>
                <p className="text-xs text-stone-500">{b.room_name} &middot; {b.date} &middot; {b.start_time}-{b.end_time}</p>
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  <Badge className={`text-[10px] ${statusColors[b.status] || ""}`}>{b.status}</Badge>
                  <span className="text-[10px] text-stone-400">{b.attendees} attendees &middot; {setupIcons[b.setup_type] || b.setup_type} &middot; {b.organizer}</span>
                  {b.catering !== "none" && <Badge className="text-[9px] bg-amber-50 text-amber-600">{b.catering}</Badge>}
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="text-lg font-bold text-stone-800">£{b.total_cost}</div>
                <div className="flex gap-1 mt-1">
                  {b.status === "confirmed" && <button onClick={() => updateStatus(b.id, "completed")} className="text-[10px] text-emerald-600 hover:underline">Complete</button>}
                  {b.status !== "cancelled" && <button onClick={() => updateStatus(b.id, "cancelled")} className="text-[10px] text-red-500 hover:underline">Cancel</button>}
                  <button onClick={() => del(b.id)} className="text-[10px] text-stone-400 hover:underline">Delete</button>
                </div>
              </div>
            </div>
          </div>
        ))}</div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg" data-testid="event-dialog"><DialogHeader><DialogTitle>Book Event</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input value={form.event_name} onChange={e => setForm({...form, event_name: e.target.value})} placeholder="Event name" data-testid="event-name" />
            <div className="grid grid-cols-2 gap-3">
              <Select value={form.room_id || "select"} onValueChange={v => setForm({...form, room_id: v})}>
                <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Select room" /></SelectTrigger>
                <SelectContent>{rooms.map(r => <SelectItem key={r.id} value={r.id}>{r.name} ({r.capacity})</SelectItem>)}</SelectContent>
              </Select>
              <Input type="date" value={form.date} onChange={e => setForm({...form, date: e.target.value})} data-testid="event-date" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <Input type="time" value={form.start_time} onChange={e => setForm({...form, start_time: e.target.value})} data-testid="event-start" />
              <Input type="time" value={form.end_time} onChange={e => setForm({...form, end_time: e.target.value})} data-testid="event-end" />
              <Input type="number" value={form.attendees} onChange={e => setForm({...form, attendees: parseInt(e.target.value)||0})} placeholder="Attendees" data-testid="event-attendees" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input value={form.organizer} onChange={e => setForm({...form, organizer: e.target.value})} placeholder="Organizer name" data-testid="event-organizer" />
              <Input value={form.contact_email} onChange={e => setForm({...form, contact_email: e.target.value})} placeholder="Email" data-testid="event-email" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Select value={form.setup_type} onValueChange={v => setForm({...form, setup_type: v})}>
                <SelectTrigger className="h-9 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="theater">Theater</SelectItem><SelectItem value="classroom">Classroom</SelectItem><SelectItem value="boardroom">Boardroom</SelectItem><SelectItem value="cocktail">Cocktail</SelectItem><SelectItem value="banquet">Banquet</SelectItem><SelectItem value="ushape">U-Shape</SelectItem></SelectContent>
              </Select>
              <Select value={form.catering || "none"} onValueChange={v => setForm({...form, catering: v})}>
                <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Catering" /></SelectTrigger>
                <SelectContent><SelectItem value="none">No Catering</SelectItem>{catering.map(c => <SelectItem key={c.id} value={c.name}>{c.name} (£{c.price_per_person}/pp)</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <Input type="number" value={form.total_cost} onChange={e => setForm({...form, total_cost: parseFloat(e.target.value)||0})} placeholder="Total cost £" data-testid="event-cost" />
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="event-save">Book Event</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const tabs = [
  { id: "rooms", label: "Meeting Rooms" },
  { id: "bookings", label: "Event Bookings" },
];

export const EventsPanel = ({ properties, activePropertyId }) => {
  const [tab, setTab] = useState("rooms");
  const pid = activePropertyId || "all";
  return (
    <div className="p-5" data-testid="events-panel">
      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1 border-b border-stone-200">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all border-b-2 -mb-[1px] ${
              tab === t.id ? "text-emerald-700 border-emerald-500 bg-emerald-50/50" : "text-stone-400 border-transparent hover:text-stone-600"
            }`} data-testid={`events-tab-${t.id}`}>{t.label}</button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
          {tab === "rooms" && <RoomsTab propertyId={pid} />}
          {tab === "bookings" && <BookingsTab propertyId={pid} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
