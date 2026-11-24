import { afterEach, describe, expect, it, vi } from "vitest";
import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import { SaveTracker, type RevealTarget } from "$lib/saving/saveTracker.svelte";
import type { SubTaskState } from "../../types/openapi_types";
import { focusSetControl, SetNavigation } from "./setNavigation.svelte";

function setup(
    send: (value: number) => Promise<void>,
    {
        index = 4,
        count = 10,
        nextOpen = index + 1 < count ? index + 1 : null,
        incomplete,
    }: {
        index?: number;
        count?: number;
        nextOpen?: number | null;
        incomplete?: () => string[];
    } = {},
) {
    const tracker = new SaveTracker();
    const revealed: RevealTarget[] = [];
    tracker.revealer = (target) => revealed.push(target);
    const work = new DebouncedSaver<number>({
        kind: "segmentation",
        group: "grader_segmentation_7",
        target: {
            to: "layers",
            section: "segmentations",
            imageId: "img",
            item: {
                kind: "segmentation",
                segmentation: {
                    id: 7,
                    annotation_type: "grader_segmentation",
                } as never,
            },
        },
        delay: 2000,
        send,
        tracker,
    });
    const statusSend = vi.fn(async (_state: SubTaskState) => {});
    const status = new DebouncedSaver<SubTaskState>({
        kind: "status",
        group: "status",
        target: { to: "focus", focus: () => {} },
        delay: 0,
        send: statusSend,
        tracker,
    });
    const navigate = vi.fn();
    const navigation = new SetNavigation({
        tracker,
        status,
        index,
        count,
        nextOpen: () => nextOpen,
        navigate,
        handoff: () => ({ selected: 0, maximised: null }),
        focus: vi.fn(),
        incomplete,
    });
    return { work, statusSend, navigate, navigation, revealed };
}

const offline = () => Promise.reject(new Error("offline"));
const settle = () => vi.advanceTimersByTimeAsync(0);

afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
});

describe("SetNavigation", () => {
    it("asks before leaving after a failed save, and after a save still running at 5 s", async () => {
        vi.useFakeTimers();
        vi.spyOn(console, "error").mockImplementation(() => {});
        const failing = setup(offline);
        failing.work.edit(1);
        void failing.navigation.move("next", { markReady: false });
        await settle();
        expect(failing.navigation.question).toEqual({ markReady: false });

        const slow = setup(() => new Promise<void>(() => {}));
        slow.work.edit(1);
        void slow.navigation.move("next", { markReady: false });
        await vi.advanceTimersByTimeAsync(4999);
        expect(slow.navigation.question).toBeNull();
        await vi.advanceTimersByTimeAsync(1);
        expect(slow.navigation.question).toEqual({ markReady: false });
    });

    it("Stay goes to what didn't save and doesn't leave", async () => {
        vi.useFakeTimers();
        vi.spyOn(console, "error").mockImplementation(() => {});
        const s = setup(offline);
        s.work.edit(1);
        void s.navigation.move("primary", { markReady: true });
        await settle();
        s.navigation.answerLeave(false);
        await settle();
        expect(s.revealed).toEqual([s.work.target]);
        expect(s.navigate).not.toHaveBeenCalled();
    });

    it("Leave opens the next set without marking this one ready", async () => {
        vi.useFakeTimers();
        vi.spyOn(console, "error").mockImplementation(() => {});
        const s = setup(offline);
        s.work.edit(1);
        void s.navigation.move("primary", { markReady: true });
        await settle();
        s.navigation.answerLeave(true);
        await settle();
        expect(s.navigate).toHaveBeenCalledWith(5);
        expect(s.statusSend).not.toHaveBeenCalled();
    });

    it("Mark ready and next marks ready only after the saves, and stays when that fails", async () => {
        vi.useFakeTimers();
        vi.spyOn(console, "error").mockImplementation(() => {});
        let release!: () => void;
        const s = setup(
            () => new Promise<void>((resolve) => (release = resolve)),
        );
        s.statusSend.mockRejectedValueOnce(new Error("offline"));
        s.work.edit(1);
        void s.navigation.move("primary", { markReady: true });
        await settle();
        expect(s.statusSend).not.toHaveBeenCalled();
        release();
        await settle();
        expect(s.statusSend).toHaveBeenCalledWith("Ready");
        expect(s.navigate).not.toHaveBeenCalled();
        expect(s.navigation.statusFailed).toBe(true);
        // The failed Ready is not queued: the next move goes without sending it again.
        void s.navigation.move("next", { markReady: false });
        await settle();
        expect(s.statusSend).toHaveBeenCalledTimes(1);
        expect(s.navigate).toHaveBeenCalled();
    });

    it("Mark ready on the last set asks nothing and goes to what didn't save", async () => {
        vi.useFakeTimers();
        vi.spyOn(console, "error").mockImplementation(() => {});
        const s = setup(offline, { index: 9, count: 10 });
        s.work.edit(1);
        void s.navigation.move("primary", { markReady: true });
        await settle();
        expect(s.navigation.question).toBeNull();
        expect(s.revealed).toEqual([s.work.target]);
        expect(s.navigate).not.toHaveBeenCalled();
    });

    it("Mark ready and next stays and shows work that became unsaved during the status save", async () => {
        vi.useFakeTimers();
        const s = setup(async () => {});
        let release!: () => void;
        s.statusSend.mockImplementationOnce(
            () => new Promise<void>((resolve) => (release = resolve)),
        );
        void s.navigation.move("primary", { markReady: true });
        await settle();
        expect(s.statusSend).toHaveBeenCalledWith("Ready");
        s.work.edit(1);
        release();
        await settle();
        expect(s.navigate).not.toHaveBeenCalled();
        expect(s.revealed).toEqual([s.work.target]);
    });
});

