import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Compass, Plus, X } from "@phosphor-icons/react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function StrategyDirectivesCard({ propertyId }) {
  const [items, setItems] = useState([]);
  const [impact, setImpact] = useState({});
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/strategy-directives/${propertyId}`, { withCredentials: true });
      setItems(r.data.items || []);
      const ri = await axios.get(`${API}/api/strategy-directives/${propertyId}/impact`, { withCredentials: true });
      setImpact(ri.data.items || {});
    } catch { /* */ }
  }, [propertyId]);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (text.trim().length < 5 || busy) return;
    setBusy(true);
    try {
      await axios.post(`${API}/api/strategy-directives/${propertyId}`, { text: text.trim() }, { withCredentials: true });
      setText("");
      toast.success("Direktif eklendi — Copilot ve Stratejist artık buna uyacak");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Eklenemedi"); } finally { setBusy(false); }
  };

  const remove = async (did) => {
    try {
      await axios.delete(`${API}/api/strategy-directives/${propertyId}/${did}`, { withCredentials: true });
      load();
    } catch { toast.error("Kaldırılamadı"); }
  };

  const PRIO = { occupancy: "Doluluk önceliği", adr: "ADR önceliği", balanced: "Dengeli" };

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4 mb-4" data-testid="strategy-directives-card">
      <div className="text-sm font-semibold text-stone-900 flex items-center gap-2 mb-1">
        <Compass size={16} weight="fill" className="text-violet-600" /> Strateji Direktifleri
        <span className="text-[10px] text-stone-400 font-normal">— kural yazmadan robota yön verin</span>
      </div>
      <p className="text-[11px] text-stone-500 mb-3">Serbest metin yazın ("Eylül'de doluluk önceliği, agresif olma") — AI yapılandırır, tüm öneri ve sohbetlerde buna uyar.</p>
      <div className="flex gap-2 mb-3">
        <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder='ör. "Eylül boyunca doluluk önceliği, fiyat artışlarında temkinli ol"' data-testid="directive-input"
          className="flex-1 border border-stone-300 rounded-lg px-3 py-2 text-xs" />
        <button onClick={add} disabled={busy || text.trim().length < 5} data-testid="directive-add-btn"
          className="px-3 py-2 text-xs font-bold rounded-lg bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50 inline-flex items-center gap-1">
          <Plus size={12} weight="bold" /> {busy ? "Yapılandırılıyor…" : "Ekle"}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="text-[11px] text-stone-400">Aktif direktif yok.</div>
      ) : (
        <div className="space-y-2">
          {items.map((d) => {
            const im = impact[d.id];
            return (
            <div key={d.id} className="flex items-start gap-2 bg-violet-50/60 border border-violet-100 rounded-lg px-3 py-2" data-testid={`directive-${d.id}`}>
              <div className="flex-1">
                <div className="text-xs text-stone-800">{d.text}</div>
                <div className="text-[10px] text-violet-700 mt-0.5">
                  {PRIO[d.parsed?.priority] || "Dengeli"} · agresiflik {d.parsed?.aggressiveness ?? 0}
                  {d.parsed?.scope_start ? ` · ${d.parsed.scope_start} → ${d.parsed.scope_end || "…"}` : " · süresiz"}
                </div>
                {im && (
                  <div className="mt-1.5 pt-1.5 border-t border-violet-100" data-testid={`directive-impact-${d.id}`}>
                    <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-stone-600">
                      <span><b>{im.decisions}</b> karar</span>
                      <span>ort Δ <b className={im.avg_delta_pct > 0 ? "text-emerald-700" : im.avg_delta_pct < 0 ? "text-rose-700" : ""}>{im.avg_delta_pct > 0 ? "+" : ""}{im.avg_delta_pct}%</b></span>
                      <span>↑{im.ups} / ↓{im.downs}</span>
                      {im.success_rate != null && <span>başarı <b>%{im.success_rate}</b></span>}
                    </div>
                    <div className={`text-[10px] mt-0.5 font-semibold ${im.aligned === false ? "text-amber-700" : im.aligned ? "text-emerald-700" : "text-stone-400"}`}>
                      {im.alignment}
                    </div>
                  </div>
                )}
              </div>
              <button onClick={() => remove(d.id)} data-testid={`directive-remove-${d.id}`} className="text-stone-400 hover:text-rose-600 mt-0.5">
                <X size={13} weight="bold" />
              </button>
            </div>
          );})}
        </div>
      )}
    </div>
  );
}
