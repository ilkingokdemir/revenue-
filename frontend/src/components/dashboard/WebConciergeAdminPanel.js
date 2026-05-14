/**
 * WebConciergeAdminPanel — admin UI to manage AI 24/7 Web Concierge:
 *  - Per-property widget config (welcome text, primary color, agent name, active)
 *  - Knowledge base (Q&A) CRUD
 *  - Live session monitoring
 *  - Embed code preview
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ChatCircleText, Plus, Trash, Copy, X } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function WebConciergeAdminPanel() {
  const [properties, setProperties] = useState([]);
  const [propertyId, setPropertyId] = useState("");
  const [tab, setTab] = useState("config");
  const [config, setConfig] = useState(null);
  const [kb, setKb] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [kbForm, setKbForm] = useState({ category: "general", question: "", answer: "" });

  useEffect(() => {
    axios.get(`${API}/properties`, { withCredentials: true })
         .then(r => {
           const list = r.data.properties || r.data.items || r.data || [];
           setProperties(list);
           if (list.length && !propertyId) setPropertyId(list[0].id);
         });
  }, [propertyId]);

  const reload = useCallback(async () => {
    if (!propertyId) return;
    try {
      const cfg = await axios.get(`${API}/web-concierge/widget-config/${propertyId}`);
      setConfig(cfg.data);
      const k = await axios.get(`${API}/web-concierge/knowledge/${propertyId}`, { withCredentials: true });
      setKb(k.data.items || []);
      const s = await axios.get(`${API}/web-concierge/sessions/${propertyId}`, { withCredentials: true });
      setSessions(s.data.items || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function saveConfig() {
    try {
      await axios.post(`${API}/web-concierge/config/${propertyId}`, config, { withCredentials: true });
      toast.success("Kaydedildi");
    } catch (e) { toast.error("Kaydedilemedi"); }
  }

  async function addKb() {
    if (!kbForm.question || !kbForm.answer) { toast.error("Soru ve cevap zorunlu"); return; }
    try {
      await axios.post(`${API}/web-concierge/knowledge/${propertyId}`, kbForm, { withCredentials: true });
      toast.success("Eklendi");
      setShowAdd(false); setKbForm({ category: "general", question: "", answer: "" });
      reload();
    } catch (e) { toast.error("Eklenemedi"); }
  }

  async function deleteKb(id) {
    if (!window.confirm("Silinsin mi?")) return;
    try {
      await axios.delete(`${API}/web-concierge/knowledge/${id}`, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Silinemedi"); }
  }

  async function loadSession(sid) {
    try {
      const r = await axios.get(`${API}/web-concierge/session/${sid}`, { withCredentials: true });
      setSelectedSession(r.data);
    } catch (e) { toast.error("Oturum yüklenemedi"); }
  }

  const embedCode = `<script src="${process.env.REACT_APP_BACKEND_URL}/widget.js" data-property="${propertyId}"></script>`;

  function copyEmbed() {
    navigator.clipboard.writeText(embedCode);
    toast.success("Embed kodu kopyalandı");
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="web-concierge-admin-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">AI Web Concierge</div>
          <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
            <ChatCircleText size={22} weight="fill" className="text-violet-600" /> Web 7/24 AI Concierge
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            Otel web sitenize embed edilen GPT-4o-mini destekli misafir asistanı (Eviivo parity)
          </p>
        </div>
        <select value={propertyId} onChange={e => setPropertyId(e.target.value)}
                data-testid="webc-property-select"
                className="px-3 py-1.5 text-sm border border-stone-300 rounded-lg bg-white">
          {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      <div className="flex gap-1 border-b border-stone-200 mb-4">
        {[{k:"config",label:"Yapılandırma"},{k:"kb",label:`Bilgi Tabanı (${kb.length})`},{k:"sessions",label:`Oturumlar (${sessions.length})`},{k:"embed",label:"Embed Kodu"}].map(t => (
          <button key={t.k} onClick={() => setTab(t.k)} data-testid={`webc-tab-${t.k}`}
                  className={`px-3 py-2 text-xs font-medium border-b-2 ${tab===t.k ? "border-violet-600 text-violet-700" : "border-transparent text-stone-500"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "config" && config && (
        <div className="bg-white border border-stone-200 rounded-xl p-5 space-y-3 max-w-2xl">
          <Inp label="Ajan Adı" v={config.agent_name} onChange={v => setConfig({...config, agent_name:v})} />
          <Inp label="Mülk Adı" v={config.property_name} onChange={v => setConfig({...config, property_name:v})} />
          <Inp label="Birincil Renk (hex)" v={config.primary_color} onChange={v => setConfig({...config, primary_color:v})} />
          <label className="block">
            <span className="text-xs text-stone-700">Karşılama Mesajı</span>
            <textarea value={config.welcome_message||""} rows={3}
                      onChange={e => setConfig({...config, welcome_message:e.target.value})}
                      data-testid="webc-welcome-input"
                      className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg mt-1" />
          </label>
          <label className="inline-flex items-center gap-2">
            <input type="checkbox" checked={config.is_active}
                   onChange={e => setConfig({...config, is_active:e.target.checked})}
                   data-testid="webc-active-toggle" />
            <span className="text-sm">Aktif</span>
          </label>
          <div>
            <button onClick={saveConfig} data-testid="webc-save-config"
                    className="text-sm px-4 py-2 bg-stone-900 text-white rounded-lg hover:bg-stone-800">
              Kaydet
            </button>
          </div>
        </div>
      )}

      {tab === "kb" && (
        <div>
          <div className="flex justify-end mb-3">
            <button onClick={() => setShowAdd(true)} data-testid="webc-add-kb-btn"
                    className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1.5">
              <Plus size={13} /> Yeni Q&A
            </button>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr>
                  <th className="px-4 py-2 text-left">Kategori</th>
                  <th className="px-4 py-2 text-left">Soru</th>
                  <th className="px-4 py-2 text-left">Yanıt</th>
                  <th className="px-4 py-2 text-right">İşlem</th>
                </tr>
              </thead>
              <tbody>
                {kb.map(k => (
                  <tr key={k.id} className="border-t border-stone-100" data-testid={`webc-kb-row-${k.id}`}>
                    <td className="px-4 py-2 text-xs"><span className="bg-stone-100 px-2 py-0.5 rounded">{k.category}</span></td>
                    <td className="px-4 py-2 font-medium">{k.question}</td>
                    <td className="px-4 py-2 text-xs text-stone-600 max-w-md">{k.answer}</td>
                    <td className="px-4 py-2 text-right">
                      <button onClick={() => deleteKb(k.id)} data-testid={`webc-kb-delete-${k.id}`}
                              className="text-xs p-1 text-rose-600 hover:bg-rose-50 rounded">
                        <Trash size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
                {kb.length === 0 && (
                  <tr><td colSpan={4} className="px-4 py-8 text-center text-stone-400 text-xs">Henüz bilgi yok. İlk sohbette varsayılan Q&A otomatik seed edilecek.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "sessions" && (
        <div className="grid lg:grid-cols-2 gap-4">
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold">Son Oturumlar</div>
            <div className="max-h-[500px] overflow-y-auto">
              {sessions.map(s => (
                <button key={s.session_id} onClick={() => loadSession(s.session_id)}
                        data-testid={`webc-session-${s.session_id}`}
                        className={`w-full text-left px-4 py-3 border-t border-stone-100 hover:bg-stone-50 ${selectedSession?.session_id===s.session_id ? "bg-violet-50":""}`}>
                  <div className="text-xs text-stone-500">{s.last_message_at?.slice(0,19)?.replace("T"," ")}</div>
                  <div className="text-sm font-medium truncate">{s.first_user_message || "(boş)"}</div>
                  <div className="text-[10px] text-stone-400 mt-0.5">{s.message_count} mesaj</div>
                </button>
              ))}
              {sessions.length === 0 && (
                <div className="px-4 py-8 text-center text-stone-400 text-xs">Henüz sohbet yok.</div>
              )}
            </div>
          </div>
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold">Sohbet Detayı</div>
            <div className="p-4 max-h-[500px] overflow-y-auto">
              {!selectedSession ? (
                <div className="text-center text-stone-400 text-xs py-8">Bir oturum seçin</div>
              ) : (
                (selectedSession.messages || []).map((m, i) => (
                  <div key={i} className={`mb-3 ${m.role==="user" ? "text-right" : ""}`}>
                    <div className={`inline-block px-3 py-2 rounded-lg max-w-[80%] text-sm ${
                      m.role==="user" ? "bg-violet-600 text-white" : "bg-stone-100 text-stone-900"}`}>
                      {m.content}
                    </div>
                    <div className="text-[10px] text-stone-400 mt-0.5">{m.ts?.slice(11,16)}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {tab === "embed" && (
        <div className="bg-white border border-stone-200 rounded-xl p-5 max-w-3xl">
          <div className="text-sm text-stone-600 mb-3">
            Aşağıdaki kodu otel web sitenizin <code className="bg-stone-100 px-1 rounded">&lt;body&gt;</code> kapanış etiketinden önce yapıştırın:
          </div>
          <div className="bg-stone-900 text-emerald-300 p-3 rounded-lg font-mono text-xs overflow-x-auto" data-testid="webc-embed-code">
            {embedCode}
          </div>
          <button onClick={copyEmbed} data-testid="webc-copy-embed"
                  className="mt-3 text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg inline-flex items-center gap-1.5">
            <Copy size={13} /> Kopyala
          </button>
          <div className="text-xs text-stone-500 mt-4 leading-relaxed">
            <strong>Test endpoint:</strong> <code>POST /api/web-concierge/chat</code> body <code>{`{property_id, session_id, message}`}</code><br/>
            Misafir mesajları GPT-4o-mini + bilgi tabanı ile yanıtlanır, oturumlar burada görüntülenir.
          </div>
        </div>
      )}

      {showAdd && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between p-4 border-b border-stone-200">
              <h3 className="text-base font-semibold">Yeni Q&A</h3>
              <button onClick={() => setShowAdd(false)} className="text-stone-400"><X size={18} /></button>
            </div>
            <div className="p-4 space-y-2">
              <Inp label="Kategori" v={kbForm.category} onChange={v => setKbForm({...kbForm, category:v})} />
              <Inp label="Soru" v={kbForm.question} onChange={v => setKbForm({...kbForm, question:v})} testId="webc-kb-q" />
              <label className="block">
                <span className="text-xs text-stone-700">Yanıt</span>
                <textarea value={kbForm.answer} rows={4} data-testid="webc-kb-a"
                          onChange={e => setKbForm({...kbForm, answer:e.target.value})}
                          className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg mt-1" />
              </label>
            </div>
            <div className="p-4 border-t border-stone-200 flex justify-end gap-2">
              <button onClick={() => setShowAdd(false)} className="text-xs px-3 py-1.5 border border-stone-300 rounded-lg">İptal</button>
              <button onClick={addKb} data-testid="webc-kb-save" className="text-xs px-3 py-1.5 bg-stone-900 text-white rounded-lg">Kaydet</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Inp({ label, v, onChange, testId }) {
  return (
    <label className="block">
      <span className="text-xs text-stone-700">{label}</span>
      <input value={v||""} onChange={e => onChange(e.target.value)} data-testid={testId}
             className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
    </label>
  );
}
