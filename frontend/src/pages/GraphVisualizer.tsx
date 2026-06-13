/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ReactFlow, Controls, Background, useNodesState, useEdgesState, Handle, Position, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useQuery } from '@tanstack/react-query';
import api from '@/lib/api';
import { ErrorState } from '@/components/shared/ErrorState';
import { Skeleton } from '@/components/shared/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { getScopedItem, setScopedItem } from '@/lib/scopedStorage';
import { X, ExternalLink } from 'lucide-react';

const fetchGraphStats = async () => (await api.get('/graph/topology')).data;

const CustomNode = ({ data, type }: any) => {
  const riskOpacity = data.risk_score ? Math.max(0.2, data.risk_score / 100) : 0.5;
  
  let bgClass = '';
  let sizeStyle = { width: 50, height: 50 };
  const label = data.label;

  if (type === 'channel') {
    const size = Math.min(150, 50 + (data.member_count || 0) / 500);
    sizeStyle = { width: size, height: size };
    bgClass = `rgba(59, 130, 246, ${riskOpacity})`;
  } else if (type === 'user') {
    sizeStyle = { width: 60, height: 60 };
    bgClass = `rgba(100, 116, 139, ${riskOpacity})`;
  } else if (type === 'domain') {
    sizeStyle = { width: 80, height: 40 };
    bgClass = `rgba(249, 115, 22, ${riskOpacity})`;
  }

  return (
    <div 
      className="flex items-center justify-center rounded-md border-2 border-border shadow-lg text-xs font-medium text-white text-center break-words p-1 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-surface"
      style={{ ...sizeStyle, backgroundColor: bgClass }}
      role="button"
      tabIndex={0}
      aria-label={`${type} node: ${label}`}
      onClick={() => data.onSelect?.(data)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          data.onSelect?.(data);
        }
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-transparent !border-none" />
      <span className="line-clamp-2">{label}</span>
      <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-none" />
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

export default function GraphVisualizer() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['graphStats'],
    queryFn: fetchGraphStats,
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<any>(null);

  const handleNodeSelect = useCallback((nodeData: any) => {
    setSelectedNode(nodeData);
  }, []);
  
  const onNodeDragStop = useCallback((_: any, node: any) => {
    try {
      const saved = JSON.parse(getScopedItem('graph_positions') || '{}');
      saved[node.id] = node.position;
      setScopedItem('graph_positions', JSON.stringify(saved));
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (data) {
      let savedPositions: Record<string, {x: number, y: number}> = {};
      try {
        savedPositions = JSON.parse(getScopedItem('graph_positions') || '{}');
      } catch {
        // ignore
      }

      const formattedNodes = Array.isArray(data.nodes) ? data.nodes.map((n: any) => ({
        id: n.id,
        type: 'custom',
        position: savedPositions[n.id] || { x: Math.random() * 500, y: Math.random() * 500 },
        data: { ...n.data, type: n.type, onSelect: handleNodeSelect },
      })) : [];

      const formattedEdges = Array.isArray(data.edges) ? data.edges.map((e: any) => {
        let style: { stroke?: string; strokeWidth?: number; strokeDasharray?: string } = {};
        let animated = false;
        
        if (e.type === 'MENTIONED') {
          style = { stroke: 'var(--text-secondary)', strokeWidth: 1 };
        } else if (e.type === 'FORWARDED_FROM') {
          style = { stroke: 'var(--primary)', strokeWidth: 3 };
        } else if (e.type === 'SHARES_DOMAIN') {
          style = { stroke: 'var(--high)', strokeWidth: 2, strokeDasharray: '5 5' };
          animated = true;
        }

        return {
          id: e.id,
          source: e.source,
          target: e.target,
          style,
          animated,
          markerEnd: { type: MarkerType.ArrowClosed, color: style.stroke },
        };
      }) : [];

      setNodes(formattedNodes);
      setEdges(formattedEdges);
    }
  }, [data, setNodes, setEdges, handleNodeSelect]);

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-8rem)] w-full bg-surface border border-border rounded-xl overflow-hidden relative shadow-sm flex items-center justify-center p-6">
        <div className="w-full h-full relative">
          <Skeleton className="absolute top-1/4 left-1/4 h-24 w-24 rounded-full" />
          <Skeleton className="absolute top-1/2 left-1/2 h-16 w-16 rounded-full" />
          <Skeleton className="absolute bottom-1/4 right-1/4 h-32 w-32 rounded-full" />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="h-[calc(100vh-8rem)] w-full flex items-center justify-center">
        <ErrorState title="Failed to load graph" message="An error occurred while fetching graph visualization data." onRetry={refetch} />
      </div>
    );
  }

  if (!data || !Array.isArray(data.nodes) || data.nodes.length === 0) {
    return (
      <div className="h-[calc(100vh-8rem)] w-full flex items-center justify-center">
        <EmptyState title="No Graph Data" message="There are no relationships to visualize." />
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-8rem)] w-full bg-surface border border-border rounded-xl overflow-hidden relative shadow-sm flex">
      <div className="flex-1 relative">
        <div className="absolute top-4 left-4 z-10 bg-background/80 backdrop-blur-sm p-3 rounded-lg border border-border text-xs space-y-2 shadow-md">
          <h3 className="font-semibold text-text-primary">Legend</h3>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-primary rounded-sm"></div> <span className="text-text-secondary">Channel</span></div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-slate-500 rounded-sm"></div> <span className="text-text-secondary">User</span></div>
          <div className="flex items-center gap-2"><div className="w-3 h-3 bg-high rounded-sm"></div> <span className="text-text-secondary">Domain</span></div>
        </div>
        <div aria-label="Graph Visualization canvas" className="h-full w-full">
          <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeDragStop={onNodeDragStop}
          nodeTypes={nodeTypes}
          onPaneClick={() => setSelectedNode(null)}
          fitView
        >
          <Background color="var(--border)" gap={16} />
          <Controls className="bg-surface border-border !fill-text-primary" />
        </ReactFlow>
        </div>
      </div>

      {/* Node Detail Side Panel */}
      <div className={`border-l border-border bg-surface transition-all duration-300 overflow-hidden ${
        selectedNode ? 'w-80' : 'w-0'
      }`}>
        {selectedNode && (
          <div className="w-80 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary truncate mr-2">Node Details</h3>
              <button
                onClick={() => setSelectedNode(null)}
                className="p-1 rounded-md text-text-secondary hover:text-text-primary hover:bg-border transition-colors"
                aria-label="Close panel"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <span className="text-[11px] text-text-secondary uppercase tracking-wider">Label</span>
                <p className="text-sm font-medium text-text-primary mt-0.5 break-words">{selectedNode.label}</p>
              </div>
              <div>
                <span className="text-[11px] text-text-secondary uppercase tracking-wider">Type</span>
                <p className="text-sm text-text-primary mt-0.5 capitalize">{selectedNode.type}</p>
              </div>
              {selectedNode.risk_score !== undefined && (
                <div>
                  <span className="text-[11px] text-text-secondary uppercase tracking-wider">Risk Score</span>
                  <p className="text-sm font-bold text-text-primary mt-0.5">{selectedNode.risk_score}</p>
                </div>
              )}
              {selectedNode.id && (
                <Link
                  to={`/investigation/${selectedNode.id}`}
                  className="flex items-center gap-2 mt-4 px-3 py-2 text-xs font-medium rounded-md bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-colors"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  View Investigation
                </Link>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
