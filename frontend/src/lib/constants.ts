import type { Edge } from '@xyflow/react'

import type { GraphNodeId } from '../types/pipeline'

export const NODE_LABELS: Record<GraphNodeId, string> = {
  fetch_voice_context: 'Voice context',
  generate_draft: 'Generate draft',
  check_alignment: 'Check alignment',
}

/** Fixed horizontal layout (React Flow coordinates) */
export const NODE_POSITIONS: Record<GraphNodeId, { x: number; y: number }> = {
  fetch_voice_context: { x: 0, y: 120 },
  generate_draft: { x: 280, y: 120 },
  check_alignment: { x: 560, y: 120 },
}

/** Forward flow uses L/R handles; retry uses bottom handles (see PipelineNode). */
export const BASE_PIPELINE_EDGES: Omit<Edge, 'animated' | 'style' | 'label'>[] =
  [
    {
      id: 'e-fetch-gen',
      source: 'fetch_voice_context',
      target: 'generate_draft',
      type: 'smoothstep',
      sourceHandle: 'out-r',
      targetHandle: 'in-l',
    },
    {
      id: 'e-gen-check',
      source: 'generate_draft',
      target: 'check_alignment',
      type: 'smoothstep',
      sourceHandle: 'out-r',
      targetHandle: 'in-l',
    },
    {
      id: 'e-retry',
      source: 'check_alignment',
      target: 'generate_draft',
      type: 'smoothstep',
      sourceHandle: 'retry-out',
      targetHandle: 'retry-in',
    },
  ]
