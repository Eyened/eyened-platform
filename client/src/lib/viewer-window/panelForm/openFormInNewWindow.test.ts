import { beforeEach, describe, expect, it, vi } from "vitest";
import { formSchemas } from "$lib/data/stores.svelte";
import { pointArming } from "$lib/forms/pointArming.svelte";
import type { FormAnnotationGET } from "../../../types/openapi_types";
import { openForm } from "./openForm.svelte";
import { openFormInNewWindow } from "./openFormInNewWindow";

vi.mock("$lib/newWindow", () => ({
    openBlankWindow: vi.fn(),
    mountInWindow: vi.fn(),
}));
const { openBlankWindow, mountInWindow } = await import("$lib/newWindow");

/** A window whose listeners the test fires by hand. */
function fakeWindow() {
    const listeners = new Map<string, () => void>();
    const win = {
        closed: false,
        close: vi.fn(() => {
            win.closed = true;
        }),
        addEventListener: (type: string, fn: () => void) =>
            listeners.set(type, fn),
        fire: (type: string) => listeners.get(type)?.(),
    };
    return win;
}

const form = (id: number) =>
    ({ id, form_schema_id: 10, form_data: {} }) as FormAnnotationGET;

describe("openFormInNewWindow", () => {
    beforeEach(() => {
        formSchemas.clear();
        vi.mocked(openBlankWindow).mockReset();
        vi.mocked(mountInWindow).mockReset();
        pointArming.session = null;
        openForm.id = null;
    });

    it("mounts the form under its schema's name and marks it open", () => {
        formSchemas.set(10, { id: 10, name: "Naevi" } as never);
        const win = fakeWindow();
        vi.mocked(openBlankWindow).mockReturnValue(win as never);
        openFormInNewWindow(form(3), true);
        expect(mountInWindow).toHaveBeenCalledWith(
            win,
            expect.anything(),
            { form: form(3), canEdit: true, viewerContext: undefined },
            "Naevi 3",
        );
        expect(openForm.id).toBe(3);
    });

    it("opening another form closes the window and its point session; a late unload leaves the newer form open", () => {
        const a = fakeWindow();
        const b = fakeWindow();
        vi.mocked(openBlankWindow)
            .mockReturnValueOnce(a as never)
            .mockReturnValueOnce(b as never);
        openFormInNewWindow(form(3), true);
        const persist = vi.fn();
        pointArming.session = { key: "a", persist } as never;
        openFormInNewWindow(form(4), true);
        expect(a.close).toHaveBeenCalled();
        expect(persist).toHaveBeenCalled();
        a.fire("beforeunload");
        expect(openForm.id).toBe(4);
        b.fire("beforeunload");
        expect(openForm.id).toBeNull();
    });
});
