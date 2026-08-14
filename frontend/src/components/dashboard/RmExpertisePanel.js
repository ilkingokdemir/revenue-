import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Medal, ChartLineUp, BookOpen, Buildings, ArrowsClockwise, Sparkle,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const CAT_TR = { prensipler: "RM Prensipleri", stratejiler: "Strateji Playbook'ları", rakipler: "Rakip RMS'ler", pazar: "Pazar Trendleri" };

export default function RmExpertisePanel({ properties = [], activePropertyId, embedded = false, embeddedPropertyId = "" }) {
  const [propertyId, setPropertyId] = useState(
    embeddedPropertyId || (activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default"));
  const [tab, setTab] = useState("brief");
  const [knowledge, setKnowledge] = useState([]);
  const [sens, setSens] = useState(null);
  const [brief, setBrief] = useState(null);
  const [busy, setBusy] = useState("");
  const [lib, setLib] = useState({ items: [], total: 0, categories: [] });
  const [libQ, setLibQ] = useState("");
  const [libCat, setLibCat] = useState("");
  const [rules, setRules] = useState([]);
  const [mlp, setMlp] = useState(null);
  const [scard, setScard] = useState(null);
  const [camps, setCamps] = useState([]);
  const [campImpact, setCampImpact] = useState(null);
  const [explore, setExplore] = useState(null);

  useEffect(() => {
    if (embeddedPropertyId) setPropertyId(embeddedPropertyId);
    else if (activePropertyId && activePropertyId !== "all") setPropertyId(activePropertyId);
  }, [activePropertyId, embeddedPropertyId]);

  const load = useCallback(async () => {
    try {
      const [k, s, b] = await Promise.all([
        axios.get(`${API}/rm-expertise/knowledge`, { withCredentials: true }),
        axios.get(`${API}/rm-expertise/${propertyId}/sensitivity`, { withCredentials: true }),
        axios.get(`${API}/rm-expertise/${propertyId}/expert-brief/latest`, { withCredentials: true }),
      ]);
      setKnowledge(k.data.items || []);
      setSens(s.data);
      setBrief(b.data);
      try {
        const r = await axios.get(`${API}/rm-expertise/${propertyId}/expert-rules`, { withCredentials: true });
        setRules(r.data.rules || []);
      } catch { /* */ }
      try {
        const m = await axios.get(`${API}/rm-expertise/${propertyId}/ml-pickup?days=24`, { withCredentials: true });
        setMlp(m.data);
        const [sc, cm, ci, ex] = await Promise.all([
          axios.get(`${API}/rm-expertise/${propertyId}/forecast-scorecard`, { withCredentials: true }),
          axios.get(`${API}/rm-expertise/${propertyId}/empty-night-campaigns`, { withCredentials: true }),
          axios.get(`${API}/rm-expertise/${propertyId}/campaign-impact`, { withCredentials: true }),
          axios.get(`${API}/rm-expertise/${propertyId}/exploration-report`, { withCredentials: true }),
        ]);
        setScard(sc.data);
        setCamps(cm.data.items || []);
        setCampImpact(ci.data);
        setExplore(ex.data);
      } catch { /* */ }
    } catch { toast.error("Uzmanlık verileri yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

  const loadLibrary = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/rm-expertise/library`, {
        params: { q: libQ, category: libCat }, withCredentials: true });
      setLib(r.data);
    } catch { /* */ }
  }, [libQ, libCat]);
  useEffect(() => { loadLibrary(); }, [loadLibrary]);

  const analyze = async () => {
    setBusy("sens");
    try {
      const r = await axios.post(`${API}/rm-expertise/${propertyId}/analyze-sensitivity`, {}, { withCredentials: true });
      setSens(r.data);
      toast.success(`Duyarlılık analizi bitti — ${r.data.sample_total} örnek işlendi`);
    } catch { toast.error("Analiz başarısız"); } finally { setBusy(""); }
  };

  const generateBrief = async () => {
    setBusy("brief");
    try {
      const r = await axios.post(`${API}/rm-expertise/${propertyId}/expert-brief`, {}, { withCredentials: true });
      setBrief(r.data);
      toast.success("Uzman brifingi hazırlandı");
    } catch { toast.error("Brifing üretilemedi"); } finally { setBusy(""); }
  };

  const internalize = async () => {
    setBusy("rules");
    try {
      const r = await axios.post(`${API}/rm-expertise/${propertyId}/internalize`, {}, { withCredentials: true });
      setRules(r.data.rules || []);
      toast.success(`${r.data.rules_count} uzman kuralı bu otelin verisiyle içselleştirildi`);
    } catch { toast.error("İçselleştirme başarısız"); } finally { setBusy(""); }
  };

  const applyCampaigns = async () => {
    setBusy("camp");
    try {
      const r = await axios.post(`${API}/rm-expertise/${propertyId}/empty-night-campaigns`, {}, { withCredentials: true });
      toast.success(r.data.detail);
      const cm = await axios.get(`${API}/rm-expertise/${propertyId}/empty-night-campaigns`, { withCredentials: true });
      setCamps(cm.data.items || []);
    } catch { toast.error("Kampanya uygulanamadı"); } finally { setBusy(""); }
  };

  const TABS = [
    { id: "brief", label: "Uzman Brifingi", icon: Sparkle },
    { id: "rules", label: "Uzman Kuralları", icon: Medal },
    { id: "mlpickup", label: "ML Pickup Tahmini", icon: ChartLineUp },
    { id: "explore", label: "Keşif Raporu", icon: ChartLineUp },
    { id: "library", label: "Bilgi Kütüphanesi", icon: BookOpen },
    { id: "sensitivity", label: "Fiyat Duyarlılığı", icon: ChartLineUp },
    { id: "principles", label: "RM Prensipleri", icon: BookOpen },
    { id: "market", label: "Rakipler & Pazar", icon: Buildings },
  ];

  return (
    <div className={embedded ? "" : "p-5 max-w-[1400px] mx-auto"} data-testid="rm-expertise-panel">
      {!embedded && (
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <Medal size={13} weight="fill" className="text-amber-500" />
            <span>Revenue · Alan Uzmanlığı</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">RM Uzmanı Robot</h1>
          <p className="text-sm text-stone-500 mt-1 max-w-2xl">
            Robot revenue management alanının tamamında uzmandır: prensipler, rakip RMS pazarı (2026), fiyat duyarlılığı
            ve strateji playbook'ları. Bu bilgi sohbete ve stratejiste otomatik beslenir; robot kendini her öğrenme döngüsünde geliştirir.
          </p>
        </div>
        {properties.length > 1 && (
          <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)}
            data-testid="rmx-property-select"
            className="text-xs border border-stone-300 rounded-md px-2 py-2 bg-white">
            {properties.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
      </div>
      )}

      <div className="flex gap-1.5 mb-4 flex-wrap">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`rmx-tab-${t.id}`}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg inline-flex items-center gap-1.5 border ${
              tab === t.id ? "bg-stone-900 text-white border-stone-900" : "bg-white text-stone-600 border-stone-200 hover:border-stone-400"}`}>
            <t.icon size={13} /> {t.label}
          </button>
        ))}
      </div>

      {tab === "brief" && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="rmx-brief">
          <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
            <div className="text-sm font-semibold text-stone-900">Uzman Strateji Brifingi
              <span className="text-[10px] text-stone-400 font-normal ml-2">pazar + rakip + duyarlılık + hafıza birleşimi</span>
            </div>
            <button onClick={generateBrief} disabled={busy === "brief"} data-testid="rmx-generate-brief"
              className="px-3 py-2 text-xs rounded-md bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 inline-flex items-center gap-1.5 font-medium">
              <ArrowsClockwise size={13} className={busy === "brief" ? "animate-spin" : ""} />
              {busy === "brief" ? "Uzman düşünüyor…" : "Yeni Brifing Üret"}
            </button>
          </div>
          {brief?.content ? (
            <div className="text-sm text-stone-700 whitespace-pre-wrap leading-relaxed" data-testid="rmx-brief-content">
              <div className="text-[10px] text-stone-400 mb-2">Üretildi: {brief.created_at?.slice(0, 16).replace("T", " ")}</div>
              {brief.content}
            </div>
          ) : (
            <div className="text-xs text-stone-500 py-8 text-center">Henüz brifing yok — "Yeni Brifing Üret" ile uzman robotun tam strateji raporunu alın.</div>
          )}
        </div>
      )}

      {tab === "rules" && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="rmx-rules">
          <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
            <div className="text-sm font-semibold text-stone-900">İçselleştirilmiş Uzman Kuralları
              <span className="text-[10px] text-stone-400 font-normal ml-2">robot sektör bilgisini BU otelin canlı rakamlarıyla uygulanabilir kurallara dönüştürür — chat ve stratejist bunları kullanır</span>
            </div>
            <button onClick={internalize} disabled={busy === "rules"} data-testid="rmx-internalize"
              className="px-3 py-2 text-xs rounded-md bg-emerald-700 text-white hover:bg-emerald-800 disabled:opacity-50 font-medium">
              {busy === "rules" ? "İçselleştiriliyor…" : "Yeniden İçselleştir"}
            </button>
          </div>
          {rules.length === 0 ? (
            <div className="text-xs text-stone-500 py-6 text-center">Henüz kural yok — "Yeniden İçselleştir" ile robotun bilgiyi bu otele uygulamasını başlatın.</div>
          ) : (
            <div className="space-y-2 mt-3">
              {rules.map((r) => (
                <div key={r.id} className="border border-emerald-100 bg-emerald-50/40 rounded-xl px-4 py-3" data-testid={`rmx-rule-${r.source_id}`}>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[10px] font-black text-emerald-700 bg-emerald-100 rounded px-1.5 py-0.5">{r.sira}</span>
                    <span className="text-sm font-semibold text-stone-900">{r.baslik}</span>
                  </div>
                  <div className="text-xs text-stone-700 leading-relaxed">{r.kural}</div>
                  <div className="text-[10px] text-stone-400 mt-1">Hesaplandı: {r.computed_at?.slice(0, 16).replace("T", " ")}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "mlpickup" && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="rmx-mlpickup">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-1">
            <div className="text-sm font-semibold text-stone-900">ML Pickup Tahmini
              <span className="text-[10px] text-stone-400 font-normal ml-2">{mlp?.model}</span>
            </div>
            <div className="flex items-center gap-2">
              {scard && (
                <span data-testid="rmx-scorecard"
                  className={`text-[10px] font-bold px-2 py-1 rounded-lg border ${scard.alert ? "bg-rose-50 border-rose-200 text-rose-700" : "bg-stone-50 border-stone-200 text-stone-600"}`}>
                  Tahmin Karnesi: {scard.overall_mape != null ? `MAPE %${scard.overall_mape} (${scard.scored} skor)` : "henüz skor yok — tahminler kaydediliyor"}
                  {scard.alert ? " ⚠ SAPMA" : ""}
                </span>
              )}
              {mlp?.empty_risk_dates?.length > 0 && (
                <button onClick={applyCampaigns} disabled={busy === "camp"} data-testid="rmx-apply-campaigns"
                  className="px-3 py-1.5 text-[11px] font-bold rounded-lg bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50">
                  {busy === "camp" ? "Uygulanıyor…" : `Riskli ${mlp.empty_risk_dates.length} Geceye Fence'li Kampanya (1 tık)`}
                </button>
              )}
            </div>
          </div>
          <p className="text-[10px] text-stone-400 mb-2">{mlp?.note}</p>
          {camps.length > 0 && (
            <div className="text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 mb-2" data-testid="rmx-camp-active">
              ✓ {camps.length} gecede aktif fence'li kampanya (üye fiyatı %8, min 2 gece): {camps.slice(0, 5).map((c) => c.date).join(", ")}{camps.length > 5 ? "…" : ""}
            </div>
          )}
          {campImpact?.stats?.measured > 0 && (
            <div className="text-[11px] text-stone-600 bg-stone-50 border border-stone-200 rounded-lg px-3 py-2 mb-2" data-testid="rmx-camp-impact">
              📈 Kampanya Etki Takibi: {campImpact.stats.measured} gece ölçüldü · ortalama pickup +{campImpact.stats.avg_pickup_gain} oda · başarı %{campImpact.stats.success_rate} — robot bu dersi kalıcı hafızasına işliyor
            </div>
          )}
          {mlp?.empty_risk_dates?.length > 0 && (
            <div className="text-[11px] font-bold text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 mb-2" data-testid="rmx-ml-risk">
              Boş gece riski (&lt;%50 tahmini): {mlp.empty_risk_dates.slice(0, 6).join(", ")}
            </div>
          )}
          {mlp?.hot_dates?.length > 0 && (
            <div className="text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 mb-2" data-testid="rmx-ml-hot">
              Sıcak günler (≥%90): {mlp.hot_dates.slice(0, 6).join(", ")} — fiyat artış penceresi
            </div>
          )}
          {(!mlp?.days || mlp.days.length === 0) ? (
            <div className="text-xs text-stone-500 py-6 text-center">Tahmin üretilemedi.</div>
          ) : (
            <table className="w-full text-xs mt-2">
              <thead><tr className="text-left text-stone-400 border-b border-stone-100">
                <th className="py-1.5">Tarih</th><th>Gün kala</th><th>OTB</th><th>Son 7g pickup</th>
                <th>ML nihai oda</th><th>ML doluluk</th><th>Naif</th><th>Durum</th></tr></thead>
              <tbody>
                {mlp.days.map((r) => (
                  <tr key={r.date} className={`border-b border-stone-50 ${r.risk === "bos_gece" ? "bg-rose-50/50" : r.risk === "sicak" ? "bg-emerald-50/50" : ""}`}>
                    <td className="py-1.5 font-semibold text-stone-700">{r.date}</td>
                    <td>T-{r.days_out}</td><td>{r.otb}</td><td>{r.pickup_last7}</td>
                    <td className="font-bold">{r.ml_final_rooms}</td>
                    <td className={`font-bold ${r.ml_final_occ_pct < 50 ? "text-rose-600" : r.ml_final_occ_pct >= 90 ? "text-emerald-600" : "text-stone-700"}`}>%{r.ml_final_occ_pct}</td>
                    <td className="text-stone-400">{r.naive_final_rooms}</td>
                    <td>{r.risk === "bos_gece" ? "⚠ boş gece" : r.risk === "sicak" ? "▲ sıcak" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "explore" && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="rmx-explore">
          <div className="text-sm font-semibold text-stone-900 mb-1">Keşif Sonuç Raporu
            <span className="text-[10px] text-stone-400 font-normal ml-2">optimizer'ın kontrollü rastgele denemeleri — kazandırdı mı, kaybettirdi mi?</span>
          </div>
          <p className="text-[11px] text-stone-500 mb-3">{explore?.note}</p>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
            {[
              { l: "Toplam deneme", v: explore?.total_experiments ?? 0, t: "rmx-exp-total" },
              { l: "Bekleyen (tarih gelmedi)", v: explore?.pending ?? 0, t: "rmx-exp-pending" },
              { l: "Ölçülen", v: explore?.measured ?? 0, t: "rmx-exp-measured" },
              { l: "İşe yaradı / Zarar", v: `${explore?.verdicts?.worked ?? 0} / ${explore?.verdicts?.hurt ?? 0}`, t: "rmx-exp-verdicts" },
              { l: "Temiz esneklik", v: explore?.clean_elasticity ?? "—", t: "rmx-exp-elasticity" },
            ].map((k) => (
              <div key={k.t} className="bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5" data-testid={k.t}>
                <div className="text-lg font-black text-stone-900">{k.v}</div>
                <div className="text-[10px] text-stone-500">{k.l}</div>
              </div>
            ))}
          </div>
          {(!explore?.rows || explore.rows.length === 0) ? (
            <div className="text-xs text-stone-500 py-4 text-center">Henüz ölçülmüş deneme yok — keşif kararlarının tarihleri geçtikçe sonuçlar burada birikecek.</div>
          ) : (
            <table className="w-full text-xs">
              <thead><tr className="text-left text-stone-400 border-b border-stone-100">
                <th className="py-1.5">Tarih</th><th>Deneme</th><th>Gün kala</th><th>Baseline doluluk</th><th>Nihai doluluk</th><th>Sonuç</th></tr></thead>
              <tbody>{explore.rows.map((r, i) => (
                <tr key={i} className="border-b border-stone-50">
                  <td className="py-1.5 font-semibold text-stone-700">{r.date}</td>
                  <td className={r.delta_pct > 0 ? "text-emerald-600 font-bold" : "text-amber-600 font-bold"}>%{r.delta_pct > 0 ? "+" : ""}{r.delta_pct}</td>
                  <td>T-{r.days_out}</td><td>%{r.baseline_occ}</td><td>%{r.final_occ}</td>
                  <td>{r.verdict === "worked" ? "✓ işe yaradı" : r.verdict === "hurt" ? "✗ zarar" : "— nötr"}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      )}

      {tab === "library" && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="rmx-library">
          <div className="text-sm font-semibold text-stone-900 mb-1">Derin Bilgi Kütüphanesi
            <span className="text-[10px] text-stone-400 font-normal ml-2">{lib.total} kayıt — RMS çalışma prensipleri, akademik vakalar, eğitim müfredatı, teknik modeller. Chat robotu sorunuza göre buradan otomatik beslenir.</span>
          </div>
          <div className="flex gap-2 mb-3 flex-wrap">
            <input value={libQ} onChange={(e) => setLibQ(e.target.value)} data-testid="rmx-lib-search"
              placeholder="Ara: pickup, overbooking, IHG, esneklik, displacement…"
              className="flex-1 min-w-[220px] px-3 py-2 text-xs border border-stone-300 rounded-lg" />
            <select value={libCat} onChange={(e) => setLibCat(e.target.value)} data-testid="rmx-lib-cat"
              className="px-2 py-2 text-xs border border-stone-300 rounded-lg bg-white">
              <option value="">Tüm kategoriler</option>
              {lib.categories.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
            </select>
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {lib.items.map((d) => (
              <div key={d.id} className="border border-stone-200 rounded-xl p-4 bg-stone-50/50" data-testid={`rmx-lib-${d.id}`}>
                <div className="text-[10px] font-black uppercase text-indigo-600 mb-1">{d.category.replace(/_/g, " ")}</div>
                <div className="text-sm font-semibold text-stone-900 mb-1">{d.title}</div>
                <div className="text-xs text-stone-600 leading-relaxed">{d.body}</div>
              </div>
            ))}
            {lib.items.length === 0 && <div className="text-xs text-stone-500 py-6 text-center col-span-2">Sonuç bulunamadı.</div>}
          </div>
        </div>
      )}

      {tab === "sensitivity" && (
        <div className="bg-white border border-stone-200 rounded-xl p-5" data-testid="rmx-sensitivity">
          <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
            <div className="text-sm font-semibold text-stone-900">Fiyat Duyarlılığı (Elasticity)</div>
            <button onClick={analyze} disabled={busy === "sens"} data-testid="rmx-analyze-sens"
              className="px-3 py-2 text-xs rounded-md bg-stone-900 text-white hover:bg-stone-700 disabled:opacity-50 font-medium">
              {busy === "sens" ? "Analiz ediliyor…" : "Analiz Et"}
            </button>
          </div>
          <p className="text-[11px] text-stone-500 mb-3">{sens?.note}</p>
          {(!sens?.buckets || sens.buckets.length === 0) ? (
            <div className="text-xs text-stone-500 py-6 text-center">Henüz ölçüm yok — fiyat kararı sonuçları biriktikçe esneklik burada belirir.</div>
          ) : (
            <table className="w-full text-xs">
              <thead><tr className="text-left text-stone-400 border-b border-stone-100">
                <th className="py-1.5">Bağlam</th><th>Esneklik</th><th>Sınıf</th><th>Örneklem</th><th>Uzman Tavsiyesi</th></tr></thead>
              <tbody>
                {sens.buckets.map((b) => (
                  <tr key={b.bucket} className="border-b border-stone-50" data-testid={`rmx-sens-${b.bucket}`}>
                    <td className="py-2 text-stone-700 font-semibold">{b.dow_type === "weekend" ? "Hafta sonu" : "Hafta içi"} · {b.band} gün kala</td>
                    <td className={`font-bold ${Math.abs(b.elasticity) >= 1 ? "text-rose-600" : Math.abs(b.elasticity) >= 0.3 ? "text-amber-600" : "text-emerald-600"}`}>{b.elasticity}</td>
                    <td className="text-stone-600">{b.label}</td>
                    <td className="text-stone-500">{b.samples}</td>
                    <td className="text-stone-600">{b.advice}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "principles" && (
        <div className="grid md:grid-cols-2 gap-3" data-testid="rmx-principles">
          {knowledge.filter((k) => k.category === "prensipler" || k.category === "stratejiler").map((k) => (
            <div key={k.id} className="bg-white border border-stone-200 rounded-xl p-4" data-testid={`rmx-card-${k.id}`}>
              <div className="text-[10px] font-black uppercase text-amber-600 mb-1">{CAT_TR[k.category]}</div>
              <div className="text-sm font-semibold text-stone-900 mb-1">{k.title}</div>
              <div className="text-xs text-stone-600 leading-relaxed">{k.body}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "market" && (
        <div className="grid md:grid-cols-2 gap-3" data-testid="rmx-market">
          {knowledge.filter((k) => k.category === "rakipler" || k.category === "pazar").map((k) => (
            <div key={k.id} className={`border rounded-xl p-4 ${k.category === "pazar" ? "bg-sky-50/60 border-sky-100" : "bg-white border-stone-200"}`} data-testid={`rmx-card-${k.id}`}>
              <div className={`text-[10px] font-black uppercase mb-1 ${k.category === "pazar" ? "text-sky-600" : "text-violet-600"}`}>{CAT_TR[k.category]}</div>
              <div className="text-sm font-semibold text-stone-900 mb-1">{k.title}</div>
              <div className="text-xs text-stone-600 leading-relaxed">{k.body}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
