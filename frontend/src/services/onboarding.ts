export const propertySectors = [
  'Office',
  'Industrial / Logistics',
  'Retail',
  'Other',
] as const

export const industries = [
  'Technology',
  'Financial services',
  'Professional services',
  'Healthcare',
  'Manufacturing',
  'Logistics',
  'Consumer goods',
  'Education',
  'Any industry',
] as const

export const horizons = [
  '0–6 months',
  '6–12 months',
  '12–18 months',
  '18–24 months',
  '24+ months',
] as const

export const opportunityTypes = [
  'Expansion',
  'Relocation',
  'Renewal',
  'New market entry',
  'Consolidation',
  'Contraction / disposal',
  'Sublease',
] as const

export interface OnboardingState {
  brokerageName: string
  propertySectors: string[]
  country: string
  primaryMetro: string
  submarkets: string[]
  minimumSqm: string
  idealMinimumSqm: string
  idealMaximumSqm: string
  maximumSqm: string
  industries: string[]
  prospectingHorizon: string
  opportunityTypes: string[]
  priorities: string[]
}

export const initialOnboardingState: OnboardingState = {
  brokerageName: '',
  propertySectors: [],
  country: 'South Africa',
  primaryMetro: '',
  submarkets: [],
  minimumSqm: '',
  idealMinimumSqm: '',
  idealMaximumSqm: '',
  maximumSqm: '',
  industries: [],
  prospectingHorizon: '',
  opportunityTypes: [],
  priorities: [],
}

export interface PriorityOption {
  id: string
  label: string
  description: string
  symbol: string
}

const priority = (
  category: string,
  label: string,
  description: string,
  symbol: string,
): PriorityOption => ({
  id: `${category}:${label}`,
  label,
  description,
  symbol,
})

export function buildPriorityOptions(state: OnboardingState): PriorityOption[] {
  const options = [
    ...state.opportunityTypes.map((value) =>
      priority(
        'opportunity',
        value,
        `Prioritize companies showing ${value.toLowerCase()} evidence.`,
        '↗',
      ),
    ),
    ...state.submarkets.map((value) =>
      priority(
        'submarket',
        value,
        'Give more weight to this submarket.',
        '◉',
      ),
    ),
    ...state.industries
      .filter((value) => value !== 'Any industry')
      .map((value) =>
        priority(
          'industry',
          value,
          'Prioritize this tenant industry.',
          '◇',
        ),
      ),
    priority(
      'deal',
      'Ideal-size deals',
      'Favor opportunities fitting your preferred size range.',
      '□',
    ),
    priority(
      'timing',
      state.prospectingHorizon || 'Preferred timing',
      'Favor companies matching your prospecting horizon.',
      '▷',
    ),
  ]
  return options.filter(
    (option, index) => options.findIndex(({ id }) => id === option.id) === index,
  )
}

const numberValue = (value: string) => Number(value.replaceAll(',', '').trim())

export function validateStep(step: number, state: OnboardingState): string | null {
  if (step === 1 && state.brokerageName.trim().length < 2)
    return 'Enter your brokerage name.'
  if (step === 2) {
    if (!state.propertySectors.length) return 'Choose at least one property sector.'
    if (!state.country.trim()) return 'Enter a country.'
    if (!state.primaryMetro.trim()) return 'Enter your primary market or metro.'
    if (!state.submarkets.length) return 'Add at least one submarket or precinct.'
  }
  if (step === 3) {
    const sizes = [
      state.minimumSqm,
      state.idealMinimumSqm,
      state.idealMaximumSqm,
      state.maximumSqm,
    ].map(numberValue)
    if (sizes.some((value) => !Number.isFinite(value) || value < 0))
      return 'Enter valid transaction sizes.'
    if (!(sizes[0] <= sizes[1] && sizes[1] <= sizes[2] && sizes[2] <= sizes[3]))
      return 'Transaction sizes must increase from minimum to maximum.'
    if (!state.industries.length) return 'Choose at least one tenant industry.'
    if (state.industries.includes('Any industry') && state.industries.length > 1)
      return 'Any industry cannot be combined with another industry.'
  }
  if (step === 4) {
    if (!state.prospectingHorizon) return 'Choose a prospecting horizon.'
    if (!state.opportunityTypes.length)
      return 'Choose at least one real-estate situation.'
  }
  if (step === 5 && !state.priorities.length)
    return 'Choose at least one priority.'
  if (step === 5 && state.priorities.length > 3)
    return 'Choose no more than three priorities.'
  return null
}

export function toSetupPayload(state: OnboardingState) {
  return {
    brokerage_name: state.brokerageName.trim(),
    property_sectors: state.propertySectors,
    country: state.country.trim(),
    primary_metro: state.primaryMetro.trim(),
    submarkets: state.submarkets,
    minimum_sqm: numberValue(state.minimumSqm),
    ideal_minimum_sqm: numberValue(state.idealMinimumSqm),
    ideal_maximum_sqm: numberValue(state.idealMaximumSqm),
    maximum_sqm: numberValue(state.maximumSqm),
    industries: state.industries,
    prospecting_horizon: state.prospectingHorizon,
    opportunity_types: state.opportunityTypes,
    priorities: state.priorities,
  }
}
