import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  ChatText, WhatsappLogo, Envelope, DeviceMobile, Globe,
  PaperPlaneTilt, Sparkle, CheckCircle, WarningCircle, Clock, User,
  FunnelSimple, ArrowsClockwise, Tag, UserCircle, X, MagnifyingGlass,
  Lightning, CaretRight, Phone, Buildings, Bed, CalendarBlank,
  ChatCircleDots, Robot, SmileyMeh, Smiley, SmileySad,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CHANNEL_CONFIG = {
  whatsapp: { name: "WhatsApp", icon: WhatsappLogo, color: "#25D366", bg: "bg-green-50", text: "text-green-700" },
  email: { name: "Email", icon: Envelope, color: "#3b82f6", bg: "bg-blue-50", text: "text-blue-700" },
  sms: { name: "SMS", icon: DeviceMobile, color: "#8b5cf6", bg: "bg-purple-50", text: "text-purple-700" },
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

export function MessagingHub({ properties, user }) {
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
  const messagesEndRef = useRef(null);
  const activePropertyId = properties?.[0]?.id || "aldgate-flats";

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
    } catch (e) { console.error("Fetch conversations error:", e); }
  }, [activePropertyId, filterStatus, filterChannel]);

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/messaging/conversations/${activePropertyId}/stats`);
      setStats(data);
    } catch (e) { console.error("Fetch stats error:", e); }
  }, [activePropertyId]);

  const fetchMessages = useCallback(async (convId) => {
    setMsgLoading(true);
    try {
      const { data } = await axios.get(`${API}/messaging/messages/${convId}`);
      setMessages(data);
      setTimeout(scrollToBottom, 100);
    } catch (e) { console.error("Fetch messages error:", e); }
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
      // Seed if needed
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
    fetchMessages(conv.id);
    // Update unread locally
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
      fetchConversations();
      fetchStats();
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
      <div className="border-b border-stone-200 bg-white px-5 py-3 flex items-center gap-6 flex-shrink-0">
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
                const ChannelIcon = cfg.icon;
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
                          <div className={`max-w-[70%] ${isGuest ? "" : ""}`}>
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
                      className="w-full text-left px-3 py-2 hover:bg-stone-50 border-b border-stone-50 last:border-0 transition-colors"
                      data-testid={`qr-${qr.id}`}>
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
              <p className="text-xs text-stone-300 mt-1">Choose from the list on the left to start responding</p>
            </div>
          </div>
        )}

        {/* Guest Profile Sidebar */}
        {selectedConv && (
          <div className="w-[260px] border-l border-stone-200 bg-white flex-shrink-0 overflow-y-auto" data-testid="guest-profile-sidebar">
            <div className="p-4 border-b border-stone-100 text-center">
              <div className="w-14 h-14 rounded-full mx-auto flex items-center justify-center text-white text-xl font-bold mb-2" style={{ background: CHANNEL_CONFIG[selectedConv.channel]?.color || "#64748b" }}>
                {selectedConv.guest_name.charAt(0).toUpperCase()}
              </div>
              <h4 className="text-sm font-semibold text-stone-900">{selectedConv.guest_name}</h4>
              <p className="text-[11px] text-stone-400 mt-0.5">{selectedConv.guest_email}</p>
              {selectedConv.guest_phone && <p className="text-[11px] text-stone-400">{selectedConv.guest_phone}</p>}
            </div>

            <div className="p-4 space-y-4">
              {/* Channel & Status */}
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

              {/* Tags */}
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

              {/* Quick Actions */}
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

              {/* Created */}
              <div className="text-[10px] text-stone-400 pt-2 border-t border-stone-100">
                Created: {new Date(selectedConv.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
