import { useEffect, useState } from "react";
import axios from "axios";
import { Star, SealCheck } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const cache = {};

export function useRoomReviews(propertyId) {
  const [data, setData] = useState(cache[propertyId] || null);
  useEffect(() => {
    if (!propertyId) return;
    if (cache[propertyId]) { setData(cache[propertyId]); return; }
    axios.get(`${API}/booking/room-reviews/${propertyId}`).then((r) => { cache[propertyId] = r.data; setData(r.data); }).catch(() => {});
  }, [propertyId]);
  return data;
}

export function RoomRatingBadge({ review, roomId }) {
  if (!review || !review.count) return null;
  return (
    <span className="flex items-center gap-1 text-amber-600 font-semibold" title={`${review.count} misafir yorumu`} data-testid={`room-rating-${roomId}`}>
      <Star size={13} weight="fill" /> {review.avg} <span className="text-slate-400 font-normal">({review.count})</span>
    </span>
  );
}

export function RoomReviewQuotes({ review, roomId, accent }) {
  if (!review || !review.quotes?.length) return null;
  return (
    <div className="mt-4" data-testid={`room-reviews-${roomId}`}>
      <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-2">Misafir yorumları <span className="flex items-center gap-1 text-amber-600"><Star size={12} weight="fill" />{review.avg} · {review.count}</span></div>
      <div className="space-y-2">
        {review.quotes.map((q, i) => (
          <blockquote key={i} className="text-sm text-slate-700 bg-slate-50 rounded-lg px-3 py-2 border-l-4" style={{ borderColor: accent }} data-testid={`room-review-quote-${roomId}-${i}`}>
            “{q.text}”
            <div className="text-xs text-slate-500 mt-1 flex items-center gap-1">— {q.author}{q.date ? ` · ${q.date}` : ""}{q.verified && <span className="flex items-center gap-0.5 text-emerald-600 font-semibold ml-1"><SealCheck size={12} weight="fill" /> Doğrulanmış konaklama</span>}</div>
          </blockquote>
        ))}
      </div>
    </div>
  );
}
