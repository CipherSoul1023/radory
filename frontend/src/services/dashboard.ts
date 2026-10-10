export type DashboardCard = {
  title: string
  emptyState: string
  description: string
  icon: 'opportunities' | 'signals' | 'market' | 'watchlist'
}

export const EMPTY_DASHBOARD_CARDS: readonly DashboardCard[] = [
  {
    title: 'Priority Opportunities',
    emptyState: 'No opportunities discovered yet.',
    description:
      'Build your radar to find companies approaching commercial property decisions.',
    icon: 'opportunities',
  },
  {
    title: 'Recent Signals',
    emptyState: 'No signals discovered yet.',
    description:
      'Signals from company activity will appear here after your radar begins researching.',
    icon: 'signals',
  },
  {
    title: 'Market Activity',
    emptyState: 'Your market intelligence will appear here.',
    description:
      'See relevant activity across the markets and tenant segments your brokerage targets.',
    icon: 'market',
  },
  {
    title: 'Watchlist Updates',
    emptyState: 'No companies on your watchlist yet.',
    description:
      'Tracked company updates will appear here once you begin using your radar.',
    icon: 'watchlist',
  },
]

export function getBrokerageInitials(name: string): string {
  const words = name
    .trim()
    .split(/\s+/)
    .map((word) => word.match(/[\p{L}\p{N}]/u)?.[0])
    .filter((character): character is string => Boolean(character))

  if (words.length > 1) return words.slice(0, 2).join('').toLocaleUpperCase()

  const characters = name.match(/[\p{L}\p{N}]/gu) ?? []
  return characters.slice(0, 2).join('').toLocaleUpperCase() || 'R'
}

export function isWorkspaceAdmin(role: string): boolean {
  return role === 'org:admin' || role === 'admin'
}

export function getMemberRadarMessage(workspaceName: string) {
  return {
    heading: `${workspaceName}'s radar hasn't been activated yet.`,
    detail: 'An administrator can build it from this dashboard.',
  }
}
