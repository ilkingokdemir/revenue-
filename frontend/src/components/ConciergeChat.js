/**
 * AI Concierge Chat — floating bubble for the public booking widget.
 * Click → expands into a chat sheet anchored bottom-right. Persists a
 * session_id in localStorage so the same visitor can pick up the thread.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { MessageCircle, X, Send, Loader2, Sparkles } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const sessionKey = (propertyId) => `concierge_session_${propertyId}`;

export default function ConciergeChat({ propertyId, hotelName = "", accentColor = "#1a3c5e" }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [suggestions, setSuggestions] = useState(["Show me the rooms", "Check-in time?", "Is parking available?"]);
  const [sessionId, setSessionId] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    let s = localStorage.getItem(sessionKey(propertyId));
    if (!s) {
      s = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(sessionKey(propertyId), s);
    }
    setSessionId(s);
  }, [propertyId]);

  const loadHistory = useCallback(async () => {
    if (!propertyId || !sessionId) return;
    try {
      const { data } = await axios.get(`${API}/concierge/${propertyId}/history?session_id=${sessionId}`);
      setMessages(data.messages || []);
    } catch { /* noop */ }
  }, [propertyId, sessionId]);

  useEffect(() => { if (open && sessionId) loadHistory(); }, [open, sessionId, loadHistory]);
  useEffect(() => { setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 80); }, [messages, open]);

  const send = async (text) => {
    const msg = (text || input).trim();
    if (!msg || sending) return;
    setInput("");
    setMessages(m => [...m, { role: "user", content: msg, created_at: new Date().toISOString() }]);
    setSending(true);
    try {
      const { data } = await axios.post(`${API}/concierge/${propertyId}/chat`,
        { session_id: sessionId, message: msg });
      setMessages(m => [...m, { role: "assistant", content: data.reply, created_at: new Date().toISOString() }]);
      if (data.suggestions?.length) setSuggestions(data.suggestions);
    } catch {
      setMessages(m => [...m, { role: "assistant", content: "Sorry, I'm offline right now. Please use the booking form.", created_at: new Date().toISOString() }]);
    }
    setSending(false);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        data-testid="concierge-open"
        style={{ background: accentColor }}
        className="fixed bottom-20 right-5 z-50 flex items-center gap-2 rounded-full px-5 py-3 text-white shadow-2xl hover:shadow-amber-500/30 transition-all hover:scale-105">
        <Sparkles className="w-4 h-4" />
        <span className="text-sm font-bold">Need help?</span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-20 right-5 z-50 w-[380px] max-w-[calc(100vw-2rem)] h-[560px] max-h-[calc(100vh-7rem)] bg-white rounded-2xl shadow-2xl border border-stone-200 flex flex-col overflow-hidden" data-testid="concierge-panel">
      {/* Header */}
      <div className="px-4 py-3 text-white flex items-center justify-between" style={{ background: accentColor }}>
        <div>
          <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest opacity-80">
            <Sparkles className="w-3 h-3" />AI Concierge
          </div>
          <p className="text-sm font-bold">{hotelName || "Hotel"}</p>
        </div>
        <button onClick={() => setOpen(false)} data-testid="concierge-close" className="p-1.5 rounded-full hover:bg-white/15">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-stone-50">
        {messages.length === 0 && (
          <div className="text-center py-8 text-stone-500 text-sm">
            <MessageCircle className="w-10 h-10 mx-auto mb-2 opacity-30" style={{ color: accentColor }} />
            <p className="font-bold">Hi! I'm your AI concierge.</p>
            <p className="text-xs mt-1">Ask me anything about your stay.</p>
          </div>
        )}
        {messages.map((m, i) => {
          const out = m.role === "user";
          return (
            <div key={i} className={`flex ${out ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm shadow-sm whitespace-pre-wrap leading-relaxed ${out ? "rounded-br-sm text-white" : "bg-white text-stone-800 rounded-bl-sm border border-stone-100"}`}
                style={out ? { background: accentColor } : undefined}>
                {m.content}
              </div>
            </div>
          );
        })}
        {sending && (
          <div className="flex justify-start">
            <div className="bg-white border border-stone-100 rounded-2xl rounded-bl-sm px-3 py-2 text-sm">
              <Loader2 className="w-3 h-3 animate-spin inline mr-2" />Thinking…
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Suggestions */}
      {!sending && suggestions?.length > 0 && (
        <div className="flex gap-1.5 px-3 py-2 border-t border-stone-100 bg-white overflow-x-auto" data-testid="concierge-suggestions">
          {suggestions.map((s, i) => (
            <button key={i} onClick={() => send(s)} data-testid={`concierge-suggestion-${i}`}
              className="text-[10px] font-bold whitespace-nowrap rounded-full border px-2.5 py-1 hover:bg-stone-50 transition"
              style={{ color: accentColor, borderColor: `${accentColor}33` }}>
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Composer */}
      <div className="p-3 border-t border-stone-100 bg-white">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") send(); }}
            placeholder="Type your question…"
            disabled={sending}
            data-testid="concierge-input"
            className="flex-1 border border-stone-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-stone-300 outline-none" />
          <button onClick={() => send()} disabled={sending || !input.trim()}
            data-testid="concierge-send"
            style={{ background: accentColor }}
            className="px-3 rounded-lg text-white disabled:opacity-50">
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[9px] text-stone-400 mt-1.5 text-center">Powered by AI · sometimes makes mistakes</p>
      </div>
    </div>
  );
}
