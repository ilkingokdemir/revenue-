import { useState, useEffect, useRef } from "react";
import { ChatCircleDots, PaperPlaneRight, X, Robot, User } from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export function AIConciergeChat({ propertyId, tmpl }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  useEffect(scrollToBottom, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: text }]);
    setLoading(true);
    try {
      const res = await fetch(`${API}/concierge/chat?property_id=${propertyId}&message=${encodeURIComponent(text)}&session_id=${sessionId}`, { method: "POST" });
      const data = await res.json();
      setMessages(prev => [...prev, { role: "assistant", content: data.reply }]);
      if (data.session_id) setSessionId(data.session_id);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Sorry, I'm having trouble connecting. Please try again." }]);
    }
    setLoading(false);
  };

  return (
    <>
      {/* Floating Chat Button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-20 sm:bottom-6 right-4 sm:right-6 z-50 w-14 h-14 rounded-full shadow-2xl flex items-center justify-center transition-transform hover:scale-110"
          style={{ background: tmpl?.colors?.accent || "#2563eb" }}
          data-testid="concierge-chat-btn"
        >
          <ChatCircleDots size={26} weight="fill" className="text-white" />
        </button>
      )}

      {/* Chat Window */}
      {open && (
        <div className="fixed bottom-20 sm:bottom-6 right-4 sm:right-6 z-50 w-[360px] max-h-[500px] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden" data-testid="concierge-chat-window">
          {/* Header */}
          <div className="px-4 py-3 flex items-center justify-between flex-shrink-0" style={{ background: tmpl?.colors?.accent || "#2563eb" }}>
            <div className="flex items-center gap-2 text-white">
              <Robot size={20} weight="fill" />
              <div>
                <span className="font-semibold text-sm block leading-tight">Hotel Concierge</span>
                <span className="text-[10px] opacity-70">AI-powered assistant</span>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/70 hover:text-white" data-testid="close-concierge">
              <X size={18} />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-[280px] max-h-[350px]" data-testid="concierge-messages">
            {messages.length === 0 && (
              <div className="text-center py-8">
                <Robot size={36} className="mx-auto text-slate-300 mb-3" />
                <p className="text-sm font-medium text-slate-700">How can I help you?</p>
                <p className="text-xs text-slate-400 mt-1">Ask about rooms, facilities, check-in, or anything else</p>
                <div className="flex flex-wrap gap-1.5 justify-center mt-4">
                  {["What rooms are available?", "Check-in time?", "Is parking available?", "Pet policy?"].map(q => (
                    <button key={q} onClick={() => { setInput(q); }}
                      className="text-[11px] px-2.5 py-1.5 rounded-full border border-gray-200 text-slate-600 hover:bg-gray-50 transition-colors"
                      data-testid={`quick-q-${q.slice(0,10)}`}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "assistant" && (
                  <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: `${tmpl?.colors?.accent || "#2563eb"}15` }}>
                    <Robot size={14} style={{ color: tmpl?.colors?.accent || "#2563eb" }} />
                  </div>
                )}
                <div className={`max-w-[75%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${msg.role === "user" ? "text-white rounded-br-md" : "bg-gray-100 text-slate-800 rounded-bl-md"}`}
                  style={msg.role === "user" ? { background: tmpl?.colors?.accent || "#2563eb" } : {}}>
                  {msg.content}
                </div>
                {msg.role === "user" && (
                  <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
                    <User size={14} className="text-slate-500" />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex gap-2">
                <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: `${tmpl?.colors?.accent || "#2563eb"}15` }}>
                  <Robot size={14} style={{ color: tmpl?.colors?.accent || "#2563eb" }} />
                </div>
                <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 p-3 flex-shrink-0">
            <div className="flex gap-2">
              <input
                value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && sendMessage()}
                placeholder="Type your question..."
                className="flex-1 border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:ring-2 focus:border-transparent"
                style={{ "--tw-ring-color": tmpl?.colors?.accent || "#2563eb" }}
                data-testid="concierge-input"
              />
              <button onClick={sendMessage} disabled={!input.trim() || loading}
                className="w-10 h-10 rounded-xl flex items-center justify-center text-white disabled:opacity-40 transition-colors"
                style={{ background: tmpl?.colors?.accent || "#2563eb" }}
                data-testid="concierge-send-btn">
                <PaperPlaneRight size={18} weight="fill" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
