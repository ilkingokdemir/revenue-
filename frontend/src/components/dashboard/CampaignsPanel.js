import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  Lightning, Plus, ArrowsClockwise, PaperPlaneTilt, CheckCircle,
  Envelope, Users, Clock, Eye, ChartBar, Trash,
} from "@phosphor-icons/react";
import { Mail, Target, Calendar, BarChart3, Zap, Send, Filter, Tag } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  draft: { color: "bg-stone-100 text-stone-600", label: "Draft" },
  scheduled: { color: "bg-blue-100 text-blue-700", label: "Scheduled" },
  sending: { color: "bg-amber-100 text-amber-700", label: "Sending" },
  sent: { color: "bg-emerald-100 text-emerald-700", label: "Sent" },
  paused: { color: "bg-red-100 text-red-700", label: "Paused" },
};

const SEGMENT_OPTIONS = [
  { id: "all_guests", label: "All Guests", icon: Users, desc: "Every guest in your database" },
  { id: "vip", label: "VIP Guests", icon: Lightning, desc: "Guests marked as VIP" },
  { id: "returning", label: "Returning Guests", icon: ArrowsClockwise, desc: "Guests with 2+ stays" },
  { id: "recent_checkout", label: "Recent Checkouts", icon: Clock, desc: "Checked out in last 7 days" },
  { id: "upcoming_checkin", label: "Upcoming Arrivals", icon: Calendar, desc: "Check-in within 7 days" },
  { id: "high_spenders", label: "High Spenders", icon: ChartBar, desc: "Total spend > £500" },
  { id: "inactive", label: "Inactive Guests", icon: Clock, desc: "No stay in 6+ months" },
  { id: "gold_platinum", label: "Gold & Platinum", icon: Lightning, desc: "Gold or Platinum tier members" },
];

const TEMPLATE_LIBRARY = [
  { id: "welcome_back", name: "Welcome Back", subject: "We'd love to see you again!", category: "retention",
    body: "Dear {guest_name},\n\nWe hope you enjoyed your stay with us. As a valued guest, we'd like to offer you an exclusive {discount}% discount on your next booking.\n\nBook now and experience our updated facilities.\n\nWarm regards,\n{hotel_name}" },
  { id: "pre_arrival", name: "Pre-Arrival", subject: "Your stay is just around the corner!", category: "operations",
    body: "Dear {guest_name},\n\nWe're looking forward to welcoming you on {check_in_date}. Here's what you need to know:\n\n- Check-in from 3:00 PM\n- Online check-in available\n- Airport transfer can be arranged\n\nIs there anything we can prepare for your arrival?\n\n{hotel_name}" },
  { id: "post_stay", name: "Post Stay Review", subject: "How was your stay?", category: "feedback",
    body: "Dear {guest_name},\n\nThank you for staying with us! We'd love to hear about your experience.\n\nPlease take a moment to share your feedback — it helps us serve you better.\n\n[Leave a Review]\n\nWe hope to see you again soon!\n{hotel_name}" },
  { id: "special_offer", name: "Special Offer", subject: "Exclusive offer just for you", category: "promotion",
    body: "Dear {guest_name},\n\nAs a {loyalty_tier} member, you have early access to our seasonal promotion:\n\n- {discount}% off room rates\n- Complimentary breakfast\n- Late checkout until 2 PM\n\nValid for bookings made this month. Use code: {promo_code}\n\n{hotel_name}" },
  { id: "birthday", name: "Birthday Wishes", subject: "Happy Birthday from {hotel_name}!", category: "loyalty",
    body: "Dear {guest_name},\n\nHappy Birthday! To celebrate, we'd like to offer you a complimentary room upgrade on your next stay.\n\nBook within the next 30 days to redeem.\n\nWishing you a wonderful day!\n{hotel_name}" },
  { id: "loyalty_upgrade", name: "Loyalty Tier Upgrade", subject: "Congratulations! You've been upgraded", category: "loyalty",
    body: "Dear {guest_name},\n\nGreat news! Based on your loyalty, you've been upgraded to {loyalty_tier} tier.\n\nYour new benefits include:\n- Priority room selection\n- Late checkout\n- Exclusive member offers\n\nThank you for choosing us!\n{hotel_name}" },
];

