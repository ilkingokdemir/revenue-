import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { MapPin, MagnifyingGlass, FloppyDisk } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PropertyLocationCard({ pid, onSaved }) {
  const [loc, setLoc] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!pid) return;
    axios.get(`${API}/properties/${pid}/location`, { withCredentials: true }).then(({ data }) => { setLoc({ latitude: data.latitude ?? "", longitude: data.longitude ?? "", address: data.address || "", city: data.city || "", country: data.country || "", country_code: data.country_code || "", postcode: data.postcode || "", phone: data.phone || "" }); setQ([data.address, data.city].filter(Boolean).join(", ")); }).catch(() => {});
  }, [pid]);

  if (!loc) return null;
  const has = loc.latitude !== "" && loc.longitude !== "";
  const geocode = async () => {
    setBusy(true);
    try { const { data } = await axios.post(`${API}/properties/${pid}/geocode`, { query: q }, { withCredentials: true }); setLoc({ ...loc, latitude: data.latitude, longitude: data.longitude }); toast.success(`Bulundu: ${data.display_name.slice(0, 60)}`); }
    catch (e) { toast.error(e.response?.data?.detail || "Bulunamadı"); } finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true);
    try { await axios.put(`${API}/properties/${pid}/location`, loc, { withCredentials: true }); toast.success("Konum kaydedildi — Hotel Ads feed'i güncellendi"); onSaved?.(); }
    catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); } finally { setBusy(false); }
  };
  const inp = "border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs w-full";
  const lat = Number(loc.latitude), lon = Number(loc.longitude);
  const bbox = has ? `${lon - 0.01},${lat - 0.006},${lon + 0.01},${lat + 0.006}` : "";

  return (
    <div className="border border-stone-200 rounded-xl p-3 space-y-2" data-testid="property-location-card">
      <div className="flex items-center gap-2 text-xs font-semibold text-stone-800"><MapPin size={14} weight="fill" className="text-rose-600" /> Tesis konumu (enlem / boylam)
        <span className={`ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full ${has ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`} data-testid="loc-status">{has ? "Tanımlı" : "Eksik"}</span></div>
      <div className="flex gap-1.5">
        <input className={inp} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Adres yazın → koordinat bul" data-testid="loc-query" />
        <button onClick={geocode} disabled={busy || !q} className="px-2.5 rounded-lg border border-stone-200 hover:bg-stone-50 disabled:opacity-50 whitespace-nowrap text-[11px] font-bold inline-flex items-center gap-1" data-testid="loc-geocode-btn"><MagnifyingGlass size={12} /> Adresten bul</button>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        <input className={inp} type="number" step="0.000001" placeholder="Enlem (lat)" value={loc.latitude} onChange={(e) => setLoc({ ...loc, latitude: e.target.value })} data-testid="loc-lat" />
        <input className={inp} type="number" step="0.000001" placeholder="Boylam (lng)" value={loc.longitude} onChange={(e) => setLoc({ ...loc, longitude: e.target.value })} data-testid="loc-lng" />
        <input className={inp} placeholder="Adres" value={loc.address} onChange={(e) => setLoc({ ...loc, address: e.target.value })} />
        <input className={inp} placeholder="Şehir" value={loc.city} onChange={(e) => setLoc({ ...loc, city: e.target.value })} />
        <input className={inp} placeholder="Ülke kodu (GB, TR)" value={loc.country_code} onChange={(e) => setLoc({ ...loc, country_code: e.target.value.toUpperCase().slice(0, 2) })} data-testid="loc-cc" />
        <input className={inp} placeholder="Telefon" value={loc.phone} onChange={(e) => setLoc({ ...loc, phone: e.target.value })} />
      </div>
      {has && <iframe title="konum" className="w-full h-40 rounded-lg border-0" loading="lazy" data-testid="loc-map" src={`https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`} />}
      <button onClick={save} disabled={busy || !has} className="w-full py-2 text-xs font-bold text-white bg-stone-900 rounded-lg disabled:opacity-50 inline-flex items-center justify-center gap-1" data-testid="loc-save"><FloppyDisk size={12} /> Konumu kaydet</button>
    </div>
  );
}
