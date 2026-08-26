import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Sun, PaperPlaneTilt, MoonStars } from "@phosphor-icons/react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/morning-karne`;
const EOD_API = `${process.env.REACT_APP_BACKEND_URL}/api/eod-report`;

export default function MorningKarnePanel({ propertyId = "default" }) {
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [trend, setTrend] = useState([]);
  const [eod, setEod] = useState(null);
  const [busy, setBusy] = useState(false);
  const [eodBusy, setEodBusy] = useState(false);
  const [digest, setDigest] = useState(null);
  const [digestBusy, setDigestBusy] = useState(false);
  const [emailCfg, setEmailCfg] = useState(null);
  const [keyInput, setKeyInput] = useState("");
  const [testTo, setTestTo] = useState("");
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async () => {
    try {
      const [l, h, t, e, d, ec] = await Promise.all([
        axios.get(`${API}/${pid}/latest`),
        axios.get(`${API}/${pid}/history`),
        axios.get(`${API}/${pid}/ladder-trend?days=14`),
        axios.get(`${EOD_API}/${pid}/latest`),
        axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/weekly-digest/${pid}/latest`),
        axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/email-settings`),
      ]);
      setData(l.data);
      setHistory(h.data.history || []);
      setTrend(t.data.trend || []);
      setEod(e.data);
      setDigest(d.data);
      setEmailCfg(ec.data);
    } catch { toast.error("Karne verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function sendDigestNow() {
    setDigestBusy(true);
    try {
      const r = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/weekly-digest/${pid}/send-now`);
      toast.success(`Haftalık bülten gönderildi → ${r.data.sent_to.length} yönetici`);
      load();
    } catch { toast.error("Bülten gönderilemedi"); }
    setDigestBusy(false);
  }

  async function saveResendKey(e) {
    e.preventDefault();
    try {
      const r = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/email-settings`, { resend_api_key: keyInput });
      toast.success(r.data.message || "Resend anahtarı kaydedildi");
      setKeyInput(""); load();
    } catch (err) { toast.error(err.response?.data?.detail || "Anahtar kaydedilemedi"); }
  }

  async function sendTestEmail() {
    if (!testTo.includes("@")) { toast.error("Test için geçerli bir alıcı e-posta girin"); return; }
    try {
      const r = await axios.post(`${process.env.REACT_APP_BACKEND_URL}/api/email-settings/test`, { to: testTo });
      if (r.data.status === "sent") toast.success(`Test e-postası GERÇEKTEN gönderildi → ${testTo}`);
      else if (r.data.status === "mocked") toast.info("Anahtar yok — test MOCK kaydedildi (email_outbox)");
      else toast.error(r.data.message || "Gönderim başarısız");
      load();
    } catch (err) { toast.error(err.response?.data?.detail || "Test gönderilemedi"); }
  }

  async function sendEodNow() {
    setEodBusy(true);
    try {
      const r = await axios.post(`${EOD_API}/${pid}/send-now`, {});
      toast.success(`Gün sonu raporu gönderildi → ${r.data.sent_to.length} yönetici`);
      load();
    } catch { toast.error("Gönderilemedi"); }
    setEodBusy(false);
  }

  async function sendNow() {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/${pid}/send-now`);
      toast.success(`Karne gönderildi (not: ${r.data.karne.grade}) → ${r.data.sent_to.length} yönetici`);
      load();
    } catch { toast.error("Gönderilemedi"); }
    setBusy(false);
  }

  async function toggle() {
    try {
      const next = !data.config.enabled;
      await axios.put(`${API}/${pid}/config`, { enabled: next });
      toast.success(next ? "Günlük otomatik karne AÇIK" : "Günlük otomatik karne kapalı");
      load();
    } catch { toast.error("Ayar kaydedilemedi"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const k = data.live_preview;
  const gradeColor = { A: "text-emerald-400", B: "text-amber-400", C: "text-rose-400" }[k.grade];

  return (
    <div className="p-5 max-w-[1000px] mx-auto space-y-4" data-testid="morning-karne-panel">
      <div className="bg-gradient-to-br from-stone-900 via-yellow-950 to-amber-950 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-yellow-300">
              <Sun size={14} /> Daily Report Card
            </div>
            <h1 className="text-2xl font-bold mt-1">Sabah Karnesi</h1>
            <p className="text-sm text-stone-300 mt-1">
              Sistem her sabah (~09:00 TR) kendi bekçi-zinciri karnesini yöneticilere e-postayla verir:
              doluluk, merdivenler, ikinci-yazıcı, vitrin ve 5xx sağlığı tek notta.
            </p>
          </div>
          <div className="flex gap-2 items-center">
            <button onClick={toggle} data-testid="karne-toggle-btn"
              className={`px-4 py-2 rounded-full text-sm font-semibold ${data.config.enabled ? "bg-emerald-500 text-stone-900" : "bg-white/15"}`}>
              Otomatik: {data.config.enabled ? "AÇIK" : "KAPALI"}
            </button>
            <button onClick={sendNow} disabled={busy} data-testid="karne-send-now-btn"
              className="px-4 py-2 rounded-full bg-yellow-500 hover:bg-yellow-400 text-stone-900 text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
              <PaperPlaneTilt size={16} /> Şimdi Gönder
            </button>
          </div>
        </div>
        <div className="flex items-center gap-6 mt-5">
          <div>
            <div className={`text-6xl font-black ${gradeColor}`} data-testid="karne-grade">{k.grade}</div>
            <div className="text-xs text-stone-300">Bugünkü not (canlı)</div>
          </div>
          <div className="text-sm text-stone-300">
            {k.date} · Doluluk %{k.occ}
            {data.latest && <div className="text-xs mt-1">Son gönderim: {data.latest.date} → {data.latest.sent_to?.length} yönetici</div>}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="ladder-weekly-card">
        <div className="text-xs uppercase tracking-wider text-stone-400 mb-2">🪜 Merdiven Haftalık Özeti (son 7 gün, tahmini)</div>
        {k.ladder_weekly ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-emerald-50 rounded-xl p-3">
              <div className="text-xl font-bold text-emerald-700">≈{k.ladder_weekly.lastday.recovered_estimate}</div>
              <div className="text-xs text-stone-500">Son-gün merdiveni kurtarılan gelir — {k.ladder_weekly.lastday.sold_after_discount} gece indirimle satıldı ({k.ladder_weekly.lastday.steps} kademe)</div>
            </div>
            <div className="bg-amber-50 rounded-xl p-3">
              <div className="text-xl font-bold text-amber-700">≈{k.ladder_weekly.ramp.uplift_estimate}</div>
              <div className="text-xs text-stone-500">Zam merdiveni ek gelir — {k.ladder_weekly.ramp.guest_approved} misafir-onaylı kademe ({k.ladder_weekly.ramp.steps} zam)</div>
            </div>
            <div className="bg-stone-900 text-white rounded-xl p-3">
              <div className="text-xl font-bold" data-testid="ladder-weekly-total">≈{k.ladder_weekly.total_estimate}</div>
              <div className="text-xs text-stone-300">Toplam merdiven katkısı (7g)</div>
            </div>
          </div>
        ) : <p className="text-sm text-stone-400">Veri yok.</p>}
        {trend.length > 0 && (
          <div className="mt-4" data-testid="ladder-trend-chart">
            <div className="text-xs uppercase tracking-wider text-stone-400 mb-1">Günlük trend (14 gün, tahmini)</div>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={trend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip formatter={(v, n) => [`≈${v}`, n === "recovered" ? "Kurtarılan (son-gün)" : n === "uplift" ? "Ek gelir (zam)" : "Toplam"]}
                  labelFormatter={(d) => `Tarih: ${d}`} />
                <Line type="monotone" dataKey="recovered" stroke="#059669" strokeWidth={2} dot={false} name="recovered" />
                <Line type="monotone" dataKey="uplift" stroke="#d97706" strokeWidth={2} dot={false} name="uplift" />
                <Line type="monotone" dataKey="total" stroke="#1c1917" strokeWidth={2} strokeDasharray="4 3" dot={false} name="total" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="eod-report-card">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
          <div>
            <div className="text-xs uppercase tracking-wider text-stone-400 mb-1 flex items-center gap-1">
              <MoonStars size={14} /> Gün Sonu Raporu (EOD)
            </div>
            <p className="text-sm text-stone-600">
              Gece denetimi (gün kapanışı) yapılınca otomatik e-postalanır — kapanış anındaki değişmez snapshot kullanılır.
            </p>
            {eod?.latest && (
              <p className="text-xs text-stone-400 mt-1" data-testid="eod-last-sent">
                Son gönderim: {eod.latest.business_date} → {eod.latest.sent_to?.length} yönetici ({eod.latest.report?.source === "night_audit_close" ? "kapanış snapshot" : "canlı tahmin"})
              </p>
            )}
          </div>
          <button onClick={sendEodNow} disabled={eodBusy} data-testid="eod-send-now-btn"
            className="px-4 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
            <PaperPlaneTilt size={16} /> Bugünü Şimdi Gönder
          </button>
        </div>
        {eod?.live_preview && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-center" data-testid="eod-preview">
            {[
              ["Doluluk", `%${eod.live_preview.occupancy}`],
              ["Gelir", `£${eod.live_preview.totals.charges}`],
              ["Giriş/Çıkış", `${eod.live_preview.counts.arrivals}/${eod.live_preview.counts.departures}`],
              ["No-show", eod.live_preview.no_shows],
              ["Yarın giriş", eod.live_preview.tomorrow_arrivals],
            ].map(([k, v]) => (
              <div key={k} className="bg-stone-50 rounded-xl p-2">
                <div className="text-base font-bold">{v}</div>
                <div className="text-[10px] text-stone-500">{k}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="weekly-digest-card">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
          <div>
            <div className="text-xs uppercase tracking-wider text-stone-400 mb-1">📊 Haftalık Yönetici Bülteni</div>
            <p className="text-sm text-stone-600">Her pazartesi ~10:00'da geçen haftanın özeti yöneticilere e-postalanır.</p>
            {digest?.latest && (
              <p className="text-xs text-stone-400 mt-1" data-testid="digest-last-sent">
                Son gönderim: {digest.latest.digest?.week_start} haftası → {digest.latest.sent_to?.length} yönetici
              </p>
            )}
          </div>
          <button onClick={sendDigestNow} disabled={digestBusy} data-testid="digest-send-now-btn"
            className="px-4 py-2 rounded-full bg-stone-900 hover:bg-stone-700 text-white text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
            <PaperPlaneTilt size={16} /> Bülteni Şimdi Gönder
          </button>
        </div>
        {digest?.live_preview && (
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-center" data-testid="digest-preview">
            {[
              ["Gelir (7g)", `£${digest.live_preview.revenue}`, digest.live_preview.deltas?.revenue_pct, "%"],
              ["Doluluk", `%${digest.live_preview.occupancy}`, digest.live_preview.deltas?.occupancy_pts, " puan"],
              ["ADR", `£${digest.live_preview.adr}`, digest.live_preview.deltas?.adr_pct, "%"],
              ["Giriş", digest.live_preview.arrivals, digest.live_preview.deltas?.arrivals_diff, ""],
              ["İptal", digest.live_preview.cancellations, null, ""],
              ["Merdiven", `≈£${digest.live_preview.ladder?.total_estimate}`, null, ""],
            ].map(([kk, v, delta, suffix]) => (
              <div key={kk} className="bg-stone-50 rounded-xl p-2">
                <div className="text-base font-bold">{v}</div>
                <div className="text-[10px] text-stone-500">{kk}</div>
                {delta != null && (
                  <div className={`text-[10px] font-bold ${delta > 0 ? "text-emerald-600" : delta < 0 ? "text-rose-600" : "text-stone-400"}`}
                    data-testid={`digest-delta-${kk}`}>
                    {delta > 0 ? `▲ +${delta}${suffix}` : delta < 0 ? `▼ ${delta}${suffix}` : `= 0${suffix}`}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="email-settings-card">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
          <div className="text-xs uppercase tracking-wider text-stone-400">✉️ E-posta (Resend) Ayarları</div>
          {emailCfg && (
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${(emailCfg.key_set || emailCfg.live) ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}
              data-testid="email-mode-badge">
              {(emailCfg.key_set || emailCfg.live) ? `✓ GERÇEK GÖNDERİM ${emailCfg.key_masked ? `(${emailCfg.key_masked})` : ""}` : "MOCK — anahtar girilmedi"}
            </span>
          )}
        </div>
        <p className="text-sm text-stone-600 mb-3">
          Resend API anahtarınızı girin; karne, EOD, kutlama ve bülten e-postaları gerçekten ulaşsın.
          Anahtar: <a href="https://resend.com/api-keys" target="_blank" rel="noreferrer" className="text-indigo-600 underline">resend.com/api-keys</a>
        </p>
        <form onSubmit={saveResendKey} className="flex flex-wrap gap-2 items-center">
          <input type="password" value={keyInput} onChange={(e) => setKeyInput(e.target.value)}
            placeholder="re_..." required data-testid="resend-key-input"
            className="flex-1 min-w-[200px] border rounded-lg px-3 py-2 text-sm" />
          <button type="submit" data-testid="resend-key-save-btn"
            className="px-4 py-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold">
            Anahtarı Kaydet
          </button>
        </form>
        <div className="flex flex-wrap gap-2 items-center mt-2">
          <input type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)}
            placeholder="test alıcısı (e-posta)" data-testid="resend-test-to-input"
            className="flex-1 min-w-[200px] border rounded-lg px-3 py-2 text-sm" />
          <button type="button" onClick={sendTestEmail} data-testid="resend-test-btn"
            className="px-4 py-2 rounded-full border border-stone-300 text-sm font-semibold hover:bg-stone-50">
            Test E-postası Gönder
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Karne Kalemleri (canlı önizleme)</h2>
        <div className="space-y-2" data-testid="karne-checks">
          {k.checks.map((c, i) => (
            <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-xl ${c.status === "ok" ? "bg-stone-50" : "bg-amber-50 border border-amber-200"}`}>
              <div className="text-sm">{c.status === "ok" ? "✅" : "⚠️"} {c.name}</div>
              <div className="text-sm font-semibold">{c.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Gönderim Geçmişi</h2>
        {history.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="karne-empty-history">Henüz gönderim yok — "Şimdi Gönder" ile test edin (Resend anahtarı yoksa e-posta MOCK olarak email_outbox'a düşer).</p>
        ) : (
          <table className="w-full text-sm" data-testid="karne-history-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Tarih</th><th>Not</th><th>Doluluk</th><th>Alıcı</th><th>Tür</th>
            </tr></thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-b border-stone-100">
                  <td className="py-2">{h.date}</td>
                  <td className="font-bold">{h.karne?.grade}</td>
                  <td>%{h.karne?.occ}</td>
                  <td className="text-xs text-stone-400">{h.sent_to?.join(", ")}</td>
                  <td className="text-xs">{h.forced ? "manuel" : "otomatik"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
