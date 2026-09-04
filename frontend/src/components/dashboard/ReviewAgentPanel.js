/**
 * ReviewAgentPanel — admin UI for AI Review Agent (Lighthouse parity).
 *  - Per-property config: auto-respond enabled, tone, min rating
 *  - Batch draft button: generates AI drafts for last un-responded reviews
 *  - Pending queue: review/edit/publish draft per item
 */
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Star, Sparkle, PaperPlaneTilt, Pencil } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ReviewAgentPanel() {
  const [properties, setProperties] = useState([]);
  const [propertyId, setPropertyId] = useState("");
  const [config, setConfig] = useState(null);
  const [queue, setQueue] = useState([]);
  const [editing, setEditing] = useState({}); // review_id -> editable text
  const [busy, setBusy] = useState(false);

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
      const c = await axios.get(`${API}/review-agent/config/${propertyId}`, { withCredentials: true });
      setConfig(c.data);
      const q = await axios.get(`${API}/review-agent/queue/${propertyId}`, { withCredentials: true });
      setQueue(q.data.items || []);
    } catch (e) { toast.error("Yüklenemedi"); }
  }, [propertyId]);

  useEffect(() => { reload(); }, [reload]);

  async function saveConfig() {
    try {
      const { property_id, created_at, updated_at, ...body } = config;
      const r = await axios.post(`${API}/review-agent/config/${propertyId}`, body, { withCredentials: true });
      setConfig(r.data);
      toast.success("Kaydedildi");
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  }

  async function batchDraft() {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/review-agent/batch-draft/${propertyId}`, { limit: 25 }, { withCredentials: true });
      toast.success(`${r.data.drafted_count} taslak üretildi, ${r.data.auto_published_count} otomatik yayımlandı`);
      reload();
    } catch (e) { toast.error("Üretilemedi"); }
    finally { setBusy(false); }
  }

  async function publish(reviewId) {
    const text = editing[reviewId];
    try {
      await axios.post(`${API}/review-agent/publish/${reviewId}`,
        text ? { response_text: text } : {},
        { withCredentials: true });
      toast.success("Yayımlandı");
      reload();
    } catch (e) { toast.error(e.response?.data?.detail || "Yayımlanamadı"); }
  }

  async function regenDraft(reviewId) {
    try {
      const r = await axios.post(`${API}/review-agent/draft/${reviewId}`, {}, { withCredentials: true });
      setEditing({...editing, [reviewId]: r.data.draft });
      toast.success("Yeniden taslak üretildi");
      reload();
    } catch (e) { toast.error("Üretilemedi"); }
  }

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="review-agent-panel">
      <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">AI Review Agent</div>
          <h2 className="text-2xl font-semibold text-stone-900 inline-flex items-center gap-2">
            <Sparkle size={22} weight="fill" className="text-amber-500" /> Yorum Yanıt Ajanı
          </h2>
          <p className="text-sm text-stone-500 mt-1">
            GPT-4o-mini ile misafir yorumlarına profesyonel yanıt taslakları üretir, opsiyonel olarak otomatik yayımlar (Lighthouse parity).
          </p>
        </div>
        <select value={propertyId} onChange={e => setPropertyId(e.target.value)}
                data-testid="ra-property-select"
                className="px-3 py-1.5 text-sm border border-stone-300 rounded-lg bg-white">
          {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      <GbpConnectCard propertyId={propertyId} />

      {config && (
        <div className="bg-white border border-stone-200 rounded-xl p-4 mb-4 grid md:grid-cols-2 gap-3">
          <label className="inline-flex items-center gap-2">
            <input type="checkbox" checked={config.auto_respond_enabled}
                   onChange={e => setConfig({...config, auto_respond_enabled:e.target.checked})}
                   data-testid="ra-auto-toggle" />
            <span className="text-sm">Otomatik Yanıtla (batch'te)</span>
          </label>
          <label className="inline-flex items-center gap-2">
            <input type="checkbox" checked={config.require_review_before_publish}
                   onChange={e => setConfig({...config, require_review_before_publish:e.target.checked})}
                   data-testid="ra-review-toggle" />
            <span className="text-sm">Yayımdan önce insan onayı iste</span>
          </label>
          <Inp label="Min Otomatik Puan" v={config.min_rating_for_auto} type="number" onChange={v => setConfig({...config, min_rating_for_auto:parseInt(v)||4})} />
          <Inp label="Maks Otomatik Puan" v={config.max_rating_for_auto} type="number" onChange={v => setConfig({...config, max_rating_for_auto:parseInt(v)||5})} />
          <label className="block">
            <span className="text-xs text-stone-700">Ton</span>
            <select value={config.tone} onChange={e => setConfig({...config, tone:e.target.value})}
                    data-testid="ra-tone-select"
                    className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1">
              <option value="warm_professional">Sıcak & Profesyonel</option>
              <option value="formal">Resmi</option>
              <option value="friendly">Samimi</option>
            </select>
          </label>
          <Inp label="Yanıt kimliği / İmza (gerçek takım veya yetkili — uydurma isim yok)" v={config.sign_off} onChange={v => setConfig({...config, sign_off:v})} />

          {/* Publishing mode (Review Ops) */}
          <div className="md:col-span-2 border-t border-stone-100 pt-3">
            <div className="text-xs font-semibold text-stone-700 mb-2">Yayın Modu</div>
            <div className="grid sm:grid-cols-3 gap-2" data-testid="publishing-mode">
              {[["manual","Manual","Her yanıt tek tek insan onayından geçer."],
                ["smart_auto","Smart Auto","Kurallara uyan (4-5★, düşük risk, kaliteli, spam değil) otomatik yayımlanır; 1-3★, refund/legal/safety, personel şikâyeti insana düşer."],
                ["full_auto","Full Auto","İşletme açıkça yetki verdiyse: kritik risk / spam / legal-safety hariç hepsi otomatik. Varsayılan kapalı."]].map(([v,l,d]) => (
                <label key={v} className={`border rounded-lg p-2.5 cursor-pointer text-xs ${config.publishing_mode===v ? "border-stone-900 bg-stone-50" : "border-stone-200"}`}>
                  <div className="flex items-center gap-2 font-semibold">
                    <input type="radio" name="pubmode" value={v} checked={config.publishing_mode===v}
                           onChange={() => setConfig({...config, publishing_mode:v})} data-testid={`pubmode-${v}`} /> {l}
                  </div>
                  <p className="text-[11px] text-stone-500 mt-1">{d}</p>
                </label>
              ))}
            </div>
            {config.publishing_mode === "full_auto" && (
              <div className="mt-2">
                <Inp label="Full Auto yetkilendiren (ad + unvan, zorunlu)" v={config.full_auto_authorised_by}
                     onChange={v => setConfig({...config, full_auto_authorised_by:v})} />
              </div>
            )}
          </div>

          {/* Auto-approval rules */}
          <div className="md:col-span-2 border-t border-stone-100 pt-3">
            <div className="text-xs font-semibold text-stone-700 mb-2">Otomatik Onay Kuralları (Smart Auto)</div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2" data-testid="auto-rules">
              {[["min_rating","Min puan"],["max_spam_pct","Maks spam %"],["max_risk","Maks risk"],["min_quality","Min kalite"],["max_similarity","Maks benzerlik %"]].map(([k,l]) => (
                <label key={k} className="block">
                  <span className="text-[11px] text-stone-600">{l}</span>
                  <input type="number" value={config.auto_rules?.[k] ?? ""} data-testid={`rule-${k}`}
                         onChange={e => setConfig({...config, auto_rules:{...(config.auto_rules||{}), [k]: parseInt(e.target.value)||0}})}
                         className="w-full px-2 py-1 text-sm border border-stone-300 rounded-lg mt-0.5" />
                </label>
              ))}
            </div>
            <div className="flex flex-wrap gap-4 mt-2 text-xs">
              {[["block_refund","Refund/telafi isteyen → insan"],["block_legal","Legal → insan"],["block_safety","Safety → insan"]].map(([k,l]) => (
                <label key={k} className="inline-flex items-center gap-1.5">
                  <input type="checkbox" checked={config.auto_rules?.[k] !== false} data-testid={`rule-${k}`}
                         onChange={e => setConfig({...config, auto_rules:{...(config.auto_rules||{}), [k]: e.target.checked}})} /> {l}
                </label>
              ))}
            </div>
            <p className="text-[11px] text-stone-400 mt-2">Sabit güvenlik: kritik risk → yönetim eskalasyonu; spam ≥80% → yanıt yok; gizlilik ihlali (rezervasyon no, telefon, e-posta, ödeme, oda no, iç not, personel bilgisi) → yayın engellenir; puan/yorum değiştirme talebi → politika cezası.</p>
          </div>

          <div className="md:col-span-2 flex gap-2">
            <button onClick={saveConfig} data-testid="ra-save-config"
                    className="text-sm px-4 py-1.5 bg-stone-900 text-white rounded-lg">
              Yapılandırmayı Kaydet
            </button>
            <button onClick={batchDraft} disabled={busy} data-testid="ra-batch-btn"
                    className="text-sm px-4 py-1.5 bg-amber-500 text-white rounded-lg hover:bg-amber-600 inline-flex items-center gap-1.5 disabled:opacity-50">
              <Sparkle size={13} weight="fill" /> {busy ? "Üretiliyor…" : "Batch Taslak Üret (son 25)"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-stone-200 text-sm font-semibold">
          Bekleyen Taslaklar ({queue.length})
        </div>
        {queue.length === 0 ? (
          <div className="px-4 py-12 text-center text-stone-400 text-xs">
            Bekleyen taslak yok. "Batch Taslak Üret" butonuna basarak son yorumlardan AI yanıt üretebilirsiniz.
          </div>
        ) : queue.map(r => (
          <div key={r.id} className="border-t border-stone-100 p-4" data-testid={`ra-queue-${r.id}`}>
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{r.author || r.guest_name || "Misafir"}</span>
                  <span className="inline-flex items-center text-amber-500">
                    {[1,2,3,4,5].map(i => <Star key={i} size={12} weight={i <= (r.rating||0) ? "fill" : "regular"} />)}
                  </span>
                </div>
                <div className="text-xs text-stone-500">{(r.created_at||"").slice(0,10)} · {r.platform || r.source || "—"}</div>
              </div>
            </div>
            <div className="text-sm bg-stone-50 border border-stone-200 rounded p-3 mb-2">
              {r.comment || r.text}
            </div>
            {(r.response_quality || r.ai_decision) && (
              <div className="text-[11px] text-stone-500 mb-1" data-testid={`ra-meta-${r.id}`}>
                Kalite <b>{r.response_quality?.total}</b> · Benzerlik <b>{r.response_similarity?.max_pct}%</b> · Risk <b>{r.sentiment_analysis?.risk_level}</b>
                {r.ai_decision && <> · Karar <b>{r.ai_decision.action}</b> ({r.ai_decision.reasons?.join(", ")})</>}
                {r.response_privacy && !r.response_privacy.ok && <span className="ml-1 text-red-600 font-semibold">· Gizlilik ihlali: {r.response_privacy.violations.map(v=>v.type).join(", ")}</span>}
              </div>
            )}
            <div className="text-xs text-stone-500 mb-1">AI Taslak:</div>
            <textarea defaultValue={editing[r.id] ?? r.ai_draft ?? ""} rows={4}
                      onChange={e => setEditing({...editing, [r.id]: e.target.value})}
                      data-testid={`ra-edit-${r.id}`}
                      className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg" />
            <div className="flex gap-2 mt-2 justify-end">
              <button onClick={() => regenDraft(r.id)} data-testid={`ra-regen-${r.id}`}
                      className="text-xs px-3 py-1.5 bg-stone-100 text-stone-700 rounded-lg inline-flex items-center gap-1 hover:bg-stone-200">
                <Pencil size={12} /> Yeniden Üret
              </button>
              <button onClick={() => publish(r.id)} data-testid={`ra-publish-${r.id}`}
                      className="text-xs px-3 py-1.5 bg-emerald-600 text-white rounded-lg inline-flex items-center gap-1 hover:bg-emerald-700">
                <PaperPlaneTilt size={12} /> Yayımla
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function GbpConnectCard({ propertyId }) {
  const [st, setSt] = useState(null);
  const [locs, setLocs] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!propertyId) return;
    try { const r = await axios.get(`${API}/gbp/status?property_id=${propertyId}`, { withCredentials: true }); setSt(r.data); }
    catch (e) { setSt(null); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("gbp");
    if (q === "connected") toast.success("Google Business Profile bağlandı — şimdi konum seçin");
    else if (q === "error") toast.error("Google bağlantısı başarısız: " + (new URLSearchParams(window.location.search).get("reason") || ""));
  }, []);
  const connect = async () => {
    setBusy(true);
    try { const r = await axios.get(`${API}/gbp/oauth/start?property_id=${propertyId}`, { withCredentials: true }); window.location.href = r.data.url; }
    catch (e) { toast.error(e.response?.data?.detail || "Başlatılamadı"); setBusy(false); }
  };
  const loadLocs = async () => {
    setBusy(true);
    try { const r = await axios.get(`${API}/gbp/oauth/locations?property_id=${propertyId}`, { withCredentials: true }); setLocs(r.data.locations || []); }
    catch (e) { toast.error(e.response?.data?.detail || "Konumlar alınamadı"); }
    finally { setBusy(false); }
  };
  const pick = async (l) => {
    try { await axios.post(`${API}/gbp/oauth/select-location`, { property_id: propertyId, ...l }, { withCredentials: true }); toast.success(`Konum seçildi: ${l.title}`); setLocs(null); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Seçilemedi"); }
  };
  const disconnect = async () => {
    if (!window.confirm("Google bağlantısı kaldırılsın mı?")) return;
    await axios.delete(`${API}/gbp/oauth/disconnect?property_id=${propertyId}`, { withCredentials: true }); load();
  };
  if (!st) return null;
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4 mb-4" data-testid="gbp-connect-card">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="text-sm font-semibold text-stone-900">Google Business Profile — Bağlantı Sihirbazı</div>
          <div className="text-xs text-stone-500 mt-0.5" data-testid="gbp-status-line">
            {st.connected ? <>Bağlı ✓ {st.connection?.location_title ? `· Konum: ${st.connection.location_title}` : "· Konum seçilmedi"} · onaylanan Google yanıtları <b>gerçek</b> yayınlanır</>
              : st.client_configured ? "OAuth istemcisi hazır — 'Google ile bağlan' ile business.manage izni verin"
              : <>OAuth istemcisi yok: backend .env'e <code>GOOGLE_CLIENT_ID</code> ve <code>GOOGLE_CLIENT_SECRET</code> ekleyin. Redirect URI: <code className="break-all">{st.redirect_uri}</code></>}
            {!st.connected && <span className="ml-1 text-amber-700">(şu an MOCK kuyruk: {st.queue_pending} bekleyen)</span>}
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          {!st.connected && (
            <button onClick={connect} disabled={busy || !st.client_configured} data-testid="gbp-connect-btn"
              className="text-sm px-4 py-1.5 bg-[#1a73e8] text-white rounded-lg hover:bg-[#1558b0] disabled:opacity-50">Google ile bağlan</button>
          )}
          {st.connected && (
            <>
              <button onClick={loadLocs} disabled={busy} data-testid="gbp-locations-btn" className="text-sm px-3 py-1.5 bg-stone-900 text-white rounded-lg">Konum seç</button>
              <button onClick={disconnect} data-testid="gbp-disconnect-btn" className="text-sm px-3 py-1.5 bg-white border border-red-200 text-red-600 rounded-lg">Bağlantıyı kes</button>
            </>
          )}
        </div>
      </div>
      {locs && (
        <div className="mt-3 grid sm:grid-cols-2 gap-2" data-testid="gbp-locations">
          {locs.length === 0 && <p className="text-xs text-stone-400">Bu Google hesabında doğrulanmış konum bulunamadı.</p>}
          {locs.map(l => (
            <button key={l.location_id} onClick={() => pick(l)} className="text-left text-xs border border-stone-200 rounded-lg p-2 hover:bg-stone-50">
              <div className="font-semibold">{l.title}</div><div className="text-stone-400">{l.account_name} · {l.store_code || l.location_id}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Inp({ label, v, onChange, type="text" }) {
  return (
    <label className="block">
      <span className="text-xs text-stone-700">{label}</span>
      <input value={v||""} type={type} onChange={e => onChange(e.target.value)}
             className="w-full px-3 py-1.5 text-sm border border-stone-300 rounded-lg mt-1" />
    </label>
  );
}
