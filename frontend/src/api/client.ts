import type {
  AdminConfig, AnalyzeRequest, AnalyzeResponse,
  SendResultsRequest, SendResultsResponse,
} from "../types";

const BASE = "/api";

async function _post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

async function _get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

async function _put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

export const analyzeMission    = (req: AnalyzeRequest)       => _post<AnalyzeResponse>("/analyze", req);
export const checkHealth       = ()                           => _get<{ cvs_loaded: number; model_ready: boolean }>("/health");
export const sendResults       = (req: SendResultsRequest)   => _post<SendResultsResponse>("/send-results", req);
export const getDomains        = ()                           => _get<{ domains: string[] }>("/domains");
export const getAdminConfig    = ()                           => _get<AdminConfig>("/config/admin");
export const updateAdminConfig = (cfg: AdminConfig)          => _put<AdminConfig>("/config/admin", cfg);
