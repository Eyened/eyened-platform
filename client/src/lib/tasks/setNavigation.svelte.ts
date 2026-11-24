import type { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import type { SaveTracker } from "$lib/saving/saveTracker.svelte";
import type { SubTaskState } from "../../types/openapi_types";
import { writeHandoff, type SetControl } from "./setHandoff";

export const STATUS_ID = "set-status";

/** Focus on the header's ◀, ▶, primary button or Set status ▾; without a primary button, an enabled ▶. */
export function focusSetControl(control: SetControl | "status"): void {
    const find = (c: SetControl | "status") =>
        c === "status"
            ? document.getElementById(STATUS_ID)
            : document.querySelector<HTMLElement>(`[data-set-control="${c}"]`);
    // After a lost Claim, or arriving by the primary move on a set that has none.
    const element =
        find(control) ?? (control === "primary" ? find("next") : null);
    if (element && !element.matches(":disabled")) element.focus();
}

/** True when everything saved within `ms`; false on a failure or when a save is still running. */
export async function flushWithin(
    tracker: SaveTracker,
    ms: number,
): Promise<boolean> {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const late = new Promise<"late">((resolve) => {
        timer = setTimeout(() => resolve("late"), ms);
    });
    try {
        // Twice: a stroke drawn during the first flush is still waiting after it.
        for (let pass = 0; pass < 2; pass++) {
            if ((await Promise.race([tracker.flushAll(), late])) === "late")
                return false;
            if (!tracker.firstUnsaved()) return true;
            if (tracker.savers.some((s) => s.state === "error")) return false;
        }
        return false;
    } finally {
        clearTimeout(timer);
    }
}

export interface SetNavigationDeps {
    tracker: SaveTracker;
    /** The set's status saver. */
    status: DebouncedSaver<SubTaskState>;
    /** This set's 0-based index and the task's set count. */
    index: number;
    count: number;
    /** The 0-based index the primary move goes to: the next open set, or null when none follows. */
    nextOpen: () => number | null;
    /** A page load to the set at this 0-based index. */
    navigate: (index: number) => void;
    /** The viewports the next set restores. */
    handoff: () => { selected: number; maximised: number | null };
    focus: (control: SetControl | "status") => void;
    /** The forms "Mark ready" warns about, read after the saves; none means no question. */
    incomplete?: () => string[];
}

/** ◀ ▶, "Mark ready and next", "Go to next set" and the last set's "Mark ready": saves first, one move at a time. */
export class SetNavigation {
    /** The control that shows its pending state, 1 s into the saves. */
    pending: SetControl | null = $state(null);
    /** Set by "Mark ready" on the last set. */
    lastReady = $state(false);
    /** The notification once "Mark ready" left nowhere to go. */
    get readyNotice(): { title: string; subtitle: string } | null {
        if (!this.lastReady) return null;
        const { index, count } = this.deps;
        return {
            title: `Set ${index + 1} marked ready`,
            subtitle:
                index >= count - 1
                    ? "This was the last set in this task."
                    : "No open sets after this one.",
        };
    }
    /** The last status save failed; the combo button shows it until a pick saves. */
    statusFailed = $state(false);
    /** The open "Leave set n without saving"; answerLeave answers it. */
    question: { markReady: boolean } | null = $state(null);
    /** The open "n forms aren't complete"; answerReady answers it. */
    readyQuestion: string[] | null = $state(null);
    /** A move is running, or the page load it started; Set status ▾ waits for it. */
    moving = $state(false);
    private answer: ((leave: boolean) => void) | null = null;
    private readyAnswer: ((go: boolean) => void) | null = null;

    constructor(private readonly deps: SetNavigationDeps) {}

    async move(
        control: SetControl,
        {
            markReady,
            reopenPanel,
        }: { markReady: boolean; reopenPanel?: "forms" },
    ): Promise<void> {
        if (this.moving) return;
        this.moving = true;
        const { tracker, index, count } = this.deps;
        // ◀ ▶ step by one; the primary move skips to the next open set.
        const to =
            control === "prev"
                ? index - 1
                : control === "next"
                  ? index + 1
                  : (this.deps.nextOpen() ?? count);
        const last = to >= count;
        const pendingTimer = setTimeout(() => (this.pending = control), 1000);
        try {
            const saved = await flushWithin(tracker, 5000);
            clearTimeout(pendingTimer);
            this.pending = null;
            if (!saved) {
                // On the last set there is nowhere to leave to, so no question.
                if (!last && (await this.ask(markReady)))
                    this.leave(control, to, reopenPanel);
                else this.revealUnsaved(control);
                return;
            }
            if (markReady) {
                // After the flush, so answers typed a moment ago count.
                const lines = this.deps.incomplete?.() ?? [];
                if (lines.length > 0 && !(await this.askReady(lines))) return;
                // A failure shows on the combo button; the grader stays.
                if (!(await this.saveStatus("Ready"))) return;
                // Work that became unsaved during the status save keeps the grader here.
                if (!last && tracker.firstUnsaved()) {
                    this.revealUnsaved(control);
                    return;
                }
            }
            if (last) {
                this.lastReady = true;
                this.deps.focus("status");
                return;
            }
            this.leave(control, to, reopenPanel);
        } finally {
            clearTimeout(pendingTimer);
            this.pending = null;
            // After a leave the page is loading; further presses stay ignored.
            if (!tracker.leaving) this.moving = false;
        }
    }

    /** Saves the set's status. A failure goes back to the saved value with nothing queued, so it never blocks or rides on a later move. */
    async saveStatus(state: SubTaskState): Promise<boolean> {
        const { status } = this.deps;
        status.edit(state);
        await status.flush();
        const ok = status.state !== "error";
        if (!ok) status.discard();
        this.statusFailed = !ok;
        return ok;
    }

    /** Leave, or Stay; the modal answers Stay once it has closed, so the focus move sticks. */
    answerLeave(leave: boolean): void {
        this.question = null;
        this.answer?.(leave);
        this.answer = null;
    }

    /** Mark ready anyway, or Go back with nothing changed. */
    answerReady(go: boolean): void {
        this.readyQuestion = null;
        this.readyAnswer?.(go);
        this.readyAnswer = null;
    }

    private askReady(lines: string[]): Promise<boolean> {
        this.readyQuestion = lines;
        return new Promise((resolve) => (this.readyAnswer = resolve));
    }

    private ask(markReady: boolean): Promise<boolean> {
        this.question = { markReady };
        return new Promise((resolve) => (this.answer = resolve));
    }

    private revealUnsaved(control: SetControl): void {
        const first = this.deps.tracker.firstUnsaved();
        if (first) this.deps.tracker.reveal(first);
        else this.deps.focus(control);
    }

    private leave(
        control: SetControl,
        to: number,
        reopenPanel?: "forms",
    ): void {
        this.deps.tracker.leaving = true;
        writeHandoff({ ...this.deps.handoff(), control, reopenPanel });
        this.deps.navigate(to);
    }
}
