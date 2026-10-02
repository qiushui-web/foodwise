type ApiEnvelope<T> = { success: boolean; data: T; message?: string };
type PagePayload<T> = { items: T[]; page: number; size: number; total: number; totalPages: number };
import { useAppStore } from "../stores/app";
import { publicPath } from "./public-base";

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly traceId?: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const app = useAppStore();
  app.clearError();
  try {
    const isForm = options?.body instanceof FormData;
    const response = await fetch(publicPath("api/v1" + path), {
      ...options,
      headers: { ...(!isForm ? { "Content-Type": "application/json" } : {}), ...(options?.headers || {}) },
    });
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json")
      ? await response.json() as ApiEnvelope<T> & { traceId?: string }
      : undefined;
    if (response.status === 401) {
      window.location.assign(publicPath("login"));
    }
    if (!response.ok || payload?.success === false || !payload) {
      const message = payload?.message || (response.status === 401 || response.status === 403
        ? "当前账号没有访问权限"
        : `请求失败（${response.status}）`);
      throw new ApiError(message, response.status, payload?.traceId);
    }
    const data = payload.data as T | PagePayload<T>;
    return (data && typeof data === "object" && "items" in data ? data.items : data) as T;
  } catch (error) {
    const normalized = error instanceof ApiError ? error : new ApiError("网络连接失败，请稍后重试", 0);
    app.reportError(normalized.message);
    throw normalized;
  }
}

export const getApi = <T = any>(path: string) => request<T>(path);
export const postApi = <T = any>(path: string, body: unknown) => request<T>(path, {
  method: "POST",
  headers: { "Idempotency-Key": crypto.randomUUID() },
  body: JSON.stringify(body),
});

export const postFormApi = <T = any>(path: string, body: FormData, idempotent = false) => request<T>(path, {
  method: "POST",
  headers: idempotent ? { "Idempotency-Key": crypto.randomUUID() } : {},
  body,
});
