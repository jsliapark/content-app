import { useCallback, useEffect, useReducer, useRef } from 'react'

import { createRun, fetchRunSnapshot } from '../api/runs'
import type { GraphNodeId } from '../types/pipeline'
import type { RunInput, RunSnapshot, SSEEvent } from '../types/pipeline'

export type PipelinePhase =
  | 'idle'
  | 'starting'
  | 'running'
  | 'complete'
  | 'failed'

export type PipelineState = {
  phase: PipelinePhase
  runId: string | null
  events: SSEEvent[]
  activeNode: GraphNodeId | null
  completedNodes: GraphNodeId[]
  /** Wall-clock ms when each node started (for elapsed UI). */
  nodeStartTimes: Partial<Record<GraphNodeId, number>>
  /** Final duration in seconds after node_end. */
  nodeDurations: Partial<Record<GraphNodeId, number>>
  /** Latest score from check_alignment node_end (for retry UX). */
  lastCheckAlignmentScore: number | null
  draft: string | null
  alignmentScore: number | null
  alignmentFeedback: string | null
  retryCount: number
  error: string | null
  submitError: string | null
}

type PipelineAction =
  | { type: 'SUBMIT_START' }
  | { type: 'RUN_STARTED'; runId: string }
  | { type: 'SUBMIT_FAILED'; error: string }
  | { type: 'SSE_EVENT'; event: SSEEvent }
  | { type: 'RUN_COMPLETE'; event: SSEEvent; snapshot: RunSnapshot }
  | { type: 'RUN_FAILED'; error: string }
  | { type: 'RESET' }

const initialState: PipelineState = {
  phase: 'idle',
  runId: null,
  events: [],
  activeNode: null,
  completedNodes: [],
  nodeStartTimes: {},
  nodeDurations: {},
  lastCheckAlignmentScore: null,
  draft: null,
  alignmentScore: null,
  alignmentFeedback: null,
  retryCount: 0,
  error: null,
  submitError: null,
}

function isGraphNode(id: string | undefined): id is GraphNodeId {
  return (
    id === 'fetch_voice_context' ||
    id === 'generate_draft' ||
    id === 'check_alignment'
  )
}

function pipelineReducer(
  state: PipelineState,
  action: PipelineAction,
): PipelineState {
  switch (action.type) {
    case 'SUBMIT_START':
      return { ...initialState, phase: 'starting' }
    case 'RUN_STARTED':
      return {
        ...initialState,
        phase: 'running',
        runId: action.runId,
      }
    case 'SUBMIT_FAILED':
      return {
        ...initialState,
        phase: 'idle',
        submitError: action.error,
      }
    case 'SSE_EVENT': {
      const ev = action.event
      const next: PipelineState = {
        ...state,
        events: [...state.events, ev],
      }
      switch (ev.type) {
        case 'run_started':
          return { ...next, phase: 'running' }
        case 'node_start':
          if (isGraphNode(ev.node)) {
            return {
              ...next,
              activeNode: ev.node,
              nodeStartTimes: {
                ...next.nodeStartTimes,
                [ev.node]: Date.now(),
              },
            }
          }
          return next
        case 'node_end': {
          if (!isGraphNode(ev.node)) return next
          const completed = next.completedNodes.includes(ev.node)
            ? next.completedNodes
            : [...next.completedNodes, ev.node]
          const active =
            next.activeNode === ev.node ? null : next.activeNode
          const startAt = next.nodeStartTimes[ev.node]
          const nodeStartTimes = { ...next.nodeStartTimes }
          delete nodeStartTimes[ev.node]
          const nodeDurations = { ...next.nodeDurations }
          if (startAt != null) {
            nodeDurations[ev.node] = Math.max(
              0,
              Math.round((Date.now() - startAt) / 1000),
            )
          }
          let lastCheckAlignmentScore = next.lastCheckAlignmentScore
          let retryCount = next.retryCount
          if (ev.node === 'check_alignment') {
            if (typeof ev.alignment_score === 'number') {
              lastCheckAlignmentScore = ev.alignment_score
            }
            if (typeof ev.retry_count === 'number') {
              retryCount = ev.retry_count
            }
          }
          return {
            ...next,
            completedNodes: completed,
            activeNode: active,
            nodeStartTimes,
            nodeDurations,
            lastCheckAlignmentScore,
            retryCount,
          }
        }
        default:
          return next
      }
    }
    case 'RUN_COMPLETE': {
      const r = action.snapshot.result
      const draft =
        typeof r?.draft === 'string' && r.draft.trim() !== ''
          ? r.draft
          : state.draft
      const graphFailed = r?.status === 'failed'
      const phase: PipelinePhase = graphFailed ? 'failed' : 'complete'

      return {
        ...state,
        phase,
        error: null,
        events: [...state.events, action.event],
        nodeStartTimes: {},
        alignmentScore:
          r?.alignment_score ??
          action.event.alignment_score ??
          state.alignmentScore,
        retryCount:
          r?.retry_count ?? action.event.retry_count ?? state.retryCount,
        draft,
        alignmentFeedback:
          typeof r?.alignment_feedback === 'string'
            ? r.alignment_feedback
            : state.alignmentFeedback,
        activeNode: null,
      }
    }
    case 'RUN_FAILED':
      if (state.phase === 'complete') return state
      return {
        ...state,
        phase: 'failed',
        error: action.error,
        activeNode: null,
      }
    case 'RESET':
      return initialState
    default:
      return state
  }
}

export function useRunPipeline() {
  const [state, dispatch] = useReducer(pipelineReducer, initialState)
  const runIdRef = useRef<string | null>(null)
  runIdRef.current = state.runId

  useEffect(() => {
    if (!state.runId || state.phase !== 'running') return

    const eventSource = new EventSource(
      `/api/runs/${encodeURIComponent(state.runId)}/events`,
    )

    eventSource.onmessage = (event) => {
      let data: SSEEvent
      try {
        data = JSON.parse(event.data) as SSEEvent
      } catch {
        return
      }

      if (data.type === 'run_complete') {
        void (async () => {
          const rid = runIdRef.current
          try {
            if (rid) {
              const snapshot = await fetchRunSnapshot(rid)
              dispatch({ type: 'RUN_COMPLETE', event: data, snapshot })
            }
          } catch {
            dispatch({
              type: 'RUN_COMPLETE',
              event: data,
              snapshot: {
                run_id: rid ?? '',
                phase: 'complete',
                result: null,
                events: [],
              },
            })
          } finally {
            eventSource.close()
          }
        })()
        return
      }

      if (data.type === 'run_failed') {
        dispatch({
          type: 'RUN_FAILED',
          error: data.error ?? 'Run failed',
        })
        eventSource.close()
        return
      }

      dispatch({ type: 'SSE_EVENT', event: data })
    }

    eventSource.onerror = () => {
      eventSource.close()
      dispatch({ type: 'RUN_FAILED', error: 'SSE connection lost' })
    }

    return () => {
      eventSource.close()
    }
  }, [state.runId, state.phase])

  const handleStartRun = useCallback(async (input: RunInput) => {
    dispatch({ type: 'SUBMIT_START' })
    try {
      const { run_id } = await createRun(input)
      dispatch({ type: 'RUN_STARTED', runId: run_id })
    } catch (e) {
      dispatch({
        type: 'SUBMIT_FAILED',
        error: e instanceof Error ? e.message : 'Failed to start run',
      })
    }
  }, [])

  const reset = useCallback(() => {
    dispatch({ type: 'RESET' })
  }, [])

  return { state, handleStartRun, reset }
}
