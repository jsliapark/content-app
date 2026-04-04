import {
  Background,
  BackgroundVariant,
  type Edge,
  type Node,
  ReactFlow,
  ReactFlowProvider,
} from '@xyflow/react'

import '@xyflow/react/dist/style.css'

import { PipelineNode, type PipelineNodeData } from './PipelineNode'

const nodeTypes = { pipeline: PipelineNode }

type Props = {
  nodes: Node<PipelineNodeData>[]
  edges: Edge[]
}

function FlowInner({ nodes, edges }: Props) {
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={false}
      zoomOnScroll={false}
      zoomOnPinch={false}
      preventScrolling
      fitView
      fitViewOptions={{ padding: 0.2 }}
      proOptions={{ hideAttribution: true }}
      className="rounded-lg bg-slate-900/50"
    >
      <Background variant={BackgroundVariant.Dots} gap={16} color="#334155" />
    </ReactFlow>
  )
}

export function PipelineVisualizer(props: Props) {
  return (
    <div className="h-[min(420px,45vh)] w-full min-h-[320px]">
      <ReactFlowProvider>
        <FlowInner {...props} />
      </ReactFlowProvider>
    </div>
  )
}
