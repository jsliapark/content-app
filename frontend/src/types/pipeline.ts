/** LangGraph node ids used in the pipeline visualizer */
export type GraphNodeId =
  | 'fetch_voice_context'
  | 'generate_draft'
  | 'check_alignment'

export type PipelinePhase =
  | 'idle'
  | 'starting'
  | 'running'
  | 'complete'
  | 'failed'

/** Payloads from GET /api/runs/{id}/events (JSON in SSE `data`) */
export type SSEEvent = {
  run_id: string
  ts?: string
  type: string
  node?: string
  status?: string
  alignment_score?: number
  retry_count?: number
  error?: string
}

export type RunInput = {
  topic: string
  platform: 'linkedin' | 'twitter' | 'blog'
  tone: string
}

export type CreateRunResponse = {
  run_id: string
}

/** GET /api/runs/{run_id} */
export type RunSnapshot = {
  run_id: string
  phase: string
  result: RunResult | null
  events: SSEEvent[]
}

export type RunResult = {
  run_id?: string
  topic?: string
  platform?: string
  tone?: string
  draft?: string
  voice_context?: string
  alignment_score?: number | null
  alignment_feedback?: string | null
  retry_count?: number | null
  status?: string
  previous_drafts?: string[]
}

/** Row from GET /api/runs?limit=… (SQLite-backed) */
export type RunHistoryRow = RunResult & {
  run_id: string
  created_at?: string | null
  updated_at?: string | null
}

export type NodeVisualStatus =
  | 'idle'
  | 'running'
  | 'done'
  | 'failed'
  | 'retrying'
