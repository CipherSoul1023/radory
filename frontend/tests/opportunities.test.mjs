import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import {
  formatOpportunityLocation,
  formatOpportunityStage,
  formatSignalKey,
} from '../src/services/opportunities.ts'

test('formats persisted opportunity report values for display', () => {
  assert.equal(formatOpportunityStage('active_evaluation'), 'Active evaluation')
  assert.equal(formatSignalKey('office_relocation'), 'Office Relocation')
  assert.equal(
    formatOpportunityLocation([
      {
        country: 'South Africa',
        market: 'Johannesburg',
        submarket: 'Sandton',
        observation_ids: ['observation-1'],
      },
    ]),
    'Sandton, Johannesburg, South Africa',
  )
  assert.equal(formatOpportunityLocation([]), null)
})

test('loads workspace-scoped persisted opportunities without starting research', () => {
  const source = readFileSync(
    new URL('../src/pages/OpportunitiesPage.tsx', import.meta.url),
    'utf8',
  )

  assert.match(source, /useAuthenticatedRequest/)
  assert.match(source, /['"]\/api\/radar\/opportunities['"]/)
  assert.doesNotMatch(source, /Tavily|Nemotron|from-observation/)
})
