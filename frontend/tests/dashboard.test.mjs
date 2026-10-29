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
import {
  isRadarJobActive,
  radarProgressMessage,
} from '../src/services/radar.ts'

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

test('dashboard activates and polls the persisted radar pipeline', async () => {
  const dashboard = await readFile(
    new URL('../src/pages/WorkspaceDashboardPage.tsx', import.meta.url),
    'utf8',
  )
  assert.match(dashboard, /useAppWorkspace/)
  assert.match(dashboard, /Build your radar/)
  assert.match(dashboard, /\/api\/radar\/jobs/)
  assert.match(dashboard, /refetchInterval/)
  assert.match(dashboard, /View opportunities/)
  assert.doesNotMatch(dashboard, /James|John Doe|JD/)
  assert.doesNotMatch(dashboard, /tavily|nemotron|fetch\(|requestIdentity/i)
})

test('radar progress follows database-backed discovery and pipeline state', () => {
  const job = {
    id: 'job-1',
    status: 'running',
    pipeline_status: 'pending',
    pipeline_error_code: null,
    pipeline_error_message: null,
    total_queries: 26,
    pending_queries: 20,
    running_queries: 1,
    succeeded_queries: 5,
    failed_queries: 0,
    completed_opportunities: 0,
    failed_opportunities: 0,
    created: true,
  }

  assert.equal(isRadarJobActive(job), true)
  assert.equal(
    radarProgressMessage(job),
    'Searching for signals… 5 of 26 searches complete.',
  )

  const completed = {
    ...job,
    status: 'completed',
    pipeline_status: 'completed',
    completed_opportunities: 3,
  }
  assert.equal(isRadarJobActive(completed), false)
  assert.equal(
    radarProgressMessage(completed),
    'Your radar is ready with 3 opportunities.',
  )
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
