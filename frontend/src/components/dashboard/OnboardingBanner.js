import { useEffect, useState } from "react";
import axios from "axios";
import { MagicWand, ArrowRight, X, CheckCircle } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Compact onboarding-progress banner shown at the top of the dashboard while
 * setup is incomplete. Auto-hides when every step is done or when the user
 * dismisses it for the current session.
 */
export const OnboardingBanner = ({ propertyId = "default", onResume }) => {
  const [status, setStatus] = useState(null);
  const [dismissed, setDismissed] = useState(() =>
    sessionStorage.getItem("onboarding-banner-dismissed") === "1"
  );

  useEffect(() => {
    let alive = true;
    axios.get(`${API}/property-onboarding/status/${propertyId}`)
      .then((r) => { if (alive) setStatus(r.data); })
      .catch(() => {});
    return () => { alive = false; };
  }, [propertyId]);

  if (dismissed || !status) return null;
  if (status.completed_at) return null;
  if (status.completed_count === status.total) return null;

  const pct = status.percent || 0;
  const remaining = status.total - status.completed_count;
  const nextStep = Object.entries(status.steps || {}).find(([, done]) => !done);
  const nextLabel = {
    property: "tell us about your property",
    rooms: "add your room types",
    rates: "pick rate plans",
    tax: "configure tax rules",
    sample: "create a sample booking",
  }[nextStep?.[0]] || "finish setup";

  const dismiss = () => {
    sessionStorage.setItem("onboarding-banner-dismissed", "1");
    setDismissed(true);
  };

  return (
    <div
      data-testid="onboarding-banner"
      className="relative mx-4 mt-4 overflow-hidden rounded-2xl border border-fuchsia-200/60 bg-gradient-to-r from-fuchsia-50 via-violet-50 to-sky-50 shadow-sm"
    >
      {/* gradient progress underline */}
      <div
        className="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-fuchsia-500 via-violet-500 to-sky-500 transition-all duration-700"
        style={{ width: `${pct}%` }}
      />
      <div className="flex items-center gap-4 px-5 py-3">
        <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-fuchsia-500 to-violet-600 flex items-center justify-center text-white shadow-lg shadow-fuchsia-500/20">
          <MagicWand size={20} weight="duotone" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-stone-900">
              You're {pct}% set up
            </span>
            <span className="text-xs text-stone-500">
              · {remaining} step{remaining === 1 ? "" : "s"} to go
            </span>
          </div>
          <p className="text-xs text-stone-600 mt-0.5 truncate">
            Next up — {nextLabel}.
          </p>
          {/* step dots */}
          <div className="hidden md:flex gap-1 mt-1.5">
            {Object.entries(status.steps || {}).map(([step, done]) => (
              <span
                key={step}
                title={step}
                className={`flex items-center justify-center w-5 h-5 rounded-full text-[9px] font-bold ${
                  done
                    ? "bg-emerald-500 text-white"
                    : "bg-white border border-stone-300 text-stone-400"
                }`}
              >
                {done ? <CheckCircle size={11} weight="fill" /> : "•"}
              </span>
            ))}
          </div>
        </div>
        <button
          onClick={() => onResume && onResume()}
          data-testid="onboarding-banner-resume"
          className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-br from-fuchsia-600 to-violet-600 hover:from-fuchsia-500 hover:to-violet-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-fuchsia-500/30 transition-transform hover:-translate-y-0.5"
        >
          Resume setup
          <ArrowRight size={14} weight="bold" />
        </button>
        <button
          onClick={dismiss}
          data-testid="onboarding-banner-dismiss"
          className="flex-shrink-0 p-1.5 rounded-lg hover:bg-white/60 text-stone-400 hover:text-stone-700 transition-colors"
          title="Dismiss for this session"
        >
          <X size={16} weight="bold" />
        </button>
      </div>
    </div>
  );
};

export default OnboardingBanner;
