import createClient from "openapi-fetch";
import type { paths } from "../../types/openapi";
import { authClient } from "../../auth";
// Token refresh state - prevents multiple simultaneous refresh attempts
let refreshPromise: Promise<void> | null = null;

// Redirect to login when authentication fails permanently
function redirectToLogin() {
    // Only redirect if not already on login page
    if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/users/login")
    ) {
        const currentUrl = encodeURIComponent(window.location.href);
        window.location.href = `/users/login?next=${currentUrl}`;
    }
}

function withCredentials(init?: RequestInit): RequestInit {
    return {
        ...init,
        credentials: "include",
    };
}

async function fetchWithCredentials(
    input: RequestInfo | URL,
    init?: RequestInit,
): Promise<Response> {
    return fetch(input, withCredentials(init));
}

// Handle token refresh with deduplication
async function handleTokenRefresh(): Promise<void> {
    // If already refreshing, wait for the existing promise
    const existingPromise = refreshPromise;
    if (existingPromise) {
        try {
            await existingPromise;
            return;
        } catch {
            // If previous refresh failed, check if we still have the same promise
            // If so, we'll start a new one below; if not, another request already started it
            if (refreshPromise === existingPromise) {
                refreshPromise = null;
            } else if (refreshPromise) {
                // Another request started a new refresh, wait for it
                await refreshPromise;
                return;
            }
        }
    }

    // Start a new refresh - create promise and assign atomically
    const promise = (async () => {
        try {
            await authClient.refresh();
        } catch (error) {
            // If refresh fails, authentication is invalid - redirect to login
            redirectToLogin();
            throw error;
        }
    })();

    // Set the promise atomically - if multiple requests arrive here simultaneously,
    // they'll all use the same promise
    refreshPromise = promise;

    try {
        await promise;
    } finally {
        // Only clear if this is still the current promise (not overwritten by another refresh)
        if (refreshPromise === promise) {
            refreshPromise = null;
        }
    }
}

export class ApiError extends Error {
    readonly status: number;
    readonly detail: unknown;

    constructor(status: number, message: string, detail?: unknown) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.detail = detail ?? message;
    }

    get code(): string | undefined {
        if (
            this.detail &&
            typeof this.detail === "object" &&
            !Array.isArray(this.detail) &&
            "code" in this.detail
        ) {
            const code = (this.detail as { code?: unknown }).code;
            return typeof code === "string" ? code : undefined;
        }
        return undefined;
    }
}

/** Pull a human message and structured detail out of a FastAPI error body. */
export function messageFromApiErrorBody(
    error: unknown,
    fallback: string,
): { message: string; detail: unknown } {
    const detail =
        error &&
        typeof error === "object" &&
        error !== null &&
        "detail" in error
            ? (error as { detail: unknown }).detail
            : error;
    if (typeof detail === "string" && detail.trim()) {
        return { message: detail, detail };
    }
    if (
        detail &&
        typeof detail === "object" &&
        !Array.isArray(detail) &&
        "message" in detail &&
        typeof (detail as { message: unknown }).message === "string"
    ) {
        const message = (detail as { message: string }).message.trim();
        if (message) return { message, detail };
    }
    return { message: fallback, detail };
}

/** Build an ApiError from a FastAPI error response (`detail` may be a string or dict). */
export async function apiErrorFromResponse(
    response: Response,
): Promise<ApiError> {
    let body: unknown;
    try {
        body = await response.json();
    } catch {
        return new ApiError(response.status, response.statusText);
    }
    const { message, detail } = messageFromApiErrorBody(
        body,
        response.statusText || `Request failed: ${response.status}`,
    );
    return new ApiError(response.status, message, detail);
}

export function isUnauthorizedStatus(status: number): boolean {
    return status === 401 || status === 403;
}

/** Retry an API operation once after refreshing tokens (covers edge cases after HTTP-level retry). */
export async function withAuthRetry<T>(
    operation: () => Promise<T>,
): Promise<T> {
    try {
        return await operation();
    } catch (error) {
        if (
            !(error instanceof ApiError) ||
            !isUnauthorizedStatus(error.status)
        ) {
            throw error;
        }
        await handleTokenRefresh();
        return await operation();
    }
}

// Custom fetch wrapper that handles 401/403 responses by refreshing tokens
async function fetchWithAuthRetry(
    input: RequestInfo | URL,
    init?: RequestInit,
): Promise<Response> {
    // Ensure credentials are included
    const requestInit = withCredentials(init);

    // Extract URL for checking
    const url =
        typeof input === "string"
            ? input
            : input instanceof URL
              ? input.href
              : input instanceof Request
                ? input.url
                : String(input);

    // Don't retry refresh endpoint itself (avoid infinite loop)
    const isRefreshEndpoint = url.includes("/auth/refresh");

    // Make the initial request
    let response = await fetch(input, requestInit);

    // If we get a 401/403, try to refresh token and retry once
    if (isUnauthorizedStatus(response.status) && !isRefreshEndpoint) {
        try {
            // Attempt to refresh the token
            await handleTokenRefresh();

            // Retry the original request with the new token (cookies are automatically included)
            response = await fetch(input, requestInit);

            // If retry still returns 401, the refresh didn't help or token is invalid
            // This shouldn't happen if refresh succeeded, but handle it gracefully
            if (isUnauthorizedStatus(response.status)) {
                // Authentication failed even after refresh - redirect to login
                redirectToLogin();
            }
        } catch (_error) {
            // If refresh fails, handleTokenRefresh already redirected to login
            // Return the original 401 response
            return response;
        }
    }

    return response;
}

export const api = createClient<paths>({
    baseUrl: "/api",
    fetch: fetchWithAuthRetry,
});

type QueryRecordValue = string | number | boolean | null | undefined;

type QueryRecord = Record<string, QueryRecordValue | Array<QueryRecordValue>>;

export interface FetchApiOptions extends RequestInit {
    query?: URLSearchParams | QueryRecord;
    skipAuthRetry?: boolean;
}

function buildQueryString(query?: URLSearchParams | QueryRecord): string {
    if (!query) {
        return "";
    }

    const params =
        query instanceof URLSearchParams ? query : new URLSearchParams();

    if (!(query instanceof URLSearchParams)) {
        for (const [key, value] of Object.entries(query)) {
            if (value == null) {
                continue;
            }

            if (Array.isArray(value)) {
                for (const item of value) {
                    if (item == null) continue;
                    params.append(key, String(item));
                }
            } else {
                params.set(key, String(value));
            }
        }
    }

    const qs = params.toString();
    return qs ? `?${qs}` : "";
}

function normalizePath(path: string): string {
    if (/^https?:\/\//i.test(path)) {
        return path;
    }

    if (path.startsWith("/api/")) {
        return path;
    }

    if (path.startsWith("/")) {
        return `/api${path}`;
    }

    return `/api/${path}`;
}

export async function fetchApi(
    path: string,
    options: FetchApiOptions = {},
): Promise<Response> {
    const { query, skipAuthRetry, ...init } = options;
    const basePath = normalizePath(path);
    const queryString = buildQueryString(query);
    const url = `${basePath}${queryString}`;

    if (skipAuthRetry) {
        return fetchWithCredentials(url, init);
    }

    return withAuthRetry(async () => {
        const response = await fetchWithAuthRetry(url, init);
        if (isUnauthorizedStatus(response.status)) {
            throw new ApiError(
                response.status,
                `Request failed: ${response.status}`,
            );
        }
        return response;
    });
}
