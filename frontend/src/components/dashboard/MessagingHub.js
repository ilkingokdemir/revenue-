import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  ChatText, WhatsappLogo, Envelope, DeviceMobile, Globe,
  PaperPlaneTilt, Sparkle, CheckCircle, WarningCircle, Clock,
  ArrowsClockwise, Tag, X, MagnifyingGlass,
  Lightning, Phone, CalendarBlank,
  ChatCircleDots, Robot, SmileyMeh, Smiley, SmileySad,
  AddressBook, Plus, TelegramLogo, PencilSimple,
  CaretLeft, CaretRight, Trash, ToggleRight,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CHANNEL_CONFIG = {
  whatsapp: { name: "WhatsApp", icon: WhatsappLogo, color: "#25D366", bg: "bg-green-50", text: "text-green-700" },
  email: { name: "Email", icon: Envelope, color: "#3b82f6", bg: "bg-blue-50", text: "text-blue-700" },
  sms: { name: "SMS", icon: DeviceMobile, color: "#8b5cf6", bg: "bg-purple-50", text: "text-purple-700" },
  telegram: { name: "Telegram", icon: TelegramLogo, color: "#0088cc", bg: "bg-sky-50", text: "text-sky-700" },
  internal: { name: "Internal", icon: ChatText, color: "#64748b", bg: "bg-slate-50", text: "text-slate-700" },
  "booking.com": { name: "Booking.com", icon: Globe, color: "#003580", bg: "bg-blue-50", text: "text-blue-800" },
  airbnb: { name: "Airbnb", icon: Globe, color: "#FF5A5F", bg: "bg-red-50", text: "text-red-700" },
  expedia: { name: "Expedia", icon: Globe, color: "#FFCC00", bg: "bg-yellow-50", text: "text-yellow-700" },
  website_chat: { name: "Website", icon: ChatCircleDots, color: "#2563eb", bg: "bg-blue-50", text: "text-blue-700" },
};

const PRIORITY_CONFIG = {
  low: { color: "bg-slate-100 text-slate-600", label: "Low" },
  medium: { color: "bg-blue-100 text-blue-700", label: "Medium" },
  high: { color: "bg-orange-100 text-orange-700", label: "High" },
  urgent: { color: "bg-red-100 text-red-700", label: "Urgent" },
};

const STATUS_CONFIG = {
  new: { color: "bg-emerald-500", label: "New" },
  in_progress: { color: "bg-blue-500", label: "In Progress" },
  waiting: { color: "bg-amber-500", label: "Waiting" },
  resolved: { color: "bg-slate-400", label: "Resolved" },
};

const SENTIMENT_ICONS = {
  positive: { icon: Smiley, color: "text-emerald-600" },
  negative: { icon: SmileySad, color: "text-red-500" },
  neutral: { icon: SmileyMeh, color: "text-slate-400" },
};

// ---- Sub-panels shown in right sidebar ----

