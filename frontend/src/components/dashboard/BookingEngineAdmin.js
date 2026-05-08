import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/* ─── DRAG & DROP ROOM PHOTO UPLOADER ─── */
const RoomPhotoUploader = ({ roomId, roomName, currentPhoto, gallery, onRefresh }) => {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);
  const galleryRef = useRef(null);

  const uploadMain = async (file) => {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await axios.post(`${API}/booking-widget/room-photo/${roomId}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`Main photo updated for ${roomName}`);
      onRefresh();
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };

  const uploadGallery = async (file) => {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await axios.post(`${API}/booking-widget/room-gallery/${roomId}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Gallery photo added");
      onRefresh();
    } catch { toast.error("Upload failed"); }
    setUploading(false);
  };

  const handleDrop = (e, isGallery) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer?.files;
    if (files?.length > 0) {
      if (isGallery) {
        Array.from(files).forEach(f => uploadGallery(f));
      } else {
        uploadMain(files[0]);
      }
    }
  };

  const handleFileSelect = (e, isGallery) => {
    const files = e.target?.files;
    if (files?.length > 0) {
      if (isGallery) {
        Array.from(files).forEach(f => uploadGallery(f));
      } else {
        uploadMain(files[0]);
      }
    }
    e.target.value = "";
  };

  const photoUrl = (url) => {
    if (!url) return "";
    if (url.startsWith("http")) return url;
    return `${process.env.REACT_APP_BACKEND_URL}${url}`;
  };

  return (
    <div className="border border-stone-200 rounded-2xl p-5 bg-white" data-testid={`room-photo-card-${roomId}`}>
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-xl bg-stone-100 flex items-center justify-center flex-shrink-0">
          <svg className="w-5 h-5 text-stone-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
        </div>
        <div>
          <h3 className="font-semibold text-stone-800">{roomName}</h3>
          <p className="text-xs text-stone-400">ID: {roomId}</p>
        </div>
      </div>

      {/* Main Photo */}
      <div className="mb-4">
        <label className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2 block">Main Photo</label>
        <div
          className={`relative rounded-xl overflow-hidden border-2 border-dashed transition-all cursor-pointer h-48 ${dragOver ? "border-emerald-400 bg-emerald-50" : "border-stone-200 hover:border-stone-300"}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => handleDrop(e, false)}
          onClick={() => fileRef.current?.click()}
          data-testid={`main-photo-dropzone-${roomId}`}
        >
          {currentPhoto ? (
            <div className="w-full h-full">
              <img src={photoUrl(currentPhoto)} alt={roomName} className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-black/0 hover:bg-black/40 transition-colors flex items-center justify-center opacity-0 hover:opacity-100">
                <div className="text-white text-center">
                  <svg className="w-8 h-8 mx-auto mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                  <span className="text-sm font-medium">Replace Photo</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-stone-400">
              <svg className="w-10 h-10 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
              <p className="text-sm font-medium">Drag & drop or click to upload</p>
              <p className="text-xs mt-0.5">JPG, PNG or WebP (max 5MB)</p>
            </div>
          )}
          {uploading && <div className="absolute inset-0 bg-white/80 flex items-center justify-center"><div className="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" /></div>}
        </div>
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={e => handleFileSelect(e, false)} data-testid={`main-photo-input-${roomId}`} />
      </div>

      {/* Gallery Photos */}
      <div>
        <label className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2 block">
          Gallery Photos <span className="text-stone-400 font-normal">({(gallery || []).length} photos)</span>
        </label>
        <div className="grid grid-cols-4 gap-2 mb-2">
          {(gallery || []).map((url, i) => (
            <div key={i} className="h-20 rounded-lg overflow-hidden bg-stone-100 relative group" data-testid={`gallery-thumb-${roomId}-${i}`}>
              <img src={photoUrl(url)} alt="" className="w-full h-full object-cover" />
            </div>
          ))}
          <button
            className="h-20 rounded-lg border-2 border-dashed border-stone-200 flex flex-col items-center justify-center text-stone-400 hover:border-emerald-300 hover:text-emerald-500 transition-colors cursor-pointer"
            onClick={() => galleryRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => handleDrop(e, true)}
            data-testid={`gallery-add-btn-${roomId}`}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
            <span className="text-[10px] mt-0.5">Add</span>
          </button>
        </div>
        <input ref={galleryRef} type="file" accept="image/*" multiple className="hidden" onChange={e => handleFileSelect(e, true)} data-testid={`gallery-input-${roomId}`} />
      </div>
    </div>
  );
};

/* ─── REVIEWS MANAGEMENT ─── */
const ReviewsManager = ({ propertyId }) => {
  const [reviews, setReviews] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ guest_name: "", country: "", rating: 9.0, title: "", comment: "", date: "" });

  const load = useCallback(async () => {
    try { const { data } = await axios.get(`${API}/booking-widget/reviews/${propertyId}`); setReviews(data); } catch { /* silent */ }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    try {
      await axios.post(`${API}/booking-widget/reviews`, { ...form, property_id: propertyId, rating: parseFloat(form.rating) });
      toast.success("Review added"); setShowCreate(false);
      setForm({ guest_name: "", country: "", rating: 9.0, title: "", comment: "", date: "" });
      load();
    } catch { toast.error("Failed"); }
  };

  const del = async (id) => {
    try { await axios.delete(`${API}/booking-widget/reviews/${id}`); toast.success("Deleted"); load(); } catch { toast.error("Failed"); }
  };

  const avg = reviews.length > 0 ? (reviews.reduce((a, r) => a + (r.rating || 0), 0) / reviews.length).toFixed(1) : "0.0";

  return (
    <div data-testid="reviews-manager">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-stone-800">Guest Reviews</h3>
          <p className="text-xs text-stone-500">{reviews.length} reviews &middot; Average: {avg}/10</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="add-review-btn">+ Add Review</button>
      </div>
      {reviews.length === 0 ? (
        <div className="text-center py-8 text-stone-400 text-sm">No reviews yet. Add reviews to show on the booking engine.</div>
      ) : (
        <div className="space-y-2">{reviews.map(r => (
          <div key={r.id} className="flex items-start justify-between border border-stone-200 rounded-xl p-4 bg-white" data-testid={`review-row-${r.id}`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-medium text-stone-800 text-sm">{r.guest_name}</span>
                <span className="text-xs text-stone-400">{r.country}</span>
                <Badge className="text-[10px] bg-emerald-50 text-emerald-700">{r.rating}/10</Badge>
                {r.verified && <Badge className="text-[9px] bg-blue-50 text-blue-600">Verified</Badge>}
              </div>
              <p className="text-sm font-medium text-stone-700">{r.title}</p>
              <p className="text-xs text-stone-500 line-clamp-2">{r.comment}</p>
              <span className="text-[10px] text-stone-400">{r.date}</span>
            </div>
            <button onClick={() => del(r.id)} className="text-xs text-red-500 hover:underline ml-3 flex-shrink-0" data-testid={`delete-review-${r.id}`}>Delete</button>
          </div>
        ))}</div>
      )}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-md" data-testid="review-dialog"><DialogHeader><DialogTitle>Add Guest Review</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <div className="grid grid-cols-2 gap-3">
              <Input value={form.guest_name} onChange={e => setForm({...form, guest_name: e.target.value})} placeholder="Guest name (e.g. Sarah M.)" data-testid="review-name" />
              <Input value={form.country} onChange={e => setForm({...form, country: e.target.value})} placeholder="Country" data-testid="review-country" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-stone-500 mb-1 block">Rating (1-10)</label>
                <Input type="number" min="1" max="10" step="0.1" value={form.rating} onChange={e => setForm({...form, rating: e.target.value})} data-testid="review-rating" /></div>
              <Input value={form.date} onChange={e => setForm({...form, date: e.target.value})} placeholder="Date (e.g. March 2026)" data-testid="review-date" />
            </div>
            <Input value={form.title} onChange={e => setForm({...form, title: e.target.value})} placeholder="Review title" data-testid="review-title" />
            <Textarea value={form.comment} onChange={e => setForm({...form, comment: e.target.value})} placeholder="Guest's comment..." rows={3} data-testid="review-comment" />
            <button onClick={create} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium" data-testid="review-save">Add Review</button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

/* ─── WIDGET THEME CONFIG ─── */
const ThemeConfig = ({ propertyId }) => {
  const [config, setConfig] = useState({ accent_color: "#1a3c5e", hero_image: "", tagline: "Premium Accommodation", subtitle: "" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    axios.get(`${API}/booking-widget/info/${propertyId}`).then(r => {
      const t = r.data.theme || {};
      setConfig({ accent_color: t.accent_color || "#1a3c5e", hero_image: t.hero_image || "", tagline: t.tagline || "", subtitle: t.subtitle || "" });
    }).catch(() => {});
  }, [propertyId]);

  const save = async () => {
    try {
      await axios.put(`${API}/booking-widget/config/${propertyId}`, config);
      toast.success("Theme saved"); setSaved(true); setTimeout(() => setSaved(false), 2000);
    } catch { toast.error("Failed"); }
  };

  return (
    <div data-testid="theme-config">
      <h3 className="text-base font-bold text-stone-800 mb-1">Booking Engine Theme</h3>
      <p className="text-xs text-stone-500 mb-4">Customize the look and feel of your public booking page</p>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-semibold text-stone-500 mb-1 block">Accent Color</label>
            <div className="flex items-center gap-2">
              <input type="color" value={config.accent_color} onChange={e => setConfig({...config, accent_color: e.target.value})} className="w-10 h-10 rounded-lg border-0 cursor-pointer" data-testid="theme-color" />
              <Input value={config.accent_color} onChange={e => setConfig({...config, accent_color: e.target.value})} className="flex-1 h-10 text-sm" data-testid="theme-color-hex" />
              <div className="w-20 h-10 rounded-lg" style={{ backgroundColor: config.accent_color }} />
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-stone-500 mb-1 block">Tagline</label>
            <Input value={config.tagline} onChange={e => setConfig({...config, tagline: e.target.value})} placeholder="Premium Accommodation" className="h-10" data-testid="theme-tagline" />
          </div>
        </div>
        <div>
          <label className="text-xs font-semibold text-stone-500 mb-1 block">Hero Image URL</label>
          <Input value={config.hero_image} onChange={e => setConfig({...config, hero_image: e.target.value})} placeholder="https://images.unsplash.com/..." className="h-10" data-testid="theme-hero" />
          {config.hero_image && <div className="mt-2 h-32 rounded-xl overflow-hidden"><img src={config.hero_image} alt="Hero preview" className="w-full h-full object-cover" /></div>}
        </div>
        <div>
          <label className="text-xs font-semibold text-stone-500 mb-1 block">Subtitle</label>
          <Textarea value={config.subtitle} onChange={e => setConfig({...config, subtitle: e.target.value})} placeholder="Experience exceptional hospitality..." rows={2} data-testid="theme-subtitle" />
        </div>
        <button onClick={save} className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-all ${saved ? "bg-emerald-100 text-emerald-700" : "bg-emerald-600 text-white hover:bg-emerald-700"}`} data-testid="theme-save">
          {saved ? "Saved!" : "Save Theme"}
        </button>
      </div>
    </div>
  );
};

