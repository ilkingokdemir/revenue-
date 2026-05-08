import React, { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Microphone,
  MicrophoneSlash,
  StopCircle,
  Headphones,
  ArrowsClockwise,
  ChartBar,
  ChatCircle,
  Lightning,
  WaveSquare,
  PaperPlaneTilt,
} from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

const INTENT_LABEL = {
  housekeeping: "Kat hizmetleri",
  room_service: "Oda servisi",
  front_desk: "Resepsiyon",
  faq: "SSS",
  maintenance: "Bakım",
  emergency: "Acil",
  concierge_chat: "Concierge",
  unknown: "—",
};

const INTENT_COLOR = {
  housekeeping: "bg-emerald-100 text-emerald-700",
  room_service: "bg-amber-100 text-amber-700",
  front_desk: "bg-sky-100 text-sky-700",
  faq: "bg-stone-100 text-stone-700",
  maintenance: "bg-violet-100 text-violet-700",
  emergency: "bg-red-100 text-red-700 ring-1 ring-red-300",
  concierge_chat: "bg-indigo-100 text-indigo-700",
};

export default function VoiceConciergePanel({ propertyId = "default", currentUser }) {
  const [tab, setTab] = useState("live");
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [stats, setStats] = useState(null);
  const [language, setLanguage] = useState("tr");
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [guestName, setGuestName] = useState("");
  const [roomNumber, setRoomNumber] = useState("");
  const sessionIdRef = useRef(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  const reload = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([
        axios.get(`${API}/api/voice/sessions/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/voice/stats/${propertyId}`, { withCredentials: true }),
      ]);
      setSessions(s.data.sessions || []);
      setStats(st.data);
    } catch (e) {
      // tolerate first-time empty
    }
  }, [propertyId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        await sendAudio(blob);
      };
      mediaRecorderRef.current = mr;
      mr.start();
      setRecording(true);
      setTranscript("");
      setReply(null);
    } catch (e) {
      toast.error("Mikrofon erişimi reddedildi");
    }
  };

  const stop = () => {
    try { mediaRecorderRef.current?.stop(); } catch {}
    setRecording(false);
  };

  const sendAudio = async (blob) => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("audio", blob, "voice.webm");
      fd.append("language", language);
      fd.append("property_id", propertyId);
      const r1 = await axios.post(`${API}/api/voice/transcribe`, fd, {
        withCredentials: true,
        headers: { "Content-Type": "multipart/form-data" },
      });
      const text = r1.data.text || "";
      setTranscript(text);
      if (!text.trim()) {
        toast.error("Ses çözümlenemedi — daha net konuşun");
        setBusy(false);
        return;
      }
      const r2 = await axios.post(
        `${API}/api/voice/concierge?property_id=${encodeURIComponent(propertyId)}`,
        {
          text,
          session_id: sessionIdRef.current,
          language: r1.data.language || language,
          guest_name: guestName || undefined,
          room_number: roomNumber || undefined,
        },
        { withCredentials: true }
      );
      sessionIdRef.current = r2.data.session_id;
      setReply(r2.data);
      reload();
      // Auto-play TTS for the AI reply (if user hasn't muted)
      if (autoSpeak && r2.data.reply) {
        await speakReply(r2.data.reply, r1.data.language || language);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Sesli concierge başarısız");
    } finally {
      setBusy(false);
    }
  };

  const speakReply = async (text, lang) => {
    try {
      const r = await axios.post(
        `${API}/api/voice/tts?property_id=${encodeURIComponent(propertyId)}`,
        { text, language: lang || language },
        { withCredentials: true, responseType: "blob" }
      );
      const url = URL.createObjectURL(new Blob([r.data], { type: "audio/mpeg" }));
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      audio.play().catch((err) => console.warn("audio play blocked:", err));
    } catch (e) {
      // Silent fail — TTS is a nice-to-have, don't block the flow
      console.warn("TTS failed:", e);
    }
  };

  const sendTypedText = async () => {
    if (!transcript.trim()) return toast.error("Önce konuş veya yaz");
    setBusy(true);
    try {
      const r = await axios.post(
        `${API}/api/voice/concierge?property_id=${encodeURIComponent(propertyId)}`,
        {
          text: transcript,
          session_id: sessionIdRef.current,
          language,
          guest_name: guestName || undefined,
          room_number: roomNumber || undefined,
        },
        { withCredentials: true }
      );
      sessionIdRef.current = r.data.session_id;
      setReply(r.data);
      reload();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Concierge başarısız");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="voice-concierge-panel">
      <div className="mb-5 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Headphones size={12} weight="fill" className="text-fuchsia-500" />
            <span>Guests · Voice Concierge (AI)</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Sesli Concierge</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Misafir mikrofona konuşur → Whisper deşifre eder → AI concierge cevaplar. Niyet
            (kat hizmetleri / oda servisi / acil) otomatik tespit edilir, ilgili göreve yönlendirilir.
          </p>
        </div>
        <button onClick={reload} className="px-3 py-2 bg-stone-100 text-stone-700 rounded-md text-sm hover:bg-stone-200 flex items-center gap-2" data-testid="voice-refresh">
          <ArrowsClockwise size={14} /> Yenile
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5" data-testid="voice-kpis">
        <Kpi label="Toplam oturum" value={stats?.total ?? 0} icon={ChatCircle} />
        <Kpi label="Kat hizmetleri" value={stats?.by_intent?.housekeeping ?? 0} icon={Lightning} tone="ok" />
        <Kpi label="Oda servisi" value={stats?.by_intent?.room_service ?? 0} icon={ChartBar} tone="warn" />
        <Kpi label="Acil" value={stats?.by_intent?.emergency ?? 0} icon={Lightning} tone={(stats?.by_intent?.emergency || 0) > 0 ? "bad" : "neutral"} />
      </div>

      <div className="flex border-b border-stone-200 mb-4">
        {[["live", "Canlı kayıt"], ["sessions", "Oturumlar"]].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`voice-tab-${k}`}
            className={`px-4 py-2 text-sm border-b-2 ${tab === k ? "border-indigo-600 text-indigo-700 font-medium" : "border-transparent text-stone-500 hover:text-stone-800"}`}>{l}</button>
        ))}
      </div>

      {tab === "live" && (
        <div className="bg-white border border-stone-200 rounded-lg p-5" data-testid="voice-live">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <Field label="Misafir adı (opsiyonel)" v={guestName} setV={setGuestName} testId="voice-guest" />
            <Field label="Oda no (opsiyonel)" v={roomNumber} setV={setRoomNumber} testId="voice-room" />
            <div>
              <label className="text-xs text-stone-500 mb-1 block">Dil</label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)} className="w-full text-sm border border-stone-200 rounded px-3 py-1.5" data-testid="voice-lang">
                <option value="tr">Türkçe</option>
                <option value="en">English</option>
                <option value="auto">Otomatik tespit</option>
              </select>
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs text-stone-600 mb-2 cursor-pointer" data-testid="voice-autospeak-toggle">
            <input type="checkbox" checked={autoSpeak} onChange={(e) => setAutoSpeak(e.target.checked)} />
            Cevabı otomatik seslendir (TTS)
          </label>

          <div className="text-center py-8">
            {!recording ? (
              <button onClick={start} disabled={busy} data-testid="voice-record-btn"
                className="w-32 h-32 rounded-full bg-gradient-to-br from-fuchsia-500 to-purple-600 text-white text-lg font-semibold flex flex-col items-center justify-center hover:scale-105 active:scale-95 transition-all shadow-lg disabled:opacity-50 mx-auto">
                <Microphone size={36} weight="fill" />
                <span className="text-xs mt-1">{busy ? "İşleniyor…" : "Konuşmaya başla"}</span>
              </button>
            ) : (
              <button onClick={stop} data-testid="voice-stop-btn"
                className="w-32 h-32 rounded-full bg-red-600 text-white text-lg font-semibold flex flex-col items-center justify-center hover:scale-105 active:scale-95 transition-all shadow-lg mx-auto animate-pulse">
                <StopCircle size={36} weight="fill" />
                <span className="text-xs mt-1">Durdur</span>
              </button>
            )}
            <p className="text-xs text-stone-400 mt-3">Mikrofon izni gerekir · 25MB altında</p>
          </div>

          {transcript && (
            <div className="mt-4 p-4 bg-stone-50 border border-stone-200 rounded-lg" data-testid="voice-transcript">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-stone-500 mb-2">
                <WaveSquare size={12} /> Deşifre edildi
              </div>
              <textarea
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                rows={2}
                className="w-full text-sm border border-stone-200 rounded px-3 py-2 bg-white"
                data-testid="voice-transcript-text"
              />
              <button onClick={sendTypedText} disabled={busy}
                className="mt-2 px-3 py-1.5 bg-indigo-600 text-white text-xs rounded hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1" data-testid="voice-send-text">
                <PaperPlaneTilt size={12} /> Düzenle ve tekrar gönder
              </button>
            </div>
          )}

          {reply && (
            <div className="mt-4 p-4 bg-fuchsia-50 border border-fuchsia-200 rounded-lg" data-testid="voice-reply">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-fuchsia-700">
                  <Headphones size={12} weight="fill" /> Concierge cevabı
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${INTENT_COLOR[reply.intent] || "bg-stone-100"}`} data-testid="voice-intent-pill">
                  {INTENT_LABEL[reply.intent] || reply.intent}
                </span>
              </div>
              <p className="text-sm text-stone-800 leading-relaxed">{reply.reply}</p>
              <button
                onClick={() => speakReply(reply.reply, language)}
                className="mt-2 px-3 py-1.5 bg-fuchsia-600 text-white text-xs rounded hover:bg-fuchsia-700 flex items-center gap-1"
                data-testid="voice-replay-btn"
              >
                <Headphones size={12} weight="fill" /> Tekrar dinle
              </button>
              {reply.action?.auto_create_task && (
                <p className="text-xs text-emerald-700 mt-2"><Lightning size={12} className="inline" weight="fill" /> Otomatik görev oluşturuldu → {reply.action.route_to}</p>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "sessions" && (
        <div className="bg-white border border-stone-200 rounded-lg p-3" data-testid="voice-sessions">
          {sessions.length === 0 && <p className="text-xs text-stone-400 italic p-3">Henüz oturum yok.</p>}
          {sessions.map((s) => (
            <div key={s.session_id} className="border-b border-stone-100 py-3">
              <div className="flex items-center justify-between mb-1">
                <div className="text-sm font-semibold text-stone-800">
                  {s.guest_name || "Anonim"} {s.room ? `· Oda ${s.room}` : ""}
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${INTENT_COLOR[s.intent] || "bg-stone-100"}`}>
                  {INTENT_LABEL[s.intent] || s.intent}
                </span>
              </div>
              {s.messages.slice(0, 3).map((m) => (
                <div key={m.id} className="text-xs text-stone-600 mb-1 pl-3 border-l-2 border-stone-200">
                  <span className="font-mono text-stone-400">[{(m.created_at || "").slice(11, 16)}]</span>{" "}
                  <span className="font-medium">misafir:</span> {m.input_text} <br />
                  <span className="font-mono text-stone-400">      </span>{" "}
                  <span className="font-medium text-fuchsia-700">AI:</span> {m.reply}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const Kpi = ({ label, value, icon: Icon, tone }) => (
  <div className={`bg-white border rounded-lg p-3 ${tone === "ok" ? "border-emerald-200" : tone === "bad" ? "border-red-200" : tone === "warn" ? "border-amber-200" : "border-stone-200"}`}>
    <div className="flex items-center justify-between text-stone-500 mb-1"><span className="text-[10px] uppercase tracking-wide">{label}</span>{Icon && <Icon size={14} />}</div>
    <div className="text-lg font-semibold text-stone-900">{value}</div>
  </div>
);

const Field = ({ label, v, setV, testId }) => (
  <div>
    <label className="text-xs text-stone-500 mb-1 block">{label}</label>
    <input value={v} onChange={(e) => setV(e.target.value)} className="w-full text-sm border border-stone-200 rounded px-3 py-1.5" data-testid={testId} />
  </div>
);
