import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { APP_ROUTES } from '../src/services/appRoutes.ts'
import {
  formatWorkspaceRole,
  presentBrokerageProfile,
} from '../src/services/settings.ts'

const profile = {
  workspace_id: 'workspace_private',
  organization_id: 'org_private',
  brokerage_name: 'ABC Commercial',
  property_sectors: ['office', 'industrial_logistics'],
  custom_property_sectors: [],
  country: 'South Africa',
  primary_market: 'Johannesburg',
  submarkets: [],
  custom_submarkets: [],
  min_transaction_size_sqm: 500,
  ideal_transaction_size_min_sqm: 1500,
  ideal_transaction_size_max_sqm: 4000,
  max_transaction_size_sqm: 8000,
  industries: ['technology'],
  custom_industries: [],
  prospecting_horizon: 'up_to_18_months',
  opportunity_types: ['lease_renewal', 'expansion'],
  priority_factors: ['property_sector_fit', 'evidence_strength'],
}

test('application navigation defines every real app route', () => {
  assert.deepEqual(
    APP_ROUTES.map(({ label, path }) => [label, path]),
    [
      ['Dashboard', '/app'],
      ['Opportunities', '/app/opportunities'],
      ['Companies', '/app/companies'],
      ['Market Activity', '/app/market-activity'],
      ['Watchlist', '/app/watchlist'],
      ['Settings', '/app/settings'],
    ],
  )
})

test('nested router renders every application page and preserves deep app routes', async () => {
  const [app, authRouting] = await Promise.all([
    readFile(new URL('../src/App.tsx', import.meta.url), 'utf8'),
    readFile(
      new URL('../src/components/auth/AuthRouting.tsx', import.meta.url),
      'utf8',
    ),
  ])
  for (const route of [
    'opportunities',
    'companies',
    'market-activity',
    'watchlist',
    'settings',
  ]) {
    assert.match(app, new RegExp(`path="${route}"`))
  }
  assert.match(app, /<Route index element={<WorkspaceDashboardPage/)
  assert.match(authRouting, /location\.pathname\.startsWith\('\/app'\)/)
  assert.doesNotMatch(authRouting, /location\.pathname !== '\/app'/)
})

test('shared sidebar uses route-aware links and shared layout owns workspace header', async () => {
  const [sidebar, layout, topbar] = await Promise.all([
    readFile(
      new URL('../src/components/app/AppSidebar.tsx', import.meta.url),
      'utf8',
    ),
    readFile(
      new URL('../src/components/app/AppLayout.tsx', import.meta.url),
      'utf8',
    ),
    readFile(
      new URL('../src/components/app/AppTopbar.tsx', import.meta.url),
      'utf8',
    ),
  ])
  assert.match(sidebar, /NavLink/)
  assert.match(sidebar, /isActive/)
  assert.match(layout, /<Outlet context=/)
  assert.match(topbar, /Active brokerage/)
  assert.match(topbar, /workspaceName/)
  assert.match(topbar, /Search companies, opportunities, signals\.\.\./)
  assert.match(topbar, /No matching Radory intelligence yet\./)
  assert.doesNotMatch(topbar, /Tavily|fetch\(|useQuery/i)
})

test('saved brokerage profile is presented with onboarding labels and optional empty submarkets', () => {
  const presented = presentBrokerageProfile(profile)
  assert.deepEqual(presented.propertySectors, [
    'Office',
    'Industrial / Logistics',
  ])
  assert.deepEqual(presented.submarkets, [])
  assert.equal(presented.prospectingHorizon, 'Up to 18 months')
  assert.deepEqual(presented.opportunityTypes, ['Lease renewal', 'Expansion'])
  assert.deepEqual(presented.priorityFactors, [
    'Property sector fit',
    'Evidence strength',
  ])
  assert.deepEqual(presented.transactionSizes, {
    minimum: '500 m²',
    idealMinimum: '1 500 m²',
    idealMaximum: '4 000 m²',
    maximum: '8 000 m²',
  })
})

test('workspace roles are human readable', () => {
  assert.equal(formatWorkspaceRole('org:admin'), 'Admin')
  assert.equal(formatWorkspaceRole('org:member'), 'Member')
})

test('Settings uses authenticated profile and Clerk account data with real logout states', async () => {
  const settings = await readFile(
    new URL('../src/pages/SettingsPage.tsx', import.meta.url),
    'utf8',
  )
  assert.match(settings, /\/api\/workspace\/brokerage-profile/)
  assert.match(settings, /useAuthenticatedRequest/)
  assert.match(settings, /useUser\(\)/)
  assert.match(settings, /primaryEmailAddress/)
  assert.match(settings, /profile\.isPending/)
  assert.match(settings, /profile\.isError/)
  assert.match(settings, /profile\.refetch/)
  assert.match(settings, /signOut\({ redirectUrl: '\/' }\)/)
  assert.doesNotMatch(settings, /workspace_private|org_private/)
})

test('all product routes use honest empty-state pages without demo records', async () => {
  const pages = await Promise.all(
    [
      'OpportunitiesPage.tsx',
      'CompaniesPage.tsx',
      'MarketActivityPage.tsx',
      'WatchlistPage.tsx',
    ].map((page) =>
      readFile(new URL(`../src/pages/${page}`, import.meta.url), 'utf8'),
    ),
  )
  const combined = pages.join('\n')
  assert.match(combined, /No opportunities yet/)
  assert.match(combined, /No companies discovered yet/)
  assert.match(combined, /No market activity yet/)
  assert.match(combined, /Your watchlist is empty/)
  assert.doesNotMatch(combined, /mock|demo|sample company/i)
})
