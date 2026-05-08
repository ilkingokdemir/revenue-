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
import { FileText, Send, Users, Shield, Camera, ChevronDown, ExternalLink, QrCode, Share2, Printer, MessageSquare, Mail, Link2, Smartphone } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { WhatsappLogo } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BASE_URL = process.env.REACT_APP_BACKEND_URL;

export function GuestJourneyPanel({ properties, activePropertyId: propActivePropertyId }) {
  const activePropertyId = propActivePropertyId || "all";
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
  const [showShare, setShowShare] = useState(null); // registration for share modal
  const [sharing, setSharing] = useState("");

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
      const params = activePropertyId === "all" ? "" : `property_id=${activePropertyId}&`;
      const { data } = await axios.get(`${API}/bookings?${params}status=confirmed`);
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
      console.error("Reception upload error:", e);
      toast.error(e.response?.data?.detail || "Upload failed. Please try again.");
    }
    setUploadingId(null);
  };

  const shareLink = async (reg, channel) => {
    setSharing(channel);
    try {
      const { data } = await axios.post(`${API}/guest-journey/share-link/${reg.id}`, { channel });
      if (data.status === "sent") {
        toast.success(`Registration link sent via ${channel}!`);
      } else if (data.status === "skipped") {
        toast.error(`${channel} not configured. Set up in Channel Settings.`);
      } else {
        toast.error(data.reason || `Failed to send via ${channel}`);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || `Failed to send via ${channel}`);
    }
    setSharing("");
  };

  const printRegistration = (reg) => {
    const url = `${BASE_URL}/register/${reg.token}`;
    const win = window.open("", "_blank", "width=400,height=600");
    win.document.write(`
      <html><head><title>Registration - ${reg.guest_name}</title>
      <style>body{font-family:Arial,sans-serif;padding:32px;text-align:center}
      h2{margin:0 0 4px;font-size:20px}p{color:#666;font-size:13px;margin:4px 0}
      .box{border:2px solid #ddd;border-radius:12px;padding:20px;margin:20px 0}
      .qr{margin:16px auto}table{width:100%;text-align:left;font-size:13px;margin:12px 0}
      td{padding:4px 8px}td:first-child{color:#888;width:40%}
      .url{font-size:10px;word-break:break-all;color:#888;margin-top:12px}
      @media print{body{padding:16px}}</style></head><body>
      <h2>${reg.hotel_name || "Hotel"}</h2>
      <p>Guest Registration</p>
      <div class="box">
        <div class="qr" id="qr"></div>
        <p style="font-size:11px;color:#999">Scan to complete registration</p>
      </div>
      <table>
        <tr><td>Guest</td><td><strong>${reg.guest_name || "—"}</strong></td></tr>
        <tr><td>Booking</td><td>${reg.booking_ref || "—"}</td></tr>
        <tr><td>Email</td><td>${reg.guest_email || "—"}</td></tr>
      </table>
      <p class="url">${url}</p>
      <script src="https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.min.js"><\/script>
      <script>
        var qr=qrcode(0,'M');qr.addData('${url}');qr.make();
        document.getElementById('qr').innerHTML=qr.createSvgTag(5,0);
        setTimeout(function(){window.print()},500);
      <\/script></body></html>
    `);
    win.document.close();
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
          { id: "welcome-info", label: "Welcome Info", icon: <Mail size={14} /> },
          { id: "kiosk", label: "Kiosk Setup", icon: <Smartphone size={14} /> },
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
                      <button onClick={(e) => { e.stopPropagation(); setShowShare(reg); }} className="p-1.5 rounded-md hover:bg-stone-100 text-stone-400 hover:text-[#1e3a5f] transition" data-testid={`btn-share-${reg.id}`} title="Share Registration Link">
                        <Share2 size={14} />
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

      {tab === "welcome-info" && (
        <WelcomeInfoTab propertyId={activePropertyId} />
      )}

      {tab === "kiosk" && (
        <KioskSetupTab propertyId={activePropertyId} />
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

                  {/* Registration URL & Share */}
                  {selectedReg.token && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">Registration Link</h4>
                      <div className="bg-stone-50 rounded-xl p-3 flex items-center gap-2">
                        <code className="text-xs text-stone-600 truncate flex-1" data-testid="registration-url">{BASE_URL}/register/{selectedReg.token}</code>
                        <button onClick={() => { navigator.clipboard.writeText(`${BASE_URL}/register/${selectedReg.token}`); toast.success("Link copied!"); }} className="p-1.5 hover:bg-stone-200 rounded-lg transition text-stone-500" data-testid="btn-copy-link">
                          <ExternalLink size={14} />
                        </button>
                      </div>
                      {/* QR Code */}
                      <div className="bg-white rounded-xl border border-stone-200 p-4 flex flex-col items-center" data-testid="drawer-qr-code">
                        <QRCodeSVG value={`${BASE_URL}/register/${selectedReg.token}`} size={120} level="M" includeMargin />
                        <p className="text-[10px] text-stone-400 mt-1">Scan to register</p>
                      </div>
                      {/* Share Buttons */}
                      <div className="flex gap-1.5 flex-wrap">
                        <button onClick={() => { setSelectedReg(null); setShowShare(selectedReg); }} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#1e3a5f] text-white rounded-lg hover:bg-[#15304f] transition" data-testid="drawer-share-all">
                          <Share2 size={12} /> Share Options
                        </button>
                        <button onClick={() => printRegistration(selectedReg)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-stone-200 text-stone-600 rounded-lg hover:bg-stone-50 transition" data-testid="drawer-print">
                          <Printer size={12} /> Print
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

      {/* Share Registration Link Modal */}
      <AnimatePresence>
        {showShare && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setShowShare(null)}>
            <motion.div initial={{ opacity: 0, scale: 0.9, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9, y: 20 }} className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden" onClick={(e) => e.stopPropagation()} data-testid="share-modal">
              {/* Header */}
              <div className="px-5 py-4 border-b border-stone-100 flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-stone-800">Share Registration Link</h3>
                  <p className="text-xs text-stone-500 mt-0.5">{showShare.guest_name} &middot; {showShare.booking_ref}</p>
                </div>
                <button onClick={() => setShowShare(null)} className="p-1.5 hover:bg-stone-100 rounded-lg transition" data-testid="close-share-modal">
                  <X size={16} className="text-stone-400" />
                </button>
              </div>

              <div className="p-5 space-y-4">
                {/* QR Code */}
                <div className="bg-stone-50 rounded-xl p-4 flex flex-col items-center" data-testid="share-qr-section">
                  <div data-testid="share-qr-code">
                    <QRCodeSVG value={`${BASE_URL}/register/${showShare.token}`} size={160} level="M" includeMargin />
                  </div>
                  <p className="text-[10px] text-stone-400 mt-2">Scan at reception or print for guest</p>
                </div>

                {/* Share Options Grid */}
                <div className="grid grid-cols-3 gap-2" data-testid="share-options">
                  {/* Copy Link */}
                  <button data-testid="share-copy-link" onClick={() => { navigator.clipboard.writeText(`${BASE_URL}/register/${showShare.token}`); toast.success("Link copied to clipboard!"); }} className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-stone-200 hover:bg-stone-50 hover:border-stone-300 transition group">
                    <div className="w-9 h-9 rounded-full bg-stone-100 flex items-center justify-center group-hover:bg-stone-200 transition">
                      <Link2 size={16} className="text-stone-600" />
                    </div>
                    <span className="text-[11px] font-medium text-stone-700">Copy Link</span>
                  </button>

                  {/* Email */}
                  <button data-testid="share-email" onClick={() => shareLink(showShare, "email")} disabled={sharing === "email"} className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-stone-200 hover:bg-blue-50 hover:border-blue-200 transition group disabled:opacity-50">
                    <div className="w-9 h-9 rounded-full bg-blue-50 flex items-center justify-center group-hover:bg-blue-100 transition">
                      <Mail size={16} className="text-blue-600" />
                    </div>
                    <span className="text-[11px] font-medium text-stone-700">{sharing === "email" ? "Sending..." : "Email"}</span>
                  </button>

                  {/* SMS */}
                  <button data-testid="share-sms" onClick={() => shareLink(showShare, "sms")} disabled={sharing === "sms"} className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-stone-200 hover:bg-emerald-50 hover:border-emerald-200 transition group disabled:opacity-50">
                    <div className="w-9 h-9 rounded-full bg-emerald-50 flex items-center justify-center group-hover:bg-emerald-100 transition">
                      <Smartphone size={16} className="text-emerald-600" />
                    </div>
                    <span className="text-[11px] font-medium text-stone-700">{sharing === "sms" ? "Sending..." : "SMS"}</span>
                  </button>

                  {/* WhatsApp */}
                  <button data-testid="share-whatsapp" onClick={() => shareLink(showShare, "whatsapp")} disabled={sharing === "whatsapp"} className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-stone-200 hover:bg-green-50 hover:border-green-200 transition group disabled:opacity-50">
                    <div className="w-9 h-9 rounded-full bg-green-50 flex items-center justify-center group-hover:bg-green-100 transition">
                      <WhatsappLogo size={16} className="text-green-600" weight="fill" />
                    </div>
                    <span className="text-[11px] font-medium text-stone-700">{sharing === "whatsapp" ? "Sending..." : "WhatsApp"}</span>
                  </button>

                  {/* Print */}
                  <button data-testid="share-print" onClick={() => printRegistration(showShare)} className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-stone-200 hover:bg-amber-50 hover:border-amber-200 transition group">
                    <div className="w-9 h-9 rounded-full bg-amber-50 flex items-center justify-center group-hover:bg-amber-100 transition">
                      <Printer size={16} className="text-amber-600" />
                    </div>
                    <span className="text-[11px] font-medium text-stone-700">Print</span>
                  </button>

                  {/* Download QR */}
                  <button data-testid="share-download-qr" onClick={() => {
                    const svg = document.querySelector('[data-testid="share-qr-code"] svg');
                    if (!svg) return;
                    const svgData = new XMLSerializer().serializeToString(svg);
                    const canvas = document.createElement("canvas");
                    canvas.width = 400; canvas.height = 400;
                    const ctx = canvas.getContext("2d");
                    const img = new Image();
                    img.onload = () => { ctx.fillStyle = "#fff"; ctx.fillRect(0,0,400,400); ctx.drawImage(img, 0, 0, 400, 400); const a = document.createElement("a"); a.download = `qr-${showShare.guest_name?.replace(/\s+/g,"-") || "guest"}.png`; a.href = canvas.toDataURL("image/png"); a.click(); };
                    img.src = "data:image/svg+xml;base64," + btoa(svgData);
                    toast.success("QR code downloaded!");
                  }} className="flex flex-col items-center gap-1.5 p-3 rounded-xl border border-stone-200 hover:bg-violet-50 hover:border-violet-200 transition group">
                    <div className="w-9 h-9 rounded-full bg-violet-50 flex items-center justify-center group-hover:bg-violet-100 transition">
                      <QrCode size={16} className="text-violet-600" />
                    </div>
                    <span className="text-[11px] font-medium text-stone-700">Save QR</span>
                  </button>
                </div>

                {/* Registration URL */}
                <div className="bg-stone-50 rounded-lg p-2.5 flex items-center gap-2">
                  <code className="text-[10px] text-stone-500 truncate flex-1" data-testid="share-reg-url">{BASE_URL}/register/{showShare.token}</code>
                </div>
              </div>
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


function WelcomeInfoTab({ propertyId }) {
  const [policies, setPolicies] = useState([]);
  const [cityInfo, setCityInfo] = useState([]);
  const [customMsg, setCustomMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/guest-journey/welcome-info/${propertyId}`);
        setPolicies(data.hotel_policies || []);
        setCityInfo(data.city_info || []);
        setCustomMsg(data.custom_message || "");
      } catch { }
      setLoading(false);
    };
    if (propertyId) load();
  }, [propertyId]);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/guest-journey/welcome-info/${propertyId}`, { hotel_policies: policies, city_info: cityInfo, custom_message: customMsg });
      toast.success("Welcome info saved!");
    } catch { toast.error("Failed to save"); }
    setSaving(false);
  };

  const addItem = (list, setList) => setList([...list, ""]);
  const updateItem = (list, setList, idx, val) => { const n = [...list]; n[idx] = val; setList(n); };
  const removeItem = (list, setList, idx) => setList(list.filter((_, i) => i !== idx));

  if (loading) return <div className="p-8 text-center text-stone-400">Loading...</div>;

  return (
    <div className="space-y-6" data-testid="welcome-info-tab">
      <div className="bg-white rounded-xl border border-stone-200/60 p-5">
        <h3 className="text-sm font-semibold text-stone-800 mb-1">Hotel Information</h3>
        <p className="text-xs text-stone-400 mb-4">These appear in the welcome email sent to guests after registration</p>
        <div className="space-y-2">
          {policies.map((p, i) => (
            <div key={i} className="flex gap-2 items-center">
              <input data-testid={`policy-input-${i}`} value={p} onChange={(e) => updateItem(policies, setPolicies, i, e.target.value)} className="flex-1 px-3 py-2 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none" placeholder="e.g. Check-in: from 3:00 PM" />
              <button onClick={() => removeItem(policies, setPolicies, i)} className="p-1.5 text-stone-400 hover:text-red-500 transition"><X size={14} /></button>
            </div>
          ))}
          <button onClick={() => addItem(policies, setPolicies)} className="text-xs text-[#1e3a5f] font-medium hover:underline" data-testid="btn-add-policy">+ Add item</button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 p-5">
        <h3 className="text-sm font-semibold text-stone-800 mb-1">City & Area Info</h3>
        <p className="text-xs text-stone-400 mb-4">Local tips and information for your guests</p>
        <div className="space-y-2">
          {cityInfo.map((c, i) => (
            <div key={i} className="flex gap-2 items-center">
              <input data-testid={`city-input-${i}`} value={c} onChange={(e) => updateItem(cityInfo, setCityInfo, i, e.target.value)} className="flex-1 px-3 py-2 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none" placeholder="e.g. Nearest metro: 5 min walk" />
              <button onClick={() => removeItem(cityInfo, setCityInfo, i)} className="p-1.5 text-stone-400 hover:text-red-500 transition"><X size={14} /></button>
            </div>
          ))}
          <button onClick={() => addItem(cityInfo, setCityInfo)} className="text-xs text-[#1e3a5f] font-medium hover:underline" data-testid="btn-add-city">+ Add item</button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 p-5">
        <h3 className="text-sm font-semibold text-stone-800 mb-1">Custom Welcome Message</h3>
        <p className="text-xs text-stone-400 mb-3">Optional personal message shown at the top of the welcome email</p>
        <textarea data-testid="custom-message-input" value={customMsg} onChange={(e) => setCustomMsg(e.target.value)} rows={3} className="w-full px-3 py-2.5 rounded-lg border border-stone-200 text-sm focus:ring-2 focus:ring-[#1e3a5f]/20 focus:border-[#1e3a5f] outline-none resize-none" placeholder="e.g. We're thrilled to have you! Don't miss our rooftop bar opening at 6pm..." />
      </div>

      <button data-testid="btn-save-welcome-info" onClick={save} disabled={saving} className="px-6 py-2.5 bg-[#1e3a5f] text-white text-sm font-semibold rounded-lg hover:bg-[#15304f] disabled:opacity-50 transition">
        {saving ? "Saving..." : "Save Welcome Info"}
      </button>
    </div>
  );
}

function KioskSetupTab({ propertyId }) {
  const kioskUrl = `${BASE_URL}/checkin-kiosk/${propertyId}`;

  return (
    <div className="space-y-6" data-testid="kiosk-setup-tab">
      <div className="bg-white rounded-xl border border-stone-200/60 p-6">
        <h3 className="text-base font-semibold text-stone-800 mb-1">iPad / Kiosk Check-In</h3>
        <p className="text-sm text-stone-400 mb-5">Set up an iPad or tablet at your reception for guest self check-in. Open this URL in Safari/Chrome full-screen mode.</p>

        <div className="bg-stone-50 rounded-xl p-4 space-y-4">
          {/* URL */}
          <div>
            <label className="text-xs font-medium text-stone-500 block mb-1.5">Kiosk URL</label>
            <div className="flex items-center gap-2">
              <code className="flex-1 px-3 py-2.5 bg-white rounded-lg border border-stone-200 text-sm text-stone-700 truncate" data-testid="kiosk-url">{kioskUrl}</code>
              <button onClick={() => { navigator.clipboard.writeText(kioskUrl); toast.success("Kiosk URL copied!"); }} className="px-3 py-2.5 bg-[#1e3a5f] text-white text-xs font-medium rounded-lg hover:bg-[#15304f] transition" data-testid="btn-copy-kiosk-url">
                Copy
              </button>
            </div>
          </div>

          {/* QR Code for kiosk */}
          <div className="flex flex-col items-center pt-2">
            <QRCodeSVG value={kioskUrl} size={140} level="M" includeMargin />
            <p className="text-[10px] text-stone-400 mt-2">Scan to open kiosk on device</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-stone-200/60 p-6">
        <h3 className="text-sm font-semibold text-stone-800 mb-3">Setup Instructions</h3>
        <div className="space-y-3 text-sm text-stone-600">
          <div className="flex gap-3">
            <span className="w-6 h-6 rounded-full bg-[#1e3a5f] text-white text-xs font-bold flex items-center justify-center flex-shrink-0">1</span>
            <p>Open the kiosk URL on your iPad or tablet in Safari or Chrome</p>
          </div>
          <div className="flex gap-3">
            <span className="w-6 h-6 rounded-full bg-[#1e3a5f] text-white text-xs font-bold flex items-center justify-center flex-shrink-0">2</span>
            <p>Enable full-screen mode: Safari &rarr; Share &rarr; Add to Home Screen</p>
          </div>
          <div className="flex gap-3">
            <span className="w-6 h-6 rounded-full bg-[#1e3a5f] text-white text-xs font-bold flex items-center justify-center flex-shrink-0">3</span>
            <p>Place the iPad at reception. Guests tap the screen to search and check in</p>
          </div>
          <div className="flex gap-3">
            <span className="w-6 h-6 rounded-full bg-[#1e3a5f] text-white text-xs font-bold flex items-center justify-center flex-shrink-0">4</span>
            <p>The kiosk auto-resets to the welcome screen after 60 seconds of inactivity</p>
          </div>
        </div>
      </div>

      <a href={kioskUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 text-white text-sm font-semibold rounded-lg hover:bg-emerald-700 transition" data-testid="btn-preview-kiosk">
        <ExternalLink size={14} /> Preview Kiosk
      </a>
    </div>
  );
}
