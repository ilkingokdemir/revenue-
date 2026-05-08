/**
 * Multi-language Message Templates Panel
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Mail, Save, Trash2, Eye, RefreshCw } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LANGS = ["en", "tr", "de", "fr", "es", "it", "ar", "ru", "zh", "pt"];

export default function MsgTemplatesPanel({ propertyId, hotelName = "" }) {
  const [keys, setKeys] = useState([]);
  const [items, setItems] = useState([]);
  const [coverage, setCoverage] = useState({});
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ key: "", language: "en", subject: "", body: "", channel: "email", active: true });
  const [preview, setPreview] = useState(null);
  const [previewLang, setPreviewLang] = useState("en");

  const refresh = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const [{ data: k }, { data: t }] = await Promise.all([
        axios.get(`${API}/msg-templates/keys`),
        axios.get(`${API}/msg-templates/${propertyId}`),
      ]);
      setKeys(k.items || []);
      setItems(t.items || []);
      setCoverage(t.coverage || {});
      if (!form.key && k.items?.length) setForm((f) => ({ ...f, key: k.items[0].key }));
    } catch { toast.error("Load failed"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [propertyId]);

  const save = async () => {
    if (!form.key || !form.subject || !form.body) return toast.error("Key + subject + body required");
    try {
      await axios.post(`${API}/msg-templates`, { property_id: propertyId, ...form });
      toast.success("Template saved");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete template?")) return;
    try {
      await axios.delete(`${API}/msg-templates/${id}`);
      toast.success("Deleted");
      refresh();
    } catch { toast.error("Failed"); }
  };

  const renderPreview = async (key) => {
    try {
      const ctx = { guest_name: "Jane Doe", first_name: "Jane", checkin_date: "2026-05-12",
                     checkout_date: "2026-05-15", hotel_name: hotelName || "Your Hotel",
                     room_type: "Deluxe King", booking_ref: "abcd1234" };
      const { data } = await axios.post(`${API}/msg-templates/render`, { property_id: propertyId, key, language: previewLang, context: ctx });
      setPreview(data);
    } catch (e) { toast.error(e.response?.data?.detail || "Preview failed"); }
  };

  return (
    <div className="space-y-6" data-testid="msg-templates-panel">
      <div>
        <h2 className="text-2xl font-semibold text-stone-100">Message Templates · Multi-language</h2>
        <p className="text-sm text-stone-400 mt-1">{hotelName ? `${hotelName} · ` : ""}Central catalog. Other modules render via key + language with English fallback.</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2">
          <div className="text-xs uppercase tracking-wider text-stone-400">Edit / create template</div>
          <div className="grid grid-cols-3 gap-2">
            <select data-testid="mt-key-select" value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
              {keys.map((k) => <option key={k.key} value={k.key}>{k.key}</option>)}
            </select>
            <select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
              {LANGS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
            <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })} className="px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-xs">
              {["email", "sms", "whatsapp", "push"].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <input data-testid="mt-subject-input" placeholder="Subject" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="w-full px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <textarea data-testid="mt-body-input" rows={8} placeholder="Body" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="w-full px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-100 text-sm" />
          <div className="text-[10px] text-stone-500">Tags: {"{guest_name}"} {"{first_name}"} {"{checkin_date}"} {"{checkout_date}"} {"{hotel_name}"} {"{room_type}"} {"{booking_ref}"}</div>
          <button data-testid="mt-save-btn" onClick={save} className="w-full px-2 py-2 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-200 text-sm flex items-center justify-center gap-2"><Save className="w-3 h-3" /> Save template</button>
        </div>

        <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-hidden">
          <div className="px-4 py-2 border-b border-stone-800 text-xs uppercase tracking-wider text-stone-400 flex items-center justify-between">
            <span>Coverage matrix</span>
            <button onClick={refresh} className="text-stone-400 hover:text-stone-200">{loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}</button>
          </div>
          <table className="min-w-full text-xs">
            <thead className="text-left text-[10px] text-stone-500 border-b border-stone-800"><tr><th className="px-3 py-2">Key</th><th className="px-3 py-2">Languages</th><th className="px-3 py-2"></th></tr></thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.key} className="border-t border-stone-800/60" data-testid="mt-coverage-row">
                  <td className="px-3 py-1 text-stone-200 font-mono">{k.key}</td>
                  <td className="px-3 py-1">
                    <div className="flex flex-wrap gap-1">
                      {(coverage[k.key] || []).map((l) => <span key={l} className="text-[10px] px-1.5 py-0.5 rounded border bg-cyan-500/20 border-cyan-500/40 text-cyan-200">{l}</span>)}
                      {(coverage[k.key] || []).length === 0 && <span className="text-[10px] text-rose-300">missing</span>}
                    </div>
                  </td>
                  <td className="px-3 py-1 text-right">
                    <select value={previewLang} onChange={(e) => setPreviewLang(e.target.value)} className="text-[10px] px-1 py-0.5 rounded bg-stone-800 border border-stone-700 text-stone-300 mr-1">
                      {LANGS.map((l) => <option key={l} value={l}>{l}</option>)}
                    </select>
                    <button data-testid="mt-preview-btn" onClick={() => renderPreview(k.key)} className="text-xs px-2 py-1 rounded bg-stone-800 border border-stone-700 text-stone-300"><Eye className="w-3 h-3 inline" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {preview && (
        <div className="rounded-xl border border-stone-800 bg-stone-900/60 p-4 space-y-2" data-testid="mt-preview-box">
          <div className="text-xs uppercase tracking-wider text-stone-400">Preview · {preview.key} · requested {preview.language_requested} · used <b className="text-cyan-300">{preview.language_used}</b></div>
          <div className="text-stone-100 font-medium">{preview.subject}</div>
          <pre className="text-xs bg-stone-950 border border-stone-800 rounded p-3 overflow-x-auto whitespace-pre-wrap text-stone-200">{preview.body}</pre>
          <button onClick={() => setPreview(null)} className="text-xs text-stone-400 hover:text-stone-200">Close</button>
        </div>
      )}

      <div className="rounded-xl border border-stone-800 bg-stone-900/60 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-[10px] uppercase tracking-wider text-stone-500 border-b border-stone-800">
            <tr><th className="px-3 py-2">Key</th><th className="px-3 py-2">Lang</th><th className="px-3 py-2">Subject</th><th className="px-3 py-2">Channel</th><th className="px-3 py-2"></th></tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id} className="border-t border-stone-800/60 text-stone-200" data-testid="mt-template-row">
                <td className="px-3 py-2 font-mono text-xs">{t.key}</td>
                <td className="px-3 py-2 text-xs">{t.language}</td>
                <td className="px-3 py-2 text-xs truncate max-w-md">{t.subject}</td>
                <td className="px-3 py-2 text-xs">{t.channel}</td>
                <td className="px-3 py-2 text-right">
                  <button onClick={() => remove(t.id)} className="text-xs px-2 py-1 rounded bg-rose-500/20 border border-rose-500/40 text-rose-200"><Trash2 className="w-3 h-3" /></button>
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-center text-stone-500"><Mail className="w-5 h-5 mx-auto mb-1 opacity-60" />No templates yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
