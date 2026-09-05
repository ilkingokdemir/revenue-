import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Globe, ArrowSquareOut } from "@phosphor-icons/react";
import { TEMPLATES as PRO_TEMPLATES } from "../../templates/templateConfig";
import { BlocksEditor, FaqEditor, InquiriesCard } from "./SiteBuilderExtras";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SiteBuilderPanel({ activePropertyId, properties }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : (properties?.[0]?.id || "default");
  const [templates, setTemplates] = useState([]);
  const [tpl, setTpl] = useState("classic");
  const [published, setPublished] = useState(false);
  const [content, setContent] = useState({ headline: "", about: "", amenities: "", phone: "", email: "", address: "", seo_title: "", seo_description: "" });
  const [photos, setPhotos] = useState([]);
  const [domain, setDomain] = useState("");
  const [domainStatus, setDomainStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [mode, setMode] = useState("simple");
  const [engineTpl, setEngineTpl] = useState("booking-classic");
  const [busy, setBusy] = useState(false);

  const saveDomain = async () => {
    if (!domain.trim()) { toast.error("Alan adı girin"); return; }
    try {
      const { data } = await axios.post(`${API}/site-builder/${pid}/domain`,
        { domain: domain.trim(), expected_target: window.location.host });
      setDomainStatus("pending");
      toast.success(data.dns_instruction);
    } catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };

  const verifyDomain = async () => {
    try {
      const { data } = await axios.post(`${API}/site-builder/${pid}/domain/verify`);
      setDomainStatus(data.status);
      data.status === "verified" ? toast.success(data.note) : toast.warning(data.note);
    } catch (e) { toast.error(e.response?.data?.detail || "Doğrulanamadı"); }
  };

  const removeDomain = async () => {
    try {
      await axios.delete(`${API}/site-builder/${pid}/domain`);
      setDomain(""); setDomainStatus(null);
      toast.success("Alan adı kaldırıldı");
    } catch { toast.error("Kaldırılamadı"); }
  };

  const uploadPhoto = async (kind, file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      await axios.post(`${API}/site-builder/${pid}/photos?kind=${kind}`, fd);
      toast.success(kind === "cover" ? "Kapak fotoğrafı yüklendi" : "Galeriye eklendi");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Yüklenemedi"); }
  };

  const deletePhoto = async (photoId) => {
    try { await axios.delete(`${API}/site-builder/${pid}/photos/${photoId}`); load(); }
    catch { toast.error("Silinemedi"); }
  };

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/site-builder/${pid}`);
      setTemplates(data.templates || []);
      const s = data.site || {};
      setTpl(s.template || "classic");
      setPublished(!!s.published);
      if (s.mode) setMode(s.mode);
      if (s.engine_template) setEngineTpl(s.engine_template);
      setContent({ headline: "", about: "", amenities: "", phone: "", email: "", address: "", seo_title: "", seo_description: "", map_query: "", blocks: [], faqs: [], pages_enabled: [], ...(s.content || {}) });
      setPhotos(data.photos || []);
      if (s.custom_domain) { setDomain(s.custom_domain); setDomainStatus(s.domain_status || "pending"); }
      try {
        const { data: st } = await axios.get(`${API}/site-builder/${pid}/stats`);
        setStats(st);
      } catch { /* silent */ }
    } catch { toast.error("Yüklenemedi"); }
  }, [pid]);

  useEffect(() => { load(); }, [load]);

  const save = async (pub) => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/site-builder/${pid}`, { template: tpl, content, published: pub, mode, engine_template: engineTpl });
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

      {/* Mod seçimi: basit tema vs profesyonel platform şablonları */}
      <div className="flex gap-2 mb-4" data-testid="site-mode-toggle">
        {[["simple", "Tema Siteleri (6) — çok sayfalı"], ["pro", "Profesyonel Şablonlar (10) — Booking.com / Airbnb / Expedia görünümü"]].map(([m, l]) => (
          <button key={m} onClick={() => setMode(m)} data-testid={`site-mode-${m}`}
            className={`px-4 py-2 rounded-full text-[11px] font-bold ${mode === m ? "bg-indigo-600 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"}`}>
            {l}
          </button>
        ))}
      </div>

      {mode === "simple" ? (
      <div className="grid grid-cols-3 gap-3 mb-5" data-testid="site-templates-grid">
        {templates.map((t) => (
          <button key={t.id} onClick={() => setTpl(t.id)} data-testid={`site-tpl-${t.id}`}
            className={`text-left rounded-xl border-2 p-4 ${tpl === t.id ? "border-indigo-600 bg-indigo-50" : "border-stone-200 hover:border-indigo-300"}`}>
            <div className="text-xs font-bold text-stone-800">{t.name}</div>
            <div className="text-[10px] text-stone-500 mt-1">{t.desc}</div>
          </button>
        ))}
      </div>
      ) : (
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-5" data-testid="site-pro-templates">
        {Object.values(PRO_TEMPLATES).map((t) => (
          <div key={t.id} className={`rounded-xl border-2 p-3 ${engineTpl === t.id ? "border-indigo-600 bg-indigo-50" : "border-stone-200 hover:border-indigo-300"}`} data-testid={`site-protpl-${t.id}`}>
            <button onClick={() => setEngineTpl(t.id)} className="text-left w-full">
              <div className="w-full h-2 rounded-full mb-2" style={{ background: t.colors?.primary || "#333" }} />
              <div className="text-[11px] font-bold text-stone-800 truncate">{t.name}</div>
              <div className="text-[9px] font-semibold text-stone-400">{t.platform} tarzı</div>
            </button>
            <a href={`/book?property=${pid}&template=${t.id}`} target="_blank" rel="noreferrer"
              data-testid={`site-protpl-preview-${t.id}`}
              className="inline-block mt-1.5 text-[9px] font-bold text-indigo-600 hover:underline">Önizle ↗</a>
          </div>
        ))}
      </div>
      )}

      {/* Ziyaret istatistikleri */}
      {stats && (
        <div className="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm mb-5" data-testid="site-stats-card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-stone-800">Ziyaret İstatistikleri · son {stats.days} gün</h3>
            <span className="text-[10px] text-stone-400">Dönüşüm = rezervasyon / görüntülenme</span>
          </div>
          <div className="grid grid-cols-5 gap-2 mb-3">
            {[["views", "Görüntülenme"], ["unique_visitors", "Tekil Ziyaretçi"], ["cta_clicks", "Rezervasyon Tıkı"], ["bookings", "Site Rezervasyonu"], ["conversion_pct", "Dönüşüm %"]].map(([k, l]) => (
              <div key={k} className="rounded-xl bg-stone-50 p-3 text-center" data-testid={`site-stat-${k}`}>
                <div className="text-xl font-black text-stone-800">{k === "conversion_pct" ? `%${stats[k]}` : stats[k]}</div>
                <div className="text-[9px] uppercase tracking-wide text-stone-400 mt-0.5">{l}</div>
              </div>
            ))}
          </div>
          {stats.sources && Object.keys(stats.sources).length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3" data-testid="site-stats-sources">
              {Object.entries(stats.sources).sort((a, b) => b[1] - a[1]).map(([s, n]) => {
                const total = Object.values(stats.sources).reduce((x, y) => x + y, 0) || 1;
                const label = { google: "Google", social: "Sosyal Medya", direct: "Direkt", other: "Diğer" }[s] || s;
                const cls = { google: "bg-blue-50 text-blue-700 border-blue-200", social: "bg-pink-50 text-pink-700 border-pink-200", direct: "bg-emerald-50 text-emerald-700 border-emerald-200", other: "bg-stone-50 text-stone-600 border-stone-200" }[s] || "bg-stone-50 text-stone-600 border-stone-200";
                return (
                  <span key={s} data-testid={`site-source-${s}`}
                    className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${cls}`}>
                    {label}: {n} (%{Math.round((n / total) * 100)})
                  </span>
                );
              })}
            </div>
          )}
          {stats.daily?.length > 0 && (
            <div className="flex items-end gap-1 h-14" data-testid="site-stats-chart">
              {stats.daily.map((d) => {
                const max = Math.max(...stats.daily.map((x) => x.views), 1);
                return (
                  <div key={d.date} className="flex-1 bg-indigo-500/80 rounded-t hover:bg-indigo-600"
                    style={{ height: `${Math.max((d.views / max) * 100, 6)}%` }}
                    title={`${d.date}: ${d.views} görüntülenme`} />
                );
              })}
            </div>
          )}
        </div>
      )}

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
        <input value={content.map_query || ""} onChange={(e) => setContent({ ...content, map_query: e.target.value })}
          placeholder="Harita arama metni (boşsa adres kullanılır — örn. 'Aldgate Flats, London')" className={inputCls} data-testid="site-map-query-input" />
        {mode === "simple" && (
          <div className="grid md:grid-cols-2 gap-3 pt-1">
            <BlocksEditor blocks={content.blocks} onChange={(b) => setContent({ ...content, blocks: b })}
              pagesEnabled={content.pages_enabled} onPagesChange={(p) => setContent({ ...content, pages_enabled: p })} />
            <FaqEditor faqs={content.faqs} onChange={(f) => setContent({ ...content, faqs: f })} />
          </div>
        )}

        {/* Fotoğraflar */}
        <div className="grid grid-cols-2 gap-3 pt-1">
          <div className="rounded-xl border border-dashed border-stone-300 p-3">
            <div className="text-[10px] font-bold uppercase text-stone-500 mb-2">Kapak Fotoğrafı (hero)</div>
            {photos.filter((p) => p.kind === "cover").map((p) => (
              <div key={p.id} className="relative inline-block mr-2 mb-2">
                <img src={p.url} alt="kapak" className="h-20 w-32 object-cover rounded-lg" data-testid={`site-photo-${p.id}`} />
                <button onClick={() => deletePhoto(p.id)} data-testid={`site-photo-del-${p.id}`}
                  className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-600 text-white text-[10px] font-bold">×</button>
              </div>
            ))}
            <label className="block">
              <input type="file" accept="image/*" className="hidden" data-testid="site-cover-upload"
                onChange={(e) => { uploadPhoto("cover", e.target.files?.[0]); e.target.value = ""; }} />
              <span className="inline-block cursor-pointer text-[10px] font-bold px-3 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700">+ Kapak Yükle</span>
            </label>
          </div>
          <div className="rounded-xl border border-dashed border-stone-300 p-3">
            <div className="text-[10px] font-bold uppercase text-stone-500 mb-2">Galeri ({photos.filter((p) => p.kind === "gallery").length})</div>
            <div className="flex flex-wrap gap-2 mb-2">
              {photos.filter((p) => p.kind === "gallery").map((p) => (
                <div key={p.id} className="relative">
                  <img src={p.url} alt="galeri" className="h-14 w-20 object-cover rounded-lg" data-testid={`site-photo-${p.id}`} />
                  <button onClick={() => deletePhoto(p.id)} data-testid={`site-photo-del-${p.id}`}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-600 text-white text-[10px] font-bold">×</button>
                </div>
              ))}
            </div>
            <label className="block">
              <input type="file" accept="image/*" className="hidden" data-testid="site-gallery-upload"
                onChange={(e) => { uploadPhoto("gallery", e.target.files?.[0]); e.target.value = ""; }} />
              <span className="inline-block cursor-pointer text-[10px] font-bold px-3 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700">+ Galeriye Ekle</span>
            </label>
          </div>
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

        {/* SEO Ayarları */}
        <div className="rounded-xl border border-stone-200 p-3 mt-2" data-testid="site-seo-card">
          <div className="text-[10px] font-bold uppercase text-stone-500 mb-2">SEO Ayarları</div>
          <div className="space-y-2">
            <div>
              <input value={content.seo_title} onChange={(e) => setContent({ ...content, seo_title: e.target.value })}
                placeholder="SEO başlığı (örn. Otelim — Şehir Merkezinde Butik Otel)" className={inputCls} data-testid="site-seo-title-input" maxLength={70} />
              <div className={`text-[9px] text-right ${content.seo_title.length > 60 ? "text-red-500" : "text-stone-400"}`}>{content.seo_title.length}/60</div>
            </div>
            <div>
              <textarea value={content.seo_description} onChange={(e) => setContent({ ...content, seo_description: e.target.value })}
                rows={2} placeholder="SEO açıklaması — aramada başlığın altında görünen metin" className={inputCls} data-testid="site-seo-desc-input" maxLength={170} />
              <div className={`text-[9px] text-right ${content.seo_description.length > 160 ? "text-red-500" : "text-stone-400"}`}>{content.seo_description.length}/160</div>
            </div>
          </div>
          {/* Google önizlemesi */}
          <div className="mt-2 rounded-lg border border-stone-100 bg-white p-3" data-testid="site-google-preview">
            <div className="text-[9px] font-bold uppercase text-stone-400 mb-1.5">Google Önizlemesi</div>
            <div className="text-[11px] text-emerald-700 truncate">{`${window.location.origin}/site/${pid}`}{domain && domainStatus === "verified" ? ` · ${domain}` : ""}</div>
            <div className="text-[15px] text-[#1a0dab] leading-snug truncate" style={{ fontFamily: "arial, sans-serif" }}>
              {content.seo_title || content.headline || "Otel adınız — başlık buraya"}
            </div>
            <div className="text-[12px] text-stone-600 leading-snug line-clamp-2" style={{ fontFamily: "arial, sans-serif" }}>
              {content.seo_description || content.about || "SEO açıklamanız burada görünecek. 160 karaktere kadar yazın."}
            </div>
          </div>
        </div>

        <InquiriesCard pid={pid} />

        {/* Özel alan adı */}
        <div className="rounded-xl border border-stone-200 p-3 mt-2" data-testid="site-domain-card">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold uppercase text-stone-500">Özel Alan Adı</span>
            {domainStatus && (
              <span data-testid="site-domain-status" className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full ${
                domainStatus === "verified" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                {domainStatus === "verified" ? "Doğrulandı ✓" : "DNS Bekleniyor"}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="otelim.com"
              className={inputCls} data-testid="site-domain-input" />
            <button onClick={saveDomain} data-testid="site-domain-save-btn"
              className="px-3 py-2 rounded-lg bg-stone-900 text-white text-[10px] font-bold hover:bg-stone-700 whitespace-nowrap">Kaydet</button>
            {domainStatus && (
              <>
                <button onClick={verifyDomain} data-testid="site-domain-verify-btn"
                  className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-[10px] font-bold hover:bg-indigo-700 whitespace-nowrap">DNS Doğrula</button>
                <button onClick={removeDomain} data-testid="site-domain-remove-btn"
                  className="px-3 py-2 rounded-lg border border-red-200 text-red-600 text-[10px] font-bold hover:bg-red-50 whitespace-nowrap">Kaldır</button>
              </>
            )}
          </div>
          <p className="text-[10px] text-stone-400 mt-2">
            DNS sağlayıcınızda CNAME kaydı ekleyin: <code className="bg-stone-100 px-1 rounded">{domain || "otelim.com"} → {window.location.host}</code> — yayılım 1-24 saat sürebilir, sonra "DNS Doğrula"ya basın.
          </p>
        </div>
      </div>
    </div>
  );
}
