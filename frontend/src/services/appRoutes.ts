export const APP_ROUTES = [
  { label: 'Dashboard', path: '/app', end: true },
  { label: 'Opportunities', path: '/app/opportunities', end: false },
  { label: 'Companies', path: '/app/companies', end: false },
  { label: 'Market Activity', path: '/app/market-activity', end: false },
  { label: 'Watchlist', path: '/app/watchlist', end: false },
  { label: 'Settings', path: '/app/settings', end: false },
] as const

export type AppRoutePath = (typeof APP_ROUTES)[number]['path']
