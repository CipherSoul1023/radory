import {
  horizons,
  industries,
  opportunityTypes,
  priorityFactors,
  propertySectors,
  type SelectOption,
} from './onboarding.ts'

export interface BrokerageProfile {
  workspace_id: string
  organization_id: string
  brokerage_name: string
  property_sectors: string[]
  custom_property_sectors: string[]
  country: 'South Africa'
  primary_market: string
  submarkets: string[]
  custom_submarkets: string[]
  min_transaction_size_sqm: number
  ideal_transaction_size_min_sqm: number
  ideal_transaction_size_max_sqm: number
  max_transaction_size_sqm: number
  industries: string[]
  custom_industries: string[]
  prospecting_horizon: string
  opportunity_types: string[]
  priority_factors: string[]
}

export function humanizeValue(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part, index) =>
      index === 0 ? part.charAt(0).toLocaleUpperCase() + part.slice(1) : part,
    )
    .join(' ')
}

export function optionLabel(
  value: string,
  options: readonly SelectOption[],
): string {
  return (
    options.find((option) => option.value === value)?.label ??
    humanizeValue(value)
  )
}

export function optionLabels(
  values: readonly string[],
  options: readonly SelectOption[],
  customValues: readonly string[] = [],
): string[] {
  return [
    ...values.map((value) => optionLabel(value, options)),
    ...customValues,
  ]
}

export function formatWorkspaceRole(role: string): string {
  return humanizeValue(role.replace(/^org:/, ''))
}

export function formatSquareMetres(value: number): string {
  return `${new Intl.NumberFormat('en-ZA').format(value)} m²`
}

export function presentBrokerageProfile(profile: BrokerageProfile) {
  return {
    propertySectors: optionLabels(
      profile.property_sectors,
      propertySectors,
      profile.custom_property_sectors,
    ),
    submarkets: profile.submarkets,
    tenantIndustries: optionLabels(
      profile.industries,
      industries,
      profile.custom_industries,
    ),
    prospectingHorizon: optionLabel(profile.prospecting_horizon, horizons),
    opportunityTypes: optionLabels(profile.opportunity_types, opportunityTypes),
    priorityFactors: optionLabels(profile.priority_factors, priorityFactors),
    transactionSizes: {
      minimum: formatSquareMetres(profile.min_transaction_size_sqm),
      idealMinimum: formatSquareMetres(profile.ideal_transaction_size_min_sqm),
      idealMaximum: formatSquareMetres(profile.ideal_transaction_size_max_sqm),
      maximum: formatSquareMetres(profile.max_transaction_size_sqm),
    },
  }
}
