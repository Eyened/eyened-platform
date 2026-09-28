import { vi } from "vitest";

export function json(body: unknown, status = 200): Response {
    return new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}

/** Stub fetch with routes keyed "METHOD /api/path"; each receives the parsed JSON body. */
export function stubFetch(routes: Record<string, (body: unknown) => Response>) {
    const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const request = new Request(input, init);
        const key = `${request.method} ${new URL(request.url).pathname}`;
        const route = routes[key];
        if (!route) throw new Error(`unstubbed request: ${key}`);
        const text = await request.text();
        return route(text ? JSON.parse(text) : undefined);
    });
    vi.stubGlobal("fetch", mock);
    return mock;
}
