/**
 * Thin fetch wrapper for the Agent ICE backend.
 *
 * The frontend NEVER makes authorization decisions. It reads backend
 * decisions and displays them. No secrets are stored here.
 */

import { API_BASE_URL } from "@/lib/constants";
import type { ApiErrorBody } from "@/types";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function parseBody(res: Response): Promise<unknown> {
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }
  try {
    return await res.text();
  } catch {
    return null;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  timeoutMs?: number;
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, query, signal, timeoutMs = 30_000 } = options;

  const url = new URL(path, API_BASE_URL);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const onAbort = () => controller.abort();
  if (signal) signal.addEventListener("abort", onAbort, { once: true });

  let res: Response;
  try {
    res = await fetch(url.toString(), {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeout);
    if (signal) signal.removeEventListener("abort", onAbort);
    if ((err as Error).name === "AbortError") {
      throw new ApiError(0, "Request timed out", null);
    }
    throw new ApiError(0, "Network error — is the backend running?", err);
  }
  clearTimeout(timeout);
  if (signal) signal.removeEventListener("abort", onAbort);

  const parsed = await parseBody(res);

  if (!res.ok) {
    const detail =
      (parsed as ApiErrorBody | null)?.detail ??
      (parsed as ApiErrorBody | null)?.message ??
      `HTTP ${res.status}`;
    throw new ApiError(res.status, detail, parsed);
  }

  return parsed as T;
}