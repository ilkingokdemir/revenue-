import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Lightning, Play, Clock, Envelope, WhatsappLogo, DeviceMobile,
  TelegramLogo, ChatText, ArrowsClockwise, CheckCircle, WarningCircle,
  PencilSimple, Trash, Plus, Eye, CalendarBlank, Users,
  PaperPlaneTilt, Robot, X, Hourglass, Queue,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TRIGGER_CONFIG = {
  pre_arrival: { name: "Pre-Arrival", color: "bg-blue-100 text-blue-700", desc: "Before guest checks in" },
  day_of_arrival: { name: "Arrival Day", color: "bg-emerald-100 text-emerald-700", desc: "On check-in day" },
  during_stay: { name: "During Stay", color: "bg-purple-100 text-purple-700", desc: "While guest is staying" },
  post_checkout: { name: "Post-Checkout", color: "bg-amber-100 text-amber-700", desc: "After guest checks out" },
  cart_abandonment: { name: "Cart Recovery", color: "bg-red-100 text-red-700", desc: "When booking is abandoned" },
};

const CHANNEL_ICONS = {
  email: { icon: Envelope, color: "text-blue-600" },
  whatsapp: { icon: WhatsappLogo, color: "text-green-600" },
  sms: { icon: DeviceMobile, color: "text-purple-600" },
  telegram: { icon: TelegramLogo, color: "text-sky-600" },
  internal: { icon: ChatText, color: "text-stone-600" },
};

const TEMPLATE_VARS = [
  { var: "{guest_name}", desc: "Guest full name" },
  { var: "{hotel_name}", desc: "Hotel/property name" },
  { var: "{booking_ref}", desc: "Booking reference" },
  { var: "{check_in}", desc: "Check-in date" },
  { var: "{check_out}", desc: "Check-out date" },
  { var: "{room_type}", desc: "Room type name" },
  { var: "{total_price}", desc: "Total price with £" },
  { var: "{checkin_link}", desc: "Self check-in URL" },
  { var: "{review_link}", desc: "Review page URL" },
  { var: "{portal_link}", desc: "Guest portal URL" },
  { var: "{cart_link}", desc: "Booking page URL" },
];