/* ─── MAIN PANEL ─── */
const tabs = [
  { id: "photos", label: "Room Photos" },
  { id: "reviews", label: "Guest Reviews" },
  { id: "theme", label: "Theme & Branding" },
  { id: "embed", label: "Embed Widget" },
];

/* ─── EMBED CODE GENERATOR — copy-paste snippet for the hotel's own website ─── */
const EmbedCodePanel = ({ propertyId }) => {
  const [height, setHeight] = useState(900);
  const [variant, setVariant] = useState("iframe"); // "iframe" | "popup-button"
  const baseUrl = `${window.location.origin}/book/${propertyId}?embed=1`;

  // Two embed flavours so the hotel's web designer can pick the one that fits.
  const iframeSnippet = `<iframe
  src="${baseUrl}"
  width="${width}"
  height="${height}"
  style="border:0; border-radius:12px; box-shadow:0 6px 20px rgba(0,0,0,0.08);"
  loading="lazy"
  title="Book Direct"
  allow="payment"
></iframe>`;

  const popupSnippet = `<button onclick="document.getElementById('hb-book-overlay').style.display='flex'"
        style="background:#1a3c5e;color:#fff;padding:12px 22px;border:0;border-radius:10px;font-weight:700;cursor:pointer">
  Book Direct
</button>
<div id="hb-book-overlay"
     style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:9999;align-items:center;justify-content:center;padding:20px"
     onclick="if(event.target===this)this.style.display='none'">
  <iframe src="${baseUrl}"
          style="width:100%;max-width:1100px;height:90vh;border:0;border-radius:14px;background:#fff"
          allow="payment" title="Book Direct"></iframe>
</div>`;

  const snippet = variant === "iframe" ? iframeSnippet : popupSnippet;

  const copy = () => {
    navigator.clipboard.writeText(snippet);
    toast.success("Embed code copied — paste it into your website's HTML");
  };

  return (
    <div className="space-y-4" data-testid="embed-panel">
      <div className="bg-gradient-to-r from-violet-50 to-indigo-50 border border-violet-200 rounded-xl p-4">
        <h3 className="text-base font-bold text-stone-800 flex items-center gap-2">
          <svg className="w-5 h-5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /></svg>
          Embed on Your Website
        </h3>
        <p className="text-xs text-stone-600 mt-1">
          Paste this snippet into your website's HTML to let guests book directly from your homepage —
          OTA komisyonu kaçırmadan. Ödemeler doğrudan Stripe üzerinden alınır, rezervasyonlar otomatik
          olarak buraya düşer.
        </p>
      </div>

      {/* Variant picker */}
      <div className="grid grid-cols-2 gap-2">
        <button onClick={() => setVariant("iframe")}
          className={`p-3 rounded-xl border-2 text-left transition-all ${variant === "iframe" ? "border-violet-500 bg-violet-50" : "border-stone-200 hover:border-stone-300"}`}
          data-testid="embed-variant-iframe">
          <div className="text-sm font-bold text-stone-900">Inline iframe</div>
          <div className="text-[11px] text-stone-500">Embeds the booking form directly on the page (recommended)</div>
        </button>
        <button onClick={() => setVariant("popup-button")}
          className={`p-3 rounded-xl border-2 text-left transition-all ${variant === "popup-button" ? "border-violet-500 bg-violet-50" : "border-stone-200 hover:border-stone-300"}`}
          data-testid="embed-variant-popup">
          <div className="text-sm font-bold text-stone-900">Popup button</div>
          <div className="text-[11px] text-stone-500">A "Book Direct" button that opens a modal — no scroll-jack</div>
        </button>
      </div>

      {/* Iframe size controls — only shown for inline mode */}
      {variant === "iframe" && (
        <div className="flex flex-wrap gap-3">
          <label className="text-xs">
            <span className="block font-bold text-stone-600 mb-1">Width</span>
            <input value={width} onChange={(e) => setWidth(e.target.value)}
              className="px-3 py-2 bg-white border border-stone-200 rounded-lg text-sm w-32" data-testid="embed-width" />
          </label>
          <label className="text-xs">
            <span className="block font-bold text-stone-600 mb-1">Height (px)</span>
            <input value={height} onChange={(e) => setHeight(e.target.value)} type="number"
              className="px-3 py-2 bg-white border border-stone-200 rounded-lg text-sm w-32" data-testid="embed-height" />
          </label>
        </div>
      )}

      {/* Snippet box */}
      <div className="relative">
        <pre className="bg-stone-950 text-emerald-300 text-xs p-4 rounded-xl overflow-x-auto font-mono leading-relaxed whitespace-pre-wrap break-all"
             data-testid="embed-snippet">{snippet}</pre>
        <button onClick={copy} data-testid="embed-copy"
          className="absolute top-3 right-3 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold rounded-lg shadow-md">
          Copy
        </button>
      </div>

      {/* Live preview */}
      <div>
        <h4 className="text-sm font-bold text-stone-800 mb-2">Live preview</h4>
        <div className="border border-stone-200 rounded-xl overflow-hidden bg-stone-50">
          <iframe
            src={baseUrl}
            title="Booking widget preview"
            className="w-full"
            style={{ height: variant === "iframe" ? `${height}px` : "700px", border: 0 }}
            data-testid="embed-preview-iframe"
          />
        </div>
      </div>
    </div>
  );
};

