import { motion } from "framer-motion";
import { Brain, Ruler, GraduationCap, SlidersHorizontal, Zap, ArrowRight, TrendingUp } from "lucide-react";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.55, ease: "easeOut" },
};

const LOOP = [
  { icon: Ruler, title: "Ölçer", desc: "Her fiyat kararının gerçek sonucunu doluluk ve pickup ile karşılaştırır." },
  { icon: GraduationCap, title: "Öğrenir", desc: "Bağlam bazlı dersler çıkarır: hangi günlerde zam işe yarıyor, hangilerinde zarar veriyor." },
  { icon: SlidersHorizontal, title: "Kendini Ayarlar", desc: "Kötü sonuç veren bağlamlarda motoru frenler, başarılı bağlamlarda cesaretlendirir." },
  { icon: Zap, title: "Uygular", desc: "Ayarlanmış stratejiyi otomatik uygular ve döngü yeniden başlar — her gece." },
];

const SAMPLE_LESSONS = [
  { text: "Hafta içi 1-3 hafta kala yapılan fiyat artışları 6 denemenin 4'ünde talebi düşürdü — motor bu bağlamda değişimi ×0.95 ile frenliyor.", tone: "amber" },
  { text: "Hafta sonu son 3 gün fiyat artışları %78 başarıyla sonuçlandı — motor bu bağlamda ×1.03 ile daha cesur.", tone: "emerald" },
  { text: "STR doluluk baskısı %90'ı aşan tarihlerde uygulanan zamlar doluluğu hiç düşürmedi — sinyal ağırlığı artırıldı.", tone: "violet" },
];

export default function BrainShowcaseSection({ onDemo }) {
  return (
    <section id="brain" className="relative border-t border-white/10 bg-[#070B14] py-24 overflow-hidden">
      <div className="absolute top-[-60px] left-[10%] w-[380px] h-[380px] rounded-full bg-violet-600/12 blur-3xl" aria-hidden="true" />
      <div className="relative max-w-7xl mx-auto px-5 sm:px-8">
        <motion.div {...fadeUp} className="max-w-2xl mb-14">
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-violet-400 mb-3 inline-flex items-center gap-2">
            <Brain size={14} /> Öğrenen Revenue Beyni
          </div>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight text-white">
            Kararlarının sonuçlarından <span className="bg-gradient-to-r from-violet-400 to-fuchsia-300 bg-clip-text text-transparent">ders çıkaran</span> tek RMS
          </h2>
          <p className="mt-4 text-stone-400 leading-relaxed">
            Çoğu sistem fiyat önerir ve unutur. ReveniQ her kararın gerçek etkisini ölçer, öğrendiğini hafızasına yazar ve fiyat motorunu otel özelinde otomatik kalibre eder. Ay sonu gelir hedefinize giden yolu her gün yeniden hesaplar.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-12 gap-10 items-start">
          {/* Kapalı döngü */}
          <motion.div {...fadeUp} className="lg:col-span-5 space-y-3" data-testid="brain-loop-steps">
            {LOOP.map((s, i) => (
              <div key={s.title} className="relative flex gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-4 hover:border-violet-400/40 transition-colors">
                <div className="w-10 h-10 shrink-0 rounded-xl bg-violet-500/15 border border-violet-400/25 flex items-center justify-center text-violet-300">
                  <s.icon size={18} />
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">{i + 1}. {s.title}</div>
                  <div className="text-xs text-stone-400 mt-1 leading-relaxed">{s.desc}</div>
                </div>
                {i < LOOP.length - 1 && (
                  <div className="absolute left-[35px] bottom-[-14px] h-[14px] w-px bg-gradient-to-b from-violet-400/40 to-transparent" aria-hidden="true" />
                )}
              </div>
            ))}
          </motion.div>

          {/* Canlı ders örnekleri */}
          <motion.div {...fadeUp} className="lg:col-span-7" data-testid="brain-sample-lessons">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="text-sm font-semibold text-white inline-flex items-center gap-2">
                  <GraduationCap size={16} className="text-violet-300" /> Beynin çıkardığı ders örnekleri
                </div>
                <span className="text-[10px] px-2 py-1 rounded-full bg-violet-500/15 border border-violet-400/30 text-violet-300 font-bold uppercase tracking-wider">Gerçek formatta</span>
              </div>
              <div className="space-y-3">
                {SAMPLE_LESSONS.map((l, i) => (
                  <div key={i} className={`rounded-xl border p-3.5 text-xs leading-relaxed ${
                    l.tone === "amber" ? "border-amber-400/25 bg-amber-500/[0.06] text-amber-100/90" :
                    l.tone === "emerald" ? "border-emerald-400/25 bg-emerald-500/[0.06] text-emerald-100/90" :
                    "border-violet-400/25 bg-violet-500/[0.06] text-violet-100/90"}`}>
                    🧠 {l.text}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-3 gap-3 mt-5">
                <Stat value="Her gece" label="otomatik öğrenme döngüsü" />
                <Stat value="Bağlam bazlı" label="öğrenilmiş fiyat çarpanları" />
                <Stat value="Hedef odaklı" label="ay sonu gelir projeksiyonu" />
              </div>
              <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-gradient-to-r from-violet-500/15 to-fuchsia-500/10 border border-violet-400/25 p-4">
                <div className="text-xs text-stone-300 inline-flex items-center gap-2">
                  <TrendingUp size={14} className="text-violet-300" />
                  Dersler AI Strateji Robotu'na otomatik beslenir — stratejiler geçmişten öğrenir.
                </div>
                <button onClick={onDemo} data-testid="brain-showcase-demo-cta"
                  className="px-5 py-2.5 rounded-xl bg-violet-500 text-sm font-semibold text-white hover:bg-violet-400 inline-flex items-center gap-2 transition-colors">
                  Beyni Çalışırken Gör <ArrowRight size={15} />
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function Stat({ value, label }) {
  return (
    <div className="rounded-xl bg-white/[0.04] border border-white/10 p-3 text-center">
      <div className="text-sm font-bold text-white">{value}</div>
      <div className="text-[10px] text-stone-400 mt-0.5">{label}</div>
    </div>
  );
}
