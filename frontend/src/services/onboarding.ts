export interface SelectOption {
  value: string
  label: string
}

export const propertySectors: readonly SelectOption[] = [
  { value: 'office', label: 'Office' },
  { value: 'industrial_logistics', label: 'Industrial / Logistics' },
  { value: 'retail', label: 'Retail' },
  { value: 'other', label: 'Other' },
]

export const industries: readonly SelectOption[] = [
  { value: 'technology', label: 'Technology' },
  { value: 'financial_services', label: 'Financial services' },
  { value: 'professional_services', label: 'Professional services' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'manufacturing', label: 'Manufacturing' },
  { value: 'logistics', label: 'Logistics' },
  { value: 'retail_businesses', label: 'Retail businesses' },
  { value: 'telecommunications', label: 'Telecommunications' },
  { value: 'media', label: 'Media' },
  { value: 'energy', label: 'Energy' },
  { value: 'legal_services', label: 'Legal services' },
  { value: 'government_public_sector', label: 'Government / Public sector' },
  { value: 'other', label: 'Other' },
  { value: 'any_industry', label: 'Any industry' },
]

export const horizons: readonly SelectOption[] = [
  { value: 'up_to_6_months', label: 'Up to 6 months' },
  { value: 'up_to_12_months', label: 'Up to 12 months' },
  { value: 'up_to_18_months', label: 'Up to 18 months' },
  { value: 'up_to_24_months', label: 'Up to 24 months' },
  { value: 'as_early_as_possible', label: 'As early as possible' },
]

export const opportunityTypes: readonly SelectOption[] = [
  { value: 'expansion', label: 'Expansion' },
  { value: 'relocation', label: 'Relocation' },
  { value: 'lease_renewal', label: 'Lease renewal' },
  { value: 'new_market_entry', label: 'New market entry' },
  { value: 'consolidation', label: 'Consolidation' },
  {
    value: 'contraction_space_disposal',
    label: 'Contraction / space disposal',
  },
  { value: 'sublease', label: 'Sublease' },
]

export interface PriorityFactor extends SelectOption {
  description: string
  symbol: string
}

export const priorityFactors: readonly PriorityFactor[] = [
  {
    value: 'location_fit',
    label: 'Location fit',
    description:
      'Prioritize companies whose likely property needs align closely with your selected markets and submarkets.',
    symbol: '◎',
  },
  {
    value: 'industry_fit',
    label: 'Industry fit',
    description:
      'Prioritize companies operating in the tenant industries your brokerage prefers.',
    symbol: '◇',
  },
  {
    value: 'property_sector_fit',
    label: 'Property sector fit',
    description:
      'Prioritize opportunities that best match the types of commercial property you specialize in.',
    symbol: '▦',
  },
  {
    value: 'deal_size_fit',
    label: 'Deal size fit',
    description:
      'Prioritize opportunities whose estimated space requirement is closest to your ideal transaction size.',
    symbol: '□',
  },
  {
    value: 'opportunity_type_fit',
    label: 'Opportunity type fit',
    description:
      'Prioritize companies whose likely situation matches the opportunity types you want to pursue.',
    symbol: '↗',
  },
  {
    value: 'timing',
    label: 'Timing',
    description:
      'Prioritize opportunities expected to reach a property decision sooner.',
    symbol: '▷',
  },
  {
    value: 'evidence_strength',
    label: 'Evidence strength',
    description:
      'Prioritize opportunities supported by stronger and more reliable evidence.',
    symbol: '★',
  },
]

export interface OnboardingState {
  brokerageName: string
  propertySectors: string[]
  customPropertySectors: string[]
  country: 'South Africa'
  primaryMarket: string
  submarkets: string[]
  minTransactionSizeSqm: string
  idealTransactionSizeMinSqm: string
  idealTransactionSizeMaxSqm: string
  maxTransactionSizeSqm: string
  industries: string[]
  customIndustries: string[]
  prospectingHorizon: string
  opportunityTypes: string[]
  priorityFactors: string[]
}

export const initialOnboardingState: OnboardingState = {
  brokerageName: '',
  propertySectors: [],
  customPropertySectors: [],
  country: 'South Africa',
  primaryMarket: '',
  submarkets: [],
  minTransactionSizeSqm: '',
  idealTransactionSizeMinSqm: '',
  idealTransactionSizeMaxSqm: '',
  maxTransactionSizeSqm: '',
  industries: [],
  customIndustries: [],
  prospectingHorizon: '',
  opportunityTypes: [],
  priorityFactors: [],
}

