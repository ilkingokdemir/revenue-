import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Rocket, CheckCircle, XCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/live-smoke`;

export default function LiveSmokePanel() {
  const [runs, setRuns] = useState([]);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ base_url: "", email: "", password: "", property_id: "default" });

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/history`);
      setRuns(r.data.runs || []);
      if (r.data.runs?.length && !result) setResult(r.data.runs[0]);
    } catch { toast.error("Duman testi geçmişi yüklenemedi"); }
  }, [result]);
  useEffect(() => { load(); }, []); // eslint-disable-line

  async function run(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await axios.post(`${API}/run`, form);
      setResult(r.data);
      r.data.verdict === "PASS"
        ? toast.success(`Duman testi PASS (${r.data.passed}/${r.data.total})`)
        : toast.error(`Duman testi FAIL (${r.data.passed}/${r.data.total})`);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Test çalıştırılamadı");
    }
    setBusy(false);
  }

  return (
    <div className="p-5 max-w-[1000px] mx-auto space-y-4" data-testid="live-smoke-panel">
      <div className="bg-gradient-to-br from-stone-900 via-cyan-950 to-teal-950 rounded-2xl p-6 text-white">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-cyan-300">
          <Rocket size={14} /> Live Smoke Test
        </div>
        <h1 className="text-2xl font-bold mt-1">Canlı Duman Testi</h1>
        <p className="text-sm text-stone-300 mt-1">
          Canlı URL'nizde uçtan uca akışı doğrular: sağlık → giriş → test rezervasyonu →
          Stripe checkout → temizlik (rezervasyon otomatik iptal edilir).
        </p>
        <form onSubmit={run} className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
          <input required value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })}
            placeholder="https://canli-adresiniz.com" data-testid="smoke-url-input"
            className="rounded-lg px-3 py-2 text-sm text-stone-900 md:col-span-2" />
          <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="Canlı admin e-posta" data-testid="smoke-email-input"
            className="rounded-lg px-3 py-2 text-sm text-stone-900" />
          <input required type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Canlı admin şifre" data-testid="smoke-password-input"
            className="rounded-lg px-3 py-2 text-sm text-stone-900" />
          <button type="submit" disabled={busy} data-testid="smoke-run-btn"
            className="md:col-span-2 px-4 py-2 rounded-full bg-cyan-500 hover:bg-cyan-400 text-stone-900 text-sm font-semibold disabled:opacity-50">
            {busy ? "Çalışıyor… (≈15 sn)" : "Duman Testini Çalıştır"}
          </button>
        </form>
      </div>

      {result && (
        <div className="bg-white rounded-2xl border border-stone-200 p-5" data-testid="smoke-result">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Sonuç — {result.base_url}</h2>
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${result.verdict === "PASS" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}
              data-testid="smoke-verdict">{result.verdict} ({result.passed}/{result.total})</span>
          </div>
          <div className="space-y-2">
            {result.steps.map((s, i) => (
              <div key={i} className={`flex items-start gap-2 px-3 py-2 rounded-xl text-sm ${s.status === "pass" ? "bg-stone-50" : "bg-rose-50"}`}>
                {s.status === "pass" ? <CheckCircle size={18} className="text-emerald-600 mt-0.5" /> : <XCircle size={18} className="text-rose-600 mt-0.5" />}
                <div className="flex-1">
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs text-stone-500">{s.detail} · {s.ms}ms</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-stone-200 p-5">
        <h2 className="text-lg font-semibold mb-3">Geçmiş Koşular</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-stone-400" data-testid="smoke-empty-history">Henüz koşu yok. Canlı URL'nizi girip testi başlatın.</p>
        ) : (
          <table className="w-full text-sm" data-testid="smoke-history-table">
            <thead><tr className="text-left text-xs text-stone-500 border-b">
              <th className="py-2">Zaman</th><th>URL</th><th>Sonuç</th><th>Çalıştıran</th>
            </tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-b border-stone-100 cursor-pointer hover:bg-stone-50" onClick={() => setResult(r)}>
                  <td className="py-2 text-xs text-stone-400">{r.ran_at?.slice(0, 16).replace("T", " ")}</td>
                  <td className="text-xs">{r.base_url}</td>
                  <td><span className={r.verdict === "PASS" ? "text-emerald-600 font-semibold" : "text-rose-600 font-semibold"}>{r.verdict} {r.passed}/{r.total}</span></td>
                  <td className="text-xs">{r.ran_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
