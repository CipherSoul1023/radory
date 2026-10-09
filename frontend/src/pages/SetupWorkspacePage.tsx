import { useClerk, useSession, useUser } from '@clerk/react'
import { useQueryClient } from '@tanstack/react-query'
import {
  ChevronLeft,
  ChevronRight,
  MapPin,
  Search,
  Sparkles,
  Star,
  TrendingUp,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import citySkyline from '../assets/auth/city-skyline.png'
import { radoryLogo } from '../components/landing/landingAssets'
import { useAuthenticatedRequest } from '../services/api'
import {
  buildPriorityOptions,
  horizons,
  industries,
  initialOnboardingState,
  opportunityTypes,
  propertySectors,
  toSetupPayload,
  validateStep,
  type OnboardingState,
} from '../services/onboarding'
import './setupWorkspace.css'

const steps = ['Brokerage', 'Coverage', 'Clients', 'Opportunities', 'Priorities']
const metroSuggestions = [
  'Johannesburg',
  'Cape Town',
  'Pretoria / Tshwane',
  'Durban',
  'Gqeberha',
  'Bloemfontein',
]

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
  options: readonly string[]
  selected: string[]
  onToggle: (value: string) => void
  single?: boolean
}) {
  return (
    <div className="setup-pills" role={single ? 'radiogroup' : 'group'}>
      {options.map((option) => {
        const active = selected.includes(option)
        return (
          <button
            aria-checked={active}
            className={`setup-pill${active ? ' is-selected' : ''}`}
            key={option}
            onClick={() => onToggle(option)}
            role={single ? 'radio' : 'checkbox'}
            type="button"
          >
            {active && <span className="setup-check">✓</span>}
            {option}
          </button>
        )
      })}
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
  const [submarket, setSubmarket] = useState('')
  const [validationError, setValidationError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const request = useAuthenticatedRequest()
  const clerk = useClerk()
  const { session } = useSession()
  const { user } = useUser()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const priorityOptions = useMemo(() => buildPriorityOptions(state), [state])

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
            error instanceof Error ? error.message : 'Unable to load workspace setup.',
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
  ) =>
    setState((current) => {
      const next = { ...current, [key]: value }
      if (
        ![
          'propertySectors',
          'submarkets',
          'industries',
          'prospectingHorizon',
          'opportunityTypes',
        ].includes(key)
      )
        return next
      const validPriorities = new Set(buildPriorityOptions(next).map(({ id }) => id))
      return {
        ...next,
        priorities: next.priorities.filter((id) => validPriorities.has(id)),
      }
    })

  const toggle = (
    key: 'propertySectors' | 'industries' | 'opportunityTypes',
    value: string,
  ) => {
    const values = state[key]
    if (key === 'industries' && value === 'Any industry') {
      update(key, values.includes(value) ? [] : [value])
      return
    }
    const withoutAny = key === 'industries' ? values.filter((item) => item !== 'Any industry') : values
    update(
      key,
      withoutAny.includes(value)
        ? withoutAny.filter((item) => item !== value)
        : [...withoutAny, value],
    )
  }

  const addSubmarket = () => {
    const value = submarket.trim()
    if (!value || state.submarkets.some((item) => item.toLowerCase() === value.toLowerCase()))
      return
    update('submarkets', [...state.submarkets, value])
    setSubmarket('')
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

  const initials =
    [user?.firstName, user?.lastName]
      .filter(Boolean)
      .map((part) => part?.[0])
      .join('') || 'R'

  return (
    <div className="setup-app">
      <header className="setup-topbar">
        <img className="setup-logo" src={radoryLogo} alt="Radory" />
        <nav className="setup-nav" aria-label="Workspace navigation">
          <span>Intelligence</span><span>Companies</span><span>Markets</span>
          <span>Opportunities</span><span className="is-active">My Workspace</span>
        </nav>
        <div className="setup-search"><Search size={15} /> Search companies, markets, or opportunities...</div>
        <div className="setup-avatar" aria-label="Signed-in user">{initials}</div>
      </header>

      <div className="setup-layout">
        <main className="setup-main">
          <div className="setup-overline">Onboarding</div>
          <div className="setup-heading">
            <div>
              <h1>Set up your brokerage workspace</h1>
              <p>Tell Radory what your tenant-representation team targets so we can build the right search coverage and rank the most relevant opportunities.</p>
            </div>
            <div className="setup-steps" aria-label={`Step ${step} of 5`}>
              {steps.map((label, index) => {
                const number = index + 1
                return (
                  <div className={`setup-step${number === step ? ' is-active' : ''}${number < step ? ' is-done' : ''}`} key={label}>
                    <div className="setup-step-circle">{number < step ? '✓' : number}</div>
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
                <h2>{steps[step - 1] === 'Coverage' ? 'Market coverage' : steps[step - 1] === 'Clients' ? 'Client focus' : steps[step - 1] === 'Opportunities' ? 'Opportunity preferences' : steps[step - 1] === 'Priorities' ? 'What should Radory prioritize?' : 'Brokerage'}</h2>
                <p>{step === 1 ? 'Your workspace will use your brokerage name.' : step === 2 ? 'Define the markets, submarkets and property sectors your team covers.' : step === 3 ? 'Tell Radory what deal sizes and tenant sectors matter to you.' : step === 4 ? 'Define the situations and timing you want Radory to surface.' : 'Choose up to 3 priorities for opportunity ranking.'}</p>
              </div>
            </div>
            <div className="setup-card-body">
              {step === 1 && (
                <>
                  <div className="setup-field">
                    <label htmlFor="brokerage-name">What is your brokerage name?</label>
                    <input id="brokerage-name" autoComplete="organization" placeholder="e.g. ABC Commercial" value={state.brokerageName} onChange={(event) => update('brokerageName', event.target.value)} />
                    <small>This becomes the name of your Radory workspace.</small>
                  </div>
                  <div className="setup-notice"><b>Tenant representation only for this version.</b><br />Radory is currently focused on tenant-representation prospecting, so this onboarding does not ask you to choose landlord representation.</div>
                </>
              )}

              {step === 2 && (
                <>
                  <div className="setup-field"><label>Which property sectors do you work in?</label><ChoicePills options={propertySectors} selected={state.propertySectors} onToggle={(value) => toggle('propertySectors', value)} /></div>
                  <div className="setup-grid-two">
                    <div className="setup-field"><label htmlFor="country">Country</label><input id="country" value={state.country} onChange={(event) => update('country', event.target.value)} /></div>
                    <div className="setup-field"><label htmlFor="metro">Primary market / metro</label><input id="metro" list="metro-options" placeholder="e.g. Johannesburg" value={state.primaryMetro} onChange={(event) => update('primaryMetro', event.target.value)} /><datalist id="metro-options">{metroSuggestions.map((metro) => <option key={metro} value={metro} />)}</datalist></div>
                  </div>
                  <div className="setup-field">
                    <label htmlFor="submarket">Which submarkets or precincts do you actively cover?</label>
                    <div className="setup-add-row"><input id="submarket" placeholder="e.g. Sandton" value={submarket} onChange={(event) => setSubmarket(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addSubmarket() } }} /><button type="button" onClick={addSubmarket}>Add submarket</button></div>
                    <div className="setup-tags">{state.submarkets.map((item) => <button type="button" key={item} onClick={() => update('submarkets', state.submarkets.filter((value) => value !== item))}>{item}<span aria-hidden="true">×</span></button>)}</div>
                    <small>Add each market your team actively covers. Select a tag to remove it.</small>
                  </div>
                </>
              )}

              {step === 3 && (
                <>
                  <div className="setup-field">
                    <label>What size transactions do you typically pursue?</label>
                    <div className="setup-size-grid">
                      <div><input aria-label="Minimum square metres" inputMode="numeric" placeholder="500" value={state.minimumSqm} onChange={(event) => update('minimumSqm', event.target.value)} /><small>Minimum m²</small></div>
                      <div className="setup-ideal-range"><input aria-label="Ideal minimum square metres" inputMode="numeric" placeholder="1,500" value={state.idealMinimumSqm} onChange={(event) => update('idealMinimumSqm', event.target.value)} /><span>–</span><input aria-label="Ideal maximum square metres" inputMode="numeric" placeholder="4,000" value={state.idealMaximumSqm} onChange={(event) => update('idealMaximumSqm', event.target.value)} /><small>Ideal range m²</small></div>
                      <div><input aria-label="Maximum square metres" inputMode="numeric" placeholder="8,000" value={state.maximumSqm} onChange={(event) => update('maximumSqm', event.target.value)} /><small>Maximum m²</small></div>
                    </div>
                  </div>
                  <div className="setup-field"><label>Which tenant industries do you actively target?</label><ChoicePills options={industries} selected={state.industries} onToggle={(value) => toggle('industries', value)} /><small>“Any industry” keeps your search universe broad and cannot be combined with another industry.</small></div>
                </>
              )}

              {step === 4 && (
                <>
                  <div className="setup-field"><label>How far ahead of a potential property decision do you want Radory to surface companies?</label><ChoicePills options={horizons} selected={state.prospectingHorizon ? [state.prospectingHorizon] : []} single onToggle={(value) => update('prospectingHorizon', value)} /><small>This is used for ranking after Radory estimates timing from company evidence.</small></div>
                  <div className="setup-field"><label>Which real-estate situations do you want to pursue?</label><ChoicePills options={opportunityTypes} selected={state.opportunityTypes} onToggle={(value) => toggle('opportunityTypes', value)} /></div>
                </>
              )}

              {step === 5 && (
                <>
                  <div className="setup-notice"><b>No repeated questionnaire.</b><br />These choices come from the markets, industries, opportunity types and deal preferences you already selected.</div>
                  <div className="setup-priority-grid">
                    {priorityOptions.map((option) => {
                      const selected = state.priorities.includes(option.id)
                      return (
                        <button aria-pressed={selected} className={`setup-priority${selected ? ' is-selected' : ''}`} key={option.id} type="button" onClick={() => { if (!selected && state.priorities.length >= 3) return; update('priorities', selected ? state.priorities.filter((id) => id !== option.id) : [...state.priorities, option.id]) }}>
                          <span className="setup-priority-top"><span>{option.symbol}</span><span className="setup-dot" /></span>
                          <span><b>{option.label}</b><small>{option.description}</small></span>
                        </button>
                      )
                    })}
                  </div>
                  <p className="setup-count">{state.priorities.length} of 3 priorities selected</p>
                </>
              )}

              {validationError && <FieldError message={validationError} />}
              {submitError && <FieldError message={submitError} />}
            </div>
          </section>

          <div className="setup-actions">
            <button className="setup-button" disabled={step === 1 || submitting} onClick={() => { setValidationError(''); setStep((current) => Math.max(1, current - 1)) }} type="button"><ChevronLeft size={17} /> Back</button>
            <button className="setup-button is-primary" disabled={loadingStatus || submitting} onClick={() => void (step === 5 ? submit() : next())} type="button">{submitting ? 'Creating workspace…' : step === 5 ? 'Create workspace' : 'Continue'}{!submitting && <ChevronRight size={17} />}</button>
          </div>
        </main>

        <aside className="setup-side">
          <div className="setup-side-card" style={{ '--setup-city': `url(${citySkyline})` } as React.CSSProperties}>
            <div className="setup-side-inner">
              <img src={radoryLogo} alt="Radory" />
              <h3>Smarter opportunities for tenant reps.</h3>
              <p>Your answers shape Radory’s search coverage and opportunity ranking, so your workspace focuses on the companies most relevant to your brokerage.</p>
              <div className="setup-benefit"><span><MapPin size={17} /></span><div><b>Search coverage</b><small>Markets, submarkets, industries and opportunity types guide discovery.</small></div></div>
              <div className="setup-benefit"><span><TrendingUp size={17} /></span><div><b>Brokerage fit</b><small>Deal size, timing and property context help rank companies.</small></div></div>
              <div className="setup-benefit"><span><Star size={17} /></span><div><b>Your priorities</b><small>Your top selections influence what appears first.</small></div></div>
              <div className="setup-tip"><b><Sparkles size={14} /> Tenant-representation first</b><p>This onboarding is intentionally focused on tenant-rep prospecting.</p></div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