function GuestDirectoryPanel({ propertyId, onStartConversation, onClose }) {
  const [guests, setGuests] = useState([]);
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (filterType !== "all") params.set("filter_type", filterType);
      const { data } = await axios.get(`${API}/messaging/guests/${propertyId}?${params}`);
      setGuests(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId, search, filterType]);

  useEffect(() => { fetch(); }, [fetch]);

  return (
    <div className="flex flex-col h-full" data-testid="guest-directory-panel">
      <div className="p-3 border-b border-stone-200 bg-stone-50">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
            <AddressBook size={14} className="text-blue-600" /> Guest Directory
          </h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={14} /></button>
        </div>
        <div className="relative mb-2">
          <MagnifyingGlass size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-stone-400" />
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, email, phone..." className="pl-8 h-7 text-[11px] border-stone-200" data-testid="guest-search-input" />
        </div>
        <div className="flex gap-1 flex-wrap">
          {[
            { value: "all", label: "All" },
            { value: "current", label: "In-House" },
            { value: "arriving_today", label: "Arriving" },
            { value: "departing_today", label: "Departing" },
            { value: "upcoming", label: "Upcoming" },
            { value: "past", label: "Past" },
          ].map(f => (
            <button key={f.value} onClick={() => setFilterType(f.value)}
              className={`text-[10px] px-2 py-1 rounded-full transition-colors ${filterType === f.value ? "bg-blue-600 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"}`}
              data-testid={`guest-filter-${f.value}`}>{f.label}</button>
          ))}
        </div>
      </div>
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="p-6 text-center"><ArrowsClockwise size={16} className="mx-auto animate-spin text-stone-300" /></div>
        ) : guests.length === 0 ? (
          <div className="p-6 text-center text-xs text-stone-400">No guests found</div>
        ) : (
          guests.map((g, i) => (
            <div key={i} className="px-3 py-2.5 border-b border-stone-50 hover:bg-stone-50 transition-colors" data-testid={`guest-contact-${i}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-semibold text-stone-800 block truncate">{g.guest_name}</span>
                  {g.guest_email && <span className="text-[10px] text-stone-400 flex items-center gap-1 mt-0.5"><Envelope size={9} /> {g.guest_email}</span>}
                  {g.guest_phone && <span className="text-[10px] text-stone-400 flex items-center gap-1"><Phone size={9} /> {g.guest_phone}</span>}
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[9px] bg-stone-100 text-stone-500 px-1.5 py-0.5 rounded">{g.check_in} — {g.check_out}</span>
                    <span className="text-[9px] text-stone-400">#{g.booking_ref}</span>
                  </div>
                </div>
                <div className="flex flex-col gap-1 ml-2 flex-shrink-0">
                  {g.guest_phone && (
                    <button onClick={() => onStartConversation(g, "whatsapp")} title="WhatsApp"
                      className="w-6 h-6 rounded-full bg-green-50 flex items-center justify-center hover:bg-green-100 transition-colors" data-testid={`wa-btn-${i}`}>
                      <WhatsappLogo size={12} className="text-green-600" weight="fill" />
                    </button>
                  )}
                  {g.guest_email && (
                    <button onClick={() => onStartConversation(g, "email")} title="Email"
                      className="w-6 h-6 rounded-full bg-blue-50 flex items-center justify-center hover:bg-blue-100 transition-colors" data-testid={`email-btn-${i}`}>
                      <Envelope size={12} className="text-blue-600" />
                    </button>
                  )}
                  {g.guest_phone && (
                    <button onClick={() => onStartConversation(g, "telegram")} title="Telegram"
                      className="w-6 h-6 rounded-full bg-sky-50 flex items-center justify-center hover:bg-sky-100 transition-colors" data-testid={`tg-btn-${i}`}>
                      <TelegramLogo size={12} className="text-sky-600" weight="fill" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </ScrollArea>
    </div>
  );
}

function CalendarPanel({ propertyId, onClose }) {
  const [month, setMonth] = useState(() => {
    const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data: d } = await axios.get(`${API}/messaging/calendar/${propertyId}?month=${month}`);
      setData(d);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId, month]);

  useEffect(() => { fetch(); }, [fetch]);

  const changeMonth = (dir) => {
    const [y, m] = month.split("-").map(Number);
    const newM = dir > 0 ? (m === 12 ? 1 : m + 1) : (m === 1 ? 12 : m - 1);
    const newY = dir > 0 ? (m === 12 ? y + 1 : y) : (m === 1 ? y - 1 : y);
    setMonth(`${newY}-${String(newM).padStart(2, "0")}`);
  };

  const getDaysInMonth = () => {
    const [y, m] = month.split("-").map(Number);
    return new Date(y, m, 0).getDate();
  };
  const getFirstDayOfWeek = () => {
    const [y, m] = month.split("-").map(Number);
    return new Date(y, m - 1, 1).getDay();
  };

  const today = new Date().toISOString().split("T")[0];
  const daysCount = getDaysInMonth();
  const firstDay = getFirstDayOfWeek();
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const [y, m] = month.split("-").map(Number);

  return (
    <div className="flex flex-col h-full" data-testid="calendar-panel">
      <div className="p-3 border-b border-stone-200 bg-stone-50">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
            <CalendarBlank size={14} className="text-amber-600" /> Bookings Calendar
          </h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={14} /></button>
        </div>
        <div className="flex items-center justify-between">
          <button onClick={() => changeMonth(-1)} className="text-stone-400 hover:text-stone-600"><CaretLeft size={14} /></button>
          <span className="text-xs font-semibold text-stone-700">{monthNames[m - 1]} {y}</span>
          <button onClick={() => changeMonth(1)} className="text-stone-400 hover:text-stone-600"><CaretRight size={14} /></button>
        </div>
      </div>

      {/* Stats */}
      {data?.stats && (
        <div className="px-3 py-2 border-b border-stone-100 flex gap-3 text-[10px]">
          <span className="text-stone-500">{data.stats.total_bookings} bookings</span>
          <span className="text-emerald-600">{data.stats.today_checkins} check-ins today</span>
          <span className="text-amber-600">{data.stats.today_checkouts} check-outs today</span>
        </div>
      )}

      {loading ? (
        <div className="p-6 text-center"><ArrowsClockwise size={16} className="mx-auto animate-spin text-stone-300" /></div>
      ) : (
        <div className="p-2 flex-1 overflow-y-auto">
          <div className="grid grid-cols-7 gap-px mb-1">
            {["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map(d => (
              <div key={d} className="text-[9px] font-semibold text-stone-400 text-center py-1">{d}</div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-px">
            {Array.from({ length: firstDay }).map((_, i) => <div key={`e${i}`} />)}
            {Array.from({ length: daysCount }).map((_, i) => {
              const day = i + 1;
              const dateStr = `${month}-${String(day).padStart(2, "0")}`;
              const events = data?.day_events?.[dateStr] || [];
              const isToday = dateStr === today;
              const checkins = events.filter(e => e.type === "check_in");
              const checkouts = events.filter(e => e.type === "check_out");
              return (
                <div key={day} className={`rounded-lg p-1 min-h-[42px] text-center relative ${isToday ? "bg-blue-50 ring-1 ring-blue-300" : "hover:bg-stone-50"}`} title={events.map(e => `${e.type === 'check_in' ? 'IN' : 'OUT'}: ${e.guest}`).join('\n')}>
                  <span className={`text-[10px] font-medium ${isToday ? "text-blue-700" : "text-stone-700"}`}>{day}</span>
                  {events.length > 0 && (
                    <div className="flex justify-center gap-0.5 mt-0.5">
                      {checkins.length > 0 && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" title={`${checkins.length} check-in(s)`} />}
                      {checkouts.length > 0 && <span className="w-1.5 h-1.5 rounded-full bg-amber-500" title={`${checkouts.length} check-out(s)`} />}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="mt-2 flex items-center gap-3 text-[10px] text-stone-400 px-1">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Check-in</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Check-out</span>
          </div>

          {/* Today's events */}
          {data?.day_events?.[today]?.length > 0 && (
            <div className="mt-3 px-1">
              <span className="text-[10px] font-semibold text-stone-500 uppercase">Today</span>
              <div className="mt-1 space-y-1">
                {data.day_events[today].map((e, i) => (
                  <div key={i} className={`text-[10px] px-2 py-1.5 rounded ${e.type === "check_in" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                    <span className="font-medium">{e.type === "check_in" ? "IN" : "OUT"}:</span> {e.guest}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AutoRepliesPanel({ propertyId, onClose }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/messaging/auto-replies/${propertyId}`);
      setRules(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetch(); }, [fetch]);

  const toggleRule = async (rule) => {
    try {
      await axios.put(`${API}/messaging/auto-replies/${rule.id}`, { enabled: !rule.enabled });
      setRules(prev => prev.map(r => r.id === rule.id ? { ...r, enabled: !r.enabled } : r));
    } catch (e) { toast.error("Failed to update"); }
  };

  const deleteRule = async (id) => {
    try {
      await axios.delete(`${API}/messaging/auto-replies/${id}`);
      setRules(prev => prev.filter(r => r.id !== id));
      toast.success("Rule deleted");
    } catch (e) { toast.error("Failed to delete"); }
  };

  return (
    <div className="flex flex-col h-full" data-testid="auto-replies-panel">
      <div className="p-3 border-b border-stone-200 bg-stone-50">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm font-semibold text-stone-800 flex items-center gap-1.5">
            <Robot size={14} className="text-purple-600" /> Auto-Reply Rules
          </h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-600"><X size={14} /></button>
        </div>
        <p className="text-[10px] text-stone-400">Auto-respond to common guest questions</p>
      </div>
      <ScrollArea className="flex-1">
        {loading ? (
          <div className="p-6 text-center"><ArrowsClockwise size={16} className="mx-auto animate-spin text-stone-300" /></div>
        ) : (
          rules.map(rule => (
            <div key={rule.id} className={`px-3 py-2.5 border-b border-stone-50 ${!rule.enabled ? "opacity-50" : ""}`} data-testid={`auto-reply-${rule.id}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-stone-800">{rule.name}</span>
                    <span className="text-[9px] bg-purple-50 text-purple-600 px-1.5 py-0.5 rounded-full">{rule.match_count} matches</span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {rule.keywords.slice(0, 4).map(kw => (
                      <span key={kw} className="text-[9px] bg-stone-100 text-stone-500 px-1.5 py-0.5 rounded">{kw}</span>
                    ))}
                    {rule.keywords.length > 4 && <span className="text-[9px] text-stone-400">+{rule.keywords.length - 4}</span>}
                  </div>
                  <p className="text-[10px] text-stone-500 mt-1 line-clamp-2">{rule.response}</p>
                </div>
                <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
                  <Switch checked={rule.enabled} onCheckedChange={() => toggleRule(rule)} className="scale-75" data-testid={`toggle-${rule.id}`} />
                  <button onClick={() => deleteRule(rule.id)} className="text-stone-300 hover:text-red-500 transition-colors"><Trash size={12} /></button>
                </div>
              </div>
            </div>
          ))
        )}
      </ScrollArea>
    </div>
  );
}

