import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { MagicWand, ArrowsClockwise, Copy, Check, X, EnvelopeSimple, WhatsappLogo } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/gap-filler`;

export default function GapFillerPanel({ propertyId = "all" }) {
  const [data, setData] = useState(null);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${propertyId}`);
      setData(r.data);
    } catch { toast.error("Kampanyalar yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  async function scan() {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/${propertyId}/scan`);
      toast.success(`${r.data.properties_scanned} tesis tarandı · ${r.data.campaigns_created} kampanya taslağı oluşturuldu`);
      load();
    } catch { toast.error("Tarama başarısız"); }
    setScanning(false);
  }

  async function saveCfg(e) {
    e.preventDefault();
    if (propertyId === "all") { toast.error("Ayar için tesis seçin"); return; }
    const f = e.target;
    try {
      await axios.put(`${API}/${propertyId}/config`, {
        occ_threshold: parseInt(f.occ.value, 10), discount_pct: parseInt(f.disc.value, 10),
        days_ahead: parseInt(f.days.value, 10), min_window_days: parseInt(f.win.value, 10),
      });
      toast.success("Ayarlar kaydedildi"); load();
    } catch { toast.error("Kaydedilemedi"); }
  }

  async function act(c, action) {
    try {
      await axios.post(`${API}/campaigns/${c.id}/${action}`);
      toast.success(action === "activate"
        ? "Kampanya aktive edildi — e-posta taslağı Campaigns modülüne eklendi 📣"
        : "Kampanya reddedildi, promo kodu kapatıldı");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "İşlem başarısız"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const { summary: s, config: c } = data;

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="gap-filler-panel">
      <div className="bg-gradient-to-br from-stone-900 via-rose-950 to-orange-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-orange-300">
              <MagicWand size={14} /> AI Gap Filler
            </div>
            <h1 className="text-2xl font-bold mt-1">Boşluk Doldurma Kampanyaları</h1>
            <p className="text-sm text-stone-300 mt-1">Düşük doluluklu tarih pencerelerini bulur, otomatik promo kodu üretir ve hazır e-posta + WhatsApp kampanya taslağı çıkarır.</p>
          </div>
          <button onClick={scan} disabled={scanning} data-testid="gf-scan-btn"
            className="px-4 py-2 bg-orange-400 hover:bg-orange-300 text-stone-900 rounded-lg text-sm font-bold inline-flex items-center gap-2 disabled:opacity-60">
            <ArrowsClockwise size={16} className={scanning ? "animate-spin" : ""} />
            {scanning ? "Taranıyor…" : "Boşlukları Tara"}
          </button>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-5">
          <Stat label="Taslak kampanya" value={s.draft} testid="gf-stat-draft" />
          <Stat label="Aktif kampanya" value={s.activated} testid="gf-stat-active" />
          <Stat label="Kod kullanımı" value={s.redemptions} testid="gf-stat-redemptions" />
        </div>
      </div>

      <form onSubmit={saveCfg} className="bg-white border border-stone-200 rounded-xl p-4 flex items-end gap-4 flex-wrap" data-testid="gf-config-form">
        <label className="text-[10px] uppercase text-stone-400">Doluluk eşiği (%)
          <input name="occ" type="number" min="10" max="80" defaultValue={c.occ_threshold} data-testid="gf-cfg-occ"
            className="block w-20 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
        <label className="text-[10px] uppercase text-stone-400">İndirim (%)
          <input name="disc" type="number" min="5" max="50" defaultValue={c.discount_pct} data-testid="gf-cfg-disc"
            className="block w-20 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
        <label className="text-[10px] uppercase text-stone-400">Ufuk (gün)
          <input name="days" type="number" min="14" max="120" defaultValue={c.days_ahead} data-testid="gf-cfg-days"
            className="block w-20 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
        <label className="text-[10px] uppercase text-stone-400">Min pencere (gün)
          <input name="win" type="number" min="1" max="14" defaultValue={c.min_window_days} data-testid="gf-cfg-win"
            className="block w-20 border border-stone-200 rounded-lg px-2 py-1 text-sm" /></label>
        <button type="submit" className="px-3 py-1.5 bg-stone-900 hover:bg-stone-700 text-white rounded-lg text-xs font-bold" data-testid="gf-cfg-save">Kaydet</button>
        <span className="text-[10px] text-stone-400">Her sabah 06:10'da otomatik tarar</span>
      </form>

      <div className="space-y-3">
        {data.campaigns.map(cp => <CampaignCard key={cp.id} cp={cp} onAct={act} />)}
        {data.campaigns.length === 0 && (
          <div className="bg-white border border-stone-200 rounded-xl px-4 py-12 text-center text-stone-400 text-sm">
            Kampanya taslağı yok. "Boşlukları Tara" ile düşük doluluklu tarihleri analiz edin.
          </div>
        )}
      </div>
    </div>
  );
}

