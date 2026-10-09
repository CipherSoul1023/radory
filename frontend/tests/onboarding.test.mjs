import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildPriorityOptions,
  initialOnboardingState,
  toSetupPayload,
  validateStep,
} from '../src/services/onboarding.ts'

const complete = {
  ...initialOnboardingState,
  brokerageName: 'Northstar Tenant Advisory',
  propertySectors: ['Office'],
  primaryMetro: 'Johannesburg',
  submarkets: ['Sandton'],
  minimumSqm: '500',
  idealMinimumSqm: '1,500',
  idealMaximumSqm: '4,000',
  maximumSqm: '8,000',
  industries: ['Technology'],
  prospectingHorizon: '6–12 months',
  opportunityTypes: ['Expansion'],
  priorities: ['opportunity:Expansion'],
}

test('all five onboarding steps accept a complete tenant-rep profile', () => {
  for (let step = 1; step <= 5; step += 1)
    assert.equal(validateStep(step, complete), null)
})

test('transaction size validation requires an ordered range', () => {
  assert.match(
    validateStep(3, { ...complete, idealMaximumSqm: '200' }),
    /increase/,
  )
})

test('priorities are generated from prior answers', () => {
  const options = buildPriorityOptions(complete)
  assert.ok(options.some(({ id }) => id === 'opportunity:Expansion'))
  assert.ok(options.some(({ id }) => id === 'submarket:Sandton'))
  assert.ok(options.some(({ id }) => id === 'industry:Technology'))
  assert.ok(options.some(({ id }) => id === 'deal:Ideal-size deals'))
})

test('submission payload uses normalized numeric values', () => {
  const payload = toSetupPayload(complete)
  assert.equal(payload.ideal_minimum_sqm, 1500)
  assert.equal(payload.maximum_sqm, 8000)
  assert.deepEqual(payload.priorities, ['opportunity:Expansion'])
})

test('Any industry is rejected when combined with a specific industry', () => {
  assert.match(
    validateStep(3, {
      ...complete,
      industries: ['Any industry', 'Technology'],
    }),
    /industry/i,
  )
})
