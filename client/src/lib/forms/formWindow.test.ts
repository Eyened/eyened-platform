import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FormAnnotationGET } from "../../types/openapi_types";
import { formWindow } from "./formWindow.svelte";
import { pointArming } from "./pointArming.svelte";

// Each mounted app is its own object, so unmount's argument can be told apart.
let apps = 0;
vi.mock("svelte", async (original) => ({
    ...(await original<typeof import("svelte")>()),
    mount: vi.fn(() => ({ app: ++apps })),
    unmount: vi.fn(),
}));
const { mount, unmount } = await import("svelte");

/** A pop-up with a real document; the test fires its listeners by hand. */
function fakeWindow() {
    const listeners = new Map<string, () => void>();
    const signals = new Map<string, AbortSignal | undefined>();
    const win = {
        closed: false,
        document: document.implementation.createHTMLDocument(""),
        focus: vi.fn(),
        close: vi.fn(() => {
            win.closed = true;
        }),
        addEventListener: (
            type: string,
            fn: () => void,
            options?: { signal?: AbortSignal },
        ) => {
            listeners.set(type, fn);
            signals.set(type, options?.signal);
        },
        // An aborted signal removes the listener, as in a browser.
        fire: (type: string) => {
            if (!signals.get(type)?.aborted) listeners.get(type)?.();
        },
    };
    return win;
}

const form = (id: number) =>
    ({ id, form_schema_id: 10, form_data: {} }) as FormAnnotationGET;
const opts = {
    source: "panel",
    canEdit: true,
    imageIds: ["img-a"],
    from: "viewer" as const,
    contexts: new Map(),
};

describe("formWindow", () => {
    let current: ReturnType<typeof fakeWindow> | null = null;
    beforeEach(() => {
        vi.mocked(mount).mockClear();
        vi.mocked(unmount).mockClear();
        formWindow.blocked = null;
        pointArming.session = null;
    });
    afterEach(() => {
        // The grader closing the window resets the page's window state.
        current?.fire("pagehide");
        current = null;
        vi.restoreAllMocks();
    });

    it("a blocked window marks the place that asked; the next window that opens clears it", () => {
        const open = vi.spyOn(window, "open").mockReturnValueOnce(null);
        formWindow.open(form(3), opts);
        expect(formWindow.blocked).toBe("panel");
        current = fakeWindow();
        open.mockReturnValueOnce(current as never);
        formWindow.open(form(3), { ...opts, source: "study:42:1" });
        expect(formWindow.blocked).toBeNull();
        expect(formWindow.formId).toBe(3);
    });

    it("once this page is gone, the pop-up's closing no longer reaches this page's window state", () => {
        current = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(current as never);
        formWindow.open(form(3), opts);
        window.dispatchEvent(new Event("pagehide"));
        formWindow.formId = 7;
        current.fire("pagehide");
        expect(formWindow.formId).toBe(7);
    });

    it("another form reuses the named pop-up: one window.open per click, the old form unmounted, its point session ended; the same form only comes to the front", () => {
        current = fakeWindow();
        const open = vi.spyOn(window, "open").mockReturnValue(current as never);
        formWindow.open(form(3), opts);
        const first = vi.mocked(mount).mock.results.at(-1)!.value;
        const persist = vi.fn();
        pointArming.session = { key: "a", persist } as never;
        vi.mocked(unmount).mockClear();
        formWindow.open(form(4), opts);
        expect(open).toHaveBeenCalledTimes(2);
        expect(open).toHaveBeenLastCalledWith(
            "",
            "eyened-form",
            expect.stringMatching(/^popup,width=/),
        );
        expect(
            vi.mocked(unmount).mock.calls.some(([app]) => app === first),
        ).toBe(true);
        expect(persist).toHaveBeenCalled();
        expect(current.close).not.toHaveBeenCalled();
        expect(formWindow.formId).toBe(4);
        current.focus.mockClear();
        formWindow.open(form(4), opts);
        expect(open).toHaveBeenCalledTimes(2);
        expect(current.focus).toHaveBeenCalled();
    });

    it("the grader closing the window clears the open form and its viewports", () => {
        current = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(current as never);
        formWindow.open(form(3), opts);
        expect(formWindow.imageIds).toEqual(["img-a"]);
        current.fire("pagehide");
        current = null;
        expect(formWindow.formId).toBeNull();
        expect(formWindow.imageIds).toEqual([]);
    });
});
