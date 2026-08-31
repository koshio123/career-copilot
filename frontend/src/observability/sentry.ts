import * as Sentry from '@sentry/react'

/** No-op unless VITE_SENTRY_DSN is set (so local/dev builds don't report). */
export function initSentry(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
  })
}
