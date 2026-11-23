import { afterEach, describe, expect, it, vi } from "vitest";
import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import { SaveTracker, type RevealTarget } from "$lib/saving/saveTracker.svelte";
import type { SubTaskState } from "../../types/openapi_types";
import { SetNavigation } from "./setNavigation.svelte";

function setup(
    send: (value: number) => Promise<void>,
    { index = 4, count = 10 } = {},
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
        navigate,
        handoff: () => ({ selected: 0, maximised: null }),
        focus: vi.fn(),
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
});
