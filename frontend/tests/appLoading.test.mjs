import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { APP_ROUTES } from '../src/services/appRoutes.ts'
import { workspaceDecision } from '../src/services/workspacePolicy.ts'

const [authRouting, appLayout, appLoader, appRouter] = await Promise.all([
  readFile(
    new URL('../src/components/auth/AuthRouting.tsx', import.meta.url),
    'utf8',
  ),
  readFile(
    new URL('../src/components/app/AppLayout.tsx', import.meta.url),
    'utf8',
  ),
  readFile(
    new URL('../src/components/app/AppContentLoader.tsx', import.meta.url),
    'utf8',
  ),
  readFile(new URL('../src/App.tsx', import.meta.url), 'utf8'),
])

test('initial workspace resolution retains the full-screen brokerage loader', () => {
  assert.match(authRouting, /if \(memberships\.isPending\)/)
  assert.match(authRouting, /Loading your brokerage…/)
})

test('membership resolution is cached across child-route navigation', () => {
  assert.match(
    authRouting,
    /queryKey: \['workspace-memberships', session\?\.id, orgId\]/,
  )
  assert.doesNotMatch(authRouting, /location\.key/)
  assert.doesNotMatch(authRouting, /isPending \|\| memberships\.isFetching/)
})

for (const { label, path } of APP_ROUTES.filter(
  ({ path }) => path !== '/app',
)) {
  test(`in-app navigation to ${label} keeps workspace loading out of ${path}`, () => {
    const childPath = path.replace('/app/', '')
    assert.match(appRouter, new RegExp(`path="${childPath}"`))
    assert.match(
      appRouter,
      new RegExp(`lazy\\(\\(\\) =>[\\s\\S]*${label.replace(' ', '')}Page`),
    )
    assert.doesNotMatch(appLoader, /Loading your brokerage/)
  })
}

test('sidebar, topbar, and active brokerage remain mounted around in-app loading', () => {
  const sidebarIndex = appLayout.indexOf('<AppSidebar />')
  const topbarIndex = appLayout.indexOf('<AppTopbar')
  const suspenseIndex = appLayout.indexOf('<Suspense')
  const outletIndex = appLayout.indexOf('<Outlet')
  assert.ok(sidebarIndex >= 0)
  assert.ok(topbarIndex > sidebarIndex)
  assert.ok(suspenseIndex > topbarIndex)
  assert.ok(outletIndex > suspenseIndex)
  assert.match(appLayout, /fallback={<AppContentLoader \/>}/)
  assert.match(appLayout, /workspaceName={workspaceName}/)
})

test('direct deep-link refresh may use initial workspace loading before the app shell', () => {
  assert.match(authRouting, /if \(memberships\.isPending\)/)
  assert.match(authRouting, /location\.pathname\.startsWith\('\/app'\)/)
  assert.match(appRouter, /path="opportunities"/)
})

test('invited-member membership routing remains unchanged', () => {
  const membership = {
    organization: { id: 'org_invited', name: 'Invited Brokerage' },
    role: 'org:member',
  }
  assert.deepEqual(workspaceDecision([membership], 'org_invited', true), {
    kind: 'app',
    organizationId: 'org_invited',
  })
})
