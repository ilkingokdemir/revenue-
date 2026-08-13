import { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PhotoContestPage() {
  const propertyId = window.location.pathname.split("/kareler/")[1]?.split("/")[0] || "";
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [voting, setVoting] = useState(null);

  const vote = async (cid) => {
    if (localStorage.getItem(`voted_${cid}`)) return;
    setVoting(cid);
    try {
      const { data: r } = await axios.post(`${API}/reputation/public/photo-contest/${propertyId}/vote`, { candidate_id: cid });
      localStorage.setItem(`voted_${cid}`, "1");
      setData((prev) => ({
        ...prev,
        candidates: prev.candidates.map((c) => c.id === cid ? { ...c, votes: r.votes } : c),
      }));
    } catch (e) {
      setError("");
      const msg = e?.response?.data?.detail;
      if (msg) {
        localStorage.setItem(`voted_${cid}`, "1");
        setData((prev) => ({ ...prev }));
      }
    }
    setVoting(null);
  };

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
          {(data?.items || []).slice(0, 1).map((it, i) => (
            <div key={i} data-testid={`gallery-item-${i}`}
              className="rounded-2xl overflow-hidden bg-stone-900 border border-stone-800 sm:col-span-2 sm:grid sm:grid-cols-2">
              <img src={`${process.env.REACT_APP_BACKEND_URL}${it.image_url}`}
                alt={`${it.month} kazananı`} className="w-full aspect-square object-cover" />
              <div className="p-6 flex flex-col justify-center">
                <span className="inline-block w-fit px-2 py-1 rounded-full bg-amber-500/15 text-amber-300 text-[10px] mb-3">
                  Güncel Kazanan
                </span>
                <p className="text-2xl font-bold">🏆 {it.winner}</p>
                <p className="text-sm text-stone-500 mt-1">{it.month} kazananı</p>
              </div>
            </div>
          ))}
        </div>
        {(data?.items || []).length > 1 && (
          <div className="mt-14" data-testid="hall-of-fame">
            <h2 className="text-lg font-semibold text-stone-200 mb-1">⭐ Şeref Duvarı</h2>
            <p className="text-xs text-stone-500 mb-6">Geçmiş ayların kazananları</p>
            {Object.entries(
              data.items.slice(1).reduce((acc, it) => {
                const y = (it.month || "").slice(0, 4) || "Diğer";
                (acc[y] = acc[y] || []).push(it);
                return acc;
              }, {})
            ).sort((a, b) => b[0].localeCompare(a[0])).map(([year, items]) => (
              <div key={year} className="mb-8" data-testid={`hof-year-${year}`}>
                <p className="text-sm font-mono text-amber-400/80 mb-3">{year}</p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {items.map((it, i) => (
                    <div key={i} className="rounded-xl overflow-hidden bg-stone-900 border border-stone-800">
                      <img src={`${process.env.REACT_APP_BACKEND_URL}${it.image_url}`}
                        alt={it.month} className="w-full aspect-square object-cover" />
                      <div className="p-2">
                        <p className="text-xs font-semibold truncate">🏆 {it.winner}</p>
                        <p className="text-[10px] text-stone-500">{it.month}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
        {(data?.candidates || []).length > 0 && (
          <div className="mt-14" data-testid="vote-section">
            <h2 className="text-lg font-semibold text-stone-200 mb-1">🗳️ Bu Ayın Adayları — Oyunuzu Verin</h2>
            <p className="text-xs text-stone-500 mb-6">En beğendiğiniz kareye oy verin; ay sonunda en çok oyu alan kazanır.</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {data.candidates.map((c) => {
                const voted = !!localStorage.getItem(`voted_${c.id}`);
                return (
                  <div key={c.id} data-testid={`candidate-${c.id}`}
                    className="rounded-xl overflow-hidden bg-stone-900 border border-stone-800">
                    <img src={`${process.env.REACT_APP_BACKEND_URL}${c.photo_url}`}
                      alt={c.guest} className="w-full aspect-square object-cover" />
                    <div className="p-2 flex items-center justify-between">
                      <div>
                        <p className="text-xs font-semibold truncate">{c.guest}</p>
                        <p className="text-[10px] text-stone-500">{c.votes} oy</p>
                      </div>
                      <button data-testid={`vote-btn-${c.id}`} disabled={voted || voting === c.id}
                        onClick={() => vote(c.id)}
                        className={`px-2 py-1 rounded-full text-xs ${voted ? "bg-rose-500/20 text-rose-300" : "bg-stone-800 hover:bg-rose-500/20 hover:text-rose-300 text-stone-300"}`}>
                        {voted ? "❤️ Oy verildi" : "🤍 Oy Ver"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        <p className="text-[11px] text-stone-600 mt-12">
          Fotoğraflar, misafirlerimizin açık izniyle paylaşılmaktadır.
        </p>
      </div>
    </div>
  );
}
