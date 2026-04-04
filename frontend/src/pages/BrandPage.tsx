import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react'

import {
  deleteSamples,
  getBrandOverview,
  ingestSamples,
  setGuidelines,
} from '../api/brand'
import type { BrandProfile } from '../types/brand'

type SampleListRow = {
  id: string
  excerpt: string
}

function asBrandProfile(p: unknown): BrandProfile {
  if (p && typeof p === 'object' && !Array.isArray(p)) {
    return p as BrandProfile
  }
  return {}
}

function guidelinesFromProfile(p: unknown): string {
  if (!p || typeof p !== 'object' || Array.isArray(p)) return ''
  const g = (p as BrandProfile).guidelines
  if (typeof g === 'string') return g
  if (g != null && typeof g === 'object') return JSON.stringify(g, null, 2)
  return ''
}

function excerptOf(item: unknown): string {
  if (typeof item === 'string') {
    return item.length > 100 ? `${item.slice(0, 100)}…` : item
  }
  if (item && typeof item === 'object') {
    const o = item as Record<string, unknown>
    const preview = o.content_preview ?? o.text ?? o.content ?? o.excerpt ?? o.body
    if (typeof preview === 'string') {
      return preview.length > 100 ? `${preview.slice(0, 100)}…` : preview
    }
  }
  const s = JSON.stringify(item)
  return s.length > 100 ? `${s.slice(0, 100)}…` : s
}

function parseSampleRows(data: unknown): SampleListRow[] {
  const raw: unknown[] = Array.isArray(data)
    ? data
    : data &&
        typeof data === 'object' &&
        'samples' in data &&
        Array.isArray((data as { samples: unknown[] }).samples)
      ? (data as { samples: unknown[] }).samples
      : []

  return raw.map((item, i) => {
    if (item && typeof item === 'object' && 'id' in item) {
      const idVal = (item as Record<string, unknown>).id
      const id = typeof idVal === 'string' ? idVal : String(idVal ?? i)
      return { id, excerpt: excerptOf(item) }
    }
    return { id: `row-${i}`, excerpt: excerptOf(item) }
  })
}

function profileSummaryEntries(profile: unknown): [string, unknown][] {
  if (!profile || typeof profile !== 'object' || Array.isArray(profile)) {
    return []
  }
  return Object.entries(profile as BrandProfile).filter(([k]) => k !== 'guidelines')
}