export const BookingEngineAdmin = ({ properties, activePropertyId }) => {
  const [tab, setTab] = useState("photos");
  const [rooms, setRooms] = useState([]);
  const pid = activePropertyId || "all";

  const loadRooms = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/booking-widget/info/${pid}`);
      setRooms(data.rooms || []);
    } catch { /* silent */ }
  }, [pid]);
  useEffect(() => { loadRooms(); }, [loadRooms]);

  const bookingUrl = `${window.location.origin}/book/${pid}`;

  return (
    <div className="p-5" data-testid="booking-engine-admin">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold text-stone-800">Booking Engine Manager</h2>
          <p className="text-sm text-stone-500">Manage photos, reviews, and theme for your public booking page</p>
        </div>
        <a href={bookingUrl} target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-2 px-4 py-2 bg-stone-800 text-white rounded-lg text-sm font-medium hover:bg-stone-900 transition-colors" data-testid="preview-booking-btn">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
          Preview Booking Page
        </a>
      </div>

      <div className="bg-gradient-to-r from-emerald-50 to-blue-50 border border-emerald-200 rounded-xl p-4 mb-6">
        <div className="flex items-center gap-2 text-sm">
          <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
          <span className="text-stone-600">Your booking page:</span>
          <code className="bg-white px-2 py-1 rounded text-xs font-mono text-emerald-700 border border-emerald-200" data-testid="booking-url">{bookingUrl}</code>
          <button onClick={() => { navigator.clipboard.writeText(bookingUrl); toast.success("URL copied!"); }} className="text-emerald-600 hover:text-emerald-700" data-testid="copy-url-btn">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1 mb-6 overflow-x-auto pb-1 border-b border-stone-200">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all border-b-2 -mb-[1px] ${
              tab === t.id ? "text-emerald-700 border-emerald-500 bg-emerald-50/50" : "text-stone-400 border-transparent hover:text-stone-600"
            }`} data-testid={`bea-tab-${t.id}`}>{t.label}</button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
          {tab === "photos" && (
            <div>
              <div className="mb-4"><h3 className="text-base font-bold text-stone-800">Room Photos</h3><p className="text-xs text-stone-500">Drag & drop or click to upload photos for each room type</p></div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {rooms.map(r => (
                  <RoomPhotoUploader key={r.id} roomId={r.id} roomName={r.name} currentPhoto={r.photo} gallery={r.gallery || []} onRefresh={loadRooms} />
                ))}
              </div>
            </div>
          )}
          {tab === "reviews" && <ReviewsManager propertyId={pid} />}
          {tab === "theme" && <ThemeConfig propertyId={pid} />}
          {tab === "embed" && <EmbedCodePanel propertyId={pid} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
