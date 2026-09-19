import { request } from "./client";
import type { CreateSessionRequest, Session } from "@/types";

export async function createSession(
  payload: CreateSessionRequest,
): Promise<Session> {
  return request<Session>("/v1/session", { method: "POST", body: payload });
}

export async function listSessions(): Promise<Session[]> {
  return request<Session[]>("/v1/sessions");
}

export async function getSession(sessionId: string): Promise<Session> {
  return request<Session>(`/v1/sessions/${encodeURIComponent(sessionId)}`);
}