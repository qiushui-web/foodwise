type ApiEnvelope<T> = { success: boolean; data: T; message?: string };
export type PagePayload<T> = { items: T[]; page: number; size: number; total: number; totalPages: number };
export type ApiRequestOptions = RequestInit & { timeoutMs?: number };
import { useAppStore } from "../stores/app";
import { publicPath } from "./public-base";

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly traceId?: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  const app = useAppStore();
  app.clearError();
  const controller = new AbortController();
  const onAbort = () => controller.abort(options?.signal?.reason);
  options?.signal?.addEventListener("abort", onAbort, { once: true });
  if (options?.signal?.aborted) onAbort();
  const timer = window.setTimeout(() => controller.abort(), options?.timeoutMs ?? 12000);
  try {
    const isForm = options?.body instanceof FormData;
    const response = await fetch(publicPath("api/v1" + path), {
      ...options,
      signal: controller.signal,
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
    return payload.data;
  } catch (error) {
    const normalized = error instanceof ApiError ? error : new ApiError(error instanceof DOMException && error.name === "AbortError" ? "请求超时，请稍后重试" : "网络连接失败，请稍后重试", 0);
    app.reportError(normalized.message);
    throw normalized;
  } finally {
    window.clearTimeout(timer);
    options?.signal?.removeEventListener("abort", onAbort);
  }
}

export const getApi = <T = unknown>(path: string, options?: ApiRequestOptions) => request<T>(path, options);
export const getPage = <T>(path: string, options?: ApiRequestOptions) => request<PagePayload<T>>(path, options);
export async function getAllPages<T>(path: string): Promise<T[]> {
  const separator = path.includes("?") ? "&" : "?";
  const first = await getPage<T>(`${path}${separator}page=1&size=100`);
  const items = [...first.items];
  for (let page = 2; page <= first.totalPages; page++) {
    items.push(...(await getPage<T>(`${path}${separator}page=${page}&size=100`)).items);
  }
  return items;
}
export const postApi = <T = unknown>(path: string, body: unknown, key: string = crypto.randomUUID()) => request<T>(path, {
  method: "POST",
  headers: { "Idempotency-Key": key },
  body: JSON.stringify(body),
});

export const postFormApi = <T = unknown>(path: string, body: FormData, idempotent: boolean | string = false) => request<T>(path, {
  method: "POST",
  headers: idempotent ? { "Idempotency-Key": typeof idempotent === "string" ? idempotent : crypto.randomUUID() } : {},
  body,
});
