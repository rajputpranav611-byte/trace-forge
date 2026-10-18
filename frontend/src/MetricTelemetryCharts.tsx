import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
} from "recharts";

export interface MetricObservation {
  id: string;
  alert_id: string;
  metric_name: string;
  timestamp: string;
  value: number;
  baseline: number;
  deviation_sigma: number;
  unit: string;
}

export interface MetricTelemetryChartsProps {
  metrics: MetricObservation[];
}

export const MetricTelemetryCharts: React.FC<MetricTelemetryChartsProps> = ({ metrics }) => {
  if (!metrics || metrics.length === 0) {
    return (
      <div className="h-40 rounded-md border border-[#232B26] bg-[#111614] flex flex-col items-center justify-center text-[#9AA69C] text-xs font-mono">
        No metric observations correlated with this incident.
      </div>
    );
  }

  // Format data for Recharts without inventing any data
  const chartData = metrics.map((m) => {
    const displayName = m.metric_name
      .replace("service_", "")
      .replace("_p99", " P99")
      .replace("_saturation", " Saturation")
      .replace("_errors", " Errors");

    return {
      name: displayName,
      id: m.id,
      observed: m.value,
      baseline: m.baseline,
      deviation: m.deviation_sigma,
      unit: m.unit,
      rawMetric: m.metric_name,
    };
  });

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* 1. Observed vs Baseline Deviations */}
      <div className="p-4 rounded-md border border-[#232B26] bg-[#111614] space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[#E9EDE5] font-mono">
              Telemetry Deviation: Observed vs Baseline
            </h4>
            <p className="text-[11px] text-[#9AA69C] mt-0.5">
              Direct graph metric anomalies with baseline references
            </p>
          </div>
          <span className="text-[9px] font-mono font-semibold px-2 py-0.5 rounded bg-[#72C6A0]/10 text-[#72C6A0] border border-[#72C6A0]/30">
            OBSERVED FACTS
          </span>
        </div>

        <div className="h-52 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#232B26" vertical={false} />
              <XAxis
                dataKey="name"
                stroke="#647067"
                fontSize={10}
                tickLine={false}
                interval={0}
                angle={-10}
                textAnchor="end"
              />
              <YAxis stroke="#647067" fontSize={10} tickLine={false} />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="p-2.5 rounded bg-[#070908] border border-[#232B26] text-xs font-mono shadow-xl">
                        <div className="font-semibold text-[#E9EDE5] mb-1">{data.rawMetric}</div>
                        <div className="text-[#EF7777]">
                          Observed: {data.observed} {data.unit}
                        </div>
                        <div className="text-[#9AA69C]">
                          Baseline: {data.baseline} {data.unit}
                        </div>
                        <div className="text-[#DDAA60] mt-1 font-semibold">
                          Anomaly: +{data.deviation}σ
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Bar dataKey="observed" fill="#EF7777" radius={[2, 2, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.deviation > 3 ? "#EF7777" : "#DDAA60"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 2. Statistical Sigma Anomaly Deviation */}
      <div className="p-4 rounded-md border border-[#232B26] bg-[#111614] space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[#E9EDE5] font-mono">
              Statistical Significance (+σ Deviation)
            </h4>
            <p className="text-[11px] text-[#9AA69C] mt-0.5">
              Standard deviation delta above normal operating threshold
            </p>
          </div>
          <span className="text-[9px] font-mono font-semibold px-2 py-0.5 rounded bg-[#EF7777]/10 text-[#EF7777] border border-[#EF7777]/30">
            CRITICAL DELTA
          </span>
        </div>

        <div className="h-52 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: -20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#232B26" vertical={false} />
              <XAxis
                dataKey="name"
                stroke="#647067"
                fontSize={10}
                tickLine={false}
                interval={0}
                angle={-10}
                textAnchor="end"
              />
              <YAxis stroke="#647067" fontSize={10} tickLine={false} domain={[0, "auto"]} />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="p-2.5 rounded bg-[#070908] border border-[#232B26] text-xs font-mono shadow-xl">
                        <div className="font-semibold text-[#E9EDE5] mb-1">{data.name}</div>
                        <div className="text-[#C8F169] font-semibold">
                          Deviation: +{data.deviation}σ
                        </div>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Line
                type="monotone"
                dataKey="deviation"
                stroke="#C8F169"
                strokeWidth={1.5}
                dot={{ fill: "#C8F169", r: 3 }}
                activeDot={{ r: 5, fill: "#E9EDE5" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