export function AutomationPanel({ properties, activePropertyId: propActivePropertyId }) {
  const [rules, setRules] = useState([]);
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [editRule, setEditRule] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  const [preview, setPreview] = useState("");
  const [showLogs, setShowLogs] = useState(false);
  const propertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [rRes, sRes, lRes] = await Promise.all([
        axios.get(`${API}/automation/rules/${propertyId}`),
        axios.get(`${API}/automation/stats/${propertyId}`),
        axios.get(`${API}/automation/logs/${propertyId}?limit=30`),
      ]);
      setRules(rRes.data);
      setStats(sRes.data);
      setLogs(lRes.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [propertyId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const toggleRule = async (rule) => {
    try {
      const { data } = await axios.post(`${API}/automation/rules/${rule.id}/toggle`);
      setRules(prev => prev.map(r => r.id === rule.id ? { ...r, enabled: data.enabled } : r));
      toast.success(data.enabled ? "Rule enabled" : "Rule disabled");
    } catch (e) { toast.error("Failed to toggle"); }
  };

  const deleteRule = async (id) => {
    try {
      await axios.delete(`${API}/automation/rules/${id}`);
      setRules(prev => prev.filter(r => r.id !== id));
      toast.success("Rule deleted");
      fetchAll();
    } catch (e) { toast.error("Failed to delete"); }
  };

  const runAutomation = async () => {
    setRunning(true);
    try {
      const { data } = await axios.post(`${API}/automation/run/${propertyId}`);
      toast.success(data.message);
      fetchAll();
    } catch (e) { toast.error("Automation failed"); }
    finally { setRunning(false); }
  };

  const openEditor = (rule = null) => {
    setEditRule(rule || {
      property_id: propertyId, name: "", trigger: "pre_arrival", timing_hours: -24,
      channel: "email", subject: "", message_template: "", enabled: true,
    });
    setPreview("");
    setShowEditor(true);
  };

  const saveRule = async () => {
    if (!editRule.name || !editRule.message_template) return toast.error("Name and message are required");
    try {
      if (editRule.id) {
        await axios.put(`${API}/automation/rules/${editRule.id}`, editRule);
        toast.success("Rule updated");
      } else {
        await axios.post(`${API}/automation/rules`, editRule);
        toast.success("Rule created");
      }
      setShowEditor(false);
      fetchAll();
    } catch (e) { toast.error("Failed to save"); }
  };

  const previewTemplate = async () => {
    try {
      const { data } = await axios.post(`${API}/automation/preview`, {
        message_template: editRule.message_template, property_id: propertyId,
      });
      setPreview(data.preview);
    } catch (e) { toast.error("Preview failed"); }
  };

  return (
    <div className="p-5" data-testid="automation-panel">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-stone-900 flex items-center gap-2">
            <Lightning size={20} weight="fill" className="text-amber-500" /> Message Automation
          </h2>
          <p className="text-sm text-stone-500">Automated guest journey messages — pre-arrival, during stay, post-checkout</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={runAutomation} disabled={running}
            className="text-xs bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 flex items-center gap-1.5 font-medium transition-colors disabled:opacity-50"
            data-testid="run-automation-btn">
            <Play size={13} weight="fill" /> {running ? "Running..." : "Run Now"}
          </button>
          <button onClick={() => setShowLogs(!showLogs)}
            className="text-xs bg-stone-100 text-stone-600 px-3 py-2 rounded-lg hover:bg-stone-200 flex items-center gap-1.5 font-medium transition-colors"
            data-testid="toggle-logs-btn">
            <Clock size={13} /> {showLogs ? "Rules" : "Logs"}
          </button>
          <button onClick={() => openEditor()}
            className="text-xs bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700 flex items-center gap-1.5 font-medium transition-colors"
            data-testid="create-rule-btn">
            <Plus size={13} weight="bold" /> New Rule
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
          {[
            { icon: Lightning, label: "Active Rules", value: stats.active_rules, sub: `of ${stats.total_rules}`, color: "text-amber-600" },
            { icon: PaperPlaneTilt, label: "Total Sent", value: stats.total_sent, color: "text-emerald-600" },
            { icon: CalendarBlank, label: "Sent Today", value: stats.sent_today, color: "text-blue-600" },
            { icon: WarningCircle, label: "Failed", value: stats.failed, color: "text-red-500" },
            { icon: Hourglass, label: "Queued", value: stats.queued, color: "text-amber-500" },
            { icon: Users, label: "By Channel", value: Object.keys(stats.by_channel).length, sub: "channels", color: "text-purple-600" },
          ].map(s => (
            <div key={s.label} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`stat-${s.label.toLowerCase().replace(/\s/g, '-')}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-stone-400 uppercase tracking-wider font-semibold">{s.label}</span>
                <s.icon size={14} className={s.color} weight="fill" />
              </div>
              <span className="text-xl font-bold text-stone-900">{s.value}</span>
              {s.sub && <span className="text-[10px] text-stone-400 ml-1">{s.sub}</span>}
            </div>
          ))}
        </div>
      )}

      {/* Main Content - Rules or Logs */}
      {!showLogs ? (
        <div className="space-y-3" data-testid="rules-list">
          {loading ? (
            <div className="py-10 text-center"><ArrowsClockwise size={24} className="mx-auto animate-spin text-stone-300" /></div>
          ) : rules.length === 0 ? (
            <div className="py-10 text-center bg-white border border-stone-200 rounded-xl">
              <Lightning size={32} className="mx-auto mb-2 text-stone-300" />
              <p className="text-sm text-stone-400">No automation rules yet</p>
              <button onClick={() => openEditor()} className="text-xs text-blue-600 hover:text-blue-700 mt-2 font-medium">Create your first rule</button>
            </div>
          ) : (
            rules.map(rule => {
              const trig = TRIGGER_CONFIG[rule.trigger] || TRIGGER_CONFIG.pre_arrival;
              const chIcon = CHANNEL_ICONS[rule.channel] || CHANNEL_ICONS.email;
              const ChIcon = chIcon.icon;
              return (
                <div key={rule.id} className={`bg-white border border-stone-200 rounded-xl p-4 transition-opacity ${!rule.enabled ? "opacity-50" : ""}`}
                  data-testid={`rule-${rule.id}`}>
                  <div className="flex items-start gap-4">
                    {/* Icon */}
                    <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center flex-shrink-0">
                      <Lightning size={18} className="text-amber-600" weight="fill" />
                    </div>
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-sm font-semibold text-stone-900">{rule.name}</h3>
                        <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${trig.color}`}>{trig.name}</span>
                        <span className="flex items-center gap-1 text-[10px] text-stone-500">
                          <ChIcon size={11} className={chIcon.color} weight="fill" /> {rule.channel}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-stone-400 mb-2">
                        <span className="flex items-center gap-1">
                          <Clock size={10} />
                          {rule.timing_hours < 0 ? `${Math.abs(rule.timing_hours)}h before` : rule.timing_hours === 0 ? "On the day" : `${rule.timing_hours}h after`}
                        </span>
                        {rule.subject && <span>Subject: {rule.subject}</span>}
                        <span className="flex items-center gap-1"><PaperPlaneTilt size={10} /> {rule.total_sent} sent</span>
                      </div>
                      <p className="text-xs text-stone-500 line-clamp-2 whitespace-pre-line">{rule.message_template}</p>
                    </div>
                    {/* Actions */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Switch checked={rule.enabled} onCheckedChange={() => toggleRule(rule)} data-testid={`toggle-rule-${rule.id}`} />
                      <button onClick={() => openEditor(rule)} className="text-stone-400 hover:text-blue-600 transition-colors p-1" data-testid={`edit-rule-${rule.id}`}>
                        <PencilSimple size={14} />
                      </button>
                      <button onClick={() => deleteRule(rule.id)} className="text-stone-400 hover:text-red-500 transition-colors p-1" data-testid={`delete-rule-${rule.id}`}>
                        <Trash size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      ) : (
        /* Logs View */
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="automation-logs">
          <div className="px-4 py-3 border-b border-stone-200 bg-stone-50 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-stone-700 flex items-center gap-1.5">
              <Clock size={14} /> Automation Logs
            </h3>
            <span className="text-xs text-stone-400">{logs.length} entries</span>
          </div>
          <ScrollArea className="max-h-[500px]">
            {logs.length === 0 ? (
              <div className="py-10 text-center text-sm text-stone-400">No logs yet. Run automation to generate entries.</div>
            ) : (
              <table className="w-full" data-testid="logs-table">
                <thead>
                  <tr className="border-b border-stone-100">
                    <th className="text-left px-4 py-2 text-[10px] font-semibold text-stone-400 uppercase">Time</th>
                    <th className="text-left px-4 py-2 text-[10px] font-semibold text-stone-400 uppercase">Rule</th>
                    <th className="text-left px-4 py-2 text-[10px] font-semibold text-stone-400 uppercase">Guest</th>
                    <th className="text-left px-4 py-2 text-[10px] font-semibold text-stone-400 uppercase">Channel</th>
                    <th className="text-left px-4 py-2 text-[10px] font-semibold text-stone-400 uppercase">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => {
                    const chIcon = CHANNEL_ICONS[log.channel] || CHANNEL_ICONS.email;
                    const ChIcon = chIcon.icon;
                    return (
                      <tr key={log.id} className="border-b border-stone-50 hover:bg-stone-50 transition-colors" data-testid={`log-${log.id}`}>
                        <td className="px-4 py-2 text-[11px] text-stone-500">
                          {new Date(log.created_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })} {new Date(log.created_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
                        </td>
                        <td className="px-4 py-2 text-xs font-medium text-stone-700">{log.rule_name}</td>
                        <td className="px-4 py-2">
                          <div className="text-xs text-stone-700">{log.guest_name}</div>
                          <div className="text-[10px] text-stone-400">{log.guest_email}</div>
                        </td>
                        <td className="px-4 py-2">
                          <span className="flex items-center gap-1 text-[11px] text-stone-600">
                            <ChIcon size={12} className={chIcon.color} weight="fill" /> {log.channel}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                            log.status === "sent" ? "bg-emerald-50 text-emerald-700" :
                            log.status === "failed" ? "bg-red-50 text-red-700" :
                            log.status === "queued" ? "bg-amber-50 text-amber-700" :
                            "bg-stone-100 text-stone-600"
                          }`}>{log.status}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </ScrollArea>
        </div>
      )}

      {/* Rule Editor Modal */}
      <Dialog open={showEditor} onOpenChange={setShowEditor}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="rule-editor-modal">
          <DialogHeader>
            <DialogTitle className="text-base flex items-center gap-2">
              <Lightning size={16} className="text-amber-500" weight="fill" />
              {editRule?.id ? "Edit Automation Rule" : "Create Automation Rule"}
            </DialogTitle>
          </DialogHeader>
          {editRule && (
            <div className="space-y-4 mt-3">
              {/* Name */}
              <div>
                <label className="text-[11px] font-medium text-stone-600 mb-1 block">Rule Name *</label>
                <Input value={editRule.name} onChange={e => setEditRule(p => ({ ...p, name: e.target.value }))} placeholder="e.g. Pre-Arrival Welcome Email" className="h-9 text-sm" data-testid="rule-name-input" />
              </div>

              {/* Trigger + Timing */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-medium text-stone-600 mb-1 block">Trigger Event</label>
                  <Select value={editRule.trigger} onValueChange={v => setEditRule(p => ({ ...p, trigger: v }))}>
                    <SelectTrigger className="h-9 text-sm" data-testid="rule-trigger-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(TRIGGER_CONFIG).map(([k, v]) => (
                        <SelectItem key={k} value={k}>{v.name} — {v.desc}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-[11px] font-medium text-stone-600 mb-1 block">Timing (hours)</label>
                  <div className="flex items-center gap-2">
                    <Input type="number" value={editRule.timing_hours} onChange={e => setEditRule(p => ({ ...p, timing_hours: parseInt(e.target.value) || 0 }))}
                      className="h-9 text-sm flex-1" data-testid="rule-timing-input" />
                    <span className="text-[10px] text-stone-400 whitespace-nowrap">
                      {editRule.timing_hours < 0 ? "before event" : editRule.timing_hours === 0 ? "on the day" : "after event"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Channel + Subject */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-medium text-stone-600 mb-1 block">Send via</label>
                  <div className="flex gap-1.5 flex-wrap">
                    {Object.entries(CHANNEL_ICONS).map(([ch, cfg]) => {
                      const Icon = cfg.icon;
                      const active = editRule.channel === ch;
                      return (
                        <button key={ch} onClick={() => setEditRule(p => ({ ...p, channel: ch }))}
                          className={`flex items-center gap-1 text-[11px] px-2.5 py-1.5 rounded-lg border font-medium transition-all ${
                            active ? "bg-emerald-50 text-emerald-700 border-emerald-300" : "bg-white text-stone-500 border-stone-200 hover:bg-stone-50"
                          }`} data-testid={`rule-channel-${ch}`}>
                          <Icon size={12} weight={active ? "fill" : "regular"} /> {ch}
                        </button>
                      );
                    })}
                  </div>
                </div>
                {editRule.channel === "email" && (
                  <div>
                    <label className="text-[11px] font-medium text-stone-600 mb-1 block">Email Subject</label>
                    <Input value={editRule.subject} onChange={e => setEditRule(p => ({ ...p, subject: e.target.value }))} placeholder="Subject line" className="h-9 text-sm" data-testid="rule-subject-input" />
                  </div>
                )}
              </div>

              {/* Message Template */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[11px] font-medium text-stone-600">Message Template *</label>
                  <button onClick={previewTemplate} className="text-[10px] text-blue-600 hover:text-blue-700 flex items-center gap-1 font-medium" data-testid="preview-template-btn">
                    <Eye size={10} /> Preview
                  </button>
                </div>
                <Textarea value={editRule.message_template} onChange={e => setEditRule(p => ({ ...p, message_template: e.target.value }))}
                  placeholder="Type your message template..." rows={6} className="text-sm resize-none font-mono" data-testid="rule-template-input" />
              </div>

              {/* Template Variables */}
              <div>
                <span className="text-[10px] font-semibold text-stone-400 uppercase tracking-wider">Available Variables (click to insert)</span>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {TEMPLATE_VARS.map(v => (
                    <button key={v.var} onClick={() => setEditRule(p => ({ ...p, message_template: p.message_template + v.var }))}
                      className="text-[10px] bg-blue-50 text-blue-700 px-2 py-1 rounded hover:bg-blue-100 transition-colors font-mono"
                      title={v.desc}>{v.var}</button>
                  ))}
                </div>
              </div>

              {/* Preview */}
              {preview && (
                <div className="bg-stone-50 border border-stone-200 rounded-lg p-3" data-testid="template-preview">
                  <span className="text-[10px] font-semibold text-stone-400 uppercase mb-1 block">Preview (sample data)</span>
                  <p className="text-xs text-stone-700 whitespace-pre-line">{preview}</p>
                </div>
              )}

              {/* Save */}
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setShowEditor(false)} className="text-xs text-stone-500 hover:text-stone-700 px-4 py-2">Cancel</button>
                <button onClick={saveRule}
                  className="text-xs bg-emerald-600 text-white px-5 py-2 rounded-lg hover:bg-emerald-700 font-medium transition-colors flex items-center gap-1.5"
                  data-testid="save-rule-btn">
                  <CheckCircle size={13} weight="fill" /> {editRule.id ? "Update Rule" : "Create Rule"}
                </button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
