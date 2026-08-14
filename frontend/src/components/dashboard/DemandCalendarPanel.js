import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CalendarHeart, Sparkle, MoonStars } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;
const HEAT = { hot: "bg-rose-500 text-white", warm: "bg-amber-400 text-stone-900", cool: "bg-sky-200 text-stone-700", cold: "bg-stone-100 text-stone-400" };

export default function DemandCalendarPanel({ activePropertyId, properties = [] }) {
  const pid = activePropertyId && activePropertyId !== "all" ? activePropertyId : properties[0]?.id || "default";
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7));
  const [data, setData] = useState(null);
  const [story, setStory] = useState(null);
  const [gaps, setGaps] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/demand-calendar/${pid}?month=${month}`, { withCredentials: true });
      setData(r.data);
      const g = await axios.get(`${API}/api/demand-calendar/${pid}/orphan-gaps`, { withCredentials: true });
      setGaps(g.data);
    } catch { toast.error("Takvim yüklenemedi"); }
  }, [pid, month]);

  useEffect(() => { load(); }, [load]);

  const analyze = async (date) => {
    setBusy(true);
    setStory({ date, story: null });
    try {
      const r = await axios.get(`${API}/api/demand-calendar/${pid}/analyze?date=${date}`, { withCredentials: true });
      setStory(r.data);
    } catch { toast.error("Analiz alınamadı"); setStory(null); } finally { setBusy(false); }
  };

  const fillGaps = async () => {
    const dates = (gaps?.gaps || []).flatMap((g) => Array.from({ length: g.nights }, (_, i) => {
      const d = new Date(g.start); d.setDate(d.getDate() + i); return d.toISOString().slice(0, 10);
    }));
    if (!dates.length) return;
    try {
      const r = await axios.post(`${API}/api/demand-calendar/${pid}/orphan-gaps/fill`, { dates }, { withCredentials: true });
      toast.success(`${r.data.filled} yetim gece için kampanya açıldı`);
    } catch { toast.error("Açılamadı"); }
  };

  const shiftMonth = (n) => {
    const d = new Date(month + "-01"); d.setMonth(d.getMonth() + n);
    setMonth(d.toISOString().slice(0, 7)); setStory(null);
  };

  return (
    <div className="p-5 max-w-[1200px] mx-auto" data-testid="demand-calendar-panel">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-stone-500 mb-1">
            <CalendarHeart size={13} weight="fill" className="text-rose-500" /><span>Talep Zekâsı</span>
          </div>
          <h1 className="text-2xl font-semibold text-stone-900">Talep Takvimi</h1>
          <p className="text-sm text-stone-500 mt-1">Isı haritası + güne tıklayın: talep hikâyesi, rakip bağlamı ve önerilen aksiyon sade Türkçe.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => shiftMonth(-1)} data-testid="dc-prev" className="px-2.5 py-1.5 border border-stone-300 rounded-lg text-sm">←</button>
          <span className="text-sm font-bold text-stone-800" data-testid="dc-month">{month}</span>
          <button onClick={() => shiftMonth(1)} data-testid="dc-next" className="px-2.5 py-1.5 border border-stone-300 rounded-lg text-sm">→</button>
        </div>
      </div>

      {data && (
        <div className="grid grid-cols-7 gap-1.5 mb-2" data-testid="dc-grid">
          {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((d) => <div key={d} className="text-[10px] text-stone-400 text-center font-bold">{d}</div>)}
          {Array.from({ length: data.days[0]?.dow ?? 0 }).map((_, i) => <div key={`e${i}`} />)}
          {data.days.map((d) => (
            <button key={d.date} onClick={() => analyze(d.date)} data-testid={`dc-day-${d.date}`}
              className={`rounded-lg p-1.5 text-left transition-transform hover:scale-105 ${HEAT[d.heat]} ${story?.date === d.date ? "ring-2 ring-violet-600" : ""}`}>
              <div className="text-[10px] font-bold">{Number(d.date.slice(8))}{d.flag === "spike" ? " ⚡" : d.flag === "dip" ? " ⚠" : ""}</div>
              <div className="text-[11px] font-black">%{d.occ}</div>
            </button>
          ))}
        </div>
      )}
      {data && <p className="text-[10px] text-stone-400 mb-4">{data.legend}</p>}

      {story && (
        <div className="bg-stone-900 text-stone-100 rounded-xl p-4 mb-4" data-testid="dc-story">
          <div className="text-xs font-bold text-violet-300 flex items-center gap-1.5 mb-1"><Sparkle size={13} weight="fill" /> {story.date} — talep hikâyesi</div>
          {busy && !story.story ? <div className="text-xs text-stone-400 animate-pulse">AI analiz ediyor…</div>
            : <p className="text-sm leading-relaxed" data-testid="dc-story-text">{story.story}</p>}
        </div>
      )}

      {gaps && (
        <div className="bg-white border border-stone-200 rounded-xl p-4" data-testid="dc-orphan-gaps">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="text-sm font-semibold text-stone-900 flex items-center gap-2">
              <MoonStars size={15} weight="fill" className="text-indigo-500" /> Yetim Geceler
              <span className="text-[10px] text-stone-400 font-normal">— rezervasyonlar arası 1-2 gecelik boşluklar (60 gün)</span>
            </div>
            {gaps.gaps.length > 0 && (
              <button onClick={fillGaps} data-testid="dc-fill-gaps-btn"
                className="px-3 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
                Tümünü Doldur (%10 + min-stay 1)
              </button>
            )}
          </div>
          {gaps.gaps.length === 0 ? (
            <div className="text-xs text-stone-400">Yetim gece yok — envanter verimli dolmuş. 🎉</div>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {gaps.gaps.map((g) => (
                <span key={g.start} data-testid={`dc-gap-${g.start}`}
                  className="px-2 py-1 rounded-lg bg-indigo-50 border border-indigo-100 text-indigo-800 text-[11px] font-semibold">
                  {g.start} · {g.nights} gece · {g.rooms} oda
                </span>
              ))}
            </div>
          )}
          <p className="text-[10px] text-stone-400 mt-2">{gaps.suggestion} Toplam {gaps.total_orphan_room_nights} yetim oda-gece.</p>
        </div>
      )}
    </div>
  );
}
