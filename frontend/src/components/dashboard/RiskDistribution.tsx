import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { RISK_LEVELS, type RiskLevel } from "@/lib/constants";

const COLOR: Record<RiskLevel, string> = {
  LOW: "#10b981",
  MEDIUM: "#eab308",
  HIGH: "#f97316",
  CRITICAL: "#ef4444",
};

export interface RiskDistributionProps {
  counts: Record<RiskLevel, number>;
  height?: number;
}

export function RiskDistribution({
  counts,
  height = 220,
}: RiskDistributionProps) {
  const data = RISK_LEVELS.map((level) => ({
    name: level,
    value: counts[level] ?? 0,
  })).filter((d) => d.value > 0);

  if (data.length === 0) {
    return (
      <div
        className="grid place-items-center text-xs text-ink-muted"
        style={{ height }}
      >
        No events yet
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <PieChart>
          <Tooltip
            contentStyle={{
              background: "#111726",
              border: "1px solid #1f2a44",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#e6ecf5" }}
          />
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="55%"
            outerRadius="85%"
            stroke="#0a0e1a"
            strokeWidth={2}
          >
            {data.map((d) => (
              <Cell key={d.name} fill={COLOR[d.name as RiskLevel]} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}