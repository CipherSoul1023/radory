import test from 'node:test'
import assert from 'node:assert/strict'
import {
  hasInvitationContext,
  withInvitationContext,
} from '../src/services/auth.ts'
import { workspaceDecision } from '../src/services/workspacePolicy.ts'

const first = {
  organization: { id: 'org_one', name: 'First brokerage' },
  role: 'org:admin',
}
const second = {
  organization: { id: 'org_two', name: 'Second brokerage' },
  role: 'org:member',
}

function assertInvitedMemberReachesApp(path) {
  assert.equal(hasInvitationContext(path.split('?')[1] ?? ''), true)
  assert.deepEqual(workspaceDecision([first], null, true), {
    kind: 'activate',
    organizationId: 'org_one',
  })
  assert.deepEqual(workspaceDecision([first], 'org_one', true), {
    kind: 'app',
    organizationId: 'org_one',
  })
}

test('new users reach setup only after an empty membership response', () => {
  assert.deepEqual(workspaceDecision([], null, false), { kind: 'setup' })
})
test('invitation recipients with no visible membership never enter setup', () => {
  assert.deepEqual(workspaceDecision([], null, true), {
    kind: 'invitation-pending',
  })
})
test('invitation sign-in continuation preserves context through membership and app', () => {
  assertInvitedMemberReachesApp(withInvitationContext('/sign-in', true))
})
test('Clerk invitation signup preserves context through membership and app', () => {
  const invitationSignup =
    '/sign-up?__clerk_ticket=test-ticket&__clerk_status=sign_up'
  assertInvitedMemberReachesApp(invitationSignup)
})
test('invitation password reset and return preserve context through membership and app', () => {
  const forgotPassword = withInvitationContext('/forgot-password', true)
  assert.equal(hasInvitationContext(forgotPassword.split('?')[1] ?? ''), true)
  const returnToSignIn = withInvitationContext('/sign-in', true)
  assertInvitedMemberReachesApp(returnToSignIn)
})
test('a sole membership is activated before app access', () => {
  assert.deepEqual(workspaceDecision([first], null, false), {
    kind: 'activate',
    organizationId: 'org_one',
  })
})
test('accepted invitations use their existing membership', () => {
  assert.deepEqual(workspaceDecision([first], null, true), {
    kind: 'activate',
    organizationId: 'org_one',
  })
})
test('a valid active organization is honored among multiple memberships', () => {
  assert.deepEqual(workspaceDecision([first, second], 'org_two', true), {
    kind: 'app',
    organizationId: 'org_two',
  })
})
test('multiple memberships require a deliberate choice without an active organization', () => {
  assert.deepEqual(workspaceDecision([first, second], null, false), {
    kind: 'choose',
  })
})
test('a stale or revoked active organization cannot grant app access', () => {
  assert.deepEqual(workspaceDecision([first, second], 'org_removed', false), {
    kind: 'choose',
  })
  assert.deepEqual(workspaceDecision([], 'org_removed', true), {
    kind: 'invitation-pending',
  })
  assert.deepEqual(workspaceDecision([first], 'org_removed', false), {
    kind: 'activate',
    organizationId: 'org_one',
  })
})
