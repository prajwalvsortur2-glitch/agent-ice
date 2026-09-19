import { Badge, type BadgeTone } from "./Badge";
import type { TrustLevel } from "@/lib/constants";

const TONES: Record<TrustLevel, BadgeTone> = {
  TRUSTED: "trusted",
  RESTRICTED: "restricted",
  UNTRUSTED: "untrusted",
};

export function TrustBadge({ level }: { level: TrustLevel }) {
  return <Badge tone={TONES[level]}>{level}</Badge>;
}