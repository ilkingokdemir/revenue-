import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  ChatText, Envelope, PaperPlaneTilt, Sparkle, CheckCircle,
  ArrowsClockwise, X, Plus, Star, Smiley, SmileyMeh, SmileySad,
  WhatsappLogo, DeviceMobile, CaretRight,
} from "@phosphor-icons/react";
import { BarChart3, Send, Settings, MessageSquare, TrendingUp, Users, Award } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function NpsGauge({ score, size = "lg" }) {
  const color = score >= 9 ? "#059669" : score >= 7 ? "#d97706" : "#dc2626";
  const label = score >= 9 ? "Promoter" : score >= 7 ? "Passive" : "Detractor";
  return (
    <div className={`flex flex-col items-center ${size === "lg" ? "gap-1" : "gap-0.5"}`}>
      <span className={`font-bold ${size === "lg" ? "text-4xl" : "text-xl"}`} style={{ color }}>{score}</span>
      <span className={`${size === "lg" ? "text-xs" : "text-[10px]"} font-medium`} style={{ color }}>{label}</span>
    </div>
  );
}

function NpsDistribution({ promoters, passives, detractors }) {
  const total = promoters + passives + detractors;
  if (!total) return null;
  const pP = Math.round((promoters / total) * 100);
  const paP = Math.round((passives / total) * 100);
  const dP = 100 - pP - paP;
  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden">
        {pP > 0 && <div className="bg-emerald-500 transition-all" style={{ width: `${pP}%` }} />}
        {paP > 0 && <div className="bg-amber-400 transition-all" style={{ width: `${paP}%` }} />}
        {dP > 0 && <div className="bg-red-500 transition-all" style={{ width: `${dP}%` }} />}
      </div>
      <div className="flex justify-between mt-1.5 text-[10px]">
        <span className="text-emerald-600 font-medium">{promoters} Promoters ({pP}%)</span>
        <span className="text-amber-600 font-medium">{passives} Passive ({paP}%)</span>
        <span className="text-red-600 font-medium">{detractors} Detractors ({dP}%)</span>
      </div>
    </div>
  );
}

