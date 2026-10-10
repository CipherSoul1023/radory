import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import {
  EMPTY_DASHBOARD_CARDS,
  getBrokerageInitials,
  getMemberRadarMessage,
  isWorkspaceAdmin,
} from '../src/services/dashboard.ts'
import { workspaceDecision } from '../src/services/workspacePolicy.ts'

test('brokerage initials are derived from the real workspace name', () => {
  assert.equal(getBrokerageInitials('ABC Commercial'), 'AC')
  assert.equal(getBrokerageInitials('  South Point Properties  '), 'SP')
  assert.equal(getBrokerageInitials('Radory'), 'RA')
})

test('only the Clerk organization admin role receives the admin dashboard', () => {
  assert.equal(isWorkspaceAdmin('org:admin'), true)
  assert.equal(isWorkspaceAdmin('admin'), true)
  assert.equal(isWorkspaceAdmin('org:member'), false)
})

test('members receive workspace-aware waiting copy', () => {
  assert.deepEqual(getMemberRadarMessage('ABC Commercial'), {
    heading: "ABC Commercial's radar hasn't been activated yet.",
    detail: 'An administrator can build it from this dashboard.',
  })
})

test('the first-time dashboard defines all four approved empty cards', () => {
  assert.deepEqual(
    EMPTY_DASHBOARD_CARDS.map(({ title }) => title),
    [
      'Priority Opportunities',
      'Recent Signals',
      'Market Activity',
      'Watchlist Updates',
    ],
  )
})

test('an invited workspace member reaches the app dashboard without onboarding', () => {
  const invitedMembership = {
    organization: { id: 'org_invited', name: 'Invited Brokerage' },
    role: 'org:member',
  }
  assert.deepEqual(
    workspaceDecision([invitedMembership], 'org_invited', true),
    { kind: 'app', organizationId: 'org_invited' },
  )
  assert.equal(isWorkspaceAdmin(invitedMembership.role), false)
})

test('dashboard uses workspace context and keeps Build your radar local-only', async () => {
  const dashboard = await readFile(
    new URL('../src/pages/WorkspaceDashboardPage.tsx', import.meta.url),
    'utf8',
  )
  assert.match(dashboard, /useAppWorkspace/)
  assert.match(dashboard, /Build your radar/)
  assert.match(dashboard, /research pipeline is connected/)
  assert.doesNotMatch(dashboard, /James|John Doe|JD/)
  assert.doesNotMatch(dashboard, /tavily|fetch\(|requestIdentity|useQuery/i)
})

test('shared app shell CSS includes tablet, mobile, and reduced-motion layouts', async () => {
  const styles = await readFile(
    new URL('../src/components/appShell.css', import.meta.url),
    'utf8',
  )
  assert.match(styles, /@media \(max-width: 1180px\)/)
  assert.match(styles, /@media \(max-width: 820px\)/)
  assert.match(styles, /@media \(max-width: 600px\)/)
  assert.match(styles, /@media \(prefers-reduced-motion: reduce\)/)
})
