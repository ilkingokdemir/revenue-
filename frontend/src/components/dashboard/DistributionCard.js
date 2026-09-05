import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Copy, CheckCircle, XCircle, GoogleLogo, Code, Tag, Gift } from "@phosphor-icons/react";
import PropertyLocationCard from "./PropertyLocationCard";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const W = { withCredentials: true };

function CopyField({ label, value, testId }) {
  const [ok, setOk] = useState(false);
  return (
    <div>
      <div className="text-[10px] font-bold uppercase text-stone-500 mb-1">{label}</div>
      <div className="flex gap-1.5">
        <code className="flex-1 text-[11px] bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-2 break-all whitespace-pre-wrap" data-testid={testId}>{value}</code>
        <button onClick={() => { navigator.clipboard?.writeText(value); setOk(true); setTimeout(() => setOk(false), 1500); }} className="px-2.5 rounded-lg border border-stone-200 hover:bg-stone-50" aria-label="copy" data-testid={`${testId}-copy`}>{ok ? <CheckCircle size={14} className="text-emerald-600" /> : <Copy size={14} />}</button>
      </div>
    </div>
  );
}

export default function DistributionCard({ propertyId }) {
  const [props, setProps] = useState([]);
  const [pid, setPid] = useState(propertyId && propertyId !== "all" ? propertyId : "");
  const [ads, setAds] = useState(null);
  const [embed, setEmbed] = useState(null);
  const [exit, setExit] = useState(null);
  const [gift, setGift] = useState(null);
  const [previewDesign, setPreviewDesign] = useState(null);

  useEffect(() => {
    axios.get(`${API}/properties`, W).then(({ data }) => { const l = Array.isArray(data) ? data : data.items || data.properties || []; setProps(l); if (!pid && l[0]) setPid(l[0].id); }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadAds = () => axios.get(`${API}/hotel-ads/status/${pid}`, W).then(({ data }) => setAds(data)).catch(() => {});
  useEffect(() => {
    if (!pid) return;
    loadAds();
    axios.get(`${API}/embed/snippet/${pid}`, W).then(({ data }) => setEmbed(data)).catch(() => {});
    axios.get(`${API}/exit-intent/config/${pid}`, W).then(({ data }) => setExit(data)).catch(() => {});
    axios.get(`${API}/booking/gift-cards/config/${pid}`).then(({ data }) => setGift(data)).catch(() => {});
  }, [pid]);

  const saveExit = async () => {
    try { const { data } = await axios.put(`${API}/exit-intent/config/${pid}`, exit, W); setExit({ ...exit, ...data }); toast.success("Exit-intent kaydedildi (promo kodu otomatik oluşturuldu)"); }
    catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };
  const saveGift = async () => {
    try { await axios.put(`${API}/gift-cards/config/${pid}`, gift, W); toast.success("Hediye çeki ayarları kaydedildi"); }
    catch (e) { toast.error(e.response?.data?.detail || "Kaydedilemedi"); }
  };
  const inp = "border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs w-full";
  const card = "bg-white border border-stone-200 rounded-xl p-4 space-y-3";

  return (
    <div className="space-y-4" data-testid="distribution-card">
      <select value={pid} onChange={(e) => setPid(e.target.value)} className="border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs" data-testid="dist-property-select">
        {props.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className={card} data-testid="hotel-ads-card">
          <div className="flex items-center gap-2"><GoogleLogo size={16} weight="bold" className="text-blue-600" /><h3 className="text-sm font-semibold text-stone-900">Google Hotel Ads — Free Booking Links</h3>
            {ads && <span className={`ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full ${ads.ready ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`} data-testid="hotel-ads-ready">{ads.ready ? "Hazır" : "Eksikler var"}</span>}
          </div>
          {ads && (
            <>
              <ul className="space-y-1">
                {ads.checks.map((c) => <li key={c.key} className="flex items-center gap-2 text-xs" data-testid={`hotel-ads-check-${c.key}`}>{c.ok ? <CheckCircle size={14} weight="fill" className="text-emerald-600" /> : <XCircle size={14} weight="fill" className="text-stone-300" />}<span className={c.ok ? "text-stone-700" : "text-stone-400"}>{c.label}</span></li>)}
              </ul>
              <PropertyLocationCard pid={pid} onSaved={loadAds} />
              <CopyField label="Hotel List Feed (XML)" value={ads.feeds.hotel_list} testId="hotel-ads-feed-list" />
              <CopyField label="ARI / Fiyat Feed (Pull, XML)" value={ads.feeds.ari} testId="hotel-ads-feed-ari" />
              <CopyField label="Point-of-Sale (Landing) URL şablonu" value={ads.feeds.point_of_sale} testId="hotel-ads-pos" />
              <div className="text-[11px] text-stone-500">Tıklama: <b>{ads.stats.clicks}</b> · Rezervasyon: <b>{ads.stats.bookings}</b></div>
              <ol className="list-decimal list-inside text-[11px] text-stone-500 space-y-0.5">{ads.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
            </>
          )}
        </div>

        <div className="space-y-4">
          <div className={card} data-testid="embed-card">
            <div className="flex items-center gap-2"><Code size={16} weight="bold" className="text-violet-600" /><h3 className="text-sm font-semibold text-stone-900">Mevcut web sitenize gömme kodu</h3></div>
            <p className="text-[11px] text-stone-500">WordPress, Wix, Squarespace… herhangi bir sayfaya yapıştırın; tarih + misafir arama kutusu çıkar ve booking engine'e yönlendirir.</p>
            {embed && <><CopyField label="Arama widget'ı (script)" value={embed.snippet} testId="embed-snippet" /><CopyField label="Tam sayfa (iframe)" value={embed.iframe} testId="embed-iframe" /></>}
          </div>

          <div className={card} data-testid="exit-intent-card">
            <div className="flex items-center gap-2"><Tag size={16} weight="bold" className="text-rose-600" /><h3 className="text-sm font-semibold text-stone-900">Exit-intent popup + kupon</h3>
              {exit && <span className="ml-auto text-[11px] text-stone-500">Gösterim {exit.stats?.shown || 0} · Dönüşüm {exit.stats?.converted || 0}</span>}</div>
            {exit && (
              <div className="grid grid-cols-2 gap-2">
                <label className="col-span-2 flex items-center gap-2 text-xs"><input type="checkbox" checked={exit.enabled !== false} onChange={(e) => setExit({ ...exit, enabled: e.target.checked })} data-testid="exit-enabled" /> Aktif</label>
                <input className={inp} placeholder="Başlık" value={exit.title || ""} onChange={(e) => setExit({ ...exit, title: e.target.value })} data-testid="exit-title" />
                <input className={inp} placeholder="Kupon kodu" value={exit.code || ""} onChange={(e) => setExit({ ...exit, code: e.target.value.toUpperCase() })} data-testid="exit-code" />
                <input className={`${inp} col-span-2`} placeholder="Metin ({pct} → indirim yüzdesi)" value={exit.body || ""} onChange={(e) => setExit({ ...exit, body: e.target.value })} />
                <input className={inp} type="number" placeholder="İndirim %" value={exit.discount_pct} onChange={(e) => setExit({ ...exit, discount_pct: e.target.value })} data-testid="exit-pct" />
                <input className={inp} type="number" placeholder="Gecikme (sn)" value={exit.delay_sec} onChange={(e) => setExit({ ...exit, delay_sec: e.target.value })} />
                <button onClick={saveExit} className="col-span-2 py-2 text-xs font-bold text-white bg-stone-900 rounded-lg" data-testid="exit-save">Kaydet</button>
              </div>
            )}
          </div>

          <div className={card} data-testid="gift-config-card">
            <div className="flex items-center gap-2"><Gift size={16} weight="bold" className="text-amber-600" /><h3 className="text-sm font-semibold text-stone-900">Hediye çeki satışı</h3></div>
            {gift && (
              <div className="grid grid-cols-2 gap-2">
                <label className="col-span-2 flex items-center gap-2 text-xs"><input type="checkbox" checked={gift.enabled !== false} onChange={(e) => setGift({ ...gift, enabled: e.target.checked })} data-testid="gift-enabled" /> Booking engine'de satışa aç</label>
                <input className={`${inp} col-span-2`} placeholder="Tutar seçenekleri (virgülle)" value={(gift.presets || []).join(",")} onChange={(e) => setGift({ ...gift, presets: e.target.value.split(",").map((x) => Number(x.trim())).filter(Boolean) })} data-testid="gift-presets" />
                <input className={inp} type="number" placeholder="Min" value={gift.min} onChange={(e) => setGift({ ...gift, min: e.target.value })} />
                <input className={inp} type="number" placeholder="Geçerlilik (gün)" value={gift.expires_days} onChange={(e) => setGift({ ...gift, expires_days: e.target.value })} />
                <div className="col-span-2">
                  <div className="text-[10px] font-bold uppercase text-stone-500 mb-1">E-posta tasarımı (varsayılan + misafire açık olanlar)</div>
                  <div className="grid grid-cols-4 gap-1.5" data-testid="gift-design-grid">
                    {(gift.designs || []).map((d) => {
                      const enabledList = gift.designs_enabled || gift.designs.map((x) => x.id);
                      const on = enabledList.includes(d.id);
                      return (
                        <div key={d.id} className={`rounded-lg border p-1.5 text-[10px] ${gift.design === d.id ? "border-stone-900" : "border-stone-200"}`} data-testid={`gift-design-${d.id}`}>
                          <button onClick={() => setGift({ ...gift, design: d.id })} className="w-full h-10 rounded-md mb-1" style={{ background: d.bg || "#0f4c5c", color: d.text }} title="Varsayılan yap"><span className="font-bold">£100</span></button>
                          <div className="font-semibold truncate">{d.name}</div>
                          <div className="flex items-center justify-between mt-0.5">
                            <label className="flex items-center gap-1"><input type="checkbox" checked={on} onChange={(e) => setGift({ ...gift, designs_enabled: e.target.checked ? [...enabledList, d.id] : enabledList.filter((x) => x !== d.id) })} data-testid={`gift-design-enable-${d.id}`} /> açık</label>
                            <button onClick={() => setPreviewDesign(previewDesign === d.id ? null : d.id)} className="text-indigo-600 font-bold" data-testid={`gift-design-preview-${d.id}`}>önizle</button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {previewDesign && <iframe title="gift preview" className="w-full h-[420px] mt-2 rounded-lg border border-stone-200 bg-white" src={`${API}/gift-cards/preview?property_id=${pid}&design=${previewDesign}&amount=100`} data-testid="gift-design-preview-frame" />}
                </div>
                <button onClick={saveGift} className="col-span-2 py-2 text-xs font-bold text-white bg-stone-900 rounded-lg" data-testid="gift-save">Kaydet</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
