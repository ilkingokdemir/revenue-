import React, { useState } from "react";
import { motion } from "framer-motion";

export default function RoiCalculatorSection({ onDemo }) {
  const [rooms, setRooms] = useState(60);
  const [adr, setAdr] = useState(120);
  const [occ, setOcc] = useState(68);

  const currentRevenue = rooms * adr * (occ / 100) * 365;
  const upliftPct = occ < 55 ? 0.14 : occ < 75 ? 0.10 : 0.07;
  const gain = currentRevenue * upliftPct;
  const fmt = (v) => `£${Math.round(v).toLocaleString("en-GB")}`;

  return (
    <section id="roi" className="relative max-w-7xl mx-auto px-5 sm:px-8 py-24" data-testid="roi-calculator-section">
      <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="max-w-2xl mb-10">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-400 mb-3">ROI Calculator</div>
        <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">See your potential <span className="bg-gradient-to-r from-emerald-300 to-lime-300 bg-clip-text text-transparent">RevPAR gain</span></h2>
        <p className="mt-4 text-stone-400">Move the sliders — based on published customer outcomes across similar portfolios.</p>
      </motion.div>
      <div className="grid lg:grid-cols-2 gap-8 items-center">
        <div className="space-y-7 bg-white/5 border border-white/10 rounded-2xl p-7 backdrop-blur">
          {[
            { label: "Rooms", val: rooms, set: setRooms, min: 10, max: 500, suffix: "" },
            { label: "Average Daily Rate", val: adr, set: setAdr, min: 40, max: 500, suffix: " £" },
            { label: "Occupancy", val: occ, set: setOcc, min: 30, max: 95, suffix: " %" },
          ].map((s) => (
            <div key={s.label}>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-stone-300">{s.label}</span>
                <span className="font-bold text-white" data-testid={`roi-val-${s.label.split(" ")[0].toLowerCase()}`}>{s.val}{s.suffix}</span>
              </div>
              <input type="range" min={s.min} max={s.max} value={s.val}
                onChange={(e) => s.set(Number(e.target.value))}
                data-testid={`roi-slider-${s.label.split(" ")[0].toLowerCase()}`}
                className="w-full accent-emerald-400" />
            </div>
          ))}
        </div>
        <div className="text-center lg:text-left">
          <div className="text-sm text-stone-400 mb-1">Estimated annual room revenue today</div>
          <div className="text-2xl font-bold text-stone-200" data-testid="roi-current">{fmt(currentRevenue)}</div>
          <div className="text-sm text-stone-400 mt-6 mb-1">Potential yearly gain with AI revenue management</div>
          <div className="text-5xl font-black bg-gradient-to-r from-emerald-300 to-lime-300 bg-clip-text text-transparent" data-testid="roi-gain">+{fmt(gain)}</div>
          <div className="text-xs text-stone-500 mt-2">Assumes +{Math.round(upliftPct * 100)}% RevPAR uplift for your occupancy profile. Your result will vary by market and baseline.</div>
          <button onClick={onDemo} data-testid="roi-demo-btn"
            className="mt-7 px-6 py-3 rounded-xl bg-emerald-400 text-stone-950 font-black text-sm hover:bg-emerald-300 transition-colors">
            Model it live in a demo →
          </button>
        </div>
      </div>
    </section>
  );
}
