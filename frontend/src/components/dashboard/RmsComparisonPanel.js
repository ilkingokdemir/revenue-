import React, { useEffect, useState, useCallback } from "react";
import {
  Trophy, CheckCircle, Brain, Sparkle, Flask, Target, ShieldCheck, Pulse, ChartLineUp, Robot, Medal,
  Presentation, X, ArrowLeft, ArrowRight,
} from "@phosphor-icons/react";

const COMPETITORS = [
  {
    name: "IDeaS G3 (SAS)", segment: "Büyük zincirler",
    edge: "Oda tipi + rate-code seviyesinde derin tahminleme, akıllı MLOS, gelişmiş grup displacement",
    ours: "Oda tipi bağımsız forecast + 24 ay forecast + belirsizlik bandı; AI MLOS/CTA kısıtlama önerileri; shoulder-night'lı grup displacement + ±30 gün alternatif tarih motoru",
    modules: ["Oda tipi forecast", "Restriction Advisor", "Grup Displacement"],
  },
  {
    name: "Duetto", segment: "Butik / lüks gruplar",
    edge: "Open Pricing — segment × kanal × oda tipi bağımsız fiyat, TRevPOR odağı",
    ours: "Open Pricing Optimizer hücre bazlı bağımsız fiyat üretir; RevPAM (toplantı salonu) + ABS (özellik satışı) ile toplam gelir yönetimi",
    modules: ["Open Pricing matrisi", "RevPAM", "ABS"],
  },
  {
    name: "Atomize (Mews)", segment: "Bağımsız oteller",
    edge: "Gerçek zamanlı otopilot fiyatlama (günlük batch değil, anlık)",
    ours: "Gün-içi re-price (pickup spike tetikli) + auto-apply + ±15% guardrail + 1-tık overbooking otomasyonu",
    modules: ["Intraday Reprice", "Optimizer Guardrail"],
  },
  {
    name: "FLYR (Pace)", segment: "Ticari ekipler",
    edge: "Grup fiyat önerisi + satış-revenue ortak karar akışı, shoulder-night displacement",
    ours: "TAM parite: komisyon-sonrası başabaş net fiyat + shoulder kaybı + alternatif tarih önerisi ('şu tarihe kaydırın, £X daha kârlı') + RFP yaşam döngüsü",
    modules: ["Group Sales OS", "Alternatif Tarih Motoru"],
  },
  {
    name: "BEONx / Propeter", segment: "Kârlılık odaklılar",
    edge: "Profit-first pricing: brüt ciro değil NET KÂR üzerinden fiyat (komisyon + oda maliyeti düşülmüş)",
    ours: "Net Contribution v2: CPOR + OTA komisyonu + ödeme ücreti + iade riski + kanal ancillary; gece yarısı Kâr Otopilotu zararlı kanala otomatik stop-sell açar",
    modules: ["Kâr-öncelikli fiyatlama", "Kâr Otopilotu"],
  },
  {
    name: "RoomPriceGenie", segment: "<50 oda",
    edge: "Aşırı basitlik, 2 saatte kurulum",
    ours: "BASİT/PRO mod ayrımı + kurulum sihirbazı + 18 ay fiyat ufku + ücretsiz Price Checker lead aracı",
    modules: ["Basit Mod", "Setup Wizard"],
  },
];

const UNIQUE = [
  { icon: Brain, title: "Öğrenen Revenue Beyni", desc: "Her fiyat kararının gerçek sonucunu ölçer; kalıcı + bölgesel + küresel hafıza. Yeni otel, portföy derslerini önsel olarak devralır." },
  { icon: ChartLineUp, title: "ML Pickup Motoru (LightGBM)", desc: "Gerçek makine öğrenmesi modeliyle gece bazlı pickup tahmini; MAPE karnesiyle doğruluk takibi." },
  { icon: Flask, title: "Keşif Modu", desc: "Kontrollü rastgele fiyat testleriyle talep esnekliğini kendisi öğrenir — rakiplerde yok." },
  { icon: Robot, title: "AI Copilot (Aksiyon Yürütür)", desc: "Sohbetten doğrudan fiyat güncelleyen, RM uzmanlık kütüphanesiyle beslenen copilot." },
  { icon: Target, title: "Robot Başarı Panosu", desc: "Robotun aylık kâr katkısı tek bakışta: günlük birikim grafiği + MTD gelir payı." },
  { icon: ShieldCheck, title: "Decision Assurance", desc: "P10/P50/P90 senaryolu, kanıtlı autopilot kararları + readback." },
  { icon: Pulse, title: "Data Quality Autopilot", desc: "Mapping drift, bayat fiyat, mükerrer rezervasyonu gece taramasıyla kendisi düzeltir." },
  { icon: Sparkle, title: "A/B Nedensel Etki", desc: "Holdout deneyleriyle fiyat kararlarının GERÇEK uplift'i ölçülür — gözlemsel değil nedensel." },
  { icon: Medal, title: "Tek Platform", desc: "PMS + RMS + Kanal + F&B + CRM tek çatıda — rakip RMS'ler yalnız fiyatlama katmanı." },
];