export function addUniqueCustomValue(
  values: string[],
  candidate: string,
): string[] {
  const value = candidate.trim()
  return !value ||
    values.some(
      (item) => item.toLocaleLowerCase() === value.toLocaleLowerCase(),
    )
    ? values
    : [...values, value]
}

export function selectPrimaryMarket(
  state: OnboardingState,
  primaryMarket: string,
): OnboardingState {
  if (state.primaryMarket === primaryMarket) return state
  return { ...state, primaryMarket, submarkets: [] }
}

export function toggleIndustry(values: string[], value: string): string[] {
  if (value === 'any_industry') return values.includes(value) ? [] : [value]
  const withoutAny = values.filter((item) => item !== 'any_industry')
  return withoutAny.includes(value)
    ? withoutAny.filter((item) => item !== value)
    : [...withoutAny, value]
}

export function togglePriorityFactor(
  values: string[],
  value: string,
): string[] {
  if (values.includes(value)) return values.filter((item) => item !== value)
  return values.length < 3 ? [...values, value] : values
}

const numberValue = (value: string) => Number(value.replaceAll(',', '').trim())

export function validateStep(
  step: number,
  state: OnboardingState,
): string | null {
  if (step === 1 && state.brokerageName.trim().length < 2)
    return 'Enter your brokerage name.'
  if (step === 2) {
    if (!state.propertySectors.length)
      return 'Choose at least one property sector.'
    if (
      state.propertySectors.includes('other') &&
      !state.customPropertySectors.length
    )
      return 'Add at least one custom property sector.'
    if (state.country !== 'South Africa')
      return 'Radory currently supports South Africa only.'
    if (!state.primaryMarket.trim()) return 'Choose your primary market.'
  }
  if (step === 3) {
    const sizes = [
      state.minTransactionSizeSqm,
      state.idealTransactionSizeMinSqm,
      state.idealTransactionSizeMaxSqm,
      state.maxTransactionSizeSqm,
    ].map(numberValue)
    if (sizes.some((value) => !Number.isFinite(value) || value <= 0))
      return 'Enter a positive number for every transaction size.'
    if (!(sizes[0] <= sizes[1] && sizes[1] <= sizes[2] && sizes[2] <= sizes[3]))
      return 'Transaction sizes must increase from minimum through the ideal range to maximum.'
    if (!state.industries.length) return 'Choose at least one tenant industry.'
    if (
      state.industries.includes('any_industry') &&
      (state.industries.length > 1 || state.customIndustries.length)
    )
      return 'Any industry cannot be combined with another industry.'
    if (state.industries.includes('other') && !state.customIndustries.length)
      return 'Add at least one custom tenant industry.'
  }
  if (step === 4) {
    if (!state.prospectingHorizon) return 'Choose a prospecting horizon.'
    if (!state.opportunityTypes.length)
      return 'Choose at least one real-estate situation.'
  }
  if (step === 5 && !state.priorityFactors.length)
    return 'Choose at least one priority factor.'
  if (step === 5 && state.priorityFactors.length > 3)
    return 'Choose no more than three priority factors.'
  return null
}

export function toSetupPayload(state: OnboardingState) {
  return {
    brokerage_name: state.brokerageName.trim(),
    property_sectors: state.propertySectors,
    custom_property_sectors: state.customPropertySectors,
    country: state.country,
    primary_market: state.primaryMarket.trim(),
    submarkets: state.submarkets,
    // Deprecated API compatibility field. Active product behavior never populates it.
    custom_submarkets: [],
    min_transaction_size_sqm: numberValue(state.minTransactionSizeSqm),
    ideal_transaction_size_min_sqm: numberValue(
      state.idealTransactionSizeMinSqm,
    ),
    ideal_transaction_size_max_sqm: numberValue(
      state.idealTransactionSizeMaxSqm,
    ),
    max_transaction_size_sqm: numberValue(state.maxTransactionSizeSqm),
    industries: state.industries,
    custom_industries: state.customIndustries,
    prospecting_horizon: state.prospectingHorizon,
    opportunity_types: state.opportunityTypes,
    priority_factors: state.priorityFactors,
  }
}
