import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  addUniqueCustomValue,
  initialOnboardingState,
  priorityFactors,
  selectPrimaryMarket,
  toSetupPayload,
  toggleIndustry,
  togglePriorityFactor,
  validateStep,
} from '../src/services/onboarding.ts'
import {
  addPreparedSubmarket,
  filterSouthAfricanCities,
  filterSouthAfricanSubmarkets,
  removeSelectedSubmarket,
  southAfricanCities,
  southAfricanSubmarkets,
  submarketsForCity,
} from '../src/data/southAfricanGeography.ts'

const complete = {
  ...initialOnboardingState,
  brokerageName: 'Northstar Tenant Advisory',
  propertySectors: ['office', 'other'],
  customPropertySectors: ['Data centres'],
  primaryMarket: 'Johannesburg',
  submarkets: ['Sandton'],
  minTransactionSizeSqm: '500',
  idealTransactionSizeMinSqm: '1,500',
  idealTransactionSizeMaxSqm: '4,000',
  maxTransactionSizeSqm: '8,000',
  industries: ['technology', 'other'],
  customIndustries: ['PropTech'],
  prospectingHorizon: 'up_to_18_months',
  opportunityTypes: ['expansion', 'lease_renewal'],
  priorityFactors: ['location_fit', 'deal_size_fit', 'evidence_strength'],
}

test('all five onboarding steps accept a complete tenant-rep profile', () => {
  for (let step = 1; step <= 5; step += 1)
    assert.equal(validateStep(step, complete), null)
})

test('South Africa is fixed in initial state and payload', () => {
  assert.equal(initialOnboardingState.country, 'South Africa')
  assert.equal(toSetupPayload(complete).country, 'South Africa')
  assert.match(
    validateStep(2, { ...complete, country: 'Botswana' }),
    /South Africa/,
  )
})

test('city search is broad, unique, province-aware, and searchable', () => {
  assert.equal(southAfricanCities.length, 50)
  assert.equal(new Set(southAfricanCities.map(({ name }) => name)).size, 50)
  assert.equal(
    new Set(southAfricanCities.map(({ province }) => province)).size,
    9,
  )
  assert.deepEqual(
    filterSouthAfricanCities('Joh').map(({ name }) => name),
    ['Johannesburg'],
  )
  assert.deepEqual(
    filterSouthAfricanCities('Pre').map(({ name }) => name),
    ['Pretoria'],
  )
})

test('submarket suggestions depend on the selected city', () => {
  assert.ok(submarketsForCity('Johannesburg').includes('Sandton'))
  assert.ok(submarketsForCity('Cape Town').includes('Century City'))
  assert.ok(!submarketsForCity('Cape Town').includes('Sandton'))
  assert.deepEqual(submarketsForCity('Stellenbosch'), [])
  assert.deepEqual(
    new Set(
      filterSouthAfricanSubmarkets('', 'Johannesburg').map(({ name }) => name),
    ),
    new Set(submarketsForCity('Johannesburg')),
  )
  assert.ok(
    filterSouthAfricanSubmarkets('Century', 'Johannesburg').some(
      ({ name, market }) => name === 'Century City' && market === 'Cape Town',
    ),
  )
})

test('changing city clears selected submarkets but preserves other state', () => {
  const changed = selectPrimaryMarket(complete, 'Cape Town')
  assert.deepEqual(changed.submarkets, [])
  assert.equal(changed.brokerageName, complete.brokerageName)
  assert.deepEqual(changed.industries, complete.industries)
})

test('custom property and industry values remain supported while custom submarkets stay empty', () => {
  assert.deepEqual(addUniqueCustomValue(['Kramerville'], '  Linbro Park  '), [
    'Kramerville',
    'Linbro Park',
  ])
  assert.deepEqual(addUniqueCustomValue(['Kramerville'], 'kramerville'), [
    'Kramerville',
  ])
  const payload = toSetupPayload(complete)
  assert.deepEqual(payload.custom_property_sectors, ['Data centres'])
  assert.deepEqual(payload.custom_submarkets, [])
  assert.deepEqual(payload.custom_industries, ['PropTech'])
})

test('prepared submarket selection supports multiple chips, removal, and reselection', () => {
  const one = addPreparedSubmarket([], 'Sandton')
  const two = addPreparedSubmarket(one, 'Rosebank')
  assert.deepEqual(two, ['Sandton', 'Rosebank'])
  assert.ok(
    !filterSouthAfricanSubmarkets('', 'Johannesburg', two).some(
      ({ name }) => name === 'Sandton',
    ),
  )
  const removed = removeSelectedSubmarket(two, 'Sandton')
  assert.ok(
    filterSouthAfricanSubmarkets('', 'Johannesburg', removed).some(
      ({ name }) => name === 'Sandton',
    ),
  )
})

