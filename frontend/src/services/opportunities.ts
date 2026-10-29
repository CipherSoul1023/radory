export type OpportunityNarrative = {
  text: string
  observation_ids: string[]
}

export type OpportunitySignal = {
  signal_key: string
  observation_ids: string[]
}

export type OpportunityLocation = {
  country: string | null
  market: string | null
  submarket: string | null
  observation_ids: string[]
}

export type OpportunityTiming = {
  expression: string
  observation_ids: string[]
}

export type RadarOpportunityReport = {
  company_name: string
  headline: OpportunityNarrative
  summary: OpportunityNarrative
  opportunity_stage: {
    value:
      | 'potential_future'
      | 'active_evaluation'
      | 'committed'
      | 'fulfilled'
      | 'weak_speculative'
      | 'unknown'
      | 'cancelled'
    observation_ids: string[]
  }
  signals: OpportunitySignal[]
  why_it_matters: OpportunityNarrative
  key_findings: OpportunityNarrative[]
  locations: OpportunityLocation[]
  timing: OpportunityTiming[]
  open_questions: string[]
  supporting_source_ids: string[]
}

export type RadarOpportunity = {
  id: string
  workspace_id: string
  search_job_id: string
  subject_company: string
  status: 'running' | 'completed' | 'failed'
  report: RadarOpportunityReport | null
  created_at: string
  updated_at: string
}

const stageLabels: Record<
  RadarOpportunityReport['opportunity_stage']['value'],
  string
> = {
  potential_future: 'Potential future',
  active_evaluation: 'Active evaluation',
  committed: 'Committed',
  fulfilled: 'Fulfilled',
  weak_speculative: 'Early signal',
  unknown: 'Stage unknown',
  cancelled: 'Cancelled',
}

export function formatOpportunityStage(
  stage: RadarOpportunityReport['opportunity_stage']['value'],
) {
  return stageLabels[stage]
}

export function formatSignalKey(signalKey: string) {
  return signalKey
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

export function formatOpportunityLocation(locations: OpportunityLocation[]) {
  if (!locations.length) return null
  const location = locations[0]
  return [location.submarket, location.market, location.country]
    .filter(Boolean)
    .join(', ')
}
