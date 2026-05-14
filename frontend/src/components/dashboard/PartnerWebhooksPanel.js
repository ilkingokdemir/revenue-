import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Plug, Key, Plus, X, Copy, Trash, PaperPlaneTilt } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/partner`;

export default function PartnerWebhooksPanel() {
  const [tab, setTab] = useState("webhooks");
  const [subs, setSubs] = useState([]);
  const [eventsCatalog, setEventsCatalog] = useState([]);
  const [keys, setKeys] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showWh, setShowWh] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [newSecret, setNewSecret] = useState(null);
  const [form, setForm] = useState({ events: [] });

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [w, k, d] = await Promise.all([
        axios.get(`${API}/webhooks`, { withCredentials: true }),
        axios.get(`${API}/api-keys`, { withCredentials: true }),
        axios.get(`${API}/webhooks/deliveries?limit=50`, { withCredentials: true }),
      ]);
      setSubs(w.data.subscriptions || []);
      setEventsCatalog(w.data.events_catalog || []);
      setKeys(k.data.api_keys || []);
      setDeliveries(d.data.deliveries || []);
    } catch (e) { toast.error("Yüklenemedi"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  async function createWebhook() {
    try {
      const r = await axios.post(`${API}/webhooks`, {
        name: form.name, url: form.url, events: form.events,
      }, { withCredentials: true });
      setNewSecret({ kind: "webhook", value: r.data.secret });
      setShowWh(false); setForm({ events: [] });
      reload();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); }
  }

  async function createKey() {
    try {
      const r = await axios.post(`${API}/api-keys`, {
        name: form.name, scopes: form.scopes ? form.scopes.split(",").map(s => s.trim()) : ["read"],
      }, { withCredentials: true });
      setNewSecret({ kind: "apikey", value: r.data.secret });
      setShowKey(false); setForm({ events: [] });
      reload();
    } catch (e) { toast.error("Eklenemedi"); }
  }

  async function testPing(id) {
    try {
      await axios.post(`${API}/webhooks/${id}/test`, {}, { withCredentials: true });
      toast.success("Test pingi gönderildi");
      reload();
    } catch (e) { toast.error("Gönderilemedi"); }
  }

  async function deleteSub(id) {
    if (!window.confirm("Webhook silinsin mi?")) return;
    try {
      await axios.delete(`${API}/webhooks/${id}`, { withCredentials: true });
      reload();
    } catch (e) { toast.error("Silinemedi"); }
  }

  async function revoke(id) {
    if (!window.confirm("API anahtarı iptal edilsin mi?")) return;
    try {
      await axios.delete(`${API}/api-keys/${id}`, { withCredentials: true });
      reload();
    } catch (e) { toast.error("İptal edilemedi"); }
  }

  function toggleEvent(ev) {
    setForm(f => ({
      ...f,
      events: f.events?.includes(ev) ? f.events.filter(e => e !== ev) : [...(f.events || []), ev],
    }));
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="partner-webhooks-panel">
      <div className="mb-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
          <Plug size={12} weight="fill" className="text-indigo-500" />
          <span>Partner Platform</span>
        </div>
        <h1 className="text-2xl font-semibold text-stone-900">Webhook'lar & API Anahtarları</h1>
        <p className="text-sm text-stone-500 mt-1 max-w-2xl">
          Üçüncü taraf entegrasyonları için real-time event bildirimleri ve API erişim anahtarları.
        </p>
      </div>

      <div className="flex gap-1 mb-4 border-b border-stone-200">
        <button onClick={() => setTab("webhooks")} data-testid="pw-tab-webhooks"
                className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === "webhooks" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
          Webhooks ({subs.length})
        </button>
        <button onClick={() => setTab("keys")} data-testid="pw-tab-keys"
                className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === "keys" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
          API Keys ({keys.length})
        </button>
        <button onClick={() => setTab("deliveries")} data-testid="pw-tab-deliveries"
                className={`px-4 py-2 text-xs font-medium border-b-2 ${tab === "deliveries" ? "border-stone-900 text-stone-900" : "border-transparent text-stone-500"}`}>
          Teslimat Logları
        </button>
        {tab === "webhooks" && (
          <button onClick={() => setShowWh(true)} className="ml-auto px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5 mb-1" data-testid="pw-new-webhook">
            <Plus size={13} /> Webhook Ekle
          </button>
        )}
        {tab === "keys" && (
          <button onClick={() => setShowKey(true)} className="ml-auto px-3 py-1.5 text-xs text-white bg-stone-900 rounded-lg inline-flex items-center gap-1.5 mb-1" data-testid="pw-new-key">
            <Plus size={13} /> Key Oluştur
          </button>
        )}
      </div>

      {loading && <div className="text-center py-12 text-stone-400 text-sm">Yükleniyor…</div>}

      {!loading && tab === "webhooks" && (
        subs.length === 0 ? (
          <div className="text-center py-12 text-stone-400 text-sm" data-testid="pw-empty-webhooks">Henüz webhook yok.</div>
        ) : (
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr><th className="px-4 py-2 text-left">Ad</th><th className="px-4 py-2 text-left">URL</th><th className="px-4 py-2 text-left">Eventler</th><th className="px-4 py-2 text-right">Başarı/Hata</th><th className="px-4 py-2"></th></tr>
              </thead>
              <tbody>
                {subs.map(s => (
                  <tr key={s.id} className="border-t border-stone-100" data-testid={`pw-wh-${s.id}`}>
                    <td className="px-4 py-2 font-medium">{s.name || "—"}</td>
                    <td className="px-4 py-2 text-xs font-mono">{s.url}</td>
                    <td className="px-4 py-2 text-xs">{(s.events || []).join(", ")}</td>
                    <td className="px-4 py-2 text-right text-xs">{s.success_count || 0} / {s.failure_count || 0}</td>
                    <td className="px-4 py-2 text-right">
                      <button onClick={() => testPing(s.id)} className="text-indigo-600 hover:text-indigo-800 mr-2" title="Test ping" data-testid={`pw-test-${s.id}`}>
                        <PaperPlaneTilt size={14} />
                      </button>
                      <button onClick={() => deleteSub(s.id)} className="text-stone-400 hover:text-rose-500" data-testid={`pw-del-${s.id}`}>
                        <Trash size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {!loading && tab === "keys" && (
        keys.length === 0 ? (
          <div className="text-center py-12 text-stone-400 text-sm" data-testid="pw-empty-keys">Henüz API key yok.</div>
        ) : (
          <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr><th className="px-4 py-2 text-left">Ad</th><th className="px-4 py-2 text-left">Prefix</th><th className="px-4 py-2 text-left">Scopes</th><th className="px-4 py-2 text-left">Oluşturuldu</th><th className="px-4 py-2"></th></tr>
              </thead>
              <tbody>
                {keys.map(k => (
                  <tr key={k.id} className="border-t border-stone-100" data-testid={`pw-key-${k.id}`}>
                    <td className="px-4 py-2 font-medium">{k.name}</td>
                    <td className="px-4 py-2 text-xs font-mono">{k.prefix}</td>
                    <td className="px-4 py-2 text-xs">{(k.scopes || []).join(", ")}</td>
                    <td className="px-4 py-2 text-xs">{new Date(k.created_at).toLocaleDateString("tr-TR")}</td>
                    <td className="px-4 py-2 text-right">
                      <button onClick={() => revoke(k.id)} className="text-stone-400 hover:text-rose-500" data-testid={`pw-revoke-${k.id}`}>
                        <Trash size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {!loading && tab === "deliveries" && (
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          {deliveries.length === 0 ? (
            <div className="text-center py-12 text-stone-400 text-sm" data-testid="pw-empty-deliveries">Henüz teslimat yok.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-stone-50 text-[11px] uppercase tracking-wider text-stone-500">
                <tr><th className="px-4 py-2 text-left">Zaman</th><th className="px-4 py-2 text-left">Event</th><th className="px-4 py-2 text-left">URL</th><th className="px-4 py-2 text-right">Status</th><th className="px-4 py-2 text-right">Süre</th></tr>
              </thead>
              <tbody>
                {deliveries.map(d => (
                  <tr key={d.id} className="border-t border-stone-100" data-testid={`pw-delivery-${d.id}`}>
                    <td className="px-4 py-2 text-xs">{new Date(d.created_at).toLocaleString("tr-TR")}</td>
                    <td className="px-4 py-2 text-xs font-medium">{d.event}</td>
                    <td className="px-4 py-2 text-xs font-mono truncate max-w-xs">{d.url}</td>
                    <td className={`px-4 py-2 text-right font-medium ${d.ok ? "text-emerald-600" : "text-rose-600"}`}>{d.status_code}</td>
                    <td className="px-4 py-2 text-right text-xs">{d.duration_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {showWh && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowWh(false)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="pw-webhook-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">Yeni Webhook</h3>
              <button onClick={() => setShowWh(false)}><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <input placeholder="Ad" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="pw-wh-name" />
              <input placeholder="https://yoursite.com/webhook" value={form.url || ""} onChange={e => setForm({ ...form, url: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="pw-wh-url" />
              <div>
                <div className="text-xs text-stone-600 mb-1">Eventler:</div>
                <div className="flex flex-wrap gap-1.5">
                  {eventsCatalog.map(ev => (
                    <button key={ev} onClick={() => toggleEvent(ev)} type="button" data-testid={`pw-wh-event-${ev}`}
                            className={`text-[11px] px-2 py-1 rounded-full border ${form.events?.includes(ev) ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-300"}`}>
                      {ev}
                    </button>
                  ))}
                </div>
              </div>
              <button onClick={createWebhook} disabled={!form.url || !form.events?.length} data-testid="pw-wh-save"
                      className="w-full py-2 text-sm text-white bg-stone-900 rounded-lg disabled:opacity-50">
                Oluştur
              </button>
            </div>
          </div>
        </div>
      )}

      {showKey && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowKey(false)}>
          <div className="bg-white rounded-xl w-full max-w-md p-5" onClick={e => e.stopPropagation()} data-testid="pw-key-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold">Yeni API Anahtarı</h3>
              <button onClick={() => setShowKey(false)}><X size={16} /></button>
            </div>
            <div className="space-y-3">
              <input placeholder="Ad" value={form.name || ""} onChange={e => setForm({ ...form, name: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" data-testid="pw-key-name" />
              <input placeholder="Scopes (virgülle: read, write, admin)" value={form.scopes || "read"}
                     onChange={e => setForm({ ...form, scopes: e.target.value })}
                     className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
              <button onClick={createKey} disabled={!form.name} data-testid="pw-key-save"
                      className="w-full py-2 text-sm text-white bg-stone-900 rounded-lg disabled:opacity-50">
                Oluştur
              </button>
            </div>
          </div>
        </div>
      )}

      {newSecret && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl w-full max-w-md p-5" data-testid="pw-secret-modal">
            <div className="flex items-center gap-2 mb-3">
              <Key size={20} className="text-amber-500" weight="fill" />
              <h3 className="text-base font-semibold">Bu değeri ŞİMDİ kopyalayın</h3>
            </div>
            <p className="text-xs text-stone-500 mb-3">Bu sırrı bir daha göremeyeceksiniz. Güvenli bir yere kaydedin.</p>
            <div className="bg-stone-50 border border-stone-200 rounded p-3 text-xs font-mono break-all">
              {newSecret.value}
            </div>
            <div className="flex gap-2 mt-3">
              <button onClick={() => { navigator.clipboard.writeText(newSecret.value); toast.success("Kopyalandı"); }}
                      className="flex-1 py-2 text-xs text-stone-700 bg-white border border-stone-300 rounded-lg inline-flex items-center justify-center gap-1.5">
                <Copy size={13} /> Kopyala
              </button>
              <button onClick={() => setNewSecret(null)} data-testid="pw-secret-close"
                      className="flex-1 py-2 text-xs text-white bg-stone-900 rounded-lg">
                Tamam
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