function CampaignCard({ cp, onAct }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState("");
  const copy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopied(key); toast.success("Panoya kopyalandı");
    setTimeout(() => setCopied(""), 1500);
  };
  const badge = cp.status === "activated" ? "bg-emerald-50 text-emerald-700"
    : cp.status === "dismissed" ? "bg-stone-100 text-stone-400" : "bg-amber-50 text-amber-700";
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`gf-campaign-${cp.id}`}>
      <div className="flex items-center gap-3 flex-wrap">
        <div className="min-w-[170px]">
          <div className="font-bold text-stone-800 font-mono text-sm">{cp.start_date} → {cp.end_date}</div>
          <div className="text-[11px] text-stone-400">{cp.days} gün · ort. doluluk %{cp.avg_occ_pct} · {cp.property_id}</div>
        </div>
        <button onClick={() => copy(cp.promo_code, "code")} data-testid={`gf-code-${cp.id}`}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold font-mono hover:bg-rose-100">
          🎟 {cp.promo_code} {copied === "code" ? <Check size={12} /> : <Copy size={12} />}
        </button>
        <span className="text-xs font-bold text-orange-600">−%{cp.discount_pct}</span>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${badge}`}>
          {cp.status === "activated" ? "Aktif" : cp.status === "dismissed" ? "Reddedildi" : "Taslak"}
        </span>
        {cp.promo_used > 0 && <span className="text-[11px] text-emerald-600 font-semibold">{cp.promo_used} kullanım</span>}
        <div className="flex-1" />
        <button onClick={() => setOpen(v => !v)} className="text-xs text-stone-500 hover:text-stone-800 font-semibold" data-testid={`gf-toggle-${cp.id}`}>
          {open ? "Gizle" : "Taslağı Gör"}
        </button>
        {cp.status === "draft" && (
          <>
            <button onClick={() => onAct(cp, "activate")} data-testid={`gf-activate-${cp.id}`}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold">Aktive Et</button>
            <button onClick={() => onAct(cp, "dismiss")} data-testid={`gf-dismiss-${cp.id}`}
              className="p-1.5 text-stone-400 hover:text-rose-600"><X size={15} /></button>
          </>
        )}
      </div>
      {open && (
        <div className="grid md:grid-cols-2 gap-3 mt-3">
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold text-stone-400"><EnvelopeSimple size={12} /> E-posta</span>
              <button onClick={() => copy(`${cp.email_subject}\n\n${cp.email_body}`, "email")} className="text-[10px] text-stone-500 hover:text-stone-800 inline-flex items-center gap-1">
                {copied === "email" ? <Check size={11} /> : <Copy size={11} />} Kopyala
              </button>
            </div>
            <div className="text-xs font-semibold text-stone-700">{cp.email_subject}</div>
            <pre className="text-[11px] text-stone-500 whitespace-pre-wrap mt-1 font-sans">{cp.email_body}</pre>
          </div>
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold text-stone-400"><WhatsappLogo size={12} /> WhatsApp / SMS</span>
              <button onClick={() => copy(cp.wa_message, "wa")} className="text-[10px] text-stone-500 hover:text-stone-800 inline-flex items-center gap-1">
                {copied === "wa" ? <Check size={11} /> : <Copy size={11} />} Kopyala
              </button>
            </div>
            <p className="text-[11px] text-stone-600">{cp.wa_message}</p>
            {cp.status === "activated" && (
              <p className="text-[10px] text-emerald-600 mt-2">✓ E-posta taslağı Campaigns modülünde — segment seçip gönderebilirsiniz.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, testid }) {
  return (
    <div className="bg-white/10 rounded-xl p-3" data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wider text-stone-300">{label}</div>
      <div className="text-xl font-bold mt-0.5">{value}</div>
    </div>
  );
}
