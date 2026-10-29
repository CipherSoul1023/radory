export type RadarJobStatus =
  'pending' | 'running' | 'completed' | 'partial_failed' | 'failed'

export type RadarJob = {
  id: string
  status: RadarJobStatus
  pipeline_status: RadarJobStatus
  pipeline_error_code: string | null
  pipeline_error_message: string | null
  total_queries: number
  pending_queries: number
  running_queries: number
  succeeded_queries: number
  failed_queries: number
  completed_opportunities: number
  failed_opportunities: number
  created?: boolean
}

export function isRadarJobActive(job: RadarJob | undefined) {
  if (!job) return false
  return (
    job.status === 'pending' ||
    job.status === 'running' ||
    job.pipeline_status === 'pending' ||
    job.pipeline_status === 'running'
  )
}

export function radarProgressMessage(job: RadarJob) {
  if (job.status === 'pending' || job.status === 'running') {
    const finished = job.succeeded_queries + job.failed_queries
    return `Searching for signals… ${finished} of ${job.total_queries} searches complete.`
  }
  if (job.pipeline_status === 'pending') {
    return 'Discovery is complete. Preparing the evidence for interpretation…'
  }
  if (job.pipeline_status === 'running') {
    return 'Interpreting evidence, investigating signals, and building opportunity reports…'
  }
  if (job.pipeline_status === 'completed') {
    return `Your radar is ready with ${job.completed_opportunities} ${job.completed_opportunities === 1 ? 'opportunity' : 'opportunities'}.`
  }
  if (job.pipeline_status === 'partial_failed') {
    return `Your radar produced ${job.completed_opportunities} ${job.completed_opportunities === 1 ? 'opportunity' : 'opportunities'}, but some evidence could not be processed.`
  }
  return (
    job.pipeline_error_message ||
    'The radar could not be completed. Please try again.'
  )
}
