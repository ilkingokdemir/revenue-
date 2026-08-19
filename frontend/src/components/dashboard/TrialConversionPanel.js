import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = process.env.REACT_APP_BACKEND_URL;
const cfg = { withCredentials: true };
const PLANS = ["basic", "rms", "cm", "pro", "full"];

const STATUS_BADGE = {
  active: ["bg-cyan-50 text-cyan-700 border-cyan-200", "Denemede"],
  expired: ["bg-rose-50 text-rose-700 border-rose-200", "Süresi doldu"],
  converted: ["bg-emerald-50 text-emerald-700 border-emerald-200", "Dönüştü ✓"],
};

export const TrialConversionPanel = () => {
  const [data, setData] = useState(null);
  const [email, setEmail] = useState(null);
  const [keyInput, setKeyInput] = useState("");
  const [senderInput, setSenderInput] = useState("");
  const [testTo, setTestTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [convertPlan, setConvertPlan] = useState({});

  const load = useCallback(async () => {
    try {
      const [t, e] = await Promise.all([
        axios.get(`${API}/api/trial-conversion/summary`, cfg),
        axios.get(`${API}/api/email-settings`, cfg),
      ]);
      setData(t.data); setEmail(e.data);
      setSenderInput(e.data.sender_email || "");
    } catch { toast.error("Deneme verileri yüklenemedi"); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const saveKey = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/email-settings`, { resend_api_key: keyInput, sender_email: senderInput }, cfg);
      toast.success(r.data.message); setKeyInput(""); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); } finally { setBusy(false); }
  };

  const sendTest = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/email-settings/test`, { to: testTo }, cfg);
      (r.data.status === "sent" ? toast.success : toast.info)(r.data.message);
    } catch (e) { toast.error(e.response?.data?.detail || "Test başarısız"); } finally { setBusy(false); }
  };

  const markConverted = async (pid) => {
    try {
      const r = await axios.post(`${API}/api/trial-conversion/${pid}/convert`, { plan: convertPlan[pid] || "pro" }, cfg);
      toast.success(`Dönüşüm kaydedildi → ${r.data.plan.toUpperCase()}`); load();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  };

  const extendTrial = async (pid) => {
    try {
      const r = await axios.post(`${API}/api/trial-conversion/${pid}/extend`, {}, cfg);
      toast.success(`Deneme 7 gün uzatıldı → yeni bitiş: ${new Date(r.data.trial_ends_at).toLocaleDateString("tr-TR")}`); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Uzatılamadı"); }
  };

  const sendUpgrade = async (pid) => {
    try {
      const r = await axios.post(`${API}/api/trial-conversion/${pid}/send-upgrade-email`, {}, cfg);
      (r.data.status === "sent" ? toast.success : toast.info)(`Yükseltme e-postası → ${r.data.to} (${r.data.status})`);
    } catch (e) { toast.error(e.response?.data?.detail || "Gönderilemedi"); }
  };

  if (!data) return null;
  const m = data.metrics;

  return (
    <div className="space-y-4">
      {/* Resend ayarları */}
      <section className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="email-settings-card">
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-sm font-black text-stone-800 flex-1">📮 E-posta Gönderimi (Resend)</h2>
          <span data-testid="email-live-badge"
            className={`px-2 py-0.5 rounded-full text-[10px] font-black border ${email?.live ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
            {email?.live ? "CANLI" : "MOCK — anahtar bekleniyor"}
          </span>
        </div>
        <div className="grid sm:grid-cols-2 gap-2">
          <input value={keyInput} onChange={(e) => setKeyInput(e.target.value)} data-testid="resend-key-input"
            placeholder={email?.key_set ? `Kayıtlı: ${email.key_masked} — değiştirmek için yenisini girin` : "re_ ile başlayan Resend API anahtarınız"}
            className="border border-stone-300 rounded-lg px-3 py-2 text-sm" type="password" autoComplete="off" />
          <input value={senderInput} onChange={(e) => setSenderInput(e.target.value)} data-testid="resend-sender-input"
            placeholder="Gönderici (ör. info@oteliniz.com)" className="border border-stone-300 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-2">
          <button onClick={saveKey} disabled={busy || !keyInput} data-testid="resend-save-btn"
            className="px-3 py-2 rounded-lg bg-stone-900 text-white text-xs font-bold disabled:opacity-40">Anahtarı Kaydet & Doğrula</button>
          <input value={testTo} onChange={(e) => setTestTo(e.target.value)} data-testid="resend-test-to-input"
            placeholder="test@adresiniz.com" className="border border-stone-300 rounded-lg px-3 py-2 text-xs w-48" />
          <button onClick={sendTest} disabled={busy || !testTo} data-testid="resend-test-btn"
            className="px-3 py-2 rounded-lg border border-stone-300 text-xs font-bold text-stone-700 disabled:opacity-40">Test E-postası Gönder</button>
          {email?.key_set && email?.verified && <span className="text-[11px] text-emerald-600 font-bold">Anahtar doğrulandı ✓</span>}
        </div>
        <p className="text-[11px] text-stone-400 mt-2">Anahtar girildiğinde karşılama, deneme hatırlatma ve rapor e-postaları gerçek gönderime geçer. Anahtar: resend.com/api-keys</p>
      </section>

      {/* Deneme dönüşüm paneli */}
      <section className="bg-white border border-stone-200 rounded-2xl p-4" data-testid="trial-conversion-card">
        <h2 className="text-sm font-black text-stone-800 mb-3">⏳ Deneme Dönüşüm Paneli — self-signup oteller</h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3">
          {[["Toplam Deneme", m.total, "text-stone-800"], ["Aktif", m.active, "text-cyan-600"],
            ["Süresi Dolan", m.expired, "text-rose-600"], ["Dönüşen", m.converted, "text-emerald-600"],
            ["Dönüşüm Oranı", `%${m.conversion_rate}`, "text-indigo-600"]].map(([l, v, c]) => (
            <div key={l} className="bg-stone-50 border border-stone-200 rounded-xl px-3 py-2" data-testid={`trial-metric-${l}`}>
              <div className={`text-lg font-black ${c}`}>{v}</div>
              <div className="text-[10px] font-bold text-stone-500 uppercase">{l}</div>
            </div>
          ))}
        </div>

        {/* Dönüşüm hunisi + haftalık kohort */}
        {data.funnel && (
          <div className="grid md:grid-cols-2 gap-3 mb-4">
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-3" data-testid="trial-funnel">
              <div className="text-[11px] font-black text-stone-600 uppercase mb-2">🔻 Dönüşüm Hunisi — kayıp nerede?</div>
              <div className="space-y-1.5">
                {data.funnel.map((f, i) => {
                  const base = data.funnel[0].count || 1;
                  const pct = Math.round((f.count / base) * 100);
                  const prev = i > 0 ? data.funnel[i - 1].count : null;
                  const loss = prev !== null && prev > 0 ? prev - f.count : 0;
                  const colors = ["bg-stone-700", "bg-sky-500", "bg-amber-500", "bg-rose-400", "bg-emerald-500"];
                  return (
                    <div key={f.step} data-testid={`funnel-step-${i}`}>
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-bold text-stone-700">{f.step}</span>
                        <span className="text-stone-500">{f.count} <span className="font-black">%{pct}</span>
                          {loss > 0 && <span className="text-rose-500 font-bold ml-1">−{loss} kayıp</span>}
                        </span>
                      </div>
                      <div className="h-3 bg-stone-200 rounded-full overflow-hidden mt-0.5">
                        <div className={`h-full rounded-full ${colors[i] || "bg-stone-500"} transition-all`} style={{ width: `${Math.max(pct, 2)}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="bg-stone-50 border border-stone-200 rounded-xl p-3" data-testid="trial-weekly">
              <div className="text-[11px] font-black text-stone-600 uppercase mb-2">📅 Son 8 Hafta — kayıt vs dönüşüm (kohort)</div>
              {(() => {
                const maxV = Math.max(1, ...data.weekly.map((w) => w.signups));
                return (
                  <div className="flex items-end gap-1.5 h-28">
                    {data.weekly.map((w) => (
                      <div key={w.week} className="flex-1 flex flex-col items-center gap-0.5" data-testid={`week-${w.week}`}
                        title={`${w.week}: ${w.signups} kayıt · ${w.conversions} dönüşüm`}>
                        <span className="text-[9px] font-black text-stone-500">{w.signups > 0 ? w.signups : ""}</span>
                        <div className="w-full flex items-end justify-center gap-0.5" style={{ height: "70px" }}>
                          <div className="w-2/5 bg-sky-400 rounded-t" style={{ height: `${(w.signups / maxV) * 100}%`, minHeight: w.signups ? 3 : 0 }} />
                          <div className="w-2/5 bg-emerald-500 rounded-t" style={{ height: `${(w.conversions / maxV) * 100}%`, minHeight: w.conversions ? 3 : 0 }} />
                        </div>
                        <span className="text-[8px] text-stone-400 whitespace-nowrap">{w.week}</span>
                      </div>
                    ))}
                  </div>
                );
              })()}
              <div className="flex gap-3 mt-1.5 text-[10px] text-stone-500">
                <span><span className="inline-block w-2 h-2 bg-sky-400 rounded-sm mr-1" />Kayıt</span>
                <span><span className="inline-block w-2 h-2 bg-emerald-500 rounded-sm mr-1" />Dönüşüm</span>
              </div>
            </div>
          </div>
        )}
        {data.trials.length === 0 ? (
          <p className="text-xs text-stone-400" data-testid="trial-empty">Henüz self-signup deneme hesabı yok.</p>
        ) : (
          <div className="space-y-1.5 max-h-96 overflow-auto">
            {data.trials.map((t) => {
              const [cls, label] = STATUS_BADGE[t.status] || STATUS_BADGE.active;
              return (
                <div key={t.property_id} className="flex flex-wrap items-center gap-2 bg-stone-50 border border-stone-200 rounded-xl px-3 py-2" data-testid={`trial-row-${t.property_id}`}>
                  <div className="flex-1 min-w-[160px]">
                    <div className="text-sm font-bold text-stone-800">{t.name || t.property_id}</div>
                    <div className="text-[10px] text-stone-500">{t.owner_email || "—"} · {(t.plan || "").toUpperCase()}</div>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-black border ${cls}`}>{label}</span>
                  {t.status !== "converted" && t.days_left !== null && (
                    <span className={`text-[11px] font-bold ${t.days_left <= 0 ? "text-rose-600" : t.days_left <= 3 ? "text-amber-600" : "text-stone-600"}`}>
                      {t.days_left <= 0 ? `${Math.abs(Math.floor(t.days_left))} gün önce bitti` : `${Math.ceil(t.days_left)} gün kaldı`}
                    </span>
                  )}
                  <div className="flex gap-1">
                    {t.emails_sent.includes("t3") && <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 text-[9px] font-black" title="3 gün hatırlatması gönderildi">✉ T-3</span>}
                    {t.emails_sent.includes("expired") && <span className="px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 text-[9px] font-black" title="Bitiş e-postası gönderildi">✉ BİTİŞ</span>}
                  </div>
                  {t.status !== "converted" && (
                    <>
                      <button onClick={() => extendTrial(t.property_id)} data-testid={`trial-extend-${t.property_id}`}
                        title="Denemeyi 7 gün uzat — süresi dolmuşsa kilit anında açılır"
                        className="px-2 py-1 rounded-lg border border-indigo-300 text-[10px] font-bold text-indigo-600 hover:bg-indigo-50">+7 gün</button>
                      <button onClick={() => sendUpgrade(t.property_id)} data-testid={`trial-send-email-${t.property_id}`}
                        className="px-2 py-1 rounded-lg border border-stone-300 text-[10px] font-bold text-stone-600 hover:bg-stone-100">✉ Yükseltme Maili</button>
                      <select value={convertPlan[t.property_id] || "pro"} data-testid={`trial-plan-select-${t.property_id}`}
                        onChange={(e) => setConvertPlan((s) => ({ ...s, [t.property_id]: e.target.value }))}
                        className="border border-stone-300 rounded-lg px-1.5 py-1 text-[10px] font-bold">
                        {PLANS.map((p) => <option key={p} value={p}>{p.toUpperCase()}</option>)}
                      </select>
                      <button onClick={() => markConverted(t.property_id)} data-testid={`trial-convert-${t.property_id}`}
                        className="px-2 py-1 rounded-lg bg-emerald-600 text-white text-[10px] font-bold hover:bg-emerald-700">Dönüştü ✓</button>
                    </>
                  )}
                  {t.status === "converted" && <span className="text-[10px] text-emerald-600 font-bold">{(t.converted_plan || "").toUpperCase()} planına geçti</span>}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
};

export default TrialConversionPanel;
