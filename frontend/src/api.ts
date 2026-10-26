export type Project = { id: string; name: string; builtin: boolean };
export type Job = {
  id: string;
  project_id: string;
  kind: string;
  status: string;
  stage: string;
  error?: string;
  created: number;
  options: { smart: boolean; repair: boolean };
};
export type Capabilities = {
  version: string;
  verify_enabled: boolean;
  smart_configured: boolean;
  smart_enabled: boolean;
  model: string;
  upload_limit_mb: number;
  tools: string[];
};
// The analysis document is the versioned engine JSON; keep extension fields intact.
export type Analysis = {
  assessment?: {
    status: string;
    message: string;
    entries_with_operation_result: number;
    entries_with_gaps: number;
  };
  summary: Record<string, number>;
  results: any[];
  coverage_gaps: any[];
  service_edges: any[];
};
export type Result = {
  before: Analysis;
  after: Analysis | null;
  contexts: any[];
  repair: any;
  smart: any;
  verification: any;
  sample_type: string;
  skill_events?: any[];
};
export function token() {
  return sessionStorage.getItem("microbind-token") || "";
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch("/api" + path, {
    ...init,
    headers: {
      Authorization: "Bearer " + token(),
      ...(init.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  }
  return response.json();
}
export async function download(id: string) {
  const r = await fetch("/api/jobs/" + id + "/download", {
    headers: { Authorization: "Bearer " + token() },
  });
  if (!r.ok) throw new Error("下载失败，请确认任务已经完成");
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "microbind-" + id.slice(0, 8) + ".zip";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
