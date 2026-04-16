import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Bot, Send, Trash2, Sparkles, TrendingUp, Target, Zap, ArrowRight, User, Mic, MicOff, Square } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const QUICK_PROMPTS = [
  { icon: TrendingUp, label: "How is today's performance?", prompt: "Give me a quick summary of today's performance — occupancy, ADR, RevPAR — and any concerns." },
  { icon: Target, label: "What should I do this week?", prompt: "What are the top 3 revenue actions I should take this week based on current booking data and upcoming demand?" },
  { icon: Zap, label: "Rate recommendations", prompt: "Based on current occupancy patterns and demand, what specific rate changes do you recommend for the next 7 days? Give me exact numbers." },
  { icon: Sparkles, label: "Revenue opportunities", prompt: "Analyze my hotel data and identify the biggest revenue opportunities I'm missing right now. Be specific with potential revenue impact." },
];

export const RevenueAICopilot = ({ propertyId }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/revenue/copilot/${propertyId}/history`).then(r => {
      setMessages(r.data.messages || []);
      setHistoryLoaded(true);
    }).catch(() => setHistoryLoaded(true));
  }, [propertyId]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Voice input using Web Speech API
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef(null);

  const startVoice = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { toast.error("Voice input not supported in this browser"); return; }
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-GB";
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results).map(r => r[0].transcript).join("");
      setInput(transcript);
    };
    recognition.onend = () => setIsRecording(false);
    recognition.onerror = () => { setIsRecording(false); toast.error("Voice recognition failed"); };
    recognitionRef.current = recognition;
    recognition.start();
    setIsRecording(true);
  }, []);

  const stopVoice = useCallback(() => {
    if (recognitionRef.current) { recognitionRef.current.stop(); }
    setIsRecording(false);
  }, []);

  const send = async (text) => {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");
    setLoading(true);

    const userMsg = { id: Date.now().toString(), role: "user", content: msg, created_at: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);

    try {
      const { data } = await axios.post(`${API}/revenue/copilot/${propertyId}/chat`, { message: msg });
      const assistantMsg = { id: data.message_id, role: "assistant", content: data.response, created_at: new Date().toISOString() };
      setMessages(prev => [...prev, assistantMsg]);
    } catch {
      toast.error("Failed to get response");
      setMessages(prev => [...prev, { id: "err", role: "assistant", content: "Sorry, I couldn't process that request. Please try again.", created_at: new Date().toISOString() }]);
    }
    setLoading(false);
    inputRef.current?.focus();
  };

  const clear = async () => {
    try {
      await axios.delete(`${API}/revenue/copilot/${propertyId}/clear`);
      setMessages([]);
      toast.success("Chat cleared");
    } catch { toast.error("Failed"); }
  };

  const formatMessage = (text) => {
    if (!text) return "";
    return text.split("\n").map((line, i) => {
      if (line.startsWith("###")) return <h3 key={i} className="font-bold text-base mt-3 mb-1">{line.replace(/^###\s*/, "")}</h3>;
      if (line.startsWith("**") && line.endsWith("**")) return <p key={i} className="font-bold mt-2">{line.replace(/\*\*/g, "")}</p>;
      if (line.startsWith("- ") || line.startsWith("• ")) return <li key={i} className="ml-4 list-disc">{line.replace(/^[-•]\s*/, "").replace(/\*\*(.*?)\*\*/g, "$1")}</li>;
      if (line.match(/^\d+\.\s/)) return <li key={i} className="ml-4 list-decimal">{line.replace(/^\d+\.\s*/, "").replace(/\*\*(.*?)\*\*/g, "$1")}</li>;
      if (line.trim() === "") return <br key={i} />;
      return <p key={i} className="mt-1">{line.replace(/\*\*(.*?)\*\*/g, "$1")}</p>;
    });
  };

  return (
    <div className="flex flex-col h-[calc(100vh-220px)] min-h-[500px]" data-testid="rev-ai-copilot">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-stone-800">AI Revenue Copilot</h2>
            <p className="text-xs text-stone-400 flex items-center gap-1">
              Powered by GPT-5.2
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-emerald-600 font-medium">Online</span>
            </p>
          </div>
        </div>
        <button onClick={clear} className="flex items-center gap-1.5 text-stone-400 hover:text-red-500 text-xs px-3 py-1.5 border border-stone-200 rounded-lg hover:border-red-200 transition-all" data-testid="rev-copilot-clear">
          <Trash2 className="w-3.5 h-3.5" />Clear Chat
        </button>
      </div>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto bg-stone-50 rounded-2xl border border-stone-200 p-4 space-y-4">
        {messages.length === 0 && historyLoaded && (
          <div className="flex flex-col items-center justify-center h-full py-8">
            <div className="w-16 h-16 bg-gradient-to-br from-violet-500 to-indigo-500 rounded-2xl flex items-center justify-center mb-4 shadow-lg shadow-violet-200">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-lg font-bold text-stone-800 mb-1">Revenue Intelligence at Your Fingertips</h3>
            <p className="text-sm text-stone-400 mb-6 text-center max-w-md">Ask me anything about your hotel's revenue performance. I analyze your live data and provide actionable insights.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-lg">
              {QUICK_PROMPTS.map(q => (
                <button key={q.label} onClick={() => send(q.prompt)}
                  className="flex items-center gap-3 bg-white border border-stone-200 rounded-xl px-4 py-3 text-left hover:border-violet-300 hover:shadow-md transition-all group" data-testid={`rev-copilot-quick-${q.label.slice(0, 10)}`}>
                  <q.icon className="w-4 h-4 text-violet-400 group-hover:text-violet-600 flex-shrink-0" />
                  <span className="text-sm text-stone-700 font-medium">{q.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id || msg.created_at} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`} data-testid={`rev-copilot-msg-${msg.role}`}>
            {msg.role === "assistant" && (
              <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-white" />
              </div>
            )}
            <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-violet-600 text-white rounded-br-md"
                : "bg-white border border-stone-200 text-stone-700 rounded-bl-md shadow-sm"
            }`}>
              {msg.role === "user" ? msg.content : <div className="prose prose-sm max-w-none">{formatMessage(msg.content)}</div>}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 bg-stone-700 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                <User className="w-4 h-4 text-white" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-white border border-stone-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2 text-sm text-stone-400">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
                <span>Analyzing your hotel data...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={isRecording ? stopVoice : startVoice}
          className={`p-3 rounded-xl transition-all flex-shrink-0 ${isRecording ? "bg-red-500 hover:bg-red-600 text-white animate-pulse" : "bg-stone-100 hover:bg-stone-200 text-stone-500"}`}
          data-testid="rev-copilot-voice"
          title={isRecording ? "Stop recording" : "Voice input"}
        >
          {isRecording ? <Square className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
        </button>
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
            placeholder={isRecording ? "Listening..." : "Ask about your revenue, pricing, occupancy, competitors..."}
            className={`w-full bg-white border rounded-xl px-4 py-3 pr-12 text-sm focus:outline-none focus:ring-2 transition-all ${isRecording ? "border-red-300 focus:border-red-400 focus:ring-red-100" : "border-stone-200 focus:border-violet-400 focus:ring-violet-100"}`}
            disabled={loading}
            data-testid="rev-copilot-input"
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-violet-600 hover:bg-violet-700 text-white p-2 rounded-lg disabled:opacity-30 transition-all"
            data-testid="rev-copilot-send"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
      <p className="text-[10px] text-stone-300 text-center mt-2">AI Copilot analyzes your live hotel data. Recommendations should be reviewed before implementation.</p>
    </div>
  );
};