export function CampaignsPanel({ properties, activePropertyId }) {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("campaigns");
  const [showCreate, setShowCreate] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [newCampaign, setNewCampaign] = useState({
    name: "", subject: "", body: "", channel: "email", segment: "all_guests",
    scheduled_at: "", property_id: "", status: "draft",
  });

  const propertyId = (activePropertyId && activePropertyId !== "all") ? activePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/campaigns/${propertyId}`);
      setCampaigns(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  const createCampaign = async () => {
    if (!newCampaign.name || !newCampaign.subject) return toast.error("Name and subject required");
    try {
      await axios.post(`${API}/campaigns`, { ...newCampaign, property_id: propertyId });
      toast.success("Campaign created");
      setShowCreate(false);
      setNewCampaign({ name: "", subject: "", body: "", channel: "email", segment: "all_guests", scheduled_at: "", property_id: "", status: "draft" });
      fetchCampaigns();
    } catch (e) { toast.error("Failed"); }
  };

  const sendCampaign = async (id) => {
    try {
      await axios.post(`${API}/campaigns/${id}/send`);
      toast.success("Campaign sent!");
      fetchCampaigns();
    } catch (e) { toast.error("Failed to send"); }
  };

  const deleteCampaign = async (id) => {
    if (!confirm("Delete this campaign?")) return;
    try {
      await axios.delete(`${API}/campaigns/${id}`);
      toast.success("Campaign deleted");
      fetchCampaigns();
    } catch (e) { toast.error("Failed"); }
  };

  const applyTemplate = (tpl) => {
    setNewCampaign(p => ({ ...p, name: tpl.name, subject: tpl.subject, body: tpl.body }));
    setShowTemplates(false);
    setSelectedTemplate(tpl.id);
  };

  const stats = {
    total: campaigns.length,
    sent: campaigns.filter(c => c.status === "sent").length,
    draft: campaigns.filter(c => c.status === "draft").length,
    totalRecipients: campaigns.reduce((s, c) => s + (c.recipients_count || 0), 0),
  };

  const tabs = [
    { id: "campaigns", label: "Campaigns", icon: Send },
    { id: "templates", label: "Templates", icon: Mail },
    { id: "segments", label: "Audience", icon: Target },
  ];

  return (
    <div className="h-full flex flex-col" data-testid="campaigns-panel">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-orange-500 flex items-center justify-center"><Zap size={18} className="text-white" /></div>
          <div><h2 className="text-lg font-bold text-stone-900" style={{ fontFamily: "Outfit, sans-serif" }}>Campaigns</h2><p className="text-[11px] text-stone-500">Email marketing, guest engagement & promotions</p></div>
        </div>
        <button onClick={() => setShowCreate(true)} className="text-xs px-4 py-2 bg-orange-500 text-white rounded-xl font-bold hover:bg-orange-600 flex items-center gap-1" data-testid="new-campaign-btn">
          <Plus size={12} /> New Campaign
        </button>
      </div>

      {/* Stats */}
      <div className="bg-white border-b border-stone-200 px-6 py-3 flex items-center gap-6 flex-shrink-0">
        {[
          { label: "Total", value: stats.total, color: "text-stone-800" },
          { label: "Sent", value: stats.sent, color: "text-emerald-600" },
          { label: "Drafts", value: stats.draft, color: "text-amber-600" },
          { label: "Recipients", value: stats.totalRecipients, color: "text-blue-600" },
        ].map((s, i) => (
          <div key={i} className="text-center">
            <div className={`text-lg font-black ${s.color}`}>{s.value}</div>
            <div className="text-[9px] text-stone-400 font-semibold">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-stone-200 px-6 flex gap-1 flex-shrink-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold border-b-[3px] transition-all ${tab === t.id ? "border-orange-500 text-orange-600" : "border-transparent text-stone-400"}`}
            data-testid={`camp-tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto bg-stone-50 p-6">
        {/* Campaigns List */}
        {tab === "campaigns" && (
          <div className="max-w-4xl mx-auto space-y-3" data-testid="campaigns-list">
            {loading ? <div className="text-center py-16"><ArrowsClockwise size={20} className="animate-spin text-stone-300 mx-auto" /></div> :
            campaigns.length === 0 ? (
              <div className="bg-white rounded-2xl border border-stone-200 p-10 text-center">
                <Send size={32} className="mx-auto text-stone-300 mb-3" />
                <p className="text-sm text-stone-500 font-medium">No campaigns yet</p>
                <p className="text-xs text-stone-400 mt-1">Create your first campaign to engage guests</p>
              </div>
            ) : campaigns.map(c => (
              <div key={c.id} className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all" data-testid={`campaign-${c.id}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${c.status === "sent" ? "bg-emerald-100" : c.status === "draft" ? "bg-stone-100" : "bg-blue-100"}`}>
                      {c.status === "sent" ? <CheckCircle size={18} className="text-emerald-600" weight="fill" /> : <Envelope size={18} className="text-stone-500" />}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-stone-900">{c.name}</div>
                      <div className="text-[11px] text-stone-500">{c.subject}</div>
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-stone-400">
                        <span>{c.channel}</span>
                        <span>·</span>
                        <span>{c.segment}</span>
                        {c.recipients_count > 0 && <><span>·</span><span>{c.recipients_count} recipients</span></>}
                        {c.sent_at && <><span>·</span><span>{c.sent_at.slice(0, 10)}</span></>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[9px] font-bold ${STATUS_CONFIG[c.status]?.color || "bg-stone-100"}`}>{STATUS_CONFIG[c.status]?.label || c.status}</Badge>
                    {c.status === "draft" && (
                      <button onClick={() => sendCampaign(c.id)} className="text-[10px] px-3 py-1.5 bg-orange-500 text-white rounded-lg font-bold hover:bg-orange-600 flex items-center gap-1" data-testid={`send-${c.id}`}>
                        <PaperPlaneTilt size={10} weight="fill" /> Send Now
                      </button>
                    )}
                    <button onClick={() => deleteCampaign(c.id)} className="text-stone-300 hover:text-red-500"><Trash size={14} /></button>
                  </div>
                </div>
                {/* Delivery Stats */}
                {c.status === "sent" && (c.delivered || c.opened || c.clicked) && (
                  <div className="mt-3 pt-3 border-t border-stone-100 grid grid-cols-4 gap-3">
                    <div className="text-center"><div className="text-sm font-bold text-stone-700">{c.delivered || 0}</div><div className="text-[9px] text-stone-400">Delivered</div></div>
                    <div className="text-center"><div className="text-sm font-bold text-blue-600">{c.opened || 0}</div><div className="text-[9px] text-stone-400">Opened</div></div>
                    <div className="text-center"><div className="text-sm font-bold text-emerald-600">{c.clicked || 0}</div><div className="text-[9px] text-stone-400">Clicked</div></div>
                    <div className="text-center"><div className="text-sm font-bold text-red-500">{c.bounced || 0}</div><div className="text-[9px] text-stone-400">Bounced</div></div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Templates */}
        {tab === "templates" && (
          <div className="max-w-4xl mx-auto" data-testid="templates-tab">
            <h3 className="text-sm font-bold text-stone-800 mb-4">Email Template Library</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {TEMPLATE_LIBRARY.map(tpl => (
                <div key={tpl.id} className="bg-white border border-stone-200 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all" data-testid={`template-${tpl.id}`}>
                  <Badge className="text-[8px] bg-orange-50 text-orange-700 mb-2">{tpl.category}</Badge>
                  <div className="text-sm font-bold text-stone-900 mb-1">{tpl.name}</div>
                  <div className="text-[11px] text-stone-500 mb-2">{tpl.subject}</div>
                  <div className="text-[10px] text-stone-400 line-clamp-3 mb-3">{tpl.body.slice(0, 120)}...</div>
                  <button onClick={() => { applyTemplate(tpl); setShowCreate(true); }}
                    className="w-full text-[10px] py-2 bg-orange-50 text-orange-700 rounded-lg font-bold hover:bg-orange-100" data-testid={`use-template-${tpl.id}`}>
                    Use Template
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Segments */}
        {tab === "segments" && (
          <div className="max-w-4xl mx-auto" data-testid="segments-tab">
            <h3 className="text-sm font-bold text-stone-800 mb-4">Audience Segments</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {SEGMENT_OPTIONS.map(seg => (
                <div key={seg.id} className="bg-white border border-stone-200 rounded-2xl p-4 shadow-sm flex items-center gap-3" data-testid={`segment-${seg.id}`}>
                  <div className="w-10 h-10 rounded-xl bg-orange-50 flex items-center justify-center"><seg.icon size={18} className="text-orange-500" /></div>
                  <div className="flex-1">
                    <div className="text-sm font-bold text-stone-800">{seg.label}</div>
                    <div className="text-[11px] text-stone-500">{seg.desc}</div>
                  </div>
                  <button onClick={() => { setNewCampaign(p => ({...p, segment: seg.id})); setShowCreate(true); }}
                    className="text-[10px] px-3 py-1.5 bg-orange-50 text-orange-700 rounded-lg font-bold hover:bg-orange-100">
                    Target
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Create Campaign Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg" data-testid="create-campaign-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Zap size={16} className="text-orange-500" /> Create Campaign</DialogTitle></DialogHeader>
          <div className="space-y-3 max-h-[60vh] overflow-y-auto">
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-[11px] font-bold text-stone-600 mb-1 block">Campaign Name</label>
                <Input value={newCampaign.name} onChange={e => setNewCampaign(p => ({...p, name: e.target.value}))} placeholder="e.g. Summer Special Offer" data-testid="campaign-name" />
              </div>
              <div>
                <label className="text-[11px] font-bold text-stone-600 mb-1 block">Channel</label>
                <Select value={newCampaign.channel} onValueChange={v => setNewCampaign(p => ({...p, channel: v}))}>
                  <SelectTrigger className="w-28 h-9 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="email">Email</SelectItem>
                    <SelectItem value="whatsapp">WhatsApp</SelectItem>
                    <SelectItem value="sms">SMS</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <label className="text-[11px] font-bold text-stone-600 mb-1 block">Email Subject</label>
              <Input value={newCampaign.subject} onChange={e => setNewCampaign(p => ({...p, subject: e.target.value}))} placeholder="Subject line" data-testid="campaign-subject" />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[11px] font-bold text-stone-600">Message Body</label>
                <button onClick={() => setShowTemplates(true)} className="text-[10px] text-orange-600 font-bold">Browse Templates</button>
              </div>
              <Textarea value={newCampaign.body} onChange={e => setNewCampaign(p => ({...p, body: e.target.value}))} placeholder="Write your message... Use {guest_name}, {hotel_name}, {check_in_date} as variables" rows={6} data-testid="campaign-body" />
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {["{guest_name}", "{hotel_name}", "{check_in_date}", "{loyalty_tier}", "{discount}", "{promo_code}"].map(v => (
                  <button key={v} onClick={() => setNewCampaign(p => ({...p, body: p.body + " " + v}))}
                    className="text-[9px] px-2 py-0.5 bg-stone-100 text-stone-500 rounded hover:bg-stone-200 font-mono">{v}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-[11px] font-bold text-stone-600 mb-1 block">Target Audience</label>
              <Select value={newCampaign.segment} onValueChange={v => setNewCampaign(p => ({...p, segment: v}))}>
                <SelectTrigger className="h-9 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {SEGMENT_OPTIONS.map(s => <SelectItem key={s.id} value={s.id}>{s.label} — {s.desc}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[11px] font-bold text-stone-600 mb-1 block">Schedule (optional)</label>
              <Input type="datetime-local" value={newCampaign.scheduled_at} onChange={e => setNewCampaign(p => ({...p, scheduled_at: e.target.value}))} className="h-9 text-xs" />
            </div>
            <div className="flex gap-2">
              <button onClick={createCampaign} className="flex-1 bg-orange-500 text-white py-2.5 rounded-xl text-sm font-bold hover:bg-orange-600 flex items-center justify-center gap-1" data-testid="save-campaign-btn">
                <Plus size={14} /> Save as Draft
              </button>
              <button onClick={async () => { await createCampaign(); }} className="flex-1 bg-[#2C4C3B] text-white py-2.5 rounded-xl text-sm font-bold hover:bg-[#1A3025] flex items-center justify-center gap-1">
                <PaperPlaneTilt size={14} weight="fill" /> Save & Send
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Template Browser Dialog */}
      <Dialog open={showTemplates} onOpenChange={setShowTemplates}>
        <DialogContent className="max-w-lg" data-testid="template-browser">
          <DialogHeader><DialogTitle>Choose Template</DialogTitle></DialogHeader>
          <div className="space-y-2 max-h-[50vh] overflow-y-auto">
            {TEMPLATE_LIBRARY.map(tpl => (
              <button key={tpl.id} onClick={() => applyTemplate(tpl)}
                className={`w-full text-left p-3 rounded-xl border-2 transition-all ${selectedTemplate === tpl.id ? "border-orange-300 bg-orange-50" : "border-stone-200 hover:border-stone-300"}`}>
                <div className="flex items-center justify-between">
                  <div className="text-xs font-bold text-stone-800">{tpl.name}</div>
                  <Badge className="text-[8px] bg-stone-100 text-stone-500">{tpl.category}</Badge>
                </div>
                <div className="text-[10px] text-stone-500 mt-0.5">{tpl.subject}</div>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
