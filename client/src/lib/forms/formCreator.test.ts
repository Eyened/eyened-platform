import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formSchemas } from "$lib/data/stores.svelte";
import type { FormAnnotationGET } from "../../types/openapi_types";
import { FormCreator } from "./formCreator.svelte";
import { formWindow } from "./formWindow.svelte";

vi.mock("svelte", async (original) => ({
    ...(await original<typeof import("svelte")>()),
    mount: vi.fn(() => ({})),
    unmount: vi.fn(),
}));
vi.mock("$lib/data", async (original) => ({
    ...(await original<typeof import("$lib/data")>()),
    createFormAnnotation: vi.fn(),
}));
const { mount } = await import("svelte");
const { createFormAnnotation } = await import("$lib/data");

function fakeWindow() {
    const listeners = new Map<string, () => void>();
    const win = {
        closed: false,
        document: document.implementation.createHTMLDocument(""),
        focus: vi.fn(),
        close: vi.fn(() => {
            win.closed = true;
            listeners.get("pagehide")?.();
        }),
        addEventListener: (type: string, fn: () => void) =>
            listeners.set(type, fn),
    };
    return win;
}

const created = { id: 9200, form_schema_id: 1 } as FormAnnotationGET;
const request = {
    key: "grade:image:img-a",
    schemaName: "Image quality grading",
    message: "Added Image quality grading for OD · OCT · 2024-05-02",
    payload: { form_schema_id: 1, patient_id: 1, form_data: {} },
    imageIds: ["img-a"],
};

function deferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (error: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

describe("FormCreator", () => {
    beforeEach(() => {
        vi.mocked(createFormAnnotation).mockReset();
        formSchemas.set(1, { id: 1, name: "Image quality grading" } as never);
    });
    afterEach(() => {
        formWindow.closeFor(formWindow.formId ?? -1);
        vi.restoreAllMocks();
    });

    it("opens the window before the create returns, then fills it and says so", async () => {
        const win = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(win as never);
        const create = deferred<FormAnnotationGET>();
        vi.mocked(createFormAnnotation).mockReturnValue(create.promise);
        const creator = new FormCreator(new Map());
        const done = creator.create(request);
        expect(window.open).toHaveBeenCalledTimes(1);
        expect(formWindow.formId).toBeNull();
        create.resolve(created);
        await done;
        expect(formWindow.formId).toBe(9200);
        expect(creator.message).toBe(
            "Added Image quality grading for OD · OCT · 2024-05-02, opened in window",
        );
    });

    it("with a form open, Grade clears it while the create runs; a failed create leaves the window open saying so, and says what failed", async () => {
        const win = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(win as never);
        formWindow.open({ id: 9100, form_schema_id: 1 } as never, {
            source: "panel",
            canEdit: true,
            imageIds: [],
            from: "viewer",
            contexts: new Map(),
        });
        const create = deferred<FormAnnotationGET>();
        vi.mocked(createFormAnnotation).mockReturnValue(create.promise);
        const creator = new FormCreator(new Map());
        const done = creator.create(request);
        expect(formWindow.formId).toBeNull();
        create.reject(new Error("403"));
        await done;
        expect(win.close).not.toHaveBeenCalled();
        expect(vi.mocked(mount).mock.lastCall?.[1].props).toMatchObject({
            view: { kind: "failed" },
        });
        expect(formWindow.formId).toBeNull();
        expect(creator.failed).toBe("Image quality grading");
    });

    it("the next create that works clears the failure", async () => {
        vi.spyOn(window, "open").mockReturnValue(fakeWindow() as never);
        vi.mocked(createFormAnnotation)
            .mockRejectedValueOnce(new Error("403"))
            .mockResolvedValueOnce(created);
        const creator = new FormCreator(new Map());
        await creator.create(request);
        await creator.create(request);
        expect(creator.failed).toBeNull();
    });

    it("a window the grader closed while the create ran shows no form", async () => {
        const blank = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(blank as never);
        const create = deferred<FormAnnotationGET>();
        vi.mocked(createFormAnnotation).mockReturnValue(create.promise);
        const done = new FormCreator(new Map()).create(request);
        blank.close();
        create.resolve(created);
        await done;
        expect(formWindow.formId).toBeNull();
    });

    it("a second press while the create runs sends nothing", async () => {
        vi.spyOn(window, "open").mockReturnValue(fakeWindow() as never);
        const create = deferred<FormAnnotationGET>();
        vi.mocked(createFormAnnotation).mockReturnValue(create.promise);
        const creator = new FormCreator(new Map());
        const first = creator.create(request);
        await creator.create(request);
        create.resolve(created);
        await first;
        expect(createFormAnnotation).toHaveBeenCalledTimes(1);
    });
});
