import type { Decision, RiskLevel } from "./constants";

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function decisionTone(
  decision: Decision,
): "allow" | "review" | "restrict" | "block" {
  switch (decision) {
    case "ALLOW":
      return "allow";
    case "REVIEW":
      return "review";
    case "RESTRICT":
      return "restrict";
    case "BLOCK":
      return "block";
  }
}

export function riskTone(
  level: RiskLevel,
): "low" | "medium" | "high" | "critical" {
  switch (level) {
    case "LOW":
      return "low";
    case "MEDIUM":
      return "medium";
    case "HIGH":
      return "high";
    case "CRITICAL":
      return "critical";
  }
}

export function clamp(n: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, n));
}