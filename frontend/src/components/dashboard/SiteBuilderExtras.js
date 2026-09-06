import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { ArrowUp, ArrowDown, Plus, Trash, Eye, EyeSlash } from "@phosphor-icons/react";
import { BLOCK_LABELS, SITE_PAGES } from "../../site/siteThemes";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const DEFAULT_ORDER = ["hero", "availability", "about", "rooms", "amenities", "gallery", "reviews", "map", "faq", "contact"];

export function normalizeBlocks(blocks) {
  const list = Array.isArray(blocks) ? blocks.filter((b) => BLOCK_LABELS[b.id]) : [];
  const seen = new Set(list.map((b) => b.id));
  return [...list, ...DEFAULT_ORDER.filter((id) => !seen.has(id)).map((id) => ({ id, enabled: true }))];
}

export function BlocksEditor({ blocks, onChange, pagesEnabled, onPagesChange }) {
  const list = normalizeBlocks(blocks);
  const move = (i, d) => { const n = [...list]; const j = i + d; if (j < 0 || j >= n.length) return; [n[i], n[j]] = [n[j], n[i]]; onChange(n); };
  const toggle = (i) => onChange(list.map((b, k) => (k === i ? { ...b, enabled: !b.enabled } : b)));
  const pages = pagesEnabled?.length ? pagesEnabled : SITE_PAGES.map((p) => p.id);
  return (
    <div className="rounded-xl border border-stone-200 p-3" data-testid="site-blocks-card">
      <div className="text-[10px] font-bold uppercase text-stone-500 mb-2">Sayfalar</div>
      <div className="flex flex-wrap gap-1.5 mb-3">
        {SITE_PAGES.map((p) => {
          const on = pages.includes(p.id);
          return (
            <button key={p.id} disabled={p.id === "home"} onClick={() => onPagesChange(on ? pages.filter((x) => x !== p.id) : [...pages, p.id])} data-testid={`site-page-toggle-${p.id}`}
              className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${on ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-stone-500 border-stone-200"} disabled:opacity-60`}>
              {p.label}
            </button>
          );
        })}
      </div>
      <div className="text-[10px] font-bold uppercase text-stone-500 mb-2">Ana sayfa blok sırası</div>
      <div className="space-y-1">
        {list.map((b, i) => (
          <div key={b.id} className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs ${b.enabled ? "bg-stone-50" : "bg-stone-50/50 text-stone-400"}`} data-testid={`site-block-${b.id}`}>
            <span className="w-4 text-[10px] text-stone-400">{i + 1}</span>
            <span className="flex-1 font-medium">{BLOCK_LABELS[b.id]}</span>
            <button onClick={() => move(i, -1)} className="p-1 hover:bg-stone-200 rounded" data-testid={`site-block-up-${b.id}`}><ArrowUp size={12} /></button>
            <button onClick={() => move(i, 1)} className="p-1 hover:bg-stone-200 rounded" data-testid={`site-block-down-${b.id}`}><ArrowDown size={12} /></button>
            <button onClick={() => toggle(i)} className="p-1 hover:bg-stone-200 rounded" data-testid={`site-block-toggle-${b.id}`}>{b.enabled ? <Eye size={12} /> : <EyeSlash size={12} />}</button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FaqEditor({ faqs, onChange }) {
  const list = faqs || [];
  const set = (i, k, v) => onChange(list.map((f, j) => (j === i ? { ...f, [k]: v } : f)));
  return (
    <div className="rounded-xl border border-stone-200 p-3" data-testid="site-faq-card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold uppercase text-stone-500">SSS ({list.length})</span>
        <button onClick={() => onChange([...list, { q: "", a: "" }])} className="text-[10px] font-bold px-2 py-1 rounded bg-stone-100 hover:bg-stone-200 inline-flex items-center gap-1" data-testid="site-faq-add"><Plus size={10} /> Soru Ekle</button>
      </div>
      <div className="space-y-2">
        {list.map((f, i) => (
          <div key={i} className="flex gap-2">
            <div className="flex-1 space-y-1">
              <input value={f.q} onChange={(e) => set(i, "q", e.target.value)} placeholder="Soru (örn. Check-in saati kaç?)" className="w-full rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs" data-testid={`site-faq-q-${i}`} />
              <textarea value={f.a} onChange={(e) => set(i, "a", e.target.value)} rows={2} placeholder="Cevap" className="w-full rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs" data-testid={`site-faq-a-${i}`} />
            </div>
            <button onClick={() => onChange(list.filter((_, j) => j !== i))} className="p-1.5 text-stone-400 hover:text-red-600 self-start" data-testid={`site-faq-del-${i}`}><Trash size={13} /></button>
          </div>
        ))}
        {list.length === 0 && <p className="text-[10px] text-stone-400">Henüz soru yok. Google'da "Sık Sorulan Sorular" zengin sonucu için 3-6 soru ekleyin.</p>}
      </div>
    </div>
  );
}

export function InquiriesCard({ pid }) {
  const [items, setItems] = useState([]);
  const load = () => axios.get(`${API}/site-builder/${pid}/inquiries`).then(({ data }) => setItems(data.items || [])).catch(() => {});
  useEffect(() => { load(); }, [pid]); // eslint-disable-line react-hooks/exhaustive-deps
  const setStatus = async (id, status) => {
    try { await axios.put(`${API}/site-builder/${pid}/inquiries/${id}`, { status }); load(); } catch { toast.error("Güncellenemedi"); }
  };
  return (
    <div className="rounded-xl border border-stone-200 p-3" data-testid="site-inquiries-card">
      <div className="text-[10px] font-bold uppercase text-stone-500 mb-2">Web Sitesi Mesajları ({items.filter((i) => i.status === "new").length} yeni)</div>
      {items.length === 0 && <p className="text-[10px] text-stone-400">Henüz mesaj yok.</p>}
      <div className="space-y-2 max-h-72 overflow-y-auto">
        {items.map((m) => (
          <div key={m.id} className={`rounded-lg border p-2.5 text-xs ${m.status === "new" ? "border-indigo-200 bg-indigo-50/40" : "border-stone-100"}`} data-testid={`site-inquiry-${m.id}`}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-bold text-stone-800">{m.name} <span className="font-normal text-stone-500">· {m.email}{m.phone ? ` · ${m.phone}` : ""}</span></span>
              <span className="text-[9px] text-stone-400">{new Date(m.created_at).toLocaleString("tr-TR")}</span>
            </div>
            <p className="mt-1 text-stone-700 whitespace-pre-wrap">{m.message}</p>
            <div className="mt-1.5 flex gap-1.5">
              <a href={`mailto:${m.email}?subject=Re: ${encodeURIComponent(m.message.slice(0, 40))}`} className="text-[10px] font-bold text-indigo-600 hover:underline">Yanıtla</a>
              {m.status !== "replied" && <button onClick={() => setStatus(m.id, "replied")} className="text-[10px] font-bold text-emerald-600 hover:underline" data-testid={`site-inquiry-replied-${m.id}`}>Yanıtlandı</button>}
              {m.status !== "closed" && <button onClick={() => setStatus(m.id, "closed")} className="text-[10px] font-bold text-stone-400 hover:underline">Kapat</button>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


export function TranslationsEditor({ translations, onChange, source, pid }) {
  const [lg, setLg] = useState("en");
  const [busy, setBusy] = useState(false);
  const tr = translations || {};
  const cur = tr[lg] || {};
  const hasSource = !!(source && (source.headline || source.about || source.seo_title || source.seo_description || source.faqs?.length));
  const set = (k, v) => onChange({ ...tr, [lg]: { ...cur, [k]: v } });
  const autoTranslate = async () => {
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/site-builder/${pid}/translate`, { lang: lg, ...(source || {}) });
      onChange({ ...tr, [lg]: { ...cur, ...data.translation, ...(data.faqs?.length ? { faqs: data.faqs } : {}) } });
      toast.success(`${lg.toUpperCase()} çevirisi hazır — düzenleyip kaydedin`);
    } catch (e) { toast.error(e.response?.data?.detail || "Çeviri başarısız"); } finally { setBusy(false); }
  };
  const inp = "w-full rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs";
  return (
    <div className="rounded-xl border border-stone-200 p-3" data-testid="site-translations-card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold uppercase text-stone-500">Çeviriler (site TR + EN/DE, hreflang otomatik)</span>
        <div className="flex gap-1 items-center">{["en", "de"].map((x) => <button key={x} onClick={() => setLg(x)} className={`text-[10px] font-bold px-2 py-0.5 rounded ${lg === x ? "bg-stone-900 text-white" : "bg-stone-100"}`} data-testid={`site-tr-lang-${x}`}>{x.toUpperCase()}{tr[x]?.headline || tr[x]?.about ? " ✓" : ""}</button>)}
          {pid && <button onClick={autoTranslate} disabled={busy || !hasSource} title={hasSource ? "TR içeriği AI ile çevir" : "Önce TR başlık/hakkımızda girin"} className="ml-1 text-[10px] font-bold px-2 py-0.5 rounded bg-indigo-600 text-white disabled:opacity-50" data-testid="site-tr-ai-btn">{busy ? "Çevriliyor…" : hasSource ? "✨ AI ile çevir" : "İçerik yok"}</button>}</div>
      </div>
      <div className="space-y-1.5">
        <input className={inp} placeholder={`Başlık (${lg.toUpperCase()})`} value={cur.headline || ""} onChange={(e) => set("headline", e.target.value)} data-testid="site-tr-headline" />
        <textarea className={inp} rows={3} placeholder={`Hakkımızda (${lg.toUpperCase()})`} value={cur.about || ""} onChange={(e) => set("about", e.target.value)} data-testid="site-tr-about" />
        <input className={inp} placeholder={`SEO başlık (${lg.toUpperCase()})`} value={cur.seo_title || ""} onChange={(e) => set("seo_title", e.target.value)} />
        <input className={inp} placeholder={`SEO açıklama (${lg.toUpperCase()})`} value={cur.seo_description || ""} onChange={(e) => set("seo_description", e.target.value)} />
      </div>
    </div>
  );
}

export function PostsEditor({ posts, onChange }) {
  const list = posts || [];
  const set = (i, k, v) => onChange(list.map((p, j) => (j === i ? { ...p, [k]: v } : p)));
  const inp = "w-full rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs";
  return (
    <div className="rounded-xl border border-stone-200 p-3" data-testid="site-posts-card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold uppercase text-stone-500">Blog & Kampanyalar ({list.length})</span>
        <button onClick={() => onChange([{ title: "", excerpt: "", body: "", type: "campaign", image_url: "", date: new Date().toISOString().slice(0, 10), published: true, cta_url: "" }, ...list])} className="text-[10px] font-bold px-2 py-1 rounded bg-stone-100 hover:bg-stone-200 inline-flex items-center gap-1" data-testid="site-post-add"><Plus size={10} /> Yazı Ekle</button>
      </div>
      <div className="space-y-3 max-h-80 overflow-y-auto">
        {list.map((p, i) => (
          <div key={p.id || i} className="border border-stone-100 rounded-lg p-2 space-y-1.5" data-testid={`site-post-edit-${i}`}>
            <div className="flex gap-1.5">
              <select value={p.type} onChange={(e) => set(i, "type", e.target.value)} className="rounded-lg border border-stone-200 px-2 py-1.5 text-xs"><option value="campaign">Kampanya</option><option value="blog">Blog</option></select>
              <input className={inp} placeholder="Başlık" value={p.title} onChange={(e) => set(i, "title", e.target.value)} data-testid={`site-post-title-${i}`} />
              <input type="date" className="rounded-lg border border-stone-200 px-2 py-1.5 text-xs" value={p.date} onChange={(e) => set(i, "date", e.target.value)} />
              <button onClick={() => onChange(list.filter((_, j) => j !== i))} className="p-1.5 text-stone-400 hover:text-red-600"><Trash size={13} /></button>
            </div>
            <input className={inp} placeholder="Kısa özet (kartta görünür)" value={p.excerpt} onChange={(e) => set(i, "excerpt", e.target.value)} />
            <textarea className={inp} rows={3} placeholder="İçerik" value={p.body} onChange={(e) => set(i, "body", e.target.value)} />
            <div className="flex gap-1.5">
              <input className={inp} placeholder="Görsel URL" value={p.image_url} onChange={(e) => set(i, "image_url", e.target.value)} />
              <input className={inp} placeholder="Kupon kodu (örn. YAZ20)" value={p.promo_code || ""} onChange={(e) => set(i, "promo_code", e.target.value.toUpperCase())} data-testid={`site-post-promo-${i}`} />
              <input className={inp} type="number" placeholder="İndirim %" value={p.discount_pct || ""} onChange={(e) => set(i, "discount_pct", e.target.value)} data-testid={`site-post-pct-${i}`} />
              <label className="text-[10px] flex items-center gap-1 whitespace-nowrap"><input type="checkbox" checked={p.published !== false} onChange={(e) => set(i, "published", e.target.checked)} /> Yayında</label>
            </div>
          </div>
        ))}
        {list.length === 0 && <p className="text-[10px] text-stone-400">Kampanya veya blog yazısı ekleyin — sitede "Blog & Kampanyalar" sayfası otomatik açılır.</p>}
      </div>
    </div>
  );
}

export function AnalyticsBrandEditor({ analytics, brand, onAnalytics, onBrand }) {
  const a = analytics || {}; const b = brand || {};
  const inp = "w-full rounded-lg border border-stone-200 px-2.5 py-1.5 text-xs";
  return (
    <div className="rounded-xl border border-stone-200 p-3 grid md:grid-cols-2 gap-3" data-testid="site-analytics-card">
      <div className="space-y-1.5">
        <div className="text-[10px] font-bold uppercase text-stone-500">Dönüşüm takibi (site + booking engine)</div>
        <input className={inp} placeholder="GA4 Measurement ID (G-XXXXXXX)" value={a.ga4_id || ""} onChange={(e) => onAnalytics({ ...a, ga4_id: e.target.value })} data-testid="site-ga4-input" />
        <input className={inp} placeholder="Google Tag Manager (GTM-XXXXX)" value={a.gtm_id || ""} onChange={(e) => onAnalytics({ ...a, gtm_id: e.target.value })} data-testid="site-gtm-input" />
        <input className={inp} placeholder="Meta Pixel ID" value={a.pixel_id || ""} onChange={(e) => onAnalytics({ ...a, pixel_id: e.target.value })} data-testid="site-pixel-input" />
        <p className="text-[10px] text-stone-400">Olaylar: page_view, begin_checkout, purchase (rezervasyon numarası + tutar). Çerez onayı "sadece zorunlu" ise yüklenmez.</p>
      </div>
      <div className="space-y-1.5">
        <div className="text-[10px] font-bold uppercase text-stone-500">Marka rengi & köşe</div>
        <div className="flex gap-2 items-center">
          <input type="color" value={b.accent || "#0f4c5c"} onChange={(e) => onBrand({ ...b, accent: e.target.value })} className="w-10 h-8 rounded border border-stone-200" data-testid="site-brand-accent" />
          <input className={inp} placeholder="#0f4c5c (boş = tema rengi)" value={b.accent || ""} onChange={(e) => onBrand({ ...b, accent: e.target.value })} />
          <button onClick={() => onBrand({ ...b, accent: "" })} className="text-[10px] font-bold text-stone-500 whitespace-nowrap">Sıfırla</button>
        </div>
        <select value={b.radius || ""} onChange={(e) => onBrand({ ...b, radius: e.target.value })} className={inp} data-testid="site-brand-radius">
          <option value="">Köşe: tema varsayılanı</option><option value="0px">Keskin (0)</option><option value="8px">Hafif (8px)</option><option value="16px">Yuvarlak (16px)</option><option value="24px">Çok yuvarlak (24px)</option>
        </select>
        <p className="text-[10px] text-stone-400">Sitemap: <code>/api/site-builder/public/sitemap/&lt;tesis&gt;.xml</code> · robots: <code>/api/site-builder/public/robots/&lt;tesis&gt;.txt</code></p>
      </div>
    </div>
  );
}