export function BrandPage() {
  const [profile, setProfile] = useState<BrandProfile | null>(null)
  const [samplesData, setSamplesData] = useState<unknown>(null)
  const [overviewLoading, setOverviewLoading] = useState(true)
  const [guidelinesDraft, setGuidelinesDraft] = useState('')
  const [ingestText, setIngestText] = useState('')
  const [ingestBusy, setIngestBusy] = useState(false)
  const [saveBusy, setSaveBusy] = useState(false)
  const [ingestError, setIngestError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)
  const [clearAllBusy, setClearAllBusy] = useState(false)

  const sampleRows = useMemo(() => parseSampleRows(samplesData), [samplesData])

  const applyOverview = useCallback((p: unknown, s: unknown) => {
    const prof = asBrandProfile(p)
    setProfile(prof)
    setSamplesData(s)
    setGuidelinesDraft(guidelinesFromProfile(prof))
  }, [])

  const refreshOverview = useCallback(async () => {
    const { profile: p, samples: s } = await getBrandOverview()
    applyOverview(p, s)
  }, [applyOverview])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const { profile: p, samples: s } = await getBrandOverview()
        if (!cancelled) applyOverview(p, s)
      } catch {
        if (!cancelled) {
          setProfile({})
          setSamplesData(null)
          setGuidelinesDraft('')
        }
      } finally {
        if (!cancelled) setOverviewLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [applyOverview])

  async function handleIngest(e: FormEvent) {
    e.preventDefault()
    setIngestError(null)
    if (!ingestText.trim()) {
      setIngestError('Paste some text to ingest.')
      return
    }
    setIngestBusy(true)
    try {
      await ingestSamples(ingestText)
      setIngestText('')
      await refreshOverview()
    } catch (err) {
      setIngestError(err instanceof Error ? err.message : 'Ingest failed')
    } finally {
      setIngestBusy(false)
    }
  }

  async function handleSaveGuidelines(e: FormEvent) {
    e.preventDefault()
    setSaveError(null)
    setSaveBusy(true)
    try {
      await setGuidelines(guidelinesDraft)
      await refreshOverview()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaveBusy(false)
    }
  }

  async function handleRemoveSample(id: string) {
    setDeleteError(null)
    setRemovingId(id)
    try {
      await deleteSamples({ sample_ids: [id] })
      await refreshOverview()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Remove failed')
    } finally {
      setRemovingId(null)
    }
  }

  async function handleClearAllSamples() {
    if (
      !window.confirm(
        'Remove all ingested samples? The learned profile is reset when none remain.',
      )
    ) {
      return
    }
    setDeleteError(null)
    setClearAllBusy(true)
    try {
      await deleteSamples({ all: true })
      await refreshOverview()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Clear failed')
    } finally {
      setClearAllBusy(false)
    }
  }

  const summaryEntries = profileSummaryEntries(profile)
  const hasVoiceSummary =
    summaryEntries.length > 0 &&
    summaryEntries.some(([, v]) => v != null && v !== '')

  return (
    <div className="mx-auto max-w-3xl flex-1 px-6 py-6">
      <h1 className="mb-6 text-xl font-semibold text-white">Brand dashboard</h1>

      <section className="mb-10">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Voice profile
        </h2>
        {overviewLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : !hasVoiceSummary ? (
          <p className="text-sm text-slate-400">
            No voice profile configured. Ingest writing samples to build your profile.
          </p>
        ) : (
          <dl className="space-y-2 rounded-lg border border-slate-800 bg-slate-900/40 p-4 text-sm">
            {summaryEntries.map(([key, value]) => (
              <div key={key}>
                <dt className="font-medium text-slate-500">{key}</dt>
                <dd className="text-slate-200">
                  {typeof value === 'object' && value !== null
                    ? JSON.stringify(value, null, 2)
                    : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section className="mb-10">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Writing samples
        </h2>
        {overviewLoading ? (
          <p className="mb-4 text-sm text-slate-500">Loading…</p>
        ) : (
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-slate-400">
              {sampleRows.length} sample
              {sampleRows.length === 1 ? '' : 's'} ingested
            </p>
            {sampleRows.length > 0 ? (
              <button
                type="button"
                disabled={clearAllBusy || removingId !== null}
                onClick={() => void handleClearAllSamples()}
                className="text-xs text-red-400 underline hover:text-red-300 disabled:opacity-50"
              >
                {clearAllBusy ? 'Clearing…' : 'Remove all'}
              </button>
            ) : null}
          </div>
        )}
        {deleteError ? (
          <p className="mb-2 text-xs text-red-400">{deleteError}</p>
        ) : null}
        {sampleRows.length > 0 ? (
          <ul className="mb-4 max-h-64 space-y-2 overflow-y-auto rounded border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
            {sampleRows.map((row) => (
              <li
                key={row.id}
                className="flex gap-3 border-b border-slate-800/80 pb-2 last:border-0"
              >
                <span className="min-w-0 flex-1 break-words">{row.excerpt || '—'}</span>
                <button
                  type="button"
                  disabled={removingId === row.id || clearAllBusy}
                  onClick={() => void handleRemoveSample(row.id)}
                  className="shrink-0 text-red-400 hover:text-red-300 disabled:opacity-50"
                >
                  {removingId === row.id ? '…' : 'Remove'}
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <form onSubmit={handleIngest} className="space-y-2">
          <textarea
            value={ingestText}
            onChange={(e) => setIngestText(e.target.value)}
            rows={5}
            placeholder="Paste writing samples…"
            className="w-full resize-y rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-violet-500 focus:outline-none"
          />
          {ingestError ? (
            <p className="text-xs text-red-400">{ingestError}</p>
          ) : null}
          <button
            type="submit"
            disabled={ingestBusy}
            className="rounded bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            {ingestBusy ? 'Ingesting…' : 'Ingest'}
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Brand guidelines
        </h2>
        <form onSubmit={handleSaveGuidelines} className="space-y-2">
          <textarea
            value={guidelinesDraft}
            onChange={(e) => setGuidelinesDraft(e.target.value)}
            rows={6}
            placeholder="Brand voice guidelines…"
            className="w-full resize-y rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-violet-500 focus:outline-none"
          />
          {saveError ? <p className="text-xs text-red-400">{saveError}</p> : null}
          <button
            type="submit"
            disabled={saveBusy}
            className="rounded border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            {saveBusy ? 'Saving…' : 'Save guidelines'}
          </button>
        </form>
      </section>
    </div>
  )
}
