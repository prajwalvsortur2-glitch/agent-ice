import { request } from "./client";
import type {
  ApproveRequest,
  ApproveResponse,
  ExecuteRequest,
  ExecutionResult,
  InspectRequest,
  InspectionResult,
  RestrictRequest,
  RestrictResponse,
} from "@/types";

export async function inspect(
  payload: InspectRequest,
): Promise<InspectionResult> {
  return request<InspectionResult>("/v1/inspect", {
    method: "POST",
    body: payload,
  });
}

export async function execute(
  payload: ExecuteRequest,
): Promise<ExecutionResult> {
  return request<ExecutionResult>("/v1/execute", {
    method: "POST",
    body: payload,
  });
}

export async function approve(
  payload: ApproveRequest,
): Promise<ApproveResponse> {
  return request<ApproveResponse>("/v1/approve", {
    method: "POST",
    body: payload,
  });
}

export async function restrict(
  payload: RestrictRequest,
): Promise<RestrictResponse> {
  return request<RestrictResponse>("/v1/restrict", {
    method: "POST",
    body: payload,
  });
}