import { afterEach, describe, expect, it, vi } from "vitest";

// Each PUT waits until the test resolves it, so saves can finish out of order.
const puts = vi.hoisted(() => [] as ((value: unknown) => void)[]);
vi.mock("$lib/api/client", () => ({
    api: { PUT: vi.fn(() => new Promise((resolve) => puts.push(resolve))) },
    apiErrorFromResponse: vi.fn(),
    fetchApi: vi.fn(),
}));
vi.mock("$lib/data/api", () => ({
    apiInvoke: (call: () => Promise<unknown>) => call(),
    apiInvokeAllowEmpty: (call: () => Promise<unknown>) => call(),
}));

const { setFormAnnotationValue } = await import("./helpers");
const { formAnnotations } = await import("./stores.svelte");

afterEach(() => {
    formAnnotations.clear();
    puts.length = 0;
});

describe("setFormAnnotationValue", () => {
    it("keeps the newer value when an older save resolves last", async () => {
        formAnnotations.set(1, { id: 1, form_data: { v: 0 } } as never);
        const first = setFormAnnotationValue(1, { v: 1 });
        const second = setFormAnnotationValue(1, { v: 2 });
        puts[1]({ data: {} });
        await second;
        puts[0]({ data: {} });
        await first;
        expect(formAnnotations.get(1)?.form_data).toEqual({ v: 2 });
    });
});
