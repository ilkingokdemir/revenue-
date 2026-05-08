import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  WhatsappLogo,
  ArrowsClockwise,
  PaperPlaneTilt,
  CheckCircle,
  WarningCircle,
  Microphone,
  ChatCircle,
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

export default function WhatsAppVoicePanel({ propertyId = "default" }) {
  const [tab, setTab] = useState("setup");
  const [config, setConfig] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [testText, setTestText] = useState("Havlu istiyorum lütfen oda 204");
  const [testFrom, setTestFrom] = useState("whatsapp:+905555550000");

  const reload = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([
        axios.get(`${API}/api/whatsapp/config/${propertyId}`, { withCredentials: true }),
        axios.get(`${API}/api/whatsapp/sessions/${propertyId}`, { withCredentials: true }),
      ]);
      setConfig(c.data);
      setSessions(s.data.sessions || []);
    } catch (e) {
      console.error(e);
    }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function runTest() {
    if (!testText.trim()) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("text", testText);
      fd.append("From", testFrom);
      const res = await axios.post(
        `${API}/api/whatsapp/test/${propertyId}`,
        fd,
        { withCredentials: true }
      );
      const intent = res.data.intent;
      const sent = res.data.send_result?.status;
      toast.success(`Niyet: ${INTENT_LABEL[intent] || intent} · ${sent}`);
      reload();
    } catch (e) {
      toast.error(`Test başarısız: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6" data-testid="whatsapp-voice-panel">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <WhatsappLogo weight="fill" className="text-emerald-600" size={28} />
            WhatsApp Sesli Concierge
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            Misafirler WhatsApp'tan sesli not gönderir → Whisper ile yazıya çevrilir → AI yanıtlar →
            otomatik kat hizmetleri / bakım görevi açılır.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
              config?.creds_ready
                ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200"
                : "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
            }`}
            data-testid="whatsapp-creds-status"
          >
            {config?.creds_ready ? (
              <>
                <CheckCircle weight="fill" size={14} /> Twilio bağlı
              </>
            ) : (
              <>
                <WarningCircle weight="fill" size={14} /> Twilio anahtarları eksik
              </>
            )}
          </span>
          <button
            onClick={reload}
            className="text-xs px-3 py-1.5 rounded-md bg-stone-100 hover:bg-stone-200 inline-flex items-center gap-1"
            data-testid="whatsapp-reload-btn"
          >
            <ArrowsClockwise size={14} /> Yenile
          </button>
        </div>
      </header>

      <nav className="flex gap-1 border-b">
        {[
          ["setup", "Kurulum"],
          ["test", "Geliştirici testi"],
          ["sessions", `Konuşmalar (${sessions.length})`],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition ${
              tab === id
                ? "border-emerald-600 text-emerald-700"
                : "border-transparent text-stone-500 hover:text-stone-800"
            }`}
            data-testid={`wa-tab-${id}`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "setup" && (
        <section className="space-y-4">
          <div className="rounded-xl border bg-white p-5">
            <h2 className="font-semibold text-stone-800 mb-3">Twilio Sandbox kurulumu</h2>
            <ol className="space-y-2 text-sm text-stone-700 list-decimal list-inside">
              <li>Twilio Console → <span className="font-mono">Messaging → Try WhatsApp → Sandbox</span> sayfasını açın.</li>
              <li>"When a message comes in" alanına aşağıdaki webhook URL'sini yapıştırın (POST):</li>
              <li className="list-none ml-5">
                <code className="block text-[12px] bg-stone-50 border rounded p-2 break-all" data-testid="wa-webhook-url">
                  {config?.webhook_url || "—"}
                </code>
              </li>
              <li>
                Backend <span className="font-mono">.env</span> dosyasına şu anahtarları ekleyin:
                <pre className="mt-1 text-[12px] bg-stone-900 text-stone-100 rounded p-3 overflow-x-auto">
{`TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
PUBLIC_BASE_URL=${API}`}
                </pre>
              </li>
              <li>Backend'i yeniden başlatın: <code className="font-mono">sudo supervisorctl restart backend</code></li>
              <li>Telefonunuzdan Twilio sandbox numarasına <span className="font-mono">"join &lt;sandbox-code&gt;"</span> mesajı gönderin.</li>
              <li>Bir <strong>sesli not</strong> kaydedip gönderin — AI concierge 5 saniye içinde yanıt verecektir.</li>
            </ol>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <Stat label="Twilio'dan" value={config?.twilio_from || "—"} />
            <Stat label="Webhook" value={config?.creds_ready ? "Hazır" : "Beklemede"} />
            <Stat label="Toplam mesaj" value={sessions.reduce((a, b) => a + (b.messages?.length || 0), 0)} />
          </div>

          <div className="rounded-xl border bg-emerald-50/60 p-4 text-sm text-emerald-900">
            <p className="font-semibold mb-1">Akış</p>
            <p>
              Sesli not → <strong>Whisper STT</strong> → niyet sınıflandırma → <strong>GPT-4o-mini</strong> yanıt →
              <strong> OpenAI TTS</strong> sesli geri yanıt → kat hizmetleri/bakım için otomatik görev açar (gerekiyorsa).
            </p>
          </div>
        </section>
      )}

      {tab === "test" && (
        <section className="space-y-4">
          <div className="rounded-xl border bg-white p-5 space-y-3">
            <h2 className="font-semibold text-stone-800">Sahte gelen mesaj simülasyonu</h2>
            <p className="text-xs text-stone-500">
              Twilio bağlamak istemeden niyet sınıflandırıcıyı ve yanıt akışını test edin.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input
                value={testFrom}
                onChange={(e) => setTestFrom(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
                placeholder="whatsapp:+905..."
                data-testid="wa-test-from-input"
              />
              <input
                value={testText}
                onChange={(e) => setTestText(e.target.value)}
                className="border rounded px-3 py-2 text-sm md:col-span-2"
                placeholder="Mesaj metni..."
                data-testid="wa-test-text-input"
              />
            </div>
            <button
              onClick={runTest}
              disabled={busy || !testText.trim()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
              data-testid="wa-test-send-btn"
            >
              <PaperPlaneTilt size={16} /> {busy ? "Gönderiliyor…" : "Test Gönder"}
            </button>
          </div>
        </section>
      )}

      {tab === "sessions" && (
        <section className="space-y-3">
          {sessions.length === 0 && (
            <div className="text-center text-sm text-stone-500 py-12 border-2 border-dashed rounded-lg">
              Henüz konuşma yok. Twilio kurulumu tamamlanınca burada görünecek.
            </div>
          )}
          {sessions.map((s) => (
            <article
              key={s.phone}
              className="rounded-xl border bg-white p-4"
              data-testid={`wa-session-${s.phone}`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <h3 className="font-semibold flex items-center gap-2">
                    <ChatCircle size={16} className="text-emerald-600" />
                    {s.guest_name || s.phone}
                  </h3>
                  <p className="text-xs text-stone-500">{s.phone}</p>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  {s.voice_count > 0 && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">
                      <Microphone size={12} /> {s.voice_count} sesli
                    </span>
                  )}
                  <span className="text-stone-500">{s.messages.length} mesaj</span>
                </div>
              </div>
              <ul className="space-y-2">
                {s.messages.slice(0, 5).map((m) => (
                  <li key={m.id} className="text-xs border-l-2 pl-3 border-stone-200">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`px-2 py-0.5 rounded ${INTENT_COLOR[m.intent] || "bg-stone-100"}`}>
                        {INTENT_LABEL[m.intent] || m.intent || "—"}
                      </span>
                      <span className="text-stone-400">{new Date(m.created_at).toLocaleString("tr-TR")}</span>
                    </div>
                    <p className="text-stone-700"><strong>Misafir:</strong> {m.input_text}</p>
                    <p className="text-emerald-700 mt-0.5"><strong>Yanıt:</strong> {m.reply}</p>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-lg border bg-white p-3">
      <p className="text-[11px] uppercase tracking-wider text-stone-500 mb-1">{label}</p>
      <p className="font-semibold text-stone-800 break-words">{value}</p>
    </div>
  );
}
