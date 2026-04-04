import type {
  CreateRunResponse,
  RunHistoryRow,
  RunInput,
  RunSnapshot,
} from '../types/pipeline'

export async function createRun(input: RunInput): Promise<CreateRunResponse> {
  const res = await fetch('/api/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Failed to create run: ${res.status} ${text}`)
  }
  return res.json() as Promise<CreateRunResponse>
}

export async function fetchRunSnapshot(runId: string): Promise<RunSnapshot> {
  const res = await fetch(`/api/runs/${runId}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch run: ${res.status}`)
  }
  return res.json() as Promise<RunSnapshot>
}

export async function listRuns(limit = 20): Promise<RunHistoryRow[]> {
  const res = await fetch(`/api/runs?limit=${limit}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch runs: ${res.status}`)
  }
  return res.json() as Promise<RunHistoryRow[]>
}
