import { config } from "@/lib/config";
import { getToken } from "@/lib/session-storage";

/** Error thrown for any non-2xx response. `detail` comes from the backend's `{ "detail": "..." }` body. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & { body?: unknown };

let onUnauthorized: (() => void) | null = null;

/** Registered by the auth store: any 401 on an authenticated request signs the user out. */
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const token = getToken();
  const isFormData = body instanceof FormData;

  let response: Response;
  try {
    response = await fetch(`${config.apiUrl}/api/v1${path}`, {
      ...rest,
      headers: {
        ...(body !== undefined && !isFormData && { "Content-Type": "application/json" }),
        ...(token && { Authorization: `Bearer ${token}` }),
        ...headers,
      },
      // FormData sets its own multipart Content-Type (with boundary).
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection.");
  }

  if (!response.ok) {
    if (response.status === 401 && token) {
      onUnauthorized?.();
    }
    throw new ApiError(response.status, await readErrorDetail(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data) {
      if (typeof data.detail === "string") return data.detail;
      // FastAPI validation errors: a list of { msg } objects.
      if (Array.isArray(data.detail) && data.detail[0] && typeof data.detail[0].msg === "string") {
        return String(data.detail[0].msg).replace(/^Value error, /, "");
      }
    }
  } catch {
    // Body was not JSON; fall through to the generic message.
  }
  return `Request failed (${response.status})`;
}

/** Absolute URL for backend-served media (`/media/...`). */
export function mediaUrl(path: string | null): string | null {
  return path ? `${config.apiUrl}${path}` : null;
}
