import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formSchemas } from "$lib/data/stores.svelte";
import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../types/openapi_types";
import { adoptFormWindow } from "./adoptFormWindow";
import { formWindow, type WindowView } from "./formWindow.svelte";
import { formWindowHandback } from "./formWindowHandback";
import { pointArming } from "./pointArming.svelte";

// Each mounted app is its own object, so unmount's argument can be told apart.
// It renders only a heading naming its view, so focus can be followed.
let apps = 0;
vi.mock("svelte", async (original) => ({
    ...(await original<typeof import("svelte")>()),
    mount: vi.fn(
        (
            _: unknown,
            { target, props }: { target: Element; props: { view: WindowView } },
        ) => {
            const h1 = target.ownerDocument.createElement("h1");
            h1.tabIndex = -1;
            h1.textContent = props.view.kind;
            target.append(h1);
            return { app: ++apps };
        },
    ),
    unmount: vi.fn(),
}));
vi.mock("$lib/data", async (original) => ({
    ...(await original<typeof import("$lib/data")>()),
    createFormAnnotation: vi.fn(),
}));
const { mount, unmount } = await import("svelte");
const { createFormAnnotation } = await import("$lib/data");

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
        vi.useRealTimers();
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

    it("showing a form takes the window's focus unless the caller says it is only following the set", () => {
        current = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(current as never);
        formWindow.open(form(3), opts);
        current.focus.mockClear();
        formWindow.showForm(current as never, form(3), {
            ...opts,
            focus: false,
        });
        expect(current.focus).not.toHaveBeenCalled();
        formWindow.showForm(current as never, form(3), opts);
        expect(current.focus).toHaveBeenCalled();
    });

    it.each([
        ["in a set", 77],
        ["on /view", undefined],
    ])(
        "a fresh window whose row Grade failed stays on the failure when the next page takes it, %s",
        (_, subTaskId) => {
            current = fakeWindow();
            vi.spyOn(window, "open").mockReturnValue(current as never);
            const win = formWindow.begin("panel")!;
            formWindow.showView(win, { kind: "failed" }, new Map());
            adoptFormWindow(win, {
                workspace: {} as never,
                images: [],
                userId: 5,
                subTaskId,
                canEdit: () => true,
                contexts: new Map(),
            });
            const last = vi.mocked(mount).mock.calls.at(-1)![1];
            expect(last.props).toMatchObject({ view: { kind: "failed" } });
        },
    );

    it("a failed Grade does not follow the window to another set", () => {
        const before = window.location.pathname;
        history.replaceState(null, "", "/tasks/1/set/3");
        current = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(current as never);
        const win = formWindow.begin("panel")!;
        formWindow.showView(win, { kind: "failed" }, new Map());
        history.replaceState(null, "", "/tasks/1/set/4");
        adoptFormWindow(win, {
            workspace: {} as never,
            images: [],
            userId: 5,
            subTaskId: 78,
            canEdit: () => true,
            contexts: new Map(),
        });
        history.replaceState(null, "", before);
        const last = vi.mocked(mount).mock.calls.at(-1)![1];
        expect(last.props).toMatchObject({ view: { kind: "closed" } });
    });

    it("Grade, then Try again after it failed, puts focus on the form", async () => {
        formSchemas.set(10, {
            id: 10,
            name: "Image quality grading",
            entity_type: "ImageInstance",
            schema: {},
        } as unknown as FormSchemaGET);
        current = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(current as never);
        const win = formWindow.begin("panel")!;
        // The window last showed a form of this schema, before the page load.
        win.document.documentElement.dataset.schemaId = "10";
        adoptFormWindow(win, {
            workspace: {
                slots: [{ imageId: "img-a" }],
                selected: 0,
                handleAt: () => undefined,
            } as never,
            images: [
                {
                    imageId: "img-a",
                    instance: {
                        id: "img-a",
                        patient: { id: 1, identifier: "P-0001" },
                        study: { id: 10, date: "2024-05-02" },
                        laterality: "R",
                        modality: "OCT",
                        etdrs_field: null,
                        device: {
                            manufacturer: "Heidelberg",
                            model: "Spectralis",
                        },
                    } as never,
                },
            ],
            userId: 5,
            subTaskId: 77,
            canEdit: () => true,
            contexts: new Map(),
        });
        const press = () => {
            const view = vi.mocked(mount).mock.calls.at(-1)![1].props!
                .view as WindowView;
            if (view.kind !== "grade") throw new Error(view.kind);
            view.ongrade();
        };
        vi.mocked(createFormAnnotation)
            .mockRejectedValueOnce(new Error("500"))
            .mockResolvedValueOnce(form(9200));
        press();
        await vi.waitFor(() =>
            expect(win.document.body.textContent).toBe("grade"),
        );
        const focus = vi.spyOn(HTMLElement.prototype, "focus");
        press();
        await vi.waitFor(() =>
            expect(win.document.body.textContent).toBe("form"),
        );
        expect(focus.mock.contexts.at(-1)).toBe(
            win.document.querySelector("h1"),
        );
        formSchemas.delete(10);
    });

    it("a window the viewer let go of through an in-app link isn't taken by a later page load in that tab", () => {
        vi.useFakeTimers();
        current = fakeWindow();
        vi.spyOn(window, "open").mockReturnValue(current as never);
        formWindow.open(form(3), opts);
        // The tab that opened the window; its page loads after the in-app link.
        let leave = () => {};
        const opener = {
            closed: false,
            document: {},
            adoptFormWindow: undefined as unknown,
            addEventListener: (_: string, fn: () => void) => (leave = fn),
        };
        formWindowHandback(
            Object.assign(current, {
                opener,
                setInterval: (fn: () => void, ms: number) =>
                    setInterval(fn, ms),
                clearInterval: (id: ReturnType<typeof setInterval>) =>
                    clearInterval(id),
            }) as never,
        );
        formWindow.release();
        leave();
        const adopt = vi.fn();
        opener.document = {};
        opener.adoptFormWindow = adopt;
        vi.advanceTimersByTime(1000);
        expect(adopt).not.toHaveBeenCalled();
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
