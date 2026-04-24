import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, Search, X, Star, Plus, Trash2, CheckCircle2, MapPin, Building2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TYPE_OPTIONS = [
  { value: "any", label: "Tümü · All" },
  { value: "apartments", label: "Apartman · Apartments" },
  { value: "hotels", label: "Otel · Hotels" },
  { value: "aparthotels", label: "Aparthotel" },
];

/**
 * Admin-facing modal for discovering nearby Booking.com hotels to add as competitors.
 *
 * Flow:
 *   1. Admin opens modal from Market Robot → Competitors tab ("Find Similar" button)
 *   2. Inherits property's postcode/city/currency — editable before search
 *   3. Hits POST /competitors/discover → renders 20-50 candidate cards
 *   4. Admin reviews: checkbox to pick, Trash icon to remove the candidate entirely from list
 *      (unlimited removals — admin's curated list), + manually add custom candidates
 *   5. "Add N Selected" → POST /competitors/bulk-add → toast + close
 *
 * Props:
 *   - propertyId: string (required)
 *   - open: boolean
 *   - onClose: () => void
 *   - onAdded: () => void  (parent refetches its competitor list)
 */
export default function DiscoverCompetitorsModal({ propertyId, open, onClose, onAdded }) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [candidates, setCandidates] = useState([]);     // result list shown to admin
  const [selected, setSelected] = useState({});          // { [booking_url]: true }
  const [searchUsed, setSearchUsed] = useState(null);
  const [postcode, setPostcode] = useState("");
  const [city, setCity] = useState("");
  const [propertyType, setPropertyType] = useState("any");
  const [maxResults, setMaxResults] = useState(20);
  // Manual-add row — admin can type a Booking.com URL and hit "+ Add Manual"
  const [manualName, setManualName] = useState("");
  const [manualUrl, setManualUrl] = useState("");

  // Pre-fill postcode/city from property when modal opens.
  useEffect(() => {
    if (!open || !propertyId) return;
    (async () => {
      try {
        const { data } = await axios.get(`${API}/revenue/market-robot/${propertyId}/our-booking`);
        setPostcode(data?.postcode || "");
        setCity(data?.city || "");
      } catch { /* noop */ }
    })();
    // Reset any prior discovery when re-opening
    setCandidates([]);
    setSelected({});
    setSearchUsed(null);
    setManualName("");
    setManualUrl("");
  }, [open, propertyId]);

  const runDiscover = useCallback(async () => {
    if (!postcode && !city) {
      toast.error("Postcode veya şehir gerekli");
      return;
    }
    setLoading(true);
    try {
      const { data } = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/competitors/discover`,
        { postcode, city, property_type: propertyType, max_results: Number(maxResults) },
      );
      const cands = data?.candidates || [];
      setCandidates(cands);
      setSearchUsed(data?.search_used || null);
      // Auto-select only the hotels that aren't already added and aren't "self"
      const picks = {};
      cands.forEach(c => {
        if (!c.already_added && !c.is_self) picks[c.booking_url] = true;
      });
      setSelected(picks);
      if (cands.length === 0) {
        toast.warning("Hiç aday bulunamadı — postcode/filtre ile deneyin");
      } else {
        toast.success(`${cands.length} aday bulundu · ${Object.keys(picks).length} otomatik seçildi`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Discovery failed");
    }
    setLoading(false);
  }, [propertyId, postcode, city, propertyType, maxResults]);

  const toggle = (url) => setSelected(p => ({ ...p, [url]: !p[url] }));

  // Remove a candidate from the list entirely (unlimited).
  const removeCandidate = (url) => {
    setCandidates(prev => prev.filter(c => c.booking_url !== url));
    setSelected(prev => { const n = { ...prev }; delete n[url]; return n; });
  };

  // Bulk select/deselect all eligible candidates.
  const selectAll = () => {
    const picks = {};
    candidates.forEach(c => { if (!c.already_added && !c.is_self) picks[c.booking_url] = true; });
    setSelected(picks);
  };
  const clearAll = () => setSelected({});

  // Manual add — admin types a custom Booking.com URL (supports unlimited additions).
  const addManual = () => {
    const name = manualName.trim();
    const url = manualUrl.trim();
    if (!name || !url) { toast.error("Name ve URL gerekli"); return; }
    if (!url.includes("booking.com/hotel/")) { toast.error("Geçerli bir Booking.com URL girin"); return; }
    if (candidates.some(c => c.booking_url === url)) { toast.error("Bu URL zaten listede"); return; }
    const slugM = url.match(/\/hotel\/[a-z]{2}\/([a-z0-9-]+)\./i);
    const newCand = {
      hotel_id: null,
      name, booking_url: url,
      slug: slugM ? slugM[1] : name.toLowerCase().replace(/\s+/g, "-"),
      stars: null, review_score: null,
      address: "Manuel eklendi · manually added",
      property_type: "",
      already_added: false, is_self: false,
    };
    setCandidates(prev => [newCand, ...prev]);
    setSelected(prev => ({ ...prev, [url]: true }));
    setManualName(""); setManualUrl("");
    toast.success("Aday listesine eklendi");
  };

  const commit = async () => {
    const picks = candidates.filter(c => selected[c.booking_url] && !c.already_added && !c.is_self);
    if (picks.length === 0) { toast.error("En az bir rakip seç"); return; }
    setSaving(true);
    try {
      const { data } = await axios.post(
        `${API}/revenue/market-robot/${propertyId}/competitors/bulk-add`,
        { candidates: picks.map(p => ({
            name: p.name, booking_url: p.booking_url,
            booking_hotel_id: p.hotel_id,
            stars: p.stars, review_score: p.review_score,
          })) },
      );
      toast.success(data.message || `${data.added} rakip eklendi`);
      onAdded?.();
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Toplu ekleme başarısız");
    }
    setSaving(false);
  };

  if (!open) return null;

  const selectedCount = candidates.filter(c => selected[c.booking_url] && !c.already_added && !c.is_self).length;

  return (
    <div className="fixed inset-0 z-[80] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
         onClick={onClose} data-testid="discover-modal-backdrop">
      <div className="bg-stone-950 border border-stone-800 rounded-2xl shadow-2xl w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden"
           onClick={(e) => e.stopPropagation()} data-testid="discover-modal">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 p-5 border-b border-stone-800 bg-gradient-to-r from-indigo-500/10 via-violet-500/10 to-stone-950">
          <div>
            <h3 className="text-lg font-black text-stone-100 flex items-center gap-2">
              <Search className="w-5 h-5 text-indigo-400" />
              Rakip Ara · Find Similar Competitors
            </h3>
            <p className="text-[11px] text-stone-400 mt-1">
              Postcode + oda tipine göre yakın Booking.com otellerini tara. Admin istediklerini seç, istemediklerini listeden çıkar, isterse manuel ekle.
            </p>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-white" data-testid="discover-close">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search controls */}
        <div className="p-5 border-b border-stone-800 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
            <input value={postcode} onChange={(e) => setPostcode(e.target.value)}
                   placeholder="Postcode · örn. E1 7TD"
                   data-testid="discover-postcode"
                   className="md:col-span-1 px-3 py-2 bg-stone-900 border border-stone-800 rounded-lg text-sm text-stone-100 placeholder:text-stone-500" />
            <input value={city} onChange={(e) => setCity(e.target.value)}
                   placeholder="City · örn. London"
                   data-testid="discover-city"
                   className="md:col-span-1 px-3 py-2 bg-stone-900 border border-stone-800 rounded-lg text-sm text-stone-100 placeholder:text-stone-500" />
            <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}
                    data-testid="discover-type"
                    className="md:col-span-1 px-3 py-2 bg-stone-900 border border-stone-800 rounded-lg text-sm text-stone-100">
              {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <select value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))}
                    data-testid="discover-max"
                    className="md:col-span-1 px-3 py-2 bg-stone-900 border border-stone-800 rounded-lg text-sm text-stone-100">
              {[10, 15, 20, 30, 40, 50].map(n => <option key={n} value={n}>{n} aday · results</option>)}
            </select>
            <button onClick={runDiscover} disabled={loading}
                    data-testid="discover-run"
                    className="md:col-span-1 flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm rounded-lg disabled:opacity-60">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              {loading ? "Taranıyor…" : "Tara · Discover"}
            </button>
          </div>
          {searchUsed && (
            <p className="text-[10px] text-stone-500 italic">
              Kullanılan sorgu: {searchUsed.postcode || "—"} · {searchUsed.city || "—"} · {searchUsed.property_type} · {searchUsed.currency}
            </p>
          )}
        </div>

        {/* Candidate list */}
        <div className="flex-1 overflow-y-auto p-5">
          {candidates.length === 0 && !loading && (
            <div className="text-center text-stone-500 py-10 text-sm">
              Henüz arama yapılmadı — yukarıdan postcode/filtre girip <b>Tara</b>'ya basın.
            </div>
          )}

          {candidates.length > 0 && (
            <>
              {/* Bulk controls */}
              <div className="flex items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="font-bold text-stone-200 tabular-nums">{candidates.length}</span>
                  <span className="text-stone-500">aday · admin'in listesi</span>
                  <span className="mx-2 text-stone-700">|</span>
                  <span className="font-bold text-indigo-300 tabular-nums">{selectedCount}</span>
                  <span className="text-stone-500">seçili</span>
                </div>
                <div className="flex items-center gap-1 text-[11px]">
                  <button onClick={selectAll} data-testid="discover-select-all"
                          className="px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 font-bold">Tümünü seç</button>
                  <button onClick={clearAll} data-testid="discover-clear-all"
                          className="px-2.5 py-1 rounded-lg bg-stone-800 text-stone-300 hover:bg-stone-700 font-bold">Temizle</button>
                </div>
              </div>

              {/* Manual add row */}
              <div className="flex flex-wrap items-center gap-2 mb-3 p-2 rounded-lg bg-violet-500/5 border border-violet-500/20">
                <span className="text-[10px] font-bold text-violet-300 flex-shrink-0 flex items-center gap-1">
                  <Plus className="w-3 h-3" /> Manuel ekle:
                </span>
                <input value={manualName} onChange={e => setManualName(e.target.value)}
                       placeholder="Hotel name"
                       className="flex-1 min-w-[120px] px-2 py-1 bg-stone-900 border border-stone-800 rounded text-[11px] text-stone-100" />
                <input value={manualUrl} onChange={e => setManualUrl(e.target.value)}
                       placeholder="https://www.booking.com/hotel/..."
                       className="flex-[2] min-w-[200px] px-2 py-1 bg-stone-900 border border-stone-800 rounded text-[11px] text-stone-100" />
                <button onClick={addManual} data-testid="discover-add-manual"
                        className="px-2.5 py-1 rounded bg-violet-500/25 text-violet-200 hover:bg-violet-500/40 text-[11px] font-bold">
                  Add
                </button>
              </div>

              {/* Cards list */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {candidates.map((c) => {
                  const isSelected = !!selected[c.booking_url];
                  const disabled = c.already_added || c.is_self;
                  return (
                    <div key={c.booking_url}
                         data-testid={`discover-card-${c.slug || c.hotel_id || "x"}`}
                         className={`relative rounded-xl border p-3 transition-all ${
                           disabled
                             ? "bg-stone-900/30 border-stone-800 opacity-50"
                             : isSelected
                             ? "bg-indigo-500/10 border-indigo-500/40 ring-1 ring-indigo-500/30"
                             : "bg-stone-900/60 border-stone-800 hover:border-stone-600"
                         }`}>
                      <div className="flex items-start gap-3">
                        <input type="checkbox"
                               checked={isSelected && !disabled}
                               disabled={disabled}
                               onChange={() => toggle(c.booking_url)}
                               className="mt-1 w-4 h-4 rounded accent-indigo-500 flex-shrink-0 cursor-pointer disabled:cursor-not-allowed"
                               data-testid={`discover-check-${c.slug || c.hotel_id || "x"}`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2 mb-1">
                            <h4 className="text-sm font-black text-stone-100 truncate" title={c.name}>
                              {c.name}
                              {c.is_self && <span className="ml-2 text-[9px] font-bold text-amber-300 bg-amber-500/15 border border-amber-500/30 rounded-full px-1.5 py-0.5">Bu siz</span>}
                              {c.already_added && <span className="ml-2 text-[9px] font-bold text-emerald-300 bg-emerald-500/15 border border-emerald-500/30 rounded-full px-1.5 py-0.5"><CheckCircle2 className="inline w-2.5 h-2.5 mr-0.5" />Eklendi</span>}
                            </h4>
                            {!disabled && (
                              <button onClick={() => removeCandidate(c.booking_url)}
                                      data-testid={`discover-remove-${c.slug || c.hotel_id || "x"}`}
                                      title="Listeden çıkar"
                                      className="text-stone-500 hover:text-rose-400 p-0.5 rounded">
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-stone-400">
                            {c.stars && (
                              <span className="flex items-center gap-0.5 text-amber-300 font-bold">
                                {Array.from({ length: c.stars }).map((_, i) => <Star key={i} className="w-2.5 h-2.5 fill-current" />)}
                              </span>
                            )}
                            {c.review_score != null && (
                              <span className="px-1.5 py-0.5 bg-emerald-500/15 text-emerald-300 rounded font-bold tabular-nums">
                                {c.review_score.toFixed(1)}
                              </span>
                            )}
                            {c.property_type && (
                              <span className="flex items-center gap-1 text-stone-400"><Building2 className="w-2.5 h-2.5" />{c.property_type}</span>
                            )}
                            {c.address && (
                              <span className="flex items-center gap-1 text-stone-500 truncate max-w-[200px]" title={c.address}>
                                <MapPin className="w-2.5 h-2.5" />{c.address}
                              </span>
                            )}
                          </div>
                          <a href={c.booking_url} target="_blank" rel="noreferrer"
                             className="text-[9px] text-indigo-400 hover:text-indigo-300 truncate block mt-1"
                             onClick={(e) => e.stopPropagation()}>
                            {c.booking_url}
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2 p-5 border-t border-stone-800 bg-stone-950">
          <div className="text-[11px] text-stone-500">
            {selectedCount > 0 ? (
              <>Seçili: <b className="text-indigo-300 tabular-nums">{selectedCount}</b> rakip eklenecek</>
            ) : (
              <>En az bir rakip seç veya modal'ı kapat</>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} data-testid="discover-cancel"
                    className="px-4 py-2 bg-stone-800 hover:bg-stone-700 text-stone-300 rounded-lg text-sm font-bold">
              İptal
            </button>
            <button onClick={commit} disabled={saving || selectedCount === 0}
                    data-testid="discover-commit"
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:brightness-110 text-white rounded-lg text-sm font-black disabled:opacity-50">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              {saving ? "Ekleniyor…" : `${selectedCount} Rakibi Ekle`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
