import React, { useEffect, useRef, useState } from "react";
import { X, ArrowRight, ArrowLeft, Robot } from "@phosphor-icons/react";

const STEPS = [
  { title: "Revenue Robotu'na hoş geldiniz", body: "Bu panel; öğrenen hafızayı, ML tahmin motorunu ve AI stratejisti tek çatı altında toplar. 1 dakikalık turla tüm yetenekleri tanıyalım." },
  { target: "brain-main-tabs", title: "3 uzmanlık alanı", body: "Öğrenme & Hafıza: ölçülen kararlar ve kalıcı dersler. Alan Uzmanlığı: ML pickup tahmini, keşif modu, rakip pazarı. AI Strateji: analiz + tek tıkla fiyat uygulama." },
  { target: "robot-impact-card", title: "Robot Başarı Panosu", body: "Robotun bu ayki tahmini kâr katkısını tek bakışta gösterir: fiyat kararlarının ölçülen etkisi + kampanya pickup geliri." },
  { target: "brain-kpi-outcomes", title: "Ölçülen kararlar", body: "Robot verdiği her fiyat kararının gerçek sonucunu (doluluk değişimi) ölçer; başarı oranı ve zarar veren kararlar burada birikir." },
  { target: "brain-goal-card", title: "Aylık gelir hedefi", body: "Hedef girin — robot ay sonu projeksiyonunu izler, geride kalırsanız somut fiyat/kampanya önerisi üretir." },
  { target: "brain-permanent-memory", title: "Kalıcı Hafıza", body: "Kritik dersler asla silinmez. Her ders için 'Kapatılırsa ne olur?' simülasyonu vardır. Bölgesel ve küresel hafıza, yeni otellere önsel olarak aktarılır." },
  { tab: "expertise", click: "rmx-tab-mlpickup", target: "rmx-mlpickup", title: "ML Pickup Tahmini", body: "LightGBM makine öğrenmesi modeli her gece için oda pickup tahmini üretir; doğruluğu MAPE karnesiyle izlenir ve boş geceler için otomatik kampanya önerilir." },
  { tab: "expertise", click: "rmx-tab-explore", target: "rmx-explore", title: "Keşif Modu", body: "Kontrollü rastgele fiyat testleriyle talep esnekliğini öğrenir; her testin sonucu ölçülüp hafızaya işlenir." },
  { tab: "strategist", target: "revenue-strategist-panel", title: "AI Strateji", body: "'Şimdi Analiz Et' ile AI destekli rapor ve aksiyon önerileri üretir; önerileri tek tıkla fiyatlara uygular. Robotla sohbet ederek de komut verebilirsiniz." },
  { tab: "memory", title: "Hazırsınız! 🚀", body: "Turu istediğiniz an üstteki 'Tanıtım Turu' butonuyla tekrar izleyebilirsiniz. İyi gelirler!" },
];

export default function RevenueRobotTour({ open, onClose, setMainTab }) {
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);
  const timer = useRef(null);

  useEffect(() => { if (open) setI(0); }, [open]);

  useEffect(() => {
    if (!open) return;
    const step = STEPS[i];
    if (step.tab) setMainTab(step.tab);
    setRect(null);
    let tries = 0;
    const find = () => {
      tries += 1;
      if (step.click) {
        const btn = document.querySelector(`[data-testid="${step.click}"]`);
        if (btn) btn.click();
      }
      const el = step.target ? document.querySelector(`[data-testid="${step.target}"]`) : null;
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        timer.current = setTimeout(() => {
          const r = el.getBoundingClientRect();
          setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
        }, 450);
      } else if (step.target && tries < 15) {
        timer.current = setTimeout(find, 300);
      }
    };
    find();
    return () => clearTimeout(timer.current);
  }, [open, i, setMainTab]);

  if (!open) return null;
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  const cardW = 380;
  let cardStyle;
  if (rect) {
    const below = rect.top + rect.height + 12;
    const top = below + 230 > window.innerHeight ? Math.max(rect.top - 235, 16) : below;
    const left = Math.min(Math.max(rect.left, 16), window.innerWidth - cardW - 16);
    cardStyle = { position: "fixed", top, left, width: cardW, zIndex: 1002 };
  } else {
    cardStyle = { position: "fixed", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: cardW, zIndex: 1002 };
  }

  return (
    <div data-testid="revenue-robot-tour">
      {rect ? (
        <div style={{
          position: "fixed", top: rect.top - 6, left: rect.left - 6,
          width: rect.width + 12, height: rect.height + 12,
          borderRadius: 12, border: "2px solid #8b5cf6",
          boxShadow: "0 0 0 9999px rgba(15,12,10,0.72)",
          zIndex: 1000, pointerEvents: "none", transition: "all 0.25s ease",
        }} />
      ) : (
        <div style={{ position: "fixed", inset: 0, background: "rgba(15,12,10,0.72)", zIndex: 1000 }} />
      )}
      <div style={{ position: "fixed", inset: 0, zIndex: 1001 }} />

      <div style={cardStyle} className="bg-white rounded-2xl shadow-2xl p-5" data-testid="tour-step-card">
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-violet-100 flex items-center justify-center shrink-0">
              <Robot size={18} weight="fill" className="text-violet-600" />
            </div>
            <div className="text-sm font-bold text-stone-900" data-testid="tour-step-title">{step.title}</div>
          </div>
          <button onClick={onClose} data-testid="tour-close-btn" className="text-stone-400 hover:text-stone-700">
            <X size={16} weight="bold" />
          </button>
        </div>
        <p className="text-xs text-stone-600 leading-relaxed mb-4" data-testid="tour-step-body">{step.body}</p>
        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            {STEPS.map((_, idx) => (
              <span key={idx} className={`w-1.5 h-1.5 rounded-full ${idx === i ? "bg-violet-600" : "bg-stone-200"}`} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {i > 0 && (
              <button onClick={() => setI(i - 1)} data-testid="tour-prev-btn"
                className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-stone-200 text-stone-600 hover:border-stone-400 inline-flex items-center gap-1">
                <ArrowLeft size={12} /> Geri
              </button>
            )}
            <button onClick={() => (last ? onClose() : setI(i + 1))} data-testid="tour-next-btn"
              className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-violet-600 text-white hover:bg-violet-700 inline-flex items-center gap-1">
              {last ? "Bitir" : "İleri"} {!last && <ArrowRight size={12} weight="bold" />}
            </button>
          </div>
        </div>
        <div className="mt-2 text-[10px] text-stone-400 text-right">{i + 1} / {STEPS.length}</div>
      </div>
    </div>
  );
}
