import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { listRuns } from '../api/runs'
import type { RunHistoryRow } from '../types/pipeline'

function scoreClass(score: number | null | undefined): string {
  if (score == null || score === undefined) return 'text-slate-500'
  if (score < 50) return 'text-red-400'
  if (score < 70) return 'text-amber-400'
  return 'text-emerald-400'
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return String(iso)
  return d.toLocaleString()
}

export function HistoryPage() {
  const [rows, setRows] = useState<RunHistoryRow[] | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const data = await listRuns(20)
        if (!cancelled) setRows(data)
      } catch {
        if (!cancelled) setRows([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (rows === null) {
    return (
      <div className="mx-auto max-w-7xl flex-1 px-6 py-6">
        <h1 className="mb-4 text-xl font-semibold text-white">Run history</h1>
        <p className="text-sm text-slate-500">Loading…</p>
      </div>
    )
  }

  if (rows.length === 0) {
    return (
      <div className="mx-auto max-w-7xl flex-1 px-6 py-6">
        <h1 className="mb-4 text-xl font-semibold text-white">Run history</h1>
        <p className="text-slate-400">
          No runs yet. Go to{' '}
          <Link to="/" className="text-violet-400 underline hover:text-violet-300">
            Pipeline
          </Link>{' '}
          to create your first run.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl flex-1 px-6 py-6">
      <h1 className="mb-4 text-xl font-semibold text-white">Run history</h1>
      <div className="overflow-x-auto rounded-lg border border-slate-800">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-slate-800 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2 font-medium">Date</th>
              <th className="px-3 py-2 font-medium">Topic</th>
              <th className="px-3 py-2 font-medium">Platform</th>
              <th className="px-3 py-2 font-medium">Tone</th>
              <th className="px-3 py-2 font-medium">Alignment</th>
              <th className="px-3 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {rows.map((row) => {
              const open = expandedId === row.run_id
              return (
                <RunHistoryTableRow
                  key={row.run_id}
                  row={row}
                  open={open}
                  onToggle={() =>
                    setExpandedId((id) => (id === row.run_id ? null : row.run_id))
                  }
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RunHistoryTableRow({
  row,
  open,
  onToggle,
}: {
  row: RunHistoryRow
  open: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr
        className="cursor-pointer bg-slate-950/40 hover:bg-slate-900/60"
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggle()
          }
        }}
        tabIndex={0}
        role="button"
        aria-expanded={open}
      >
        <td className="px-3 py-2 text-slate-400">{formatDate(row.created_at)}</td>
        <td className="max-w-[200px] truncate px-3 py-2 text-slate-200">
          {row.topic ?? '—'}
        </td>
        <td className="px-3 py-2 text-slate-400">{row.platform ?? '—'}</td>
        <td className="max-w-[140px] truncate px-3 py-2 text-slate-400">
          {row.tone ?? '—'}
        </td>
        <td className={`px-3 py-2 font-medium tabular-nums ${scoreClass(row.alignment_score ?? null)}`}>
          {row.alignment_score ?? '—'}
        </td>
        <td className="px-3 py-2 text-slate-400">{row.status ?? '—'}</td>
      </tr>
      {open ? (
        <tr className="bg-slate-900/40">
          <td colSpan={6} className="px-3 py-3 text-slate-300">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Draft
            </p>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded border border-slate-800 bg-slate-950 p-3 font-sans text-xs leading-relaxed">
              {row.draft?.trim() ? row.draft : '—'}
            </pre>
          </td>
        </tr>
      ) : null}
    </>
  )
}
