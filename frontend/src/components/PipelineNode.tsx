import { type CSSProperties, useEffect, useState } from 'react'
import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'

import type { NodeVisualStatus } from '../types/pipeline'

export type PipelineNodeData = {
  label: string
  status: NodeVisualStatus
  startedAt?: number | null
  finishedDurationSec?: number | null
  /** When check_alignment is in retrying state, score from last node_end. */
  retryAlignmentScore?: number | null
}

/** L/R handles: vertical center of the node box (same fixed height on all pipeline nodes). */
const HANDLE_LR_STYLE: CSSProperties = {
  top: '50%',
  transform: 'translateY(-50%)',
}

/** Bottom handles: horizontally centered on the node box. */
const HANDLE_BOTTOM_STYLE: CSSProperties = {
  left: '50%',
  bottom: 0,
  transform: 'translate(-50%, 50%)',
}

const RING: Record<NodeVisualStatus, string> = {
  idle: 'border-slate-600 bg-slate-900/80 text-slate-400',
  running:
    'border-blue-500 bg-blue-950/50 text-blue-200 shadow-[0_0_20px_rgba(59,130,246,0.35)]',
  done: 'border-emerald-500 bg-emerald-950/40 text-emerald-100',
  failed: 'border-red-500 bg-red-950/40 text-red-100',
  retrying:
    'border-amber-500 bg-amber-950/40 text-amber-100 animate-pulse',
}

function ElapsedLine({
  status,
  startedAt,
  finishedDurationSec,
}: {
  status: NodeVisualStatus
  startedAt: number | null | undefined
  finishedDurationSec: number | null | undefined
}) {
  const [elapsedSec, setElapsedSec] = useState(0)

  useEffect(() => {
    if (status !== 'running' || startedAt == null) return
    const update = () => {
      setElapsedSec(
        Math.max(0, Math.floor((Date.now() - startedAt) / 1000)),
      )
    }
    update()
    const id = window.setInterval(update, 1000)
    return () => window.clearInterval(id)
  }, [status, startedAt])

  if (status === 'running' && startedAt != null) {
    return (
      <div className="mt-1 font-mono text-xs tabular-nums text-slate-400">
        {elapsedSec}s
      </div>
    )
  }

  if (
    (status === 'done' || status === 'failed' || status === 'retrying') &&
    finishedDurationSec != null &&
    finishedDurationSec >= 0
  ) {
    return (
      <div className="mt-1 font-mono text-xs tabular-nums text-slate-500">
        {finishedDurationSec}s
      </div>
    )
  }

  return null
}

export function PipelineNode({
  id,
  data,
}: NodeProps<Node<PipelineNodeData, 'pipeline'>>) {
  const pulse = data.status === 'running' ? ' animate-pulse' : ''
  const showRetryScore =
    data.status === 'retrying' &&
    data.retryAlignmentScore != null &&
    data.retryAlignmentScore >= 0

  return (
    <div
      className={`relative box-border flex h-[128px] min-w-[152px] flex-col items-center justify-center rounded-xl border-2 px-3 py-2 text-center text-sm font-medium transition-colors duration-300${pulse} ${RING[data.status]}`}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="in-l"
        style={HANDLE_LR_STYLE}
        className="!h-2.5 !w-2.5 !border-slate-500 !bg-slate-700"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="out-r"
        style={HANDLE_LR_STYLE}
        className="!h-2.5 !w-2.5 !border-slate-500 !bg-slate-700"
      />
      {id === 'generate_draft' && (
        <Handle
          type="target"
          position={Position.Bottom}
          id="retry-in"
          style={HANDLE_BOTTOM_STYLE}
          className="!h-2.5 !w-2.5 !border-amber-600 !bg-amber-900"
        />
      )}
      {id === 'check_alignment' && (
        <Handle
          type="source"
          position={Position.Bottom}
          id="retry-out"
          style={HANDLE_BOTTOM_STYLE}
          className="!h-2.5 !w-2.5 !border-amber-600 !bg-amber-900"
        />
      )}
      <div className="flex max-h-full w-full flex-col items-center justify-center gap-0.5 overflow-hidden leading-tight">
        <div className="shrink-0">{data.label}</div>
        {showRetryScore && (
          <div className="shrink-0 text-xs font-normal text-amber-200/90">
            Score: {data.retryAlignmentScore}/100 — retrying
          </div>
        )}
        <ElapsedLine
          key={data.startedAt ?? 'idle'}
          status={data.status}
          startedAt={data.startedAt}
          finishedDurationSec={data.finishedDurationSec}
        />
      </div>
    </div>
  )
}
