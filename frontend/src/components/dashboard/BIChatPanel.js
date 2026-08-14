import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ChartBar, PaperPlaneTilt } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const SUGGESTIONS = [
  "Geçen hafta doluluk nasıldı, önceki haftaya göre değişim ne?",
  "Bu ay hangi kanal en çok gelir getirdi?",
  "Gelecek 7 gün doluluk görünümü nasıl?",
  "Robotun son katkısı ne kadar?",
];

export default function BIChatPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId] = useState(() => Math.random().toString(36).slice(2, 10));
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async (text) => {
    const q = (text || input).trim();
    if (!q || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/bi-chat/${pid}`, { question: q, session_id: sessionId }, { withCredentials: true });
      setMessages((m) => [...m, { role: "assistant", content: r.data.answer }]);
    } catch { toast.error("Yanıt alınamadı"); } finally { setBusy(false); }
  };

  return (
    <div className="p-5 max-w-[900px] mx-auto flex flex-col h-[calc(100vh-80px)]" data-testid="bi-chat-panel">
      <div className="mb-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <ChartBar size={13} weight="fill" className="text-sky-500" /><span>İş Zekası · Doğal Dil</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Veriye Sor</h1>
        <p className="text-sm text-stone-500 mt-1">Doluluk, gelir, kanal, pickup — otel verinize Türkçe soru sorun, sayılarla yanıt alın.</p>
      </div>

      <div className="flex-1 overflow-y-auto bg-white border border-stone-200 rounded-xl p-4 space-y-3" data-testid="bi-chat-messages">
        {messages.length === 0 && (
          <div className="space-y-2 py-6">
            <div className="text-xs text-stone-400 text-center mb-3">Örnek sorular:</div>
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)} data-testid="bi-chat-suggestion"
                className="block w-full text-left text-xs text-sky-800 bg-sky-50 border border-sky-100 rounded-lg px-3 py-2 hover:bg-sky-100">
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`max-w-[85%] text-sm rounded-xl px-3.5 py-2.5 whitespace-pre-wrap ${
            m.role === "user" ? "ml-auto bg-stone-900 text-white" : "bg-stone-100 text-stone-800"}`}
            data-testid={`bi-chat-msg-${m.role}`}>
            {m.content}
          </div>
        ))}
        {busy && <div className="text-xs text-stone-400 animate-pulse">Veriler analiz ediliyor…</div>}
        <div ref={endRef} />
      </div>

      <div className="flex gap-2 mt-3">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="ör. Geçen hafta RevPAR'ı ne sürükledi?" data-testid="bi-chat-input"
          className="flex-1 border border-stone-300 rounded-xl px-4 py-2.5 text-sm" />
        <button onClick={() => send()} disabled={busy || !input.trim()} data-testid="bi-chat-send"
          className="px-4 py-2.5 rounded-xl bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-50">
          <PaperPlaneTilt size={16} weight="fill" />
        </button>
      </div>
    </div>
  );
}
