import React, { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type Node,
  type Edge,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Server, Database, ShieldAlert, Cpu } from "lucide-react";

export interface TopologyServiceNode {
  id: string;
  name: string;
  tier: number;
  team: string;
  status: string;
}

export interface DependencyEdgeData {
  source: string;
  target: string;
  type: string;
  protocol?: string;
  critical?: boolean;
}

export interface InteractiveGraphProps {
  services: TopologyServiceNode[];
  edges: DependencyEdgeData[];
  selectedServiceId: string | null;
  onSelectService: (serviceId: string | null) => void;
  highlightedPath?: string[];
  severedEdges?: Array<{ source: string; target: string }>;
  isExperiment?: boolean;
  showMiniMap?: boolean;
  tierSpacingX?: number;
  nodeSpacingY?: number;
}

// Custom Service Node Component for Graphite Instrumentation
function CustomServiceNodeComponent({ data }: { data: any }) {
  const isSelected = data.isSelected;
  const isSevered = data.isSevered;
  const isRootCause = data.isRootCause;
  const isDownstream = data.isDownstream;

  const getBorderColor = () => {
    if (isSelected) return "border-[#C8F169] shadow-[0_0_12px_rgba(200,241,105,0.25)] ring-1 ring-[#C8F169]/40";
    if (isRootCause) return "border-[#EF7777] bg-[#EF7777]/10";
    if (isSevered) return "border-dashed border-[#EF7777]/80 opacity-60";
    if (isDownstream) return "border-[#DDAA60] bg-[#DDAA60]/5";
    return "border-[#232B26] hover:border-[#344039]";
  };

  const getNodeIcon = () => {
    const id = data.id.toLowerCase();
    if (id.includes("db") || id.includes("vault") || id.includes("redis") || id.includes("store")) {
      return <Database className="w-3.5 h-3.5 text-[#72C6A0]" />;
    }
    if (id.includes("orchestrator") || id.includes("gateway")) {
      return <Server className="w-3.5 h-3.5 text-[#89B8D9]" />;
    }
    return <Cpu className="w-3.5 h-3.5 text-[#9AA69C]" />;
  };

  return (
    <div
      className={`relative px-3.5 py-2.5 rounded-md bg-[#111614] border ${getBorderColor()} min-w-[175px] max-w-[215px] text-xs transition-colors shadow-md`}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2 !h-2 !bg-[#89B8D9] !border !border-[#070908]"
      />

      <div className="flex items-center justify-between gap-1.5 mb-1">
        <div className="flex items-center gap-1.5 truncate">
          {getNodeIcon()}
          <span className="font-mono font-semibold text-[11px] text-[#E9EDE5] tracking-tight truncate">
            {data.id}
          </span>
        </div>
        <span
          className={`text-[8px] font-mono px-1 py-0.2 rounded font-semibold uppercase ${
            data.status === "degraded" || data.status === "failing"
              ? "bg-[#EF7777]/15 text-[#EF7777] border border-[#EF7777]/30"
              : "bg-[#72C6A0]/15 text-[#72C6A0] border border-[#72C6A0]/30"
          }`}
        >
          T{data.tier}
        </span>
      </div>

      <div className="text-[10px] text-[#9AA69C] truncate font-sans">{data.name}</div>

      <div className="mt-1.5 pt-1.5 border-t border-[#232B26] flex items-center justify-between text-[9px] font-mono text-[#647067]">
        <span className="truncate">{data.team}</span>
        {isRootCause && (
          <span className="text-[#EF7777] font-bold uppercase flex items-center gap-0.5">
            <ShieldAlert className="w-2.5 h-2.5" /> Cause
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!w-2 !h-2 !bg-[#C8F169] !border !border-[#070908]"
      />
    </div>
  );
}

const nodeTypes = {
  serviceNode: CustomServiceNodeComponent,
};

export const InteractiveTopologyGraph: React.FC<InteractiveGraphProps> = ({
  services,
  edges: rawEdges,
  selectedServiceId,
  onSelectService,
  highlightedPath = [],
  severedEdges = [],
  isExperiment = false,
  showMiniMap = true,
  tierSpacingX = 320,
  nodeSpacingY = 115,
}) => {
  // Deterministic 2D layered layout positioning
  const { nodes, edges } = useMemo(() => {
    // 1. Group services by Tier (Tier 1 = Client/Gateway, Tier 2 = Core Logic, Tier 3 = Storage/DB)
    const tiers: Record<number, TopologyServiceNode[]> = { 1: [], 2: [], 3: [], 4: [] };
    services.forEach((s) => {
      const t = s.tier in tiers ? s.tier : 2;
      tiers[t].push(s);
    });

    const calculatedNodes: Node[] = [];

    Object.entries(tiers).forEach(([tierStr, svcs]) => {
      const tierNum = parseInt(tierStr, 10);
      const totalInTier = svcs.length;
      const startY = -((totalInTier - 1) * nodeSpacingY) / 2;

      svcs.forEach((svc, idx) => {
        const isSelected = selectedServiceId === svc.id;
        const isRootCause = svc.id === "payment-core";
        const isDownstream = highlightedPath.includes(svc.id);

        calculatedNodes.push({
          id: svc.id,
          type: "serviceNode",
          position: {
            x: (tierNum - 1) * tierSpacingX + 40,
            y: startY + idx * nodeSpacingY + 140,
          },
          data: {
            ...svc,
            isSelected,
            isRootCause,
            isDownstream,
          },
        });
      });
    });

    // 2. Build directional edges
    const calculatedEdges: Edge[] = rawEdges.map((e, idx) => {
      const isSevered = severedEdges.some(
        (sev) =>
          (sev.source === e.source && sev.target === e.target) ||
          (sev.source === e.target && sev.target === e.source)
      );

      const isPathEdge =
        highlightedPath.includes(e.source) && highlightedPath.includes(e.target);

      let strokeColor = "#344039";
      let strokeWidth = 1.5;

      if (isSevered) {
        strokeColor = "#EF7777";
        strokeWidth = 2;
      } else if (isPathEdge) {
        strokeColor = "#C8F169";
        strokeWidth = 2.5;
      } else if (e.critical) {
        strokeColor = "#72C6A0";
      }

      return {
        id: `edge-${idx}-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        animated: isPathEdge && !isSevered,
        style: {
          stroke: strokeColor,
          strokeWidth,
          strokeDasharray: isSevered ? "4 4" : undefined,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 14,
          height: 14,
        },
      };
    });

    return { nodes: calculatedNodes, edges: calculatedEdges };
  }, [services, rawEdges, selectedServiceId, highlightedPath, severedEdges, tierSpacingX, nodeSpacingY]);

  return (
    <div className="w-full h-full rounded-md border border-[#232B26] overflow-hidden relative bg-[#070908]">
      {isExperiment && (
        <div className="absolute top-3 left-3 z-10 px-2 py-0.5 rounded bg-[#EF7777]/10 border border-[#EF7777]/30 text-[10px] font-mono font-semibold text-[#EF7777] uppercase tracking-wider">
          Isolated FalkorDB Counterfactual Graph State
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onSelectService(node.id)}
        onPaneClick={() => onSelectService(null)}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.3}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#171D19" gap={16} size={1} />
        <Controls showInteractive={false} className="!left-3 !bottom-3" />
        {showMiniMap && (
          <MiniMap
            nodeColor={(node: any) => {
              if (node.data?.isRootCause) return "#EF7777";
              if (node.data?.isSelected) return "#C8F169";
              return "#72C6A0";
            }}
            maskColor="rgba(7, 9, 8, 0.8)"
            className="!right-3 !bottom-3"
          />
        )}
      </ReactFlow>
    </div>
  );
};
