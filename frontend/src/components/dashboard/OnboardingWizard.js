import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Building2, BedDouble, Tags, Receipt, CheckCircle2, Circle, Plus, Trash2,
  Sparkles, ArrowRight, ArrowLeft, PartyPopper, Loader2, MapPin, Banknote,
  Radar, Zap, RefreshCw, Mail, BellOff,
} from "lucide-react";
import { getCurrencyInfo } from "../../lib/currency";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STEP_META = [
  { id: "property", label: "Your Property", icon: Building2, tint: "fuchsia" },
  { id: "rooms", label: "Room Types", icon: BedDouble, tint: "sky" },
  { id: "rates", label: "Rate Plans", icon: Tags, tint: "emerald" },
  { id: "tax", label: "Tax Profile", icon: Receipt, tint: "amber" },
  { id: "sample", label: "Sample Booking", icon: Sparkles, tint: "violet" },
];

const TINT_CLASSES = {
  fuchsia: { bg: "from-fuchsia-500 to-pink-600", ring: "ring-fuchsia-400/50", soft: "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200" },
  sky: { bg: "from-sky-500 to-blue-600", ring: "ring-sky-400/50", soft: "bg-sky-50 text-sky-700 border-sky-200" },
  emerald: { bg: "from-emerald-500 to-teal-600", ring: "ring-emerald-400/50", soft: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  amber: { bg: "from-amber-500 to-orange-600", ring: "ring-amber-400/50", soft: "bg-amber-50 text-amber-700 border-amber-200" },
  violet: { bg: "from-violet-500 to-purple-600", ring: "ring-violet-400/50", soft: "bg-violet-50 text-violet-700 border-violet-200" },
};

export const OnboardingWizard = ({ propertyId = "default", onClose, onNavigate }) => {
  const [status, setStatus] = useState(null);
  const [idx, setIdx] = useState(0);
  const [saving, setSaving] = useState(false);
  const [finished, setFinished] = useState(false);
  const [quickLoading, setQuickLoading] = useState(false);

  const [property, setProperty] = useState({ name: "", city: "", country: "United Kingdom", currency: "GBP" });
  const [rooms, setRooms] = useState([{ name: "Standard Double", max_guests: 2, bed_type: "double", base_price: 120, total_rooms: 10 }]);
  const [rates, setRates] = useState({ bar: true, nr: true });
  const [tax, setTax] = useState({ name: "Default VAT Profile", vat_pct: 20, city_tax: 0 });
  const [sample, setSample] = useState({ guest_name: "Demo Guest", guest_email: "demo@hotel.example", nights: 2, room_type_id: "" });
  const [roomTypes, setRoomTypes] = useState([]);

  const current = STEP_META[idx];
  const tint = TINT_CLASSES[current.tint];

  const loadStatus = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/property-onboarding/status/${propertyId}`);
      setStatus(data);
      if (data.completed_at) setFinished(true);

      // Load property name as starting value
      try {
        const { data: props } = await axios.get(`${API}/properties`);
        const me = (props || []).find(p => p.id === propertyId);
        if (me) setProperty(p => ({ ...p, name: me.name || "", city: me.city || "", country: me.country || p.country, currency: me.currency || p.currency }));
      } catch { /* silent */ }

      // Room types
      try {
        const { data: rt } = await axios.get(`${API}/room-types?property_id=${propertyId}`);
        setRoomTypes(rt || []);
        if (rt?.length && !sample.room_type_id) {
          setSample(s => ({ ...s, room_type_id: rt[0].id }));
        }
      } catch { /* silent */ }
    } catch (e) {
      toast.error("Could not load onboarding status");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const markStep = async (step) => {
    try {
      await axios.post(`${API}/property-onboarding/step-complete/${propertyId}/${step}`);
    } catch { /* non-fatal */ }
  };

  // ---- Step handlers ----
  const saveProperty = async () => {
    if (!property.name) return toast.error("Property name is required");
    setSaving(true);
    try {
      await axios.put(`${API}/properties/${propertyId}`, {
        name: property.name, city: property.city, country: property.country,
      });
      await axios.put(`${API}/currency-fx/properties/${propertyId}`, { currency: property.currency });
      await markStep("property");
      toast.success("Property saved");
      setIdx(1);
      loadStatus();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to save property");
    } finally { setSaving(false); }
  };

  const saveRooms = async () => {
    const bad = rooms.find(r => !r.name || !r.base_price);
    if (bad) return toast.error("Each room needs a name and base price");
    setSaving(true);
    try {
      for (const r of rooms) {
        await axios.post(`${API}/room-types`, {
          property_id: propertyId,
          name: r.name,
          max_guests: parseInt(r.max_guests) || 2,
          bed_type: r.bed_type,
          base_price: parseFloat(r.base_price) || 0,
          currency: property.currency,
          total_rooms: parseInt(r.total_rooms) || 1,
          breakfast_included: true,
          free_cancellation: true,
        });
      }
      await markStep("rooms");
      toast.success(`Created ${rooms.length} room type${rooms.length === 1 ? "" : "s"}`);
      setIdx(2);
      loadStatus();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to create rooms"); }
    finally { setSaving(false); }
  };

  const saveRates = async () => {
    setSaving(true);
    try {
      if (rates.bar) {
        await axios.post(`${API}/rate-structure/products`, {
          property_id: propertyId, name: "Best Available Rate", code: "BAR",
          kind: "flex", meal_plan: "bed_breakfast", cancellation_policy: "free_24h",
          active: true,
        });
      }
      if (rates.nr) {
        await axios.post(`${API}/rate-structure/products`, {
          property_id: propertyId, name: "Non-Refundable", code: "NR",
          kind: "non_refundable", meal_plan: "room_only", cancellation_policy: "non_refundable",
          cancellation_fee_pct: 100, active: true,
        });
      }
      await markStep("rates");
      toast.success("Rate plans created");
      setIdx(3);
      loadStatus();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to create rates"); }
    finally { setSaving(false); }
  };

  const saveTax = async () => {
    setSaving(true);
    try {
      const rules = [];
      if (tax.vat_pct > 0) {
        rules.push({ kind: "vat", label: `VAT ${tax.vat_pct}%`, basis: "percent", rate: parseFloat(tax.vat_pct), applies_to: ["room", "fnb"], included_in_rate: false });
      }
      if (tax.city_tax > 0) {
        rules.push({ kind: "city_tax", label: `City Tax £${tax.city_tax}/night/guest`, basis: "per_night_per_guest", rate: parseFloat(tax.city_tax), applies_to: ["room"], included_in_rate: false });
      }
      await axios.post(`${API}/tax-config/profiles`, {
        property_id: propertyId, name: tax.name, rules, active: true,
      });
      await markStep("tax");
      toast.success("Tax profile created");
      setIdx(4);
      loadStatus();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to create tax profile"); }
    finally { setSaving(false); }
  };

  const saveSample = async () => {
    const rtId = sample.room_type_id || roomTypes[0]?.id;
    if (!rtId) return toast.error("Create a room type first");
    setSaving(true);
    try {
      const today = new Date();
      const checkIn = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7);
      const checkOut = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 7 + parseInt(sample.nights || 1));
      const iso = (d) => d.toISOString().slice(0, 10);
      await axios.post(`${API}/bookings`, {
        property_id: propertyId,
        room_type_id: rtId,
        guest_name: sample.guest_name,
        guest_email: sample.guest_email,
        guest_phone: "",
        check_in: iso(checkIn),
        check_out: iso(checkOut),
        adults: 2, children: 0, rooms: 1,
      });
      await markStep("sample");
      await axios.post(`${API}/property-onboarding/complete/${propertyId}`);
      setFinished(true);
      toast.success("🎉 Onboarding complete!");
      loadStatus();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to create sample booking"); }
    finally { setSaving(false); }
  };

  const skipStep = async () => {
    await markStep(current.id);
    if (idx < 4) setIdx(idx + 1);
    else {
      await axios.post(`${API}/property-onboarding/complete/${propertyId}`);
      setFinished(true);
    }
    loadStatus();
  };

  const runQuickStart = async () => {
    setQuickLoading(true);
    try {
      const { data } = await axios.post(`${API}/property-onboarding/quick-start/${propertyId}`, {
        property_name: property.name || undefined,
        city: property.city || undefined,
        currency: property.currency || undefined,
        base_price: parseFloat(rooms[0]?.base_price) || 120,
        seed_bookings: 15,
      });
      const c = data.created || {};
      toast.success(`Hızlı kurulum tamam! ${c.rooms} oda tipi · ${c.rate_products} rate plan · ${c.bookings} demo rezervasyon oluşturuldu.`);
      setFinished(true);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Hızlı kurulum başarısız");
    } finally { setQuickLoading(false); }
  };

  if (finished) {
    return <FinishedScreen propertyId={propertyId} onClose={onClose} onNavigate={onNavigate} />;
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-5" data-testid="onboarding-wizard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-stone-500">
          <Sparkles className="w-3.5 h-3.5" />First-run setup · ~3 minutes
        </div>
        {onClose && (
          <button onClick={onClose} className="text-xs text-stone-500 hover:text-stone-800">Skip for now →</button>
        )}
      </div>

      {/* Quick Start — one click setup */}
      <div className="bg-stone-900 rounded-2xl p-5 md:p-6 flex flex-col md:flex-row md:items-center gap-4" data-testid="quick-start-card">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-lg flex-shrink-0">
          <Zap className="w-6 h-6 text-white" />
        </div>
        <div className="flex-1">
          <h2 className="text-lg font-black text-white">Hızlı Başlangıç — 30 saniyede kur</h2>
          <p className="text-xs text-stone-400 mt-1">
            Tek tıkla <b className="text-stone-200">3 oda tipi</b>, <b className="text-stone-200">BAR + Non-Refundable rate planları</b>,
            <b className="text-stone-200"> vergi profili</b> ve <b className="text-stone-200">15 demo rezervasyon</b> oluşturulur.
            Panele boş değil, canlı verilerle girersiniz. Demo verileri tek tıkla silinebilir.
          </p>
        </div>
        <button onClick={runQuickStart} disabled={quickLoading}
          data-testid="quick-start-btn"
          className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 hover:from-amber-300 hover:to-orange-400 text-white text-sm font-bold shadow-lg disabled:opacity-50 transition-transform hover:-translate-y-0.5 flex-shrink-0">
          {quickLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
          {quickLoading ? "Kuruluyor…" : "Hızlı Kurulum Başlat"}
        </button>
      </div>

      <div className="flex items-center gap-3 text-[10px] font-bold uppercase tracking-wider text-stone-400">
        <div className="flex-1 h-px bg-stone-200" />veya adım adım manuel kurulum<div className="flex-1 h-px bg-stone-200" />
      </div>

      {/* Progress rail */}
      <div className="bg-white border border-stone-200 rounded-2xl p-4">
        <div className="flex items-center justify-between gap-2">
          {STEP_META.map((s, i) => {
            const done = status?.steps?.[s.id];
            const active = i === idx;
            return (
              <button key={s.id} onClick={() => setIdx(i)} data-testid={`onboarding-step-${s.id}`}
                className={`flex-1 flex flex-col items-center gap-1.5 px-2 py-2 rounded-lg transition-all ${
                  active ? `ring-2 ${TINT_CLASSES[s.tint].ring}` : "hover:bg-stone-50"
                }`}>
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${
                  done ? "bg-emerald-500 text-white"
                       : active ? `bg-gradient-to-br ${TINT_CLASSES[s.tint].bg} text-white shadow-lg`
                                : "bg-stone-100 text-stone-400"
                }`}>
                  {done ? <CheckCircle2 className="w-5 h-5" /> : <s.icon className="w-5 h-5" />}
                </div>
                <div className={`text-[10px] font-bold uppercase tracking-wider ${active ? "text-stone-900" : "text-stone-400"}`}>
                  {s.label}
                </div>
              </button>
            );
          })}
        </div>
        <div className="mt-4 h-1.5 w-full bg-stone-100 rounded-full overflow-hidden">
          <div className={`h-full bg-gradient-to-r ${tint.bg} transition-all duration-500`}
               style={{ width: `${((idx + 1) / STEP_META.length) * 100}%` }} />
        </div>
      </div>

      {/* Step body */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 md:p-8">
        {idx === 0 && (
          <StepBody tint={tint} icon={Building2} title="Tell us about your property"
            subtitle="The basics. You can edit any of this later in Settings.">
            <div className="grid grid-cols-2 gap-4">
              <F label="Property Name *">
                <input value={property.name} onChange={e => setProperty({ ...property, name: e.target.value })}
                  data-testid="onb-prop-name"
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" placeholder="The Grand London" />
              </F>
              <F label="Country">
                <input value={property.country} onChange={e => setProperty({ ...property, country: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
              </F>
              <F label={<><MapPin className="inline w-3 h-3" /> City</>}>
                <input value={property.city}
                  data-testid="onb-prop-city"
                  onChange={e => {
                    const city = e.target.value;
                    const info = getCurrencyInfo(city);
                    setProperty(p => ({
                      ...p,
                      city,
                      // Auto-set currency only when a known city is detected
                      currency: info.code !== "GBP" || /london|manchester|edinburgh|uk|united kingdom|england/i.test(city)
                        ? info.code
                        : p.currency,
                    }));
                  }}
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" placeholder="London, Zurich, Istanbul, Tokyo..." />
                {property.city && (
                  <div className="mt-1.5 text-[10px] text-stone-500 flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3 text-fuchsia-500" />
                    Auto-detected: <b className="text-stone-900">{getCurrencyInfo(property.city).code}</b>
                    <span className="text-stone-400">({getCurrencyInfo(property.city).symbol.trim() || "—"})</span>
                  </div>
                )}
              </F>
              <F label={<><Banknote className="inline w-3 h-3" /> Primary Currency</>}>
                <select value={property.currency} onChange={e => setProperty({ ...property, currency: e.target.value })}
                  data-testid="onb-prop-currency"
                  className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                  {["GBP", "USD", "EUR", "CHF", "TRY", "AED", "JPY", "CAD", "AUD", "SEK", "NOK", "DKK", "PLN"].map(c => <option key={c}>{c}</option>)}
                </select>
              </F>
            </div>
          </StepBody>
        )}

        {idx === 1 && (
          <StepBody tint={tint} icon={BedDouble} title="Add your room types"
            subtitle={`We'll create these in your inventory with full calendar availability. Use ${property.currency} pricing.`}>
            <div className="space-y-2">
              {rooms.map((r, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-center p-3 bg-stone-50 border border-stone-200 rounded-xl">
                  <input value={r.name} onChange={e => { const n = [...rooms]; n[i] = { ...r, name: e.target.value }; setRooms(n); }}
                    placeholder="Room name" className="col-span-4 w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid={`onb-room-name-${i}`} />
                  <select value={r.bed_type} onChange={e => { const n = [...rooms]; n[i] = { ...r, bed_type: e.target.value }; setRooms(n); }}
                    className="col-span-2 w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                    <option value="single">Single</option>
                    <option value="double">Double</option>
                    <option value="twin">Twin</option>
                    <option value="king">King</option>
                    <option value="suite">Suite</option>
                  </select>
                  <input type="number" value={r.max_guests} onChange={e => { const n = [...rooms]; n[i] = { ...r, max_guests: e.target.value }; setRooms(n); }}
                    placeholder="Max" className="col-span-1 w-full border border-stone-200 rounded-lg px-2 py-2 text-sm" />
                  <input type="number" value={r.base_price} onChange={e => { const n = [...rooms]; n[i] = { ...r, base_price: e.target.value }; setRooms(n); }}
                    placeholder="Price" className="col-span-2 w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid={`onb-room-price-${i}`} />
                  <input type="number" value={r.total_rooms} onChange={e => { const n = [...rooms]; n[i] = { ...r, total_rooms: e.target.value }; setRooms(n); }}
                    placeholder="Qty" className="col-span-2 w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
                  <button onClick={() => setRooms(rooms.filter((_, j) => j !== i))}
                    disabled={rooms.length === 1}
                    className="col-span-1 p-1 text-rose-500 hover:bg-rose-50 rounded disabled:opacity-30 flex justify-center">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button onClick={() => setRooms([...rooms, { name: "", max_guests: 2, bed_type: "double", base_price: 100, total_rooms: 1 }])}
                data-testid="onb-room-add"
                className="w-full p-3 border-2 border-dashed border-stone-200 hover:border-stone-400 rounded-xl text-sm font-semibold text-stone-500 flex items-center justify-center gap-1.5">
                <Plus className="w-4 h-4" />Add another room type
              </button>
              <div className="grid grid-cols-5 gap-1 text-[10px] uppercase text-stone-400 font-bold px-3">
                <div className="col-span-4">Name</div><div>Bed</div><div>Max</div><div>Price</div><div>Qty</div>
              </div>
            </div>
          </StepBody>
        )}

        {idx === 2 && (
          <StepBody tint={tint} icon={Tags} title="Set up rate plans"
            subtitle="Pick the products you want to sell. You can add Advance Purchase, Corporate and Packages later.">
            <div className="grid grid-cols-2 gap-3">
              <RatePick label="Best Available Rate (BAR)" desc="Flexible · free cancellation · bed & breakfast" code="BAR"
                checked={rates.bar} onToggle={() => setRates({ ...rates, bar: !rates.bar })} testId="onb-rate-bar" />
              <RatePick label="Non-Refundable" desc="Pre-paid · 10-15% cheaper · no cancellation" code="NR"
                checked={rates.nr} onToggle={() => setRates({ ...rates, nr: !rates.nr })} testId="onb-rate-nr" />
            </div>
          </StepBody>
        )}

        {idx === 3 && (
          <StepBody tint={tint} icon={Receipt} title="Add tax rules"
            subtitle="Default VAT for most countries. Add city tax if you're in a destination that charges per-night tourist tax.">
            <div className="grid grid-cols-2 gap-4">
              <F label="Profile Name">
                <input value={tax.name} onChange={e => setTax({ ...tax, name: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
              </F>
              <F label="VAT % (0 to skip)">
                <input type="number" value={tax.vat_pct} onChange={e => setTax({ ...tax, vat_pct: e.target.value })}
                  data-testid="onb-tax-vat" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" step="0.5" />
              </F>
              <F label="City Tax £/night/guest (0 to skip)">
                <input type="number" value={tax.city_tax} onChange={e => setTax({ ...tax, city_tax: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" step="0.25" />
              </F>
            </div>
            <p className="mt-4 text-xs text-stone-500 bg-stone-50 border border-stone-200 rounded-lg p-3">
              Common defaults — UK VAT 20% · DE VAT 7% · TR VAT 8% · ES VAT 10% · FR VAT 10% · US ~0% (state-specific).
            </p>
          </StepBody>
        )}

        {idx === 4 && (
          <StepBody tint={tint} icon={Sparkles} title="Create a sample booking"
            subtitle="One demo booking so you immediately see the calendar populated. You can delete it after exploring.">
            <div className="grid grid-cols-2 gap-4">
              <F label="Guest Name">
                <input value={sample.guest_name} onChange={e => setSample({ ...sample, guest_name: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" data-testid="onb-sample-guest" />
              </F>
              <F label="Guest Email">
                <input value={sample.guest_email} onChange={e => setSample({ ...sample, guest_email: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
              </F>
              <F label="Room Type">
                <select value={sample.room_type_id} onChange={e => setSample({ ...sample, room_type_id: e.target.value })}
                  data-testid="onb-sample-room" className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm">
                  {roomTypes.length === 0 && <option value="">— Create a room first —</option>}
                  {roomTypes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </F>
              <F label="Number of nights">
                <input type="number" value={sample.nights} onChange={e => setSample({ ...sample, nights: e.target.value })} className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm" />
              </F>
            </div>
            <p className="mt-4 text-xs text-stone-500">
              The booking will arrive <b>7 days from today</b> so it shows up nicely on the calendar without blocking check-in today.
            </p>
          </StepBody>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <button onClick={() => idx > 0 && setIdx(idx - 1)} disabled={idx === 0}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-stone-500 hover:text-stone-900 disabled:opacity-30">
          <ArrowLeft className="w-4 h-4" />Back
        </button>
        <div className="flex gap-2">
          <button onClick={skipStep}
            className="px-4 py-2 text-sm font-semibold text-stone-500 hover:text-stone-900">
            Skip this step
          </button>
          <button
            onClick={[saveProperty, saveRooms, saveRates, saveTax, saveSample][idx]}
            disabled={saving}
            data-testid={`onb-save-${STEP_META[idx].id}`}
            className={`flex items-center gap-1.5 px-6 py-2.5 rounded-xl text-sm font-bold text-white bg-gradient-to-br ${tint.bg} disabled:opacity-50 shadow-lg transition-transform hover:-translate-y-0.5`}>
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            {idx < 4 ? "Save & Continue" : "Finish Setup"}
            {!saving && <ArrowRight className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
};

// Helpers
const FinishedScreen = ({ propertyId, onClose, onNavigate }) => {
  const [demoCount, setDemoCount] = useState(0);
  const [seeding, setSeeding] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [mrConfig, setMrConfig] = useState(null);
  const [mrStarting, setMrStarting] = useState(false);
  const [propCity, setPropCity] = useState("");
  // Booking.com URL state
  const [bookingUrl, setBookingUrl] = useState("");
  const [bookingUrlSaved, setBookingUrlSaved] = useState("");
  const [bookingValidating, setBookingValidating] = useState(false);
  const [bookingSaving, setBookingSaving] = useState(false);
  const [bookingValidation, setBookingValidation] = useState(null);
  // Room-count panel state: shows manual override + auto-scan value side by side.
  const [roomCountState, setRoomCountState] = useState(null);
  const [manualRoomInput, setManualRoomInput] = useState("");
  const [savingManualRC, setSavingManualRC] = useState(false);

  const loadDemoCount = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/demo-seeder/status/${propertyId}`);
      setDemoCount(data.demo_booking_count || 0);
    } catch { /* silent */ }
  }, [propertyId]);

  const loadMarketRobot = useCallback(async () => {
    try {
      const [cfg, props, ob] = await Promise.all([
        axios.get(`${API}/revenue/market-robot/${propertyId}/config`).then(r => r.data).catch(() => null),
        axios.get(`${API}/properties`).then(r => r.data).catch(() => []),
        axios.get(`${API}/revenue/market-robot/${propertyId}/our-booking`).then(r => r.data).catch(() => null),
      ]);
      setMrConfig(cfg);
      const me = (props || []).find(p => p.id === propertyId);
      setPropCity(me?.city || cfg?.city || "London");
      setBookingUrl(ob?.booking_url || "");
      setBookingUrlSaved(ob?.booking_url || "");
    } catch { /* silent */ }
  }, [propertyId]);

  useEffect(() => { loadDemoCount(); loadMarketRobot(); }, [loadDemoCount, loadMarketRobot]);

  const loadRoomCountState = useCallback(async () => {
    if (!propertyId) return;
    try {
      const { data } = await axios.get(`${API}/revenue/market-robot/${propertyId}/room-count`);
      setRoomCountState(data);
      if (data.manual_room_count) setManualRoomInput(String(data.manual_room_count));
    } catch { /* non-fatal */ }
  }, [propertyId]);
  useEffect(() => { loadRoomCountState(); }, [loadRoomCountState]);

  const startMarketRobot = async () => {
    setMrStarting(true);
    try {
      const city = propCity || mrConfig?.city || "London";
      const info = getCurrencyInfo(city);
      await axios.put(`${API}/revenue/market-robot/${propertyId}/config`, {
        enabled: true,
        scanner_active: true,
        city,
        currency: info.code,
        scan_interval_minutes: 60,
        days_ahead: 30,
        auto_pricing: false,
      });
      // Trigger a first scan right away so the user sees data immediately
      try { await axios.post(`${API}/revenue/market-robot/${propertyId}/scan`, { days_ahead: 30 }); } catch { /* non-fatal */ }
      toast.success(`Market Robot ${city} için aktif edildi (${info.code})`);
      loadMarketRobot();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Market Robot başlatılamadı");
    } finally { setMrStarting(false); }
  };

  const testBookingUrl = async () => {
    if (!bookingUrl) { toast.error("Önce Booking.com URL'si yapıştırın"); return; }
    setBookingValidating(true);
    setBookingValidation(null);
    try {
      const info = getCurrencyInfo(propCity);
      const { data: v } = await axios.post(`${API}/revenue/market-robot/validate-booking-url`, {
        booking_url: bookingUrl,
        currency: info.code,
      });
      setBookingValidation(v);
      if (v.ok) toast.success(`${v.hotel_name} · ${v.currency} ${v.sample_price}`);
      else toast.error(`Doğrulanamadı: ${v.error || "bilinmeyen"}`);
    } catch {
      toast.error("Validator error");
    }
    setBookingValidating(false);
  };

  const saveBookingUrl = async () => {
    if (!bookingUrl) { toast.error("Önce URL yapıştırın"); return; }
    if (!bookingUrl.toLowerCase().includes("booking.com")) {
      toast.error("Booking.com URL'si gerekli"); return;
    }
    setBookingSaving(true);
    try {
      const { data } = await axios.put(`${API}/revenue/market-robot/${propertyId}/our-booking`, {
        booking_url: bookingUrl,
      });
      setBookingUrlSaved(bookingUrl);
      if (data?.validation?.ok) {
        toast.success(`Kaydedildi: ${data.validation.hotel_name}`);
        setBookingValidation(data.validation);
      } else if (data?.validation && !data.validation.ok) {
        toast.warning(`URL kaydedildi ama doğrulama başarısız: ${data.validation.error}`);
        setBookingValidation(data.validation);
      } else {
        toast.success("Booking URL kaydedildi");
      }
      // Trigger first scrape to populate Our Booking Live card
      try { await axios.post(`${API}/revenue/market-robot/${propertyId}/our-booking/scan`); } catch { /* non-fatal */ }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydetme başarısız");
    } finally { setBookingSaving(false); }
  };

  const seed = async (count) => {
    setSeeding(true);
    try {
      const { data } = await axios.post(`${API}/demo-seeder/seed/${propertyId}?count=${count}`);
      toast.success(`Created ${data.created} demo bookings`);
      loadDemoCount();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to seed demo data");
    } finally { setSeeding(false); }
  };
  const seedOccupancy = async (occupancy) => {
    setSeeding(true);
    try {
      const { data } = await axios.post(`${API}/demo-seeder/seed-occupancy/${propertyId}?occupancy=${occupancy}&days=30`);
      toast.success(`Seeded ${data.created} bookings → ${data.actual_occupancy_pct}% actual occupancy (last 30 days)`);
      loadDemoCount();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to seed occupancy");
    } finally { setSeeding(false); }
  };
  const refreshRoomCount = async () => {
    setSeeding(true);
    try {
      await axios.post(`${API}/revenue/market-robot/${propertyId}/refresh-room-count`);
      toast.info("Booking.com tarama başladı (6+ tarih paralel taranıyor) — ~60-150 saniye sürebilir...");
      const start = Date.now();
      const poll = async () => {
        try {
          const { data } = await axios.get(`${API}/revenue/market-robot/${propertyId}/refresh-room-count/status`);
          if (data.status === "done" && data.result?.room_count) {
            const src = data.result.source === "booking_com_vision_multidate" ? "multi-date vision" : data.result.source === "booking_com_vision" ? "vision LLM" : "Booking.com HTML";
            toast.success(`Oda sayısı: ${data.result.room_count} (${src}${data.result.evidence ? ` · ${data.result.evidence}` : ""})`);
            loadRoomCountState();
            return true;
          }
          if (data.status === "no_data") {
            toast.warning(
              data.error || "Booking.com bu mülk için açık oda sayısı sergilemiyor. Lütfen aşağıdan manuel girin.",
              { duration: 10000 }
            );
            loadRoomCountState();
            return true;
          }
          if (data.error) { toast.error(`Tarama başarısız: ${data.error}`); return true; }
          return false;
        } catch { return false; }
      };
      const interval = setInterval(async () => {
        if (await poll() || Date.now() - start > 300000) {
          clearInterval(interval);
          setSeeding(false);
        }
      }, 5000);
      setTimeout(poll, 1500);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Refresh failed");
      setSeeding(false);
    }
  };
  const saveManualRoomCount = async (clear = false) => {
    setSavingManualRC(true);
    try {
      const payload = clear ? { room_count: null } : { room_count: parseInt(manualRoomInput, 10) || 0 };
      const { data } = await axios.post(`${API}/revenue/market-robot/${propertyId}/room-count/manual`, payload);
      if (data.cleared) {
        toast.success("Manuel oda sayısı temizlendi — otomatik tarama değeri kullanılacak.");
        setManualRoomInput("");
      } else {
        toast.success(`Manuel oda sayısı: ${data.manual_room_count} (otomatik taramayı geçersiz kılar)`);
      }
      loadRoomCountState();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydetme başarısız");
    } finally { setSavingManualRC(false); }
  };
  const clear = async () => {
    if (!window.confirm("Remove all demo bookings? Your real bookings will stay untouched.")) return;
    setClearing(true);
    try {
      const { data } = await axios.post(`${API}/demo-seeder/clear/${propertyId}`);
      toast.success(`Removed ${data.deleted} demo bookings`);
      loadDemoCount();
    } catch (e) { toast.error("Clear failed"); }
    finally { setClearing(false); }
  };

  return (
    <div className="max-w-3xl mx-auto p-6" data-testid="onboarding-done">
      <div className="bg-gradient-to-br from-fuchsia-50 via-violet-50 to-sky-50 border border-fuchsia-200 rounded-3xl p-10 text-center">
        <div className="inline-flex w-20 h-20 rounded-full bg-gradient-to-br from-fuchsia-500 to-violet-600 items-center justify-center text-white mb-5 shadow-xl shadow-fuchsia-500/20">
          <PartyPopper className="w-10 h-10" />
        </div>
        <h1 className="text-4xl font-black text-stone-900">You're live.</h1>
        <p className="text-stone-600 mt-3 max-w-xl mx-auto">
          Your property is configured, rooms are in the inventory, rate plans are ready for OTA distribution,
          tax rules are attached, and your first booking is on the calendar.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-8">
          {STEP_META.map(s => (
            <div key={s.id} className="p-3 rounded-xl bg-white border border-stone-200">
              <div className={`inline-flex w-8 h-8 rounded-lg bg-gradient-to-br ${TINT_CLASSES[s.tint].bg} items-center justify-center text-white mb-2`}>
                <s.icon className="w-4 h-4" />
              </div>
              <div className="text-[10px] uppercase text-stone-400 font-bold">{s.label}</div>
              <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-1 mx-auto" />
            </div>
          ))}
        </div>
      </div>

      {/* Demo seeder */}
      <div className="mt-5 bg-white border border-stone-200 rounded-3xl p-6 md:p-7" data-testid="demo-seeder-card">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 text-white flex items-center justify-center shadow-lg">
            <Sparkles className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-black text-stone-900">Want to see it live?</h2>
            <p className="text-sm text-stone-500 mt-1">
              Populate the calendar with realistic demo bookings across the next 60 days —
              varied guests, channels (Booking.com, Expedia, Airbnb, walk-in), room types
              and revenue. Finance dashboards and charts light up instantly. You can remove
              it all with one click later.
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              {[10, 20, 50].map(n => (
                <button key={n} onClick={() => seed(n)} disabled={seeding}
                  data-testid={`demo-seed-${n}`}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white text-xs font-bold disabled:opacity-50 shadow hover:-translate-y-0.5 transition-transform">
                  {seeding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                  Seed {n} bookings
                </button>
              ))}
              <button onClick={() => seedOccupancy(65)} disabled={seeding}
                data-testid="demo-seed-occupancy-65"
                title="Populate the last 30 days with enough bookings to reach ~65% actual occupancy — makes the Robot Performance Report show realistic revenue uplift."
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white text-xs font-bold disabled:opacity-50 shadow hover:-translate-y-0.5 transition-transform">
                {seeding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                Seed 65% occupancy (30d)
              </button>
              <button onClick={refreshRoomCount} disabled={seeding}
                data-testid="refresh-room-count"
                title="Re-read the property's room/apartment/unit count directly from the Booking.com hotel page (NOT from reviews). Use this when the dashboard shows the wrong total room count."
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white text-xs font-bold disabled:opacity-50 shadow hover:-translate-y-0.5 transition-transform">
                {seeding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                Re-scan room count
              </button>
              {demoCount > 0 && (
                <button onClick={clear} disabled={clearing}
                  data-testid="demo-clear"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white hover:bg-rose-50 border border-rose-200 text-rose-600 text-xs font-bold disabled:opacity-50">
                  {clearing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                  Clear {demoCount} demo booking{demoCount === 1 ? "" : "s"}
                </button>
              )}
            </div>
            {demoCount > 0 && (
              <p className="text-[11px] text-stone-400 mt-3">
                <CheckCircle2 className="w-3 h-3 inline text-emerald-500" /> {demoCount} demo booking{demoCount === 1 ? "" : "s"} currently in the system.
              </p>
            )}

            {/* Manual room count override — PRIMARY way to get this right */}
            <div className="mt-4 pt-4 border-t-2 border-fuchsia-200" data-testid="manual-room-count-card">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h4 className="text-sm font-bold text-stone-900 flex items-center gap-2">
                    <span className="inline-block w-2 h-2 rounded-full bg-fuchsia-500"></span>
                    Toplam Oda Sayısı (Manuel)
                  </h4>
                  <p className="text-[11px] text-stone-500 mt-0.5 max-w-md">
                    Performance Report'ta kullanılan oda sayısı. Otomatik tarama Booking.com'un bot-engellemesi nedeniyle çoğu zaman çalışmaz; <b className="text-fuchsia-700">gerçek envanteri biliyorsanız buraya yazın</b> — her zaman önceliklidir.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="1"
                    max="5000"
                    value={manualRoomInput}
                    onChange={(e) => setManualRoomInput(e.target.value)}
                    placeholder="ör. 9"
                    data-testid="manual-room-count-input"
                    className="w-24 px-3 py-2 rounded-xl border border-stone-300 focus:border-fuchsia-400 focus:outline-none text-sm font-semibold text-center"
                  />
                  <button
                    onClick={() => saveManualRoomCount(false)}
                    disabled={savingManualRC || !manualRoomInput}
                    data-testid="save-manual-room-count"
                    className="px-4 py-2 rounded-xl bg-gradient-to-br from-fuchsia-500 to-violet-600 hover:from-fuchsia-400 hover:to-violet-500 text-white text-xs font-bold disabled:opacity-50 shadow"
                  >
                    {savingManualRC ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Kaydet"}
                  </button>
                  {roomCountState?.manual_room_count ? (
                    <button
                      onClick={() => saveManualRoomCount(true)}
                      disabled={savingManualRC}
                      data-testid="clear-manual-room-count"
                      title="Manuel override'ı kaldır ve otomatik taramaya dön"
                      className="px-3 py-2 rounded-xl bg-white hover:bg-rose-50 border border-rose-200 text-rose-600 text-xs font-bold disabled:opacity-50">
                      Temizle
                    </button>
                  ) : null}
                </div>
              </div>
              {roomCountState && (
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <div className="rounded-lg bg-fuchsia-50 border border-fuchsia-200 p-2 text-center">
                    <div className="text-[9px] uppercase font-bold text-fuchsia-700">Manuel (aktif)</div>
                    <div className={`text-base font-black ${roomCountState.manual_room_count ? "text-fuchsia-900" : "text-stone-300"}`}>
                      {roomCountState.manual_room_count || "—"}
                    </div>
                  </div>
                  <div className="rounded-lg bg-sky-50 border border-sky-200 p-2 text-center">
                    <div className="text-[9px] uppercase font-bold text-sky-700">Booking.com</div>
                    <div className={`text-base font-black ${roomCountState.booking_room_count ? "text-sky-900" : "text-stone-300"}`}>
                      {roomCountState.booking_room_count || "—"}
                    </div>
                  </div>
                  <div className="rounded-lg bg-stone-50 border border-stone-200 p-2 text-center">
                    <div className="text-[9px] uppercase font-bold text-stone-600">Lokal (room_types)</div>
                    <div className={`text-base font-black ${roomCountState.room_types_total ? "text-stone-900" : "text-stone-300"}`}>
                      {roomCountState.room_types_total || "—"}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Market Robot activation */}
      <div className="mt-5 bg-white border border-stone-200 rounded-3xl p-6 md:p-7" data-testid="market-robot-activation">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-fuchsia-500 to-pink-600 text-white flex items-center justify-center shadow-lg">
            <Radar className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xl font-black text-stone-900">Activate Market Robot</h2>
              {mrConfig?.enabled && mrConfig?.scanner_active && (
                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" /> Scanning Live
                </span>
              )}
            </div>
            <p className="text-sm text-stone-500 mt-1">
              Start continuous competitor scanning for <b className="text-stone-900">{propCity || "your city"}</b>.
              Detects pricing gaps vs Booking.com listings, overlays your occupancy & rate on top of market data,
              and surfaces revenue opportunities — updated every 60 minutes in the background.
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-4">
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-fuchsia-50 border border-fuchsia-200 text-fuchsia-700 text-[11px] font-bold">
                <MapPin className="w-3.5 h-3.5" /> {propCity || "—"}
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-50 border border-sky-200 text-sky-700 text-[11px] font-bold">
                <Banknote className="w-3.5 h-3.5" /> {getCurrencyInfo(propCity).code}
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-stone-50 border border-stone-200 text-stone-600 text-[11px] font-bold">
                Every 60 min · 30 days ahead
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-4">
              {mrConfig?.enabled && mrConfig?.scanner_active ? (
                <button disabled
                  data-testid="market-robot-active-pill"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-bold shadow cursor-default">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Market Robot Active
                </button>
              ) : (
                <button onClick={startMarketRobot} disabled={mrStarting}
                  data-testid="market-robot-start-btn"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-br from-fuchsia-500 to-pink-600 hover:from-fuchsia-400 hover:to-pink-500 text-white text-xs font-bold disabled:opacity-50 shadow hover:-translate-y-0.5 transition-transform">
                  {mrStarting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                  Start Market Robot
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Link Booking.com listing */}
      <div className="mt-5 bg-white border border-stone-200 rounded-3xl p-6 md:p-7" data-testid="onboarding-booking-url-card">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 text-white flex items-center justify-center shadow-lg">
            <Banknote className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xl font-black text-stone-900">Link Booking.com Listing</h2>
              {bookingUrlSaved && (
                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Linked
                </span>
              )}
            </div>
            <p className="text-sm text-stone-500 mt-1">
              Paste your property's Booking.com URL. The scraper uses it to pull live <b>lowest nightly rate</b>, <b>review score</b> and <b>availability</b> every 3 hours — powering "Biz vs Pazar" comparisons.
              The <b>Test URL</b> button confirms Booking.com recognizes it before saving.
            </p>
            <div className="mt-3 flex flex-col md:flex-row gap-2">
              <input
                value={bookingUrl}
                onChange={(e) => { setBookingUrl(e.target.value); setBookingValidation(null); }}
                placeholder="https://www.booking.com/hotel/ch/your-hotel.en-gb.html"
                className="flex-1 border border-stone-300 rounded-lg px-3 py-2 text-xs font-mono focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400"
                data-testid="onboarding-booking-url-input"
              />
              <button onClick={testBookingUrl} disabled={bookingValidating || !bookingUrl}
                      className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
                      data-testid="onboarding-booking-url-test">
                {bookingValidating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                {bookingValidating ? "Testing…" : "Test URL"}
              </button>
              <button onClick={saveBookingUrl} disabled={bookingSaving || !bookingUrl}
                      className="px-4 py-2 rounded-lg bg-gradient-to-br from-indigo-500 to-blue-600 hover:from-indigo-400 hover:to-blue-500 text-white text-xs font-bold inline-flex items-center justify-center gap-1.5 disabled:opacity-50"
                      data-testid="onboarding-booking-url-save">
                {bookingSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                {bookingSaving ? "Saving…" : "Save"}
              </button>
            </div>
            {bookingValidation && (
              <div
                className={`mt-3 border rounded-lg p-3 text-xs ${
                  bookingValidation.ok
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-rose-50 border-rose-200 text-rose-700"
                }`}
                data-testid="onboarding-booking-url-result"
              >
                {bookingValidation.ok ? (
                  <>
                    <div className="font-bold">✓ {bookingValidation.hotel_name}</div>
                    <div className="mt-0.5">
                      Booking ID <span className="font-mono">{bookingValidation.hotel_id}</span> · Örnek fiyat <span className="font-bold">{bookingValidation.currency} {bookingValidation.sample_price}</span>
                    </div>
                  </>
                ) : (
                  <div>✗ {bookingValidation.error || "Bilinmeyen hata"} — URL'yi kontrol edin.</div>
                )}
              </div>
            )}
            <p className="text-[10px] text-stone-400 mt-2">İsteğe bağlı · boş bırakabilirsiniz, daha sonra Market Robot → Our Booking.com Live kartından da ekleyebilirsiniz.</p>
          </div>
        </div>
      </div>

      {/* Explore tour — the platform's core value in 3 clicks */}
      <div className="mt-5 bg-white border border-stone-200 rounded-3xl p-6 md:p-7" data-testid="explore-tour-card">
        <h2 className="text-xl font-black text-stone-900 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-violet-500" /> Sıradaki 3 adım — platformun gücünü keşfedin
        </h2>
        <p className="text-sm text-stone-500 mt-1">Kurulum bitti. Şimdi ReveniQ'nun asıl değerini görün:</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
          {[
            { view: "revenue", icon: Radar, title: "Market Robot", desc: "Şehrinizdeki rakip fiyatlarını canlı tarayın, fiyat boşluklarını görün.", tint: "from-fuchsia-500 to-pink-600" },
            { view: "revenue-brain", icon: Zap, title: "Revenue Brain", desc: "Geçmiş kararlarından öğrenen, fiyatları otomatik ayarlayan yapay zekâ.", tint: "from-violet-500 to-purple-600" },
            { view: "chmgr-hub", icon: RefreshCw, title: "Channel Manager", desc: "Booking.com, Expedia ve Airbnb'ye tek yerden fiyat ve müsaitlik gönderin.", tint: "from-sky-500 to-blue-600" },
          ].map(t => (
            <button key={t.view} onClick={() => onNavigate ? onNavigate(t.view) : onClose?.()}
              data-testid={`tour-${t.view}`}
              className="p-4 rounded-2xl border border-stone-200 bg-stone-50 hover:bg-white hover:border-stone-300 hover:shadow-md text-left transition-all group">
              <div className={`inline-flex w-9 h-9 rounded-xl bg-gradient-to-br ${t.tint} items-center justify-center text-white mb-2 group-hover:scale-110 transition-transform`}>
                <t.icon className="w-4.5 h-4.5" />
              </div>
              <div className="text-sm font-black text-stone-900 flex items-center gap-1">
                {t.title} <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
              <p className="text-[11px] text-stone-500 mt-1">{t.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* First 7 days email series */}
      <DripCard propertyId={propertyId} />

      <div className="mt-6 flex justify-center">
        <button onClick={onClose} data-testid="onboarding-go-dashboard"
          className="px-8 py-3.5 bg-stone-900 hover:bg-stone-800 text-white rounded-xl font-bold text-sm inline-flex items-center gap-2">
          Go to Dashboard <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

const DripCard = ({ propertyId }) => {
  const [drip, setDrip] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/onboarding-drip/status/${propertyId}`);
      setDrip(data);
    } catch { /* silent */ }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const enrollOrToggle = async () => {
    try {
      if (!drip?.enrolled) {
        await axios.post(`${API}/onboarding-drip/enroll/${propertyId}`, {});
        toast.success("İlk 7 Gün e-posta serisine kaydoldunuz");
      } else {
        const { data } = await axios.post(`${API}/onboarding-drip/toggle/${propertyId}`);
        toast.success(data.enabled ? "Seri tekrar açıldı" : "Seri duraklatıldı");
      }
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "İşlem başarısız"); }
  };

  if (!drip) return null;
  const active = drip.enrolled && drip.enabled;
  return (
    <div className="mt-5 bg-white border border-stone-200 rounded-3xl p-6 md:p-7" data-testid="drip-card">
      <div className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white flex items-center justify-center shadow-lg">
          <Mail className="w-6 h-6" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-xl font-black text-stone-900">İlk 7 Gün E-posta Serisi</h2>
            {active && (
              <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold uppercase tracking-wider">Aktif</span>
            )}
          </div>
          <p className="text-sm text-stone-500 mt-1">
            {active
              ? <>Aktivasyon rehberi <b className="text-stone-900">{drip.email}</b> adresine gidiyor — hoş geldin, Market Robot (1. gün), Booking.com bağlantısı (3. gün) ve Revenue Brain raporu (7. gün).</>
              : "Platformun çekirdek değerine adım adım yönlendiren 4 kısa e-posta: hoş geldin, Market Robot, Booking.com bağlantısı ve Revenue Brain raporu."}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-4">
            {(drip.timeline || []).map(t => (
              <div key={t.key} data-testid={`drip-step-${t.key}`}
                className={`p-2.5 rounded-xl border text-center ${t.sent_at ? "bg-emerald-50 border-emerald-200" : "bg-stone-50 border-stone-200"}`}>
                <div className="text-[9px] uppercase font-bold text-stone-400">Gün {t.day}</div>
                <div className="text-[11px] font-bold text-stone-800 truncate">
                  {{ welcome: "Hoş geldin", market_robot: "Market Robot", booking_url: "Booking.com bağla", revenue_brain: "Revenue Brain" }[t.key] || t.key}
                </div>
                {t.sent_at
                  ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 mx-auto mt-1" />
                  : <Circle className="w-3.5 h-3.5 text-stone-300 mx-auto mt-1" />}
              </div>
            ))}
          </div>
          <div className="mt-4">
            <button onClick={enrollOrToggle} data-testid="drip-toggle-btn"
              className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold shadow transition-transform hover:-translate-y-0.5 ${
                active ? "bg-white border border-stone-300 text-stone-600 hover:bg-stone-50"
                       : "bg-gradient-to-br from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white"}`}>
              {active ? <><BellOff className="w-3.5 h-3.5" /> Seriyi Duraklat</> : <><Mail className="w-3.5 h-3.5" /> {drip.enrolled ? "Seriyi Aç" : "Seriye Kaydol"}</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const StepBody = ({ tint, icon: Icon, title, subtitle, children }) => (
  <>
    <div className="flex items-start gap-4 mb-6">
      <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${tint.bg} text-white flex items-center justify-center shadow-lg`}>
        <Icon className="w-7 h-7" />
      </div>
      <div>
        <h2 className="text-2xl font-black text-stone-900">{title}</h2>
        <p className="text-sm text-stone-500 mt-1">{subtitle}</p>
      </div>
    </div>
    {children}
  </>
);

const F = ({ label, children }) => (
  <div>
    <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1.5">{label}</label>
    {children}
  </div>
);

const RatePick = ({ label, desc, code, checked, onToggle, testId }) => (
  <button onClick={onToggle} data-testid={testId}
    className={`p-4 rounded-xl border-2 text-left transition-all ${
      checked ? "border-emerald-500 bg-emerald-50" : "border-stone-200 bg-white hover:border-stone-300"
    }`}>
    <div className="flex items-start justify-between">
      <div>
        <div className="flex items-center gap-2">
          <span className={`font-mono font-bold text-sm ${checked ? "text-emerald-700" : "text-stone-500"}`}>{code}</span>
          <span className="font-bold text-stone-900">{label}</span>
        </div>
        <p className="text-xs text-stone-500 mt-1">{desc}</p>
      </div>
      {checked ? <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" /> : <Circle className="w-5 h-5 text-stone-300 flex-shrink-0" />}
    </div>
  </button>
);

export default OnboardingWizard;
