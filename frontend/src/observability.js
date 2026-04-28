/**
 * Lightweight observability bootstrap — Sentry-ready, env-gated.
 *
 * Why this is small: we deliberately do NOT depend on @sentry/react in the bundle.
 * If you need production error monitoring, install @sentry/react in your deploy
 * and call the init code from your own bootstrap, then set window.__APP_ERROR_HOOK__
 * to a Sentry-aware function. We provide stable global hooks that ErrorBoundary
 * and feature code can call without caring whether Sentry is wired or not.
 *
 * Window globals exposed:
 *   window.__APP_ERROR_HOOK__(error, info, errorId)  — called by ErrorBoundary
 *   window.__APP_TRACK__(event, props)               — called by feature code
 *
 * Production wiring (after `yarn add @sentry/react`):
 *   import * as Sentry from "@sentry/react";
 *   Sentry.init({ dsn: process.env.REACT_APP_SENTRY_DSN, tracesSampleRate: 0.1 });
 *   window.__APP_ERROR_HOOK__ = (err, info, id) => {
 *     Sentry.withScope((s) => { s.setTag("error_id", id); Sentry.captureException(err); });
 *   };
 *   window.__APP_TRACK__ = (e, p) => Sentry.addBreadcrumb({ message: e, data: p });
 */

let installed = false;

export function initObservability() {
  if (installed) return;
  installed = true;

  // Default no-op hooks (always safe to call from feature code)
  if (!window.__APP_ERROR_HOOK__) {
    window.__APP_ERROR_HOOK__ = (err, info, id) => {
      if (process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.warn("[obs:no-op]", id, err?.message, info?.componentStack?.slice(0, 200));
      }
    };
  }
  if (!window.__APP_TRACK__) {
    window.__APP_TRACK__ = () => {};
  }

  if (process.env.REACT_APP_SENTRY_DSN && process.env.NODE_ENV === "production") {
    // Hint for production deploys; real wiring happens in deploy bootstrap.
    // eslint-disable-next-line no-console
    console.info(
      "[obs] REACT_APP_SENTRY_DSN detected. " +
      "To activate Sentry, install @sentry/react and override window.__APP_ERROR_HOOK__ in your deploy bootstrap."
    );
  }
}
