import { useQuery } from '@tanstack/react-query'
import { AlertCircle, Building2, Clock3, MapPin, Target } from 'lucide-react'
import { AppContentLoader } from '../components/app/AppContentLoader'
import { EmptyState } from '../components/app/EmptyState'
import { useAuthenticatedRequest } from '../services/api'
import {
  formatOpportunityLocation,
  formatOpportunityStage,
  formatSignalKey,
  type RadarOpportunity,
} from '../services/opportunities'

export function OpportunitiesPage() {
  const request = useAuthenticatedRequest()
  const opportunities = useQuery({
    queryKey: ['radar-opportunities'],
    queryFn: () => request<RadarOpportunity[]>('/api/radar/opportunities'),
  })

  if (opportunities.isPending) return <AppContentLoader />

  return (
    <section className="app-content-page opportunities-page">
      <header className="app-page-heading opportunities-heading">
        <div>
          <p className="app-page-eyebrow">Workspace intelligence</p>
          <h1>Opportunities</h1>
          <p>
            Concise company intelligence combining what Radory discovered with
            what its investigation confirmed.
          </p>
        </div>
        {opportunities.data?.length ? (
          <span className="opportunities-count">
            {opportunities.data.length}{' '}
            {opportunities.data.length === 1 ? 'opportunity' : 'opportunities'}
          </span>
        ) : null}
      </header>

      {opportunities.isError ? (
        <div className="opportunities-error" role="alert">
          <AlertCircle aria-hidden="true" size={22} />
          <div>
            <strong>Opportunities could not be loaded.</strong>
            <p>{opportunities.error.message}</p>
          </div>
          <button type="button" onClick={() => void opportunities.refetch()}>
            Try again
          </button>
        </div>
      ) : opportunities.data?.length ? (
        <div className="opportunities-list">
          {opportunities.data.map((opportunity) => {
            const report = opportunity.report
            if (!report) return null
            const location = formatOpportunityLocation(report.locations)
            const timing = report.timing[0]?.expression
            return (
              <article className="opportunity-card" key={opportunity.id}>
                <div className="opportunity-card-topline">
                  <span
                    className={`opportunity-stage stage-${report.opportunity_stage.value}`}
                  >
                    {formatOpportunityStage(report.opportunity_stage.value)}
                  </span>
                  <span className="opportunity-sources">
                    {report.supporting_source_ids.length} supporting{' '}
                    {report.supporting_source_ids.length === 1
                      ? 'source'
                      : 'sources'}
                  </span>
                </div>

                <div className="opportunity-company">
                  <span className="opportunity-company-icon">
                    <Building2 aria-hidden="true" size={20} />
                  </span>
                  <div>
                    <p>{report.company_name}</p>
                    <h2>{report.headline.text}</h2>
                  </div>
                </div>

                <p className="opportunity-summary">{report.summary.text}</p>

                {(location || timing) && (
                  <div className="opportunity-meta">
                    {location && (
                      <span>
                        <MapPin aria-hidden="true" size={15} /> {location}
                      </span>
                    )}
                    {timing && (
                      <span>
                        <Clock3 aria-hidden="true" size={15} /> {timing}
                      </span>
                    )}
                  </div>
                )}

                <div className="opportunity-signals">
                  {report.signals.map((signal) => (
                    <span key={signal.signal_key}>
                      {formatSignalKey(signal.signal_key)}
                    </span>
                  ))}
                </div>

                <div className="opportunity-insight">
                  <strong>Why it matters</strong>
                  <p>{report.why_it_matters.text}</p>
                </div>

                <ul className="opportunity-findings">
                  {report.key_findings.slice(0, 3).map((finding) => (
                    <li key={finding.text}>{finding.text}</li>
                  ))}
                </ul>

                {report.open_questions.length > 0 && (
                  <div className="opportunity-open-question">
                    <Target aria-hidden="true" size={16} />
                    <span>{report.open_questions[0]}</span>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      ) : (
        <EmptyState
          icon={Target}
          title="No opportunities yet"
          description="Once your radar completes discovery and investigation, its unified company reports will appear here."
        />
      )}
    </section>
  )
}
