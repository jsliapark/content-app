import { useMemo } from 'react'
import type { Edge, Node } from '@xyflow/react'

import type { PipelineNodeData } from '../components/PipelineNode'
import {
  BASE_PIPELINE_EDGES,
  NODE_LABELS,
  NODE_POSITIONS,
} from '../lib/constants'
import type { GraphNodeId, NodeVisualStatus } from '../types/pipeline'
import type { PipelineState } from './useRunPipeline'

export function usePipelineNodes(pipeline: PipelineState): {
  nodes: Node<PipelineNodeData>[]
  edges: Edge[]
} {
  return useMemo(() => {
    const isRetrying =
      pipeline.phase === 'running' &&
      pipeline.activeNode === 'generate_draft' &&
      pipeline.completedNodes.includes('check_alignment')

    function deriveNodeStatus(id: GraphNodeId): NodeVisualStatus {
      if (pipeline.phase === 'failed') {
        return pipeline.completedNodes.includes(id) ? 'done' : 'idle'
      }
      if (pipeline.phase === 'complete') {
        return 'done'
      }

      const isActive = pipeline.activeNode === id
      const isDone = pipeline.completedNodes.includes(id)

      if (isActive) return 'running'

      if (id === 'check_alignment' && isRetrying) {
        return 'retrying'
      }

      if (isDone) return 'done'
      return 'idle'
    }

    const ids = Object.keys(NODE_POSITIONS) as GraphNodeId[]
    const nodes: Node<PipelineNodeData>[] = ids.map((id) => ({
      id,
      type: 'pipeline',
      position: NODE_POSITIONS[id],
      draggable: false,
      selectable: false,
      data: {
        label: NODE_LABELS[id],
        status: deriveNodeStatus(id),
        startedAt: pipeline.nodeStartTimes[id] ?? null,
        finishedDurationSec: pipeline.nodeDurations[id] ?? null,
        retryAlignmentScore:
          id === 'check_alignment' && isRetrying
            ? pipeline.lastCheckAlignmentScore
            : null,
      },
    }))

    const edges: Edge[] = BASE_PIPELINE_EDGES.map((base) => {
      const isRetryEdge = base.id === 'e-retry'
      if (isRetryEdge && !isRetrying) {
        return {
          ...base,
          hidden: true,
          animated: false,
        }
      }
      if (isRetryEdge && isRetrying) {
        return {
          ...base,
          hidden: false,
          label: 'retry',
          labelStyle: { fill: '#f59e0b', fontSize: 12 },
          pathOptions: { offset: 72, borderRadius: 12 },
          style: {
            stroke: '#f59e0b',
            strokeWidth: 2,
            strokeDasharray: '6 4',
          },
          animated: true,
        }
      }

      const target = base.target as GraphNodeId
      const source = base.source as GraphNodeId
      const targetActive = pipeline.activeNode === target
      const sourceActive = pipeline.activeNode === source
      const animated =
        pipeline.phase === 'running' && (targetActive || sourceActive)

      return {
        ...base,
        hidden: false,
        animated,
      }
    })

    return { nodes, edges }
  }, [pipeline])
}