describe("Mark ready with forms that aren't complete", () => {
    const LINES = [
        "Image quality grading for OD · OCT · 2024-05-02: not graded",
    ];

    it("asks after the saves; Go back saves no status and stays", async () => {
        vi.useFakeTimers();
        const order: string[] = [];
        const { work, statusSend, navigate, navigation } = setup(
            async () => {
                order.push("saved");
            },
            {
                incomplete: () => {
                    order.push("checked");
                    return LINES;
                },
            },
        );
        work.edit(1);
        const move = navigation.move("primary", { markReady: true });
        await settle();
        expect(order).toEqual(["saved", "checked"]);
        expect(navigation.readyQuestion).toEqual(LINES);
        navigation.answerReady(false);
        await move;
        expect(statusSend).not.toHaveBeenCalled();
        expect(navigate).not.toHaveBeenCalled();
        expect(navigation.readyAttempted).toBe(true);
    });

    it("Mark ready and next in the modal saves Ready and moves", async () => {
        vi.useFakeTimers();
        const { statusSend, navigate, navigation } = setup(async () => {}, {
            incomplete: () => LINES,
        });
        const move = navigation.move("primary", { markReady: true });
        await settle();
        navigation.answerReady(true);
        await move;
        expect(statusSend).toHaveBeenCalledWith("Ready");
        expect(navigate).toHaveBeenCalledWith(5);
    });

    it("a complete set and Go to next set ask nothing", async () => {
        vi.useFakeTimers();
        const incomplete = vi.fn(() => [] as string[]);
        const { navigation } = setup(async () => {}, { incomplete });
        await navigation.move("primary", { markReady: true });
        expect(navigation.readyQuestion).toBeNull();
        const other = setup(async () => {}, { incomplete: () => LINES });
        await other.navigation.move("primary", { markReady: false });
        expect(other.navigation.readyQuestion).toBeNull();
        expect(other.navigate).toHaveBeenCalledWith(5);
    });
});

describe("Next open set", () => {
    it("the main move goes to the next open set", async () => {
        const s = setup(async () => {}, { nextOpen: 7 });
        void s.navigation.move("primary", { markReady: true });
        await vi.waitFor(() => expect(s.navigate).toHaveBeenCalledWith(7));
        expect(s.statusSend).toHaveBeenCalledWith("Ready");
    });

    it("▶ still goes to the next set when the next open set is further on", async () => {
        const s = setup(async () => {}, { nextOpen: 7 });
        void s.navigation.move("next", { markReady: false });
        await vi.waitFor(() => expect(s.navigate).toHaveBeenCalledWith(5));
    });

    it("with no open set after this one, Mark ready stays and says so", async () => {
        const s = setup(async () => {}, {
            index: 4,
            count: 10,
            nextOpen: null,
        });
        void s.navigation.move("primary", { markReady: true });
        await vi.waitFor(() => expect(s.navigation.lastReady).toBe(true));
        expect(s.statusSend).toHaveBeenCalledWith("Ready");
        expect(s.navigate).not.toHaveBeenCalled();
        expect(s.navigation.readyNotice).toEqual({
            title: "Set 5 marked ready",
            subtitle: "No open sets after this one.",
        });
    });

    it("on the last set by index the notification says it was the last", async () => {
        const s = setup(async () => {}, { index: 9, count: 10 });
        void s.navigation.move("primary", { markReady: true });
        await vi.waitFor(() => expect(s.navigation.lastReady).toBe(true));
        expect(s.navigation.readyNotice?.subtitle).toBe(
            "This was the last set in this task.",
        );
    });

    it("focus meant for the main button goes to ▶ when there is none", () => {
        document.body.innerHTML = `<button data-set-control="next">Next set</button>`;
        focusSetControl("primary");
        expect(document.activeElement).toBe(
            document.querySelector('[data-set-control="next"]'),
        );
        document.body.innerHTML = "";
    });
});
