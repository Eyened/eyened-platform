import { describe, it, expect, vi, beforeEach } from "vitest";
import { formSchemas } from "$lib/data/stores.svelte";
import { pointArming } from "$lib/forms/pointArming.svelte";
import { openFormInNewWindow } from "./openFormInNewWindow";
import type { FormAnnotationGET } from "../../../types/openapi_types";

const close = vi.fn();
const addEventListener = vi.fn();

vi.mock("$lib/newWindow", () => ({
    openNewWindow: vi.fn(() => ({ close, addEventListener })),
}));

const { openNewWindow } = await import("$lib/newWindow");

const form = {
    id: 3,
    form_schema_id: 10,
    form_data: {},
} as FormAnnotationGET;

describe("openFormInNewWindow", () => {
    beforeEach(() => {
        formSchemas.clear();
        close.mockClear();
        addEventListener.mockClear();
        vi.mocked(openNewWindow).mockClear();
        pointArming.session = null;
    });

    it("opens a titled window and disarms on unload", () => {
        formSchemas.set(10, {
            id: 10,
            name: "Naevi",
        } as never);

        const win = openFormInNewWindow(form, true);
        expect(openNewWindow).toHaveBeenCalledWith(
            expect.anything(),
            { form, canEdit: true, viewerContext: undefined },
            "Naevi 3",
        );
        expect(addEventListener).toHaveBeenCalledWith(
            "beforeunload",
            expect.any(Function),
        );

        const handler = addEventListener.mock.calls[0][1] as () => void;
        handler();
        expect(pointArming.session).toBeNull();
        expect(win).toBeTruthy();
    });

    it("closes a previous window and disarms before opening another", () => {
        const persist = vi.fn();
        pointArming.session = {
            key: "a",
            persist,
        } as never;
        openFormInNewWindow(form, false);
        expect(close).not.toHaveBeenCalled();

        openFormInNewWindow({ ...form, id: 4 } as FormAnnotationGET, false);
        expect(close).toHaveBeenCalled();
        expect(persist).toHaveBeenCalled();
        expect(openNewWindow).toHaveBeenLastCalledWith(
            expect.anything(),
            expect.objectContaining({ canEdit: false }),
            "Form 4",
        );
    });
});
