import React from "react";
import { ArrowsClockwise, WarningOctagon } from "@phosphor-icons/react";

/**
 * App-level ErrorBoundary — catches uncaught render errors and shows a recovery card.
 * In production wire `componentDidCatch` to Sentry/Bugsnag via window.__APP_ERROR_HOOK__.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorId: null };
  }

  static getDerivedStateFromError(error) {
    const errorId = `ERR-${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
    return { hasError: true, error, errorId };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
    if (typeof window !== "undefined" && typeof window.__APP_ERROR_HOOK__ === "function") {
      try {
        window.__APP_ERROR_HOOK__(error, errorInfo, this.state.errorId);
      } catch {
        /* never let the hook crash the boundary */
      }
    }
  }

  handleReload = () => {
    window.location.reload();
  };

  handleHome = () => {
    window.location.assign("/");
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div
        className="min-h-screen bg-stone-50 flex items-center justify-center p-6"
        data-testid="error-boundary"
      >
        <div className="max-w-md w-full bg-white border border-rose-200 rounded-2xl shadow-xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-full bg-rose-100 inline-flex items-center justify-center">
              <WarningOctagon size={24} weight="fill" className="text-rose-500" />
            </div>
            <div>
              <div className="text-lg font-bold text-stone-900">Bir şeyler ters gitti</div>
              <div className="text-xs text-stone-500 font-mono">Ref: {this.state.errorId}</div>
            </div>
          </div>
          <p className="text-sm text-stone-600 mb-5">
            Üzgünüz, bu ekranda beklenmedik bir hata oldu. Sayfayı yenileyebilir veya ana sayfaya
            dönebilirsiniz. Sorun devam ederse yukarıdaki referans kodunu destek ekibine iletin.
          </p>
          {this.state.error?.message && (
            <pre className="bg-stone-50 border border-stone-100 rounded-md p-2 text-[10px] text-stone-600 overflow-x-auto mb-4 max-h-32">
              {String(this.state.error.message).slice(0, 400)}
            </pre>
          )}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={this.handleReload}
              data-testid="error-boundary-reload"
              className="py-2 rounded-md bg-stone-900 text-white text-sm font-semibold hover:bg-stone-800 inline-flex items-center justify-center gap-1.5"
            >
              <ArrowsClockwise size={14} /> Yenile
            </button>
            <button
              onClick={this.handleHome}
              data-testid="error-boundary-home"
              className="py-2 rounded-md bg-stone-100 text-stone-700 text-sm font-semibold hover:bg-stone-200"
            >
              Ana Sayfa
            </button>
          </div>
        </div>
      </div>
    );
  }
}
