/**
 * Signature Pad — minimal canvas e-signature with mouse + touch + pen support.
 * Returns dataURL via onChange("" when cleared, "data:image/png;base64,..." otherwise).
 * Zero dependencies — works on every browser including iPad / Android tablets
 * which is what hotels typically hand to guests at check-in.
 */
import { useEffect, useRef, useState } from "react";
import { Eraser } from "lucide-react";

export default function SignaturePad({ onChange, height = 140 }) {
  const ref = useRef(null);
  const drawing = useRef(false);
  const last = useRef(null);
  const [empty, setEmpty] = useState(true);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = cv.getBoundingClientRect();
    cv.width = rect.width * dpr;
    cv.height = rect.height * dpr;
    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#1e293b";
  }, []);

  const xy = (e) => {
    const cv = ref.current;
    const rect = cv.getBoundingClientRect();
    const t = e.touches?.[0];
    const cx = t ? t.clientX : e.clientX;
    const cy = t ? t.clientY : e.clientY;
    return { x: cx - rect.left, y: cy - rect.top };
  };

  const start = (e) => {
    e.preventDefault();
    drawing.current = true;
    last.current = xy(e);
  };
  const move = (e) => {
    if (!drawing.current) return;
    e.preventDefault();
    const cv = ref.current;
    const ctx = cv.getContext("2d");
    const p = xy(e);
    ctx.beginPath();
    ctx.moveTo(last.current.x, last.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last.current = p;
    if (empty) setEmpty(false);
  };
  const end = () => {
    if (!drawing.current) return;
    drawing.current = false;
    const cv = ref.current;
    const dataUrl = cv.toDataURL("image/png");
    onChange?.(empty ? "" : dataUrl);
  };

  const clear = () => {
    const cv = ref.current;
    cv.getContext("2d").clearRect(0, 0, cv.width, cv.height);
    setEmpty(true);
    onChange?.("");
  };

  return (
    <div data-testid="signature-pad" className="relative rounded-lg border border-stone-300 bg-white overflow-hidden">
      <canvas
        ref={ref}
        style={{ height, touchAction: "none", display: "block", width: "100%" }}
        onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
        onTouchStart={start} onTouchMove={move} onTouchEnd={end}
      />
      {empty && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none text-xs text-stone-400 italic">
          Sign here with your finger / mouse / stylus
        </div>
      )}
      <button type="button" onClick={clear} data-testid="signature-clear"
        className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded bg-white border border-stone-200 text-[10px] text-stone-600 hover:bg-stone-50">
        <Eraser className="w-3 h-3" />Clear
      </button>
    </div>
  );
}
