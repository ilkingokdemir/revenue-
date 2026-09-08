import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const cfg = { withCredentials: true };
const SCOPES = ["read:availability", "read:bookings", "write:bookings", "read:guests"];

export default function PublicApiKeysCard({ pid }) {
  const [keys, setKeys] = useState([]);
  const [usage, setUsage] = useState(null);
  const [docs, setDocs] = useState(null);
  const [showDocs, setShowDocs] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [form, setForm] = useState({ name: "", scopes: SCOPES.slice(0, 3), rate_per_min: 120 });

  const load = useCallback(async () => {
    try {
      const [k, u] = await Promise.all([axios.get(`${API}/api/public-keys/${pid}`, cfg), axios.get(`${API}/api/public-keys/${pid}/usage`, cfg)]);
      setKeys(k.data.keys); setUsage(u.data);
    } catch { toast.error("API anahtarları yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (showDocs && !docs) axios.get(`${API}/api/public/v1/docs`).then((r) => setDocs(r.data)).catch(() => {}); }, [showDocs, docs]);

  const createKey = async () => {
    try {
      const r = await axios.post(`${API}/api/public-keys/${pid}`, form, cfg);
      setNewKey(r.data.key); toast.success("API anahtarı üretildi — bir kez gösterilir, kopyalayın!"); load();
    } catch { toast.error("Anahtar üretilemedi"); }
  };
  const toggleActive = async (k) => {
    try { await axios.put(`${API}/api/public-keys/${pid}/${k.id}`, { active: !k.active }, cfg); toast.success(k.active ? "Anahtar iptal edildi" : "Anahtar aktif"); load(); }
    catch { toast.error("Güncellenemedi"); }
  };
  const toggleScope = (s) => setForm((f) => ({ ...f, scopes: f.scopes.includes(s) ? f.scopes.filter((x) => x !== s) : [...f.scopes, s] }));

  return (
    <section className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="pa-keys">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-black text-stone-800">🔑 Public API v1 Anahtarları</h3>
        <button onClick={() => setShowDocs(!showDocs)} className="text-[11px] underline text-indigo-600" data-testid="pa-docs-toggle">{showDocs ? "Dokümanı gizle" : "Dokümantasyon & curl"}</button>
      </div>
      <div className="flex flex-wrap gap-2 items-end mb-2">
        <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Anahtar adı (örn. Channel Manager X)" className="border border-stone-300 rounded-lg px-2 py-1.5 text-xs w-52" data-testid="pa-key-name" />
        <label className="text-[10px] text-stone-500">İstek/dk<input type="number" min={10} max={5000} value={form.rate_per_min} onChange={(e) => setForm({ ...form, rate_per_min: Number(e.target.value) })} className="block border border-stone-300 rounded-lg px-2 py-1.5 text-xs w-20" data-testid="pa-key-rate" /></label>
        <div className="flex gap-1 flex-wrap">{SCOPES.map((s) => <button key={s} onClick={() => toggleScope(s)} className={`px-2 py-1 rounded-full text-[10px] font-bold border ${form.scopes.includes(s) ? "bg-stone-900 text-white border-stone-900" : "border-stone-300 text-stone-500"}`} data-testid={`pa-key-scope-${s.replace(":", "-")}`}>{s}</button>)}</div>
        <button onClick={createKey} data-testid="pa-key-create" className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-xs font-bold">+ Anahtar Üret</button>
      </div>
      {newKey && <div className="text-[11px] bg-amber-50 border border-amber-200 rounded-lg p-2 mb-2 break-all font-mono" data-testid="pa-key-new">{newKey}</div>}
      <div className="space-y-1">
        {keys.map((k) => (
          <div key={k.id} className={`flex flex-wrap items-center gap-2 text-[11px] rounded-lg px-2 py-1.5 ${k.active ? "bg-stone-50" : "bg-rose-50 opacity-70"}`} data-testid={`pa-key-row-${k.id}`}>
            <span className="font-bold text-stone-800">{k.name}</span>
            <span className="font-mono text-stone-500">{k.key}</span>
            <span className="text-stone-400">{k.scopes.join(" · ")}</span>
            <span className="text-stone-400">{k.rate_per_min}/dk</span>
            <span className="ml-auto text-stone-500">{k.calls || 0} çağrı{usage?.by_key?.[k.id] ? ` · 7g: ${usage.by_key[k.id]}` : ""}</span>
            <button onClick={() => toggleActive(k)} className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${k.active ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"}`} data-testid={`pa-key-toggle-${k.id}`}>{k.active ? "İptal et" : "Aktifleştir"}</button>
          </div>
        ))}
        {!keys.length && <div className="text-[11px] text-stone-400" data-testid="pa-keys-empty">Henüz anahtar yok.</div>}
      </div>
      {showDocs && docs && (
        <div className="mt-3 border-t border-stone-100 pt-3 space-y-2" data-testid="pa-docs">
          <p className="text-[11px] text-stone-600"><b>Kimlik:</b> {docs.auth}</p>
          <p className="text-[11px] text-stone-600"><b>Limit:</b> {docs.rate_limit}</p>
          <p className="text-[11px] text-stone-600"><b>Idempotency:</b> {docs.idempotency}</p>
          <table className="w-full text-[11px]"><tbody>
            {docs.endpoints.map((e) => (
              <tr key={e.method + e.path} className="border-t border-stone-100"><td className="py-1 font-mono font-bold text-stone-800 whitespace-nowrap">{e.method} {e.path}</td><td className="py-1 text-stone-500 px-2">{e.scope}</td><td className="py-1 text-stone-600">{e.desc}</td></tr>
            ))}
          </tbody></table>
          {docs.curl_examples.map((c) => (
            <div key={c.title}><div className="text-[10px] font-bold text-stone-500">{c.title}</div><pre className="text-[10px] bg-stone-900 text-emerald-200 rounded-lg p-2 overflow-x-auto whitespace-pre-wrap break-all" data-testid={`pa-docs-curl-${c.title}`}>{c.cmd}</pre></div>
          ))}
        </div>
      )}
    </section>
  );
}
