import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Globe, ArrowSquareOut } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SiteBuilderPanel({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [templates, setTemplates] = useState([]);
  const [tpl, setTpl] = useState("classic");
  const [published, setPublished] = useState(false);
  const [content, setContent] = useState({ headline: "", about: "", amenities: "", phone: "", email: "", address: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/site-builder/${pid}`);
      setTemplates(data.templates || []);
      const s = data.site || {};
      setTpl(s.template || "classic");
      setPublished(!!s.published);
      setContent({ headline: "", about: "", amenities: "", phone: "", email: "", address: "", ...(s.content || {}) });
    } catch { toast.error("Yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const save = async (pub) => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/site-builder/${pid}`, { template: tpl, content, published: pub });
      setPublished(pub);
      toast.success(pub ? `Site yayında! ${window.location.origin}/site/${pid}` : "Taslak kaydedildi");
      if (pub) window.open(`/site/${pid}`, "_blank");
      return data;
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
    finally { setBusy(false); }
  };

  const inputCls = "w-full rounded-lg border border-stone-200 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-600";

  return (
    <div className="p-6 max-w-4xl" data-testid="site-builder-panel">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-stone-800">Web Sitesi Oluşturucu</h2>
          <p className="text-xs text-stone-500 mt-1">Şablon seç, içeriği doldur, tek tıkla yayınla — rezervasyon motoru otomatik gömülür.</p>
        </div>
        {published && (
          <a href={`/site/${pid}`} target="_blank" rel="noreferrer" data-testid="site-view-link"
            className="flex items-center gap-1 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg">
            <Globe size={13} weight="bold" /> Yayında — Görüntüle <ArrowSquareOut size={11} />
          </a>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 mb-5">
        {templates.map((t) => (
          <button key={t.id} onClick={() => setTpl(t.id)} data-testid={`site-tpl-${t.id}`}
            className={`text-left rounded-xl border-2 p-4 ${tpl === t.id ? "border-indigo-600 bg-indigo-50" : "border-stone-200 hover:border-indigo-300"}`}>
            <div className="text-xs font-bold text-stone-800">{t.name}</div>
            <div className="text-[10px] text-stone-500 mt-1">{t.desc}</div>
          </button>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm space-y-3">
        <input value={content.headline} onChange={(e) => setContent({ ...content, headline: e.target.value })}
          placeholder="Ana başlık (örn. Şehrin kalbinde butik konfor)" className={inputCls} data-testid="site-headline-input" />
        <textarea value={content.about} onChange={(e) => setContent({ ...content, about: e.target.value })}
          rows={3} placeholder="Hakkımızda metni..." className={inputCls} data-testid="site-about-input" />
        <input value={content.amenities} onChange={(e) => setContent({ ...content, amenities: e.target.value })}
          placeholder="Olanaklar (virgülle: Ücretsiz Wi-Fi, Kahvaltı, Spa)" className={inputCls} data-testid="site-amenities-input" />
        <div className="grid grid-cols-3 gap-2">
          <input value={content.phone} onChange={(e) => setContent({ ...content, phone: e.target.value })} placeholder="Telefon" className={inputCls} data-testid="site-phone-input" />
          <input value={content.email} onChange={(e) => setContent({ ...content, email: e.target.value })} placeholder="E-posta" className={inputCls} data-testid="site-email-input" />
          <input value={content.address} onChange={(e) => setContent({ ...content, address: e.target.value })} placeholder="Adres" className={inputCls} data-testid="site-address-input" />
        </div>
        <div className="flex gap-2 pt-1">
          <button onClick={() => save(false)} disabled={busy} data-testid="site-save-draft-btn"
            className="px-4 py-2 rounded-lg border border-stone-300 text-xs font-bold text-stone-700 hover:bg-stone-50 disabled:opacity-50">
            Taslak Kaydet
          </button>
          <button onClick={() => save(true)} disabled={busy} data-testid="site-publish-btn"
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-xs font-bold hover:opacity-90 disabled:opacity-50">
            {published ? "Güncelle & Yayınla" : "Tek Tıkla Yayınla 🚀"}
          </button>
          {published && (
            <button onClick={() => save(false)} disabled={busy} data-testid="site-unpublish-btn"
              className="px-4 py-2 rounded-lg border border-red-200 text-xs font-bold text-red-600 hover:bg-red-50 disabled:opacity-50">
              Yayından Kaldır
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
