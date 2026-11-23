import { ApiError } from "$lib/api/client";
import {
    saveTracker,
    type RevealTarget,
    type SaveKind,
    type SaveState,
    type Saver,
    type SaveTracker,
} from "./saveTracker.svelte";

export interface DebouncedSaverOptions<T> {
    kind: SaveKind;
    group: string;
    target: RevealTarget;
    /** Milliseconds after the last edit; 0 sends at once. */
    delay: number;
    send: (value: T) => Promise<unknown>;
    /** The store write; it runs only for the reply to the newest edit with nothing waiting. */
    onSaved?: (value: T) => void;
    tracker?: SaveTracker;
}

/** Saves the newest edit: one request in flight, and edits meanwhile collapse into the newest. */
export class DebouncedSaver<T> implements Saver {
    state: SaveState = $state("synced");
    readonly kind: SaveKind;
    readonly group: string;
    /** Replaced by each caller of a shared saver, so it names what is open now. */
    target: RevealTarget;
    private readonly tracker: SaveTracker;
    private readonly leave: () => void;
    private waiting: { value: T } | null = null;
    private sending = false;
    private timer: ReturnType<typeof setTimeout> | null = null;
    private idle: (() => void)[] = [];

    constructor(private readonly options: DebouncedSaverOptions<T>) {
        this.kind = options.kind;
        this.group = options.group;
        this.target = options.target;
        this.tracker = options.tracker ?? saveTracker;
        this.leave = this.tracker.join(this);
    }

    edit(value: T): void {
        this.tracker.edited = true;
        this.waiting = { value };
        this.state = "saving";
        this.clearTimer();
        if (this.options.delay === 0) {
            this.send();
            return;
        }
        this.timer = setTimeout(() => {
            this.timer = null;
            this.send();
        }, this.options.delay);
    }

    flush(): Promise<void> {
        this.clearTimer();
        this.send();
        if (!this.sending) return Promise.resolve();
        return new Promise((resolve) => this.idle.push(resolve));
    }

    /** Drops a failed value, so no later flush sends it again: the screen has already undone it. */
    discard(): void {
        this.clearTimer();
        this.waiting = null;
        if (!this.sending) this.state = "synced";
    }

    /** Leaves the tracker once what waits has been sent. */
    dispose(): void {
        void this.flush().then(this.leave);
    }

    private send(): void {
        if (this.sending || !this.waiting) return;
        const { value } = this.waiting;
        this.waiting = null;
        this.sending = true;
        this.state = "saving";
        this.options.send(value).then(
            () => {
                this.sending = false;
                if (this.waiting) {
                    // A newer edit waits; it goes now unless its delay is still running.
                    if (!this.timer) this.send();
                } else {
                    this.options.onSaved?.(value);
                    this.state = "synced";
                }
                // A flush resolves only when nothing is left to send; an edit still in its delay sends first.
                if (!this.sending && !this.waiting) this.settle();
            },
            (error: unknown) => {
                // Only the status: an error body can echo the value, and comments and answers are clinical text.
                console.error(
                    `Couldn't save the ${this.kind}`,
                    error instanceof ApiError ? error.status : "request failed",
                );
                this.sending = false;
                // Retry, or the next edit, sends the newest value.
                this.waiting ??= { value };
                this.state = "error";
                this.settle();
            },
        );
    }

    private settle(): void {
        const resolvers = this.idle;
        this.idle = [];
        for (const resolve of resolvers) resolve();
    }

    private clearTimer(): void {
        if (this.timer) clearTimeout(this.timer);
        this.timer = null;
    }
}
