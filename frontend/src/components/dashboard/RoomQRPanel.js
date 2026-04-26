/**
 * Room QR Sheet Panel
 * --------------------
 * Lists every room in the property with its scannable QR thumbnail. One click
 * opens a printable A4 sheet (3 columns) generated server-side.
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, QrCode, Printer, RefreshCw, ExternalLink } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RoomQRPanel({ propertyId, hotelName = "" }) {
  const [data, setData] = useState({ items: [], count: 0 });
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!propertyId) return;
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/room-qr/${propertyId}/list`);
      setData(data || { items: [], count: 0 });
    } catch { toast.error("Failed to load rooms"); }
    setLoading(false);
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const printSheet = () => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/room-qr/${propertyId}/sheet`;
    const tok = localStorage.getItem("token");
    // The endpoint requires admin/manager role — open in same tab so cookies/auth headers work,
    // but axios authorization header is not sent by browser. Fall back to fetch + blob.
    if (!tok) return window.open(url, "_blank");
    fetch(url, { headers: { Authorization: `Bearer ${tok}` } })
      .then((r) => r.text())
      .then((html) => {
        const w = window.open("", "_blank");
        if (!w) return toast.error("Pop-up blocked");
        w.document.open(); w.document.write(html); w.document.close();
      })
      .catch(() => toast.error("Failed to open sheet"));
  };

  return (
    <div className="space-y-6" data-testid="room-qr-panel">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <QrCode className="w-5 h-5 text-cyan-400" />
            <h2 className="text-2xl font-semibold text-stone-100">Room QR codes</h2>
            <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-cyan-500/15 text-cyan-300 rounded">
              Mobile-ready
            </span>
          </div>
          <p className="text-sm text-stone-400 mt-1">
            {hotelName ? `${hotelName} · ` : ""}Stick on the inside of each door — staff scan to open the mobile housekeeping/maintenance view.
          </p>
        </div>
        <div className="flex gap-2">
          <button data-testid="qr-refresh-btn" onClick={load}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 border border-stone-700">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button data-testid="qr-print-sheet-btn" onClick={printSheet} disabled={!data.count}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 text-sm disabled:opacity-50">
            <Printer className="w-4 h-4" /> Print A4 sheet
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-stone-500">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : data.count === 0 ? (
        <div className="text-center text-stone-500 py-12">
          No rooms seeded for this property yet — seed rooms in Housekeeping first.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {data.items.map((r) => (
            <div key={r.room_number} data-testid="qr-card"
              className="rounded-xl border border-stone-800 bg-stone-900/60 p-3 flex flex-col items-center text-center">
              <div className="flex items-center justify-between w-full mb-2 text-xs">
                <span className="text-stone-100 font-semibold">Room {r.room_number}</span>
                <span className="text-stone-500">Fl. {r.floor || "—"}</span>
              </div>
              <img src={`${process.env.REACT_APP_BACKEND_URL}${r.image_url}`}
                alt={`QR for room ${r.room_number}`}
                className="w-full max-w-[140px] aspect-square bg-white rounded p-1" />
              <a href={r.qr_url} target="_blank" rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-[10px] text-cyan-300 hover:underline">
                <ExternalLink className="w-3 h-3" />Test link
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
