import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "$lib/api/client";
import { fetchSubTaskByIndex, updateSubTask } from "$lib/data/api";
import { subtasks } from "$lib/data/stores.svelte";
import { SaveTracker } from "$lib/saving/saveTracker.svelte";
import { mockWidth } from "$lib/workspace/testUtils";
import HolderControl from "./HolderControl.svelte";
import { SetHolder } from "./holder.svelte";

vi.mock("$lib/data/api", () => ({
    updateSubTask: vi.fn(),
    fetchSubTaskByIndex: vi.fn(),
}));

const SUBTASK_ID = 41;
const ME = 7;
const ANNA = { id: 8, name: "Anna de Vries" };

function storeSet(over: Record<string, unknown> = {}) {
    subtasks.set(SUBTASK_ID, {
        id: SUBTASK_ID,
        creator_id: null,
        creator: null,
        can_edit_status_and_comments: true,
        next_open_index: 5,
        ...over,
    } as never);
}

function setup(over: Record<string, unknown> = {}) {
    storeSet(over);
    const focusAfterRace = vi.fn();
    const tracker = new SaveTracker();
    const holder = new SetHolder({
        subTaskId: SUBTASK_ID,
        taskId: 3,
        index: 4,
        userId: ME,
        tracker,
        focusAfterRace,
    });
    // From lg the action is a ghost button beside the tag.
    mockWidth({ md: true, lg: true, xlg: true });
    render(HolderControl, { props: { holder, showStatus: true } });
    return { holder, focusAfterRace, tracker };
}

const tag = () => document.querySelector('[data-slot="tag"]');

afterEach(() => {
    vi.useRealTimers();
    subtasks.clear();
    vi.restoreAllMocks();
    vi.mocked(updateSubTask).mockReset();
    vi.mocked(fetchSubTaskByIndex).mockReset();
});

/** Claim answers 409 and the refetch shows `winner` holding the set. */
function loseClaimTo(winner: { id: number; name: string }) {
    vi.mocked(updateSubTask).mockRejectedValue(
        new ApiError(409, "Conflict", {
            code: "subtask_already_claimed",
            message: "taken",
        }),
    );
    vi.mocked(fetchSubTaskByIndex).mockImplementation(async () => {
        storeSet({
            creator_id: winner.id,
            creator: winner,
            can_edit_status_and_comments: false,
        });
        return {} as never;
    });
}

describe("HolderControl", () => {
    it.each([
        [
            { creator_id: ME, creator: { id: ME, name: "Kim" } },
            "Yours",
            "Give back",
        ],
        [{}, "Unclaimed", "Claim"],
        [{ creator_id: ANNA.id, creator: ANNA }, "Held by Anna de Vries", null],
    ])("names the holder and offers the action: %#", (over, text, action) => {
        setup(over);
        expect(tag()).toHaveTextContent(text);
        if (action)
            expect(screen.getByRole("button")).toHaveTextContent(action);
        else expect(screen.queryByRole("button")).toBeNull();
    });

    it("offers no Claim when I may not change the set", () => {
        setup({ can_edit_status_and_comments: false });
        expect(tag()).toHaveTextContent("Unclaimed");
        expect(screen.queryByRole("button")).toBeNull();
    });

    it("a Claim someone else won shows their name, says so first, and moves focus on", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(updateSubTask).mockRejectedValue(
            new ApiError(409, "Conflict", {
                code: "subtask_already_claimed",
                message: "taken",
            }),
        );
        vi.mocked(fetchSubTaskByIndex).mockImplementation(async () => {
            storeSet({
                creator_id: ANNA.id,
                creator: ANNA,
                can_edit_status_and_comments: false,
            });
            return {} as never;
        });
        const { holder, focusAfterRace } = setup();

        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));

        await waitFor(() => expect(focusAfterRace).toHaveBeenCalled());
        expect(fetchSubTaskByIndex).toHaveBeenCalledWith(3, 4);
        expect(tag()).toHaveTextContent("Held by Anna de Vries");
        expect(screen.queryByRole("button")).toBeNull();
        expect(holder.notice).toEqual({
            title: "Anna de Vries claimed this set first",
            subtitle: "What you save here is saved as yours, inside this set.",
            alert: true,
        });
    });

    it("a lost Claim is announced once: by the notice, not by the tag", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        loseClaimTo(ANNA);
        // The tag's live region as the winner's name lands in it.
        let live: string | null | undefined;
        const refetch = vi.mocked(fetchSubTaskByIndex).getMockImplementation()!;
        vi.mocked(fetchSubTaskByIndex).mockImplementation(async (...args) => {
            const set = await refetch(...args);
            await tick();
            live = tag()!.closest('[role="status"]')?.getAttribute("aria-live");
            return set;
        });
        const { focusAfterRace } = setup();

        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));
        await waitFor(() => expect(focusAfterRace).toHaveBeenCalled());

        expect(live).toBe("off");
    });

    it('drops "claimed this set first" once the holder changes again', async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        loseClaimTo(ANNA);
        const { holder, focusAfterRace } = setup();
        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));
        await waitFor(() => expect(focusAfterRace).toHaveBeenCalled());

        storeSet({
            creator_id: 9,
            creator: { id: 9, name: "Ben Smit" },
            can_edit_status_and_comments: false,
        });

        expect(holder.notice).toEqual({
            title: "Ben Smit holds this set",
            subtitle: "What you save here is saved as yours, inside this set.",
            alert: false,
        });
    });

    it("a Claim that fails otherwise keeps the tag and says to try again", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(updateSubTask).mockRejectedValue(new Error("offline"));
        setup();

        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));

        await waitFor(() =>
            expect(screen.getByRole("alert")).toHaveTextContent(
                "Couldn't claim. Try again.",
            ),
        );
        expect(tag()).toHaveTextContent("Unclaimed");
    });

    it("drops the failed Claim text once the set becomes mine", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        vi.mocked(updateSubTask).mockRejectedValue(new Error("offline"));
        setup();

        await fireEvent.click(screen.getByRole("button", { name: "Claim" }));
        await waitFor(() =>
            expect(screen.getByRole("alert")).toHaveTextContent(
                "Couldn't claim. Try again.",
            ),
        );

        storeSet({ creator_id: ME, creator: { id: ME, name: "Kim" } });

        await waitFor(() => expect(tag()).toHaveTextContent("Yours"));
        expect(screen.queryByText("Couldn't claim. Try again.")).toBeNull();
    });

    it("a Give back whose save is still running at 5 s says it wasn't given back", async () => {
        vi.useFakeTimers();
        const { tracker } = setup({
            creator_id: ME,
            creator: { id: ME, name: "Kim" },
        });
        tracker.join({
            kind: "form",
            group: "form_1",
            target: { to: "focus", focus: () => {} },
            state: "saving",
            flush: () => new Promise<void>(() => {}),
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "Give back" }),
        );
        await vi.advanceTimersByTimeAsync(5000);

        expect(screen.getByRole("alert")).toHaveTextContent(
            "Couldn't give back. Try again.",
        );
    });
});
