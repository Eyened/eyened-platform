import { beforeEach, describe, expect, it, vi } from "vitest";
import { formSchemas } from "$lib/data/stores.svelte";
import { openForm } from "$lib/viewer-window/panelForm/openForm.svelte";
import { openFormInNewWindow } from "$lib/viewer-window/panelForm/openFormInNewWindow";
import type { FormAnnotationGET } from "../../types/openapi_types";
import { FormCreator } from "./formCreator.svelte";

vi.mock("$lib/newWindow", () => ({
    openBlankWindow: vi.fn(),
    mountInWindow: vi.fn(),
}));
vi.mock("$lib/data", async (original) => ({
    ...(await original<typeof import("$lib/data")>()),
    createFormAnnotation: vi.fn(),
}));
const { openBlankWindow, mountInWindow } = await import("$lib/newWindow");
const { createFormAnnotation } = await import("$lib/data");

function fakeWindow() {
    const win = {
        closed: false,
        close: vi.fn(() => {
            win.closed = true;
        }),
        addEventListener: vi.fn(),
    };
    return win;
}

const created = { id: 9200, form_schema_id: 1 } as FormAnnotationGET;
const request = {
    key: "grade:image:img-a",
    schemaName: "Image quality grading",
    message: "Added Image quality grading for OD · OCT · 2024-05-02",
    payload: { form_schema_id: 1, patient_id: 1, form_data: {} },
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
        vi.mocked(openBlankWindow).mockReset();
        vi.mocked(mountInWindow).mockReset();
        vi.mocked(createFormAnnotation).mockReset();
        formSchemas.set(1, { id: 1, name: "Image quality grading" } as never);
        openForm.id = null;
    });

    it("opens the window before the create returns, then fills it and says so", async () => {
        const win = fakeWindow();
        vi.mocked(openBlankWindow).mockReturnValue(win as never);
        const create = deferred<FormAnnotationGET>();
        vi.mocked(createFormAnnotation).mockReturnValue(create.promise);
        const creator = new FormCreator();
        const done = creator.create(request);
        expect(openBlankWindow).toHaveBeenCalledTimes(1);
        expect(mountInWindow).not.toHaveBeenCalled();
        create.resolve(created);
        await done;
        expect(openForm.id).toBe(9200);
        expect(creator.message).toBe(
            "Added Image quality grading for OD · OCT · 2024-05-02, opened in window",
        );
    });

    it("with a form open, Grade clears it while the create runs; a failed create closes the blank window and says what failed", async () => {
        const first = fakeWindow();
        const blank = fakeWindow();
        vi.mocked(openBlankWindow)
            .mockReturnValueOnce(first as never)
            .mockReturnValueOnce(blank as never);
        openFormInNewWindow({ id: 9100, form_schema_id: 1 } as never, true);
        const create = deferred<FormAnnotationGET>();
        vi.mocked(createFormAnnotation).mockReturnValue(create.promise);
        const creator = new FormCreator();
        const done = creator.create(request);
        expect(openForm.id).toBeNull();
        create.reject(new Error("403"));
        await done;
        expect(blank.close).toHaveBeenCalled();
        expect(openForm.id).toBeNull();
        expect(creator.failed).toBe("Image quality grading");
    });

    it("the next create that works clears the failure", async () => {
        vi.mocked(openBlankWindow).mockReturnValue(fakeWindow() as never);
        vi.mocked(createFormAnnotation)
            .mockRejectedValueOnce(new Error("403"))
            .mockResolvedValueOnce(created);
        const creator = new FormCreator();
        await creator.create(request);
        await creator.create(request);
        expect(creator.failed).toBeNull();
    });

    it("a blank window the grader closed gets nothing mounted", async () => {
        const blank = fakeWindow();
        vi.mocked(openBlankWindow).mockReturnValue(blank as never);
        const create = deferred<FormAnnotationGET>();
        vi.mocked(createFormAnnotation).mockReturnValue(create.promise);
        const done = new FormCreator().create(request);
        blank.closed = true;
        create.resolve(created);
        await done;
        expect(mountInWindow).not.toHaveBeenCalled();
        expect(openForm.id).toBeNull();
    });

    it("a second press while the create runs sends nothing", async () => {
        vi.mocked(openBlankWindow).mockReturnValue(fakeWindow() as never);
        const create = deferred<FormAnnotationGET>();
        vi.mocked(createFormAnnotation).mockReturnValue(create.promise);
        const creator = new FormCreator();
        const first = creator.create(request);
        await creator.create(request);
        create.resolve(created);
        await first;
        expect(createFormAnnotation).toHaveBeenCalledTimes(1);
    });
});
