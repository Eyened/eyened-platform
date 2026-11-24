import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { subtasks } from "$lib/data/stores.svelte";
import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import { SaveTracker } from "$lib/saving/saveTracker.svelte";
import type { SubTaskState } from "../../types/openapi_types";
import { SetHolder } from "./holder.svelte";
import { SetNavigation } from "./setNavigation.svelte";
import SetStatusControl from "./SetStatusControl.svelte";
import SetStatusTag from "./SetStatusTag.svelte";

const SUBTASK_ID = 41;

const ME = 7;

function setup(
    send: (state: SubTaskState) => Promise<void> = async () => {},
    {
        showStatus = true,
        set = {},
    }: {
        showStatus?: boolean;
        set?: Record<string, unknown>;
    } = {},
) {
    subtasks.set(SUBTASK_ID, {
        id: SUBTASK_ID,
        task_state: "NotStarted",
        creator_id: null,
        can_edit_status_and_comments: true,
        next_open_index: 5,
        ...set,
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
    const holder = new SetHolder({
        subTaskId: SUBTASK_ID,
        taskId: 3,
        index: 4,
        userId: ME,
        tracker,
        focusAfterRace: vi.fn(),
    });
    render(SetStatusTag, { props: { subTaskId: SUBTASK_ID } });
    render(SetStatusControl, {
        props: {
            subTaskId: SUBTASK_ID,
            index: 4,
            showStatus,
            navigation,
            status,
            holder,
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

    // The label table's cells that today's code gets wrong; the other three already hold.
    it.each([
        [
            "can edit, not Ready, none after",
            true,
            true,
            "NotStarted",
            null,
            "Mark ready",
            true,
        ],
        ["can edit, Ready, none after", true, true, "Ready", null, null, true],
        [
            "can't edit, an open set after",
            true,
            false,
            "NotStarted",
            5,
            "Go to next set",
            false,
        ],
        [
            "can't edit, none after",
            true,
            false,
            "NotStarted",
            null,
            null,
            false,
        ],
        [
            "status off, none after",
            false,
            true,
            "NotStarted",
            null,
            null,
            false,
        ],
    ] as const)(
        "%s",
        (_name, showStatus, canEdit, state, nextOpen, main, menu) => {
            setup(undefined, {
                showStatus,
                set: {
                    task_state: state,
                    can_edit_status_and_comments: canEdit,
                    next_open_index: nextOpen,
                },
            });
            const primary = document.querySelector(
                '[data-set-control="primary"]',
            );
            if (main) expect(primary?.textContent?.trim()).toBe(main);
            else expect(primary).toBeNull();
            expect(
                screen.queryByRole("button", { name: /^Set status/ }) !== null,
            ).toBe(menu);
        },
    );

    it.each([
        [{ creator_id: null }, "Claim set 5"],
        [{ creator_id: ME }, "Give back set 5"],
    ])("below lg, ▾ ends with the holder action: %#", async (set, name) => {
        // Tests run below lg: the test setup's matchMedia answers false.
        setup(undefined, { set });
        await fireEvent.keyDown(trigger(), { key: "Enter" });
        expect(
            await screen.findByRole("menuitem", {
                name: new RegExp(`^${name}`),
            }),
        ).toBeInTheDocument();
    });
});
