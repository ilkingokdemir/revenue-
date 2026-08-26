import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Storefront, ArrowsClockwise, WarningCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/storefront-verify`;

export default function StorefrontVerifyPanel({ propertyId = "default" }) {
  const [data, setData] = useState(null);
  const [scanning, setScanning] = useState(false);
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${pid}/report`);
      setData(r.data);
    } catch { toast.error("Vitrin raporu yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function scan() {
    setScanning(true);
    try {
      const r = await axios.post(`${API}/${pid}/scan`);
      toast.success(`Vitrin tarandı: ${r.data.total} gün, ${r.data.flagged} sapma`);
      load();
    } catch { toast.error("Tarama başarısız"); }
    setScanning(false);
  }

  async function injectDemo() {
    try {
      const d = new Date(); d.setDate(d.getDate() + 2);
      const day = d.toISOString().slice(0, 10);
      const row = data?.latest?.rows?.find((r) => r.date === day);
      const obs = row ? Math.round(row.expected_guest * 0.9 * 100) / 100 : 99;
      await axios.post(`${API}/${pid}/inject-drift`, { date: day, observed_rate: obs });
      toast.success(`Demo sapma eklendi (${day}) — tekrar tarayın`);
    } catch { toast.error("Demo sapma eklenemedi"); }
  }

  async function clearDrift() {
    try {
      await axios.delete(`${API}/${pid}/drift`);
      toast.success("Simüle sapmalar temizlendi"); scan();
    } catch { toast.error("Temizlenemedi"); }
  }

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const scanDoc = data.latest;

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="storefront-verify-panel">
      <div className="bg-gradient-to-br from-stone-900 via-sky-950 to-blue-900 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-sky-300">
              <Storefront size={14} /> Own Storefront Scan
            </div>
            <h1 className="text-2xl font-bold mt-1">Vitrin Doğrulaması</h1>
            <p className="text-sm text-stone-300 mt-1">
              Kendi Booking vitrininiz misafir gözüyle taranır: panele yazılan fiyat + indirim katmanları →
              beklenen misafir fiyatı; vitrinde görünenle kuruşuna kıyaslanır.
              Mod: <b>{data.config.mode === "mock" ? "MOCK (canlı scraper anahtarı bekleniyor)" : "CANLI"}</b>
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button onClick={scan} disabled={scanning} data-testid="storefront-scan-btn"
              className="px-4 py-2 rounded-full bg-sky-500 hover:bg-sky-400 text-stone-900 text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
              <ArrowsClockwise size={16} className={scanning ? "animate-spin" : ""} /> Vitrini Tara
            </button>
            <button onClick={injectDemo} data-testid="storefront-inject-demo-btn"
              className="px-3 py-2 rounded-full bg-white/15 hover:bg-white/25 text-xs">Demo sapma enjekte et</button>
            <button onClick={clearDrift} data-testid="storefront-clear-drift-btn"
              className="px-3 py-2 rounded-full bg-white/15 hover:bg-white/25 text-xs">Sapmaları temizle</button>
          </div>
        </div>
        {scanDoc && (
          <div className="grid grid-cols-3 gap-3 mt-5">
            <div className="bg-white/10 rounded-xl p-3" data-testid="storefront-stat-days">
              <div className="text-2xl font-bold">{scanDoc.total}</div>
              <div className="text-xs text-stone-300">Taranan gün</div>
            </div>
            <div className="bg-white/10 rounded-xl p-3" data-testid="storefront-stat-flagged">
              <div className={`text-2xl font-bold ${scanDoc.flagged > 0 ? "text-rose-300" : "text-emerald-300"}`}>{scanDoc.flagged}</div>
              <div className="text-xs text-stone-300">Sapmalı gün</div>
            </div>
            <div className="bg-white/10 rounded-xl p-3">
              <div className="text-2xl font-bold">±%{scanDoc.tolerance_pct}</div>
              <div className="text-xs text-stone-300">Tolerans</div>
            </div>
          </div>
        )}
      </div>

      {!scanDoc ? (
        <div className="bg-white rounded-2xl border border-stone-200 p-8 text-center text-stone-400" data-testid="storefront-empty">
          Henüz tarama yapılmadı — "Vitrini Tara" ile başlayın.
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-stone-200 p-5">
          <h2 className="text-lg font-semibold mb-1">Gün Gün Kıyas — {scanDoc.scanned_at?.slice(0, 16).replace("T", " ")}</h2>
          <p className="text-xs text-stone-400 mb-3">
            Aktif katmanlar: {scanDoc.rows[0]?.layers?.map((l) => `${l.name} −%${l.pct}`).join(" · ") || "yok"}
          </p>
          <table className="w-full text-sm" data-testid="storefront-rows-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Tarih</th><th>Yazılan (brüt)</th><th>Beklenen misafir</th><th>Vitrinde görünen</th><th>Sapma</th><th>Durum</th>
            </tr></thead>
            <tbody>
              {scanDoc.rows.map((r) => (
                <tr key={r.date} className={`border-b border-stone-100 ${r.status === "drift" ? "bg-rose-50" : ""}`}>
                  <td className="py-2">{r.date}</td>
                  <td>{r.written}</td>
                  <td>{r.expected_guest}</td>
                  <td className="font-semibold">{r.observed}</td>
                  <td className={r.status === "drift" ? "text-rose-600 font-semibold" : "text-stone-400"}>
                    {r.deviation_pct > 0 ? "+" : ""}{r.deviation_pct}%
                  </td>
                  <td>{r.status === "drift"
                    ? <span className="inline-flex items-center gap-1 text-rose-600 text-xs font-semibold"><WarningCircle size={14} /> SAPMA{r.injected ? " (simüle)" : ""}</span>
                    : <span className="text-emerald-600 text-xs font-semibold">✓ Doğrulandı</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