// ---- New Conversation Modal ----

function NewConversationModal({ isOpen, onClose, guest, channel, propertyId, onCreated }) {
  const [form, setForm] = useState({ guest_name: "", guest_email: "", guest_phone: "", channel: "whatsapp", message: "" });

  useEffect(() => {
    if (guest) {
      setForm(prev => ({
        ...prev,
        guest_name: guest.guest_name || "",
        guest_email: guest.guest_email || "",
        guest_phone: guest.guest_phone || "",
        channel: channel || "whatsapp",
        booking_ref: guest.booking_ref || "",
      }));
    }
  }, [guest, channel]);

  const send = async () => {
    if (!form.message.trim()) return toast.error("Please type a message");
    if (!form.guest_name.trim()) return toast.error("Guest name is required");
    try {
      const { data } = await axios.post(`${API}/messaging/new-conversation`, { ...form, property_id: propertyId });
      toast.success(`Conversation started via ${CHANNEL_CONFIG[form.channel]?.name || form.channel}`);
      onCreated(data.conversation);
      onClose();
    } catch (e) { toast.error("Failed to create conversation"); }
  };

  const ChannelIcon = CHANNEL_CONFIG[form.channel]?.icon || ChatText;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="new-conversation-modal">
        <DialogHeader>
          <DialogTitle className="text-base flex items-center gap-2">
            <Plus size={16} className="text-emerald-600" /> New Conversation
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-2">
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Guest Name *</label>
            <Input value={form.guest_name} onChange={e => setForm(p => ({ ...p, guest_name: e.target.value }))} placeholder="Guest name" className="h-8 text-sm" data-testid="new-conv-name" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] font-medium text-stone-600 mb-1 block">Email</label>
              <Input value={form.guest_email} onChange={e => setForm(p => ({ ...p, guest_email: e.target.value }))} placeholder="Email" className="h-8 text-sm" data-testid="new-conv-email" />
            </div>
            <div>
              <label className="text-[11px] font-medium text-stone-600 mb-1 block">Phone</label>
              <Input value={form.guest_phone} onChange={e => setForm(p => ({ ...p, guest_phone: e.target.value }))} placeholder="+44..." className="h-8 text-sm" data-testid="new-conv-phone" />
            </div>
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Send via</label>
            <div className="flex gap-2 flex-wrap">
              {["whatsapp", "telegram", "email", "sms", "internal"].map(ch => {
                const cfg = CHANNEL_CONFIG[ch];
                const Icon = cfg.icon;
                const active = form.channel === ch;
                return (
                  <button key={ch} onClick={() => setForm(p => ({ ...p, channel: ch }))}
                    className={`flex items-center gap-1.5 text-[11px] px-3 py-1.5 rounded-lg transition-all font-medium border ${
                      active ? `${cfg.bg} ${cfg.text} border-current` : "bg-white text-stone-500 border-stone-200 hover:bg-stone-50"
                    }`} data-testid={`channel-${ch}`}>
                    <Icon size={13} weight={active ? "fill" : "regular"} /> {cfg.name}
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <label className="text-[11px] font-medium text-stone-600 mb-1 block">Message *</label>
            <Textarea value={form.message} onChange={e => setForm(p => ({ ...p, message: e.target.value }))} placeholder="Type your message..." rows={3} className="text-sm resize-none" data-testid="new-conv-message" />
          </div>
          <button onClick={send}
            className="w-full flex items-center justify-center gap-2 bg-emerald-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors"
            data-testid="new-conv-send-btn">
            <ChannelIcon size={14} weight="fill" /> Send via {CHANNEL_CONFIG[form.channel]?.name}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---- Main Messaging Hub ----

export function MessagingHub({ properties, user, activePropertyId: propActivePropertyId }) {
  const [conversations, setConversations] = useState([]);
  const [selectedConv, setSelectedConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [msgLoading, setMsgLoading] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [aiSuggesting, setAiSuggesting] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState("");
  const [quickReplies, setQuickReplies] = useState([]);
  const [showQuickReplies, setShowQuickReplies] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterChannel, setFilterChannel] = useState("all");
  const [search, setSearch] = useState("");
  // Right panel state
  const [rightPanel, setRightPanel] = useState("profile"); // profile, directory, calendar, autoreplies
  // New conversation modal
  const [newConvOpen, setNewConvOpen] = useState(false);
  const [newConvGuest, setNewConvGuest] = useState(null);
  const [newConvChannel, setNewConvChannel] = useState("whatsapp");

  const messagesEndRef = useRef(null);
  const activePropertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });

  const fetchConversations = useCallback(async () => {
    try {
      let url = `${API}/messaging/conversations/${activePropertyId}`;
      const params = [];
      if (filterStatus !== "all") params.push(`status=${filterStatus}`);
      if (filterChannel !== "all") params.push(`channel=${filterChannel}`);
      if (params.length) url += `?${params.join("&")}`;
      const { data } = await axios.get(url);
      setConversations(data);
    } catch (e) { console.error(e); }
  }, [activePropertyId, filterStatus, filterChannel]);

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/messaging/conversations/${activePropertyId}/stats`);
      setStats(data);
    } catch (e) { console.error(e); }
  }, [activePropertyId]);

  const fetchMessages = useCallback(async (convId) => {
    setMsgLoading(true);
    try {
      const { data } = await axios.get(`${API}/messaging/messages/${convId}`);
      setMessages(data);
      setTimeout(scrollToBottom, 100);
    } catch (e) { console.error(e); }
    finally { setMsgLoading(false); }
  }, []);

  const fetchQuickReplies = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/messaging/quick-replies`);
      setQuickReplies(data);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      try { await axios.post(`${API}/messaging/seed/${activePropertyId}`); } catch (e) { /* already seeded */ }
      await Promise.all([fetchConversations(), fetchStats(), fetchQuickReplies()]);
      setLoading(false);
    };
    init();
  }, [activePropertyId, fetchConversations, fetchStats, fetchQuickReplies]);

  useEffect(() => { fetchConversations(); }, [filterStatus, filterChannel, fetchConversations]);

  const selectConversation = (conv) => {
    setSelectedConv(conv);
    setAiSuggestion("");
    setInput("");
    setRightPanel("profile");
    fetchMessages(conv.id);
    setConversations(prev => prev.map(c => c.id === conv.id ? { ...c, unread_count: 0 } : c));
  };

  const sendMessage = async () => {
    if (!input.trim() || !selectedConv) return;
    setSending(true);
    try {
      const { data } = await axios.post(`${API}/messaging/messages`, {
        conversation_id: selectedConv.id, content: input.trim(), channel: selectedConv.channel,
      });
      setMessages(prev => [...prev, data]);
      setInput("");
      setAiSuggestion("");
      setTimeout(scrollToBottom, 100);

      // Try auto-reply check for the last guest message
      const lastGuestMsg = [...messages].reverse().find(m => m.sender_type === "guest");
      if (lastGuestMsg) {
        // just update stats quietly, auto-reply already handled on receive
      }

      fetchConversations();
      fetchStats();
    } catch (e) { toast.error("Failed to send message"); }
    finally { setSending(false); }
  };

  const getAiSuggestion = async () => {
    if (!selectedConv) return;
    setAiSuggesting(true);
    const lastGuestMsg = [...messages].reverse().find(m => m.sender_type === "guest");
    try {
      const { data } = await axios.post(`${API}/messaging/messages/ai-suggest?conversation_id=${selectedConv.id}&guest_message=${encodeURIComponent(lastGuestMsg?.content || "")}&property_id=${activePropertyId}`);
      setAiSuggestion(data.suggestion);
      setInput(data.suggestion);
    } catch (e) { toast.error("AI suggestion failed"); }
    finally { setAiSuggesting(false); }
  };

  const checkAutoReply = async () => {
    const lastGuestMsg = [...messages].reverse().find(m => m.sender_type === "guest");
    if (!lastGuestMsg) return;
    try {
      const { data } = await axios.post(`${API}/messaging/auto-replies/check?property_id=${activePropertyId}&message=${encodeURIComponent(lastGuestMsg.content)}`);
      if (data.matched) {
        setInput(data.response);
        toast.success(`Auto-reply matched: ${data.rule_name}`, { description: "Response loaded. Click Send to reply." });
      } else {
        toast("No auto-reply match", { description: "Try AI Suggest for a custom response" });
      }
    } catch (e) { console.error(e); }
  };

  const applyQuickReply = (qr) => {
    setInput(qr.content);
    setShowQuickReplies(false);
    axios.post(`${API}/messaging/quick-replies/${qr.id}/use`).catch(() => {});
  };

  const resolveConversation = async () => {
    if (!selectedConv) return;
    try {
      await axios.post(`${API}/messaging/conversations/${selectedConv.id}/resolve`);
      setSelectedConv(prev => ({ ...prev, status: "resolved" }));
      fetchConversations(); fetchStats();
      toast.success("Conversation resolved");
    } catch (e) { toast.error("Failed to resolve"); }
  };

  const assignToMe = async () => {
    if (!selectedConv) return;
    try {
      await axios.post(`${API}/messaging/conversations/${selectedConv.id}/assign?user_id=${user?.id || "admin"}&user_name=${encodeURIComponent(user?.name || "Admin")}`);
      setSelectedConv(prev => ({ ...prev, assigned_to: user?.id, assigned_name: user?.name, status: "in_progress" }));
      fetchConversations();
      toast.success("Assigned to you");
    } catch (e) { toast.error("Failed to assign"); }
  };

  const startConversation = (guest, channel) => {
    setNewConvGuest(guest);
    setNewConvChannel(channel);
    setNewConvOpen(true);
  };

  const onConversationCreated = (conv) => {
    setConversations(prev => [conv, ...prev]);
    selectConversation(conv);
    fetchStats();
  };

  const filtered = conversations.filter(c => {
    if (search) {
      const s = search.toLowerCase();
      return c.guest_name.toLowerCase().includes(s) || c.guest_email.toLowerCase().includes(s) || c.last_message_preview.toLowerCase().includes(s);
    }
    return true;
  });

  const channelBadge = (channel) => {
    const cfg = CHANNEL_CONFIG[channel] || CHANNEL_CONFIG.internal;
    const Icon = cfg.icon;
    return (
      <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${cfg.bg} ${cfg.text}`}>
        <Icon size={10} weight="fill" /> {cfg.name}
      </span>
    );
  };

  return (
    <div className="h-[calc(100vh-0px)] flex flex-col" data-testid="messaging-hub">
      {/* Stats Bar */}
      <div className="border-b border-stone-200 bg-white px-5 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-6">
          <h2 className="text-lg font-semibold text-stone-900 flex items-center gap-2">
            <ChatText size={20} weight="fill" className="text-emerald-600" /> Guest Messaging
          </h2>
          {stats && (
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" /> {stats.new} new</span>
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-500" /> {stats.in_progress} active</span>
              <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-500" /> {stats.waiting} waiting</span>
              <span className="text-stone-400">|</span>
              <span className="text-stone-500">{stats.total} total</span>
            </div>
          )}
        </div>
        <button onClick={() => { setNewConvGuest(null); setNewConvChannel("whatsapp"); setNewConvOpen(true); }}
          className="text-xs bg-emerald-600 text-white px-3 py-1.5 rounded-lg hover:bg-emerald-700 flex items-center gap-1.5 font-medium transition-colors"
          data-testid="new-conversation-btn">
          <Plus size={12} weight="bold" /> New Conversation
        </button>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Conversation List */}
        <div className="w-[340px] border-r border-stone-200 bg-white flex flex-col flex-shrink-0" data-testid="conversation-list-panel">
          {/* Search + Filters */}
          <div className="p-3 border-b border-stone-100 space-y-2">
            <div className="relative">
              <MagnifyingGlass size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
              <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search guests..." className="pl-9 h-8 text-xs border-stone-200" data-testid="msg-search" />
            </div>
            <div className="flex gap-2">
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="h-7 text-[11px] border-stone-200 flex-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="new">New</SelectItem>
                  <SelectItem value="in_progress">In Progress</SelectItem>
                  <SelectItem value="waiting">Waiting</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filterChannel} onValueChange={setFilterChannel}>
                <SelectTrigger className="h-7 text-[11px] border-stone-200 flex-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Channels</SelectItem>
                  <SelectItem value="whatsapp">WhatsApp</SelectItem>
                  <SelectItem value="telegram">Telegram</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="sms">SMS</SelectItem>
                  <SelectItem value="booking.com">Booking.com</SelectItem>
                  <SelectItem value="website_chat">Website</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* List */}
          <ScrollArea className="flex-1">
            {loading ? (
              <div className="p-8 text-center"><ArrowsClockwise size={20} className="mx-auto animate-spin text-stone-300" /></div>
            ) : filtered.length === 0 ? (
              <div className="p-8 text-center"><ChatText size={24} className="mx-auto mb-2 text-stone-300" /><p className="text-xs text-stone-400">No conversations</p></div>
            ) : (
              filtered.map(conv => {
                const isActive = selectedConv?.id === conv.id;
                const cfg = CHANNEL_CONFIG[conv.channel] || CHANNEL_CONFIG.internal;
                const pri = PRIORITY_CONFIG[conv.priority] || PRIORITY_CONFIG.medium;
                const SentIcon = SENTIMENT_ICONS[conv.sentiment]?.icon || SmileyMeh;
                const sentColor = SENTIMENT_ICONS[conv.sentiment]?.color || "text-slate-400";
                return (
                  <div key={conv.id} onClick={() => selectConversation(conv)}
                    className={`px-3 py-3 border-b border-stone-50 cursor-pointer transition-colors ${isActive ? "bg-blue-50 border-l-2 border-l-blue-500" : "hover:bg-stone-50 border-l-2 border-l-transparent"}`}
                    data-testid={`conv-${conv.id}`}>
                    <div className="flex items-start gap-2.5">
                      <div className="relative flex-shrink-0">
                        <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-xs font-bold" style={{ background: cfg.color }}>
                          {conv.guest_name.charAt(0).toUpperCase()}
                        </div>
                        {conv.unread_count > 0 && (
                          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[9px] flex items-center justify-center font-bold">{conv.unread_count}</span>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <span className={`text-sm font-medium truncate ${conv.unread_count > 0 ? "text-stone-900" : "text-stone-700"}`}>{conv.guest_name}</span>
                          <span className="text-[10px] text-stone-400 flex-shrink-0">{new Date(conv.last_message_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}</span>
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          {channelBadge(conv.channel)}
                          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${pri.color}`}>{pri.label}</span>
                          <SentIcon size={12} className={sentColor} weight="fill" />
                        </div>
                        <p className={`text-xs mt-1 truncate ${conv.unread_count > 0 ? "text-stone-700 font-medium" : "text-stone-500"}`}>{conv.last_message_preview}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${STATUS_CONFIG[conv.status]?.color || "bg-slate-400"}`} />
                          <span className="text-[10px] text-stone-400">{STATUS_CONFIG[conv.status]?.label}</span>
                          {conv.assigned_name && <span className="text-[10px] text-stone-400">· {conv.assigned_name}</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </ScrollArea>
        </div>

        {/* Chat Area */}
        {selectedConv ? (
          <div className="flex-1 flex flex-col bg-stone-50" data-testid="chat-area">
            {/* Header */}
            <div className="bg-white border-b border-stone-200 px-5 py-3 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold" style={{ background: CHANNEL_CONFIG[selectedConv.channel]?.color || "#64748b" }}>
                  {selectedConv.guest_name.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-stone-900" data-testid="chat-guest-name">{selectedConv.guest_name}</h3>
                    {channelBadge(selectedConv.channel)}
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${PRIORITY_CONFIG[selectedConv.priority]?.color}`}>
                      {PRIORITY_CONFIG[selectedConv.priority]?.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-stone-400 mt-0.5">
                    {selectedConv.guest_email && <span className="flex items-center gap-1"><Envelope size={10} /> {selectedConv.guest_email}</span>}
                    {selectedConv.guest_phone && <span className="flex items-center gap-1"><Phone size={10} /> {selectedConv.guest_phone}</span>}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selectedConv.status !== "resolved" && (
                  <>
                    {!selectedConv.assigned_to && (
                      <button onClick={assignToMe} className="text-xs bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-100 transition-colors font-medium" data-testid="assign-to-me-btn">
                        Assign to me
                      </button>
                    )}
                    <button onClick={resolveConversation} className="text-xs bg-emerald-50 text-emerald-700 px-3 py-1.5 rounded-lg hover:bg-emerald-100 transition-colors font-medium flex items-center gap-1" data-testid="resolve-btn">
                      <CheckCircle size={12} weight="fill" /> Resolve
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Tags */}
            {selectedConv.tags?.length > 0 && (
              <div className="bg-white border-b border-stone-100 px-5 py-2 flex items-center gap-1.5">
                <Tag size={12} className="text-stone-400" />
                {selectedConv.tags.map(t => (
                  <span key={t} className="text-[10px] bg-stone-100 text-stone-600 px-2 py-0.5 rounded-full">{t}</span>
                ))}
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3" data-testid="messages-area">
              {msgLoading ? (
                <div className="flex justify-center py-10"><ArrowsClockwise size={20} className="animate-spin text-stone-300" /></div>
              ) : (
                <AnimatePresence>
                  {messages.map((msg) => {
                    const isGuest = msg.sender_type === "guest";
                    const isAI = msg.sender_type === "ai";
                    const isSystem = msg.sender_type === "system";
                    return (
                      <motion.div key={msg.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                        className={`flex ${isGuest ? "justify-start" : "justify-end"}`}>
                        {isSystem ? (
                          <div className="w-full text-center"><span className="text-[10px] text-stone-400 bg-stone-100 px-3 py-1 rounded-full">{msg.content}</span></div>
                        ) : (
                          <div className="max-w-[70%]">
                            <div className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                              isGuest ? "bg-white border border-stone-200 rounded-bl-md text-stone-800"
                              : isAI ? "bg-purple-50 border border-purple-200 rounded-br-md text-purple-900"
                              : "bg-emerald-600 text-white rounded-br-md"
                            }`}>
                              {msg.content}
                            </div>
                            <div className={`flex items-center gap-2 mt-1 text-[10px] text-stone-400 ${isGuest ? "" : "justify-end"}`}>
                              {!isGuest && msg.sender_name && <span>{msg.sender_name}</span>}
                              {isAI && <span className="flex items-center gap-0.5"><Robot size={10} /> AI</span>}
                              {msg.sender_type === "auto_reply" && <span className="flex items-center gap-0.5"><Robot size={10} /> Auto</span>}
                              <span>{new Date(msg.created_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</span>
                            </div>
                          </div>
                        )}
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* AI Suggestion Banner */}
            {aiSuggestion && (
              <div className="mx-5 mb-2 bg-purple-50 border border-purple-200 rounded-lg px-4 py-2.5 flex items-start gap-3" data-testid="ai-suggestion-banner">
                <Sparkle size={16} className="text-purple-600 mt-0.5 flex-shrink-0" weight="fill" />
                <div className="flex-1 min-w-0">
                  <span className="text-[10px] font-semibold text-purple-700 uppercase">AI Suggestion</span>
                  <p className="text-xs text-purple-800 mt-0.5">{aiSuggestion}</p>
                </div>
                <button onClick={() => setAiSuggestion("")} className="text-purple-400 hover:text-purple-600"><X size={14} /></button>
              </div>
            )}

            {/* Quick Replies Dropdown */}
            <AnimatePresence>
              {showQuickReplies && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }}
                  className="mx-5 mb-2 bg-white border border-stone-200 rounded-lg shadow-lg max-h-48 overflow-y-auto" data-testid="quick-replies-panel">
                  {quickReplies.map(qr => (
                    <button key={qr.id} onClick={() => applyQuickReply(qr)}
                      className="w-full text-left px-3 py-2 hover:bg-stone-50 border-b border-stone-50 last:border-0 transition-colors">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-stone-800">{qr.name}</span>
                        {qr.shortcut && <code className="text-[10px] bg-stone-100 text-stone-500 px-1.5 rounded">{qr.shortcut}</code>}
                      </div>
                      <p className="text-[11px] text-stone-500 truncate mt-0.5">{qr.content}</p>
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Input Area */}
            {selectedConv.status !== "resolved" && (
              <div className="bg-white border-t border-stone-200 px-5 py-3 flex-shrink-0" data-testid="message-input-area">
                <div className="flex items-center gap-2 mb-2">
                  <button onClick={() => setShowQuickReplies(!showQuickReplies)}
                    className="text-xs bg-stone-100 text-stone-600 px-2.5 py-1.5 rounded-lg hover:bg-stone-200 transition-colors flex items-center gap-1" data-testid="quick-replies-btn">
                    <Lightning size={12} /> Quick Replies
                  </button>
                  <button onClick={checkAutoReply}
                    className="text-xs bg-amber-50 text-amber-700 px-2.5 py-1.5 rounded-lg hover:bg-amber-100 transition-colors flex items-center gap-1" data-testid="auto-reply-btn">
                    <Robot size={12} /> Auto-Reply
                  </button>
                  <button onClick={getAiSuggestion} disabled={aiSuggesting}
                    className="text-xs bg-purple-50 text-purple-700 px-2.5 py-1.5 rounded-lg hover:bg-purple-100 transition-colors flex items-center gap-1 disabled:opacity-50" data-testid="ai-suggest-btn">
                    <Sparkle size={12} weight="fill" /> {aiSuggesting ? "Thinking..." : "AI Suggest"}
                  </button>
                </div>
                <div className="flex gap-2">
                  <Input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()}
                    placeholder="Type your reply..." className="flex-1 border-stone-200 text-sm" data-testid="message-input" />
                  <button onClick={sendMessage} disabled={!input.trim() || sending}
                    className="bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-40 flex items-center gap-1.5 text-sm font-medium" data-testid="send-message-btn">
                    <PaperPlaneTilt size={14} weight="fill" /> Send
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-stone-50" data-testid="no-conversation-selected">
            <div className="text-center">
              <div className="w-16 h-16 rounded-2xl bg-stone-100 flex items-center justify-center mx-auto mb-4">
                <ChatText size={28} className="text-stone-300" />
              </div>
              <p className="text-sm font-medium text-stone-400">Select a conversation</p>
              <p className="text-xs text-stone-300 mt-1">Choose from the list or start a new one</p>
            </div>
          </div>
        )}

        {/* Right Sidebar — Profile / Directory / Calendar / Auto-Replies */}
        <div className="w-[280px] border-l border-stone-200 bg-white flex-shrink-0 flex flex-col" data-testid="right-sidebar">
          {/* Tab buttons */}
          <div className="flex border-b border-stone-200 bg-stone-50 flex-shrink-0">
            {[
              { id: "profile", icon: ChatText, label: "Chat" },
              { id: "directory", icon: AddressBook, label: "Guests" },
              { id: "calendar", icon: CalendarBlank, label: "Calendar" },
              { id: "autoreplies", icon: Robot, label: "FAQ Bot" },
            ].map(tab => (
              <button key={tab.id} onClick={() => setRightPanel(tab.id)}
                className={`flex-1 flex flex-col items-center gap-0.5 py-2.5 text-[10px] font-medium transition-colors ${
                  rightPanel === tab.id ? "text-emerald-700 border-b-2 border-emerald-500 bg-white" : "text-stone-400 hover:text-stone-600"
                }`} data-testid={`tab-${tab.id}`}>
                <tab.icon size={14} weight={rightPanel === tab.id ? "fill" : "regular"} />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Panel content */}
          <div className="flex-1 overflow-hidden">
            {rightPanel === "profile" && selectedConv && (
              <div className="h-full overflow-y-auto" data-testid="guest-profile-sidebar">
                <div className="p-4 border-b border-stone-100 text-center">
                  <div className="w-14 h-14 rounded-full mx-auto flex items-center justify-center text-white text-xl font-bold mb-2" style={{ background: CHANNEL_CONFIG[selectedConv.channel]?.color || "#64748b" }}>
                    {selectedConv.guest_name.charAt(0).toUpperCase()}
                  </div>
                  <h4 className="text-sm font-semibold text-stone-900">{selectedConv.guest_name}</h4>
                  <p className="text-[11px] text-stone-400 mt-0.5">{selectedConv.guest_email}</p>
                  {selectedConv.guest_phone && <p className="text-[11px] text-stone-400">{selectedConv.guest_phone}</p>}
                </div>
                <div className="p-4 space-y-4">
                  <div>
                    <span className="text-[10px] font-semibold text-stone-400 uppercase tracking-wider">Details</span>
                    <div className="mt-2 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-stone-500">Channel</span>
                        {channelBadge(selectedConv.channel)}
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-stone-500">Status</span>
                        <span className="flex items-center gap-1.5">
                          <span className={`w-2 h-2 rounded-full ${STATUS_CONFIG[selectedConv.status]?.color}`} />
                          {STATUS_CONFIG[selectedConv.status]?.label}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-stone-500">Priority</span>
                        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${PRIORITY_CONFIG[selectedConv.priority]?.color}`}>
                          {PRIORITY_CONFIG[selectedConv.priority]?.label}
                        </span>
                      </div>
                      {selectedConv.assigned_name && (
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-stone-500">Assigned</span>
                          <span className="text-stone-700 font-medium">{selectedConv.assigned_name}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  {selectedConv.tags?.length > 0 && (
                    <div>
                      <span className="text-[10px] font-semibold text-stone-400 uppercase tracking-wider">Tags</span>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {selectedConv.tags.map(t => (
                          <span key={t} className="text-[10px] bg-stone-100 text-stone-600 px-2 py-0.5 rounded-full">{t}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div>
                    <span className="text-[10px] font-semibold text-stone-400 uppercase tracking-wider">Actions</span>
                    <div className="mt-2 space-y-1.5">
                      <button onClick={() => {
                        axios.put(`${API}/messaging/conversations/${selectedConv.id}`, { priority: "urgent" }).then(() => {
                          setSelectedConv(p => ({ ...p, priority: "urgent" }));
                          fetchConversations();
                          toast.success("Marked as urgent");
                        });
                      }} className="w-full text-left text-xs bg-red-50 text-red-700 px-3 py-2 rounded-lg hover:bg-red-100 transition-colors flex items-center gap-2" data-testid="mark-urgent-btn">
                        <WarningCircle size={14} weight="fill" /> Mark Urgent
                      </button>
                      <button onClick={() => {
                        axios.put(`${API}/messaging/conversations/${selectedConv.id}`, { priority: "low" }).then(() => {
                          setSelectedConv(p => ({ ...p, priority: "low" }));
                          fetchConversations();
                          toast.success("Priority lowered");
                        });
                      }} className="w-full text-left text-xs bg-stone-50 text-stone-600 px-3 py-2 rounded-lg hover:bg-stone-100 transition-colors flex items-center gap-2" data-testid="lower-priority-btn">
                        <Clock size={14} /> Lower Priority
                      </button>
                    </div>
                  </div>
                  <div className="text-[10px] text-stone-400 pt-2 border-t border-stone-100">
                    Created: {new Date(selectedConv.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
                  </div>
                </div>
              </div>
            )}

            {rightPanel === "profile" && !selectedConv && (
              <div className="flex items-center justify-center h-full">
                <p className="text-xs text-stone-400">Select a conversation to see details</p>
              </div>
            )}

            {rightPanel === "directory" && (
              <GuestDirectoryPanel propertyId={activePropertyId} onStartConversation={startConversation} onClose={() => setRightPanel("profile")} />
            )}

            {rightPanel === "calendar" && (
              <CalendarPanel propertyId={activePropertyId} onClose={() => setRightPanel("profile")} />
            )}

            {rightPanel === "autoreplies" && (
              <AutoRepliesPanel propertyId={activePropertyId} onClose={() => setRightPanel("profile")} />
            )}
          </div>
        </div>
      </div>

      {/* New Conversation Modal */}
      <NewConversationModal
        isOpen={newConvOpen} onClose={() => setNewConvOpen(false)}
        guest={newConvGuest} channel={newConvChannel}
        propertyId={activePropertyId} onCreated={onConversationCreated}
      />
    </div>
  );
}
