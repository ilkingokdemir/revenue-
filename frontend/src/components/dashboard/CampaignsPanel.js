import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import {
  Megaphone, Plus, PaperPlaneTilt, Users, Envelope,
  WhatsappLogo, DeviceMobile, ArrowsClockwise, Eye,
  Trash, ChartBar, CheckCircle, Clock,
} from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CHANNEL_ICONS = {
  email: { icon: Envelope, color: "text-blue-500" },
  whatsapp: { icon: WhatsappLogo, color: "text-green-500" },
  sms: { icon: DeviceMobile, color: "text-purple-500" },
};

export function CampaignsPanel({ properties, activePropertyId }) {
  const [campaigns, setCampaigns] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newCampaign, setNewCampaign] = useState({ name: "", channel: "email", subject: "", message: "", segment: {} });
  const [previewData, setPreviewData] = useState(null);

  const propertyId = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "city-gate");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [campRes, statsRes] = await Promise.all([
        axios.get(`${API}/campaigns/${propertyId}`),
        axios.get(`${API}/campaigns/${propertyId}/stats`),
      ]);
      setCampaigns(campRes.data);
      setStats(statsRes.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const createCampaign = async () => {
    if (!newCampaign.name) return;
    await axios.post(`${API}/campaigns`, { ...newCampaign, property_id: propertyId });
    setShowCreate(false);
    setNewCampaign({ name: "", channel: "email", subject: "", message: "", segment: {} });
    fetchData();
  };

  const sendCampaign = async (id) => {
    await axios.post(`${API}/campaigns/${id}/send`);
    fetchData();
  };

  const deleteCampaign = async (id) => {
    await axios.delete(`${API}/campaigns/${id}`);
    fetchData();
  };

  const previewRecipients = async (id) => {
    const res = await axios.post(`${API}/campaigns/${id}/preview`);
    setPreviewData(res.data);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5" data-testid="campaigns-panel">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2" data-testid="campaigns-title">
            <Megaphone size={22} className="text-orange-500" weight="fill" />
            Campaign Manager
          </h1>
          <p className="text-sm text-stone-500 mt-0.5">Bulk messaging with guest segmentation</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="text-xs px-3 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 font-medium flex items-center gap-1.5"
          data-testid="create-campaign-btn">
          <Plus size={12} /> New Campaign
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-stone-800">{stats.total || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Campaigns</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-emerald-600">{stats.sent || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Sent</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-stone-800">{stats.total_messages_sent || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Messages Sent</div>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-3 text-center">
          <div className="text-xl font-bold text-blue-600">{stats.total_recipients || 0}</div>
          <div className="text-[10px] text-stone-500 uppercase">Recipients</div>
        </div>
      </div>

      {/* Campaign List */}
      {loading ? (
        <div className="flex justify-center py-16"><ArrowsClockwise size={24} className="animate-spin text-stone-300" /></div>
      ) : campaigns.length === 0 ? (
        <div className="bg-white border border-stone-200 rounded-xl p-12 text-center">
          <Megaphone size={32} className="text-stone-300 mx-auto mb-2" />
          <p className="text-sm text-stone-500">No campaigns yet. Create your first one!</p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="campaign-list">
          {campaigns.map(c => {
            const ChIcon = CHANNEL_ICONS[c.channel]?.icon || Envelope;
            const chColor = CHANNEL_ICONS[c.channel]?.color || "text-stone-500";
            return (
              <div key={c.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`campaign-${c.id}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-orange-50 flex items-center justify-center">
                      <ChIcon size={18} className={chColor} weight="fill" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-stone-800">{c.name}</div>
                      <div className="flex items-center gap-2 text-[10px] text-stone-400 mt-0.5">
                        <span>{c.channel}</span>
                        {c.subject && <span>· {c.subject}</span>}
                        {c.total_sent > 0 && <span>· {c.total_sent} sent</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[10px] ${c.status === "sent" ? "bg-emerald-100 text-emerald-700" : c.status === "draft" ? "bg-stone-100 text-stone-600" : "bg-amber-100 text-amber-700"}`}>
                      {c.status}
                    </Badge>
                    {c.status === "draft" && (
                      <>
                        <button onClick={() => previewRecipients(c.id)} className="text-[10px] px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100">
                          <Eye size={11} className="inline mr-0.5" /> Preview
                        </button>
                        <button onClick={() => sendCampaign(c.id)} className="text-[10px] px-2 py-1 bg-emerald-50 text-emerald-600 rounded hover:bg-emerald-100">
                          <PaperPlaneTilt size={11} className="inline mr-0.5" /> Send
                        </button>
                        <button onClick={() => deleteCampaign(c.id)} className="text-[10px] p-1 text-red-400 hover:text-red-600">
                          <Trash size={13} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Campaign Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Megaphone size={18} className="text-orange-500" /> New Campaign</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input placeholder="Campaign name" value={newCampaign.name} onChange={e => setNewCampaign(p => ({...p, name: e.target.value}))} data-testid="campaign-name-input" />
            <Select value={newCampaign.channel} onValueChange={v => setNewCampaign(p => ({...p, channel: v}))}>
              <SelectTrigger className="h-9 text-sm" data-testid="campaign-channel">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="whatsapp">WhatsApp</SelectItem>
                <SelectItem value="sms">SMS</SelectItem>
              </SelectContent>
            </Select>
            {newCampaign.channel === "email" && (
              <Input placeholder="Subject line" value={newCampaign.subject} onChange={e => setNewCampaign(p => ({...p, subject: e.target.value}))} data-testid="campaign-subject" />
            )}
            <Textarea placeholder="Message body (use {guest_name} for personalization)" value={newCampaign.message}
              onChange={e => setNewCampaign(p => ({...p, message: e.target.value}))} rows={4} data-testid="campaign-message" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCreate(false)} className="text-xs px-3 py-2 text-stone-500 hover:text-stone-700">Cancel</button>
              <button onClick={createCampaign} className="text-xs px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 font-medium" data-testid="save-campaign-btn">
                Create Campaign
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Preview Recipients Dialog */}
      <Dialog open={!!previewData} onOpenChange={() => setPreviewData(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Recipients Preview ({previewData?.total || 0})</DialogTitle>
          </DialogHeader>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {previewData?.preview?.map((r, i) => (
              <div key={i} className="text-xs bg-stone-50 rounded p-2 flex items-center justify-between">
                <span className="font-medium text-stone-700">{r.name}</span>
                <span className="text-stone-400">{r.email || r.phone}</span>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
