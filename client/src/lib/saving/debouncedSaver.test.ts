import { ApiError } from "$lib/api/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DebouncedSaver } from "./debouncedSaver.svelte";
import { SaveTracker } from "./saveTracker.svelte";

/** A send whose replies the test settles one by one. */
function controlledSend() {
    const calls: { resolve: () => void; reject: (error: Error) => void }[] = [];
    const send = vi.fn(
        (_value: number) =>
            new Promise<void>((resolve, reject) =>
                calls.push({ resolve, reject }),
            ),
    );
    return { send, calls };
}

function saverWith(send: (value: number) => Promise<void>) {
    const onSaved = vi.fn();
    const saver = new DebouncedSaver<number>({
        kind: "form",
        group: "form-annotation-1",
        target: { to: "focus", focus: () => {} },
        delay: 0,
        send,
        onSaved,
        tracker: new SaveTracker(),
    });
    return { saver, onSaved };
}

const replies = () => new Promise((resolve) => setTimeout(resolve, 0));

afterEach(() => vi.restoreAllMocks());

describe("DebouncedSaver", () => {
    it("sends one edit at a time; of the edits that wait, only the newest goes next", async () => {
        const { send, calls } = controlledSend();
        const { saver } = saverWith(send);
        saver.edit(1);
        saver.edit(2);
        saver.edit(3);
        expect(send.mock.calls.map(([value]) => value)).toEqual([1]);
        calls[0].resolve();
        await replies();
        expect(send.mock.calls.map(([value]) => value)).toEqual([1, 3]);
    });

    it("an older reply doesn't write the store while a newer edit waits", async () => {
        const { send, calls } = controlledSend();
        const { saver, onSaved } = saverWith(send);
        saver.edit(1);
        saver.edit(2);
        calls[0].resolve();
        await replies();
        expect(onSaved).not.toHaveBeenCalled();
        calls[1].resolve();
        await replies();
        expect(onSaved.mock.calls).toEqual([[2]]);
        expect(saver.state).toBe("synced");
    });

    it("after an error, Retry sends the newest edit", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        const { send, calls } = controlledSend();
        const { saver } = saverWith(send);
        saver.edit(1);
        saver.edit(2);
        calls[0].reject(new Error("offline"));
        await replies();
        expect(saver.state).toBe("error");
        expect(send).toHaveBeenCalledTimes(1);
        void saver.flush();
        expect(send).toHaveBeenLastCalledWith(2);
    });

    it("flush() resolves when the save fails", async () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        const { send, calls } = controlledSend();
        const { saver } = saverWith(send);
        saver.edit(1);
        const flushed = saver.flush();
        calls[0].reject(new Error("offline"));
        await flushed;
        expect(saver.state).toBe("error");
    });

    it("a failed save logs the HTTP status, never what was being saved", async () => {
        const log = vi.spyOn(console, "error").mockImplementation(() => {});
        const saver = new DebouncedSaver<string>({
            kind: "comments",
            group: "comments",
            target: { to: "focus", focus: () => {} },
            delay: 0,
            send: () =>
                Promise.reject(
                    new ApiError(422, "Unprocessable", {
                        input: "Blurry OS, query drusen",
                    }),
                ),
            tracker: new SaveTracker(),
        });
        saver.edit("Blurry OS, query drusen");
        await saver.flush();
        expect(log).toHaveBeenCalledWith("Couldn't save the comments", 422);
        expect(JSON.stringify(log.mock.calls)).not.toContain("drusen");
    });
});
