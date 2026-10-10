import { useClerk, useSession, useUser } from '@clerk/react'
import { useQueryClient } from '@tanstack/react-query'
import {
  ChevronLeft,
  ChevronRight,
  LockKeyhole,
  MapPin,
  Search,
  Sparkles,
  Star,
  TrendingUp,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import citySkyline from '../assets/auth/city-skyline.png'
import {
  SearchableCombobox,
  SearchableMultiCombobox,
  type SearchOption,
} from '../components/onboarding/SearchableSelect'
import { radoryLogo } from '../components/landing/landingAssets'
import {
  addPreparedSubmarket,
  findSouthAfricanCity,
  removeSelectedSubmarket,
  southAfricanCities,
  southAfricanSubmarkets,
} from '../data/southAfricanGeography'
import { useAuthenticatedRequest } from '../services/api'
import {
  addUniqueCustomValue,
  horizons,
  industries,
  initialOnboardingState,
  opportunityTypes,
  priorityFactors,
  propertySectors,
  selectPrimaryMarket,
  toSetupPayload,
  toggleIndustry,
  togglePriorityFactor,
  validateStep,
  type OnboardingState,
  type SelectOption,
} from '../services/onboarding'
import './setupWorkspace.css'

const steps = [
  'Brokerage',
  'Market & property',
  'Ideal clients',
  'Opportunities',
  'Priorities',
]
const cityOptions: SearchOption[] = southAfricanCities.map(
  ({ id, name, province }) => ({
    id,
    label: name,
    meta: province,
  }),
)

interface SetupStatus {
  status: 'needs_setup' | 'provisioning' | 'ready'
  organization_id: string | null
}

interface SetupResponse {
  workspace_id: string
  organization_id: string
  organization_name: string
  status: 'ready'
}

function ChoicePills({
  options,
  selected,
  onToggle,
  single = false,
}: {
  options: readonly SelectOption[]
  selected: string[]
  onToggle: (value: string) => void
  single?: boolean
}) {
  return (
    <div className="setup-pills" role={single ? 'radiogroup' : 'group'}>
      {options.map((option) => {
        const active = selected.includes(option.value)
        return (
          <button
            aria-checked={active}
            className={`setup-pill${active ? ' is-selected' : ''}`}
            key={option.value}
            onClick={() => onToggle(option.value)}
            role={single ? 'radio' : 'checkbox'}
            type="button"
          >
            {active && <span className="setup-check">✓</span>}
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

function CustomValuesField({
  id,
  label,
  examples,
  values,
  onChange,
}: {
  id: string
  label: string
  examples: string
  values: string[]
  onChange: (values: string[]) => void
}) {
  const [input, setInput] = useState('')
  const addValue = () => {
    const next = addUniqueCustomValue(values, input)
    if (next !== values) {
      onChange(next)
      setInput('')
    }
  }
  return (
    <div className="setup-custom-field">
      <label htmlFor={id}>{label}</label>
      <div className="setup-add-row">
        <input
          id={id}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              addValue()
            }
          }}
          placeholder={examples}
          value={input}
        />
        <button onClick={addValue} type="button">
          Add
        </button>
      </div>
      {values.length > 0 && (
        <div className="setup-tags">
          {values.map((value) => (
            <button
              key={value}
              onClick={() => onChange(values.filter((item) => item !== value))}
              type="button"
            >
              {value}
              <X aria-hidden="true" size={12} />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function FieldError({ message }: { message: string }) {
  return (
    <p className="setup-error" role="alert">
      {message}
    </p>
  )
}

export function SetupWorkspacePage() {
  const [step, setStep] = useState(1)
  const [state, setState] = useState<OnboardingState>(initialOnboardingState)
  const [validationError, setValidationError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [marketChangeNotice, setMarketChangeNotice] = useState('')
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const request = useAuthenticatedRequest()
  const clerk = useClerk()
  const { session } = useSession()
  const { user } = useUser()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const openWorkspace = async (organizationId: string) => {
    await clerk.setActive({ organization: organizationId })
    await session?.reload()
    await queryClient.invalidateQueries({ queryKey: ['workspace-memberships'] })
    navigate('/app', { replace: true })
  }

  useEffect(() => {
    let cancelled = false
    void request<SetupStatus>('/api/workspace/setup-status')
      .then(async (status) => {
        if (!cancelled && status.status === 'ready' && status.organization_id)
          await openWorkspace(status.organization_id)
      })
      .catch((error: unknown) => {
        if (!cancelled)
          setSubmitError(
            error instanceof Error
              ? error.message
              : 'Unable to load workspace setup.',
          )
      })
      .finally(() => {
        if (!cancelled) setLoadingStatus(false)
      })
    return () => {
      cancelled = true
    }
    // Run once for this mounted authenticated setup route.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const update = <K extends keyof OnboardingState>(
    key: K,
    value: OnboardingState[K],
  ) => setState((current) => ({ ...current, [key]: value }))

  const toggle = (
    key: 'propertySectors' | 'opportunityTypes',
    value: string,
  ) => {
    const values = state[key]
    const next = values.includes(value)
      ? values.filter((item) => item !== value)
      : [...values, value]
    setState((current) => ({
      ...current,
      [key]: next,
      ...(key === 'propertySectors' &&
      value === 'other' &&
      !next.includes('other')
        ? { customPropertySectors: [] }
        : {}),
    }))
  }

  const chooseMarket = (option: SearchOption) => {
    const changed = Boolean(
      state.primaryMarket && state.primaryMarket !== option.label,
    )
    const hadSubmarkets = state.submarkets.length > 0
    setState((current) => selectPrimaryMarket(current, option.label))
    setMarketChangeNotice(
      changed && hadSubmarkets
        ? 'Your previous submarket selections were cleared for the new primary market.'
        : '',
    )
  }

  const next = () => {
    const error = validateStep(step, state)
    if (error) {
      setValidationError(error)
      return
    }
    setValidationError('')
    setStep((current) => Math.min(5, current + 1))
  }

  const submit = async () => {
    for (let currentStep = 1; currentStep <= 5; currentStep += 1) {
      const error = validateStep(currentStep, state)
      if (error) {
        setStep(currentStep)
        setValidationError(error)
        return
      }
    }
    setSubmitting(true)
    setSubmitError('')
    try {
      const result = await request<SetupResponse>('/api/workspace/setup', {
        method: 'POST',
        body: JSON.stringify(toSetupPayload(state)),
      })
      await openWorkspace(result.organization_id)
    } catch (submitFailure) {
      setSubmitError(
        submitFailure instanceof Error
          ? submitFailure.message
          : 'Workspace creation failed. Please retry.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  const selectedCity = findSouthAfricanCity(state.primaryMarket)
  const selectedCityOption = selectedCity
    ? {
        id: selectedCity.id,
        label: selectedCity.name,
        meta: selectedCity.province,
      }
    : null
  const submarketOptions: SearchOption[] = southAfricanSubmarkets.map(
    ({ id, name, market, province }) => ({
      id,
      label: name,
      meta: `${market} · ${province}`,
      preferred: market === state.primaryMarket,
    }),
  )
  const hasMarketSuggestions = submarketOptions.some(
    ({ preferred }) => preferred,
  )
  const initials =
    [user?.firstName, user?.lastName]
      .filter(Boolean)
      .map((part) => part?.[0])
      .join('') || 'R'

  const headings = [
    ['Brokerage', 'Name the brokerage that this workspace represents.'],
    [
      'Market & Property Coverage',
      'Define the commercial property and South African markets your team covers.',
    ],
    [
      'Ideal Client / Deal Profile',
      'Describe the tenant businesses and space requirements that suit your brokerage.',
    ],
    [
      'Opportunity Preferences',
      'Choose the situations and timing your team wants to pursue.',
    ],
    [
      'Priority Factors',
      'Select up to three factors Radory should emphasize when ordering relevant opportunities.',
    ],
  ] as const

  return (
    <div className="setup-app">
      <header className="setup-topbar">
        <img className="setup-logo" src={radoryLogo} alt="Radory" />
        <nav className="setup-nav" aria-label="Workspace navigation">
          <span>Intelligence</span>
          <span>Companies</span>
          <span>Markets</span>
          <span>Opportunities</span>
          <span className="is-active">My Workspace</span>
        </nav>
        <div className="setup-search">
          <Search size={15} /> Search companies, markets, or opportunities...
        </div>
        <div className="setup-avatar" aria-label="Signed-in user">
          {initials}
        </div>
      </header>

      <div className="setup-layout">
        <main className="setup-main">
          <div className="setup-overline">Onboarding</div>
          <div className="setup-heading">
            <div>
              <h1>Set up your brokerage workspace</h1>
              <p>
                Define which tenant opportunities suit your brokerage, then
                choose what should matter most when Radory orders those matches.
              </p>
            </div>
            <div className="setup-steps" aria-label={`Step ${step} of 5`}>
              {steps.map((label, index) => {
                const number = index + 1
                return (
                  <div
                    className={`setup-step${number === step ? ' is-active' : ''}${number < step ? ' is-done' : ''}`}
                    key={label}
                  >
                    <div className="setup-step-circle">
                      {number < step ? '✓' : number}
                    </div>
                    <div>{label}</div>
                  </div>
                )
              })}
            </div>
          </div>

          <section className="setup-card">
            <div className="setup-card-head">
              <div className="setup-number">{step}</div>
              <div>
                <h2>{headings[step - 1][0]}</h2>
                <p>{headings[step - 1][1]}</p>
              </div>
            </div>
            <div className="setup-card-body">
              {step === 1 && (
                <>
                  <div className="setup-field">
                    <label htmlFor="brokerage-name">
                      What is the name of your brokerage?
                    </label>
                    <input
                      id="brokerage-name"
                      autoComplete="organization"
                      placeholder="e.g. ABC Commercial"
                      value={state.brokerageName}
                      onChange={(event) =>
                        update('brokerageName', event.target.value)
                      }
                    />
                    <small>
                      This will be used as the name of your Radory workspace.
                    </small>
                  </div>
                  <div className="setup-notice">
                    Radory currently supports tenant-representation prospecting.
                  </div>
                </>
              )}

              {step === 2 && (
                <>
                  <div className="setup-field">
                    <label>
                      Which types of commercial property do you represent
                      tenants in?
                    </label>
                    <p className="setup-helper">
                      Property sector describes the type of space your clients
                      need — for example offices, warehouses or retail space.
                      This is different from tenant industry, which describes
                      what the tenant&apos;s business does.
                    </p>
                    <ChoicePills
                      options={propertySectors}
                      selected={state.propertySectors}
                      onToggle={(value) => toggle('propertySectors', value)}
                    />
                    {state.propertySectors.includes('other') && (
                      <CustomValuesField
                        id="custom-property-sector"
                        label="Add another property sector"
                        examples="e.g. Data centres"
                        values={state.customPropertySectors}
                        onChange={(values) =>
                          update('customPropertySectors', values)
                        }
                      />
                    )}
                  </div>
                  <div className="setup-grid-two">
                    <div className="setup-field">
                      <label>Which country do you operate in?</label>
                      <div className="setup-locked-field">
                        South Africa{' '}
                        <LockKeyhole aria-label="Locked" size={15} />
                      </div>
                    </div>
                    <div className="setup-field">
                      <label htmlFor="primary-market">
                        What is your primary market?
                      </label>
                      <p className="setup-helper">
                        Select the South African city or metro where you
                        primarily prospect for tenant opportunities.
                      </p>
                      <SearchableCombobox
                        id="primary-market"
                        options={cityOptions}
                        value={selectedCityOption}
                        placeholder="Search South African cities"
                        onSelect={chooseMarket}
                      />
                    </div>
                  </div>
                  {state.primaryMarket && (
                    <div className="setup-field">
                      <label htmlFor="submarkets">
                        Which submarkets, precincts or business districts do you
                        usually work in?
                      </label>
                      <p className="setup-helper">
                        Optional — search and select the areas you regularly
                        cover.
                      </p>
                      <SearchableMultiCombobox
                        id="submarkets"
                        options={submarketOptions}
                        selected={state.submarkets}
                        placeholder="Search submarkets..."
                        onSelect={(value) =>
                          update(
                            'submarkets',
                            addPreparedSubmarket(state.submarkets, value),
                          )
                        }
                        onRemove={(value) =>
                          update(
                            'submarkets',
                            removeSelectedSubmarket(state.submarkets, value),
                          )
                        }
                      />
                      {!hasMarketSuggestions && (
                        <small>
                          No market-specific suggestions are available yet. Type
                          to search the broader prepared South African list.
                        </small>
                      )}
                      {marketChangeNotice && (
                        <p className="setup-state-notice" role="status">
                          {marketChangeNotice}
                        </p>
                      )}
                    </div>
                  )}
                </>
              )}

              {step === 3 && (
                <>
                  <div className="setup-field">
                    <label>
                      What size space requirements are the best fit for your
                      brokerage?
                    </label>
                    <p className="setup-helper">
                      Enter the approximate floor area of tenant requirements
                      you typically want to pursue.
                    </p>
                    <div className="setup-size-grid">
                      <label>
                        Minimum size
                        <div className="setup-unit-input">
                          <input
                            aria-label="Minimum size"
                            inputMode="numeric"
                            placeholder="500"
                            value={state.minTransactionSizeSqm}
                            onChange={(event) =>
                              update(
                                'minTransactionSizeSqm',
                                event.target.value,
                              )
                            }
                          />
                          <span>m²</span>
                        </div>
                      </label>
                      <label>
                        Ideal range
                        <div className="setup-ideal-range">
                          <div className="setup-unit-input">
                            <input
                              aria-label="Ideal minimum size"
                              inputMode="numeric"
                              placeholder="1,500"
                              value={state.idealTransactionSizeMinSqm}
                              onChange={(event) =>
                                update(
                                  'idealTransactionSizeMinSqm',
                                  event.target.value,
                                )
                              }
                            />
                            <span>m²</span>
                          </div>
                          <b>to</b>
                          <div className="setup-unit-input">
                            <input
                              aria-label="Ideal maximum size"
                              inputMode="numeric"
                              placeholder="4,000"
                              value={state.idealTransactionSizeMaxSqm}
                              onChange={(event) =>
                                update(
                                  'idealTransactionSizeMaxSqm',
                                  event.target.value,
                                )
                              }
                            />
                            <span>m²</span>
                          </div>
                        </div>
                      </label>
                      <label>
                        Maximum size
                        <div className="setup-unit-input">
                          <input
                            aria-label="Maximum size"
                            inputMode="numeric"
                            placeholder="8,000"
                            value={state.maxTransactionSizeSqm}
                            onChange={(event) =>
                              update(
                                'maxTransactionSizeSqm',
                                event.target.value,
                              )
                            }
                          />
                          <span>m²</span>
                        </div>
                      </label>
                    </div>
                  </div>
                  <div className="setup-field">
                    <label>
                      Which types of businesses do you most often want to
                      represent?
                    </label>
                    <p className="setup-helper">
                      Tenant industry describes what the company does, not the
                      type of property it occupies.
                    </p>
                    <ChoicePills
                      options={industries}
                      selected={state.industries}
                      onToggle={(value) => {
                        const next = toggleIndustry(state.industries, value)
                        setState((current) => ({
                          ...current,
                          industries: next,
                          customIndustries: next.includes('other')
                            ? current.customIndustries
                            : [],
                        }))
                      }}
                    />
                    {state.industries.includes('other') && (
                      <CustomValuesField
                        id="custom-industry"
                        label="Add another tenant industry"
                        examples="e.g. Life sciences"
                        values={state.customIndustries}
                        onChange={(values) =>
                          update('customIndustries', values)
                        }
                      />
                    )}
                    <small>
                      Any industry keeps your profile broad and cannot be
                      combined with another industry.
                    </small>
                  </div>
                </>
              )}

              {step === 4 && (
                <>
                  <div className="setup-field">
                    <label>
                      How early would you like Radory to surface a company
                      before it may need to make a property decision?
                    </label>
                    <p className="setup-helper">
                      Earlier opportunities may have weaker evidence but give
                      you more time to build a relationship. Nearer-term
                      opportunities may be more actionable but could already be
                      competitive.
                    </p>
                    <ChoicePills
                      options={horizons}
                      selected={
                        state.prospectingHorizon
                          ? [state.prospectingHorizon]
                          : []
                      }
                      single
                      onToggle={(value) => update('prospectingHorizon', value)}
                    />
                  </div>
                  <div className="setup-field">
                    <label>
                      Which tenant real-estate situations are you interested in
                      pursuing?
                    </label>
                    <p className="setup-helper">
                      Choose the situations where you would want Radory to alert
                      you to a potential tenant-representation opportunity.
                    </p>
                    <ChoicePills
                      options={opportunityTypes}
                      selected={state.opportunityTypes}
                      onToggle={(value) => toggle('opportunityTypes', value)}
                    />
                  </div>
                </>
              )}

              {step === 5 && (
                <>
                  <div className="setup-field">
                    <label>
                      What should matter most when Radory ranks your
                      opportunities?
                    </label>
                    <p className="setup-helper">
                      Your profile already tells Radory what is relevant. Now
                      choose the factors Radory should give the most weight when
                      deciding which matching opportunities appear first.
                    </p>
                  </div>
                  <div className="setup-priority-grid">
                    {priorityFactors.map((option) => {
                      const selected = state.priorityFactors.includes(
                        option.value,
                      )
                      return (
                        <button
                          aria-pressed={selected}
                          className={`setup-priority${selected ? ' is-selected' : ''}`}
                          key={option.value}
                          type="button"
                          onClick={() =>
                            update(
                              'priorityFactors',
                              togglePriorityFactor(
                                state.priorityFactors,
                                option.value,
                              ),
                            )
                          }
                        >
                          <span className="setup-priority-top">
                            <span>{option.symbol}</span>
                            <span className="setup-dot" />
                          </span>
                          <span>
                            <b>{option.label}</b>
                            <small>{option.description}</small>
                          </span>
                        </button>
                      )
                    })}
                  </div>
                  <p className="setup-count">
                    {state.priorityFactors.length} of 3 priority factors
                    selected
                  </p>
                  <p className="setup-helper">
                    These choices affect ordering only. Radory will still
                    consider every matching factor in your profile.
                  </p>
                </>
              )}

              {validationError && <FieldError message={validationError} />}
              {submitError && <FieldError message={submitError} />}
            </div>
          </section>

          <div className="setup-actions">
            <button
              className="setup-button"
              disabled={step === 1 || submitting}
              onClick={() => {
                setValidationError('')
                setStep((current) => Math.max(1, current - 1))
              }}
              type="button"
            >
              <ChevronLeft size={17} /> Back
            </button>
            <button
              className="setup-button is-primary"
              disabled={loadingStatus || submitting}
              onClick={() => void (step === 5 ? submit() : next())}
              type="button"
            >
              {submitting
                ? 'Creating workspace…'
                : step === 5
                  ? 'Create workspace'
                  : 'Continue'}
              {!submitting && <ChevronRight size={17} />}
            </button>
          </div>
        </main>

        <aside className="setup-side">
          <div
            className="setup-side-card"
            style={
              { '--setup-city': `url(${citySkyline})` } as React.CSSProperties
            }
          >
            <div className="setup-side-inner">
              <img src={radoryLogo} alt="Radory" />
              <h3>Smarter opportunities for tenant reps.</h3>
              <p>
                Your answers define the opportunities that fit your brokerage
                and the factors that should move the strongest matches higher.
              </p>
              <div className="setup-benefit">
                <span>
                  <MapPin size={17} />
                </span>
                <div>
                  <b>Relevant markets</b>
                  <small>
                    Your markets, submarkets, industries and property sectors
                    define a good fit.
                  </small>
                </div>
              </div>
              <div className="setup-benefit">
                <span>
                  <TrendingUp size={17} />
                </span>
                <div>
                  <b>Brokerage fit</b>
                  <small>
                    Deal size, timing and property context help order relevant
                    companies.
                  </small>
                </div>
              </div>
              <div className="setup-benefit">
                <span>
                  <Star size={17} />
                </span>
                <div>
                  <b>Your priorities</b>
                  <small>
                    Your top factors influence which matching opportunities
                    appear first.
                  </small>
                </div>
              </div>
              <div className="setup-tip">
                <b>
                  <Sparkles size={14} /> Tenant-representation first
                </b>
                <p>
                  This onboarding is focused on tenant-representation
                  prospecting.
                </p>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
