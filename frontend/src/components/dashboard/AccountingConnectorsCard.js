import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const NAMES = { xero: "Xero", qbo: "QuickBooks Online" };

export default function AccountingConnectorsCard({ propertyId }) {
  const [d, setD] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!propertyId) return;
    try { const r = await axios.get(`${API}/accounting/connectors/${propertyId}`); setD(r.data); } catch { setD(null); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("acct") === "connected") toast.success(`${NAMES[p.get("provider")] || "Muhasebe"} bağlandı`);
    if (p.get("acct") === "error") toast.error("Muhasebe bağlantısı başarısız: " + (p.get("reason") || ""));
  }, []);
  const connect = async (p) => {
    try { const r = await axios.get(`${API}/accounting/oauth/${p}/start`, { params: { property_id: propertyId } }); window.location.href = r.data.url; }
    catch (e) { toast.error(e.response?.data?.detail || "Başlatılamadı"); }
  };
  const disconnect = async (p) => { await axios.delete(`${API}/accounting/oauth/${p}/disconnect`, { params: { property_id: propertyId } }); load(); };
  const run = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/accounting/sync/run/${propertyId}`);
      const res = r.data.results?.[0];
      toast.success(`Yevmiye: ${Object.entries(res?.results || {}).map(([p, s]) => `${NAMES[p]} → ${s}`).join(", ")}${res?.efatura ? ` · e-Fatura ${res.efatura.issued} adet (${res.efatura.mode})` : ""}`);
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Çalıştırılamadı"); } finally { setBusy(false); }
  };
  const doPreview = async () => { const r = await axios.get(`${API}/accounting/journal/preview/${propertyId}`); setPreview(r.data); };
  const toggleEf = async (v) => { await axios.post(`${API}/accounting/settings/${propertyId}`, { efatura_enabled: v }); load(); };
  if (!d) return null;
  return (
    <div className="bg-stone-900 border border-stone-700 rounded-xl p-4 space-y-3" data-testid="accounting-connectors-card">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="font-semibold text-stone-100">Muhasebe Konektörleri — günlük yevmiye (03:30 robotu)</h3>
        <div className="flex gap-2">
          <button onClick={doPreview} data-testid="acct-preview-btn" className="text-xs px-3 py-1.5 rounded-lg bg-stone-700 text-stone-100">Dünün yevmiyesi</button>
          <button onClick={run} disabled={busy} data-testid="acct-run-btn" className="text-xs px-3 py-1.5 rounded-lg bg-emerald-600 text-white disabled:opacity-50">{busy ? "Gönderiliyor…" : "Şimdi gönder"}</button>
        </div>
      </div>
      <div className="grid md:grid-cols-3 gap-3">
        {Object.entries(d.providers).map(([p, v]) => (
          <div key={p} className="border border-stone-700 rounded-lg p-3 text-xs" data-testid={`acct-provider-${p}`}>
            <div className="font-semibold text-stone-100">{NAMES[p]} {v.connected ? <span className="text-emerald-400">● bağlı</span> : <span className="text-stone-500">○ bağlı değil</span>}</div>
            <div className="text-stone-400 mt-1">{v.client_configured ? "OAuth istemcisi hazır" : <>Env'de {p.toUpperCase()}_CLIENT_ID/SECRET yok · redirect: <code className="break-all">{v.redirect_uri}</code></>}</div>
            <MappingEditor provider={p} propertyId={propertyId} mapping={v.mapping} onSaved={load} />
            <div className="mt-2 flex gap-1.5">
              {!v.connected ? <button onClick={() => connect(p)} disabled={!v.client_configured} data-testid={`acct-connect-${p}`} className="px-2 py-1 rounded bg-sky-600 text-white disabled:opacity-40">Bağlan</button>
                : <button onClick={() => disconnect(p)} data-testid={`acct-disconnect-${p}`} className="px-2 py-1 rounded bg-red-700 text-white">Bağlantıyı kes</button>}
            </div>
          </div>
        ))}
        <div className="border border-stone-700 rounded-lg p-3 text-xs" data-testid="acct-efatura">
          <div className="font-semibold text-stone-100">TR e-Fatura (UBL-TR 1.2) {d.efatura.live ? <span className="text-emerald-400">● entegratör</span> : <span className="text-amber-400">● MOCK taslak</span>}</div>
          <div className="text-stone-400 mt-1">Çıkış yapan konaklamalar için TEMELFATURA XML. Kesilen: <b className="text-stone-200">{d.efatura.issued}</b>{!d.efatura.live && " · EFATURA_INTEGRATOR_KEY yok → GİB'e gönderilmez"}</div>
          <label className="mt-2 flex items-center gap-2 text-stone-300"><input type="checkbox" checked={d.efatura.enabled} onChange={e => toggleEf(e.target.checked)} data-testid="acct-efatura-toggle" /> Günlük robotta otomatik kes</label>
        </div>
      </div>
      {preview && (
        <div className="border border-stone-700 rounded-lg p-3 text-xs text-stone-300" data-testid="acct-preview">
          <b>{preview.business_date}</b> · tahsilat {preview.payments} · gelir (net) {preview.revenue} · vergi {preview.tax} · AR Δ {preview.ar_delta} · {preview.checkouts} çıkış · {preview.balanced ? "✓ dengeli" : "✗ dengesiz"}
          <div className="mt-1 text-stone-400">{preview.lines.map(l => `${l.side === "debit" ? "DR" : "CR"} ${l.account} ${l.amount}`).join(" · ")}</div>
        </div>
      )}
      {d.recent_journals.length > 0 && (
        <div className="text-[11px] text-stone-400" data-testid="acct-recent">
          Son gönderimler: {d.recent_journals.slice(0, 5).map(j => `${j.business_date} ${NAMES[j.provider]} → ${j.status}`).join(" · ")}
        </div>
      )}
    </div>
  );
}


function MappingEditor({ provider, propertyId, mapping, onSaved }) {
  const [m, setM] = useState(mapping);
  const [dirty, setDirty] = useState(false);
  useEffect(() => { setM(mapping); setDirty(false); }, [mapping]);
  const save = async () => {
    try { await axios.post(`${API}/accounting/mapping/${provider}/${propertyId}`, m); toast.success("Hesap eşlemesi kaydedildi"); setDirty(false); onSaved(); }
    catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };
  return (
    <div className="mt-2 grid grid-cols-4 gap-1" data-testid={`acct-mapping-${provider}`}>
      {[["payments", "Tahsilat"], ["revenue", "Gelir"], ["tax", "Vergi"], ["ar", "AR"]].map(([k, l]) => (
        <label key={k} className="block"><span className="text-[9px] text-stone-500">{l}</span>
          <input value={m[k] ?? ""} onChange={e => { setM({ ...m, [k]: e.target.value }); setDirty(true); }} data-testid={`acct-map-${provider}-${k}`}
            className="w-full h-6 px-1 rounded bg-stone-800 border border-stone-600 text-stone-100 text-[11px]" /></label>
      ))}
      {dirty && <button onClick={save} data-testid={`acct-map-save-${provider}`} className="col-span-4 h-6 mt-1 rounded bg-emerald-600 text-white text-[10px]">Eşlemeyi kaydet</button>}
    </div>
  );
}
