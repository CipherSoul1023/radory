import test from 'node:test'
import assert from 'node:assert/strict'
import { sendClerkEmailVerificationCode } from '../src/services/auth.ts'

test('successful email-code delivery enters verification only after Clerk accepts the request', async () => {
  let acceptRequest
  let verificationVisible = false
  const request = new Promise((resolve) => {
    acceptRequest = resolve
  })

  const delivery = sendClerkEmailVerificationCode(request).then(() => {
    verificationVisible = true
  })

  await Promise.resolve()
  assert.equal(verificationVisible, false)
  acceptRequest({ error: null })
  await delivery
  assert.equal(verificationVisible, true)
})

test('failed email-code delivery stays off verification and logs a safe Clerk error code', async () => {
  const originalError = console.error
  const logged = []
  let verificationVisible = false
  console.error = (...args) => logged.push(args)
  const clerkError = {
    errors: [{ code: 'email_delivery_failed', longMessage: 'Delivery failed' }],
    token: 'must-not-be-logged',
  }

  try {
    await assert.rejects(
      sendClerkEmailVerificationCode(
        Promise.resolve({ error: clerkError }),
      ).then(() => {
        verificationVisible = true
      }),
      (error) => error === clerkError,
    )
  } finally {
    console.error = originalError
  }

  assert.deepEqual(logged, [
    [
      'Clerk email verification code request failed.',
      { code: 'email_delivery_failed' },
    ],
  ])
  assert.equal(verificationVisible, false)
  assert.equal(JSON.stringify(logged).includes('must-not-be-logged'), false)
})
