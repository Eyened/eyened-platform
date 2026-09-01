import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import { ApiError } from "$lib/api/client";
import { addSubTaskImage } from "$lib/data/helpers";
import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
import { toast } from "svelte-sonner";
import BrowserOverlay from "./BrowserOverlay.svelte";
import type { ViewerWindowContext } from "./viewerWindowContext.svelte";

// The overlay constructs its own BrowserContext and reads the selection back
// out of it on teardown, so the test needs a handle on that instance to stand
// in for the user picking an image in the browser.
const { browserContexts } = vi.hoisted(() => ({
    browserContexts: [] as { selectedIds: string[] }[],
}));

vi.mock("$lib/browser/browserContext.svelte", () => ({
    BrowserContext: class {
        selectedIds: string[] = [];
        urlSync = true;
        limit = 10;
        constructor() {
            browserContexts.push(this);
        }
    },
}));

// The real Browser pulls in the whole search UI; none of it is under test here.
vi.mock("$lib/browser/Browser.svelte", () => ({ default: () => {} }));

// viewerWindowContext reaches cornerstone's WADO loader, which throws on import
// under jsdom. The test supplies a spy for this prop, so the real class is dead
// weight either way.
vi.mock("./viewerWindowContext.svelte", () => ({
    ViewerWindowContext: class {},
}));

vi.mock("$lib/data/helpers", () => ({
    addSubTaskImage: vi.fn(),
    removeSubTaskImage: vi.fn(),
}));

vi.mock("svelte-sonner", () => ({ toast: { error: vi.fn() } }));

const REFUSED_ID = "88213";

const refusal = new ApiError(409, "conflict", {
    code: "image_outside_task_declaration",
    message: "Image 88213 is in a project this task does not declare.",
    image_projects: [17],
    declared_projects: [4, 9],
});

async function renderOverlay() {
    const setInstanceIDs = vi.fn();
    const viewerWindowContext = {
        instanceIds: [],
        setInstanceIDs,
    } as unknown as ViewerWindowContext;

    // The overlay reads its client config off the task definition; an empty
    // one leaves CLIENT_DEFAULTS in place.
    const taskContext = {
        subTask: { id: 31 },
        task: { task_definition: {} },
    } as unknown as TaskContext;

    const { unmount } = render(BrowserOverlay, {
        props: { viewerWindowContext },
        context: new Map<string, unknown>([["taskContext", taskContext]]),
    });

    // "Update task image links" is off by default; the write only happens
    // when the grader has ticked it.
    await fireEvent.click(screen.getByLabelText(/Update task image links/i));

    const browserContext = browserContexts[browserContexts.length - 1];
    browserContext.selectedIds = [REFUSED_ID];

    return { setInstanceIDs, unmount };
}

describe("BrowserOverlay teardown", () => {
    beforeEach(() => {
        browserContexts.length = 0;
        // toast.error is a module-level spy shared by every test in the file,
        // and the negative test waits on it. A call left over from a
        // neighbouring test would satisfy that wait immediately and put the
        // timing hole below straight back.
        vi.clearAllMocks();
    });

    it("does not persist an image link the server refused", async () => {
        vi.mocked(addSubTaskImage).mockRejectedValue(refusal);

        const { setInstanceIDs, unmount } = await renderOverlay();

        // close() is registered only as onDestroy(close), so unmounting is the
        // one way the app ever reaches it.
        unmount();

        // onDestroy does not await, so flush microtasks before reading the
        // spies. Wait on the toast, not on addSubTaskImage: the request goes
        // out on close()'s first tick, so waiting on it returns before the
        // rejection has even propagated back and the assertion below would
        // read a spy that has not yet had its chance to fire -- which lets a
        // component that toasts and then persists anyway pass. toast.error and
        // setInstanceIDs sit in the same synchronous continuation, so once the
        // toast is observable the write either happened or never will.
        await vi.waitFor(() => expect(toast.error).toHaveBeenCalled());

        expect(addSubTaskImage).toHaveBeenCalledWith(31, REFUSED_ID);

        // The defect this test exists for: the overlay used to write the
        // refused id into the view state regardless, so the UI showed an image
        // the database does not have.
        expect(setInstanceIDs).not.toHaveBeenCalled();
    });

    it("reports a failure that is not the declaration refusal", async () => {
        vi.mocked(addSubTaskImage).mockRejectedValue(new Error("Network down"));

        const { setInstanceIDs, unmount } = await renderOverlay();

        unmount();

        // One argument, not two: the refusal's description names projects the
        // server never sent for this error.
        await vi.waitFor(() =>
            expect(toast.error).toHaveBeenCalledWith("Error: Network down"),
        );

        expect(setInstanceIDs).not.toHaveBeenCalled();
    });

    it("persists the selection when the server accepts the link", async () => {
        vi.mocked(addSubTaskImage).mockResolvedValue(undefined);

        const { setInstanceIDs, unmount } = await renderOverlay();

        unmount();

        await vi.waitFor(() =>
            expect(setInstanceIDs).toHaveBeenCalledWith([REFUSED_ID]),
        );
    });
});
