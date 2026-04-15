import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  PaperPlaneTilt, CheckCircle, Clock, Upload, Eye, X, UserCircle,
  ArrowsClockwise, Envelope, Smiley, WarningCircle, CaretRight,
} from "@phosphor-icons/react";
import { FileText, Send, Users, Shield, Camera, ChevronDown, ExternalLink } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BASE_URL = process.env.REACT_APP_BACKEND_URL;

export function GuestJourneyPanel({ properties, activePropertyId: propActivePropertyId }) {
  const activePropertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");
  const [registrations, setRegistrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedReg, setSelectedReg] = useState(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sendingLink, setSendingLink] = useState(null);
  const [sendingSatisfaction, setSendingSatisfaction] = useState(false);
  const [uploadingId, setUploadingId] = useState(null);
  const fileInputRef = useRef(null);

  // Fetch bookings for "send link" 
  const [bookings, setBookings] = useState([]);
  const [showSendDialog, setShowSendDialog] = useState(false);
  const [tab, setTab] = useState("registrations"); // registrations | satisfaction

  const fetchRegistrations = useCallback(async () => {
    if (!activePropertyId) return;
    try {
      const { data } = await axios.get(`${API}/guest-journey/registrations/${activePropertyId}`);
      setRegistrations(data);
    } catch (e) {
      console.error("Failed to load registrations", e);
    }
    setLoading(false);
  }, [activePropertyId]);

  const fetchBookings = useCallback(async () => {
    if (!activePropertyId) return;
    try {
      const { data } = await axios.get(`${API}/bookings?property_id=${activePropertyId}&status=confirmed`);
      setBookings(Array.isArray(data) ? data : (data.bookings || []));
    } catch { }
  }, [activePropertyId]);

  useEffect(() => { fetchRegistrations(); fetchBookings(); }, [fetchRegistrations, fetchBookings]);

  const sendRegistrationLink = async (bookingId) => {
    setSendingLink(bookingId);
    try {
      const { data } = await axios.post(`${API}/guest-journey/send-registration/${bookingId}`);
      toast.success("Registration link sent!");
      setShowSendDialog(false);
      fetchRegistrations();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to send link");
    }
    setSendingLink(null);
  };

  const sendSatisfactionChecks = async () => {
    setSendingSatisfaction(true);
    try {
      const { data } = await axios.post(`${API}/guest-journey/send-satisfaction-check/${activePropertyId}`);
      toast.success(`Satisfaction checks sent to ${data.sent} guests`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to send checks");
    }
    setSendingSatisfaction(false);
  };

  const handleReceptionUpload = async (bookingId, file) => {
    setUploadingId(bookingId);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await axios.post(`${API}/guest-journey/reception-upload-id/${bookingId}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("ID uploaded successfully");
      fetchRegistrations();
    } catch (e) {
      toast.error("Upload failed");
    }
    setUploadingId(null);
  };

  const filtered = registrations.filter(r => {
    if (filter === "completed" && r.status !== "completed") return false;
    if (filter === "pending" && r.status !== "pending") return false;
    if (search && !r.guest_name?.toLowerCase().includes(search.toLowerCase()) && !r.booking_ref?.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const stats = {
    total: registrations.length,
    completed: registrations.filter(r => r.status === "completed").length,
    pending: registrations.filter(r => r.status === "pending").length,
    idUploaded: registrations.filter(r => r.id_uploaded).length,
  };

  return (
    <div className="p-6 space-y-6" data-testid="guest-journey-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-stone-800" data-testid="guest-journey-title">Guest Journey</h1>
          <p className="text-sm text-stone-500 mt-0.5">Pre-arrival registration, ID verification & satisfaction checks</p>
        </div>
        <div className="flex gap-2">
          <button data-testid="btn-send-satisfaction" onClick={sendSatisfactionChecks} disabled={sendingSatisfaction} className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition flex items-center gap-2">
            <Smiley size={16} weight="fill" />
            {sendingSatisfaction ? "Sending..." : "Satisfaction Check"}
          </button>
          <button data-testid="btn-open-send-dialog" onClick={() => { fetchBookings(); setShowSendDialog(true); }} className="px-4 py-2 bg-[#1e3a5f] text-white text-sm font-medium rounded-lg hover:bg-[#15304f] transition flex items-center gap-2">
            <PaperPlaneTilt size={16} weight="fill" />
            Send Registration Link
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4" data-testid="journey-stats">
        {[
          { label: "Total Sent", value: stats.total, color: "bg-blue-50 text-blue-700", icon: <Envelope size={18} className="text-blue-500" /> },
          { label: "Completed", value: stats.completed, color: "bg-emerald-50 text-emerald-700", icon: <CheckCircle size={18} className="text-emerald-500" weight="fill" /> },
          { label: "Pending", value: stats.pending, color: "bg-amber-50 text-amber-700", icon: <Clock size={18} className="text-amber-500" weight="fill" /> },
          { label: "IDs Uploaded", value: stats.idUploaded, color: "bg-violet-50 text-violet-700", icon: <Shield size={18} className="text-violet-500" /> },
        ].map((s, i) => (
          <div key={i} className={`${s.color} rounded-xl p-4 flex items-center gap-3`} data-testid={`stat-${s.label.toLowerCase().replace(/ /g, "-")}`}>
            {s.icon}
            <div>
              <p className="text-2xl font-bold">{s.value}</p>
              <p className="text-xs font-medium opacity-70">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-stone-100 p-1 rounded-lg w-fit" data-testid="journey-tabs">
        {[
          { id: "registrations", label: "Registrations", icon: <FileText size={14} /> },
          { id: "satisfaction", label: "Satisfaction", icon: <Smiley size={14} /> },
        ].map(t => (
          <button key={t.id} data-testid={`tab-${t.id}`} onClick={() => setTab(t.id)} className={`px-4 py-2 text-sm font-medium rounded-md flex items-center gap-2 transition ${tab === t.id ? "bg-white shadow-sm text-stone-800" : "text-stone-500 hover:text-stone-700"}`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === "registrations" && (
        <>
          {/* Filters */}
          <div className="flex items-center gap-3" data-testid="journey-filters">
            <Input data-testid="search-registrations" placeholder="Search guest or booking ref..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
            <Select value={filter} onValueChange={setFilter}>
              <SelectTrigger className="w-40" data-testid="filter-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
              </SelectContent>
            </Select>
            <button onClick={fetchRegistrations} className="p-2 text-stone-400 hover:text-stone-600 transition" data-testid="btn-refresh">
              <ArrowsClockwise size={18} />
            </button>
          </div>

          {/* Registrations Table */}
          <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden" data-testid="registrations-table">
            <div className="grid grid-cols-[1fr_120px_100px_80px_80px_100px_80px] gap-2 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wide border-b">
              <span>Guest</span><span>Booking Ref</span><span>Status</span><span>ID</span><span>T&C</span><span>Date</span><span>Actions</span>
            </div>
            <ScrollArea className="max-h-[400px]">
              {loading ? (
                <div className="p-8 text-center text-stone-400 text-sm">Loading...</div>
              ) : filtered.length === 0 ? (
                <div className="p-8 text-center text-stone-400 text-sm" data-testid="no-registrations">
                  No registrations yet. Send a registration link to get started.
                </div>
              ) : (
                filtered.map(reg => (
                  <div key={reg.id} className="grid grid-cols-[1fr_120px_100px_80px_80px_100px_80px] gap-2 px-4 py-3 border-b border-stone-100 items-center hover:bg-stone-50/50 transition cursor-pointer" onClick={() => setSelectedReg(reg)} data-testid={`reg-row-${reg.id}`}>
                    <div className="flex items-center gap-2">
                      <UserCircle size={20} className="text-stone-400" />
                      <div>
                        <p className="text-sm font-medium text-stone-800 truncate">{reg.guest_name || "—"}</p>
                        <p className="text-[11px] text-stone-400 truncate">{reg.guest_email || ""}</p>
                      </div>
                    </div>
                    <span className="text-xs font-mono text-stone-600">{reg.booking_ref || "—"}</span>
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full w-fit ${reg.status === "completed" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                      {reg.status === "completed" ? <CheckCircle size={12} weight="fill" /> : <Clock size={12} weight="fill" />}
                      {reg.status === "completed" ? "Done" : "Pending"}
                    </span>
                    <span>{reg.id_uploaded ? <CheckCircle size={16} className="text-emerald-500" weight="fill" /> : <X size={16} className="text-stone-300" />}</span>
                    <span>{reg.terms_accepted ? <CheckCircle size={16} className="text-emerald-500" weight="fill" /> : <X size={16} className="text-stone-300" />}</span>
                    <span className="text-xs text-stone-500">{reg.created_at ? new Date(reg.created_at).toLocaleDateString() : "—"}</span>
                    <div className="flex gap-1">
                      <button onClick={(e) => { e.stopPropagation(); setSelectedReg(reg); }} className="p-1.5 rounded-md hover:bg-stone-100 text-stone-400 hover:text-stone-600 transition" data-testid={`btn-view-reg-${reg.id}`}>
                        <Eye size={14} />
                      </button>
                      {!reg.id_uploaded && (
                        <button onClick={(e) => { e.stopPropagation(); fileInputRef.current?.setAttribute("data-booking", reg.booking_id); fileInputRef.current?.click(); }} className="p-1.5 rounded-md hover:bg-stone-100 text-stone-400 hover:text-stone-600 transition" data-testid={`btn-upload-for-${reg.id}`}>
                          <Camera size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </ScrollArea>
          </div>
          <input ref={fileInputRef} type="file" accept="image/*,.pdf" className="hidden" onChange={(e) => {
            const bookingId = fileInputRef.current?.getAttribute("data-booking");
            if (bookingId && e.target.files?.[0]) handleReceptionUpload(bookingId, e.target.files[0]);
            e.target.value = "";
          }} />
        </>
      )}

      {tab === "satisfaction" && (
        <SatisfactionTab propertyId={activePropertyId} />
      )}

      {/* Send Registration Link Dialog */}
      <AnimatePresence>
        {showSendDialog && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setShowSendDialog(false)}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="bg-white rounded-2xl shadow-xl max-w-lg w-full max-h-[70vh] overflow-hidden" onClick={(e) => e.stopPropagation()} data-testid="send-link-dialog">
              <div className="p-5 border-b border-stone-100 flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-stone-800">Send Registration Link</h3>
                  <p className="text-xs text-stone-500 mt-0.5">Select a booking to send the pre-arrival registration link</p>
                </div>
                <button onClick={() => setShowSendDialog(false)} className="p-1.5 hover:bg-stone-100 rounded-lg transition">
                  <X size={18} className="text-stone-400" />
                </button>
              </div>
              <ScrollArea className="max-h-[50vh]">
                <div className="p-4 space-y-2">
                  {bookings.length === 0 ? (
                    <p className="text-sm text-stone-400 text-center py-8">No upcoming bookings found</p>
                  ) : (
                    bookings.map(b => {
                      const alreadySent = registrations.some(r => r.booking_id === b.id);
                      return (
                        <div key={b.id} className="flex items-center justify-between p-3 rounded-xl border border-stone-200/60 hover:bg-stone-50 transition" data-testid={`booking-item-${b.id}`}>
                          <div>
                            <p className="text-sm font-medium text-stone-800">{b.guest_name || "Guest"}</p>
                            <p className="text-xs text-stone-500">{b.booking_ref} &middot; {b.check_in} &rarr; {b.check_out}</p>
                            <p className="text-xs text-stone-400">{b.guest_email || "No email"}</p>
                          </div>
                          {alreadySent ? (
                            <span className="text-xs text-emerald-600 font-medium flex items-center gap-1"><CheckCircle size={14} weight="fill" /> Sent</span>
                          ) : (
                            <button data-testid={`btn-send-link-${b.id}`} onClick={() => sendRegistrationLink(b.id)} disabled={sendingLink === b.id || !b.guest_email} className="px-3 py-1.5 bg-[#1e3a5f] text-white text-xs font-medium rounded-lg hover:bg-[#15304f] disabled:opacity-40 transition flex items-center gap-1.5">
                              <Send size={12} />
                              {sendingLink === b.id ? "Sending..." : "Send Link"}
                            </button>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </ScrollArea>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Registration Detail Drawer */}
      <AnimatePresence>
        {selectedReg && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/40 flex items-center justify-end z-50" onClick={() => setSelectedReg(null)}>
            <motion.div initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 300 }} className="bg-white h-full w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()} data-testid="registration-detail-drawer">
              <div className="p-5 border-b border-stone-100 flex items-center justify-between">
                <h3 className="font-semibold text-stone-800">Registration Details</h3>
                <button onClick={() => setSelectedReg(null)} className="p-1.5 hover:bg-stone-100 rounded-lg transition" data-testid="close-detail-drawer">
                  <X size={18} className="text-stone-400" />
                </button>
              </div>
              <ScrollArea className="h-[calc(100vh-64px)]">
                <div className="p-5 space-y-4">
                  {/* Status */}
                  <div className={`p-3 rounded-xl text-center ${selectedReg.status === "completed" ? "bg-emerald-50" : "bg-amber-50"}`}>
                    <span className={`text-sm font-semibold ${selectedReg.status === "completed" ? "text-emerald-700" : "text-amber-700"}`}>
                      {selectedReg.status === "completed" ? "Registration Complete" : "Registration Pending"}
                    </span>
                  </div>

                  {/* Guest Info */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Guest Information</h4>
                    <div className="bg-stone-50 rounded-xl p-4 space-y-2 text-sm">
                      <Row label="Name" value={selectedReg.guest_name} />
                      <Row label="Email" value={selectedReg.guest_email} />
                      <Row label="Booking Ref" value={selectedReg.booking_ref} />
                    </div>
                  </div>

                  {/* Form Data */}
                  {selectedReg.form_data && Object.keys(selectedReg.form_data).length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Submitted Details</h4>
                      <div className="bg-stone-50 rounded-xl p-4 space-y-2 text-sm">
                        {Object.entries(selectedReg.form_data).map(([k, v]) => v && (
                          <Row key={k} label={k.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())} value={v} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Checklist */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Checklist</h4>
                    <div className="bg-stone-50 rounded-xl p-4 space-y-3">
                      <CheckItem label="ID Uploaded" done={selectedReg.id_uploaded} />
                      <CheckItem label="Terms Accepted" done={selectedReg.terms_accepted} />
                      <CheckItem label="Welcome Pack Sent" done={selectedReg.welcome_sent} />
                      <CheckItem label="Satisfaction Check" done={selectedReg.satisfaction_check_sent} />
                    </div>
                  </div>

                  {/* Signature */}
                  {selectedReg.signature && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Signature</h4>
                      <div className="bg-stone-50 rounded-xl p-4">
                        <p className="text-lg italic text-stone-700 font-serif">{selectedReg.signature}</p>
                      </div>
                    </div>
                  )}

                  {/* Timeline */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Timeline</h4>
                    <div className="bg-stone-50 rounded-xl p-4 space-y-2 text-sm">
                      <Row label="Sent" value={selectedReg.created_at ? new Date(selectedReg.created_at).toLocaleString() : "—"} />
                      {selectedReg.completed_at && <Row label="Completed" value={new Date(selectedReg.completed_at).toLocaleString()} />}
                    </div>
                  </div>

                  {/* Registration URL */}
                  {selectedReg.token && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Registration Link</h4>
                      <div className="bg-stone-50 rounded-xl p-3 flex items-center gap-2">
                        <code className="text-xs text-stone-600 truncate flex-1" data-testid="registration-url">{BASE_URL}/register/{selectedReg.token}</code>
                        <button onClick={() => { navigator.clipboard.writeText(`${BASE_URL}/register/${selectedReg.token}`); toast.success("Link copied!"); }} className="p-1.5 hover:bg-stone-200 rounded-lg transition text-stone-500" data-testid="btn-copy-link">
                          <ExternalLink size={14} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SatisfactionTab({ propertyId }) {
  const [checks, setChecks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/guest-journey/satisfaction-checks/${propertyId}`);
        setChecks(data);
      } catch { }
      setLoading(false);
    };
    if (propertyId) load();
  }, [propertyId]);

  return (
    <div className="bg-white rounded-xl border border-stone-200/60 overflow-hidden" data-testid="satisfaction-table">
      <div className="grid grid-cols-[1fr_120px_100px_1fr_120px] gap-2 px-4 py-3 bg-stone-50 text-xs font-semibold text-stone-500 uppercase tracking-wide border-b">
        <span>Guest</span><span>Booking Ref</span><span>Status</span><span>Message</span><span>Date</span>
      </div>
      <ScrollArea className="max-h-[400px]">
        {loading ? (
          <div className="p-8 text-center text-stone-400 text-sm">Loading...</div>
        ) : checks.length === 0 ? (
          <div className="p-8 text-center text-stone-400 text-sm" data-testid="no-satisfaction-checks">
            No satisfaction checks sent yet. Click "Satisfaction Check" to send to eligible guests.
          </div>
        ) : (
          checks.map(c => (
            <div key={c.id} className="grid grid-cols-[1fr_120px_100px_1fr_120px] gap-2 px-4 py-3 border-b border-stone-100 items-center" data-testid={`satisfaction-row-${c.id}`}>
              <span className="text-sm font-medium text-stone-800">{c.guest_name || "—"}</span>
              <span className="text-xs font-mono text-stone-600">{c.booking_ref || "—"}</span>
              <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full w-fit ${
                c.status === "responded" ? (c.response === "all_good" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700") : "bg-stone-100 text-stone-500"
              }`}>
                {c.status === "responded" ? (c.response === "all_good" ? <Smiley size={12} weight="fill" /> : <WarningCircle size={12} weight="fill" />) : <Clock size={12} />}
                {c.status === "responded" ? (c.response === "all_good" ? "Happy" : "Help") : "Sent"}
              </span>
              <span className="text-xs text-stone-500 truncate">{c.message || "—"}</span>
              <span className="text-xs text-stone-500">{c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}</span>
            </div>
          ))
        )}
      </ScrollArea>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between">
      <span className="text-stone-500">{label}</span>
      <span className="font-medium text-stone-800 text-right truncate max-w-[200px]">{value || "—"}</span>
    </div>
  );
}

function CheckItem({ label, done }) {
  return (
    <div className="flex items-center gap-2">
      {done ? <CheckCircle size={16} className="text-emerald-500" weight="fill" /> : <div className="w-4 h-4 rounded-full border-2 border-stone-300" />}
      <span className={`text-sm ${done ? "text-stone-800" : "text-stone-400"}`}>{label}</span>
    </div>
  );
}
