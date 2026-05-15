/**
 * PMS Pro — Next-gen PMS module to leapfrog Mews/Cloudbeds/Pace/Apaleo.
 *
 * Tabs:
 *  1. Smart Assign       — AI önerisi en uygun oda numarası
 *  2. AI Concierge       — Doğal dil operasyon sorguları (Türkçe)
 *  3. Journey Rules      — Trigger → action otomasyon kuralları
 *  4. Anomaly Alerts     — VIP, no-show, bakım çakışmaları
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2, Sparkles, MessageSquare, Workflow, AlertTriangle,
  Send, Trash2, ToggleLeft, ToggleRight, Plus, RefreshCw, Bot,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PmsProPanel({ propertyId, hotelName = "" }) {
  const [tab, setTab] = useState("smart");
  const pid = propertyId || "default";

  const tabs = [
    { id: "smart",    label: "Smart Assign",    icon: Sparkles      },
    { id: "ai",       label: "AI Concierge",    icon: MessageSquare },
    { id: "journey",  label: "Journey Rules",   icon: Workflow      },
    { id: "anomaly",  label: "Anomaly Alerts",  icon: AlertTriangle },
  ];

  return (
    <div className="space-y-4" data-testid="pms-pro-panel">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Bot className="w-6 h-6 text-violet-600" />
            PMS Pro
            <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 ml-2">
              Next-gen operations
            </span>
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            {hotelName ? `${hotelName} · ` : ""}Akıllı oda atama, doğal-dil komuta, journey orchestration ve anomali alarmları.
          </p>
        </div>
      </header>

      <div className="flex gap-1 border-b border-stone-200 overflow-x-auto">
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-testid={`pms-pro-tab-${t.id}`}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px flex items-center gap-2 whitespace-nowrap transition ${
                active
                  ? "border-violet-600 text-violet-700"
                  : "border-transparent text-stone-500 hover:text-stone-700"
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      <div className="pt-2">
        {tab === "smart"   && <SmartAssignTab   pid={pid} />}
        {tab === "ai"      && <AiConciergeTab   pid={pid} />}
        {tab === "journey" && <JourneyRulesTab  pid={pid} />}
        {tab === "anomaly" && <AnomalyAlertsTab pid={pid} />}
      </div>
    </div>
  );
}

// ============== 1) SMART ASSIGN ==============
function SmartAssignTab({ pid }) {
  const [form, setForm] = useState({
    check_in: new Date(Date.now() + 86400000).toISOString().slice(0, 10),
    check_out: new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10),
    room_type: "",
    adults: 2,
    preferences: [],
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const togglePref = (p) => {
    setForm((f) => ({
      ...f,
      preferences: f.preferences.includes(p) ? f.preferences.filter((x) => x !== p) : [...f.preferences, p],
    }));
  };

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      const { data } = await axios.post(`${API}/pms-pro/smart-assign`, { property_id: pid, ...form });
      setResult(data);
      if (!data.ok) toast.warning(data.error || "Uygun oda bulunamadı");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Smart Assign failed");
    }
    setLoading(false);
  };

  const prefs = [
    { key: "high_floor", label: "Yüksek kat" },
    { key: "low_floor",  label: "Alçak kat"  },
    { key: "quiet",      label: "Sessiz"     },
    { key: "accessibility", label: "Engelli erişim" },
  ];

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div className="rounded-xl border border-stone-200 bg-white p-4 space-y-3">
        <h3 className="font-semibold text-stone-800">Atama kriterleri</h3>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-stone-600 col-span-1">
            Check-in
            <input type="date" value={form.check_in}
                   onChange={(e) => setForm({ ...form, check_in: e.target.value })}
                   className="mt-1 w-full px-3 py-2 border border-stone-200 rounded-lg text-sm"
                   data-testid="smart-assign-checkin" />
          </label>
          <label className="text-xs text-stone-600">
            Check-out
            <input type="date" value={form.check_out}
                   onChange={(e) => setForm({ ...form, check_out: e.target.value })}
                   className="mt-1 w-full px-3 py-2 border border-stone-200 rounded-lg text-sm"
                   data-testid="smart-assign-checkout" />
          </label>
          <label className="text-xs text-stone-600">
            Oda tipi
            <input type="text" placeholder="deluxe, suite..." value={form.room_type}
                   onChange={(e) => setForm({ ...form, room_type: e.target.value })}
                   className="mt-1 w-full px-3 py-2 border border-stone-200 rounded-lg text-sm"
                   data-testid="smart-assign-roomtype" />
          </label>
          <label className="text-xs text-stone-600">
            Yetişkin
            <input type="number" min="1" max="8" value={form.adults}
                   onChange={(e) => setForm({ ...form, adults: parseInt(e.target.value || "1", 10) })}
                   className="mt-1 w-full px-3 py-2 border border-stone-200 rounded-lg text-sm"
                   data-testid="smart-assign-adults" />
          </label>
        </div>
        <div>
          <div className="text-xs text-stone-600 mb-2">Misafir tercihleri</div>
          <div className="flex flex-wrap gap-2">
            {prefs.map((p) => (
              <button key={p.key} onClick={() => togglePref(p.key)}
                      data-testid={`smart-assign-pref-${p.key}`}
                      className={`px-3 py-1.5 rounded-full text-xs border transition ${
                        form.preferences.includes(p.key)
                          ? "bg-violet-600 text-white border-violet-600"
                          : "bg-white text-stone-600 border-stone-200 hover:border-stone-300"
                      }`}>
                {p.label}
              </button>
            ))}
          </div>
        </div>
        <button onClick={run} disabled={loading}
                data-testid="smart-assign-run-btn"
                className="w-full py-2.5 rounded-lg bg-violet-600 hover:bg-violet-700 text-white font-medium text-sm flex items-center justify-center gap-2 disabled:opacity-60">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          AI ile en uygun odayı bul
        </button>
      </div>

      <div className="rounded-xl border border-stone-200 bg-white p-4 min-h-[200px]">
        <h3 className="font-semibold text-stone-800 mb-3">Sonuç</h3>
        {!result && <p className="text-sm text-stone-400">Henüz çalıştırılmadı.</p>}
        {result && result.ok && (
          <div data-testid="smart-assign-result" className="space-y-3">
            <div className="rounded-lg bg-violet-50 border border-violet-200 p-3">
              <div className="text-xs uppercase text-violet-600 font-medium">En iyi seçim</div>
              <div className="text-xl font-bold text-violet-800">Oda {result.best_room}</div>
              <div className="text-xs text-violet-700">Skor: {result.best_score}</div>
              <ul className="mt-2 text-xs text-violet-800 list-disc pl-5 space-y-0.5">
                {result.best_reasons.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
            <div>
              <div className="text-xs font-medium text-stone-600 mb-1">Alternatifler</div>
              <ul className="space-y-1">
                {result.top_candidates.slice(1).map((c) => (
                  <li key={c.room_number} className="text-xs flex justify-between items-center px-3 py-1.5 rounded bg-stone-50">
                    <span>Oda <strong>{c.room_number}</strong> · Kat {c.floor}</span>
                    <span className="text-stone-500">skor {c.score}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        {result && !result.ok && <p className="text-sm text-amber-600">{result.error}</p>}
      </div>
    </div>
  );
}

// ============== 2) AI CONCIERGE ==============
function AiConciergeTab({ pid }) {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([]);

  const ask = async () => {
    if (!query.trim()) return;
    const q = query;
    setQuery("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/pms-pro/ai-concierge`, { query: q, property_id: pid });
      setMessages((m) => [...m, { role: "ai", text: data.summary, intent: data.intent, count: data.result_count, raw: data.raw }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "ai", text: "AI yanıt veremedi. Tekrar deneyin.", error: true }]);
    }
    setBusy(false);
  };

  const suggestions = [
    "Yarın gelen VIP'leri göster",
    "Bugün çıkış yapacak misafirler",
    "Açık bakım talepleri",
    "Housekeeping kuyruğu",
  ];

  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4 space-y-3">
      <div className="text-sm text-stone-600">
        Doğal dilde sorun. Sistem otomatik olarak kategori belirler, DB'yi sorgular ve Türkçe özet üretir.
      </div>

      <div className="flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button key={s} onClick={() => setQuery(s)}
                  data-testid={`ai-concierge-suggestion-${s.slice(0, 10)}`}
                  className="text-xs px-3 py-1 rounded-full bg-stone-100 hover:bg-stone-200 text-stone-700">
            {s}
          </button>
        ))}
      </div>

      <div className="min-h-[180px] max-h-[360px] overflow-y-auto rounded-lg bg-stone-50 p-3 space-y-2"
           data-testid="ai-concierge-messages">
        {messages.length === 0 && <p className="text-sm text-stone-400">Henüz sohbet yok.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`p-2.5 rounded-lg text-sm ${m.role === "user" ? "bg-violet-100 text-violet-900 ml-12" : "bg-white border border-stone-200 mr-12"}`}>
            <div className="text-[10px] uppercase tracking-wide text-stone-500 mb-0.5">
              {m.role === "user" ? "Sen" : `AI${m.intent ? ` · ${m.intent}` : ""}${typeof m.count === "number" ? ` · ${m.count} sonuç` : ""}`}
            </div>
            <div className="whitespace-pre-wrap">{m.text}</div>
          </div>
        ))}
        {busy && <div className="text-xs text-stone-500 flex items-center gap-2"><Loader2 className="w-3 h-3 animate-spin" /> AI düşünüyor...</div>}
      </div>

      <div className="flex gap-2">
        <input value={query} onChange={(e) => setQuery(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && !busy && ask()}
               placeholder="Örn: Yarın gelen 2 yetişkinli VIP rezervasyonlar"
               data-testid="ai-concierge-input"
               className="flex-1 px-3 py-2 border border-stone-200 rounded-lg text-sm" />
        <button onClick={ask} disabled={busy || !query.trim()}
                data-testid="ai-concierge-send"
                className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium flex items-center gap-2 disabled:opacity-60">
          <Send className="w-4 h-4" /> Sor
        </button>
      </div>
    </div>
  );
}

// ============== 3) JOURNEY RULES ==============
const TRIGGERS = [
  "booking_confirmed", "pre_arrival_24h", "pre_arrival_1h", "checked_in",
  "mid_stay", "pre_checkout_2h", "checked_out", "no_show", "late_checkout_requested",
];
const ACTIONS = [
  "send_email", "send_sms", "send_app_push", "create_task",
  "send_qr_key", "offer_upsell", "trigger_housekeeping", "notify_manager",
];

function JourneyRulesTab({ pid }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", trigger: "pre_arrival_24h", action: "send_email", template: "", priority: 100 });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/pms-pro/journey-rules`, { params: { property_id: pid } });
      setRules(data.items || []);
    } catch { toast.error("Kurallar yüklenemedi"); }
    setLoading(false);
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!form.name.trim()) { toast.warning("İsim gerekli"); return; }
    try {
      await axios.post(`${API}/pms-pro/journey-rules`, { property_id: pid, ...form });
      toast.success("Kural oluşturuldu");
      setShowForm(false);
      setForm({ name: "", trigger: "pre_arrival_24h", action: "send_email", template: "", priority: 100 });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Hata"); }
  };

  const toggle = async (id) => {
    try { await axios.patch(`${API}/pms-pro/journey-rules/${id}/toggle`); load(); }
    catch { toast.error("Toggle failed"); }
  };

  const del = async (id) => {
    if (!window.confirm("Bu kuralı silmek istediğine emin misin?")) return;
    try { await axios.delete(`${API}/pms-pro/journey-rules/${id}`); toast.success("Silindi"); load(); }
    catch { toast.error("Silinemedi"); }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-stone-600">Tetikleyici → aksiyon. Misafir yolculuğunun her adımı için otomasyon.</p>
        <div className="flex gap-2">
          <button onClick={load} data-testid="journey-rules-refresh"
                  className="px-3 py-1.5 text-xs rounded-lg border border-stone-200 hover:bg-stone-50 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Yenile
          </button>
          <button onClick={() => setShowForm((v) => !v)} data-testid="journey-rules-add-btn"
                  className="px-3 py-1.5 text-xs rounded-lg bg-violet-600 hover:bg-violet-700 text-white flex items-center gap-1">
            <Plus className="w-3 h-3" /> Yeni kural
          </button>
        </div>
      </div>

      {showForm && (
        <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-4 space-y-2" data-testid="journey-rules-form">
          <div className="grid md:grid-cols-2 gap-2">
            <input value={form.name} placeholder="Kural adı"
                   onChange={(e) => setForm({ ...form, name: e.target.value })}
                   data-testid="journey-rule-name"
                   className="px-3 py-2 border border-stone-200 rounded text-sm" />
            <input type="number" value={form.priority}
                   onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value || "100", 10) })}
                   placeholder="Öncelik (düşük → öncelikli)"
                   className="px-3 py-2 border border-stone-200 rounded text-sm" />
            <select value={form.trigger} onChange={(e) => setForm({ ...form, trigger: e.target.value })}
                    data-testid="journey-rule-trigger"
                    className="px-3 py-2 border border-stone-200 rounded text-sm">
              {TRIGGERS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}
                    data-testid="journey-rule-action"
                    className="px-3 py-2 border border-stone-200 rounded text-sm">
              {ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <textarea value={form.template} onChange={(e) => setForm({ ...form, template: e.target.value })}
                    placeholder="Şablon / mesaj içeriği..." rows={2}
                    className="w-full px-3 py-2 border border-stone-200 rounded text-sm" />
          <div className="flex justify-end gap-2">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-xs rounded border border-stone-200">İptal</button>
            <button onClick={create} data-testid="journey-rule-save"
                    className="px-3 py-1.5 text-xs rounded bg-violet-600 text-white">Kaydet</button>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-stone-200 bg-white overflow-hidden">
        {loading && <div className="p-4 text-sm text-stone-400 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Yükleniyor...</div>}
        {!loading && rules.length === 0 && (
          <div className="p-6 text-sm text-stone-400 text-center" data-testid="journey-rules-empty">
            Henüz kural yok. Bir tane oluştur ve guest journey'yi otomatikleştir.
          </div>
        )}
        {!loading && rules.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-stone-50 text-xs uppercase text-stone-500">
              <tr>
                <th className="text-left px-3 py-2">Kural</th>
                <th className="text-left px-3 py-2">Trigger</th>
                <th className="text-left px-3 py-2">Action</th>
                <th className="text-center px-3 py-2">Önc.</th>
                <th className="text-center px-3 py-2">Durum</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-t border-stone-100" data-testid={`journey-rule-row-${r.id}`}>
                  <td className="px-3 py-2 font-medium text-stone-800">{r.name}</td>
                  <td className="px-3 py-2 text-stone-600">{r.trigger}</td>
                  <td className="px-3 py-2 text-stone-600">{r.action}</td>
                  <td className="px-3 py-2 text-center">{r.priority}</td>
                  <td className="px-3 py-2 text-center">
                    <button onClick={() => toggle(r.id)} data-testid={`journey-rule-toggle-${r.id}`}>
                      {r.enabled
                        ? <ToggleRight className="w-5 h-5 text-emerald-600 inline" />
                        : <ToggleLeft  className="w-5 h-5 text-stone-400 inline" />}
                    </button>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={() => del(r.id)} data-testid={`journey-rule-delete-${r.id}`}
                            className="text-stone-400 hover:text-red-600">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ============== 4) ANOMALY ALERTS ==============
function AnomalyAlertsTab({ pid }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/pms-pro/anomalies/${pid}`);
      setData(r.data);
    } catch { toast.error("Anomali yüklenemedi"); }
    setLoading(false);
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const levelStyle = {
    critical: "bg-red-50 border-red-200 text-red-800",
    warning:  "bg-amber-50 border-amber-200 text-amber-800",
    info:     "bg-sky-50 border-sky-200 text-sky-800",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-stone-600">
          {data && (
            <>
              {data.alert_count} aktif alarm
              {data.critical_count > 0 && <span className="ml-2 text-red-600 font-semibold">· {data.critical_count} kritik</span>}
              {data.checked_at && <span className="ml-2 text-stone-400">· {new Date(data.checked_at).toLocaleTimeString("tr-TR")}</span>}
            </>
          )}
        </div>
        <button onClick={load} data-testid="anomaly-refresh"
                className="px-3 py-1.5 text-xs rounded-lg border border-stone-200 hover:bg-stone-50 flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> Yenile
        </button>
      </div>

      {loading && <div className="p-4 text-sm text-stone-400 flex items-center gap-2"><Loader2 className="w-4 h-4 animate-spin" /> Tarama...</div>}

      {!loading && data && data.alerts.length === 0 && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-center text-emerald-700" data-testid="anomaly-empty">
          ✓ Şu an aktif anomali yok. Operasyon temiz.
        </div>
      )}

      <div className="space-y-2" data-testid="anomaly-list">
        {data && data.alerts.map((a, i) => (
          <div key={i} className={`rounded-lg border p-3 ${levelStyle[a.level] || levelStyle.info}`}
               data-testid={`anomaly-card-${a.category}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="font-semibold">{a.title}</div>
                <div className="text-xs mt-1 opacity-80">{a.action}</div>
                {a.samples && a.samples.length > 0 && (
                  <div className="text-xs mt-2 opacity-70">Örnek: {a.samples.join(", ")}</div>
                )}
              </div>
              <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-white/60 border border-current/20">
                {a.level}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