export function SurveyPanel({ properties, user, activePropertyId: propActivePropertyId }) {
  const [tab, setTab] = useState("analytics");
  const [analytics, setAnalytics] = useState(null);
  const [responses, setResponses] = useState([]);
  const [invites, setInvites] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("30d");
  const [sending, setSending] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [manualForm, setManualForm] = useState({ guest_name: "", guest_email: "", booking_ref: "" });

  const activePropertyId = (propActivePropertyId && propActivePropertyId !== "all") ? propActivePropertyId : (properties?.[0]?.id || "aldgate-flats");

  const fetchAnalytics = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/surveys/analytics/${activePropertyId}?period=${period}`);
      setAnalytics(data);
    } catch (e) { console.error(e); }
  }, [activePropertyId, period]);

  const fetchResponses = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/surveys/responses/${activePropertyId}?period=${period}`);
      setResponses(data);
    } catch (e) { console.error(e); }
  }, [activePropertyId, period]);

  const fetchInvites = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/surveys/invites/${activePropertyId}`);
      setInvites(data);
    } catch (e) { console.error(e); }
  }, [activePropertyId]);

  const fetchSettings = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/surveys/settings/${activePropertyId}`);
      setSettings(data);
    } catch (e) { console.error(e); }
  }, [activePropertyId]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([fetchAnalytics(), fetchResponses(), fetchInvites(), fetchSettings()]);
      setLoading(false);
    };
    init();
  }, [fetchAnalytics, fetchResponses, fetchInvites, fetchSettings]);

  const sendSurveys = async () => {
    setSending(true);
    try {
      const { data } = await axios.post(`${API}/surveys/send/${activePropertyId}`);
      toast.success(`${data.sent} survey(s) sent`);
      fetchInvites();
      fetchAnalytics();
    } catch (e) { toast.error("Failed to send surveys"); }
    finally { setSending(false); }
  };

  const sendManual = async () => {
    if (!manualForm.guest_name || !manualForm.guest_email) return toast.error("Name and email required");
    try {
      const { data } = await axios.post(`${API}/surveys/send-manual`, { ...manualForm, property_id: activePropertyId });
      toast.success(`Survey sent to ${manualForm.guest_name}`);
      setManualForm({ guest_name: "", guest_email: "", booking_ref: "" });
      fetchInvites();
    } catch (e) { toast.error("Failed to send"); }
  };

  const saveSettings = async () => {
    setSavingSettings(true);
    try {
      await axios.put(`${API}/surveys/settings/${activePropertyId}`, settings);
      toast.success("Settings saved");
    } catch (e) { toast.error("Failed to save"); }
    finally { setSavingSettings(false); }
  };

  const upd = (key, val) => setSettings(prev => ({ ...prev, [key]: val }));

  const tabs = [
    { id: "analytics", label: "Analytics", icon: BarChart3 },
    { id: "responses", label: "Responses", icon: MessageSquare },
    { id: "send", label: "Send", icon: Send },
    { id: "settings", label: "Settings", icon: Settings },
  ];

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <ArrowsClockwise size={24} className="animate-spin text-stone-300" />
    </div>
  );

  return (
    <div className="h-[calc(100vh-0px)] flex flex-col" data-testid="survey-panel">
      {/* Header */}
      <div className="border-b border-stone-200 bg-white px-6 py-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center">
            <Award size={18} className="text-emerald-700" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Guest Satisfaction Surveys</h2>
            <p className="text-xs text-stone-400">NPS scores, category ratings & guest feedback</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={period} onValueChange={v => { setPeriod(v); }}>
            <SelectTrigger className="h-8 text-xs w-28 border-stone-200"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="14d">Last 14 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <button onClick={sendSurveys} disabled={sending}
            className="text-xs bg-emerald-600 text-white px-3 py-1.5 rounded-lg hover:bg-emerald-700 flex items-center gap-1.5 font-medium disabled:opacity-50"
            data-testid="auto-send-surveys-btn">
            <Send size={12} /> {sending ? "Sending..." : "Auto-Send"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-stone-200 bg-white px-6 flex gap-1 flex-shrink-0">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium transition-colors border-b-2 ${
              tab === t.id ? "border-emerald-500 text-emerald-700" : "border-transparent text-stone-400 hover:text-stone-600"
            }`} data-testid={`survey-tab-${t.id}`}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto bg-stone-50">
        {/* Analytics Tab */}
        {tab === "analytics" && analytics && (
          <div className="p-6 space-y-6 max-w-5xl mx-auto" data-testid="survey-analytics">
            {/* KPI Row */}
            <div className="grid grid-cols-5 gap-4">
              <div className="bg-white rounded-xl border border-stone-200 p-4 text-center">
                <span className="text-3xl font-bold text-emerald-700">{analytics.nps_net_score}</span>
                <p className="text-[10px] text-stone-500 mt-1">Net NPS Score</p>
              </div>
              <div className="bg-white rounded-xl border border-stone-200 p-4 text-center">
                <span className="text-3xl font-bold text-stone-800">{analytics.avg_nps}</span>
                <p className="text-[10px] text-stone-500 mt-1">Avg NPS</p>
              </div>
              <div className="bg-white rounded-xl border border-stone-200 p-4 text-center">
                <span className="text-3xl font-bold text-blue-700">{analytics.total_responses}</span>
                <p className="text-[10px] text-stone-500 mt-1">Responses</p>
              </div>
              <div className="bg-white rounded-xl border border-stone-200 p-4 text-center">
                <span className="text-3xl font-bold text-stone-800">{analytics.total_sent}</span>
                <p className="text-[10px] text-stone-500 mt-1">Surveys Sent</p>
              </div>
              <div className="bg-white rounded-xl border border-stone-200 p-4 text-center">
                <span className="text-3xl font-bold text-amber-700">{analytics.response_rate}%</span>
                <p className="text-[10px] text-stone-500 mt-1">Response Rate</p>
              </div>
            </div>

            {/* NPS Distribution */}
            <div className="bg-white rounded-xl border border-stone-200 p-5">
              <h3 className="text-sm font-semibold text-stone-800 mb-3">NPS Distribution</h3>
              <NpsDistribution promoters={analytics.promoters} passives={analytics.passives} detractors={analytics.detractors} />
            </div>

            {/* Category Ratings */}
            {Object.keys(analytics.category_averages || {}).length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-5">
                <h3 className="text-sm font-semibold text-stone-800 mb-3">Category Ratings</h3>
                <div className="space-y-3">
                  {Object.entries(analytics.category_averages).map(([cat, avg]) => (
                    <div key={cat} className="flex items-center gap-3">
                      <span className="text-xs text-stone-600 w-28 capitalize">{cat.replace(/_/g, " ")}</span>
                      <div className="flex-1 h-2.5 bg-stone-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all" style={{
                          width: `${(avg / 5) * 100}%`,
                          background: avg >= 4 ? "#059669" : avg >= 3 ? "#d97706" : "#dc2626"
                        }} />
                      </div>
                      <span className="text-xs font-semibold text-stone-700 w-8 text-right">{avg}/5</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Comments */}
            {analytics.recent_comments?.length > 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-5">
                <h3 className="text-sm font-semibold text-stone-800 mb-3">Recent Feedback</h3>
                <div className="space-y-3">
                  {analytics.recent_comments.map((c, i) => (
                    <div key={i} className="flex items-start gap-3 border-b border-stone-50 pb-3 last:border-0 last:pb-0">
                      <NpsGauge score={c.nps_score} size="sm" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-stone-800">{c.guest_name}</span>
                          <span className="text-[10px] text-stone-400">{c.date}</span>
                        </div>
                        <p className="text-xs text-stone-600 mt-0.5">{c.comment}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {analytics.total_responses === 0 && (
              <div className="bg-white rounded-xl border border-stone-200 p-10 text-center">
                <Award size={32} className="mx-auto text-stone-300 mb-3" />
                <p className="text-sm text-stone-500">No survey responses yet</p>
                <p className="text-xs text-stone-400 mt-1">Send surveys to guests after checkout to collect feedback</p>
              </div>
            )}
          </div>
        )}

        {/* Responses Tab */}
        {tab === "responses" && (
          <div className="p-6 max-w-5xl mx-auto" data-testid="survey-responses">
            {responses.length === 0 ? (
              <div className="bg-white rounded-xl border border-stone-200 p-10 text-center">
                <MessageSquare size={32} className="mx-auto text-stone-300 mb-3" />
                <p className="text-sm text-stone-500">No responses in this period</p>
              </div>
            ) : (
              <div className="space-y-3">
                {responses.map(r => (
                  <motion.div key={r.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    className="bg-white rounded-xl border border-stone-200 p-4" data-testid={`response-${r.id}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        <NpsGauge score={r.nps_score} size="sm" />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-semibold text-stone-800">{r.guest_name}</span>
                            <span className="text-[10px] text-stone-400">{r.guest_email}</span>
                            {r.booking_ref && <span className="text-[10px] bg-stone-100 text-stone-500 px-1.5 py-0.5 rounded">#{r.booking_ref}</span>}
                          </div>
                          {/* Category ratings */}
                          {Object.keys(r.category_ratings || {}).length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-1.5">
                              {Object.entries(r.category_ratings).map(([k, v]) => (
                                <span key={k} className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                                  v >= 4 ? "bg-emerald-50 text-emerald-700" : v >= 3 ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-700"
                                }`}>{k.replace(/_/g, " ")}: {v}/5</span>
                              ))}
                            </div>
                          )}
                          {r.comment && <p className="text-xs text-stone-600">{r.comment}</p>}
                        </div>
                      </div>
                      <span className="text-[10px] text-stone-400 flex-shrink-0">{r.created_at?.slice(0, 10)}</span>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Send Tab */}
        {tab === "send" && (
          <div className="p-6 max-w-3xl mx-auto space-y-6" data-testid="survey-send">
            {/* Auto Send */}
            <div className="bg-white rounded-xl border border-stone-200 p-5">
              <h3 className="text-sm font-semibold text-stone-800 mb-2 flex items-center gap-2">
                <Send size={14} className="text-emerald-600" /> Auto-Send to Recent Checkouts
              </h3>
              <p className="text-xs text-stone-500 mb-4">Automatically sends surveys to guests who checked out recently (based on your configured delay).</p>
              <button onClick={sendSurveys} disabled={sending}
                className="bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
                data-testid="send-auto-btn">
                <Send size={14} /> {sending ? "Sending..." : "Send Surveys Now"}
              </button>
            </div>

            {/* Manual Send */}
            <div className="bg-white rounded-xl border border-stone-200 p-5">
              <h3 className="text-sm font-semibold text-stone-800 mb-2 flex items-center gap-2">
                <Users size={14} className="text-blue-600" /> Send to Specific Guest
              </h3>
              <div className="grid grid-cols-3 gap-3 mt-3">
                <div>
                  <label className="text-[11px] font-medium text-stone-600 mb-1 block">Guest Name *</label>
                  <Input value={manualForm.guest_name} onChange={e => setManualForm(p => ({ ...p, guest_name: e.target.value }))} placeholder="Guest name" className="h-8 text-sm" data-testid="manual-guest-name" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-stone-600 mb-1 block">Email *</label>
                  <Input value={manualForm.guest_email} onChange={e => setManualForm(p => ({ ...p, guest_email: e.target.value }))} placeholder="guest@email.com" className="h-8 text-sm" data-testid="manual-guest-email" />
                </div>
                <div>
                  <label className="text-[11px] font-medium text-stone-600 mb-1 block">Booking Ref</label>
                  <Input value={manualForm.booking_ref} onChange={e => setManualForm(p => ({ ...p, booking_ref: e.target.value }))} placeholder="MHB-XXXX" className="h-8 text-sm" />
                </div>
              </div>
              <button onClick={sendManual}
                className="mt-3 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2"
                data-testid="send-manual-btn">
                <Envelope size={14} /> Send Survey
              </button>
            </div>

            {/* Recent Invites */}
            <div className="bg-white rounded-xl border border-stone-200 p-5">
              <h3 className="text-sm font-semibold text-stone-800 mb-3">Recent Survey Invites</h3>
              {invites.length === 0 ? (
                <p className="text-xs text-stone-400">No invites sent yet</p>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {invites.slice(0, 20).map(inv => (
                    <div key={inv.id} className="flex items-center justify-between text-xs bg-stone-50 rounded-lg px-3 py-2" data-testid={`invite-${inv.id}`}>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-stone-700">{inv.guest_name}</span>
                        <span className="text-stone-400">{inv.guest_email}</span>
                        {inv.booking_ref && <span className="text-[10px] text-stone-400">#{inv.booking_ref}</span>}
                      </div>
                      <div className="flex items-center gap-2">
                        {inv.completed ? (
                          <span className="text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full font-medium flex items-center gap-0.5"><CheckCircle size={10} weight="fill" /> Completed</span>
                        ) : (
                          <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full font-medium">Pending</span>
                        )}
                        <span className="text-[10px] text-stone-400">{inv.sent_at?.slice(0, 10)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Settings Tab */}
        {tab === "settings" && settings && (
          <div className="p-6 max-w-3xl mx-auto space-y-4" data-testid="survey-settings">
            <div className="bg-white rounded-xl border border-stone-200 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-stone-800">Enable Surveys</h3>
                  <p className="text-[10px] text-stone-400">Turn on/off guest satisfaction surveys</p>
                </div>
                <Switch checked={settings.enabled} onCheckedChange={v => upd("enabled", v)} data-testid="survey-enabled-toggle" />
              </div>

              <div className="border-t border-stone-100 pt-4">
                <h4 className="text-xs font-semibold text-stone-700 mb-2">Delivery</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] font-medium text-stone-600 mb-1 block">Send Delay (hours after checkout)</label>
                    <Input type="number" value={settings.send_delay_hours} onChange={e => upd("send_delay_hours", parseInt(e.target.value) || 2)} className="h-8 text-sm" data-testid="delay-hours-input" />
                  </div>
                  <div>
                    <label className="text-[11px] font-medium text-stone-600 mb-1 block">Survey Type</label>
                    <Select value={settings.survey_type} onValueChange={v => upd("survey_type", v)}>
                      <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="nps_only">NPS Only (Quick)</SelectItem>
                        <SelectItem value="detailed">Detailed (NPS + Categories)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex items-center gap-4 mt-3">
                  <label className="flex items-center gap-2 text-xs text-stone-600">
                    <input type="checkbox" checked={settings.channels?.includes("email")} onChange={e => {
                      const chs = settings.channels || [];
                      upd("channels", e.target.checked ? [...chs, "email"] : chs.filter(c => c !== "email"));
                    }} className="rounded" /> <Envelope size={14} /> Email
                  </label>
                  <label className="flex items-center gap-2 text-xs text-stone-600">
                    <input type="checkbox" checked={settings.channels?.includes("whatsapp")} onChange={e => {
                      const chs = settings.channels || [];
                      upd("channels", e.target.checked ? [...chs, "whatsapp"] : chs.filter(c => c !== "whatsapp"));
                    }} className="rounded" /> <WhatsappLogo size={14} /> WhatsApp
                  </label>
                </div>
              </div>

              <div className="border-t border-stone-100 pt-4">
                <h4 className="text-xs font-semibold text-stone-700 mb-2">Email Template</h4>
                <div className="space-y-2">
                  <div>
                    <label className="text-[11px] font-medium text-stone-600 mb-1 block">Subject</label>
                    <Input value={settings.email_subject} onChange={e => upd("email_subject", e.target.value)} className="h-8 text-sm" data-testid="email-subject-input" />
                  </div>
                  <div>
                    <label className="text-[11px] font-medium text-stone-600 mb-1 block">Body</label>
                    <Textarea value={settings.email_body} onChange={e => upd("email_body", e.target.value)} rows={3} className="text-sm resize-none" />
                  </div>
                  <div>
                    <label className="text-[11px] font-medium text-stone-600 mb-1 block">Thank You Message</label>
                    <Input value={settings.thank_you_message} onChange={e => upd("thank_you_message", e.target.value)} className="h-8 text-sm" />
                  </div>
                </div>
              </div>

              <div className="border-t border-stone-100 pt-4">
                <h4 className="text-xs font-semibold text-stone-700 mb-2">Alerts & Automation</h4>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs text-stone-700">Low Score Alert</span>
                      <p className="text-[10px] text-stone-400">Get notified when NPS is below threshold</p>
                    </div>
                    <Switch checked={settings.low_score_alert_enabled} onCheckedChange={v => upd("low_score_alert_enabled", v)} />
                  </div>
                  {settings.low_score_alert_enabled && (
                    <div className="ml-0">
                      <label className="text-[11px] font-medium text-stone-600 mb-1 block">Alert Threshold (NPS score)</label>
                      <Input type="number" min={0} max={10} value={settings.low_score_alert_threshold} onChange={e => upd("low_score_alert_threshold", parseInt(e.target.value) || 6)} className="h-8 text-sm w-24" />
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs text-stone-700">Auto-Tag Guest Profiles</span>
                      <p className="text-[10px] text-stone-400">Tag guests as promoter/passive/detractor</p>
                    </div>
                    <Switch checked={settings.auto_tag_profiles} onCheckedChange={v => upd("auto_tag_profiles", v)} />
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-xs text-stone-700">Send Reminder</span>
                      <p className="text-[10px] text-stone-400">Remind guests who haven't responded</p>
                    </div>
                    <Switch checked={settings.reminder_enabled} onCheckedChange={v => upd("reminder_enabled", v)} />
                  </div>
                </div>
              </div>

              <button onClick={saveSettings} disabled={savingSettings}
                className="w-full bg-emerald-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
                data-testid="save-survey-settings-btn">
                {savingSettings ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
