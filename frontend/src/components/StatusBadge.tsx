import type { PipelinePhase } from '../hooks/useRunPipeline'

const LABELS: Record<PipelinePhase, string> = {
  idle: 'Idle',
  starting: 'Starting…',
  running: 'Running',
  complete: 'Complete',
  failed: 'Failed',
}

const STYLES: Record<PipelinePhase, string> = {
  idle: 'bg-slate-700 text-slate-300',
  starting: 'bg-amber-900/60 text-amber-200',
  running: 'bg-blue-900/60 text-blue-200 animate-pulse',
  complete: 'bg-emerald-900/60 text-emerald-200',
  failed: 'bg-red-900/60 text-red-200',
}

export function StatusBadge({
  phase,
  hasDraft,
}: {
  phase: PipelinePhase
  /** When phase is `failed`, a non-empty draft means max-retries / best-effort, not a hard error. */
  hasDraft?: boolean
}) {
  if (phase === 'failed' && hasDraft) {
    return (
      <span className="inline-flex rounded-full bg-amber-900/60 px-3 py-1 text-xs font-medium text-amber-100">
        Exhausted
      </span>
    )
  }

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-xs font-medium ${STYLES[phase]}`}
    >
      {LABELS[phase]}
    </span>
  )
}
