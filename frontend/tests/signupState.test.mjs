import test from 'node:test'
import assert from 'node:assert/strict'
import { hasInvitationContext } from '../src/services/auth.ts'
import {
  hasActiveSignUpAttempt,
  hasNewSignUpIntent,
  signUpEntryAction,
  withActiveSignUpAttempt,
  withNewSignUpIntent,
  withoutSignUpAttemptMarkers,
} from '../src/services/signupState.ts'

const staleVerification = {
  activeAttempt: false,
  invited: false,
  newSignup: false,
  status: 'missing_requirements',
  needsEmailVerification: true,
}

test('stale verification state on a fresh sign-up entry resets to the form', () => {
  assert.equal(signUpEntryAction(staleVerification), 'reset-to-form')
})

test('email A abandonment followed by a landing CTA explicitly starts email B signup', () => {
  const abandoned = withActiveSignUpAttempt('/sign-up')
  assert.equal(hasActiveSignUpAttempt(abandoned.split('?')[1]), true)

  const landingDestination = withNewSignUpIntent('/sign-up')
  const landingSearch = landingDestination.split('?')[1]
  assert.equal(hasNewSignUpIntent(landingSearch), true)
  assert.equal(
    signUpEntryAction({
      ...staleVerification,
      activeAttempt: true,
      newSignup: true,
    }),
    'reset-to-form',
  )

  const cleanEntry = withoutSignUpAttemptMarkers(landingDestination)
  assert.equal(cleanEntry, '/sign-up')
  const emailBVerification = withActiveSignUpAttempt(cleanEntry)
  assert.equal(hasActiveSignUpAttempt(emailBVerification.split('?')[1]), true)
})

test('an active current signup keeps the verification step', () => {
  const path = withActiveSignUpAttempt('/sign-up')
  assert.equal(hasActiveSignUpAttempt(path.split('?')[1]), true)
  assert.equal(
    signUpEntryAction({
      ...staleVerification,
      activeAttempt: true,
    }),
    'show-verification',
  )
})

test('successful verification continues normally', () => {
  assert.equal(
    signUpEntryAction({
      activeAttempt: true,
      invited: false,
      newSignup: false,
      status: 'complete',
      needsEmailVerification: false,
    }),
    'continue',
  )
})

test('starting over removes active state and returns to a clean form entry', () => {
  const cleanPath = withoutSignUpAttemptMarkers(
    '/sign-up?signup_attempt=active',
  )
  assert.equal(cleanPath, '/sign-up')
  assert.equal(hasActiveSignUpAttempt(cleanPath), false)
  assert.equal(signUpEntryAction(staleVerification), 'reset-to-form')
})

test('using a different email resets the same active verification state', () => {
  const cleanPath = withoutSignUpAttemptMarkers(
    '/sign-up?signup_attempt=active',
  )
  assert.equal(cleanPath, '/sign-up')
  assert.equal(hasActiveSignUpAttempt(cleanPath), false)
})

test('explicit new signup overrides an active signup attempt', () => {
  assert.equal(
    signUpEntryAction({
      ...staleVerification,
      activeAttempt: true,
      newSignup: true,
    }),
    'reset-to-form',
  )
})

test('invitation signup preserves invitation context while resetting local progress', () => {
  const invitation =
    '/sign-up?__clerk_ticket=test-ticket&__clerk_status=sign_up&signup_attempt=active'
  const restarted = withoutSignUpAttemptMarkers(invitation)
  const search = restarted.split('?')[1]
  assert.equal(hasInvitationContext(search), true)
  assert.equal(hasActiveSignUpAttempt(search), false)
  assert.equal(
    signUpEntryAction({
      activeAttempt: false,
      invited: true,
      newSignup: false,
      status: 'missing_requirements',
      needsEmailVerification: false,
    }),
    'show-form',
  )
})

test('new signup reset removes control markers but preserves invitation parameters', () => {
  const invitation =
    '/sign-up?__clerk_ticket=test-ticket&__clerk_status=sign_up&signup_attempt=active&new=1'
  const reset = withoutSignUpAttemptMarkers(invitation)
  const search = reset.split('?')[1]
  assert.equal(hasInvitationContext(search), true)
  assert.equal(hasActiveSignUpAttempt(search), false)
  assert.equal(hasNewSignUpIntent(search), false)
})
