import { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PhotoContestPage() {
  const propertyId = window.location.pathname.split("/kareler/")[1]?.split("/")[0] || "";
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    axios.get(`${API}/reputation/public/photo-contest/${propertyId}`)
      .then(({ data: d }) => setData(d))
      .catch(() => setError("Galeri bulunamadı."));
  }, [propertyId]);

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100" data-testid="photo-contest-page">
      <div className="max-w-4xl mx-auto px-6 py-14">
        <p className="text-xs uppercase tracking-[0.3em] text-amber-400 mb-3">Ayın Karesi</p>
        <h1 className="text-4xl sm:text-5xl font-bold mb-2">
          {data?.hotel || "Misafir Kareleri"}
        </h1>
        <p className="text-stone-400 text-sm mb-10">
          Her ay misafirlerimizin paylaştığı en beğenilen kare 🏆 — siz de konaklama
          sonrası anketimizle fotoğrafınızı paylaşın, gelecek ayın yıldızı olun.
        </p>
        {error && <p data-testid="gallery-error" className="text-rose-400 text-sm">{error}</p>}
        {data && data.items.length === 0 && (
          <p data-testid="gallery-empty" className="text-stone-500 text-sm">
            İlk kazanan yakında duyurulacak — takipte kalın! ⭐
          </p>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
          {(data?.items || []).map((it, i) => (
            <div key={i} data-testid={`gallery-item-${i}`}
              className="rounded-2xl overflow-hidden bg-stone-900 border border-stone-800">
              <img src={`${process.env.REACT_APP_BACKEND_URL}${it.image_url}`}
                alt={`${it.month} kazananı`} className="w-full aspect-square object-cover" />
              <div className="p-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold">🏆 {it.winner}</p>
                  <p className="text-[11px] text-stone-500">{it.month} kazananı</p>
                </div>
                {i === 0 && (
                  <span className="px-2 py-1 rounded-full bg-amber-500/15 text-amber-300 text-[10px]">
                    Güncel Kazanan
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
        <p className="text-[11px] text-stone-600 mt-12">
          Fotoğraflar, misafirlerimizin açık izniyle paylaşılmaktadır.
        </p>
      </div>
    </div>
  );
}
