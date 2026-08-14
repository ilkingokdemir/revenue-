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
    } catch { toast.error("Uzmanlık verileri yüklenemedi"); }
  }, [propertyId]);
  useEffect(() => { load(); }, [load]);

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

  const TABS = [
    { id: "brief", label: "Uzman Brifingi", icon: Sparkle },
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
