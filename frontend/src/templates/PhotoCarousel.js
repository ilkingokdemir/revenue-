import { useState } from "react";
import { CaretLeft, CaretRight, Bed } from "@phosphor-icons/react";

export function PhotoCarousel({ photos, borderRadius }) {
  const [idx, setIdx] = useState(0);
  if (!photos || photos.length === 0) return <div className="w-full h-full flex items-center justify-center bg-slate-200"><Bed size={48} className="text-slate-300" /></div>;
  return (
    <div className="relative w-full h-full group overflow-hidden">
      <img src={photos[idx]} alt="" className="w-full h-full object-cover transition-opacity duration-300" loading="lazy" />
      {photos.length > 1 && (
        <>
          <button onClick={(e) => { e.stopPropagation(); setIdx(i => (i - 1 + photos.length) % photos.length); }}
            className="absolute left-1.5 top-1/2 -translate-y-1/2 w-7 h-7 bg-white/90 rounded-full flex items-center justify-center shadow opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white"
            data-testid="photo-prev-btn">
            <CaretLeft size={14} weight="bold" className="text-slate-700" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); setIdx(i => (i + 1) % photos.length); }}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 w-7 h-7 bg-white/90 rounded-full flex items-center justify-center shadow opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white"
            data-testid="photo-next-btn">
            <CaretRight size={14} weight="bold" className="text-slate-700" />
          </button>
          <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 flex gap-1">
            {photos.map((_, i) => <div key={i} className={`w-1.5 h-1.5 rounded-full transition-colors ${i === idx ? "bg-white" : "bg-white/40"}`} />)}
          </div>
        </>
      )}
    </div>
  );
}