test('unknown typed submarkets cannot enter persisted state', () => {
  assert.deepEqual(addPreparedSubmarket(['Sandton'], 'random xyz'), ['Sandton'])
  assert.deepEqual(
    filterSouthAfricanSubmarkets('random xyz', 'Johannesburg'),
    [],
  )
  assert.equal(
    new Set(southAfricanSubmarkets.map(({ name }) => name)).size,
    southAfricanSubmarkets.length,
  )
})

test('market and submarket menus are portaled fixed overlays with no custom creation UI', () => {
  const component = readFileSync(
    new URL(
      '../src/components/onboarding/SearchableSelect.tsx',
      import.meta.url,
    ),
    'utf8',
  )
  const css = readFileSync(
    new URL('../src/pages/setupWorkspace.css', import.meta.url),
    'utf8',
  )
  assert.equal(component.match(/createPortal\(/g)?.length, 2)
  assert.match(component, /data-floating-overlay="true"/)
  assert.match(component, /No matching submarket found/)
  assert.doesNotMatch(component, /onAddCustom|chooseCustom|Add .*submarket/)
  assert.match(component, /Math\.min\(220, availableHeight\)/)
  assert.match(component, /safeBottomMargin = 20/)
  assert.doesNotMatch(component, /filtered\.slice/)
  assert.match(css, /\.setup-combobox-menu\s*\{[\s\S]*?position:\s*fixed/)
  assert.match(css, /\.setup-combobox-menu\s*\{[\s\S]*?z-index:\s*1000/)
  assert.match(css, /\.setup-combobox-menu\s*\{[\s\S]*?max-height:\s*220px/)
})

test('Other requires custom property-sector and tenant-industry values', () => {
  assert.match(
    validateStep(2, { ...complete, customPropertySectors: [] }),
    /custom property sector/,
  )
  assert.match(
    validateStep(3, { ...complete, customIndustries: [] }),
    /custom tenant industry/,
  )
})

test('Any industry is mutually exclusive and selecting a specific industry clears it', () => {
  assert.deepEqual(toggleIndustry(['technology'], 'any_industry'), [
    'any_industry',
  ])
  assert.deepEqual(toggleIndustry(['any_industry'], 'technology'), [
    'technology',
  ])
  assert.match(
    validateStep(3, {
      ...complete,
      industries: ['any_industry', 'technology'],
      customIndustries: [],
    }),
    /industry/i,
  )
})

test('transaction size validation requires positive ordered values', () => {
  assert.match(
    validateStep(3, { ...complete, idealTransactionSizeMaxSqm: '200' }),
    /increase/,
  )
  assert.match(
    validateStep(3, { ...complete, minTransactionSizeSqm: '0' }),
    /positive/,
  )
})

test('new maximum-horizon value and successful payload are preserved', () => {
  const payload = toSetupPayload(complete)
  assert.equal(payload.prospecting_horizon, 'up_to_18_months')
  assert.equal(payload.ideal_transaction_size_min_sqm, 1500)
  assert.equal(payload.max_transaction_size_sqm, 8000)
})

test('the final step has exactly seven fixed ranking factors and enforces three', () => {
  assert.deepEqual(
    priorityFactors.map(({ value }) => value),
    [
      'location_fit',
      'industry_fit',
      'property_sector_fit',
      'deal_size_fit',
      'opportunity_type_fit',
      'timing',
      'evidence_strength',
    ],
  )
  assert.deepEqual(
    togglePriorityFactor(
      ['location_fit', 'deal_size_fit', 'timing'],
      'industry_fit',
    ),
    ['location_fit', 'deal_size_fit', 'timing'],
  )
  assert.deepEqual(togglePriorityFactor(['location_fit'], 'location_fit'), [])
  assert.match(
    validateStep(5, { ...complete, priorityFactors: [] }),
    /at least one/,
  )
})

test('state values survive moving between steps and successful submission', () => {
  const stateAfterSteps = { ...complete }
  for (let step = 1; step <= 5; step += 1)
    assert.equal(validateStep(step, stateAfterSteps), null)
  const payload = toSetupPayload(stateAfterSteps)
  assert.equal(payload.brokerage_name, complete.brokerageName)
  assert.equal(payload.primary_market, 'Johannesburg')
  assert.deepEqual(payload.priority_factors, complete.priorityFactors)
})
