import { type FormEvent, useState } from 'react'

import type { RunInput } from '../types/pipeline'

type Props = {
  disabled: boolean
  submitError: string | null
  onSubmit: (data: RunInput) => void
}

export function RunForm({ disabled, submitError, onSubmit }: Props) {
  const [topic, setTopic] = useState('')
  const [platform, setPlatform] = useState<RunInput['platform']>('linkedin')
  const [tone, setTone] = useState('professional')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!topic.trim() || disabled) return
    onSubmit({ topic: topic.trim(), platform, tone: tone.trim() || 'neutral' })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-4 border-b border-slate-800 pb-4"
    >
      <div className="flex min-w-[200px] flex-1 flex-col gap-1">
        <label htmlFor="topic" className="text-xs font-medium text-slate-400">
          Topic
        </label>
        <input
          id="topic"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={disabled}
          className="rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none disabled:opacity-50"
          placeholder="e.g. AI trends"
        />
      </div>
      <div className="flex w-40 flex-col gap-1">
        <label
          htmlFor="platform"
          className="text-xs font-medium text-slate-400"
        >
          Platform
        </label>
        <select
          id="platform"
          value={platform}
          onChange={(e) =>
            setPlatform(e.target.value as RunInput['platform'])
          }
          disabled={disabled}
          className="rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:border-blue-500 focus:outline-none disabled:opacity-50"
        >
          <option value="linkedin">linkedin</option>
          <option value="twitter">twitter</option>
          <option value="blog">blog</option>
        </select>
      </div>
      <div className="flex min-w-[140px] flex-1 flex-col gap-1">
        <label htmlFor="tone" className="text-xs font-medium text-slate-400">
          Tone
        </label>
        <input
          id="tone"
          value={tone}
          onChange={(e) => setTone(e.target.value)}
          disabled={disabled}
          className="rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none disabled:opacity-50"
          placeholder="e.g. professional"
        />
      </div>
      <button
        type="submit"
        disabled={disabled || !topic.trim()}
        className="rounded-md bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
      >
        Run pipeline
      </button>
      {submitError && (
        <p className="w-full text-sm text-red-400">{submitError}</p>
      )}
    </form>
  )
}
