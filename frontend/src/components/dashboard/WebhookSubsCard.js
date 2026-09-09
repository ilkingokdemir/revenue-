import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const cfg = { withCredentials: true };
const ST = { delivered: ["Teslim", "bg-emerald-100 text-emerald-700"], retrying: ["Yeniden deneniyor", "bg-amber-100 text-amber-800"], failed: ["Başarısız", "bg-rose-100 text-rose-700"] };

export default function WebhookSubsCard({ pid }) {
  const [data, setData] = useState({ subscriptions: [], recent_deliveries: [], counts: {}, events: [] });
  const [url, setUrl] = useState("");
  const [newSecret, setNewSecret] = useState("");
  const [showSig, setShowSig] = useState(false);
  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/api/webhook-subs/${pid}`, cfg); setData(r.data); } catch { toast.error("Webhook'lar yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    try { const r = await axios.post(`${API}/api/webhook-subs/${pid}`, { url, events: ["*"] }, cfg); setNewSecret(r.data.secret); setUrl(""); toast.success("Abonelik eklendi — secret bir kez gösterilir"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Eklenemedi"); }
  };
  const toggle = async (s) => { try { await axios.put(`${API}/api/webhook-subs/${pid}/${s.id}`, { active: !s.active }, cfg); load(); } catch { toast.error("Güncellenemedi"); } };
  const remove = async (s) => { if (!window.confirm("Abonelik silinsin mi?")) return; try { await axios.delete(`${API}/api/webhook-subs/${pid}/${s.id}`, cfg); load(); } catch { toast.error("Silinemedi"); } };
  const rotate = async (s) => {
    if (!window.confirm("Secret yenilensin mi? Partnerin eski secret'ı geçersiz olur.")) return;
    try { const r = await axios.post(`${API}/api/webhook-subs/${pid}/${s.id}/rotate-secret`, {}, cfg); setNewSecret(r.data.secret); toast.success("Secret yenilendi — bir kez gösterilir"); load(); }
    catch { toast.error("Yenilenemedi"); }
  };
  const test = async () => { try { const r = await axios.post(`${API}/api/webhook-subs/${pid}/test`, {}, cfg); toast.success(`Test gönderildi: ${r.data.sent} başarılı`); load(); } catch { toast.error("Test başarısız"); } };
  const retry = async (d) => { try { const r = await axios.post(`${API}/api/webhook-subs/${pid}/deliveries/${d.id}/retry`, {}, cfg); toast[r.data.ok ? "success" : "error"](r.data.ok ? "Teslim edildi" : `Yine başarısız: ${r.data.last_error}`); load(); } catch { toast.error("Yeniden denenemedi"); } };

  const c = data.counts || {};
  return (
    <section className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="pa-webhooks">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-black text-stone-800">🔔 Giden Webhook'lar</h3>
        <div className="flex gap-2 text-[10px] font-bold" data-testid="pa-webhook-counts">
          <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">{c.delivered || 0} teslim</span>
          <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">{c.retrying || 0} kuyrukta</span>
          <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700">{c.failed || 0} başarısız</span>
        </div>
      </div>
      <p className="text-[11px] text-stone-500 mb-2">Başarısız teslimatlar otomatik yeniden denenir: 1 dk → 5 dk → 30 dk → 2 sa → 12 sa (6 deneme). Her istek <b>HMAC-SHA256</b> ile imzalanır (<code>X-Webhook-Signature</code>). <button onClick={() => setShowSig(!showSig)} className="underline text-indigo-600" data-testid="pa-webhook-sig-toggle">{showSig ? "Doğrulama örneğini gizle" : "Doğrulama örneği"}</button></p>
      {showSig && (
        <div className="text-[10px] bg-stone-900 text-emerald-200 rounded-lg p-2 mb-2 whitespace-pre-wrap font-mono" data-testid="pa-webhook-sig-doc">{`Başlıklar: X-Webhook-Timestamp (unix sn), X-Webhook-Signature: v1=<hex>, X-Webhook-Event, X-Webhook-Delivery
İmzalanan metin: "<timestamp>.<ham gövde>"   (JSON'u yeniden serileştirmeyin; 5 dk'dan eski zaman damgasını reddedin)

# Python
expected = "v1=" + hmac.new(SECRET.encode(), f"{ts}.".encode() + raw_body, hashlib.sha256).hexdigest()
ok = hmac.compare_digest(expected, request.headers["X-Webhook-Signature"])

// Node
const expected = "v1=" + crypto.createHmac("sha256", SECRET).update(\`\${ts}.\`).update(rawBody).digest("hex");`}</div>
      )}
      <div className="flex gap-2 mb-2">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://partner.example.com/webhooks" className="flex-1 border border-stone-300 rounded-lg px-2 py-1.5 text-xs" data-testid="pa-webhook-url" />
        <button onClick={add} disabled={!url.startsWith("http")} className="px-3 py-1.5 rounded-lg bg-stone-900 text-white text-xs font-bold disabled:opacity-40" data-testid="pa-webhook-add">+ Ekle</button>
        <button onClick={test} disabled={!data.subscriptions.length} className="px-3 py-1.5 rounded-lg border border-stone-300 text-xs font-bold disabled:opacity-40" data-testid="pa-webhook-test">Test gönder</button>
      </div>
      {newSecret && <div className="text-[11px] bg-amber-50 border border-amber-200 rounded-lg p-2 mb-2 font-mono break-all" data-testid="pa-webhook-secret">X-Webhook-Secret: {newSecret}</div>}
      <div className="space-y-1 mb-3">
        {data.subscriptions.map((s) => (
          <div key={s.id} className={`flex items-center gap-2 text-[11px] rounded-lg px-2 py-1.5 ${s.active === false ? "bg-rose-50 opacity-70" : "bg-stone-50"}`} data-testid={`pa-webhook-sub-${s.id}`}>
            <span className="font-mono text-stone-700 truncate flex-1">{s.url}</span>
            <span className="text-stone-400">{(s.events || []).join(", ")}</span>
            <button onClick={() => rotate(s)} className="px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-700 text-[10px] font-bold" data-testid={`pa-webhook-rotate-${s.id}`}>Secret yenile</button>
            <button onClick={() => toggle(s)} className="px-2 py-0.5 rounded-md bg-stone-200 text-[10px] font-bold" data-testid={`pa-webhook-toggle-${s.id}`}>{s.active === false ? "Aç" : "Duraklat"}</button>
            <button onClick={() => remove(s)} className="px-2 py-0.5 rounded-md bg-rose-100 text-rose-700 text-[10px] font-bold" data-testid={`pa-webhook-del-${s.id}`}>Sil</button>
          </div>
        ))}
        {!data.subscriptions.length && <div className="text-[11px] text-stone-400" data-testid="pa-webhook-empty">Henüz abonelik yok.</div>}
      </div>
      {data.recent_deliveries.length > 0 && (
        <table className="w-full text-[11px]" data-testid="pa-webhook-deliveries"><thead><tr className="text-left text-stone-400"><th className="py-1">Zaman</th><th>Olay</th><th>Durum</th><th>Deneme</th><th>Hata / sonraki</th><th></th></tr></thead><tbody>
          {data.recent_deliveries.map((d) => { const [lbl, cls] = ST[d.status] || [d.ok ? "Teslim" : "Başarısız", d.ok ? ST.delivered[1] : ST.failed[1]]; return (
            <tr key={d.id} className="border-t border-stone-100" data-testid={`pa-webhook-delivery-${d.id}`}>
              <td className="py-1 text-stone-500">{String(d.at).slice(5, 16).replace("T", " ")}</td>
              <td className="font-mono">{d.event}</td>
              <td><span className={`px-1.5 py-0.5 rounded-full font-bold ${cls}`} data-testid={`pa-webhook-status-${d.id}`}>{lbl}</span></td>
              <td>{d.attempts || 1}</td>
              <td className="text-stone-500 truncate max-w-[220px]">{d.status === "retrying" && d.next_retry_at ? `→ ${String(d.next_retry_at).slice(11, 16)} UTC · ` : ""}{d.last_error || (d.status_code ? `HTTP ${d.status_code}` : "")}</td>
              <td className="text-right">{d.status !== "delivered" && <button onClick={() => retry(d)} className="text-[10px] underline text-indigo-600" data-testid={`pa-webhook-retry-${d.id}`}>Şimdi dene</button>}</td>
            </tr>); })}
        </tbody></table>
      )}
    </section>
  );
}
