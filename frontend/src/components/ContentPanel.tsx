import type { PipelineState } from '../hooks/useRunPipeline'

import { StatusBadge } from './StatusBadge'

function scoreColor(score: number): string {
  if (score < 50) return 'bg-red-500'
  if (score < 70) return 'bg-amber-400'
  return 'bg-emerald-500'
}

function hasUsableDraft(pipeline: PipelineState): boolean {
  return Boolean(pipeline.draft?.trim())
}

export function ContentPanel({ pipeline }: { pipeline: PipelineState }) {
  const score = pipeline.alignmentScore
  const pct =
    score == null ? 0 : Math.min(100, Math.max(0, Math.round(score)))

  const draftPresent = hasUsableDraft(pipeline)
  const bestEffortFailure =
    pipeline.phase === 'failed' && draftPresent

  const pipelineRetrying =
    pipeline.phase === 'running' &&
    pipeline.activeNode === 'generate_draft' &&
    pipeline.completedNodes.includes('check_alignment')

  return (
    <div className="flex h-full min-h-[320px] flex-col gap-4 rounded-lg border border-slate-700 bg-slate-900/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Output
        </h2>
        <StatusBadge phase={pipeline.phase} hasDraft={draftPresent} />
      </div>

      {bestEffortFailure && (
        <p className="rounded-md border border-amber-800/50 bg-amber-950/40 px-3 py-2 text-sm text-amber-100">
          Alignment threshold not met after{' '}
          {pipeline.retryCount > 0
            ? `${pipeline.retryCount} attempt${pipeline.retryCount === 1 ? '' : 's'}`
            : 'multiple attempts'}
          . Showing the last draft and score below.
        </p>
      )}

      {pipelineRetrying && pipeline.lastCheckAlignmentScore != null && (
        <p className="rounded-md border border-amber-800/50 bg-amber-950/40 px-3 py-2 text-sm text-amber-100">
          Alignment {pipeline.lastCheckAlignmentScore}/100 below threshold —
          retrying draft
          {pipeline.retryCount > 0
            ? ` (check ${pipeline.retryCount})`
            : ''}
        </p>
      )}

      {pipeline.error && !bestEffortFailure && (
        <p className="rounded-md border border-red-800 bg-red-950/50 p-3 text-sm text-red-200">
          {pipeline.error}
        </p>
      )}

      <div>
        <div className="mb-1 flex justify-between text-xs text-slate-500">
          <span>Alignment score</span>
          {score != null ? <span>{score} / 100</span> : <span>—</span>}
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-800">
          <div
            className={`h-full transition-all duration-500 ${score == null ? 'w-0' : scoreColor(score)}`}
            style={{ width: score == null ? 0 : `${pct}%` }}
          />
        </div>
      </div>

      <div className="text-xs text-slate-500">
        Retries (check cycles):{' '}
        <span className="font-mono text-slate-300">{pipeline.retryCount}</span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <span className="mb-1 text-xs text-slate-500">Draft</span>
        <textarea
          readOnly
          className="min-h-[180px] flex-1 resize-none rounded-md border border-slate-700 bg-slate-950/80 p-3 font-mono text-sm leading-relaxed text-slate-200"
          placeholder={
            pipeline.phase === 'idle'
              ? 'Submit a run to generate content…'
              : pipeline.phase === 'running' || pipeline.phase === 'starting'
                ? 'Waiting for draft…'
                : pipeline.phase === 'failed' && !draftPresent
                  ? 'No draft available.'
                  : ''
          }
          value={pipeline.draft ?? ''}
        />
      </div>

      {pipeline.alignmentFeedback && (
        <div>
          <span className="text-xs text-slate-500">Feedback</span>
          <p className="mt-1 text-sm text-slate-300">
            {pipeline.alignmentFeedback}
          </p>
        </div>
      )}

      {pipeline.phase === 'running' &&
        pipeline.activeNode === 'generate_draft' &&
        pipeline.events.some((e) => e.type === 'agent_tool_call') && (
          <div>
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Agent steps
            </span>
            <ul className="mt-2 max-h-28 space-y-1 overflow-y-auto font-mono text-[11px] text-slate-400">
              {pipeline.events
                .filter((e) => e.type === 'agent_tool_call')
                .slice(-8)
                .map((e, i) => {
                  const label =
                    e.tool === 'web_search'
                      ? '🔍'
                      : e.tool === 'get_writing_examples'
                        ? '📝'
                        : e.tool === 'draft_content'
                          ? '✍️'
                          : '⚙️'
                  const hint =
                    e.tool === 'web_search' &&
                    typeof e.input?.query === 'string'
                      ? e.input.query.slice(0, 80)
                      : e.tool === 'get_writing_examples' &&
                          typeof e.input?.topic === 'string'
                        ? e.input.topic.slice(0, 80)
                        : e.tool ?? 'tool'
                  return (
                    <li key={`${e.ts ?? ''}-${e.iteration ?? i}-${i}`}>
                      {label} {e.tool} {e.iteration != null ? `#${e.iteration} ` : ''}
                      <span className="text-slate-500">— {hint}</span>
                    </li>
                  )
                })}
            </ul>
          </div>
        )}
    </div>
  )
}
