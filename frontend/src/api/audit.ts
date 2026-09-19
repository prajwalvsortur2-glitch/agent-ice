import { request } from "./client";
import type { AuditEvent, Incident, PoliciesResponse } from "@/types";

export interface AuditQuery {
  session_id?: string;
  decision?: string;
  limit?: number;
  offset?: number;
}

export async function listAuditEvents(
  q: AuditQuery = {},
): Promise<AuditEvent[]> {
  const response = await request<{ events: AuditEvent[] }>("/v1/audit", {
    query: {
      session_id: q.session_id,
      decision: q.decision,
      limit: q.limit,
      offset: q.offset,
    },
  });
  return response.events;
}

export async function listIncidents(
  limit = 100,
  offset = 0,
): Promise<Incident[]> {
  const response = await request<{ incidents: Incident[] }>("/v1/incidents", {
    query: { limit, offset },
  });
  return response.incidents;
}

export async function getPolicies(): Promise<PoliciesResponse> {
  return request<PoliciesResponse>("/v1/policies");
}