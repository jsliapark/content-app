import { useMemo } from 'react'

import { ContentPanel } from './components/ContentPanel'
import { PipelineVisualizer } from './components/PipelineVisualizer'
import { RunForm } from './components/RunForm'
import { usePipelineNodes } from './hooks/usePipelineNodes'
import { useRunPipeline } from './hooks/useRunPipeline'

export default function App() {
  const { state, handleStartRun, reset } = useRunPipeline()
  const { nodes, edges } = usePipelineNodes(state)

  const busy = state.phase === 'starting' || state.phase === 'running'

  const recentEvents = useMemo(
    () => state.events.slice(-12).reverse(),
    [state.events],
  )

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-800 px-6 py-4">
        <div className="mx-auto flex max-w-7xl flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight text-white">
            Content pipeline
          </h1>
          <p className="text-sm text-slate-500">
            LangGraph + brandvoice-mcp — live run visualization
          </p>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-4 px-6 py-4">
        <RunForm
          disabled={busy}
          submitError={state.submitError}
          onSubmit={handleStartRun}
        />

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[3fr_2fr]">
          <section className="flex min-h-0 flex-col gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Pipeline
            </h2>
            <PipelineVisualizer nodes={nodes} edges={edges} />
            <div className="flex justify-end">
              <button
                type="button"
                onClick={reset}
                className="text-xs text-slate-500 underline hover:text-slate-300"
              >
                Reset state
              </button>
            </div>
          </section>

          <section className="min-h-0">
            <ContentPanel pipeline={state} />
          </section>
        </div>

        <section className="border-t border-slate-800 pt-3">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">
            Recent events (debug)
          </h3>
          <ul className="max-h-32 space-y-1 overflow-y-auto font-mono text-[10px] text-slate-500">
            {recentEvents.length === 0 ? (
              <li>—</li>
            ) : (
              recentEvents.map((ev, i) => (
                <li key={`${ev.ts ?? i}-${i}`}>
                  {ev.type}
                  {ev.node ? ` · ${ev.node}` : ''}
                </li>
              ))
            )}
          </ul>
        </section>
      </main>
    </div>
  )
}
