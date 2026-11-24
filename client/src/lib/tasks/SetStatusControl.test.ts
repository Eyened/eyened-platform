import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { subtasks } from "$lib/data/stores.svelte";
import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import { SaveTracker } from "$lib/saving/saveTracker.svelte";
import type { SubTaskState } from "../../types/openapi_types";
import { SetNavigation } from "./setNavigation.svelte";
import SetStatusControl from "./SetStatusControl.svelte";
import SetStatusTag from "./SetStatusTag.svelte";

const SUBTASK_ID = 41;

function setup(send: (state: SubTaskState) => Promise<void>) {
    subtasks.set(SUBTASK_ID, {
        id: SUBTASK_ID,
        task_state: "NotStarted",
    } as never);
    const tracker = new SaveTracker();
    const statusSend = vi.fn(send);
    const status = new DebouncedSaver<SubTaskState>({
        kind: "status",
        group: "status",
        target: { to: "focus", focus: () => {} },
        delay: 0,
        send: statusSend,
        tracker,
    });
    const navigation = new SetNavigation({
        tracker,
        status,
        index: 4,
        count: 10,
        nextOpen: () => 5,
        navigate: vi.fn(),
        handoff: () => ({ selected: 0, maximised: null }),
        focus: vi.fn(),
    });
    render(SetStatusTag, { props: { subTaskId: SUBTASK_ID } });
    render(SetStatusControl, {
        props: {
            subTaskId: SUBTASK_ID,
            index: 4,
            count: 10,
            showStatus: true,
            navigation,
            status,
        },
    });
    return { statusSend, navigation };
}

const trigger = () => screen.getByRole("button", { name: /^Set status/ });

async function pickStatus(name: RegExp) {
    await fireEvent.keyDown(trigger(), { key: "Enter" });
    await fireEvent.click(await screen.findByRole("menuitemradio", { name }));
}

afterEach(() => {
    subtasks.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
});

describe("SetStatusControl", () => {
    it("picking a status in the menu saves that status", async () => {
        const { statusSend } = setup(async () => {});
        await pickStatus(/^In progress/);
        await waitFor(() => expect(statusSend).toHaveBeenCalledWith("Busy"));
    });

    it("a failed status save keeps the tag on the saved status and says to pick again", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        setup(() => Promise.reject(new Error("offline")));
        await pickStatus(/^In progress/);
        await waitFor(() =>
            expect(screen.getByRole("alert")).toHaveTextContent(
                "Status couldn't save. Pick it again.",
            ),
        );
        expect(document.querySelector('[data-slot="tag"]')).toHaveTextContent(
            "Not started",
        );
        expect(trigger()).toHaveAccessibleName("Set status: Not started");
    });

    it("once a move has started, ▾ is unavailable and a pick saves nothing", async () => {
        const { statusSend, navigation } = setup(async () => {});
        await navigation.move("next", { markReady: false });
        await waitFor(() =>
            expect(trigger()).toHaveAttribute("aria-disabled", "true"),
        );
        await fireEvent.keyDown(trigger(), { key: "Enter" });
        expect(screen.queryByRole("menu")).toBeNull();
        expect(statusSend).not.toHaveBeenCalled();
    });
});
