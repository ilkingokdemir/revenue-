import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Detective, ArrowsClockwise, UploadSimple } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/second-writer`;

export default function SecondWriterPanel({ propertyId = "default" }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const pid = propertyId === "all" ? "default" : propertyId;

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/${pid}`);
      setData(r.data);
    } catch { toast.error("İkinci yazıcı verisi yüklenemedi"); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  async function act(name, fn, ok) {
    setBusy(name);
    try { const r = await fn(); toast.success(ok(r)); load(); }
    catch { toast.error("İşlem başarısız"); }
    setBusy("");
  }

  const push = () => act("push", () => axios.post(`${API}/${pid}/push`),
    (r) => `${r.data.cells_written} hücre kanallara imzalı yazıldı`);
  const scan = () => act("scan", () => axios.post(`${API}/${pid}/scan`),
    (r) => `Tarama bitti: ${r.data.new_alerts} yeni alarm`);
  const simulate = () => {
    const d = new Date(); d.setDate(d.getDate() + 1);
    return act("sim", () => axios.post(`${API}/${pid}/simulate-foreign-write`, {
      date: d.toISOString().slice(0, 10), channel: "booking", rate: 42, actor: "legacy-tool",
    }), () => "Yabancı yazım simüle edildi — şimdi tarayın");
  };
  const repush = () => act("repush", () => axios.post(`${API}/${pid}/repush`),
    (r) => `Onarıldı: ${r.data.cells_written} hücre yeniden yazıldı`);
  const ack = (id) => act(`ack-${id}`, () => axios.post(`${API}/${pid}/alerts/${id}/ack`),
    () => "Alarm onaylandı");

  if (!data) return <div className="p-8 text-center text-stone-400">Yükleniyor…</div>;
  const { alerts, summary: s } = data;

  return (
    <div className="p-5 max-w-[1100px] mx-auto space-y-4" data-testid="second-writer-panel">
      <div className="bg-gradient-to-br from-stone-900 via-red-950 to-orange-950 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-orange-300">
              <Detective size={14} /> Second-Writer Detection
            </div>
            <h1 className="text-2xl font-bold mt-1">İkinci Yazıcı Alarmı</h1>
            <p className="text-sm text-stone-300 mt-1">
              Her yazımımız aktör imzalıdır ({data.our_actor}). Kanala bizden başka bir sistem
              (eski araç, elle müdahale) fiyat yazarsa saatler içinde yakalanır ve alarma bağlanır.
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button onClick={push} disabled={busy === "push"} data-testid="sw-push-btn"
              className="px-4 py-2 rounded-full bg-orange-500 hover:bg-orange-400 text-stone-900 text-sm font-semibold flex items-center gap-2 disabled:opacity-50">
              <UploadSimple size={16} /> Fiyatları İmzalı Yaz
            </button>
            <button onClick={scan} disabled={busy === "scan"} data-testid="sw-scan-btn"
              className="px-4 py-2 rounded-full bg-white/15 hover:bg-white/25 text-sm flex items-center gap-2 disabled:opacity-50">
              <ArrowsClockwise size={16} className={busy === "scan" ? "animate-spin" : ""} /> Tara
            </button>
            <button onClick={simulate} disabled={busy === "sim"} data-testid="sw-simulate-btn"
              className="px-3 py-2 rounded-full bg-white/15 hover:bg-white/25 text-xs">Tatbikat: yabancı yazım simüle et</button>
          </div>
        </div>
        <div className="grid grid-cols-4 gap-3 mt-5">
          <div className="bg-white/10 rounded-xl p-3" data-testid="sw-stat-open">
            <div className={`text-2xl font-bold ${s.open > 0 ? "text-rose-300" : "text-emerald-300"}`}>{s.open}</div>
            <div className="text-xs text-stone-300">Açık alarm</div>
          </div>
          <div className="bg-white/10 rounded-xl p-3"><div className="text-2xl font-bold">{s.acked}</div><div className="text-xs text-stone-300">Onaylanan</div></div>
          <div className="bg-white/10 rounded-xl p-3"><div className="text-2xl font-bold">{s.ledger_cells}</div><div className="text-xs text-stone-300">İmzalı hücre (ledger)</div></div>
          <div className="bg-white/10 rounded-xl p-3"><div className="text-sm font-semibold mt-1">{s.last_push_at ? s.last_push_at.slice(0, 16).replace("T", " ") : "—"}</div><div className="text-xs text-stone-300">Son imzalı yazım</div></div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Alarmlar</h2>
          {s.open > 0 && (
            <button onClick={repush} disabled={busy === "repush"} data-testid="sw-repush-btn"
              className="px-4 py-1.5 rounded-full bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold disabled:opacity-50">
              Bizim fiyatları geri yaz (onar)
            </button>
          )}
        </div>
        {alerts.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="sw-empty-alerts">
            Alarm yok. "Fiyatları İmzalı Yaz" ile ledger'ı doldurun; tatbikat butonu ile tespiti test edebilirsiniz.
          </p>
        ) : (
          <table className="w-full text-sm" data-testid="sw-alerts-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Tespit</th><th>Gece</th><th>Kanal</th><th>Bizim yazdığımız</th><th>Kanalda görünen</th><th>Yabancı aktör</th><th>Durum</th><th></th>
            </tr></thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id} className={`border-b border-stone-100 ${a.status === "open" ? "bg-rose-50" : ""}`}>
                  <td className="py-2 text-xs text-stone-400">{a.detected_at?.slice(0, 16).replace("T", " ")}</td>
                  <td>{a.date}</td>
                  <td className="capitalize">{a.channel}</td>
                  <td>{a.expected_rate}</td>
                  <td className="font-semibold text-rose-600">{a.channel_rate}</td>
                  <td><span className="px-2 py-0.5 rounded-full bg-stone-100 text-xs">{a.channel_actor}</span></td>
                  <td>{a.status === "open" ? <span className="text-rose-600 text-xs font-semibold">AÇIK</span>
                    : a.status === "repushed" ? <span className="text-sky-600 text-xs font-semibold">ONARILDI</span>
                    : <span className="text-stone-400 text-xs">Onaylandı</span>}</td>
                  <td>{a.status === "open" && (
                    <button onClick={() => ack(a.id)} data-testid={`sw-ack-btn-${a.id}`}
                      className="text-xs px-2 py-1 rounded-full border border-stone-300 hover:bg-stone-50">Onayla</button>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
