import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DECISIONS, type Decision } from "@/lib/constants";

const COLOR: Record<Decision, string> = {
  ALLOW: "#10b981",
  REVIEW: "#f59e0b",
  RESTRICT: "#f97316",
  BLOCK: "#ef4444",
};

export interface DecisionDistributionProps {
  counts: Record<Decision, number>;
  height?: number;
}

export function DecisionDistribution({
  counts,
  height = 220,
}: DecisionDistributionProps) {
  const data = DECISIONS.map((d) => ({ decision: d, count: counts[d] ?? 0 }));
  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid
            stroke="#1f2a44"
            strokeDasharray="3 3"
            vertical={false}
          />
          <XAxis
            dataKey="decision"
            tick={{ fill: "#9aa9c2", fontSize: 11 }}
            axisLine={{ stroke: "#1f2a44" }}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: "#9aa9c2", fontSize: 11 }}
            axisLine={{ stroke: "#1f2a44" }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "#111726",
              border: "1px solid #1f2a44",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#e6ecf5" }}
            cursor={{ fill: "rgba(34,211,238,0.06)" }}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {data.map((d) => (
              <Cell key={d.decision} fill={COLOR[d.decision]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}