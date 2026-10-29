import {
  Activity,
  ArrowRight,
  Bell,
  ChevronRight,
  Flag,
  Radar,
  Star,
} from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuthenticatedRequest } from '../services/api'
import { useAppWorkspace } from '../services/appWorkspace'
import {
  EMPTY_DASHBOARD_CARDS,
  getMemberRadarMessage,
  isWorkspaceAdmin,
  type DashboardCard,
} from '../services/dashboard'
import {
  isRadarJobActive,
  radarProgressMessage,
  type RadarJob,
} from '../services/radar'

const cardIcons = {
  opportunities: Flag,
  signals: Bell,
  market: Activity,
  watchlist: Star,
} as const

function EmptyDashboardCard({ card }: { card: DashboardCard }) {
  const Icon = cardIcons[card.icon]
  return (
    <article className="workspace-dashboard-card">
      <div className="workspace-dashboard-card-heading">
        <h2>{card.title}</h2>
        <ChevronRight aria-hidden="true" size={18} />
      </div>
      <Icon
        aria-hidden="true"
        className="workspace-dashboard-card-icon"
        strokeWidth={1.25}
      />
      <strong>{card.emptyState}</strong>
      <p>{card.description}</p>
    </article>
  )
}

export function WorkspaceDashboardPage() {
  const { workspaceName, role } = useAppWorkspace()
  const request = useAuthenticatedRequest()
  const admin = isWorkspaceAdmin(role)
  const memberMessage = getMemberRadarMessage(workspaceName)
  const buildRadar = useMutation({
    mutationFn: () =>
      request<RadarJob>('/api/radar/jobs', {
        method: 'POST',
      }),
  })
  const jobId = buildRadar.data?.id
  const radarJob = useQuery({
    queryKey: ['radar-job', jobId],
    queryFn: () => request<RadarJob>(`/api/radar/jobs/${jobId}`),
    enabled: Boolean(jobId),
    initialData: buildRadar.data,
    refetchInterval: (query) =>
      isRadarJobActive(query.state.data) ? 2_000 : false,
  })
  const job = radarJob.data ?? buildRadar.data
  const active = buildRadar.isPending || isRadarJobActive(job)
  const notice = buildRadar.isError
    ? buildRadar.error.message
    : radarJob.isError
      ? radarJob.error.message
      : job
        ? radarProgressMessage(job)
        : ''

  return (
    <section className="workspace-dashboard-shell">
      <div className="workspace-dashboard-hero">
        <div className="workspace-dashboard-radar" aria-hidden="true">
          <span className="radar-ring radar-ring-one" />
          <span className="radar-ring radar-ring-two" />
          <span className="radar-ring radar-ring-three" />
          <span className="radar-cross radar-cross-horizontal" />
          <span className="radar-cross radar-cross-vertical" />
          <span className="radar-sweep" />
          <span className="radar-dot radar-dot-one" />
          <span className="radar-dot radar-dot-two" />
          <span className="radar-dot radar-dot-three" />
        </div>

        <h1>
          Welcome to <span>Radory</span>
        </h1>
        <p className="workspace-dashboard-intro">
          Your brokerage profile is ready. Build your radar to start discovering
          companies that may be approaching commercial property decisions.
        </p>

        {admin ? (
          <button
            className="workspace-dashboard-build"
            type="button"
            disabled={active}
            onClick={() => buildRadar.mutate()}
          >
            <Radar aria-hidden="true" size={22} />
            <span>{active ? 'Building your radar…' : 'Build your radar'}</span>
            <ArrowRight aria-hidden="true" size={20} />
          </button>
        ) : (
          <div className="workspace-dashboard-member-message">
            <strong>{memberMessage.heading}</strong>
            <span>{memberMessage.detail}</span>
          </div>
        )}

        {notice && (
          <div className="workspace-dashboard-notice" role="status">
            <span>{notice}</span>
            {job &&
              (job.pipeline_status === 'completed' ||
                job.pipeline_status === 'partial_failed') && (
                <Link to="/app/opportunities">View opportunities</Link>
              )}
          </div>
        )}
      </div>

      <div className="workspace-dashboard-grid">
        {EMPTY_DASHBOARD_CARDS.map((card) => (
          <EmptyDashboardCard key={card.title} card={card} />
        ))}
      </div>
    </section>
  )
}
