export async function configureMonitoring() {
  const sentryDsn = import.meta.env.VITE_SENTRY_DSN
  if (sentryDsn) {
    const Sentry = await import('@sentry/react')
    Sentry.init({ dsn: sentryDsn })
  }

  const posthogKey = import.meta.env.VITE_POSTHOG_KEY
  if (posthogKey) {
    const { default: posthog } = await import('posthog-js')
    posthog.init(posthogKey, {
      api_host: import.meta.env.VITE_POSTHOG_HOST || 'https://us.i.posthog.com',
      autocapture: false,
      capture_pageview: false,
    })
  }
}