const TOTAL_SLIDES = 2 + COMPETITORS.length + 1; // giriş + 6 rakip + farklar + kapanış

export default function RmsComparisonPanel() {
  const [presenting, setPresenting] = useState(false);
  const [slide, setSlide] = useState(0);

  const next = useCallback(() => setSlide((s) => Math.min(s + 1, TOTAL_SLIDES - 1)), []);
  const prev = useCallback(() => setSlide((s) => Math.max(s - 1, 0)), []);

  useEffect(() => {
    if (!presenting) return;
    const onKey = (e) => {
      if (e.key === "ArrowRight" || e.key === " ") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key === "Escape") setPresenting(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [presenting, next, prev]);

  return (
    <div className="p-5 max-w-[1400px] mx-auto" data-testid="rms-comparison-panel">
      {presenting && <PresentationDeck slide={slide} next={next} prev={prev} exit={() => setPresenting(false)} />}

      <div className="bg-stone-900 rounded-2xl p-6 text-stone-100 mb-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-400 mb-2">
              <Trophy size={14} weight="fill" className="text-amber-400" />
              <span>2026 Pazar Denetimi · Satış Demosu</span>
            </div>
            <h1 className="text-2xl font-semibold">RMS Rakip Karşılaştırma</h1>
            <p className="text-sm text-stone-400 mt-1 max-w-2xl">
              En iyi 6 hotel revenue yazılımının fark yaratan özellikleri — ve her birinin bizdeki karşılığı.
            </p>
          </div>
          <button onClick={() => { setSlide(0); setPresenting(true); }} data-testid="rmsc-present-btn"
            className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-900 text-sm font-black inline-flex items-center gap-2">
            <Presentation size={16} weight="fill" /> Sunum Modu
          </button>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <Chip label="6 rakip analiz edildi" testId="rmsc-kpi-competitors" />
          <Chip label="6/6 özellik paritesi ✓" emerald testId="rmsc-kpi-parity" />
          <Chip label="9 benzersiz fark" violet testId="rmsc-kpi-unique" />
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden mb-6">
        <table className="w-full text-xs" data-testid="rmsc-table">
          <thead className="bg-stone-50 text-stone-500 uppercase text-[10px]">
            <tr>
              <th className="px-4 py-3 text-left">Rakip</th>
              <th className="px-4 py-3 text-left">Segment</th>
              <th className="px-4 py-3 text-left w-[28%]">Fark yaratan özelliği</th>
              <th className="px-4 py-3 text-left w-[34%]">Bizdeki karşılığı</th>
              <th className="px-4 py-3 text-left">Modüller</th>
            </tr>
          </thead>
          <tbody>
            {COMPETITORS.map((c) => (
              <tr key={c.name} className="border-t border-stone-100 align-top" data-testid={`rmsc-row-${c.name.split(" ")[0].toLowerCase()}`}>
                <td className="px-4 py-3 font-bold text-stone-900 whitespace-nowrap">{c.name}</td>
                <td className="px-4 py-3 text-stone-500">{c.segment}</td>
                <td className="px-4 py-3 text-stone-600">{c.edge}</td>
                <td className="px-4 py-3">
                  <div className="flex items-start gap-1.5">
                    <CheckCircle size={14} weight="fill" className="text-emerald-500 shrink-0 mt-0.5" />
                    <span className="text-stone-800">{c.ours}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {c.modules.map((m) => (
                      <span key={m} className="px-2 py-0.5 rounded-full bg-violet-50 border border-violet-100 text-violet-700 text-[10px] font-semibold whitespace-nowrap">{m}</span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="text-sm font-bold text-stone-900 mb-3 flex items-center gap-2">
        <Sparkle size={16} weight="fill" className="text-violet-500" /> Bizde olup rakiplerde olmayan 9 fark
      </h2>
      <div className="grid md:grid-cols-3 gap-3" data-testid="rmsc-unique-grid">
        {UNIQUE.map((u) => (
          <div key={u.title} className="bg-white border border-stone-200 rounded-xl p-4 hover:border-violet-300 transition-colors" data-testid={`rmsc-unique-${u.title.split(" ")[0].toLowerCase()}`}>
            <div className="w-8 h-8 rounded-lg bg-violet-50 flex items-center justify-center mb-2">
              <u.icon size={17} weight="fill" className="text-violet-600" />
            </div>
            <div className="text-xs font-bold text-stone-900">{u.title}</div>
            <div className="text-[11px] text-stone-500 mt-1 leading-relaxed">{u.desc}</div>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-stone-400 mt-5">
        Son denetim: Ağustos 2026 · Kaynaklar: kamuya açık ürün dokümantasyonları + iç modül envanteri. Satış demolarında kullanım için hazırlanmıştır.
      </p>
    </div>
  );
}

function PresentationDeck({ slide, next, prev, exit }) {
  const isFirst = slide === 0;
  const isUnique = slide === TOTAL_SLIDES - 2;
  const isLast = slide === TOTAL_SLIDES - 1;
  const comp = !isFirst && !isUnique && !isLast ? COMPETITORS[slide - 1] : null;

  return (
    <div className="fixed inset-0 z-[1100] bg-stone-950 text-stone-100 flex flex-col" data-testid="rmsc-slide-deck">
      <div className="flex items-center justify-between px-8 py-4 shrink-0">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-stone-500">
          <Trophy size={14} weight="fill" className="text-amber-400" /> RMS Rakip Karşılaştırma · 2026
        </div>
        <button onClick={exit} data-testid="rmsc-slide-exit" className="text-stone-500 hover:text-white p-2">
          <X size={20} weight="bold" />
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center px-10 md:px-24 overflow-y-auto" data-testid="rmsc-slide">
        {isFirst && (
          <div className="text-center max-w-3xl">
            <div className="text-amber-400 text-sm font-black uppercase tracking-[0.3em] mb-6">Satış Sunumu</div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black leading-tight">Dünyanın en iyi 6 RMS'i.<br /><span className="text-violet-400">Hepsinin gücü tek platformda.</span></h1>
            <div className="flex justify-center gap-3 mt-10">
              <Chip label="6/6 özellik paritesi ✓" emerald />
              <Chip label="9 benzersiz fark" violet />
            </div>
            <p className="text-stone-500 text-sm mt-10">→ tuşu veya İleri ile ilerleyin · ESC ile çıkın</p>
          </div>
        )}
        {comp && (
          <div className="max-w-4xl w-full">
            <div className="text-stone-500 text-xs font-bold uppercase tracking-[0.25em] mb-2">Rakip {slide} / {COMPETITORS.length} · {comp.segment}</div>
            <h2 className="text-4xl font-black mb-10">{comp.name}</h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="bg-stone-900 border border-stone-800 rounded-2xl p-6">
                <div className="text-[11px] font-black uppercase tracking-wider text-stone-500 mb-3">Onların kozu</div>
                <p className="text-lg text-stone-300 leading-relaxed">{comp.edge}</p>
              </div>
              <div className="bg-emerald-950/40 border border-emerald-800/50 rounded-2xl p-6">
                <div className="text-[11px] font-black uppercase tracking-wider text-emerald-400 mb-3 flex items-center gap-1.5">
                  <CheckCircle size={14} weight="fill" /> Bizdeki karşılığı
                </div>
                <p className="text-lg text-emerald-100 leading-relaxed">{comp.ours}</p>
                <div className="flex flex-wrap gap-1.5 mt-4">
                  {comp.modules.map((m) => (
                    <span key={m} className="px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-bold">{m}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
        {isUnique && (
          <div className="max-w-5xl w-full">
            <h2 className="text-3xl font-black mb-8 flex items-center gap-3">
              <Sparkle size={28} weight="fill" className="text-violet-400" /> Bizde olup rakiplerde olmayan 9 fark
            </h2>
            <div className="grid md:grid-cols-3 gap-4">
              {UNIQUE.map((u) => (
                <div key={u.title} className="bg-stone-900 border border-stone-800 rounded-xl p-4">
                  <u.icon size={20} weight="fill" className="text-violet-400 mb-2" />
                  <div className="text-sm font-bold">{u.title}</div>
                  <div className="text-xs text-stone-400 mt-1 leading-relaxed">{u.desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        {isLast && (
          <div className="text-center max-w-3xl">
            <h2 className="text-4xl sm:text-5xl font-black leading-tight">Tek platform.<br /><span className="text-emerald-400">6/6 parite.</span> <span className="text-violet-400">9 benzersiz fark.</span></h2>
            <p className="text-xl text-stone-400 mt-8">PMS + RMS + Kanal + F&B + CRM — ayrı ayrı 5 yazılımın işini tek abonelikle yapın.</p>
            <p className="text-stone-500 text-sm mt-10">Teşekkürler 🙌 · ESC ile sunumdan çıkın</p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between px-8 py-5 shrink-0">
        <button onClick={prev} disabled={isFirst} data-testid="rmsc-slide-prev"
          className="px-4 py-2 rounded-lg border border-stone-700 text-stone-300 hover:border-stone-500 text-sm font-bold disabled:opacity-30 inline-flex items-center gap-1.5">
          <ArrowLeft size={14} weight="bold" /> Geri
        </button>
        <div className="flex gap-1.5">
          {Array.from({ length: TOTAL_SLIDES }).map((_, i) => (
            <span key={i} className={`w-2 h-2 rounded-full ${i === slide ? "bg-amber-400" : "bg-stone-700"}`} />
          ))}
        </div>
        <button onClick={isLast ? exit : next} data-testid="rmsc-slide-next"
          className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-stone-900 text-sm font-black inline-flex items-center gap-1.5">
          {isLast ? "Bitir" : "İleri"} {!isLast && <ArrowRight size={14} weight="bold" />}
        </button>
      </div>
    </div>
  );
}

function Chip({ label, emerald, violet, testId }) {
  const cls = emerald ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
    : violet ? "bg-violet-500/15 text-violet-300 border-violet-500/30"
    : "bg-stone-700/60 text-stone-300 border-stone-600";
  return <span className={`px-3 py-1 rounded-full border text-[11px] font-bold ${cls}`} data-testid={testId}>{label}</span>;
}
