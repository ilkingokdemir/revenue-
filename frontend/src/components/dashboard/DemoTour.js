import React, { useEffect, useState, useCallback } from "react";

const STEPS = [
  { selector: '[data-testid="demo-mode-active-strip"]', title: "🎬 Demo Veri Modu",
    text: "25 gerçekçi örnek rezervasyon yüklendi. Gerçek verinle karışmaz — işin bitince buradaki 'Demo Verisini Temizle' ile tek tıkla silersin." },
  { selector: '[data-testid="today-kpi-row"]', title: "📊 Canlı KPI'ların",
    text: "Doluluk, bugünkü gelir, ADR ve RevPAR artık dolu. Bu kutular her rezervasyonla anlık güncellenir." },
  { selector: '[data-testid="sidebar-calendar"]', title: "🗓️ Rezervasyon Takvimi",
    text: "Tüm demo rezervasyonları takvimde oda oda görebilir, sürükleyerek taşıyabilirsin." },
  { selector: '[data-testid="ai-copilot-btn"]', title: "🤖 AI Copilot",
    text: "Günlük 'bugün ne yapmalıyım?' listesi ve fiyat önerileri burada. Demo veriyle önerilerin nasıl çalıştığını hemen görebilirsin." },
  { selector: '[data-testid="branch-selector-container"]', title: "🏨 Şube Seçici",
    text: "Birden çok oteli tek panelden yönetirsin — şubeler arası buradan geçilir. Tur bitti, keşfetmeye başla!" },
];

export const DemoTour = ({ onClose }) => {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);

  const steps = STEPS.filter((s) => document.querySelector(s.selector));
  const step = steps[i];

  const measure = useCallback(() => {
    if (!step) return;
    const el = document.querySelector(step.selector);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    setTimeout(() => setRect(el.getBoundingClientRect()), 350);
  }, [step]);

  useEffect(() => { measure(); }, [measure]);
  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  if (!step) return null;
  const finish = () => { try { localStorage.setItem("mhb_demo_tour_done", "1"); } catch { /* ignore */ } onClose(); };

  const tooltipTop = rect ? Math.min(Math.max(rect.bottom + 12, 16), window.innerHeight - 190) : 100;
  const tooltipLeft = rect ? Math.min(Math.max(rect.left, 16), window.innerWidth - 360) : 100;

  return (
    <div className="fixed inset-0 z-[90]" data-testid="demo-tour-overlay">
      <div className="absolute inset-0 bg-black/60" onClick={finish} />
      {rect && (
        <div className="absolute rounded-xl ring-4 ring-indigo-400 pointer-events-none transition-all duration-300"
          style={{ top: rect.top - 6, left: rect.left - 6, width: rect.width + 12, height: rect.height + 12,
                   boxShadow: "0 0 0 9999px rgba(0,0,0,0.6)" }} />
      )}
      <div className="absolute w-[340px] bg-white rounded-2xl shadow-2xl p-4 transition-all duration-300"
        style={{ top: tooltipTop, left: tooltipLeft }} data-testid="demo-tour-tooltip">
        <div className="text-sm font-black text-stone-900">{step.title}</div>
        <div className="text-xs text-stone-600 mt-1.5 leading-relaxed">{step.text}</div>
        <div className="flex items-center gap-1.5 mt-3">
          {steps.map((_, k) => (
            <span key={k} className={`w-1.5 h-1.5 rounded-full ${k === i ? "bg-indigo-600" : "bg-stone-300"}`} />
          ))}
          <div className="flex-1" />
          <button onClick={finish} data-testid="demo-tour-skip"
            className="px-2.5 py-1.5 rounded-lg text-[11px] font-bold text-stone-500 hover:bg-stone-100">Geç</button>
          {i > 0 && (
            <button onClick={() => setI(i - 1)} data-testid="demo-tour-prev"
              className="px-2.5 py-1.5 rounded-lg border border-stone-200 text-[11px] font-bold text-stone-700 hover:bg-stone-50">← Geri</button>
          )}
          {i < steps.length - 1 ? (
            <button onClick={() => setI(i + 1)} data-testid="demo-tour-next"
              className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-[11px] font-black hover:bg-indigo-700">İleri →</button>
          ) : (
            <button onClick={finish} data-testid="demo-tour-finish"
              className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-[11px] font-black hover:bg-emerald-700">Bitir ✓</button>
          )}
        </div>
      </div>
    </div>
  );
};

export default DemoTour;
