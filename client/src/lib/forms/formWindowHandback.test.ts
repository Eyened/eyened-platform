import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formWindowHandback } from "./formWindowHandback";

/** The opening page; `document` changes when it loads another page. */
function fakeOpener() {
    const listeners = new Map<string, () => void>();
    return {
        closed: false,
        document: {} as object,
        adoptFormWindow: undefined as ((win: unknown) => void) | undefined,
        addEventListener: (type: string, fn: () => void) =>
            listeners.set(type, fn),
        fire: (type: string) => listeners.get(type)?.(),
    };
}

function fakeWindow(opener: ReturnType<typeof fakeOpener>) {
    const doc = document.implementation.createHTMLDocument("");
    doc.body.textContent = "the form";
    return {
        document: doc,
        opener,
        setInterval: (fn: () => void, ms: number) => setInterval(fn, ms),
        clearInterval: (id: ReturnType<typeof setInterval>) =>
            clearInterval(id),
    };
}

describe("formWindowHandback", () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("shows the loading words when the opener's page goes away, then calls the next page's adoptFormWindow once, never the old page's", () => {
        const opener = fakeOpener();
        const oldAdopt = vi.fn();
        opener.adoptFormWindow = oldAdopt;
        const win = fakeWindow(opener);
        win.document.documentElement.dataset.loading = "Loading set 13…";
        formWindowHandback(win as never);
        opener.fire("pagehide");
        expect(win.document.body.textContent).toBe("Loading set 13…");
        vi.advanceTimersByTime(500);
        expect(oldAdopt).not.toHaveBeenCalled();
        const adopt = vi.fn();
        opener.document = {};
        opener.adoptFormWindow = adopt;
        vi.advanceTimersByTime(1000);
        expect(adopt).toHaveBeenCalledTimes(1);
        expect(adopt).toHaveBeenCalledWith(win);
    });

    it("shows the closed state when the opener closes", () => {
        const opener = fakeOpener();
        const win = fakeWindow(opener);
        formWindowHandback(win as never);
        opener.fire("pagehide");
        expect(win.document.body.textContent).toBe("Loading…");
        opener.closed = true;
        vi.advanceTimersByTime(250);
        expect(win.document.body.textContent).toBe(
            "The viewer closed. Open a form from the viewer to continue.",
        );
    });

    it("shows the closed state after 10 s without a hand-back, in /browse's words when opened there, and lets the next open inject it again", () => {
        const opener = fakeOpener();
        const win = fakeWindow(opener);
        const root = win.document.documentElement;
        root.dataset.from = "browse";
        root.dataset.eyenedForm = "1";
        formWindowHandback(win as never);
        opener.fire("pagehide");
        opener.document = {};
        vi.advanceTimersByTime(9750);
        expect(win.document.body.textContent).toBe("Loading…");
        vi.advanceTimersByTime(250);
        expect(win.document.body.textContent).toBe(
            "The page that opened this form closed. Open the form again to continue.",
        );
        expect(root.dataset.eyenedForm).toBeUndefined();
    });
});
